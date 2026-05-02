#!/usr/bin/env python3
"""
cross_border/validator.py

Validate cross-border scholar data for consistency:
- Timeline consistency (cannot be full-time in two countries simultaneously)
- Title mapping合理性 (国内教授 vs 国外助理教授需有合理解释)
- Paper duplication detection
- Education-career timeline coherence

Usage:
    python cross_border/validator.py --input ./data/merged_cross_border.json
"""

import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from core.utils import get_logger

logger = get_logger("cross_border_validator")


# Title hierarchy mapping (from low to high)
_TITLE_HIERARCHY = {
    "postdoc": 1,
    "researcher": 1,
    "assistant professor": 2,
    "associate professor": 3,
    "professor": 4,
    "distinguished professor": 5,
    "chair professor": 5,
    # Chinese equivalents
    "博士后": 1,
    "助理研究员": 1,
    "助理教授": 2,
    "副教授": 3,
    "教授": 4,
    "特聘教授": 5,
    "长江学者": 5,
}


def _get_title_level(title: str) -> int:
    """Get numeric level for a title."""
    if not title:
        return 0
    title_lower = title.lower()
    # Match longer keys first to avoid "professor" matching before "distinguished professor"
    for t, level in sorted(_TITLE_HIERARCHY.items(), key=lambda x: -len(x[0])):
        if t in title_lower:
            return level
    return 0


def validate_timeline_consistency(data: dict) -> list[dict]:
    """Check if career timeline has impossible overlaps."""
    errors = []
    timeline = data.get("basic_profile", {}).get("career_timeline", [])

    if not isinstance(timeline, list):
        return errors

    # Extract employment periods with institutions
    periods = []
    for event in timeline:
        if not isinstance(event, dict):
            continue
        year = event.get("year")
        if not year:
            continue
        event_text = event.get("event", "")
        institution = event.get("institution", "")

        # Detect employment start/end events
        if any(kw in event_text for kw in ["入职", "joined", "appointed", "聘", "任教"]):
            periods.append({
                "start": year,
                "end": None,
                "institution": institution,
                "event": event_text,
            })
        elif any(kw in event_text for kw in ["离职", "left", "resigned", "departed", "调离"]):
            # Try to match with last unclosed period
            for p in reversed(periods):
                if p["end"] is None:
                    p["end"] = year
                    break

    # Check for overlapping full-time positions
    for i, p1 in enumerate(periods):
        for p2 in periods[i + 1:]:
            if p1["institution"] == p2["institution"]:
                continue
            # Check overlap
            s1, e1 = p1["start"], p1["end"] or datetime.now().year
            s2, e2 = p2["start"], p2["end"] or datetime.now().year
            if s1 <= e2 and s2 <= e1:
                overlap_start = max(s1, s2)
                overlap_end = min(e1, e2)
                if overlap_end - overlap_start >= 2:  # Overlap of 2+ years
                    errors.append({
                        "type": "timeline_overlap",
                        "severity": "high",
                        "description": (
                            f"时间线重叠：{p1['institution']} ({p1['start']}-{p1['end'] or '现在'}) "
                            f"与 {p2['institution']} ({p2['start']}-{p2['end'] or '现在'}) "
                            f"重叠 {overlap_start}-{overlap_end}"
                        ),
                        "details": {
                            "period1": p1,
                            "period2": p2,
                            "overlap_years": list(range(overlap_start, overlap_end + 1)),
                        },
                        "suggestion": "核实是否为兼职/访问职位，或确认时间线准确性",
                    })

    return errors


def validate_title_mapping(data: dict) -> list[dict]:
    """Check if title progression across borders is reasonable."""
    errors = []
    cross_info = data.get("cross_border_info", {})
    conflicts = cross_info.get("conflicts", [])

    # Check for title inconsistency conflicts
    for conflict in conflicts:
        if conflict.get("type") == "title_inconsistency":
            errors.append({
                "type": "title_mapping_unreasonable",
                "severity": conflict["severity"],
                "description": conflict["description"],
                "details": {
                    "domestic_title": conflict.get("domestic"),
                    "international_title": conflict.get("international"),
                },
                "suggestion": "核实时间线：是否国内职称是在国外晋升之后获得的",
            })

    # Additional check: if domestic title is higher than international, verify timeline
    profile = data.get("basic_profile", {})
    dom_title = cross_info.get("domestic_counterpart", {}).get("title_cn", "")
    intl_title = profile.get("current_title", "")

    dom_level = _get_title_level(dom_title)
    intl_level = _get_title_level(intl_title)

    if dom_level > 0 and intl_level > 0:
        if intl_level > dom_level + 1:
            errors.append({
                "type": "title_progression_unusual",
                "severity": "low",
                "description": (
                    f"国际职级（{intl_title}, level {intl_level}）显著高于国内职级"
                    f"（{dom_title}, level {dom_level}），需确认是否为跳槽晋升"
                ),
                "details": {"domestic_level": dom_level, "international_level": intl_level},
                "suggestion": "核实是否为海外引进人才或特殊人才计划",
            })

    return errors


def validate_paper_consistency(data: dict) -> list[dict]:
    """Check paper metadata consistency across sources."""
    errors = []
    papers = data.get("academic_outputs", {}).get("paper_list", [])
    cross_info = data.get("cross_border_info", {})

    # Check for papers with conflicting metadata
    doi_map = {}
    for p in papers:
        doi = p.get("doi", "").lower().strip()
        if doi:
            if doi in doi_map:
                prev = doi_map[doi]
                # Compare key fields
                conflicts = []
                for field in ["year", "journal", "title"]:
                    v1 = prev.get(field)
                    v2 = p.get(field)
                    if v1 and v2 and v1 != v2:
                        conflicts.append(f"{field}: '{v1}' vs '{v2}'")
                if conflicts:
                    errors.append({
                        "type": "paper_metadata_conflict",
                        "severity": "low",
                        "description": f"DOI {doi} 的论文元数据存在冲突: {'; '.join(conflicts)}",
                        "details": {"doi": doi, "conflicts": conflicts},
                        "suggestion": "核实原始数据源，选择更权威的来源",
                    })
            else:
                doi_map[doi] = p

    # Check duplicate ratio
    dup_count = cross_info.get("duplicates", 0)
    total = len(papers)
    if total > 0:
        dup_ratio = dup_count / total
        if dup_ratio > 0.5:
            errors.append({
                "type": "high_duplication_rate",
                "severity": "medium",
                "description": f"国内外论文重复率过高 ({dup_count}/{total} = {dup_ratio*100:.0f}%)，可能为同一时期产出",
                "details": {"duplicate_count": dup_count, "total_papers": total, "ratio": dup_ratio},
                "suggestion": "核实是否国内任职期间同时保留了国外兼职职位",
            })

    return errors


def validate_education_coherence(data: dict) -> list[dict]:
    """Check if education timeline is coherent with career timeline."""
    errors = []
    profile = data.get("basic_profile", {})
    education = profile.get("education_background", [])
    timeline = profile.get("career_timeline", [])

    if not isinstance(education, list) or not isinstance(timeline, list):
        return errors

    # Find PhD year
    phd_year = None
    for edu in education:
        if not isinstance(edu, dict):
            continue
        degree = edu.get("degree", "").lower()
        if degree in ["phd", "博士", "doctor"]:
            phd_year = edu.get("year")
            break

    if not phd_year:
        return errors

    # Find first professorial appointment
    first_prof_year = None
    for event in timeline:
        if not isinstance(event, dict):
            continue
        year = event.get("year")
        event_text = event.get("event", "").lower()
        if year and any(kw in event_text for kw in ["professor", "教授", "appointed", "joined"]):
            first_prof_year = year
            break

    if first_prof_year and first_prof_year < phd_year:
        errors.append({
            "type": "education_career_incoherence",
            "severity": "high",
            "description": (
                f"职业时间线显示 {first_prof_year} 年已有教职记录，"
                f"但博士毕业于 {phd_year} 年，存在时间矛盾"
            ),
            "details": {"phd_year": phd_year, "first_prof_year": first_prof_year},
            "suggestion": "核实教育背景或职业时间线是否存在录入错误",
        })

    # Check if PhD to first independent position gap is reasonable
    if first_prof_year and first_prof_year - phd_year < 2:
        errors.append({
            "type": "rapid_promotion",
            "severity": "low",
            "description": (
                f"博士毕业 {phd_year} 年后 {first_prof_year} 年即获教职，"
                f"间隔仅 {first_prof_year - phd_year} 年"
            ),
            "details": {"phd_year": phd_year, "first_prof_year": first_prof_year, "gap": first_prof_year - phd_year},
            "suggestion": "核实是否为直博+快速晋升，或存在时间线缺失",
        })

    return errors


def validate(data: dict) -> tuple[list, list]:
    """
    Validate cross-border scholar data.

    Returns: (errors, warnings)
    """
    errors = []
    warnings = []

    # Run all validators
    timeline_errors = validate_timeline_consistency(data)
    title_errors = validate_title_mapping(data)
    paper_errors = validate_paper_consistency(data)
    edu_errors = validate_education_coherence(data)

    for e in timeline_errors + title_errors + paper_errors + edu_errors:
        if e["severity"] in ("high", "critical"):
            errors.append(e)
        else:
            warnings.append(e)

    # Overall assessment
    if not errors and not warnings:
        logger.info("Cross-border validation passed with no issues")
    else:
        logger.info("Cross-border validation: %d errors, %d warnings", len(errors), len(warnings))

    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description="Cross-border data validator")
    parser.add_argument("--input", "-i", required=True, help="Path to merged cross_border JSON")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    errors, warnings = validate(data)

    if warnings:
        for w in warnings:
            print(f"[WARNING] {w['type']}: {w['description']}")
            if w.get("suggestion"):
                print(f"          建议: {w['suggestion']}")

    if errors:
        for e in errors:
            print(f"[ERROR] {e['type']}: {e['description']}")
            if e.get("suggestion"):
                print(f"        建议: {e['suggestion']}")
        print(f"\nValidation FAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
    else:
        print(f"Validation PASSED: 0 error(s), {len(warnings)} warning(s)")


if __name__ == "__main__":
    main()
