#!/usr/bin/env python3
"""
international/scholar_data_builder.py

Builds international scholar_data.json from auto-fetched API data.
Compatible with the unified scholar_data.schema.json.

Usage:
    python international/scholar_data_builder.py --config ./config.yaml --auto-data ./data/auto_fetched.json --output ./scholar_data.json
"""

import argparse
import json
from pathlib import Path
from datetime import datetime

from core_utils import get_logger, load_json, save_json, load_config as utils_load_config

logger = get_logger("intl_scholar_builder")


def build_international_scholar_data(config: dict, auto_data: dict, xiaohongshu_data: dict = None) -> dict:
    """
    Build scholar_data.json from automatically fetched international data.

    Args:
        config: Loaded config.yaml
        auto_data: Output from data_fetcher.fetch_all()
        xiaohongshu_data: Optional output from xiaohongshu_client

    Returns:
        dict conforming to scholar_data.schema.json
    """
    scholar = config.get("scholar", {})
    name = scholar.get("name", "")
    institution = scholar.get("institution", "")

    # Extract author profile from best available source
    profile = auto_data.get("author_profile", {})
    oa_profile = profile.get("openalex", {})
    s2_profile = profile.get("semantic_scholar", {})
    gs_profile = profile.get("google_scholar", {})

    # Build basic profile
    basic_profile = {
        "name": name,
        "institution": institution,
        "institution_en": scholar.get("institution_en", ""),
        "current_title": scholar.get("current_title", ""),
        "academic_title": scholar.get("academic_title", ""),
        "department": scholar.get("department", ""),
        "discipline": scholar.get("discipline", ""),
        "education_background": "[TO BE FILLED - manual ORCID verification recommended]",
        "career_timeline": "[TO BE FILLED - manual institution verification recommended]",
        "tenure_status": "[TO BE FILLED]",
        "orcid": oa_profile.get("orcid", ""),
    }

    # Build papers list
    papers = auto_data.get("papers", [])
    verified_count = len(papers)

    # Build academic outputs
    academic_outputs = {
        "claimed_papers": scholar.get("claims", {}).get("papers", {}).get("total", "[TO BE FILLED]"),
        "verified_papers": verified_count,
        "claimed_monographs": 0,
        "verified_monographs": 0,
        "source_databases": list(auto_data.get("source_metadata", {}).keys()),
        "recent_3yr_papers": len([p for p in papers if p.get("year") and p["year"] >= datetime.now().year - 3]),
        "paper_list": papers,
    }

    # Build metrics
    metrics = auto_data.get("metrics", {})
    quality_assessment = {
        "originality_score": "[TO BE FILLED - requires LLM assessment]",
        "theoretical_depth": "[TO BE FILLED]",
        "journal_quality": "[TO BE FILLED]",
        "metrics_summary": metrics,
    }

    # Build relationship network
    relationships = {
        "advisors": [],
        "collaborators": [],
        "editorial_boards": [],
        "institutional_affiliations": [],
    }

    # Extract collaborators from OpenAlex works
    oa_data = auto_data.get("source_metadata", {}).get("openalex", {})
    collaborator_counts = {}
    for work in oa_data.get("works", []):
        for auth in work.get("authorships", []):
            auth_name = auth.get("author_name", "")
            if auth_name and auth_name != name:
                collaborator_counts[auth_name] = collaborator_counts.get(auth_name, 0) + 1

    top_collaborators = sorted(collaborator_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    relationships["collaborators"] = [
        {"name": name, "co_paper_count": count, "institution": ""}
        for name, count in top_collaborators
    ]

    # Anomalies (placeholder - will be filled by heuristics_classifier)
    anomalies = []

    # Student reviews
    student_reviews = {
        "status": "loaded" if xiaohongshu_data else "no_report_found",
        "xiaohongshu": xiaohongshu_data or {},
    }

    # Confidence ratings
    confidence_ratings = {
        "basic_profile": "medium",
        "output_quantity": "high" if verified_count > 0 else "low",
        "quality_assessment": "low",
        "relationship_network": "medium",
        "anomaly_detection": "low",
        "student_reviews": "medium" if xiaohongshu_data else "low",
    }

    return {
        "name": name,
        "institution": institution,
        "investigation_date": datetime.now().strftime("%Y-%m-%d"),
        "investigation_type": "international",
        "basic_profile": basic_profile,
        "academic_outputs": academic_outputs,
        "quality_assessment": quality_assessment,
        "relationship_network": relationships,
        "anomalies": anomalies,
        "confidence_ratings": confidence_ratings,
        "student_reviews": student_reviews,
        "metadata": {
            "auto_fetched_at": datetime.now().isoformat(),
            "sources_used": list(auto_data.get("source_metadata", {}).keys()),
            "total_api_calls": len(auto_data.get("source_metadata", {})),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Build international scholar_data.json")
    parser.add_argument("--config", "-c", required=True, help="Path to config.yaml")
    parser.add_argument("--auto-data", "-a", required=True, help="Path to auto_fetched.json (from data_fetcher)")
    parser.add_argument("--xiaohongshu", "-x", help="Path to xiaohongshu_reviews.json")
    parser.add_argument("--output", "-o", required=True, help="Output scholar_data.json path")
    parser.add_argument("--fix", action="store_true", help="Auto-fix missing fields with defaults")
    args = parser.parse_args()

    config = utils_load_config(Path(args.config).parent, Path(args.config).name)
    auto_data = load_json(Path(args.auto_data))
    xhs_data = load_json(Path(args.xiaohongshu)) if args.xiaohongshu else None

    scholar_data = build_international_scholar_data(config, auto_data, xhs_data)

    if args.fix:
        # Auto-fill obvious defaults
        if not scholar_data["basic_profile"]["department"]:
            scholar_data["basic_profile"]["department"] = "[TO BE FILLED]"

    save_json(scholar_data, Path(args.output))
    logger.info("International scholar_data.json saved: %s", args.output)
    print(f"[OK] scholar_data.json built: {args.output}")
    print(f"     Papers: {scholar_data['academic_outputs']['verified_papers']}")
    print(f"     Sources: {', '.join(scholar_data['academic_outputs']['source_databases'])}")


if __name__ == "__main__":
    main()
