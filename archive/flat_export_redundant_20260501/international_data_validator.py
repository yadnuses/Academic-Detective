#!/usr/bin/env python3
"""
international/data_validator.py

Validation rules specific to international scholar investigations.
Extends domestic validation with international-specific fields.

Usage:
    python international/data_validator.py --input ./scholar_data.json
"""

import argparse
import json
from pathlib import Path
from datetime import datetime

from core_utils import get_logger

logger = get_logger("intl_data_validator")


# Required top-level fields for international scholars
REQUIRED_FIELDS = [
    "name",
    "institution",
    "investigation_date",
    "investigation_type",
    "basic_profile",
    "academic_outputs",
    "quality_assessment",
    "relationship_network",
    "anomalies",
    "confidence_ratings",
    "student_reviews",
]

# International-specific required profile fields
REQUIRED_PROFILE_FIELDS = [
    "name",
    "institution",
    "current_title",
    "education_background",
    "career_timeline",
]


def validate(data: dict, fix: bool = False) -> tuple[list, list]:
    """
    Validate international scholar_data.json.

    Returns: (errors, warnings)
    """
    errors = []
    warnings_list = []

    # 1. Top-level fields
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"[MISSING] Required field '{field}' is missing")

    # 2. Type checks
    if "anomalies" in data and not isinstance(data["anomalies"], list):
        errors.append("[TYPE] 'anomalies' must be a list")

    if "confidence_ratings" in data and not isinstance(data["confidence_ratings"], dict):
        errors.append("[TYPE] 'confidence_ratings' must be a dict")

    # 3. Investigation type
    if data.get("investigation_type") != "international":
        warnings_list.append(f"[TYPE] investigation_type is '{data.get('investigation_type')}', expected 'international'")

    # 4. Profile fields
    profile = data.get("basic_profile", {})
    for field in REQUIRED_PROFILE_FIELDS:
        if field not in profile:
            errors.append(f"[MISSING] basic_profile.{field} is required")

    # 5. International-specific validations
    # ORCID presence
    orcid = profile.get("orcid", "")
    if not orcid:
        warnings_list.append("[DATA] ORCID not provided - identity verification will be limited")

    # Papers
    outputs = data.get("academic_outputs", {})
    verified = outputs.get("verified_papers", 0)
    claimed = outputs.get("claimed_papers", 0)

    if isinstance(claimed, (int, float)) and isinstance(verified, (int, float)):
        if verified > claimed:
            warnings_list.append(f"[LOGIC] verified_papers ({verified}) > claimed_papers ({claimed})")
        if claimed > 0:
            discrepancy = (claimed - verified) / claimed
            if discrepancy > 0.2:
                warnings_list.append(f"[RED FLAG] Paper discrepancy: {discrepancy*100:.0f}% difference between claimed ({claimed}) and verified ({verified})")

    # Recent activity
    recent = outputs.get("recent_3yr_papers", 0)
    if isinstance(recent, int):
        if recent == 0:
            warnings_list.append("[YELLOW FLAG] No papers in last 3 years - research stagnation?")
        elif recent < 3:
            warnings_list.append(f"[WARNING] Only {recent} papers in last 3 years")

    # Quality assessment
    qa = data.get("quality_assessment", {})
    if qa.get("metrics_summary"):
        metrics = qa["metrics_summary"]
        h_index = metrics.get("h_index", 0)
        if h_index == 0:
            warnings_list.append("[DATA] h-index is 0 - may indicate early career or data gap")

    # Student reviews
    reviews = data.get("student_reviews", {})
    xhs = reviews.get("xiaohongshu", {})
    if xhs.get("matched") and xhs.get("red_flags"):
        red_flags = xhs["red_flags"]
        if len(red_flags) >= 3:
            warnings_list.append(f"[RED FLAG] {len(red_flags)} red flags from Xiaohongshu reviews")

    # Auto-fix
    if fix:
        data = auto_fix(data)

    return errors, warnings_list


def auto_fix(data: dict) -> dict:
    """Auto-populate missing fields with defaults."""
    # Ensure top-level fields with correct types
    defaults = {
        "anomalies": [],
        "confidence_ratings": {},
        "relationship_network": {},
        "student_reviews": {},
        "basic_profile": {},
        "academic_outputs": {},
        "quality_assessment": {},
        "investigation_type": "international",
        "investigation_date": "",
        "name": "[TO BE FILLED]",
        "institution": "[TO BE FILLED]",
    }
    for field in REQUIRED_FIELDS:
        if field not in data:
            data[field] = defaults.get(field, "[TO BE FILLED]")

    # Ensure profile fields
    profile = data.setdefault("basic_profile", {})
    if not isinstance(profile, dict):
        data["basic_profile"] = profile = {}
    for field in REQUIRED_PROFILE_FIELDS:
        if field not in profile:
            profile[field] = "[TO BE FILLED]"

    # Ensure investigation_date
    if not data.get("investigation_date"):
        data["investigation_date"] = datetime.now().strftime("%Y-%m-%d")

    # Ensure investigation_type
    if not data.get("investigation_type"):
        data["investigation_type"] = "international"

    return data


def is_corruption_network(data: dict) -> bool:
    return isinstance(data, dict) and "network_name" in data and "nodes" in data


def main():
    parser = argparse.ArgumentParser(description="Validate international scholar_data.json")
    parser.add_argument("--input", "-i", required=True, help="Path to scholar_data.json")
    parser.add_argument("--fix", action="store_true", help="Auto-fix missing fields")
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        logger.error("File not found: %s", path)
        return

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    errors, warnings = validate(data, fix=args.fix)

    if warnings:
        for w in warnings:
            print(f"[WARNING] {w}")

    if errors:
        for e in errors:
            print(f"[ERROR] {e}")
        print(f"\nValidation FAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
    else:
        print(f"Validation PASSED: 0 error(s), {len(warnings)} warning(s)")

    if args.fix:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[FIXED] Auto-filled defaults saved to {path}")


if __name__ == "__main__":
    main()
