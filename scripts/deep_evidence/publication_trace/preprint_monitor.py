#!/usr/bin/env python3
"""
preprint_monitor.py

Monitor preprint servers for a target author and detect publication anomalies:
- Preprint submission date vs journal submission date overlap (duplicate submission)
- Preprint rejected but content re-submitted elsewhere without update
- Content fragmentation across multiple outlets

Supported sources (free APIs only):
    arXiv, bioRxiv, medRxiv, ChemRxiv

Usage:
    python preprint_monitor.py --name "张三" --arxiv-name "Zhang San" \
        --journal-papers ./data/unified_papers.json --output ./data/preprints.json

    python preprint_monitor.py --orcid 0000-0001-2345-6789 --output ./data/preprints.json
"""

import json
import argparse
import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict
import sys
import difflib

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.utils import get_logger, save_json

logger = get_logger("preprint_monitor")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class PreprintRecord:
    source: str           # arxiv | biorxiv | medrxiv | chemrxiv
    title: str
    authors: list[str]
    submit_date: str      # ISO date YYYY-MM-DD
    url: str
    doi: Optional[str]
    abstract: Optional[str]
    version_count: int = 1
    journal_doi: Optional[str] = None  # linked journal pub, if known
    category: Optional[str] = None


@dataclass
class OverlapAlert:
    preprint_title: str
    preprint_date: str
    journal_title: str
    journal_date: str
    overlap_type: str     # duplicate_submission | content_reuse | suspicious_gap
    confidence: str       # low | medium | high
    explanation: str


# ---------------------------------------------------------------------------
# arXiv fetcher
# ---------------------------------------------------------------------------

ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def fetch_arxiv(author_query: str, max_results: int = 100) -> list[PreprintRecord]:
    """Query arXiv API for an author."""
    url = (
        "http://export.arxiv.org/api/query?"
        f"search_query=au:{urllib.parse.quote(author_query)}"
        f"&start=0&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"
    )
    records = []
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        logger.warning("arXiv API unreachable: %s", exc)
        return records

    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        logger.warning("arXiv XML parse error: %s", exc)
        return records

    for entry in root.findall("atom:entry", ARXIV_NS):
        title = entry.findtext("atom:title", "", ARXIV_NS).replace("\n", " ").strip()
        authors = [
            a.findtext("atom:name", "", ARXIV_NS)
            for a in entry.findall("atom:author", ARXIV_NS)
        ]
        published = entry.findtext("atom:published", "", ARXIV_NS)
        link = entry.find("atom:id", ARXIV_NS)
        url_str = link.text if link is not None else ""
        doi = None
        for lnk in entry.findall("atom:link", ARXIV_NS):
            if lnk.get("title") == "doi":
                doi = lnk.get("href")
        abstract = entry.findtext("atom:summary", "", ARXIV_NS).replace("\n", " ").strip()
        cat = entry.findtext("arxiv:primary_category", "", ARXIV_NS)

        if not title or not published:
            continue

        records.append(PreprintRecord(
            source="arxiv",
            title=title,
            authors=authors,
            submit_date=published[:10],
            url=url_str,
            doi=doi,
            abstract=abstract[:500] if abstract else None,
            version_count=1,
            category=cat or None,
        ))

    logger.info("arXiv: fetched %d records for author '%s'", len(records), author_query)
    return records


# ---------------------------------------------------------------------------
# bioRxiv / medRxiv fetcher
# ---------------------------------------------------------------------------

BIORXIV_BASE = "https://api.biorxiv.org"


def _fetch_biorxiv_server(author_query: str, server: str, max_results: int = 100) -> list[PreprintRecord]:
    """Query bioRxiv or medRxiv API."""
    records = []
    end = datetime.now()
    start = datetime(end.year - 5, end.month, end.day)

    cursor = 0
    while True:
        url = (
            f"{BIORXIV_BASE}/details/{server}/"
            f"{start.strftime('%Y-%m-%d')}/{end.strftime('%Y-%m-%d')}/"
            f"{cursor}"
        )
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                payload = json.loads(resp.read())
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
            logger.warning("%s API unreachable at cursor %d: %s", server, cursor, exc)
            break

        collection = payload.get("collection", [])
        if not collection:
            break

        for item in collection:
            authors_raw = item.get("authors", "")
            if not authors_raw:
                continue
            author_names = [a.strip() for a in authors_raw.split(";") if a.strip()]
            if not any(author_query.lower() in a.lower() for a in author_names):
                continue

            records.append(PreprintRecord(
                source=server,
                title=item.get("title", "").strip(),
                authors=author_names,
                submit_date=item.get("date", "")[:10],
                url=item.get("biorxiv_url", item.get("medrxiv_url", "")),
                doi=item.get("doi"),
                abstract=None,
                version_count=item.get("version", 1),
                journal_doi=item.get("published_doi"),
            ))

        total = payload.get("messages", [{}])[0].get("total", 0)
        cursor += len(collection)
        if cursor >= total or cursor >= max_results:
            break

    logger.info("%s: fetched %d records matching author '%s'", server, len(records), author_query)
    return records


def fetch_biorxiv(author_query: str, max_results: int = 100) -> list[PreprintRecord]:
    return _fetch_biorxiv_server(author_query, "biorxiv", max_results)


def fetch_medrxiv(author_query: str, max_results: int = 100) -> list[PreprintRecord]:
    return _fetch_biorxiv_server(author_query, "medrxiv", max_results)


# ---------------------------------------------------------------------------
# Overlap detection
# ---------------------------------------------------------------------------

SIMILARITY_THRESHOLD = 0.75


def _title_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def detect_overlaps(preprints: list[PreprintRecord], journal_papers: list[dict]) -> list[OverlapAlert]:
    """Compare preprint dates with journal paper dates to flag anomalies."""
    alerts = []
    for pre in preprints:
        pre_date = datetime.strptime(pre.submit_date, "%Y-%m-%d")
        for jp in journal_papers:
            j_title = jp.get("title", "")
            j_date_str = jp.get("date", jp.get("year", ""))
            if not j_title or not j_date_str:
                continue
            sim = _title_similarity(pre.title, j_title)
            if sim < SIMILARITY_THRESHOLD:
                continue

            try:
                j_date = datetime.strptime(j_date_str, "%Y-%m-%d")
            except ValueError:
                try:
                    j_date = datetime.strptime(str(j_date_str), "%Y")
                    j_date = j_date.replace(month=12, day=31)
                except ValueError:
                    continue

            delta_days = (j_date - pre_date).days

            if -30 <= delta_days <= 30:
                alerts.append(OverlapAlert(
                    preprint_title=pre.title,
                    preprint_date=pre.submit_date,
                    journal_title=j_title,
                    journal_date=j_date_str,
                    overlap_type="duplicate_submission",
                    confidence="high" if sim > 0.9 else "medium",
                    explanation=f"预印本提交({pre.submit_date})与期刊投稿/见刊({j_date_str})间隔{delta_days}天，标题相似度{sim:.2f}",
                ))
            elif 31 <= delta_days <= 180:
                alerts.append(OverlapAlert(
                    preprint_title=pre.title,
                    preprint_date=pre.submit_date,
                    journal_title=j_title,
                    journal_date=j_date_str,
                    overlap_type="content_reuse",
                    confidence="medium",
                    explanation=f"预印本提交后{delta_days}天期刊发表，可能为正常预印本-期刊转化",
                ))
            elif delta_days < -30:
                alerts.append(OverlapAlert(
                    preprint_title=pre.title,
                    preprint_date=pre.submit_date,
                    journal_title=j_title,
                    journal_date=j_date_str,
                    overlap_type="suspicious_gap",
                    confidence="medium",
                    explanation=f"期刊发表日期({j_date_str})早于预印本提交({pre.submit_date}){abs(delta_days)}天，可能存在隐瞒预印本历史",
                ))
    return alerts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Preprint monitor for academic investigation")
    p.add_argument("--name", required=True, help="Author name (Chinese or English)")
    p.add_argument("--arxiv-name", help="Author name for arXiv query if different from --name")
    p.add_argument("--orcid", help="ORCID iD (optional, for future integration)")
    p.add_argument("--journal-papers", type=Path, help="Path to unified_papers.json from data_importer")
    p.add_argument("--output", type=Path, default=Path("./data/preprints.json"), help="Output JSON path")
    p.add_argument("--max-results", type=int, default=100, help="Max records per source")
    p.add_argument("--sources", nargs="+", default=["arxiv", "biorxiv", "medrxiv"],
                   choices=["arxiv", "biorxiv", "medrxiv", "chemrxiv"],
                   help="Preprint sources to query")
    p.add_argument("--verbose", action="store_true", help="Verbose logging")
    return p


def main():
    args = build_parser().parse_args()
    if args.verbose:
        logger.setLevel("DEBUG")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    all_preprints: list[PreprintRecord] = []
    author = args.name
    arxiv_author = args.arxiv_name or author

    if "arxiv" in args.sources:
        all_preprints.extend(fetch_arxiv(arxiv_author, args.max_results))
    if "biorxiv" in args.sources:
        all_preprints.extend(fetch_biorxiv(author, args.max_results))
    if "medrxiv" in args.sources:
        all_preprints.extend(fetch_medrxiv(author, args.max_results))

    # Deduplicate by source+doi+title similarity
    deduped: list[PreprintRecord] = []
    for pr in all_preprints:
        dup = False
        for existing in deduped:
            if pr.source == existing.source and (pr.doi and pr.doi == existing.doi):
                dup = True
                break
            if _title_similarity(pr.title, existing.title) > 0.95:
                dup = True
                break
        if not dup:
            deduped.append(pr)

    logger.info("Total unique preprints after dedup: %d", len(deduped))

    # Load journal papers for overlap detection
    journal_papers = []
    if args.journal_papers and args.journal_papers.exists():
        with open(args.journal_papers, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            journal_papers = data if isinstance(data, list) else data.get("papers", [])
        logger.info("Loaded %d journal papers for overlap detection", len(journal_papers))

    alerts = detect_overlaps(deduped, journal_papers)

    def _alert_confidence(conf: str) -> float:
        return {"low": 0.3, "medium": 0.5, "high": 0.8}.get(conf, 0.5)

    signals = []
    for a in alerts:
        signals.append({
            "type": a.overlap_type,
            "description": a.explanation[:200],
            "confidence": _alert_confidence(a.confidence),
            "paper_id": a.journal_title or a.preprint_title,
            "source": "preprint_monitor",
            "evidence": {
                "preprint_title": a.preprint_title,
                "preprint_date": a.preprint_date,
                "journal_date": a.journal_date,
            },
        })

    result = {
        "meta": {
            "script": "preprint_monitor",
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "input_file": str(args.journal_papers) if args.journal_papers else "",
        },
        "signals": signals,
        "details": {
            "preprints": [asdict(pr) for pr in deduped],
            "alerts": [asdict(a) for a in alerts],
        },
    }

    save_json(result, args.output)
    logger.info("Saved results to %s", args.output)

    # Summary print
    print(f"\n{'='*60}")
    print(f"Preprint Monitor Summary")
    print(f"{'='*60}")
    print(f"Author:        {author}")
    print(f"Sources:       {', '.join(args.sources)}")
    print(f"Preprints:     {len(deduped)}")
    print(f"Alerts:        {len(alerts)}")
    if alerts:
        print(f"\nTop alerts:")
        for a in alerts[:5]:
            print(f"  [{a.confidence.upper()}] {a.overlap_type}: {a.explanation}")
    print(f"\nOutput:        {args.output}")


if __name__ == "__main__":
    main()
