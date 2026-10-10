#!/usr/bin/env python3
"""
reporter.py — Citation verification report generation.

Produces structured JSON compatible with Academic-Detective's pipeline
and human-readable summaries.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def save_report(
    results: List[dict],
    output_path: str,
    case_id: str = "",
    scholar_name: str = "",
) -> dict:
    """Save verification results to JSON and optional CSV.

    Args:
        results: List of merged citation+verification dicts from verifier.
        output_path: Path to the output JSON file.
        case_id: Optional case identifier.
        scholar_name: Optional scholar name.

    Returns:
        The report dict that was saved.
    """
    report = _build_report(results, case_id, scholar_name)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Also save a CSV alongside for quick review
    csv_path = out.with_suffix(".csv")
    _save_csv(results, csv_path)

    # Save issues-only CSV
    issues_csv = out.with_name(out.stem + "_issues.csv")
    _save_csv(results, issues_csv, issues_only=True)

    return report


def _build_report(results: List[dict], case_id: str, scholar_name: str) -> dict:
    """Build the structured report dict."""
    total = len(results)
    exists_yes = sum(1 for r in results if r.get("verification", {}).get("citation_exists", "").lower() == "yes")
    exists_no = sum(1 for r in results if r.get("verification", {}).get("citation_exists", "").lower() == "no")
    integrity_ok = sum(1 for r in results if r.get("verification", {}).get("citation_integrity", "").lower() == "correct")
    integrity_bad = sum(1 for r in results if "incorrect" in r.get("verification", {}).get("citation_integrity", "").lower())
    usage_ok = sum(1 for r in results if r.get("verification", {}).get("citation_usage_correct", "").lower() == "yes")
    usage_no = sum(1 for r in results if r.get("verification", {}).get("citation_usage_correct", "").lower() == "no")
    usage_partial = sum(1 for r in results if "partial" in r.get("verification", {}).get("citation_usage_correct", "").lower())
    pro_count = sum(1 for r in results if r.get("verification", {}).get("pro_verified"))
    override_count = sum(1 for r in results if r.get("verification", {}).get("pro_override"))

    # Collect flagged citations as anomaly signals
    flagged = []
    for r in results:
        v = r.get("verification", {})
        if _is_flagged(v):
            flagged.append({
                "citation_key": r.get("key", ""),
                "exists": v.get("citation_exists", ""),
                "integrity": v.get("citation_integrity", ""),
                "usage": v.get("citation_usage_correct", ""),
                "reasoning": v.get("citation_usage_reasoning", ""),
                "recommendation": v.get("recommendation", ""),
                "pro_override": v.get("pro_override", False),
            })

    return {
        "report_type": "citation_verification",
        "generated_at": datetime.now().isoformat(),
        "case_id": case_id,
        "scholar_name": scholar_name,
        "summary": {
            "total_citations": total,
            "exists": {"yes": exists_yes, "no": exists_no},
            "integrity": {"correct": integrity_ok, "incorrect": integrity_bad},
            "usage": {"yes": usage_ok, "no": usage_no, "partial": usage_partial},
            "pro_model": {"verified": pro_count, "overrides": override_count},
            "flagged_count": len(flagged),
        },
        "flagged_citations": flagged,
        "citations": [
            {
                "key": r.get("key", ""),
                "ref_text": r.get("ref_text", ""),
                "usage_count": r.get("usage_count", 0),
                "verification": r.get("verification", {}),
            }
            for r in results
        ],
    }


def _is_flagged(v: dict) -> bool:
    """Check if a verification result is flagged as problematic."""
    if v.get("citation_exists", "").lower() == "no":
        return True
    if "incorrect" in v.get("citation_integrity", "").lower():
        return True
    if v.get("citation_usage_correct", "").lower() in ("no", "partially"):
        return True
    if v.get("recommendation", "").upper() in ("REPLACE", "REMOVE"):
        return True
    return False


def _save_csv(results: List[dict], csv_path: Path, issues_only: bool = False) -> None:
    """Save results as CSV for quick human review."""
    rows = []
    for r in results:
        v = r.get("verification", {})
        if issues_only and not _is_flagged(v):
            continue
        rows.append({
            "Key": r.get("key", ""),
            "Ref Text": r.get("ref_text", "")[:200],
            "Exists": v.get("citation_exists", ""),
            "Integrity": v.get("citation_integrity", ""),
            "Usage": v.get("citation_usage_correct", ""),
            "Reasoning": v.get("citation_usage_reasoning", "")[:300],
            "Recommendation": v.get("recommendation", ""),
            "Pro Override": "Yes" if v.get("pro_override") else "",
        })

    if not rows:
        return

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def generate_summary(results: List[dict]) -> str:
    """Generate a human-readable summary string."""
    report = _build_report(results, "", "")
    s = report["summary"]
    lines = [
        "=== Citation Verification Summary ===",
        f"Total citations checked: {s['total_citations']}",
        "",
        "Existence:",
        f"  Confirmed: {s['exists']['yes']}",
        f"  Not found: {s['exists']['no']}",
        "",
        "Integrity (metadata accuracy):",
        f"  Correct:   {s['integrity']['correct']}",
        f"  Incorrect: {s['integrity']['incorrect']}",
        "",
        "Usage (supports the claim?):",
        f"  Yes:       {s['usage']['yes']}",
        f"  No:        {s['usage']['no']}",
        f"  Partial:   {s['usage']['partial']}",
    ]
    if s["pro_model"]["verified"] > 0:
        lines.extend([
            "",
            "Strong model verification:",
            f"  Verified:  {s['pro_model']['verified']}",
            f"  Overrides: {s['pro_model']['overrides']}",
        ])
    if s["flagged_count"] > 0:
        lines.extend(["", f"Flagged citations: {s['flagged_count']}"])
        for fc in report["flagged_citations"][:10]:
            lines.append(f"  [{fc['citation_key']}] {fc['integrity']} | {fc['usage']} | {fc['reasoning'][:80]}")
    lines.append("=" * 38)
    return "\n".join(lines)
