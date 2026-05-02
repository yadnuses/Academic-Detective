#!/usr/bin/env python3
"""
recommended_reviewer_network.py

Analyze recommended reviewer networks for conflicts of interest.
Builds an author-reviewer network and flags direct coauthorship,
shared institutions, recent collaborations, citation loops, and
repeated reviewer nominations.

Data sources: Input paper metadata (no external API required)

Usage:
    python recommended_reviewer_network.py --papers ./data/papers.json \
        --output ./data/reviewer_network.json

    python recommended_reviewer_network.py --reviewers ./data/reviewers.json \
        --output ./data/reviewer_network.json --coauthorship-lookback 3
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.utils import get_logger, save_json

logger = get_logger("recommended_reviewer_network")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ConflictRecord:
    paper_title: str
    paper_doi: Optional[str]
    reviewer_name: str
    conflict_type: str
    confidence: str
    explanation: str


@dataclass
class PaperConflictSummary:
    paper_title: str
    paper_doi: Optional[str]
    conflict_score: float
    conflict_level: str
    conflict_count: int
    conflicts: list[ConflictRecord] = field(default_factory=list)


@dataclass
class ReviewerNode:
    name: str
    institution: Optional[str]
    papers_as_reviewer: int = 0
    papers_as_author: int = 0
    coauthors: set[str] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Network builders
# ---------------------------------------------------------------------------

def load_papers(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return raw if isinstance(raw, list) else raw.get("papers", [])


def load_reviewers(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return raw if isinstance(raw, list) else raw.get("reviewers", [])


def extract_name(person: dict | str) -> str:
    if isinstance(person, str):
        return person.strip()
    return (person.get("name", f"{person.get('given', '')} {person.get('family', '')}")).strip()


def extract_institution(person: dict | str) -> Optional[str]:
    if isinstance(person, str):
        return None
    aff = person.get("affiliation", person.get("institution", ""))
    if isinstance(aff, list):
        return aff[0] if aff else None
    return aff or None


def normalize_name(name: str) -> str:
    """Basic name normalization for matching."""
    return " ".join(name.lower().split())


def build_author_index(papers: list[dict]) -> dict[str, list[dict]]:
    """Map normalized author names to their papers."""
    index: dict[str, list[dict]] = {}
    for paper in papers:
        for author in paper.get("authors", []):
            name = normalize_name(extract_name(author))
            if name:
                index.setdefault(name, []).append(paper)
    return index


def build_coauthor_map(papers: list[dict], lookback_years: int) -> dict[str, set[str]]:
    """Build a map of coauthors for each author within the lookback period."""
    cutoff_year = datetime.now().year - lookback_years
    coauthors: dict[str, set[str]] = {}

    for paper in papers:
        year = paper.get("year", paper.get("date", ""))
        if isinstance(year, str):
            year = int(year[:4]) if year[:4].isdigit() else datetime.now().year
        if year < cutoff_year:
            continue

        authors = [normalize_name(extract_name(a)) for a in paper.get("authors", [])]
        authors = [a for a in authors if a]
        for a in authors:
            for b in authors:
                if a != b:
                    coauthors.setdefault(a, set()).add(b)

    return coauthors


def institution_match(inst_a: Optional[str], inst_b: Optional[str]) -> bool:
    """Check if two institution strings likely match."""
    if not inst_a or not inst_b:
        return False
    a = inst_a.lower()
    b = inst_b.lower()
    if a == b:
        return True
    # Simple substring match for common institutions
    if len(a) > 10 and len(b) > 10 and (a in b or b in a):
        return True
    return False


def has_recent_collaboration(author_name: str, reviewer_name: str, coauthor_map: dict[str, set[str]], lookback_years: int) -> bool:
    """Check if author and reviewer have coauthored within lookback period."""
    return reviewer_name in coauthor_map.get(author_name, set())


def has_citation_loop(author_papers: list[dict], reviewer_papers: list[dict]) -> bool:
    """Detect mutual heavy citation between author and reviewer."""
    author_dois = {p.get("doi", p.get("DOI", "")).lower() for p in author_papers if p.get("doi") or p.get("DOI")}
    reviewer_dois = {p.get("doi", p.get("DOI", "")).lower() for p in reviewer_papers if p.get("doi") or p.get("DOI")}

    author_cites_reviewer = 0
    reviewer_cites_author = 0

    for p in author_papers:
        refs = p.get("references", [])
        for r in refs:
            ref_doi = (r.get("doi", r.get("DOI", "")) or "").lower()
            if ref_doi in reviewer_dois:
                author_cites_reviewer += 1

    for p in reviewer_papers:
        refs = p.get("references", [])
        for r in refs:
            ref_doi = (r.get("doi", r.get("DOI", "")) or "").lower()
            if ref_doi in author_dois:
                reviewer_cites_author += 1

    return author_cites_reviewer >= 3 and reviewer_cites_author >= 3


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

def detect_conflicts_for_paper(
    paper: dict,
    author_index: dict[str, list[dict]],
    coauthor_map: dict[str, set[str]],
    reviewer_nomination_counts: dict[str, int],
    lookback_years: int,
) -> list[ConflictRecord]:
    """Detect all conflicts for recommended reviewers in a single paper."""
    conflicts: list[ConflictRecord] = []
    recommended = paper.get("recommended_reviewers", [])
    if not recommended:
        return conflicts

    paper_authors = [normalize_name(extract_name(a)) for a in paper.get("authors", [])]
    paper_authors = [a for a in paper if a]

    for rev in recommended:
        rev_name = normalize_name(extract_name(rev))
        rev_inst = extract_institution(rev)
        if not rev_name:
            continue

        # Direct coauthor
        for auth in paper_authors:
            if has_recent_collaboration(auth, rev_name, coauthor_map, lookback_years):
                conflicts.append(ConflictRecord(
                    paper_title=paper.get("title", ""),
                    paper_doi=paper.get("doi", paper.get("DOI", None)),
                    reviewer_name=rev_name,
                    conflict_type="direct_coauthor",
                    confidence="high",
                    explanation=f"推荐审稿人'{rev_name}'与作者'{auth}'在近{lookback_years}年内有合著论文",
                ))

        # Same institution
        for author in paper.get("authors", []):
            auth_inst = extract_institution(author)
            if institution_match(auth_inst, rev_inst):
                auth_name = normalize_name(extract_name(author))
                conflicts.append(ConflictRecord(
                    paper_title=paper.get("title", ""),
                    paper_doi=paper.get("doi", paper.get("DOI", None)),
                    reviewer_name=rev_name,
                    conflict_type="same_institution",
                    confidence="medium",
                    explanation=f"推荐审稿人'{rev_name}'与作者'{auth_name}'属于同一机构({auth_inst})",
                ))
                break  # one same-institution conflict per reviewer is enough

        # Repeated reviewer
        if reviewer_nomination_counts.get(rev_name, 0) > 2:
            conflicts.append(ConflictRecord(
                paper_title=paper.get("title", ""),
                paper_doi=paper.get("doi", paper.get("DOI", None)),
                reviewer_name=rev_name,
                conflict_type="repeated_reviewer",
                confidence="low",
                explanation=f"该审稿人'{rev_name}'被推荐次数达{reviewer_nomination_counts[rev_name]}次",
            ))

        # Citation loop
        author_papers = []
        for a in paper_authors:
            author_papers.extend(author_index.get(a, []))
        reviewer_papers = author_index.get(rev_name, [])
        if has_citation_loop(author_papers, reviewer_papers):
            conflicts.append(ConflictRecord(
                paper_title=paper.get("title", ""),
                paper_doi=paper.get("doi", paper.get("DOI", None)),
                reviewer_name=rev_name,
                conflict_type="citation_loop",
                confidence="medium",
                explanation=f"作者与审稿人'{rev_name}'之间存在高频互引",
            ))

    return conflicts


def compute_conflict_score(conflicts: list[ConflictRecord]) -> tuple[float, str]:
    """Compute overall conflict score (0-1) and level label."""
    if not conflicts:
        return 0.0, "none"

    weights = {
        "direct_coauthor": 0.35,
        "same_institution": 0.20,
        "recent_collaboration": 0.25,
        "citation_loop": 0.15,
        "repeated_reviewer": 0.05,
    }

    score = 0.0
    seen_types = set()
    for c in conflicts:
        if c.conflict_type not in seen_types:
            seen_types.add(c.conflict_type)
            score += weights.get(c.conflict_type, 0.1)

    score = min(score, 1.0)
    if score >= 0.6:
        level = "high"
    elif score >= 0.3:
        level = "medium"
    else:
        level = "low"
    return score, level


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Recommended reviewer network conflict analyzer")
    p.add_argument("--papers", type=Path, help="Path to papers.json with recommended_reviewers field")
    p.add_argument("--reviewers", type=Path, help="Path to reviewers.json metadata")
    p.add_argument("--output", type=Path, default=Path("./data/reviewer_network.json"))
    p.add_argument("--coauthorship-lookback", type=int, default=3, help="Years to look back for coauthorship")
    p.add_argument("--verbose", action="store_true")
    return p


def main():
    args = build_parser().parse_args()
    if args.verbose:
        logger.setLevel("DEBUG")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    if not args.papers and not args.reviewers:
        logger.error("Either --papers or --reviewers must be provided")
        sys.exit(1)

    if args.papers and not args.papers.exists():
        logger.error("Input file not found: %s", args.papers)
        sys.exit(1)
    if args.reviewers and not args.reviewers.exists():
        logger.error("Input file not found: %s", args.reviewers)
        sys.exit(1)

    all_papers: list[dict] = []
    if args.papers and args.papers.exists():
        all_papers = load_papers(args.papers)
    elif args.reviewers and args.reviewers.exists():
        # If only reviewers provided, we still need papers for context
        all_papers = load_reviewers(args.reviewers)
    else:
        logger.error("Input file not found")
        sys.exit(1)

    # Check for recommended_reviewers field
    has_recommended = any("recommended_reviewers" in p for p in all_papers)
    if not has_recommended:
        logger.warning("No 'recommended_reviewers' field found in input; marking as insufficient_data")
        result = {
            "meta": {
                "script": "recommended_reviewer_network",
                "version": "1.0",
                "timestamp": datetime.now().isoformat(),
                "input_file": str(args.papers) if args.papers else str(args.reviewers),
            },
            "signals": [],
            "details": {
                "summaries": [],
                "conflicts": [],
                "note": "insufficient_data: input lacks recommended_reviewers field",
            },
        }
        save_json(result, args.output)
        print(f"\nOutput: {args.output}")
        return

    author_index = build_author_index(all_papers)
    coauthor_map = build_coauthor_map(all_papers, args.coauthorship_lookback)

    # Count reviewer nominations across all papers
    nomination_counts: dict[str, int] = {}
    for paper in all_papers:
        for rev in paper.get("recommended_reviewers", []):
            name = normalize_name(extract_name(rev))
            if name:
                nomination_counts[name] = nomination_counts.get(name, 0) + 1

    summaries: list[PaperConflictSummary] = []
    all_conflicts: list[ConflictRecord] = []

    for paper in all_papers:
        if "recommended_reviewers" not in paper:
            continue
        conflicts = detect_conflicts_for_paper(
            paper, author_index, coauthor_map, nomination_counts, args.coauthorship_lookback
        )
        score, level = compute_conflict_score(conflicts)
        summaries.append(PaperConflictSummary(
            paper_title=paper.get("title", ""),
            paper_doi=paper.get("doi", paper.get("DOI", None)),
            conflict_score=score,
            conflict_level=level,
            conflict_count=len(conflicts),
            conflicts=conflicts,
        ))
        all_conflicts.extend(conflicts)

    str_confidence = {
        "high": 0.85,
        "medium": 0.7,
        "low": 0.55,
    }
    type_map = {
        "direct_coauthor": "direct_coauthor_conflict",
        "same_institution": "same_institution_conflict",
        "repeated_reviewer": "repeated_reviewer",
        "citation_loop": "citation_loop_conflict",
    }
    signals = []
    for c in all_conflicts:
        signals.append({
            "type": type_map.get(c.conflict_type, c.conflict_type),
            "description": c.explanation,
            "confidence": str_confidence.get(c.confidence, 0.7),
            "paper_id": c.paper_doi or c.paper_title,
            "source": "recommended_reviewer_network",
            "evidence": {
                "reviewer_name": c.reviewer_name,
            },
        })

    high_conflict_count = sum(1 for s in summaries if s.conflict_level == "high")

    result = {
        "meta": {
            "script": "recommended_reviewer_network",
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "input_file": str(args.papers) if args.papers else str(args.reviewers),
        },
        "signals": signals,
        "details": {
            "summaries": [asdict(s) for s in summaries],
            "conflicts": [asdict(c) for c in all_conflicts],
        },
    }

    save_json(result, args.output)
    logger.info("Saved reviewer network analysis to %s", args.output)

    print(f"\n{'='*60}")
    print(f"Recommended Reviewer Network Summary")
    print(f"{'='*60}")
    print(f"Papers analyzed:      {len(all_papers)}")
    print(f"Papers with reviewers:{len(summaries)}")
    print(f"Total signals:        {len(signals)}")
    print(f"High conflict papers: {high_conflict_count}")
    if signals:
        print(f"\nTop signals:")
        for s in signals[:5]:
            print(f"  [{s['confidence']}] {s['type']}: {s['description']}")
    print(f"\nOutput:               {args.output}")


if __name__ == "__main__":
    main()
