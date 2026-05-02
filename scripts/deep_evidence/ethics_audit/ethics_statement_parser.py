#!/usr/bin/env python3
"""
ethics_statement_parser.py

Parse ethics statements from papers to extract and validate IRB/ethics information.
Detects missing approval numbers, generic template language, and contradictions
between study design and ethics disclosure.

Supported sources: free text / local JSON paper dumps (no paid APIs).

Usage:
    python ethics_statement_parser.py --papers ./data/papers.json \
        --output ./data/ethics_audit.json [--check-clinical] [--verbose]

    python ethics_statement_parser.py --text-dir ./data/txt_papers/ \
        --output ./data/ethics_audit.json [--check-clinical] [--verbose]
"""

import json
import argparse
import re
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import Optional
import sys
import difflib

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.utils import get_logger, save_json

logger = get_logger("ethics_statement_parser")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ParsedEthics:
    paper_id: str
    title: str
    ethics_found: bool
    approval_numbers: list[str]
    approval_date: Optional[str]
    informed_consent: str          # yes | no | unclear
    animal_ethics: str             # yes | no | unclear
    generic_statement: bool
    missing_number: bool
    contradiction: bool
    confidence: str                # low | medium | high
    explanation: str
    raw_snippets: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Keyword & pattern definitions
# ---------------------------------------------------------------------------

ETHICS_KEYWORDS = [
    "IRB", "ethics committee", "institutional review",
    "知情同意", "伦理委员会", "伦理审批", "animal care",
    "IACUC", "institutional animal care", "ethical approval",
    "伦理审查", "伦理批准", " Helsinki ", "declaration of Helsinki",
]

CLINICAL_KEYWORDS = [
    "clinical trial", "randomized controlled", "RCT", "patient",
    "patients", "subjects", "participant", "participants",
    "临床研究", "临床试验", "患者", "受试者", "随机对照",
]

INFORMED_CONSENT_KEYWORDS = [
    "informed consent", "signed consent", "written consent",
    "oral consent", "知情同意", "患者知情同意", "家属知情同意",
]

ANIMAL_ETHICS_KEYWORDS = [
    "animal", "IACUC", "institutional animal care",
    "动物实验", "动物伦理", "实验动物", "animal welfare",
]

GENERIC_TEMPLATES = [
    "本研究已通过伦理委员会批准",
    "本研究经伦理委员会批准",
    "所有患者均签署知情同意书",
    "所有受试者均签署知情同意书",
    "the study was approved by the ethics committee",
    "the study was approved by the institutional review board",
    "ethical approval was obtained from",
]

APPROVAL_NUMBER_PATTERNS = [
    re.compile(r"[A-Z]{2,}-\d{4,}-\d+"),
    re.compile(r"\d{4}[年/-]\d+[-号]?\d*"),
    re.compile(r"IRB[\s.#-]?\d+"),
    re.compile(r"EC[\s.#-]?\d+"),
    re.compile(r"伦理批件[号]?[：:]\s*\d+"),
]

DATE_PATTERN = re.compile(r"(\d{4}[年/-]\d{1,2}[月/-]\d{1,2}[日]?)")


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _load_text(paper: dict) -> str:
    """Extract best available text from paper dict."""
    for key in ("full_text", "text", "body", "content"):
        if paper.get(key):
            return str(paper[key])
    parts = []
    for key in ("title", "abstract", "summary"):
        if paper.get(key):
            parts.append(str(paper[key]))
    return "\n".join(parts)


def _contains_any(text: str, keywords: list[str]) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def _find_approval_numbers(text: str) -> list[str]:
    found: set[str] = set()
    for pat in APPROVAL_NUMBER_PATTERNS:
        for m in pat.finditer(text):
            found.add(m.group(0).strip())
    return sorted(found)


def _find_approval_date(text: str) -> Optional[str]:
    m = DATE_PATTERN.search(text)
    return m.group(1) if m else None


def _has_generic_template(text: str) -> bool:
    text_lower = text.lower()
    for tmpl in GENERIC_TEMPLATES:
        if tmpl.lower() in text_lower:
            return True
    return False


def _check_informed_consent(text: str) -> str:
    if _contains_any(text, INFORMED_CONSENT_KEYWORDS):
        return "yes"
    if _contains_any(text, ["no consent", "豁免知情同意", "waived"]):
        return "no"
    return "unclear"


def _check_animal_ethics(text: str) -> str:
    if _contains_any(text, ANIMAL_ETHICS_KEYWORDS):
        if _contains_any(text, ["approved", "批准", "伦理批件", "IACUC"]):
            return "yes"
    return "unclear"


def _extract_snippets(text: str, keywords: list[str], window: int = 80) -> list[str]:
    """Extract surrounding text for each keyword hit."""
    snippets = []
    text_lower = text.lower()
    for kw in keywords:
        idx = text_lower.find(kw.lower())
        if idx >= 0:
            start = max(0, idx - window)
            end = min(len(text), idx + len(kw) + window)
            snippets.append(text[start:end].replace("\n", " "))
    return snippets[:5]


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_approval_format(number: str) -> bool:
    """Basic format validation for major Chinese hospital/university patterns."""
    # Chinese hospital format: XXXX-YYYY-ZZZ or 2023-001
    if re.match(r"^\d{4}[年/-]\d+[号]?$", number):
        return True
    # University IRB format: IRB-YYYY-NNNN
    if re.match(r"^IRB[\s.#-]?\d+", number, re.I):
        return True
    # Standard alphanumeric
    if re.match(r"^[A-Z]{2,}-\d{4,}-\d+$", number):
        return True
    return False


def _has_clinical_indicators(paper: dict, text: str) -> bool:
    title = str(paper.get("title", ""))
    abstract = str(paper.get("abstract", ""))
    combined = f"{title} {abstract}"
    return _contains_any(combined, CLINICAL_KEYWORDS)


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------

def parse_paper(paper: dict, check_clinical: bool = False) -> ParsedEthics:
    paper_id = str(paper.get("id", paper.get("doi", paper.get("title", "unknown"))))
    title = str(paper.get("title", ""))
    text = _load_text(paper)
    text_lower = text.lower()

    ethics_found = _contains_any(text, ETHICS_KEYWORDS)
    approval_numbers = _find_approval_numbers(text) if ethics_found else []
    approval_date = _find_approval_date(text) if ethics_found else None
    informed_consent = _check_informed_consent(text)
    animal_ethics = _check_animal_ethics(text)
    generic_statement = _has_generic_template(text) if ethics_found else False
    missing_number = ethics_found and len(approval_numbers) == 0

    # Validate each approval number
    valid_numbers = [n for n in approval_numbers if _validate_approval_format(n)]

    contradiction = False
    if check_clinical and _has_clinical_indicators(paper, text) and not ethics_found:
        contradiction = True

    # Confidence scoring
    confidence = "low"
    if ethics_found and not missing_number and not generic_statement:
        confidence = "high"
    elif ethics_found and valid_numbers:
        confidence = "medium"
    elif ethics_found:
        confidence = "medium"

    explanation_parts = []
    if ethics_found:
        explanation_parts.append(f"发现伦理声明， approval numbers: {len(approval_numbers)}")
    else:
        explanation_parts.append("未找到伦理声明")
    if missing_number:
        explanation_parts.append("提及伦理但未找到批号")
    if generic_statement:
        explanation_parts.append("疑似模板化表述")
    if contradiction:
        explanation_parts.append("研究涉及人体但无伦理声明，疑似矛盾")

    snippets = _extract_snippets(text, ETHICS_KEYWORDS) if ethics_found else []

    return ParsedEthics(
        paper_id=paper_id,
        title=title,
        ethics_found=ethics_found,
        approval_numbers=valid_numbers,
        approval_date=approval_date,
        informed_consent=informed_consent,
        animal_ethics=animal_ethics,
        generic_statement=generic_statement,
        missing_number=missing_number,
        contradiction=contradiction,
        confidence=confidence,
        explanation="；".join(explanation_parts),
        raw_snippets=snippets,
    )


def parse_from_directory(text_dir: Path) -> list[ParsedEthics]:
    results = []
    if not text_dir.exists():
        logger.error("Text directory not found: %s", text_dir)
        return results
    for txt_path in sorted(text_dir.glob("*.txt")):
        text = txt_path.read_text(encoding="utf-8")
        paper = {
            "id": txt_path.stem,
            "title": txt_path.stem,
            "full_text": text,
        }
        results.append(parse_paper(paper))
    logger.info("Parsed %d papers from %s", len(results), text_dir)
    return results


def parse_from_json(papers_path: Path) -> list[ParsedEthics]:
    with open(papers_path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    paper_list = raw if isinstance(raw, list) else raw.get("papers", [])
    logger.info("Loaded %d papers from %s", len(paper_list), papers_path)
    return [parse_paper(p) for p in paper_list]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Parse and validate ethics statements from papers")
    p.add_argument("--papers", type=Path, help="Path to papers JSON file")
    p.add_argument("--text-dir", type=Path, help="Directory containing .txt paper files")
    p.add_argument("--output", type=Path, default=Path("./data/ethics_audit.json"), help="Output JSON path")
    p.add_argument("--check-clinical", action="store_true", help="Flag contradictions for clinical/patient studies")
    p.add_argument("--verbose", action="store_true", help="Verbose logging")
    return p


def main():
    args = build_parser().parse_args()
    if args.verbose:
        logger.setLevel("DEBUG")

    if not args.papers and not args.text_dir:
        logger.error("Must provide --papers or --text-dir")
        sys.exit(1)

    if args.papers and args.papers.exists():
        results = parse_from_json(args.papers)
    elif args.text_dir and args.text_dir.exists():
        results = parse_from_directory(args.text_dir)
    else:
        input_path = args.papers or args.text_dir
        logger.error("Input not found: %s", input_path)
        sys.exit(1)

    flagged = [r for r in results if r.missing_number or r.contradiction or r.generic_statement]

    signals = []
    for r in flagged:
        flag_count = sum([r.missing_number, r.contradiction, r.generic_statement])
        conf = 0.8 if flag_count >= 2 else 0.6
        if r.missing_number:
            signals.append({
                "type": "missing_ethics_number",
                "description": r.explanation[:200],
                "confidence": conf,
                "paper_id": r.paper_id,
                "source": "ethics_statement_parser",
                "evidence": {
                    "approval_numbers": r.approval_numbers,
                    "ethics_found": r.ethics_found,
                },
            })
        if r.generic_statement:
            signals.append({
                "type": "generic_ethics_statement",
                "description": r.explanation[:200],
                "confidence": conf,
                "paper_id": r.paper_id,
                "source": "ethics_statement_parser",
                "evidence": {
                    "generic_statement": True,
                    "raw_snippets": r.raw_snippets[:2],
                },
            })
        if r.contradiction:
            signals.append({
                "type": "ethics_contradiction",
                "description": r.explanation[:200],
                "confidence": conf,
                "paper_id": r.paper_id,
                "source": "ethics_statement_parser",
                "evidence": {
                    "contradiction": True,
                    "informed_consent": r.informed_consent,
                },
            })

    result = {
        "meta": {
            "script": "ethics_statement_parser",
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "input_file": str(args.papers or args.text_dir),
        },
        "signals": signals,
        "details": {
            "results": [asdict(r) for r in results],
            "summary": {
                "ethics_found": sum(1 for r in results if r.ethics_found),
                "missing_number": sum(1 for r in results if r.missing_number),
                "generic_statement": sum(1 for r in results if r.generic_statement),
                "contradiction": sum(1 for r in results if r.contradiction),
                "animal_ethics_yes": sum(1 for r in results if r.animal_ethics == "yes"),
                "informed_consent_yes": sum(1 for r in results if r.informed_consent == "yes"),
            },
        },
    }

    save_json(result, args.output)
    logger.info("Saved ethics audit to %s", args.output)

    print(f"\n{'='*60}")
    print("Ethics Statement Parser Summary")
    print(f"{'='*60}")
    print(f"Papers scanned:     {len(results)}")
    print(f"Ethics found:       {result['summary']['ethics_found']}")
    print(f"Missing numbers:    {result['summary']['missing_number']}")
    print(f"Generic statements: {result['summary']['generic_statement']}")
    print(f"Contradictions:     {result['summary']['contradiction']}")
    if flagged:
        print(f"\nTop flags:")
        for r in flagged[:5]:
            print(f"  [{r.confidence.upper()}] {r.paper_id}: {r.explanation}")
    print(f"\nOutput:             {args.output}")


if __name__ == "__main__":
    main()
