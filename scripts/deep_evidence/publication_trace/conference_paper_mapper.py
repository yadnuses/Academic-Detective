#!/usr/bin/env python3
"""
conference_paper_mapper.py

Map conference papers to journal papers to detect undisclosed duplicate publication,
salami slicing, and normal conference-to-journal evolution paths.

Supported sources (free APIs only):
    DBLP API, Crossref API

Usage:
    python conference_paper_mapper.py --papers ./data/papers.json \
        --output ./data/conference_map.json [--similarity-threshold 0.85] [--verbose]

    python conference_paper_mapper.py --conference-papers ./data/conf.json \
        --journal-papers ./data/journal.json --output ./data/conference_map.json
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
import sys
import difflib
import time

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.utils import get_logger, save_json

logger = get_logger("conference_paper_mapper")

USER_AGENT = "AcademicInvestigationBot/3.0 (mailto:investigation@example.org)"
DBLP_API = "https://dblp.org/search/publ/api"
CROSSREF_BASE = "https://api.crossref.org/works"

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ConferenceMatch:
    conference_title: str
    conference_authors: list[str]
    conference_date: Optional[str]
    conference_venue: Optional[str]
    journal_title: str
    journal_authors: list[str]
    journal_date: Optional[str]
    journal_venue: Optional[str]
    title_similarity: float
    author_overlap_ratio: float
    months_gap: Optional[int]
    match_type: str           # undisclosed_dual_publication | salami_slicing | conference_first_journal_later
    confidence: str           # low | medium | high
    explanation: str


# ---------------------------------------------------------------------------
# Paper loading
# ---------------------------------------------------------------------------

def _is_conference(paper: dict) -> bool:
    venue = str(paper.get("venue", paper.get("journal", paper.get("source", ""))))
    title = str(paper.get("title", ""))
    return any(k in venue.lower() for k in ("proceedings", "conference", "symposium", "workshop", "会议")) or \
           "conf." in venue.lower()


def _normalize_date(date_val) -> Optional[str]:
    if not date_val:
        return None
    s = str(date_val)
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(s[: len(fmt) + (2 if fmt == "%Y-%m-%d" else 0)], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _year_from_date(date_str: Optional[str]) -> Optional[int]:
    if not date_str:
        return None
    try:
        return int(str(date_str)[:4])
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Similarity helpers
# ---------------------------------------------------------------------------

def _title_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _author_overlap(authors_a: list[str], authors_b: list[str]) -> float:
    if not authors_a or not authors_b:
        return 0.0
    set_a = {a.lower().strip() for a in authors_a if a.strip()}
    set_b = {b.lower().strip() for b in authors_b if b.strip()}
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    return len(intersection) / max(len(set_a), len(set_b))


# ---------------------------------------------------------------------------
# External API enrichment
# ---------------------------------------------------------------------------

def fetch_dblp_metadata(title: str) -> Optional[dict]:
    """Query DBLP API for a paper by title."""
    url = f"{DBLP_API}?q={urllib.parse.quote(title)}&format=json&h=3"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        logger.debug("DBLP query failed for '%s...': %s", title[:40], exc)
        return None

    hits = data.get("result", {}).get("hits", {}).get("hit", [])
    if not hits:
        return None

    best = hits[0].get("info", {})
    return {
        "title": best.get("title", ""),
        "authors": [a.get("text", "") for a in best.get("authors", {}).get("author", [])] if isinstance(best.get("authors", {}).get("author", []), list) else [best.get("authors", {}).get("author", {}).get("text", "")],
        "venue": best.get("venue", ""),
        "year": best.get("year", ""),
        "type": best.get("type", ""),
        "url": best.get("url", ""),
    }


def fetch_crossref_by_title(title: str) -> Optional[dict]:
    """Query Crossref for a paper by title."""
    url = f"{CROSSREF_BASE}?query.title={urllib.parse.quote(title)}&rows=3&select=title,author,container-title,published-print,type"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        logger.debug("Crossref query failed for '%s...': %s", title[:40], exc)
        return None

    items = data.get("message", {}).get("items", [])
    if not items:
        return None

    item = items[0]
    authors = []
    for a in item.get("author", []):
        name = " ".join(filter(None, [a.get("given", ""), a.get("family", "")]))
        if name:
            authors.append(name)

    pp = item.get("published-print", {}).get("date-parts", [[]])
    year = str(pp[0][0]) if pp and pp[0] else None

    return {
        "title": item.get("title", [""])[0] if isinstance(item.get("title"), list) else item.get("title", ""),
        "authors": authors,
        "venue": item.get("container-title", [""])[0] if item.get("container-title") else "",
        "year": year,
        "type": item.get("type", ""),
    }


# ---------------------------------------------------------------------------
# Matching engine
# ---------------------------------------------------------------------------

def detect_matches(
    conference_papers: list[dict],
    journal_papers: list[dict],
    similarity_threshold: float = 0.85,
    year_window: int = 24,
) -> list[ConferenceMatch]:
    matches: list[ConferenceMatch] = []

    for cp in conference_papers:
        c_title = str(cp.get("title", ""))
        c_authors = cp.get("authors", [])
        if isinstance(c_authors, str):
            c_authors = [a.strip() for a in c_authors.split(",") if a.strip()]
        c_date = _normalize_date(cp.get("date", cp.get("year", "")))
        c_venue = str(cp.get("venue", cp.get("journal", cp.get("source", ""))))
        c_year = _year_from_date(c_date) or _year_from_date(cp.get("year", ""))

        if not c_title:
            continue

        for jp in journal_papers:
            j_title = str(jp.get("title", ""))
            j_authors = jp.get("authors", [])
            if isinstance(j_authors, str):
                j_authors = [a.strip() for a in j_authors.split(",") if a.strip()]
            j_date = _normalize_date(jp.get("date", jp.get("year", "")))
            j_venue = str(jp.get("venue", jp.get("journal", jp.get("source", ""))))
            j_year = _year_from_date(j_date) or _year_from_date(jp.get("year", ""))

            if not j_title:
                continue

            title_sim = _title_similarity(c_title, j_title)
            if title_sim < similarity_threshold:
                continue

            author_overlap = _author_overlap(c_authors, j_authors)
            if author_overlap < 0.5:
                continue

            # Time proximity: conference within 24 months before journal
            months_gap = None
            if c_year and j_year:
                months_gap = (j_year - c_year) * 12
                if months_gap < 0 or months_gap > year_window:
                    continue

            # Determine match type
            abs_c = str(cp.get("abstract", ""))
            abs_j = str(jp.get("abstract", ""))
            abstract_sim = _title_similarity(abs_c, abs_j) if abs_c and abs_j else 0.0

            if abstract_sim > 0.7 or title_sim > 0.95:
                if months_gap is not None and months_gap <= 3:
                    match_type = "undisclosed_dual_publication"
                    explanation = f"会议与期刊版本标题高度相似({title_sim:.2f})且时间接近({months_gap}个月)，疑似未披露双重发表"
                    confidence = "high"
                else:
                    match_type = "salami_slicing"
                    explanation = f"会议与期刊版本内容重叠度高(标题相似度{title_sim:.2f}，摘要相似度{abstract_sim:.2f})，疑似香肠论文"
                    confidence = "medium"
            else:
                match_type = "conference_first_journal_later"
                explanation = f"会议先发表后扩展至期刊，标题相似度{title_sim:.2f}，间隔{months_gap}个月"
                confidence = "low"

            matches.append(ConferenceMatch(
                conference_title=c_title,
                conference_authors=c_authors,
                conference_date=c_date,
                conference_venue=c_venue,
                journal_title=j_title,
                journal_authors=j_authors,
                journal_date=j_date,
                journal_venue=j_venue,
                title_similarity=round(title_sim, 3),
                author_overlap_ratio=round(author_overlap, 3),
                months_gap=months_gap,
                match_type=match_type,
                confidence=confidence,
                explanation=explanation,
            ))

    # Sort by confidence then similarity
    conf_order = {"high": 0, "medium": 1, "low": 2}
    matches.sort(key=lambda m: (conf_order.get(m.confidence, 3), -m.title_similarity))
    return matches


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Map conference papers to journal papers")
    p.add_argument("--papers", type=Path, help="Unified papers JSON (mixed conference + journal)")
    p.add_argument("--conference-papers", type=Path, help="Conference papers JSON")
    p.add_argument("--journal-papers", type=Path, help="Journal papers JSON")
    p.add_argument("--output", type=Path, default=Path("./data/conference_map.json"), help="Output JSON path")
    p.add_argument("--similarity-threshold", type=float, default=0.85, help="Minimum title similarity for match")
    p.add_argument("--year-window", type=int, default=24, help="Max months between conference and journal")
    p.add_argument("--verbose", action="store_true", help="Verbose logging")
    p.add_argument("--enrich", action="store_true", help="Query DBLP/Crossref for missing metadata")
    return p


def main():
    args = build_parser().parse_args()
    if args.verbose:
        logger.setLevel("DEBUG")

    conference_papers: list[dict] = []
    journal_papers: list[dict] = []

    if args.papers and args.papers.exists():
        with open(args.papers, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        paper_list = raw if isinstance(raw, list) else raw.get("papers", [])
        conference_papers = [p for p in paper_list if _is_conference(p)]
        journal_papers = [p for p in paper_list if not _is_conference(p)]
        logger.info("Loaded %d papers: %d conference, %d journal", len(paper_list), len(conference_papers), len(journal_papers))
    elif args.conference_papers and args.conference_papers.exists() and args.journal_papers and args.journal_papers.exists():
        with open(args.conference_papers, "r", encoding="utf-8") as fh:
            c_raw = json.load(fh)
        conference_papers = c_raw if isinstance(c_raw, list) else c_raw.get("papers", [])
        with open(args.journal_papers, "r", encoding="utf-8") as fh:
            j_raw = json.load(fh)
        journal_papers = j_raw if isinstance(j_raw, list) else j_raw.get("papers", [])
        logger.info("Loaded %d conference and %d journal papers", len(conference_papers), len(journal_papers))
    else:
        logger.error("Must provide --papers or both --conference-papers and --journal-papers")
        sys.exit(1)

    # Optional enrichment
    if args.enrich:
        for cp in conference_papers:
            if not cp.get("venue") and cp.get("title"):
                meta = fetch_dblp_metadata(cp["title"])
                if meta:
                    cp["venue"] = meta.get("venue", "")
                    if not cp.get("year") and meta.get("year"):
                        cp["year"] = meta["year"]
                time.sleep(0.3)

    matches = detect_matches(conference_papers, journal_papers, args.similarity_threshold, args.year_window)

    undisclosed = [m for m in matches if m.match_type == "undisclosed_dual_publication"]
    salami = [m for m in matches if m.match_type == "salami_slicing"]

    def _match_confidence(conf: str) -> float:
        return {"low": 0.3, "medium": 0.5, "high": 0.8}.get(conf, 0.5)

    signals = []
    for m in matches:
        if m.match_type == "conference_first_journal_later":
            continue
        signals.append({
            "type": m.match_type,
            "description": m.explanation[:200],
            "confidence": _match_confidence(m.confidence),
            "paper_id": m.journal_title,
            "source": "conference_paper_mapper",
            "evidence": {
                "conference_title": m.conference_title,
                "similarity_score": m.title_similarity,
            },
        })

    result = {
        "meta": {
            "script": "conference_paper_mapper",
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "input_file": str(args.papers) if args.papers else f"{args.conference_papers},{args.journal_papers}",
        },
        "signals": signals,
        "details": {
            "matches": [asdict(m) for m in matches],
            "summary": {
                "undisclosed_dual_publication": len(undisclosed),
                "salami_slicing": len(salami),
                "conference_first_journal_later": len(matches) - len(undisclosed) - len(salami),
            },
        },
    }

    save_json(result, args.output)
    logger.info("Saved conference map to %s", args.output)

    print(f"\n{'='*60}")
    print("Conference Paper Mapper Summary")
    print(f"{'='*60}")
    print(f"Conference papers:       {len(conference_papers)}")
    print(f"Journal papers:          {len(journal_papers)}")
    print(f"Matches found:           {len(matches)}")
    print(f"  Undisclosed dual pub:  {len(undisclosed)}")
    print(f"  Salami slicing:        {len(salami)}")
    if matches:
        print(f"\nTop matches:")
        for m in matches[:5]:
            print(f"  [{m.confidence.upper()}] {m.match_type}: {m.explanation}")
    print(f"\nOutput:                  {args.output}")


if __name__ == "__main__":
    main()
