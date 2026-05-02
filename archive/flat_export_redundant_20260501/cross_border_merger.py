#!/usr/bin/env python3
"""
cross_border/merger.py

Merge domestic and international scholar_data into a unified cross-border record.
Handles overseas-returned scholars with affiliations in both China and abroad.

Key operations:
- Deduplicate papers by DOI match
- Detect conflicts between domestic and international records
- Build unified timeline

Usage:
    python cross_border/merger.py \
        --domestic ./data/domestic_scholar.json \
        --international ./data/international_scholar.json \
        --output ./data/merged_cross_border.json
"""

import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from core.utils import get_logger, save_json

logger = get_logger("cross_border_merger")


def load_scholar_data(path: str | Path) -> dict:
    """Load scholar_data.json."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_doi(doi: str) -> str:
    """Normalize DOI for comparison."""
    if not doi:
        return ""
    doi = doi.lower().strip()
    doi = doi.replace("https://doi.org/", "")
    doi = doi.replace("http://doi.org/", "")
    doi = doi.replace("doi:", "")
    return doi.strip()


def normalize_title(title: str) -> str:
    """Normalize title for fuzzy comparison."""
    if not title:
        return ""
    title = title.lower().strip()
    # Remove common punctuation
    for ch in ":;,.!?-'\"()[]{}":
        title = title.replace(ch, " ")
    # Normalize whitespace
    title = " ".join(title.split())
    return title


def titles_similar(t1: str, t2: str, threshold: float = 0.85) -> bool:
    """Check if two titles are similar using simple word overlap."""
    n1 = normalize_title(t1)
    n2 = normalize_title(t2)
    if not n1 or not n2:
        return False
    if n1 == n2:
        return True
    words1 = set(n1.split())
    words2 = set(n2.split())
    if not words1 or not words2:
        return False
    intersection = words1 & words2
    union = words1 | words2
    if not union:
        return False
    jaccard = len(intersection) / len(union)
    return jaccard >= threshold


def deduplicate_papers(domestic_papers: list, international_papers: list) -> tuple[list, list]:
    """
    Deduplicate papers between domestic and international sources.

    Returns:
        (merged_papers, duplicates) where duplicates lists the matched pairs
    """
    merged = []
    duplicates = []
    seen_dois = set()
    seen_titles = []

    # Process international papers first (usually higher quality metadata)
    for p in international_papers:
        doi = normalize_doi(p.get("doi", ""))
        title = p.get("title", "")
        if doi and doi in seen_dois:
            continue
        # Check title similarity
        is_dup = any(titles_similar(title, existing) for existing in seen_titles)
        if is_dup:
            continue
        merged.append(p)
        if doi:
            seen_dois.add(doi)
        seen_titles.append(title)

    # Process domestic papers, flagging conflicts
    for p in domestic_papers:
        doi = normalize_doi(p.get("doi", ""))
        title = p.get("title", "")

        # Exact DOI match
        if doi and doi in seen_dois:
            duplicates.append({
                "type": "exact_doi_match",
                "domestic_paper": p,
                "international_paper": next(
                    (mp for mp in merged if normalize_doi(mp.get("doi", "")) == doi), None
                ),
            })
            continue

        # Title similarity match
        matched = None
        for mp in merged:
            if titles_similar(title, mp.get("title", "")):
                matched = mp
                break

        if matched:
            duplicates.append({
                "type": "title_similarity_match",
                "domestic_paper": p,
                "international_paper": matched,
            })
            # Merge metadata: prefer international for journal info, domestic for CN citations
            merged_paper = dict(matched)
            if p.get("citation_count_cn") and not merged_paper.get("citation_count"):
                merged_paper["citation_count_cn"] = p["citation_count_cn"]
            # Replace in merged list
            idx = merged.index(matched)
            merged[idx] = merged_paper
        else:
            # New paper unique to domestic source
            merged.append(p)
            if doi:
                seen_dois.add(doi)
            seen_titles.append(title)

    return merged, duplicates


def detect_conflicts(domestic: dict, international: dict) -> list[dict]:
    """Detect conflicts between domestic and international records."""
    conflicts = []

    dom_profile = domestic.get("basic_profile", {})
    intl_profile = international.get("basic_profile", {})

    # Name mismatch
    dom_name = domestic.get("name", "").strip()
    intl_name = international.get("name", "").strip()
    if dom_name and intl_name and dom_name != intl_name:
        conflicts.append({
            "type": "name_mismatch",
            "severity": "medium",
            "description": f"国内记录姓名 '{dom_name}' 与国际记录姓名 '{intl_name}' 不一致",
            "domestic": dom_name,
            "international": intl_name,
        })

    # Institution simultaneous tenure (impossible to be full-time in two countries)
    dom_inst = dom_profile.get("institution", "")
    intl_inst = intl_profile.get("institution", "")
    if dom_inst and intl_inst:
        dom_tenure = dom_profile.get("tenure_status", "")
        intl_tenure = intl_profile.get("tenure_status", "")
        # If both show active full-time positions without end dates, flag
        if dom_tenure in ("tenured", "tenure_track") and intl_tenure in ("tenured", "tenure_track"):
            conflicts.append({
                "type": "simultaneous_fulltime",
                "severity": "high",
                "description": f"国内 '{dom_inst}' 与国际 '{intl_inst}' 均显示全职任职，时间线可能重叠",
                "domestic": {"institution": dom_inst, "status": dom_tenure},
                "international": {"institution": intl_inst, "status": intl_tenure},
            })

    # Title inconsistency
    dom_title = dom_profile.get("current_title", "")
    intl_title = intl_profile.get("current_title", "")
    title_mappings = {
        ("教授", "assistant professor"): "职称差异巨大：国内教授 vs 国外助理教授",
        ("教授", "postdoc"): "职称差异巨大：国内教授 vs 国外博士后",
    }
    for (cn, en), msg in title_mappings.items():
        if cn in dom_title.lower() and en in intl_title.lower():
            conflicts.append({
                "type": "title_inconsistency",
                "severity": "medium",
                "description": msg,
                "domestic": dom_title,
                "international": intl_title,
            })

    # Paper count discrepancy
    dom_verified = domestic.get("academic_outputs", {}).get("verified_papers", 0)
    intl_verified = international.get("academic_outputs", {}).get("verified_papers", 0)
    if isinstance(dom_verified, int) and isinstance(intl_verified, int):
        if dom_verified > 0 and intl_verified > 0:
            discrepancy = abs(dom_verified - intl_verified) / max(dom_verified, intl_verified)
            if discrepancy > 0.3:
                conflicts.append({
                    "type": "paper_count_discrepancy",
                    "severity": "low",
                    "description": (
                        f"国内核实 {dom_verified} 篇 vs 国际核实 {intl_verified} 篇，"
                        f"差异率 {discrepancy*100:.0f}%"
                    ),
                    "domestic": dom_verified,
                    "international": intl_verified,
                })

    return conflicts


def merge_profiles(domestic: dict, international: dict) -> dict:
    """Merge basic_profile from both sources."""
    dom_profile = domestic.get("basic_profile", {})
    intl_profile = international.get("basic_profile", {})

    # Prefer international for English fields, domestic for Chinese fields
    merged = {
        "name": dom_profile.get("name", intl_profile.get("name", "")),
        "name_en": intl_profile.get("name", dom_profile.get("name", "")),
        "institution": dom_profile.get("institution", intl_profile.get("institution", "")),
        "institution_en": intl_profile.get("institution", dom_profile.get("institution_en", "")),
        "current_title": intl_profile.get("current_title", dom_profile.get("current_title", "")),
        "academic_title": dom_profile.get("academic_title", intl_profile.get("academic_title", "")),
        "department": intl_profile.get("department", dom_profile.get("department", "")),
        "discipline": intl_profile.get("discipline", dom_profile.get("discipline", "")),
        "orcid": intl_profile.get("orcid", dom_profile.get("orcid", "")),
        "education_background": intl_profile.get("education_background", dom_profile.get("education_background", "")),
        "career_timeline": _merge_timelines(
            dom_profile.get("career_timeline", []),
            intl_profile.get("career_timeline", []),
        ),
    }

    # Fill in any missing fields from either source
    for key in set(list(dom_profile.keys()) + list(intl_profile.keys())):
        if key not in merged:
            merged[key] = intl_profile.get(key, dom_profile.get(key, "[TO BE FILLED]"))

    return merged


def _merge_timelines(dom_timeline, intl_timeline) -> list:
    """Merge career timelines and sort chronologically."""
    events = []
    seen = set()

    for src, timeline in [("domestic", dom_timeline), ("international", intl_timeline)]:
        if isinstance(timeline, list):
            for event in timeline:
                if not isinstance(event, dict):
                    continue
                year = event.get("year")
                event_text = event.get("event", "")
                key = f"{year}:{event_text}"
                if key not in seen:
                    seen.add(key)
                    events.append({**event, "source": src})
        elif isinstance(timeline, str) and timeline != "[TO BE FILLED]":
            events.append({"year": None, "event": timeline, "source": src})

    # Sort by year if available
    events.sort(key=lambda e: (e.get("year") or 9999, e.get("event", "")))
    return events


def merge_scholar_data(domestic_path: str | Path, international_path: str | Path) -> dict:
    """
    Merge domestic and international scholar_data.json into cross-border record.

    Returns:
        Unified scholar_data with investigation_type: "cross_border"
    """
    domestic = load_scholar_data(domestic_path)
    international = load_scholar_data(international_path)

    logger.info("Merging: domestic=%s, international=%s", domestic_path, international_path)

    # Deduplicate papers
    dom_papers = domestic.get("academic_outputs", {}).get("paper_list", [])
    intl_papers = international.get("academic_outputs", {}).get("paper_list", [])
    merged_papers, duplicates = deduplicate_papers(dom_papers, intl_papers)

    # Detect conflicts
    conflicts = detect_conflicts(domestic, international)
    dom_profile = domestic.get("basic_profile", {})

    # Merge profiles
    merged_profile = merge_profiles(domestic, international)

    # Merge academic outputs
    dom_outputs = domestic.get("academic_outputs", {})
    intl_outputs = international.get("academic_outputs", {})

    dom_verified = dom_outputs.get("verified_papers", 0)
    intl_verified = intl_outputs.get("verified_papers", 0)
    total_verified = 0
    if isinstance(dom_verified, int):
        total_verified += dom_verified
    if isinstance(intl_verified, int):
        total_verified += intl_verified
    total_verified -= len(duplicates)  # Subtract duplicates

    merged_outputs = {
        "claimed_papers": max(
            dom_outputs.get("claimed_papers", 0) if isinstance(dom_outputs.get("claimed_papers"), int) else 0,
            intl_outputs.get("claimed_papers", 0) if isinstance(intl_outputs.get("claimed_papers"), int) else 0,
        ),
        "verified_papers": total_verified,
        "claimed_monographs": dom_outputs.get("claimed_monographs", 0),
        "verified_monographs": dom_outputs.get("verified_monographs", 0),
        "source_databases": list(set(
            (dom_outputs.get("source_databases", []) if isinstance(dom_outputs.get("source_databases"), list) else [])
            + (intl_outputs.get("source_databases", []) if isinstance(intl_outputs.get("source_databases"), list) else [])
        )),
        "recent_3yr_papers": max(
            dom_outputs.get("recent_3yr_papers", 0) if isinstance(dom_outputs.get("recent_3yr_papers"), int) else 0,
            intl_outputs.get("recent_3yr_papers", 0) if isinstance(intl_outputs.get("recent_3yr_papers"), int) else 0,
        ),
        "paper_list": merged_papers,
    }

    # Merge anomalies
    dom_anomalies = domestic.get("anomalies", [])
    intl_anomalies = international.get("anomalies", [])
    merged_anomalies = list(dom_anomalies) + list(intl_anomalies)
    # Add cross-border specific anomalies
    for conflict in conflicts:
        merged_anomalies.append({
            "description": conflict["description"],
            "severity": conflict["severity"],
            "confidence_level": "L3",
            "evidence_sources": ["cross_border_conflict_detection"],
            "cross_border_type": conflict["type"],
        })

    # Build result
    result = {
        "name": merged_profile.get("name", ""),
        "institution": merged_profile.get("institution", ""),
        "investigation_date": datetime.now().strftime("%Y-%m-%d"),
        "investigation_type": "cross_border",
        "basic_profile": merged_profile,
        "academic_outputs": merged_outputs,
        "quality_assessment": international.get("quality_assessment", domestic.get("quality_assessment", {})),
        "relationship_network": {
            "advisors": _merge_lists(
                domestic.get("relationship_network", {}).get("advisors", []),
                international.get("relationship_network", {}).get("advisors", []),
            ),
            "collaborators": _merge_lists(
                domestic.get("relationship_network", {}).get("collaborators", []),
                international.get("relationship_network", {}).get("collaborators", []),
            ),
            "editorial_boards": _merge_lists(
                domestic.get("relationship_network", {}).get("editorial_boards", []),
                international.get("relationship_network", {}).get("editorial_boards", []),
            ),
            "institutional_affiliations": _merge_lists(
                domestic.get("relationship_network", {}).get("institutional_affiliations", []),
                international.get("relationship_network", {}).get("institutional_affiliations", []),
            ),
        },
        "anomalies": merged_anomalies,
        "confidence_ratings": {
            "basic_profile": "medium",
            "output_quantity": "medium",
            "quality_assessment": "low",
            "relationship_network": "medium",
            "anomaly_detection": "medium",
            "student_reviews": "medium",
        },
        "student_reviews": {
            "status": "loaded",
            "domestic": domestic.get("student_reviews", {}),
            "xiaohongshu": international.get("student_reviews", {}).get("xiaohongshu", {}),
        },
        "cross_border_info": {
            "domestic_counterpart": {
                "name_cn": domestic.get("name", ""),
                "institution_cn": dom_profile.get("institution", ""),
                "title_cn": dom_profile.get("current_title", ""),
            },
            "conflicts": conflicts,
            "duplicates": len(duplicates),
            "timeline_consistency": len(conflicts) == 0,
        },
        "metadata": {
            "merged_at": datetime.now().isoformat(),
            "sources": ["domestic", "international"],
            "total_papers_domestic": len(dom_papers),
            "total_papers_international": len(intl_papers),
            "merged_papers": len(merged_papers),
            "duplicate_count": len(duplicates),
            "conflict_count": len(conflicts),
        },
    }

    return result


def _merge_lists(list1: list, list2: list) -> list:
    """Merge two lists of dicts, deduplicating by name."""
    merged = []
    seen = set()
    for item in list1 + list2:
        if not isinstance(item, dict):
            continue
        name = item.get("name", item.get("journal", item.get("institution", str(item))))
        if name and name not in seen:
            seen.add(name)
            merged.append(item)
    return merged


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Merge domestic + international scholar_data")
    parser.add_argument("--domestic", "-d", required=True, help="Path to domestic scholar_data.json")
    parser.add_argument("--international", "-i", required=True, help="Path to international scholar_data.json")
    parser.add_argument("--output", "-o", required=True, help="Output merged JSON path")
    args = parser.parse_args()

    result = merge_scholar_data(args.domestic, args.international)

    save_json(result, Path(args.output))
    logger.info("Cross-border merge saved to: %s", args.output)

    meta = result.get("metadata", {})
    print(f"[OK] Cross-border merge complete")
    print(f"     Domestic papers: {meta.get('total_papers_domestic', 0)}")
    print(f"     International papers: {meta.get('total_papers_international', 0)}")
    print(f"     Merged (deduplicated): {meta.get('merged_papers', 0)}")
    print(f"     Duplicates found: {meta.get('duplicate_count', 0)}")
    print(f"     Conflicts detected: {meta.get('conflict_count', 0)}")
    print(f"     Saved to: {args.output}")


if __name__ == "__main__":
    main()
