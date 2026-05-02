#!/usr/bin/env python3
"""
editorial_self_publishing_detector.py

Detect when an editor publishes extensively in their own journal.
Flags potential editorial bias, self-dealing, or bypass of normal peer review.

Data sources: Input paper metadata (no external API required)

Usage:
    python editorial_self_publishing_detector.py --papers ./data/papers.json \
        --editor-journals ./data/editor_roles.json --output ./data/editorial_audit.json

    python editorial_self_publishing_detector.py --papers ./data/papers.json \
        --output ./data/editorial_audit.json --threshold 0.15
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

logger = get_logger("editorial_self_publishing_detector")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class EditorJournalRecord:
    editor_name: str
    journal_issn: Optional[str]
    journal_name: str
    role: str  # editor-in-chief | associate_editor | guest_editor
    term_start: Optional[str]
    term_end: Optional[str]


@dataclass
class SelfPublishingResult:
    editor_name: str
    journal_name: str
    journal_issn: Optional[str]
    total_papers: int
    self_journal_papers: int
    self_journal_ratio: float
    inferred: bool = False
    flags: list[str] = field(default_factory=list)
    papers: list[dict] = field(default_factory=list)


@dataclass
class EditorialAlert:
    editor_name: str
    journal_name: str
    alert_type: str
    confidence: str
    explanation: str
    paper_id: str = ""


# ---------------------------------------------------------------------------
# Inference helpers
# ---------------------------------------------------------------------------

def infer_editor_journals(papers: list[dict]) -> list[EditorJournalRecord]:
    """
    Infer editor-journal relationships from paper metadata.
    Looks for papers where an author is listed with an editorial role keyword.
    Less reliable; all inferred records are flagged.
    """
    inferred: list[EditorJournalRecord] = []
    role_keywords = ["editor-in-chief", "editor in chief", "associate editor", "guest editor", "editorial board"]

    seen = set()
    for paper in papers:
        authors = paper.get("authors", [])
        journal = paper.get("journal", paper.get("container-title", ""))
        issn = paper.get("issn", paper.get("ISSN", ""))
        if isinstance(issn, list):
            issn = issn[0] if issn else None

        for author_entry in authors:
            name = ""
            role = ""
            if isinstance(author_entry, dict):
                name = author_entry.get("name", author_entry.get("given", "") + " " + author_entry.get("family", "")).strip()
                affiliation = (author_entry.get("affiliation", "") or "").lower()
                for kw in role_keywords:
                    if kw in affiliation:
                        role = kw
                        break
            elif isinstance(author_entry, str):
                name = author_entry.strip()

            if not name or not role:
                continue

            key = (name.lower(), journal.lower())
            if key in seen:
                continue
            seen.add(key)
            inferred.append(EditorJournalRecord(
                editor_name=name,
                journal_issn=issn,
                journal_name=journal,
                role=role,
                term_start=None,
                term_end=None,
            ))

    logger.info("Inferred %d editor-journal relationships from metadata", len(inferred))
    return inferred


# ---------------------------------------------------------------------------
# Analysis engine
# ---------------------------------------------------------------------------

def load_editor_journals(path: Path) -> list[EditorJournalRecord]:
    """Load explicit editor-journal mapping from JSON."""
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)

    records = raw if isinstance(raw, list) else raw.get("editors", [])
    result = []
    for r in records:
        result.append(EditorJournalRecord(
            editor_name=r.get("name", r.get("editor_name", "")),
            journal_issn=r.get("issn", r.get("journal_issn")),
            journal_name=r.get("journal", r.get("journal_name", "")),
            role=r.get("role", "editor"),
            term_start=r.get("term_start"),
            term_end=r.get("term_end"),
        ))
    return result


def journal_matches(paper: dict, record: EditorJournalRecord) -> bool:
    """Check whether a paper belongs to the editor's journal."""
    paper_journal = paper.get("journal", paper.get("container-title", "")).lower()
    paper_issn = paper.get("issn", paper.get("ISSN", ""))
    if isinstance(paper_issn, list):
        paper_issn = paper_issn[0] if paper_issn else ""
    paper_issn = (paper_issn or "").lower().replace("-", "")

    record_issn = (record.journal_issn or "").lower().replace("-", "")

    if record_issn and paper_issn and record_issn == paper_issn:
        return True
    if record.journal_name.lower() in paper_journal or paper_journal in record.journal_name.lower():
        return True
    return False


def author_matches(paper: dict, editor_name: str) -> bool:
    """Check whether the editor is an author of the paper."""
    authors = paper.get("authors", [])
    editor_lower = editor_name.lower()
    for a in authors:
        if isinstance(a, dict):
            name = a.get("name", f"{a.get('given', '')} {a.get('family', '')}").strip().lower()
        elif isinstance(a, str):
            name = a.strip().lower()
        else:
            continue
        if editor_lower in name or name in editor_lower:
            return True
    return False


def extract_review_cycle_days(paper: dict) -> Optional[int]:
    """Extract review cycle duration in days if available."""
    received = paper.get("received")
    accepted = paper.get("accepted")
    if received and accepted:
        try:
            r = datetime.strptime(received, "%Y-%m-%d")
            a = datetime.strptime(accepted, "%Y-%m-%d")
            return (a - r).days
        except ValueError:
            pass
    return paper.get("review_cycle_days")


def detect_special_issue_batch(papers: list[dict]) -> list[dict]:
    """Detect multiple papers in the same special issue."""
    special_issue_counts: dict[str, list[dict]] = {}
    for p in papers:
        si = p.get("special_issue", p.get("issue_title", ""))
        if si:
            key = si.lower()
            special_issue_counts.setdefault(key, []).append(p)
    return [group for group in special_issue_counts.values() if len(group) >= 2]


def analyze_editor(editor: EditorJournalRecord, all_papers: list[dict], threshold: float) -> tuple[Optional[SelfPublishingResult], list[EditorialAlert]]:
    """Analyze self-publishing patterns for a single editor."""
    editor_papers = [p for p in all_papers if author_matches(p, editor.editor_name)]
    if not editor_papers:
        return None, []

    self_journal_papers = [p for p in editor_papers if journal_matches(p, editor)]
    ratio = len(self_journal_papers) / len(editor_papers) if editor_papers else 0.0

    result = SelfPublishingResult(
        editor_name=editor.editor_name,
        journal_name=editor.journal_name,
        journal_issn=editor.journal_issn,
        total_papers=len(editor_papers),
        self_journal_papers=len(self_journal_papers),
        self_journal_ratio=ratio,
        inferred=False,
        papers=[{"title": p.get("title", ""), "doi": p.get("doi", p.get("DOI", "")), "date": p.get("date", p.get("year", ""))} for p in self_journal_papers],
    )
    alerts: list[EditorialAlert] = []

    # High self-journal rate
    if ratio > threshold:
        result.flags.append("high_self_journal_rate")
        alerts.append(EditorialAlert(
            editor_name=editor.editor_name,
            journal_name=editor.journal_name,
            alert_type="high_self_journal_rate",
            confidence="high" if ratio > 0.3 else "medium",
            explanation=f"自任编辑的期刊发文占比{ratio:.1%}（共{len(self_journal_papers)}/{len(editor_papers)}篇），远超编辑正常自投率（<5%）",
            paper_id=result.papers[0].get("title", "") if result.papers else "",
        ))

    # Short review cycles in self-journal papers
    short_cycle_papers = []
    for p in self_journal_papers:
        cycle = extract_review_cycle_days(p)
        if cycle is not None and cycle < 14:
            short_cycle_papers.append(p)
    if short_cycle_papers:
        result.flags.append("editorial_bypass_suspected")
        alerts.append(EditorialAlert(
            editor_name=editor.editor_name,
            journal_name=editor.journal_name,
            alert_type="editorial_bypass_suspected",
            confidence="medium",
            explanation=f"自投论文中有{len(short_cycle_papers)}篇审稿周期短于14天，疑似绕过正常审稿流程",
            paper_id=short_cycle_papers[0].get("title", ""),
        ))

    # Guest editor special issue
    if "guest" in editor.role.lower():
        batches = detect_special_issue_batch(self_journal_papers)
        if batches:
            result.flags.append("guest_editor_special_issue")
            for batch in batches:
                alerts.append(EditorialAlert(
                    editor_name=editor.editor_name,
                    journal_name=editor.journal_name,
                    alert_type="guest_editor_special_issue",
                    confidence="medium",
                    explanation=f"作为客座编辑在专题'{batch[0].get('special_issue', batch[0].get('issue_title', ''))}'中发表{len(batch)}篇论文",
                    paper_id=batch[0].get("title", ""),
                ))

    logger.info("Editor %s: %d/%d self-journal papers (%.1f%%)",
                editor.editor_name, len(self_journal_papers), len(editor_papers), ratio * 100)
    return result, alerts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Editorial self-publishing detector")
    p.add_argument("--papers", type=Path, required=True, help="Path to papers.json")
    p.add_argument("--editor-journals", type=Path, help="Path to editor_roles.json")
    p.add_argument("--output", type=Path, default=Path("./data/editorial_audit.json"))
    p.add_argument("--threshold", type=float, default=0.15, help="Self-journal ratio threshold")
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

    with open(args.papers, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    all_papers = raw if isinstance(raw, list) else raw.get("papers", [])
    logger.info("Loaded %d papers", len(all_papers))

    editor_records: list[EditorJournalRecord] = []
    if args.editor_journals and args.editor_journals.exists():
        editor_records = load_editor_journals(args.editor_journals)
        logger.info("Loaded %d explicit editor records", len(editor_records))
    else:
        logger.warning("--editor-journals not provided; inferring from metadata (less reliable)")
        editor_records = infer_editor_journals(all_papers)
        for er in editor_records:
            er.role = "inferred"

    results: list[SelfPublishingResult] = []
    all_alerts: list[EditorialAlert] = []

    for editor in editor_records:
        result, alerts = analyze_editor(editor, all_papers, args.threshold)
        if result:
            if not args.editor_journals:
                result.inferred = True
            results.append(result)
            all_alerts.extend(alerts)

    str_confidence = {
        "high": 0.85,
        "medium": 0.7,
        "low": 0.55,
    }
    type_map = {
        "high_self_journal_rate": "high_self_journal_rate",
        "editorial_bypass_suspected": "editorial_bypass_suspected",
        "guest_editor_special_issue": "guest_editor_special_issue_selfpub",
    }
    signals = []
    for a in all_alerts:
        signals.append({
            "type": type_map.get(a.alert_type, a.alert_type),
            "description": a.explanation,
            "confidence": str_confidence.get(a.confidence, 0.7),
            "paper_id": a.paper_id,
            "source": "editorial_self_publishing_detector",
            "evidence": {
                "editor_name": a.editor_name,
                "journal_name": a.journal_name,
            },
        })

    result = {
        "meta": {
            "script": "editorial_self_publishing_detector",
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "input_file": str(args.papers),
        },
        "signals": signals,
        "details": {
            "results": [asdict(r) for r in results],
            "alerts": [asdict(a) for a in all_alerts],
        },
    }

    save_json(result, args.output)
    logger.info("Saved editorial audit to %s", args.output)

    print(f"\n{'='*60}")
    print(f"Editorial Self-Publishing Detector Summary")
    print(f"{'='*60}")
    print(f"Papers loaded:    {len(all_papers)}")
    print(f"Editors analyzed: {len(editor_records)}")
    print(f"Signals:          {len(signals)}")
    if signals:
        print(f"\nTop signals:")
        for s in signals[:5]:
            print(f"  [{s['confidence']}] {s['type']}: {s['description']}")
    print(f"\nOutput:           {args.output}")


if __name__ == "__main__":
    main()
