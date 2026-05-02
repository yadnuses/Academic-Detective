#!/usr/bin/env python3
"""
recommendation_engine.py

Dynamic task recommendation engine for the academic investigation v3.1
reactive state machine.

Scans case directories for deep_evidence output JSON (Schema v1.0) and
produces prioritized tool recommendations based on built-in heuristic rules.

Usage:
    from core.recommendation_engine import RuleEngine, Recommendation

    engine = RuleEngine()
    recs = engine.evaluate(Path("./cases/zhangsan"))
    for r in recs:
        print(r.priority, r.tools, r.reason)
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from core.utils import get_logger, load_json

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Recommendation:
    """A single triggered recommendation."""
    priority: int
    tools: list[str]
    reason: str
    rule_id: str
    trigger_source: str


# ---------------------------------------------------------------------------
# Trigger helpers (file-level)
# ---------------------------------------------------------------------------

def _load_papers(data: dict) -> list[dict]:
    """Normalize various papers JSON shapes into a list of paper dicts."""
    papers = data.get("papers", []) if isinstance(data, dict) else []
    if isinstance(papers, list):
        return papers
    return data if isinstance(data, list) else []


def check_file_has_signals(file_path: Path, min_count: int = 1) -> bool:
    """Return True if JSON file contains a non-empty signals array."""
    data = load_json(file_path)
    if not isinstance(data, dict):
        return False
    signals = data.get("signals", [])
    return isinstance(signals, list) and len(signals) >= min_count


def check_file_has_alert_type(file_path: Path, alert_type: str) -> bool:
    """Return True if JSON file contains given alert type in signals or details.alerts."""
    data = load_json(file_path)
    if not isinstance(data, dict):
        return False
    for signal in data.get("signals", []):
        if isinstance(signal, dict) and signal.get("type") == alert_type:
            return True
    details = data.get("details", {})
    alerts = details.get("alerts", []) if isinstance(details, dict) else []
    for alert in alerts:
        if isinstance(alert, dict) and alert.get("alert_type") == alert_type:
            return True
    return False


def check_papers_have_keyword(papers_json: Path, keywords: list[str]) -> bool:
    """Return True if any paper title contains any keyword (case-insensitive)."""
    data = load_json(papers_json)
    papers = _load_papers(data)
    keywords_lower = [k.lower() for k in keywords]
    for paper in papers:
        if isinstance(paper, dict):
            title = paper.get("title", "")
            if isinstance(title, str) and any(k in title.lower() for k in keywords_lower):
                return True
    return False


def check_journal_frequency(papers_json: Path, threshold: int = 3) -> list[str]:
    """Return journals with paper count >= threshold."""
    data = load_json(papers_json)
    papers = _load_papers(data)
    freq: dict[str, int] = {}
    for paper in papers:
        if isinstance(paper, dict):
            journal = paper.get("journal") or paper.get("venue") or ""
            if isinstance(journal, str) and journal.strip():
                j = journal.strip()
                freq[j] = freq.get(j, 0) + 1
    return [j for j, c in freq.items() if c >= threshold]


def check_has_cjk_and_english(papers_json: Path) -> bool:
    """Return True if papers contain both CJK and English titles."""
    data = load_json(papers_json)
    papers = _load_papers(data)
    has_cjk = has_en = False
    cjk_re = re.compile(r"[\u4e00-\u9fff\u3000-\u303f\u3040-\u309f\u30a0-\u30ff]")
    for paper in papers:
        if isinstance(paper, dict):
            title = paper.get("title", "")
            if isinstance(title, str):
                if cjk_re.search(title):
                    has_cjk = True
                if re.search(r"[a-zA-Z]", title):
                    has_en = True
                if has_cjk and has_en:
                    return True
    return False


def check_has_dois(papers_json: Path) -> bool:
    """Return True if any paper has a non-empty DOI."""
    data = load_json(papers_json)
    papers = _load_papers(data)
    return any(isinstance(p, dict) and p.get("doi") for p in papers)


def check_has_issns(papers_json: Path) -> bool:
    """Return True if any paper has a non-empty ISSN."""
    data = load_json(papers_json)
    papers = _load_papers(data)
    return any(isinstance(p, dict) and p.get("issn") for p in papers)


def check_has_conference_papers(papers_json: Path) -> bool:
    """Return True if any paper looks like a conference paper."""
    data = load_json(papers_json)
    papers = _load_papers(data)
    hints = ["conference", "proceeding", "symposium", "workshop", "会议"]
    for paper in papers:
        if isinstance(paper, dict):
            combined = f"{paper.get('venue','')} {paper.get('journal','')} {paper.get('title','')} {paper.get('type','')}".lower()
            if any(h in combined for h in hints):
                return True
    return False


# ---------------------------------------------------------------------------
# File finder
# ---------------------------------------------------------------------------

def _find_file(case_dir: Path, *hints: str) -> Optional[Path]:
    """Find first JSON file in case_dir whose name contains any hint."""
    for f in case_dir.rglob("*.json"):
        name = f.name.lower()
        for h in hints:
            if h.lower() in name:
                return f
    return None


# ---------------------------------------------------------------------------
# Built-in rule triggers (case_dir -> source path or None)
# ---------------------------------------------------------------------------

def _trigger_r01(case_dir: Path) -> Optional[str]:
    f = _find_file(case_dir, "common_heuristics")
    return str(f) if f and check_file_has_signals(f) else None


def _trigger_r02(case_dir: Path) -> Optional[str]:
    f = _find_file(case_dir, "citation_profiler")
    return str(f) if f and check_file_has_alert_type(f, "citation_cartel") else None


def _trigger_r03(case_dir: Path) -> Optional[str]:
    f = _find_file(case_dir, "papers")
    return str(f) if f and check_papers_have_keyword(f, ["clinical trial", "patient"]) else None


def _trigger_r04(case_dir: Path) -> Optional[str]:
    f = _find_file(case_dir, "papers")
    return str(f) if f and check_has_cjk_and_english(f) else None


def _trigger_r05(case_dir: Path) -> Optional[str]:
    f = _find_file(case_dir, "papers")
    if f and check_journal_frequency(f, threshold=3):
        return str(f)
    return None


def _trigger_r06(case_dir: Path) -> Optional[str]:
    f = _find_file(case_dir, "quality_rubric", "quality")
    if not f:
        return None
    data = load_json(f)
    if not isinstance(data, dict):
        return None
    details = data.get("details", {})
    cluster = details.get("cluster") if isinstance(details, dict) else None
    if cluster in ("C", "D", "c", "d"):
        return str(f)
    for signal in data.get("signals", []):
        if isinstance(signal, dict):
            ev = signal.get("evidence", {})
            if isinstance(ev, dict) and ev.get("cluster") in ("C", "D", "c", "d"):
                return str(f)
    return None


def _trigger_r07(case_dir: Path) -> Optional[str]:
    f = _find_file(case_dir, "papers")
    return str(f) if f and check_has_dois(f) else None


def _trigger_r08(case_dir: Path) -> Optional[str]:
    f = _find_file(case_dir, "papers")
    return str(f) if f and check_has_issns(f) else None


def _trigger_r09(case_dir: Path) -> Optional[str]:
    f = _find_file(case_dir, "papers")
    return str(f) if f and check_has_conference_papers(f) else None


# ---------------------------------------------------------------------------
# Default recommendation rules
# ---------------------------------------------------------------------------

RECOMMENDATION_RULES: list[dict] = [
    {
        "id": "R01",
        "trigger": _trigger_r01,
        "tools": ["publication_trace/preprint_monitor"],
        "priority": 1,
        "reason": "Common heuristics detected signals. Preprint monitoring recommended.",
    },
    {
        "id": "R02",
        "trigger": _trigger_r02,
        "tools": [
            "data_forensics/stats_reverse_engineer",
            "data_forensics/image_metadata_extractor",
        ],
        "priority": 1,
        "reason": "Citation cartel pattern detected. Deep data forensics advised.",
    },
    {
        "id": "R03",
        "trigger": _trigger_r03,
        "tools": [
            "ethics_audit/ethics_statement_parser",
            "ethics_audit/clinical_trial_registry_checker",
        ],
        "priority": 2,
        "reason": "Clinical content detected in papers. Ethics audit recommended.",
    },
    {
        "id": "R04",
        "trigger": _trigger_r04,
        "tools": ["publication_trace/bilingual_publication_detector"],
        "priority": 2,
        "reason": "Both CJK and English titles found. Bilingual publication check advised.",
    },
    {
        "id": "R05",
        "trigger": _trigger_r05,
        "tools": ["peer_review_intel/review_cycle_analyzer"],
        "priority": 2,
        "reason": "High journal concentration detected. Review cycle analysis recommended.",
    },
    {
        "id": "R06",
        "trigger": _trigger_r06,
        "tools": [
            "peer_review_intel/editorial_self_publishing_detector",
            "peer_review_intel/recommended_reviewer_network",
        ],
        "priority": 3,
        "reason": "Quality rubric shows C/D cluster. Peer review intelligence advised.",
    },
    {
        "id": "R07",
        "trigger": _trigger_r07,
        "tools": ["publication_trace/crossref_event_tracker"],
        "priority": 3,
        "reason": "Papers have DOIs. Crossref event tracking available.",
    },
    {
        "id": "R08",
        "trigger": _trigger_r08,
        "tools": ["peer_review_intel/journal_retraction_history"],
        "priority": 4,
        "reason": "Journal ISSNs available. Retraction history check possible.",
    },
    {
        "id": "R09",
        "trigger": _trigger_r09,
        "tools": ["publication_trace/conference_paper_mapper"],
        "priority": 3,
        "reason": "Conference papers detected. Conference-to-journal mapping recommended.",
    },
]


# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------

class RuleEngine:
    """Evaluate recommendation rules against case directory output."""

    def __init__(self, rules: Optional[list[dict]] = None):
        self.rules = rules if rules is not None else RECOMMENDATION_RULES.copy()

    def evaluate(self, case_dir: Path) -> list[Recommendation]:
        """Scan case_dir for output JSON files and return triggered recommendations."""
        case_dir = Path(case_dir).resolve()
        recommendations: list[Recommendation] = []
        seen: set[str] = set()

        for rule in self.rules:
            trigger = rule["trigger"]
            source: Optional[str] = None
            if isinstance(trigger, str):
                matches = list(case_dir.rglob(trigger))
                if matches:
                    source = str(matches[0])
            elif callable(trigger):
                source = trigger(case_dir)
            if source:
                key = f"{rule['id']}:{','.join(rule['tools'])}"
                if key in seen:
                    continue
                seen.add(key)
                recommendations.append(
                    Recommendation(
                        priority=rule["priority"],
                        tools=rule["tools"],
                        reason=rule["reason"],
                        rule_id=rule["id"],
                        trigger_source=source,
                    )
                )
        recommendations.sort(key=lambda r: (r.priority, r.rule_id))
        logger.info(
            "RuleEngine: %d rules evaluated, %d recommendations for %s",
            len(self.rules),
            len(recommendations),
            case_dir,
        )
        return recommendations

    def get_recommendations_for_phase(
        self, phase: str, case_dir: Path
    ) -> list[Recommendation]:
        """Return recommendations appropriate for the given investigation phase."""
        if phase == "deep_evidence":
            return self.evaluate(case_dir)
        return []
