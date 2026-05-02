#!/usr/bin/env python3
"""
review_cycle_analyzer.py

Analyze publication timeline anomalies using free Crossref metadata.
Detects:
- Unusually short submission-to-publication intervals per journal
- Abnormally high publication velocity in single journal windows
- Batch acceptance patterns (multiple papers accepted within days)
- Journal-level vs author-level cycle benchmarking

Data source: Crossref API (free, no key required for basic usage)

Usage:
    python review_cycle_analyzer.py --papers ./data/unified_papers.json \
        --output ./data/cycle_analysis.json

    python review_cycle_analyzer.py --papers ./data/unified_papers.json \
        --journal-benchmarks ./data/journal_benchmarks.json \
        --output ./data/cycle_analysis.json
"""

import json
import argparse
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional
import statistics
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.utils import get_logger, save_json

logger = get_logger("review_cycle_analyzer")
CROSSREF_BASE = "https://api.crossref.org/works"
USER_AGENT = "AcademicInvestigationBot/3.0 (mailto:investigation@example.org)"

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class PaperTimeline:
    doi: Optional[str]
    title: str
    journal: str
    issn: Optional[str]
    published_date: Optional[str]   # YYYY-MM-DD
    received_date: Optional[str]    # from Crossref if available
    accepted_date: Optional[str]    # from Crossref if available
    created_date: Optional[str]     # Crossref record creation
    deposited_date: Optional[str]   # Crossref deposit
    cycle_days: Optional[int]       # accepted -> published (or best proxy)
    source: str = "crossref"


@dataclass
class JournalBenchmark:
    issn: str
    journal_name: str
    avg_cycle_days: Optional[float]
    median_cycle_days: Optional[float]
    std_cycle_days: Optional[float]
    sample_size: int
    source: str = "crossref_proxy"


@dataclass
class CycleAlert:
    paper_title: str
    journal: str
    cycle_days: int
    benchmark_median: Optional[float]
    deviation_factor: Optional[float]
    alert_type: str     # fast_cycle | batch_acceptance | high_velocity
    confidence: str     # low | medium | high
    explanation: str


# ---------------------------------------------------------------------------
# Crossref fetcher
# ---------------------------------------------------------------------------

def fetch_work(doi: str, timeout: int = 15) -> dict:
    """Fetch a single work from Crossref API."""
    url = f"{CROSSREF_BASE}/{urllib.parse.quote(doi, safe='')}" if doi.startswith("10.") else f"{CROSSREF_BASE}/{urllib.parse.quote(doi, safe='')}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read()).get("message", {})
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        logger.warning("Crossref fetch failed for DOI %s: %s", doi, exc)
        return {}


def parse_crossref_dates(msg: dict) -> dict:
    """Extract relevant dates from Crossref work message."""
    dates = {
        "published_print": None,
        "published_online": None,
        "created": None,
        "deposited": None,
        "received": None,
        "accepted": None,
    }

    # published-print / published-online
    pp = msg.get("published-print", {})
    if pp and pp.get("date-parts"):
        parts = pp["date-parts"][0]
        dates["published_print"] = _parts_to_iso(parts)

    po = msg.get("published-online", {})
    if po and po.get("date-parts"):
        parts = po["date-parts"][0]
        dates["published_online"] = _parts_to_iso(parts)

    # created (Crossref record creation)
    created = msg.get("created", {})
    if created and created.get("date-time"):
        dates["created"] = created["date-time"][:10]
    elif created and created.get("date-parts"):
        dates["created"] = _parts_to_iso(created["date-parts"][0])

    # deposited
    dep = msg.get("deposited", {})
    if dep and dep.get("date-time"):
        dates["deposited"] = dep["date-time"][:10]

    # Some publishers include received/accepted in Crossref via updates
    # Crossref does not standardize these, but we check anyway
    for relation in msg.get("relation", {}).values():
        if isinstance(relation, list):
            for r in relation:
                if isinstance(r, dict):
                    id_type = r.get("id-type", "").lower()
                    if "received" in id_type:
                        dates["received"] = r.get("asserted", "")[:10]
                    if "accepted" in id_type:
                        dates["accepted"] = r.get("asserted", "")[:10]

    return dates


def _parts_to_iso(parts: list) -> Optional[str]:
    """Convert Crossref date-parts [YYYY, MM, DD] to ISO string."""
    if not parts:
        return None
    y = parts[0]
    m = parts[1] if len(parts) > 1 else 1
    d = parts[2] if len(parts) > 2 else 1
    try:
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    except (ValueError, TypeError):
        return None


def compute_proxy_cycle(dates: dict) -> Optional[int]:
    """Compute best-available proxy for submission-to-publication cycle."""
    # Ideal: accepted -> published-print
    if dates.get("accepted") and dates.get("published_print"):
        try:
            a = datetime.strptime(dates["accepted"], "%Y-%m-%d")
            p = datetime.strptime(dates["published_print"], "%Y-%m-%d")
            return (p - a).days
        except ValueError:
            pass

    # Fallback: created -> published-print (proxy for editorial pipeline)
    if dates.get("created") and dates.get("published_print"):
        try:
            c = datetime.strptime(dates["created"], "%Y-%m-%d")
            p = datetime.strptime(dates["published_print"], "%Y-%m-%d")
            diff = (p - c).days
            if 0 < diff < 1500:
                return diff
        except ValueError:
            pass

    # Fallback 2: deposited -> published-print
    if dates.get("deposited") and dates.get("published_print"):
        try:
            d = datetime.strptime(dates["deposited"], "%Y-%m-%d")
            p = datetime.strptime(dates["published_print"], "%Y-%m-%d")
            diff = (p - d).days
            if 0 < diff < 1500:
                return diff
        except ValueError:
            pass

    return None


# ---------------------------------------------------------------------------
# Journal benchmark builder
# ---------------------------------------------------------------------------

def build_journal_benchmark(issn: str, sample_size: int = 50) -> Optional[JournalBenchmark]:
    """Query Crossref for recent papers in a journal to establish benchmark."""
    url = (
        f"{CROSSREF_BASE}?filter=issn:{urllib.parse.quote(issn)}"
        f"&rows={sample_size}&sort=published-print&order=desc"
        f"&select=DOI,published-print,created,deposited,accepted"
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    cycles = []
    journal_name = ""
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        logger.warning("Crossref benchmark query failed for ISSN %s: %s", issn, exc)
        return None

    items = data.get("message", {}).get("items", [])
    for item in items:
        if not journal_name:
            journal_name = item.get("container-title", [""])[0]
        dates = parse_crossref_dates(item)
        cycle = compute_proxy_cycle(dates)
        if cycle is not None and 7 <= cycle <= 730:  # 1 week to 2 years
            cycles.append(cycle)

    if len(cycles) < 5:
        logger.info("Insufficient cycle data for ISSN %s (%d samples)", issn, len(cycles))
        return None

    return JournalBenchmark(
        issn=issn,
        journal_name=journal_name,
        avg_cycle_days=statistics.mean(cycles),
        median_cycle_days=statistics.median(cycles),
        std_cycle_days=statistics.stdev(cycles) if len(cycles) > 1 else 0,
        sample_size=len(cycles),
    )


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

def detect_anomalies(timelines: list[PaperTimeline], benchmarks: dict[str, JournalBenchmark]) -> list[CycleAlert]:
    alerts = []

    # Group by journal
    by_journal: dict[str, list[PaperTimeline]] = {}
    for pt in timelines:
        key = pt.issn or pt.journal
        by_journal.setdefault(key, []).append(pt)

    for issn, papers in by_journal.items():
        bench = benchmarks.get(issn)
        papers_sorted = sorted([p for p in papers if p.published_date], key=lambda x: x.published_date or "")

        # Alert 1: Fast cycle per paper
        for pt in papers_sorted:
            if pt.cycle_days is None or pt.cycle_days <= 0:
                continue
            median = bench.median_cycle_days if bench else None
            if median and median > 0:
                factor = median / pt.cycle_days  # >2 means 2x faster than median
                if factor >= 2.0:
                    alerts.append(CycleAlert(
                        paper_title=pt.title,
                        journal=pt.journal,
                        cycle_days=pt.cycle_days,
                        benchmark_median=median,
                        deviation_factor=factor,
                        alert_type="fast_cycle",
                        confidence="high" if factor >= 3.0 else "medium",
                        explanation=f"发表周期{pt.cycle_days}天，为该期刊中位数({median:.0f}天)的{factor:.1f}倍速",
                    ))

        # Alert 2: Batch acceptance (multiple papers within 7 days)
        dates_only = [p.published_date for p in papers_sorted if p.published_date]
        for i in range(len(dates_only) - 1):
            window = [dates_only[i]]
            for j in range(i + 1, len(dates_only)):
                d1 = datetime.strptime(dates_only[i], "%Y-%m-%d")
                d2 = datetime.strptime(dates_only[j], "%Y-%m-%d")
                if (d2 - d1).days <= 7:
                    window.append(dates_only[j])
                else:
                    break
            if len(window) >= 3:
                alerts.append(CycleAlert(
                    paper_title=",".join([p.title for p in papers_sorted if p.published_date in window][:2]) + "...",
                    journal=papers_sorted[0].journal if papers_sorted else "",
                    cycle_days=0,
                    benchmark_median=None,
                    deviation_factor=None,
                    alert_type="batch_acceptance",
                    confidence="medium",
                    explanation=f"{len(window)}篇论文在7天窗口内见刊 ({window[0]} 至 {window[-1]})",
                ))
                break  # only one batch alert per journal

        # Alert 3: High velocity (>=4 papers in same journal in 12 months)
        if len(papers_sorted) >= 4:
            for i in range(len(papers_sorted)):
                d_i = datetime.strptime(papers_sorted[i].published_date, "%Y-%m-%d")
                count = 1
                for j in range(i + 1, len(papers_sorted)):
                    d_j = datetime.strptime(papers_sorted[j].published_date, "%Y-%m-%d")
                    if (d_j - d_i).days <= 365:
                        count += 1
                    else:
                        break
                if count >= 4:
                    alerts.append(CycleAlert(
                        paper_title=papers_sorted[i].title,
                        journal=papers_sorted[i].journal,
                        cycle_days=0,
                        benchmark_median=None,
                        deviation_factor=None,
                        alert_type="high_velocity",
                        confidence="medium",
                        explanation=f"12个月内在该期刊发表{count}篇论文",
                    ))
                    break

    return alerts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Review cycle analyzer using Crossref metadata")
    p.add_argument("--papers", type=Path, required=True, help="Path to unified_papers.json")
    p.add_argument("--output", type=Path, default=Path("./data/cycle_analysis.json"))
    p.add_argument("--journal-benchmarks", type=Path, help="Path to cached journal_benchmarks.json")
    p.add_argument("--save-benchmarks", type=Path, help="Save fetched benchmarks to this path")
    p.add_argument("--sample-size", type=int, default=50, help="Papers per journal for benchmark")
    p.add_argument("--delay", type=float, default=0.5, help="Seconds between Crossref requests")
    p.add_argument("--verbose", action="store_true")
    return p


def main():
    args = build_parser().parse_args()
    if args.verbose:
        logger.setLevel("DEBUG")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    if not args.papers.exists():
        logger.error("Input file not found: %s", args.papers)
        sys.exit(1)

    # Load paper list
    with open(args.papers, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    paper_list = raw if isinstance(raw, list) else raw.get("papers", [])
    logger.info("Loaded %d papers", len(paper_list))

    # Fetch Crossref metadata for each paper
    timelines: list[PaperTimeline] = []
    import time
    for idx, paper in enumerate(paper_list):
        doi = paper.get("doi", paper.get("DOI", ""))
        if not doi:
            logger.debug("Skipping paper without DOI: %s", paper.get("title", "")[:60])
            continue

        msg = fetch_work(doi)
        if not msg:
            continue

        dates = parse_crossref_dates(msg)
        cycle = compute_proxy_cycle(dates)

        issns = msg.get("ISSN", [])
        issn = issns[0] if issns else None
        journal_name = msg.get("container-title", [""])[0] if msg.get("container-title") else paper.get("journal", "")

        pt = PaperTimeline(
            doi=doi,
            title=paper.get("title", msg.get("title", [""])[0] if isinstance(msg.get("title"), list) else msg.get("title", "")),
            journal=journal_name,
            issn=issn,
            published_date=dates.get("published_print") or dates.get("published_online"),
            received_date=dates.get("received"),
            accepted_date=dates.get("accepted"),
            created_date=dates.get("created"),
            deposited_date=dates.get("deposited"),
            cycle_days=cycle,
        )
        timelines.append(pt)

        if idx < len(paper_list) - 1:
            time.sleep(args.delay)

    logger.info("Retrieved Crossref metadata for %d/%d papers", len(timelines), len(paper_list))

    # Build / load journal benchmarks
    benchmarks: dict[str, JournalBenchmark] = {}
    if args.journal_benchmarks and args.journal_benchmarks.exists():
        with open(args.journal_benchmarks, "r", encoding="utf-8") as fh:
            for b in json.load(fh):
                benchmarks[b["issn"]] = JournalBenchmark(**b)
        logger.info("Loaded %d cached benchmarks", len(benchmarks))

    # Fetch missing benchmarks
    needed_issns = {pt.issn for pt in timelines if pt.issn and pt.issn not in benchmarks}
    for issn in needed_issns:
        bench = build_journal_benchmark(issn, args.sample_size)
        if bench:
            benchmarks[issn] = bench
            time.sleep(args.delay)

    if args.save_benchmarks:
        save_json([asdict(b) for b in benchmarks.values()], args.save_benchmarks)
        logger.info("Saved %d benchmarks to %s", len(benchmarks), args.save_benchmarks)

    # Detect anomalies
    alerts = detect_anomalies(timelines, benchmarks)

    confidence_map = {
        "fast_cycle": 0.7,
        "batch_acceptance": 0.8,
        "high_velocity": 0.75,
    }
    signals = []
    for a in alerts:
        signals.append({
            "type": a.alert_type,
            "description": a.explanation,
            "confidence": confidence_map.get(a.alert_type, 0.7),
            "paper_id": a.paper_title,
            "source": "review_cycle_analyzer",
            "evidence": {
                "cycle_days": a.cycle_days,
                "benchmark_median": a.benchmark_median,
                "deviation_factor": a.deviation_factor,
                "journal": a.journal,
            },
        })

    result = {
        "meta": {
            "script": "review_cycle_analyzer",
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "input_file": str(args.papers),
        },
        "signals": signals,
        "details": {
            "timelines": [asdict(t) for t in timelines],
            "benchmarks": {k: asdict(v) for k, v in benchmarks.items()},
            "alerts": [asdict(a) for a in alerts],
        },
    }

    save_json(result, args.output)
    logger.info("Saved cycle analysis to %s", args.output)

    # Summary
    print(f"\n{'='*60}")
    print(f"Review Cycle Analysis Summary")
    print(f"{'='*60}")
    print(f"Papers queried:     {len(paper_list)}")
    print(f"Crossref hits:      {len(timelines)}")
    print(f"Benchmarked:        {len(benchmarks)} journals")
    print(f"Signals:            {len(signals)}")
    if signals:
        print(f"\nTop signals:")
        for s in signals[:5]:
            print(f"  [{s['confidence']}] {s['type']}: {s['description']}")
    print(f"\nOutput:             {args.output}")


if __name__ == "__main__":
    main()
