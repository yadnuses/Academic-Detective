#!/usr/bin/env python3
"""
crossref_event_tracker.py

Track Crossref Event Data for papers to assess unusual attention patterns.
Detects:
- Coordinated promotion (suspicious attention spike near publication)
- High social media mentions with low academic citations
- Unusually early policy document citations

Data source: Crossref Event Data API (free, no key required)

Usage:
    python crossref_event_tracker.py --papers ./data/papers.json \
        --output ./data/crossref_events.json

    python crossref_event_tracker.py --dois ./data/dois.txt \
        --output ./data/crossref_events.json --delay 1.0
"""

import json
import argparse
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from typing import Optional
import time
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.utils import get_logger, save_json

logger = get_logger("crossref_event_tracker")
EVENTDATA_BASE = "https://api.eventdata.crossref.org/v1/events"
USER_AGENT = "AcademicInvestigationBot/3.0 (mailto:investigation@example.org)"

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class EventSummary:
    doi: str
    total_events: int = 0
    citations: int = 0
    mentions: int = 0
    social_media: int = 0
    news: int = 0
    policy_documents: int = 0
    other: int = 0
    first_event_date: Optional[str] = None
    last_event_date: Optional[str] = None
    events_near_publication: int = 0
    temporal_spread_days: Optional[int] = None
    flags: list[str] = field(default_factory=list)
    source: str = "crossref_eventdata"


@dataclass
class EventAlert:
    doi: str
    alert_type: str
    confidence: str
    explanation: str


# ---------------------------------------------------------------------------
# Crossref Event Data fetcher
# ---------------------------------------------------------------------------

def fetch_events(doi: str, timeout: int = 20) -> list[dict]:
    """Query Crossref Event Data API for a single DOI."""
    url = f"{EVENTDATA_BASE}?obj.id={urllib.parse.quote(doi, safe='')}&rows=10000"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        logger.warning("Event Data API failed for DOI %s: %s", doi, exc)
        return []

    return data.get("message", {}).get("events", [])


def classify_event(event: dict) -> str:
    """Classify an event into a high-level category."""
    source = (event.get("source_id") or "").lower()
    relation = (event.get("subj", {}).get("type") or "").lower()

    if source in ("crossref", "datacite"):
        return "citations"
    if source in ("twitter", "facebook", "reddit", "wikipedia", "web"):
        return "social_media"
    if source in ("newsfeed", "news") or "news" in source:
        return "news"
    if source in ("hypothesis") or "mention" in source:
        return "mentions"
    if source in ("policy") or "policy" in source:
        return "policy_documents"
    return "other"


def parse_event_date(event: dict) -> Optional[datetime]:
    """Extract the event timestamp."""
    ts = event.get("occurred_at") or event.get("timestamp")
    if not ts:
        return None
    try:
        return datetime.strptime(ts[:10], "%Y-%m-%d")
    except ValueError:
        return None


def analyze_doi(doi: str, publication_date: Optional[str], delay: float) -> tuple[EventSummary, list[EventAlert]]:
    """Fetch and analyze events for a single DOI."""
    events = fetch_events(doi)
    time.sleep(delay)

    summary = EventSummary(doi=doi)
    alerts: list[EventAlert] = []

    if not events:
        logger.info("No events found for DOI %s", doi)
        return summary, alerts

    summary.total_events = len(events)
    dates: list[datetime] = []

    for ev in events:
        category = classify_event(ev)
        if category == "citations":
            summary.citations += 1
        elif category == "mentions":
            summary.mentions += 1
        elif category == "social_media":
            summary.social_media += 1
        elif category == "news":
            summary.news += 1
        elif category == "policy_documents":
            summary.policy_documents += 1
        else:
            summary.other += 1

        ev_date = parse_event_date(ev)
        if ev_date:
            dates.append(ev_date)

    if dates:
        dates.sort()
        summary.first_event_date = dates[0].strftime("%Y-%m-%d")
        summary.last_event_date = dates[-1].strftime("%Y-%m-%d")
        summary.temporal_spread_days = (dates[-1] - dates[0]).days

    # Temporal analysis relative to publication
    if publication_date and dates:
        try:
            pub_dt = datetime.strptime(publication_date, "%Y-%m-%d")
            window_end = pub_dt + timedelta(days=7)
            near_count = sum(1 for d in dates if pub_dt <= d <= window_end)
            summary.events_near_publication = near_count

            if summary.total_events > 10 and near_count / summary.total_events > 0.5:
                summary.flags.append("suspicious_attention_spike")
                alerts.append(EventAlert(
                    doi=doi,
                    alert_type="suspicious_attention_spike",
                    confidence="high" if near_count / summary.total_events > 0.7 else "medium",
                    explanation=f"发表后7天内集中出现{near_count}条事件记录，占总事件数{summary.total_events}的{near_count/summary.total_events:.1%}，疑似协调推广",
                ))
        except ValueError:
            pass

    # Zero citations but high mentions
    if summary.total_events > 20 and summary.citations == 0 and summary.social_media > 10:
        summary.flags.append("zero_citations_high_mentions")
        alerts.append(EventAlert(
            doi=doi,
            alert_type="zero_citations_high_mentions",
            confidence="medium",
            explanation=f"社交媒体关注度高({summary.social_media}条)但学术引用为零，可能存在非学术推广",
        ))

    # Policy citation anomaly
    if summary.policy_documents > 0 and publication_date:
        try:
            pub_dt = datetime.strptime(publication_date, "%Y-%m-%d")
            policy_dates = [d for d in dates if d > pub_dt]
            if policy_dates:
                earliest_policy = min(policy_dates)
                days_to_policy = (earliest_policy - pub_dt).days
                if days_to_policy < 30:
                    summary.flags.append("policy_citation_anomaly")
                    alerts.append(EventAlert(
                        doi=doi,
                        alert_type="policy_citation_anomaly",
                        confidence="medium",
                        explanation=f"发表后仅{days_to_policy}天即被政策文件引用，时间过短",
                    ))
        except ValueError:
            pass

    logger.info("DOI %s: %d events, flags=%s", doi, summary.total_events, summary.flags)
    return summary, alerts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def load_dois_from_papers(path: Path) -> list[dict]:
    """Load DOIs and publication dates from papers JSON."""
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    papers = raw if isinstance(raw, list) else raw.get("papers", [])
    results = []
    for p in papers:
        doi = p.get("doi", p.get("DOI", ""))
        if doi:
            results.append({
                "doi": doi,
                "publication_date": p.get("date", p.get("year", p.get("published", ""))),
            })
    return results


def load_dois_from_file(path: Path) -> list[dict]:
    """Load DOIs from a text file, one per line."""
    dois = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                dois.append({"doi": line, "publication_date": None})
    return dois


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Crossref Event Data tracker for attention pattern analysis")
    p.add_argument("--papers", type=Path, help="Path to papers.json with DOI and date fields")
    p.add_argument("--dois", type=Path, help="Path to text file with one DOI per line")
    p.add_argument("--output", type=Path, default=Path("./data/crossref_events.json"))
    p.add_argument("--delay", type=float, default=1.0, help="Seconds between API calls")
    p.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    return p


def main():
    args = build_parser().parse_args()
    if args.verbose:
        logger.setLevel("DEBUG")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    if not args.papers and not args.dois:
        logger.error("Either --papers or --dois must be provided")
        sys.exit(1)

    doi_entries = []
    if args.papers and args.papers.exists():
        doi_entries = load_dois_from_papers(args.papers)
    elif args.dois and args.dois.exists():
        doi_entries = load_dois_from_file(args.dois)
    else:
        logger.error("Input file not found")
        sys.exit(1)

    logger.info("Loaded %d DOIs to query", len(doi_entries))

    summaries: list[EventSummary] = []
    all_alerts: list[EventAlert] = []

    for idx, entry in enumerate(doi_entries):
        doi = entry["doi"]
        pub_date = entry.get("publication_date")
        # Normalize publication date to YYYY-MM-DD if possible
        if pub_date and isinstance(pub_date, str):
            if len(pub_date) == 4:
                pub_date = f"{pub_date}-01-01"
            elif len(pub_date) == 7:
                pub_date = f"{pub_date}-01"

        summary, alerts = analyze_doi(doi, pub_date, args.delay)
        summaries.append(summary)
        all_alerts.extend(alerts)

        if idx < len(doi_entries) - 1:
            time.sleep(args.delay)

    def _alert_confidence(conf: str) -> float:
        return {"low": 0.3, "medium": 0.5, "high": 0.8}.get(conf, 0.5)

    signals = []
    for a in all_alerts:
        signals.append({
            "type": a.alert_type,
            "description": a.explanation[:200],
            "confidence": _alert_confidence(a.confidence),
            "paper_id": a.doi,
            "source": "crossref_event_tracker",
            "evidence": {
                "doi": a.doi,
            },
        })

    result = {
        "meta": {
            "script": "crossref_event_tracker",
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "input_file": str(args.papers) if args.papers else str(args.dois),
        },
        "signals": signals,
        "details": {
            "summaries": [asdict(s) for s in summaries],
            "alerts": [asdict(a) for a in all_alerts],
        },
    }

    save_json(result, args.output)
    logger.info("Saved results to %s", args.output)

    print(f"\n{'='*60}")
    print(f"Crossref Event Tracker Summary")
    print(f"{'='*60}")
    print(f"DOIs queried:     {len(doi_entries)}")
    print(f"Total events:     {result['meta']['total_events']}")
    print(f"Alerts:           {len(all_alerts)}")
    if all_alerts:
        print(f"\nTop alerts:")
        for a in all_alerts[:5]:
            print(f"  [{a.confidence.upper()}] {a.alert_type}: {a.explanation}")
    print(f"\nOutput:           {args.output}")


if __name__ == "__main__":
    main()
