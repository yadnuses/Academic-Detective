#!/usr/bin/env python3
"""
data_validator.py

Validates the structured JSON produced by manual research + LLM analysis.
Supports both single-scholar data (scholar_data.json) and corruption networks
(corruption_network.json).

Usage:
    python data_validator.py --input ./scholar_data.json
    python data_validator.py --input ./corruption_network.json --fix
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# Scholar data constants
# ---------------------------------------------------------------------------
REQUIRED_TOP_LEVEL = {
    "name": str,
    "institution": str,
    "investigation_date": str,
    "basic_profile": dict,
    "academic_outputs": dict,
    "quality_assessment": dict,
    "relationship_network": dict,
    "anomalies": list,
    "confidence_ratings": dict,
    "student_reviews": dict,
}

REQUIRED_PROFILE_FIELDS = ["name", "institution", "current_title", "education_background", "career_timeline"]
REQUIRED_OUTPUT_FIELDS = ["claimed_papers", "verified_papers", "claimed_monographs", "verified_monographs", "source_databases", "recent_3yr_papers"]


# ---------------------------------------------------------------------------
# Corruption network constants
# ---------------------------------------------------------------------------
VALID_NODE_TYPES = {
    "core_subject", "protector", "accomplice", "external",
    "academic", "institution", "family", "victim", "official"
}
VALID_LINK_TYPES = {
    "shelter", "academic", "academic_packaging", "money_laundering", "project_collab",
    "clinical", "accomplice", "victimization", "family",
    "formal_punishment", "affiliated_with"
}
VALID_CASE_TYPES = {
    "criminal_case", "disciplinary_case", "death_event",
    "academic_misconduct", "other"
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def validate_type(value, expected_type, path: str) -> list:
    errors = []
    if expected_type == list and not isinstance(value, list):
        errors.append(f"[TYPE] {path}: expected list, got {type(value).__name__}")
    elif expected_type == dict and not isinstance(value, dict):
        errors.append(f"[TYPE] {path}: expected dict, got {type(value).__name__}")
    elif expected_type == str and not isinstance(value, str):
        errors.append(f"[TYPE] {path}: expected str, got {type(value).__name__}")
    elif expected_type == int and not isinstance(value, int):
        errors.append(f"[TYPE] {path}: expected int, got {type(value).__name__}")
    return errors


def is_corruption_network(data: dict) -> bool:
    return isinstance(data, dict) and "network_name" in data and "nodes" in data and "links" in data


def _parse_fuzzy_date(date_str: str) -> bool:
    s = str(date_str).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            datetime.strptime(s, fmt)
            return True
        except ValueError:
            continue
    return False


# ---------------------------------------------------------------------------
# Scholar data validation
# ---------------------------------------------------------------------------

def validate_scholar_data(data: dict, fix: bool = False) -> tuple:
    errors = []
    warnings = []

    # Top-level presence
    for field, expected_type in REQUIRED_TOP_LEVEL.items():
        if field not in data:
            errors.append(f"[MISSING] Required top-level field missing: '{field}'")
        else:
            errors.extend(validate_type(data[field], expected_type, field))

    if errors and not fix:
        return errors, warnings

    # Basic profile
    profile = data.get("basic_profile", {})
    for field in REQUIRED_PROFILE_FIELDS:
        if field not in profile:
            errors.append(f"[MISSING] basic_profile missing field: '{field}'")

    # Academic outputs
    outputs = data.get("academic_outputs", {})
    for field in REQUIRED_OUTPUT_FIELDS:
        if field not in outputs:
            errors.append(f"[MISSING] academic_outputs missing field: '{field}'")

    # Verify numeric consistency if both present
    claimed = outputs.get("claimed_papers")
    verified = outputs.get("verified_papers")
    if isinstance(claimed, int) and isinstance(verified, int):
        if verified > claimed:
            warnings.append(f"[LOGIC] Verified papers ({verified}) > claimed papers ({claimed}). Double-check.")
        elif claimed > 0:
            discrepancy = (claimed - verified) / claimed
            if discrepancy > 0.20:
                warnings.append(f"[RED FLAG] Paper discrepancy {discrepancy:.1%} exceeds 20% threshold.")

    # Recent 3-year activity check
    recent_3yr = outputs.get("recent_3yr_papers")
    if isinstance(recent_3yr, int):
        if recent_3yr == 0:
            warnings.append("[RED FLAG] Zero peer-reviewed papers in the last 3 years suggests research stagnation or heavy administrative load.")
        elif recent_3yr < 3:
            warnings.append("[WARNING] Fewer than 3 papers in the last 3 years (average < 1/year). Verify current research activity.")

    # Funding verification check
    funding = data.get("funding_verification", {})
    nsfc_active = funding.get("nsfc_active_projects")
    if nsfc_active is not None and isinstance(nsfc_active, int) and nsfc_active == 0:
        warnings.append("[YELLOW FLAG] No active NSFC projects found in the last 3 years. STEM labs may face equipment/stipend constraints.")

    # Anomalies
    anomalies = data.get("anomalies", [])
    for i, item in enumerate(anomalies):
        if not isinstance(item, dict):
            errors.append(f"[TYPE] anomalies[{i}] should be a dict")
            continue
        if "description" not in item:
            errors.append(f"[MISSING] anomalies[{i}] missing 'description'")
        if "severity" not in item:
            warnings.append(f"[WARNING] anomalies[{i}] missing 'severity' (suggest: low/medium/high)")
        if "evidence_sources" not in item or len(item.get("evidence_sources", [])) < 2:
            warnings.append(f"[WARNING] anomalies[{i}] has fewer than 2 evidence sources. Multi-source validation recommended.")

    # Confidence ratings
    ratings = data.get("confidence_ratings", {})
    valid_levels = {"low", "medium", "high", "very_high"}
    for key, val in ratings.items():
        if val not in valid_levels and val not in {"⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"}:
            warnings.append(f"[FORMAT] confidence_ratings['{key}'] uses non-standard value: '{val}'. Suggest: low/medium/high/very_high.")

    # Student reviews
    reviews = data.get("student_reviews", {})
    if reviews.get("matched"):
        leads = reviews.get("investigation_leads", [])
        high_severity_leads = [l for l in leads if l.get("severity") in ("high", "critical")]
        critical_leads = [l for l in leads if l.get("severity") == "critical"]
        if critical_leads:
            warnings.append(f"[CRITICAL] {len(critical_leads)} critical-severity lead(s) from student reviews: {[l.get('label') for l in critical_leads]}. Immediate cross-checking required.")
        if len(high_severity_leads) >= 2:
            warnings.append(f"[RED FLAG] {len(high_severity_leads)} high/critical-severity leads from structured student reviews. Prioritize cross-checking.")
        elif high_severity_leads:
            warnings.append(f"[WARNING] {len(high_severity_leads)} high-severity lead from student reviews. Requires verification.")
        if not leads:
            warnings.append("[INFO] Student reviews matched but generated zero investigation leads. Consider manual reading of raw reviews.")

        valid_confidence_levels = {"L5", "L4", "L3", "L2", "L1"}
        valid_severities = {"critical", "high", "medium", "low"}
        for i, lead in enumerate(leads):
            conf = lead.get("confidence_level", "")
            if conf and conf not in valid_confidence_levels:
                warnings.append(f"[FORMAT] investigation_leads[{i}] has non-standard confidence_level: '{conf}'. Expected: L1-L5.")
            sev = lead.get("severity", "")
            if sev and sev not in valid_severities:
                warnings.append(f"[FORMAT] investigation_leads[{i}] has non-standard severity: '{sev}'. Expected: critical/high/medium/low.")
            if sev in ("high", "critical") and not lead.get("evidence_quotes"):
                warnings.append(f"[QUALITY] investigation_leads[{i}] ({lead.get('label')}) is high/critical but lacks evidence_quotes.")

        risk = reviews.get("overall_risk_assessment", {})
        if risk:
            risk_level = risk.get("level", "")
            if risk_level not in {"critical", "high", "medium", "low", "unknown", ""}:
                warnings.append(f"[FORMAT] overall_risk_assessment.level is non-standard: '{risk_level}'.")
            if risk_level in ("critical", "high") and not critical_leads and not high_severity_leads:
                warnings.append(f"[LOGIC] overall_risk_assessment.level is '{risk_level}' but no high/critical leads found. Inconsistent.")

        dim_summary = reviews.get("dimension_summary", {})
        radar_data = reviews.get("radar_data", [])
        radar_dims = {d.get("dimension") for d in radar_data}
        summary_dims = set(dim_summary.keys())
        missing_from_radar = summary_dims - radar_dims
        if missing_from_radar:
            warnings.append(f"[STRUCTURE] Dimensions in dimension_summary but not in radar_data: {missing_from_radar}")
        missing_from_summary = radar_dims - summary_dims
        if missing_from_summary:
            warnings.append(f"[STRUCTURE] Dimensions in radar_data but not in dimension_summary: {missing_from_summary}")

    # Investigation date format check
    inv_date = data.get("investigation_date", "")
    try:
        datetime.strptime(inv_date, "%Y-%m-%d")
    except ValueError:
        warnings.append(f"[FORMAT] investigation_date '{inv_date}' not in YYYY-MM-DD format.")

    # Version tracking check
    version = data.get("_version")
    if not version:
        warnings.append("[INFO] _version field missing. Run scholar_data_builder.py with the latest version to enable round tracking.")
    elif not isinstance(version, dict):
        errors.append("[TYPE] _version should be a dict")
    else:
        coll_round = version.get("data_collection_round")
        if coll_round is None:
            warnings.append("[INFO] _version.data_collection_round missing. Version tracking incomplete.")
        elif not isinstance(coll_round, int) or coll_round < 0:
            errors.append(f"[VALUE] _version.data_collection_round should be a non-negative int, got: {coll_round}")
        if not version.get("builder_build_timestamp"):
            warnings.append("[INFO] _version.builder_build_timestamp missing. Version tracking incomplete.")
        if not version.get("serial"):
            warnings.append("[INFO] _version.serial missing. Version tracking incomplete.")

    # Peer cohort check
    peer_cohort = data.get("peer_cohort", [])
    if not isinstance(peer_cohort, list):
        errors.append("[TYPE] peer_cohort should be a list")
    elif peer_cohort:
        for i, peer in enumerate(peer_cohort):
            if not isinstance(peer, dict):
                errors.append(f"[TYPE] peer_cohort[{i}] should be a dict")
                continue
            if not peer.get("name"):
                warnings.append(f"[INFO] peer_cohort[{i}] missing 'name'")

    return errors, warnings


def auto_fix_scholar_data(data: dict) -> dict:
    for field, expected_type in REQUIRED_TOP_LEVEL.items():
        if field not in data:
            if expected_type == list:
                data[field] = []
            elif expected_type == dict:
                data[field] = {}
            else:
                data[field] = ""

    for key in ["basic_profile", "academic_outputs", "quality_assessment", "relationship_network", "confidence_ratings", "student_reviews"]:
        if not isinstance(data.get(key), dict):
            data[key] = {}

    if not isinstance(data.get("anomalies"), list):
        data["anomalies"] = []

    for field in REQUIRED_PROFILE_FIELDS:
        if field not in data["basic_profile"]:
            data["basic_profile"][field] = "[TO BE FILLED]"

    for field in REQUIRED_OUTPUT_FIELDS:
        if field not in data["academic_outputs"]:
            data["academic_outputs"][field] = "[TO BE FILLED]"

    if not isinstance(data.get("funding_verification"), dict):
        data["funding_verification"] = {}

    if not isinstance(data.get("student_reviews"), dict):
        data["student_reviews"] = {}

    if not data.get("investigation_date"):
        data["investigation_date"] = datetime.now().strftime("%Y-%m-%d")

    return data


# ---------------------------------------------------------------------------
# Corruption network validation
# ---------------------------------------------------------------------------

def validate_corruption_network(data: dict, fix: bool = False) -> tuple:
    errors = []
    warnings = []

    # Required top-level fields
    for field in ("network_name", "nodes", "links"):
        if field not in data:
            errors.append(f"[MISSING] Required top-level field missing: '{field}'")

    nodes = data.get("nodes", []) if isinstance(data.get("nodes"), list) else []
    links = data.get("links", []) if isinstance(data.get("links"), list) else []
    cases = data.get("cases", []) if isinstance(data.get("cases"), list) else []
    timelines = data.get("timelines", []) if isinstance(data.get("timelines"), list) else []
    grants = data.get("grants", []) if isinstance(data.get("grants"), list) else []
    negative_space = data.get("negative_space", {}) if isinstance(data.get("negative_space"), dict) else {}

    node_ids = set()
    node_id_positions = {}
    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"[TYPE] nodes[{i}] should be a dict")
            continue
        nid = node.get("id")
        if not nid:
            errors.append(f"[MISSING] nodes[{i}] missing 'id'")
            continue
        if nid in node_ids:
            errors.append(f"[DUPLICATE] Duplicate node id: '{nid}'")
        node_ids.add(nid)
        node_id_positions[nid] = i
        if not node.get("name"):
            errors.append(f"[MISSING] nodes[{i}] ('{nid}') missing 'name'")
        ntype = node.get("type")
        if not ntype:
            errors.append(f"[MISSING] nodes[{i}] ('{nid}') missing 'type'")
        elif ntype not in VALID_NODE_TYPES:
            errors.append(f"[VALUE] nodes[{i}] ('{nid}') has invalid type: '{ntype}'. Valid: {', '.join(sorted(VALID_NODE_TYPES))}")
        if not node.get("institution"):
            warnings.append(f"[INFO] nodes[{i}] ('{nid}') missing 'institution'")
        if not node.get("detail"):
            warnings.append(f"[INFO] nodes[{i}] ('{nid}') missing 'detail'")

    # Links validation
    linked_node_ids = set()
    for i, link in enumerate(links):
        if not isinstance(link, dict):
            errors.append(f"[TYPE] links[{i}] should be a dict")
            continue
        src = link.get("source")
        tgt = link.get("target")
        ltype = link.get("type")
        if not src:
            errors.append(f"[MISSING] links[{i}] missing 'source'")
        if not tgt:
            errors.append(f"[MISSING] links[{i}] missing 'target'")
        if src and src not in node_ids:
            errors.append(f"[REFERENCE] links[{i}] source '{src}' does not match any node id")
        if tgt and tgt not in node_ids:
            errors.append(f"[REFERENCE] links[{i}] target '{tgt}' does not match any node id")
        if ltype not in VALID_LINK_TYPES:
            errors.append(f"[VALUE] links[{i}] has invalid type: '{ltype}'. Valid: {', '.join(sorted(VALID_LINK_TYPES))}")
        if src and tgt:
            linked_node_ids.add(src)
            linked_node_ids.add(tgt)
        if not link.get("detail"):
            warnings.append(f"[INFO] links[{i}] ({src} -> {tgt}) missing 'detail'")
        weight = link.get("weight")
        if weight is not None and (not isinstance(weight, (int, float)) or weight < 0):
            warnings.append(f"[VALUE] links[{i}] weight should be a non-negative number")

    # Orphan nodes
    orphan_nodes = node_ids - linked_node_ids
    if orphan_nodes:
        # institution nodes often legitimately have only affiliated_with links,
        # but if they have zero links of any kind, that's suspicious.
        # linked_node_ids already captures all sources and targets.
        for nid in orphan_nodes:
            warnings.append(f"[STRUCTURE] Node '{nid}' has no incident links (orphan node)")

    # Cases validation
    case_ids = set()
    for i, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"[TYPE] cases[{i}] should be a dict")
            continue
        cid = case.get("id")
        if not cid:
            errors.append(f"[MISSING] cases[{i}] missing 'id'")
        else:
            if cid in case_ids:
                errors.append(f"[DUPLICATE] Duplicate case id: '{cid}'")
            case_ids.add(cid)
        if not case.get("name"):
            errors.append(f"[MISSING] cases[{i}] missing 'name'")
        ctype = case.get("type")
        if ctype and ctype not in VALID_CASE_TYPES:
            errors.append(f"[VALUE] cases[{i}] has invalid type: '{ctype}'. Valid: {', '.join(sorted(VALID_CASE_TYPES))}")
        if case.get("date") and not _parse_fuzzy_date(case.get("date")):
            warnings.append(f"[FORMAT] cases[{i}] date '{case.get('date')}' not in YYYY-MM-DD, YYYY-MM, or YYYY format")
        if ctype == "death_event" and not case.get("date"):
            warnings.append(f"[DATA] cases[{i}] is a death_event but lacks a date")
        primary = case.get("primary_node_id")
        if primary and primary not in node_ids:
            errors.append(f"[REFERENCE] cases[{i}] primary_node_id '{primary}' does not match any node id")

    # Timelines validation
    for ti, tl in enumerate(timelines):
        if not isinstance(tl, dict):
            errors.append(f"[TYPE] timelines[{ti}] should be a dict")
            continue
        if "id" not in tl:
            errors.append(f"[MISSING] timelines[{ti}] missing 'id'")
        events = tl.get("events", [])
        if not isinstance(events, list):
            errors.append(f"[TYPE] timelines[{ti}].events should be a list")
            continue
        for ei, ev in enumerate(events):
            prefix = f"timelines[{ti}].events[{ei}]"
            if not isinstance(ev, dict):
                errors.append(f"[TYPE] {prefix} should be a dict")
                continue
            if "date" not in ev:
                errors.append(f"[MISSING] {prefix} missing 'date'")
            elif not _parse_fuzzy_date(ev.get("date", "")):
                warnings.append(f"[FORMAT] {prefix} date '{ev.get('date')}' not in YYYY-MM-DD, YYYY-MM, or YYYY format")
            if "event" not in ev:
                errors.append(f"[MISSING] {prefix} missing 'event'")
            for nid in ev.get("node_ids", []):
                if nid not in node_ids:
                    errors.append(f"[REFERENCE] {prefix} node_ids contains unknown node '{nid}'")

    # Grants validation
    for i, g in enumerate(grants):
        prefix = f"grants[{i}]"
        if not isinstance(g, dict):
            errors.append(f"[TYPE] {prefix} should be a dict")
            continue
        if not g.get("grant_id"):
            warnings.append(f"[INFO] {prefix} missing 'grant_id'")
        if not g.get("name"):
            warnings.append(f"[INFO] {prefix} missing 'name'")

    # Negative space validation
    if negative_space:
        evasion = negative_space.get("evasion_score")
        if evasion is not None and (not isinstance(evasion, (int, float)) or evasion < 0 or evasion > 1):
            errors.append(f"[VALUE] negative_space.evasion_score ({evasion}) must be between 0.0 and 1.0")
        matrix = negative_space.get("matrix", [])
        if isinstance(matrix, list):
            for i, row in enumerate(matrix):
                if not isinstance(row, dict):
                    errors.append(f"[TYPE] negative_space.matrix[{i}] should be a dict")
                    continue
                if "question" not in row:
                    errors.append(f"[MISSING] negative_space.matrix[{i}] missing 'question'")
                if "score" in row and (not isinstance(row["score"], (int, float)) or row["score"] < 0 or row["score"] > 1):
                    errors.append(f"[VALUE] negative_space.matrix[{i}] score must be between 0.0 and 1.0")

    # Count consistency
    declared_node_count = data.get("node_count")
    declared_link_count = data.get("link_count")
    if declared_node_count is not None and declared_node_count != len(nodes):
        warnings.append(f"[MISMATCH] node_count ({declared_node_count}) != actual nodes ({len(nodes)})")
    if declared_link_count is not None and declared_link_count != len(links):
        warnings.append(f"[MISMATCH] link_count ({declared_link_count}) != actual links ({len(links)})")

    return errors, warnings


def auto_fix_corruption_network(data: dict) -> dict:
    if "network_name" not in data:
        data["network_name"] = "未命名调查网络"
    if not isinstance(data.get("nodes"), list):
        data["nodes"] = []
    if not isinstance(data.get("links"), list):
        data["links"] = []
    if not isinstance(data.get("cases"), list):
        data["cases"] = []
    if not isinstance(data.get("timelines"), list):
        data["timelines"] = []
    if not isinstance(data.get("grants"), list):
        data["grants"] = []
    if not isinstance(data.get("negative_space"), dict):
        data["negative_space"] = {}
    data["node_count"] = len(data.get("nodes", []))
    data["link_count"] = len(data.get("links", []))
    return data


# ---------------------------------------------------------------------------
# Unified interface
# ---------------------------------------------------------------------------

def validate(data: dict, fix: bool = False) -> tuple:
    if is_corruption_network(data):
        return validate_corruption_network(data, fix=fix)
    return validate_scholar_data(data, fix=fix)


def auto_fix(data: dict) -> dict:
    if is_corruption_network(data):
        return auto_fix_corruption_network(data)
    return auto_fix_scholar_data(data)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Validate scholar investigation or corruption network JSON data")
    parser.add_argument("--input", "-i", required=True, help="Path to JSON file")
    parser.add_argument("--fix", action="store_true", help="Auto-fix missing fields and overwrite file")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    mode = "corruption_network" if is_corruption_network(data) else "scholar_data"
    print(f"[INFO] Detected data mode: {mode}")

    if args.fix:
        data = auto_fix(data)
        with open(args.input, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[INFO] Auto-fixed and saved: {args.input}")

    errors, warnings = validate(data, fix=args.fix)

    if warnings:
        print("\n[WARNINGS]")
        for w in warnings:
            print(f"  - {w}")

    if errors:
        print("\n[ERRORS]")
        for e in errors:
            print(f"  - {e}")
        print(f"\nValidation failed: {len(errors)} error(s), {len(warnings)} warning(s).")
        sys.exit(1)
    else:
        print(f"\nValidation passed: 0 error(s), {len(warnings)} warning(s).")


if __name__ == "__main__":
    main()
