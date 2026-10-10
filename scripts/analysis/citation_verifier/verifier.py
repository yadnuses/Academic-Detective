#!/usr/bin/env python3
"""
verifier.py — Citation verification task builder and result merger.

This module does NOT call external LLM APIs.  Academic-Detective is operated
by an LLM agent that performs verification itself using web search and
reasoning.  This module provides two helpers:

  build_task(citations)  → produces a verification task JSON template
                           with empty verification fields for the LLM to fill
  merge_results(task)    → merges filled verification fields back into a
                           results list ready for the reporter
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List


# ---------------------------------------------------------------------------
# Task template
# ---------------------------------------------------------------------------

_VERIFICATION_TEMPLATE = {
    "citation_exists": "",
    "citation_integrity": "",
    "citation_integrity_details": "",
    "citation_usage_correct": "",
    "citation_usage_reasoning": "",
    "recommendation": "",
    "suggested_replacement": "",
}


def build_task(citations: List[dict], output_path: str = None) -> dict:
    """Build a verification task template from extracted citations.

    Each citation gets an empty ``verification`` dict that the operating LLM
    fills in after checking the reference.

    Args:
        citations: List of citation dicts from the parser.
        output_path: Optional path to write the task JSON.

    Returns:
        Task dict with citations and empty verification fields.
    """
    task = {
        "task_type": "citation_verification",
        "created_at": datetime.now().isoformat(),
        "instruction": (
            "For each citation below, verify:\n"
            "  1. citation_exists: Does the cited paper actually exist? (Yes/No)\n"
            "  2. citation_integrity: Is the metadata (author, year, title) correct? (Correct/Incorrect)\n"
            "  3. citation_integrity_details: Explain any discrepancies.\n"
            "  4. citation_usage_correct: Does the cited paper support the claim in the usage text? (Yes/No/Partially)\n"
            "  5. citation_usage_reasoning: Explain your assessment.\n"
            "  6. recommendation: KEEP / REPLACE / REMOVE\n"
            "  7. suggested_replacement: If REPLACE, provide the full reference.\n"
            "\n"
            "Multi-citation rule: if the text cites multiple sources (e.g. \"(1, 2)\"),\n"
            "this reference only needs to support ONE PART of the claim.\n"
        ),
        "citations": [
            {
                "key": cit.get("key", ""),
                "ref_text": cit.get("ref_text", ""),
                "usage_count": cit.get("usage_count", 0),
                "context_block": cit.get("context_block", ""),
                "verification": dict(_VERIFICATION_TEMPLATE),
            }
            for cit in citations
        ],
    }

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(task, f, ensure_ascii=False, indent=2)

    return task


def merge_results(task: dict) -> List[dict]:
    """Extract completed verification results from a filled task.

    Call this after the operating LLM has filled in the ``verification``
    fields for each citation.

    Args:
        task: Task dict with filled verification fields.

    Returns:
        List of result dicts ready for the reporter.
    """
    results = []
    for cit in task.get("citations", []):
        v = cit.get("verification", {})
        # Check if the LLM actually filled in the fields
        if not any(v.get(k) for k in ("citation_exists", "citation_usage_correct")):
            v["status"] = "unverified"
        results.append({
            "key": cit.get("key", ""),
            "ref_text": cit.get("ref_text", ""),
            "usage_count": cit.get("usage_count", 0),
            "verification": v,
        })
    return results
