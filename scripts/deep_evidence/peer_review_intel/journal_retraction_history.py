#!/usr/bin/env python3
"""
journal_retraction_history.py

Analyze retraction history of journals where a target author publishes.
Uses PubMed E-utilities and optional local Retraction Watch CSV fallback.

Data sources:
    - PubMed E-utilities (free)
    - Crossref (is-retraction-of relation, best effort)
    - Optional local Retraction Watch CSV

Usage:
    python journal_retraction_history.py --papers ./data/papers.json \
        --output ./data/retraction_history.json

    python journal_retraction_history.py --issns 0028-0836 0140-6736 \
        --output ./data/retraction_history.json --years 5

    python journal_retraction_history.py --papers ./data/papers.json \
        --retraction-watch-csv ./data/retractionwatch.csv --output ./data/retraction_history.json
"""

import json
import argparse
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import Optional
import time
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.utils import get_logger, save_json

logger = get_logger("journal_retraction_history")
PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
CROSSREF_BASE = "https://api.crossref.org/works"
USER_AGENT = "AcademicInvestigationBot/3.0 (mailto:investigation@example.org)"

# Baseline retraction rate for STEM journals (~0.02%)
BASELINE_RETRACTION_RATE = 0.0002

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RetractionRecord:
    title: str
    doi: Optional[str]
    pmid: Optional[str]
    retraction_year: int
    reason: Optional[str]
    source: str


@dataclass
class JournalRetractionProfile:
    issn: str
    journal_name: str
    total_retractions: int
    retractions_last_n_years: int
    estimated_publications: int
    retraction_rate: float
    flagged: bool
    author_has_papers_here: bool
    author_retracted_papers: list[dict] = field(default_factory=list)
    retraction_records: list[RetractionRecord] = field(default_factory=list)
    common_reasons: dict[str, int] = field(default_factory=dict)
    source_note: str = ""


@dataclass
class RetractionAlert:
    journal_name: str
    issn: str
    alert_type: str
    confidence: str
    explanation: str


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------

def extract_issns_from_papers(papers: list[dict]) -> dict[str, str]:
    """Extract unique ISSNs mapped to journal names from paper list."""
    issn_map: dict[str, str] = {}
    for p in papers:
        issn = p.get("issn", p.get("ISSN", ""))
        if isinstance(issn, list):
            issn = issn[0] if issn else ""
        issn = (issn or "").strip().upper().replace("-", "")
        if not issn:
            continue
        journal = p.get("journal", p.get("container-title", "Unknown"))
        issn_map[issn] = journal
    return issn_map


def load_papers(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return raw if isinstance(raw, list) else raw.get("papers", [])


def _pubmed_fetch_ids(term: str, max_results: int = 1000, timeout: int = 20) -> list[str]:
    """Fetch PMIDs from PubMed esearch."""
    url = f"{PUBMED_ESEARCH}?db=pubmed&term={urllib.parse.quote(term)}&retmode=json&retmax={max_results}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            return data.get("esearchresult", {}).get("idlist", [])
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        logger.warning("PubMed ID fetch failed for term '%s': %s", term, exc)
        return []


def fetch_pubmed_retractions(journal_name: str, years: int) -> tuple[int, list[RetractionRecord]]:
    """Query PubMed for retracted publications in a journal."""
    cutoff = datetime.now().year - years
    term = f'"{journal_name}"[journal] retracted publication[pt]'
    pmids = _pubmed_fetch_ids(term)
    time.sleep(0.34)  # NCBI rate limit: ~3 requests/sec

    records: list[RetractionRecord] = []
    if not pmids:
        return 0, records

    # Fetch summaries for the first 50 PMIDs to keep requests reasonable
    batch = pmids[:50]
    id_str = ",".join(batch)
    url = f"{PUBMED_ESUMMARY}?db=pubmed&id={id_str}&retmode=json"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        logger.warning("PubMed summary fetch failed: %s", exc)
        return len(pmids), records

    result = data.get("result", {})
    for pmid in batch:
        doc = result.get(pmid, {})
        if not doc:
            continue
        year = doc.get("pubdate", "")[:4]
        try:
            year_int = int(year) if year.isdigit() else 0
        except ValueError:
            year_int = 0
        if year_int < cutoff:
            continue
        records.append(RetractionRecord(
            title=doc.get("title", ""),
            doi=None,
            pmid=pmid,
            retraction_year=year_int,
            reason=None,
            source="pubmed",
        ))

    time.sleep(0.34)
    return len(pmids), records


def fetch_crossref_retractions(issn: str, years: int) -> tuple[int, list[RetractionRecord]]:
    """Best-effort Crossref query for retractions by ISSN."""
    url = (
        f"{CROSSREF_BASE}?filter=issn:{urllib.parse.quote(issn)},type:retraction"
        f"&rows=200&sort=published-print&order=desc"
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        logger.warning("Crossref retraction query failed for ISSN %s: %s", issn, exc)
        return 0, []

    cutoff = datetime.now().year - years
    items = data.get("message", {}).get("items", [])
    records: list[RetractionRecord] = []
    for item in items:
        date_parts = item.get("published-print", {}).get("date-parts", [[]])[0]
        year = date_parts[0] if date_parts else 0
        if isinstance(year, int) and year >= cutoff:
            records.append(RetractionRecord(
                title=item.get("title", [""])[0] if isinstance(item.get("title"), list) else item.get("title", ""),
                doi=item.get("DOI"),
                pmid=None,
                retraction_year=year,
                reason=None,
                source="crossref",
            ))
    return len(items), records


def load_retraction_watch_csv(path: Path, issn: str, years: int) -> tuple[int, list[RetractionRecord]]:
    """Read retractions from a local Retraction Watch CSV."""
    import csv
    cutoff = datetime.now().year - years
    records: list[RetractionRecord] = []
    count = 0
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                row_issn = (row.get("ISSN", row.get("issn", "")) or "").replace("-", "").upper()
                if row_issn != issn:
                    continue
                count += 1
                year_str = row.get("RetractionYear", row.get("Year", row.get("year", "")))
                try:
                    year = int(year_str)
                except ValueError:
                    year = 0
                if year < cutoff:
                    continue
                records.append(RetractionRecord(
                    title=row.get("Title", row.get("title", "")),
                    doi=row.get("Doi", row.get("doi", None)) or None,
                    pmid=None,
                    retraction_year=year,
                    reason=row.get("Reason", row.get("reason", None)) or None,
                    source="retraction_watch_csv",
                ))
    except Exception as exc:
        logger.warning("Failed to parse Retraction Watch CSV: %s", exc)
    return count, records


def estimate_journal_publications(issn: str, journal_name: str) -> int:
    """Rough estimate of total publications from Crossref."""
    url = (
        f"{CROSSREF_BASE}?filter=issn:{urllib.parse.quote(issn)},from-pub-date:{datetime.now().year - 5}"
        f"&rows=0"
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
            return data.get("message", {}).get("total-results", 0)
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        logger.debug("Could not estimate publication volume for %s: %s", journal_name, exc)
        return 0


# ---------------------------------------------------------------------------
# Profile builder
# ---------------------------------------------------------------------------

def build_journal_profile(
    issn: str,
    journal_name: str,
    author_papers: list[dict],
    years: int,
    rw_csv: Optional[Path],
) -> tuple[JournalRetractionProfile, list[RetractionAlert]]:
    """Build a retraction risk profile for a single journal."""
    alerts: list[RetractionAlert] = []

    # Try sources in priority order
    total_retractions = 0
    recent_records: list[RetractionRecord] = []
    source_note = ""

    if rw_csv and rw_csv.exists():
        total_retractions, recent_records = load_retraction_watch_csv(rw_csv, issn, years)
        source_note = "retraction_watch_csv"
        logger.info("ISSN %s: loaded %d retractions from local CSV", issn, len(recent_records))

    if not recent_records:
        total_retractions, recent_records = fetch_pubmed_retractions(journal_name, years)
        source_note = "pubmed"
        if not recent_records:
            total_retractions, recent_records = fetch_crossref_retractions(issn, years)
            source_note = "crossref" if recent_records else "none"

    if source_note == "none":
        source_note = "data_incomplete: no data source returned retractions"

    est_publications = estimate_journal_publications(issn, journal_name)
    time.sleep(0.5)

    retraction_rate = (total_retractions / est_publications) if est_publications and est_publications > 0 else 0.0

    # Check if author has papers here
    author_here = any(
        (p.get("issn", p.get("ISSN", "")) or "").replace("-", "").upper() == issn
        for p in author_papers
    )

    # Check for author's own retracted papers
    author_retracted: list[dict] = []
    for p in author_papers:
        p_issn = (p.get("issn", p.get("ISSN", "")) or "").replace("-", "").upper()
        if p_issn == issn:
            # Heuristic: check if paper title matches any retraction record
            p_title = p.get("title", "").lower()
            for r in recent_records:
                if r.title and p_title in r.title.lower():
                    author_retracted.append({
                        "title": p.get("title", ""),
                        "doi": p.get("doi", p.get("DOI", None)),
                        "retraction_year": r.retraction_year,
                    })

    profile = JournalRetractionProfile(
        issn=issn,
        journal_name=journal_name,
        total_retractions=total_retractions,
        retractions_last_n_years=len(recent_records),
        estimated_publications=est_publications,
        retraction_rate=retraction_rate,
        flagged=retraction_rate > 0.001,
        author_has_papers_here=author_here,
        author_retracted_papers=author_retracted,
        retraction_records=recent_records,
        common_reasons={},
        source_note=source_note,
    )

    if retraction_rate > 0.001:
        alerts.append(RetractionAlert(
            journal_name=journal_name,
            issn=issn,
            alert_type="high_retraction_journal",
            confidence="high" if retraction_rate > 0.005 else "medium",
            explanation=f"撤稿率{retraction_rate:.3%}，远高于基线(~0.02%)，近{years}年撤稿{len(recent_records)}篇",
        ))

    if author_here and retraction_rate > 0.001:
        alerts.append(RetractionAlert(
            journal_name=journal_name,
            issn=issn,
            alert_type="author_published_in_retracted_journal",
            confidence="medium",
            explanation=f"作者在该高撤稿期刊({journal_name})有发表论文",
        ))

    if author_retracted:
        alerts.append(RetractionAlert(
            journal_name=journal_name,
            issn=issn,
            alert_type="author_has_retracted_paper",
            confidence="high",
            explanation=f"作者在该期刊有{len(author_retracted)}篇论文被撤稿",
        ))

    return profile, alerts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Journal retraction history analyzer")
    p.add_argument("--papers", type=Path, help="Path to papers.json")
    p.add_argument("--issns", nargs="+", help="List of journal ISSNs")
    p.add_argument("--output", type=Path, default=Path("./data/retraction_history.json"))
    p.add_argument("--years", type=int, default=5, help="Lookback period in years")
    p.add_argument("--retraction-watch-csv", type=Path, help="Path to local Retraction Watch CSV")
    p.add_argument("--verbose", action="store_true")
    return p


def main():
    args = build_parser().parse_args()
    if args.verbose:
        logger.setLevel("DEBUG")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    if args.papers and not args.papers.exists():
        logger.error("Input file not found: %s", args.papers)
        sys.exit(1)
    if args.retraction_watch_csv and not args.retraction_watch_csv.exists():
        logger.error("Input file not found: %s", args.retraction_watch_csv)
        sys.exit(1)

    if not args.papers and not args.issns:
        logger.error("Either --papers or --issns must be provided")
        sys.exit(1)

    author_papers: list[dict] = []
    issn_map: dict[str, str] = {}

    if args.papers and args.papers.exists():
        author_papers = load_papers(args.papers)
        issn_map = extract_issns_from_papers(author_papers)
        logger.info("Extracted %d unique ISSNs from %d papers", len(issn_map), len(author_papers))

    if args.issns:
        for issn in args.issns:
            clean = issn.strip().upper().replace("-", "")
            if clean not in issn_map:
                issn_map[clean] = "Unknown"

    if not issn_map:
        logger.error("No ISSNs found to analyze")
        sys.exit(1)

    profiles: list[JournalRetractionProfile] = []
    all_alerts: list[RetractionAlert] = []

    for idx, (issn, journal_name) in enumerate(issn_map.items()):
        profile, alerts = build_journal_profile(issn, journal_name, author_papers, args.years, args.retraction_watch_csv)
        profiles.append(profile)
        all_alerts.extend(alerts)
        if idx < len(issn_map) - 1:
            time.sleep(0.5)

    type_map = {
        "high_retraction_journal": "high_retraction_journal",
        "author_published_in_retracted_journal": "author_paper_retracted",
        "author_has_retracted_paper": "author_paper_retracted",
    }
    signals = []
    for a in all_alerts:
        conf = 0.7 if a.alert_type == "high_retraction_journal" else 0.9
        signals.append({
            "type": type_map.get(a.alert_type, a.alert_type),
            "description": a.explanation,
            "confidence": conf,
            "paper_id": a.issn or a.journal_name,
            "source": "journal_retraction_history",
            "evidence": {
                "journal_name": a.journal_name,
                "issn": a.issn,
            },
        })

    result = {
        "meta": {
            "script": "journal_retraction_history",
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "input_file": str(args.papers) if args.papers else "",
        },
        "signals": signals,
        "details": {
            "profiles": [asdict(p) for p in profiles],
            "alerts": [asdict(a) for a in all_alerts],
        },
    }

    save_json(result, args.output)
    logger.info("Saved retraction history to %s", args.output)

    print(f"\n{'='*60}")
    print(f"Journal Retraction History Summary")
    print(f"{'='*60}")
    print(f"Journals analyzed: {len(issn_map)}")
    print(f"High-risk journals:{sum(1 for p in profiles if p.flagged)}")
    print(f"Signals:           {len(signals)}")
    if signals:
        print(f"\nTop signals:")
        for s in signals[:5]:
            print(f"  [{s['confidence']}] {s['type']}: {s['description']}")
    print(f"\nOutput:            {args.output}")


if __name__ == "__main__":
    main()
