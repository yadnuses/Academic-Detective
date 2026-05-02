#!/usr/bin/env python3
"""
clinical_trial_registry_checker.py

Check if clinical trials mentioned in papers are registered in public registries.
Extracts trial registry numbers and validates existence, timing, and result
reporting against publication metadata.

Supported sources (free APIs only):
    ClinicalTrials.gov API v2, ChiCTR (best-effort web search)

Usage:
    python clinical_trial_registry_checker.py --papers ./data/papers.json \
        --output ./data/trial_registry.json [--registry clinicaltrials.gov,chictr] [--verbose]

    python clinical_trial_registry_checker.py --trial-ids NCT04212345,ChiCTR2000034567 \
        --output ./data/trial_registry.json [--verbose]
"""

import json
import argparse
import urllib.request
import urllib.error
import urllib.parse
import re
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import Optional
import sys
import time

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.utils import get_logger, save_json

logger = get_logger("clinical_trial_registry_checker")

USER_AGENT = "AcademicInvestigationBot/3.0 (mailto:investigation@example.org)"
CT_GOV_API = "https://clinicaltrials.gov/api/v2/studies"
CHICTR_SEARCH = "http://www.chictr.org.cn/searchproj.aspx"

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class TrialRecord:
    trial_id: str
    registry: str                       # clinicaltrials.gov | chictr | unknown
    title: Optional[str] = None
    status: Optional[str] = None
    registration_date: Optional[str] = None
    start_date: Optional[str] = None
    completion_date: Optional[str] = None
    results_posted: bool = False
    url: Optional[str] = None
    source: str = "registry_api"


@dataclass
class TrialAlert:
    paper_id: str
    trial_id: str
    alert_type: str                   # unregistered_trial | late_registration | registration_date_mismatch | results_not_reported
    confidence: str                   # low | medium | high
    explanation: str
    paper_date: Optional[str] = None
    registry_date: Optional[str] = None


@dataclass
class PaperTrials:
    paper_id: str
    title: str
    detected_ids: list[str] = field(default_factory=list)
    records: list[TrialRecord] = field(default_factory=list)
    alerts: list[TrialAlert] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ID extraction
# ---------------------------------------------------------------------------

NCT_PATTERN = re.compile(r"NCT\d+", re.I)
CHICTR_PATTERN = re.compile(r"ChiCTR[\d\-]+", re.I)
OTHER_TRIAL_PATTERNS = [
    re.compile(r"ACTRN\d+", re.I),
    re.compile(r"UMIN\d+", re.I),
    re.compile(r"DRKS\d+", re.I),
    re.compile(r"ISRCTN\d+", re.I),
]


def extract_trial_ids(text: str) -> list[str]:
    """Extract all known trial registry IDs from text."""
    found: set[str] = set()
    for m in NCT_PATTERN.finditer(text):
        found.add(m.group(0).upper())
    for m in CHICTR_PATTERN.finditer(text):
        found.add(m.group(0))
    for pat in OTHER_TRIAL_PATTERNS:
        for m in pat.finditer(text):
            found.add(m.group(0).upper())
    return sorted(found)


# ---------------------------------------------------------------------------
# ClinicalTrials.gov v2 API
# ---------------------------------------------------------------------------

def query_clinicaltrials_gov(nct_id: str) -> Optional[TrialRecord]:
    """Query ClinicalTrials.gov API v2 for a single study."""
    url = f"{CT_GOV_API}/{urllib.parse.quote(nct_id)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            logger.debug("Trial %s not found on ClinicalTrials.gov", nct_id)
            return None
        logger.warning("ClinicalTrials.gov HTTP error for %s: %s", nct_id, exc)
        return None
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        logger.warning("ClinicalTrials.gov fetch failed for %s: %s", nct_id, exc)
        return None

    protocol = data.get("protocolSection", {})
    ident = protocol.get("identificationModule", {})
    status_mod = protocol.get("statusModule", {})
    sponsor = protocol.get("sponsorCollaboratorsModule", {})
    results = data.get("resultsSection", {})

    # Dates
    reg_date = None
    if status_mod.get("studyFirstSubmitDate"):
        reg_date = status_mod["studyFirstSubmitDate"]
    start_date = status_mod.get("startDateStruct", {}).get("date")
    completion_date = status_mod.get("completionDateStruct", {}).get("date")

    results_posted = bool(results)

    return TrialRecord(
        trial_id=nct_id,
        registry="clinicaltrials.gov",
        title=ident.get("briefTitle") or ident.get("officialTitle"),
        status=status_mod.get("overallStatus"),
        registration_date=reg_date,
        start_date=start_date,
        completion_date=completion_date,
        results_posted=results_posted,
        url=f"https://clinicaltrials.gov/study/{nct_id}",
    )


# ---------------------------------------------------------------------------
# ChiCTR best-effort
# ---------------------------------------------------------------------------

def query_chictr(trial_id: str) -> Optional[TrialRecord]:
    """Best-effort ChiCTR query via search page. Documented limitation: may be blocked."""
    # ChiCTR does not offer a stable public JSON API; attempt a simple GET search.
    query = urllib.parse.quote(trial_id)
    url = f"{CHICTR_SEARCH}?title={query}&pagenum=1"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        logger.warning("ChiCTR unreachable for %s: %s", trial_id, exc)
        return None

    # Heuristic: if the exact trial ID appears in the page title or results table,
    # assume it exists. We deliberately do not parse deep HTML to keep robustness.
    found = trial_id in html
    if not found:
        return None

    # Attempt to extract a title from page
    title = None
    title_match = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    if title_match:
        title_text = title_match.group(1).strip()
        if trial_id not in title_text:
            title = title_text

    return TrialRecord(
        trial_id=trial_id,
        registry="chictr",
        title=title,
        status=None,
        registration_date=None,
        start_date=None,
        completion_date=None,
        results_posted=False,
        url=f"http://www.chictr.org.cn/showproj.aspx?proj={trial_id}",
        source="chictr_heuristic",
    )


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(date_str[: len(fmt)], fmt)
        except ValueError:
            continue
    return None


def _days_diff(a: Optional[str], b: Optional[str]) -> Optional[int]:
    da = _parse_date(a)
    db = _parse_date(b)
    if da and db:
        return (db - da).days
    return None


# ---------------------------------------------------------------------------
# Alert generation
# ---------------------------------------------------------------------------

def generate_alerts(paper: dict, records: list[TrialRecord]) -> list[TrialAlert]:
    alerts = []
    paper_id = str(paper.get("id", paper.get("doi", "unknown")))
    paper_date = paper.get("date", paper.get("year", paper.get("publication_date", "")))

    detected_ids = extract_trial_ids(f"{paper.get('title', '')} {paper.get('abstract', '')} {paper.get('full_text', '')}")

    # Unregistered: IDs mentioned but no record found
    for tid in detected_ids:
        matched = [r for r in records if r.trial_id.upper() == tid.upper()]
        if not matched:
            alerts.append(TrialAlert(
                paper_id=paper_id,
                trial_id=tid,
                alert_type="unregistered_trial",
                confidence="high",
                explanation=f"论文提及试验注册号 {tid}，但在指定注册库中未检索到记录",
                paper_date=str(paper_date) if paper_date else None,
            ))

    for rec in records:
        if rec.registry == "clinicaltrials.gov":
            reg_date = rec.registration_date
            start = rec.start_date

            # Late registration: registration after start date
            if reg_date and start:
                diff = _days_diff(reg_date, start)
                if diff is not None and diff > 0:
                    alerts.append(TrialAlert(
                        paper_id=paper_id,
                        trial_id=rec.trial_id,
                        alert_type="registration_date_mismatch",
                        confidence="high",
                        explanation=f"注册日期({reg_date})晚于试验开始日期({start})",
                        registry_date=reg_date,
                    ))

            # Late registration relative to paper
            if paper_date and reg_date:
                pdt = _parse_date(str(paper_date))
                rdt = _parse_date(reg_date)
                if pdt and rdt and (pdt - rdt).days < 0:
                    alerts.append(TrialAlert(
                        paper_id=paper_id,
                        trial_id=rec.trial_id,
                        alert_type="late_registration",
                        confidence="medium",
                        explanation=f"论文发表日期({paper_date})早于试验注册日期({reg_date})",
                        paper_date=str(paper_date),
                        registry_date=reg_date,
                    ))

            # Results not reported
            if rec.status in ("Completed", "完成") and not rec.results_posted:
                alerts.append(TrialAlert(
                    paper_id=paper_id,
                    trial_id=rec.trial_id,
                    alert_type="results_not_reported",
                    confidence="medium",
                    explanation=f"试验状态为已完成，但尚未在注册库提交结果",
                    registry_date=reg_date,
                ))

    return alerts


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def process_papers(papers: list[dict], registries: list[str]) -> list[PaperTrials]:
    results: list[PaperTrials] = []
    cache: dict[str, Optional[TrialRecord]] = {}

    for paper in papers:
        paper_id = str(paper.get("id", paper.get("doi", "unknown")))
        title = str(paper.get("title", ""))
        text = f"{title} {paper.get('abstract', '')} {paper.get('full_text', '')}"
        detected_ids = extract_trial_ids(text)

        pt = PaperTrials(paper_id=paper_id, title=title, detected_ids=detected_ids)

        for tid in detected_ids:
            if tid in cache:
                rec = cache[tid]
            else:
                rec = None
                if tid.upper().startswith("NCT") and "clinicaltrials.gov" in registries:
                    rec = query_clinicaltrials_gov(tid.upper())
                    time.sleep(0.3)
                elif tid.startswith("ChiCTR") and "chictr" in registries:
                    rec = query_chictr(tid)
                    time.sleep(0.3)
                cache[tid] = rec

            if rec:
                pt.records.append(rec)

        pt.alerts = generate_alerts(paper, pt.records)
        results.append(pt)

    logger.info("Processed %d papers, queried %d unique trial IDs", len(results), len(cache))
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Clinical trial registry checker")
    p.add_argument("--papers", type=Path, help="Path to papers JSON file")
    p.add_argument("--trial-ids", help="Comma-separated list of trial registry numbers")
    p.add_argument("--output", type=Path, default=Path("./data/trial_registry.json"), help="Output JSON path")
    p.add_argument("--registry", default="clinicaltrials.gov,chictr",
                   help="Comma-separated registries to check")
    p.add_argument("--verbose", action="store_true", help="Verbose logging")
    return p


def main():
    args = build_parser().parse_args()
    if args.verbose:
        logger.setLevel("DEBUG")

    registries = [r.strip().lower() for r in args.registry.split(",")]
    logger.info("Checking registries: %s", registries)

    papers: list[dict] = []
    if args.papers and args.papers.exists():
        with open(args.papers, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        papers = raw if isinstance(raw, list) else raw.get("papers", [])
        logger.info("Loaded %d papers from %s", len(papers), args.papers)
    elif args.trial_ids:
        # Synthetic paper containing only trial IDs for direct lookup
        for tid in args.trial_ids.split(","):
            papers.append({"id": tid.strip(), "title": tid.strip(), "abstract": tid.strip()})
    else:
        logger.error("Must provide --papers or --trial-ids")
        sys.exit(1)

    paper_trials = process_papers(papers, registries)

    all_alerts = [a for pt in paper_trials for a in pt.alerts]

    def _alert_confidence(conf: str) -> float:
        return {"low": 0.3, "medium": 0.5, "high": 0.8}.get(conf, 0.5)

    signals = []
    for a in all_alerts:
        signals.append({
            "type": a.alert_type,
            "description": a.explanation[:200],
            "confidence": _alert_confidence(a.confidence),
            "paper_id": a.paper_id,
            "source": "clinical_trial_registry_checker",
            "evidence": {
                "trial_id": a.trial_id,
                "paper_date": a.paper_date,
                "registry_date": a.registry_date,
            },
        })

    result = {
        "meta": {
            "script": "clinical_trial_registry_checker",
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "input_file": str(args.papers) if args.papers else "trial_ids",
        },
        "signals": signals,
        "details": {
            "papers": [
                {
                    "paper_id": pt.paper_id,
                    "title": pt.title,
                    "detected_ids": pt.detected_ids,
                    "records": [asdict(r) for r in pt.records],
                    "alerts": [asdict(a) for a in pt.alerts],
                }
                for pt in paper_trials
            ],
            "summary": {
                "unregistered_trial": sum(1 for a in all_alerts if a.alert_type == "unregistered_trial"),
                "late_registration": sum(1 for a in all_alerts if a.alert_type == "late_registration"),
                "registration_date_mismatch": sum(1 for a in all_alerts if a.alert_type == "registration_date_mismatch"),
                "results_not_reported": sum(1 for a in all_alerts if a.alert_type == "results_not_reported"),
            },
        },
    }

    save_json(result, args.output)
    logger.info("Saved trial registry check to %s", args.output)

    print(f"\n{'='*60}")
    print("Clinical Trial Registry Checker Summary")
    print(f"{'='*60}")
    print(f"Papers checked:          {len(paper_trials)}")
    print(f"Total alerts:            {len(all_alerts)}")
    for k, v in result["summary"].items():
        print(f"  {k}: {v}")
    if all_alerts:
        print(f"\nTop alerts:")
        for a in all_alerts[:5]:
            print(f"  [{a.confidence.upper()}] {a.alert_type}: {a.explanation}")
    print(f"\nOutput:                  {args.output}")


if __name__ == "__main__":
    main()
