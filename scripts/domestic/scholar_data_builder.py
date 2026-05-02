#!/usr/bin/env python3
"""
scholar_data_builder.py

Builds a unified scholar_data.json from config.yaml and scattered script outputs.
Eliminates the manual copy-paste bottleneck in the investigation workflow.

Usage:
    python scholar_data_builder.py --config ./config.yaml --data-dir ./data --output ./scholar_data.json
    python scholar_data_builder.py --config ./config.yaml --data-dir ./data --output ./scholar_data.json --fix
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime


def load_yaml(path: str) -> dict:
    """Load config.yaml. Uses PyYAML if available; otherwise uses a minimal safe parser."""
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ImportError:
        pass

    # Minimal YAML parser for the template structure (no nested dicts under lists)
    data = {}
    current_section = None
    current_subsection = None
    list_context = None

    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                continue

            indent = len(line) - len(stripped)

            # Top-level key
            if indent == 0 and stripped.endswith(":"):
                current_section = stripped[:-1]
                data[current_section] = {}
                current_subsection = None
                list_context = None
                continue

            if current_section is None:
                continue

            # Second-level key
            if indent == 2 and stripped.endswith(":"):
                current_subsection = stripped[:-1]
                data[current_section][current_subsection] = {}
                list_context = None
                continue

            # Third-level key (value or nested dict start)
            if indent == 4 and current_subsection is not None:
                if ": " in stripped or stripped.endswith(":" ):
                    if stripped.endswith(":"):
                        key = stripped[:-1]
                        data[current_section][current_subsection][key] = {}
                        list_context = None
                    else:
                        key, val = stripped.split(": ", 1)
                        # Try int/float/null/bool
                        if val == "null" or val == "~":
                            val = None
                        elif val == "true":
                            val = True
                        elif val == "false":
                            val = False
                        elif val.startswith('"') and val.endswith('"'):
                            val = val[1:-1]
                        elif val.startswith("'") and val.endswith("'"):
                            val = val[1:-1]
                        else:
                            try:
                                val = int(val)
                            except ValueError:
                                try:
                                    val = float(val)
                                except ValueError:
                                    pass
                        data[current_section][current_subsection][key] = val
                        list_context = None
                continue

            # List item under third level
            if indent >= 6 and stripped.startswith("-"):
                list_item = stripped.lstrip("- ").strip()
                # Find the deepest dict to append
                target = data[current_section][current_subsection]
                # If current_subsection is a dict with scalar values, list belongs to last key
                if isinstance(target, dict):
                    # Try to find a nested dict that might be list container
                    pass
                continue

    # Fallback: if minimal parser fails structurally, warn user
    if not data:
        print("[WARN] Minimal YAML parser produced empty result. Install PyYAML for full parsing: pip install pyyaml", file=sys.stderr)
    return data


def find_script_outputs(data_dir: Path) -> dict:
    """Auto-discover JSON outputs from other scripts in the data directory."""
    outputs = {
        "text_profiles": [],
        "citation_report": None,
        "style_report": None,
        "review_matched": None,
        "validation_report": None,
        "hybrid_score_report": None,
    }

    if not data_dir.exists():
        return outputs

    # Scan root-level JSON files
    for p in data_dir.iterdir():
        if not p.is_file() or not p.suffix == ".json":
            continue
        name = p.name.lower()
        if name.endswith("_profile.json"):
            outputs["text_profiles"].append(str(p))
        elif name.endswith("citation_report.json") or "citation" in name:
            outputs["citation_report"] = str(p)
        elif name.endswith("style_report.json") or "stylometry" in name or "style" in name:
            outputs["style_report"] = str(p)
        elif name.endswith("reviews_matched.json") or "review" in name:
            outputs["review_matched"] = str(p)
        elif name.endswith("_validated.json") or "validation" in name:
            outputs["validation_report"] = str(p)

    # Scan nested scoring directories (hybrid_scores, quality_scores, etc.)
    for subdir in data_dir.iterdir():
        if not subdir.is_dir():
            continue
        if subdir.name.endswith("_scores") or "hybrid" in subdir.name or "score" in subdir.name or "quality" in subdir.name:
            ranked = subdir / "_final_ranked_report.json"
            if ranked.exists():
                outputs["hybrid_score_report"] = str(ranked)
            # Also pick up profiles stored inside scoring output directories
            for prof in subdir.glob("*_profile.json"):
                outputs["text_profiles"].append(str(prof))

    return outputs


def load_json_if_exists(path: str | None) -> dict | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def build_scholar_data(config: dict, data_dir: Path) -> dict:
    """Assemble the unified JSON."""
    scholar = config.get("scholar", {})
    manual = config.get("manual_sources", {})
    claims = config.get("claims", {})
    investigation = config.get("investigation", {})
    outputs_meta = find_script_outputs(data_dir)

    # Load external JSONs
    text_profiles = [load_json_if_exists(p) for p in outputs_meta["text_profiles"]]
    citation_report = load_json_if_exists(outputs_meta["citation_report"])
    style_report = load_json_if_exists(outputs_meta["style_report"])
    review_report = load_json_if_exists(outputs_meta.get("review_matched"))
    hybrid_report = load_json_if_exists(outputs_meta.get("hybrid_score_report"))

    # Basic structure aligned with data_validator expectations
    data = {
        "name": scholar.get("name", ""),
        "institution": scholar.get("institution", ""),
        "investigation_date": investigation.get("date", datetime.now().strftime("%Y-%m-%d")),

        "basic_profile": {
            "name": scholar.get("name", ""),
            "institution": scholar.get("institution", ""),
            "current_title": scholar.get("current_title", ""),
            "academic_title": scholar.get("academic_title", ""),
            "birth_year": scholar.get("birth_year"),
            "gender": scholar.get("gender", ""),
            "department": scholar.get("department", ""),
            "education_background": "[TO BE FILLED]",
            "career_timeline": "[TO BE FILLED]",
            "overseas_experience": "[TO BE FILLED]",
        },

        "academic_outputs": {
            "claimed_papers": _parse_claim(claims.get("papers", {}).get("total", "0")),
            "verified_papers": "[TO BE FILLED]",
            "claimed_monographs": _parse_claim(claims.get("monographs", {}).get("total", "0")),
            "verified_monographs": "[TO BE FILLED]",
            "source_databases": "[TO BE FILLED]",
            "recent_3yr_papers": _parse_claim(claims.get("papers", {}).get("recent_3yr_total", "0")),
            "paper_list": "[TO BE FILLED]",
            "monograph_list": "[TO BE FILLED]",
        },

        "quality_assessment": {
            "originality_score": "[TO BE FILLED]",
            "theoretical_depth": "[TO BE FILLED]",
            "journal_quality": "[TO BE FILLED]",
            "text_profile_summary": _summarize_text_profiles(text_profiles),
            "style_analysis": _summarize_style_report(style_report),
            "hybrid_score_summary": _summarize_hybrid_report(hybrid_report),
        },

        "relationship_network": {
            "advisor": "[TO BE FILLED]",
            "key_collaborators": "[TO BE FILLED]",
            "editorial_connections": "[TO BE FILLED]",
            "institutional_dependencies": "[TO BE FILLED]",
            "citation_analysis": _summarize_citation_report(citation_report),
        },

        "anomalies": [],

        "confidence_ratings": {
            "basic_profile": "medium",
            "output_quantity": "medium",
            "quality_assessment": "medium",
            "relationship_network": "medium",
            "anomaly_detection": "medium",
        },

        "student_reviews": _summarize_reviews(review_report),

        "funding_verification": {
            "nsfc_portal_searched": investigation.get("funding_check", {}).get("nsfc_portal_searched", False),
            "nsfc_active_projects": investigation.get("funding_check", {}).get("nsfc_active_projects"),
            "nsfc_last_search_date": investigation.get("funding_check", {}).get("nsfc_last_search_date"),
            "provincial_projects_found": investigation.get("funding_check", {}).get("provincial_projects_found"),
            "corporate_projects_found": investigation.get("funding_check", {}).get("corporate_projects_found"),
        },

        "manual_sources": manual,
        "claims": claims,
        "investigation_scope": investigation,
        "script_outputs": {
            "text_profiles": outputs_meta["text_profiles"],
            "citation_report": outputs_meta["citation_report"],
            "style_report": outputs_meta["style_report"],
            "review_matched": outputs_meta.get("review_matched"),
            "hybrid_score_report": outputs_meta.get("hybrid_score_report"),
        },

        "_builder_notes": [
            "This JSON was auto-generated by scholar_data_builder.py.",
            "Fields marked [TO BE FILLED] require manual input or LLM-assisted completion.",
            "Run data_validator.py before report generation."
        ]
    }

    return data


def _parse_claim(claim_str: str) -> int | str:
    """Extract a numeric value from fuzzy claims like '70余篇'."""
    if isinstance(claim_str, int):
        return claim_str
    import re
    nums = re.findall(r"\d+", str(claim_str))
    if nums:
        return int(nums[0])
    return claim_str


def _summarize_text_profiles(profiles: list) -> dict:
    valid = [p for p in profiles if p]
    if not valid:
        return {"status": "no_profiles_found", "note": "Run text_profiler.py on acquired PDFs first."}
    return {
        "status": f"{len(valid)} profile(s) loaded",
        "files": [p.get("source_file") or p.get("source_pdf") for p in valid],
        "total_characters": sum(p.get("basic_stats", {}).get("total_characters", 0) for p in valid),
        "total_originality_markers": sum(p.get("originality_markers", {}).get("total", 0) for p in valid),
        "total_references": sum(p.get("references", {}).get("count", 0) for p in valid),
    }


def _summarize_hybrid_report(report: dict | None) -> dict:
    if not report:
        return {"status": "no_report_found", "note": "Run hybrid_scorer.py prepare + apply first."}
    papers = report.get("papers", [])
    if not papers:
        return {"status": "empty_report", "note": "Report exists but contains no paper entries."}
    scores = [p.get("llm_score", 0) for p in papers]
    ratings = {}
    for p in papers:
        r = p.get("llm_rating", "?")
        ratings[r] = ratings.get(r, 0) + 1
    return {
        "status": f"loaded ({len(papers)} papers)",
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "max_score": round(max(scores), 1) if scores else None,
        "min_score": round(min(scores), 1) if scores else None,
        "rating_distribution": ratings,
        "top_papers": [
            {
                "title": p.get("file_name", "").replace(".md", "").replace(".pdf", ""),
                "score": p.get("llm_score"),
                "rating": p.get("llm_rating"),
            }
            for p in papers[:5]
        ],
        "bottom_papers": [
            {
                "title": p.get("file_name", "").replace(".md", "").replace(".pdf", ""),
                "score": p.get("llm_score"),
                "rating": p.get("llm_rating"),
            }
            for p in papers[-3:]
        ],
    }


def _summarize_citation_report(report: dict | None) -> dict:
    if not report:
        return {"status": "no_report_found", "note": "Run citation_profiler.py first."}
    raw_flags = report.get("red_flags", [])
    return {
        "status": "loaded",
        "self_citation_ratio": report.get("citation_structure", {}).get("ratios", {}).get("self_citation"),
        "team_citation_ratio": report.get("citation_structure", {}).get("ratios", {}).get("team_citation"),
        "h_index_anomalies": len(report.get("h_index_analysis", {}).get("anomalies", [])),
        "red_flags": [f["signal"] for f in raw_flags],
        "red_flags_detail": [
            {"signal": f.get("signal", ""), "detail": f.get("detail", ""), "severity": f.get("severity", "medium")}
            for f in raw_flags if f.get("signal") != "None detected"
        ],
    }


def _summarize_style_report(report: dict | None) -> dict:
    if not report:
        return {"status": "no_report_found", "note": "Run stylometry_profiler.py first."}
    return {
        "status": "loaded",
        "document_count": report.get("document_count"),
        "red_flags": [f["signal"] for f in report.get("red_flags", [])],
    }


def _summarize_reviews(report: dict | None) -> dict:
    if not report:
        return {"status": "no_report_found", "note": "Run review_matcher.py first.", "matched": False}

    # Build unified summary from review_matcher.py v2.0 output
    result = {
        "status": "loaded",
        "matched": report.get("matched", True),
        "count": report.get("review_count") or report.get("count"),
        "average_rating": report.get("rating_stats", {}).get("average") or report.get("average_rating") or report.get("avg_rating"),
        "average_credibility": report.get("credibility", {}).get("average_score"),
        # v2.0 new fields
        "investigation_leads": report.get("investigation_leads", []),
        "overall_risk_assessment": report.get("overall_risk_assessment", {}),
        "cross_dimensional_anomalies": report.get("cross_dimensional_anomalies", []),
        "dimension_summary": report.get("dimension_summary", {}),
        "radar_data": report.get("radar_data", []),
        # Raw evidence for downstream LLM reference
        "top_reviews": report.get("credibility", {}).get("top_reviews", []),
        "disclaimer": report.get("disclaimer", ""),
    }

    # Enrich leads with severity summary for quick reference
    leads = result["investigation_leads"]
    if leads:
        severity_counts = {}
        confidence_breakdown = {}
        for lead in leads:
            sev = lead.get("severity", "unknown")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            conf = lead.get("confidence_level", "L2")
            confidence_breakdown[conf] = confidence_breakdown.get(conf, 0) + 1
        result["lead_summary"] = {
            "total": len(leads),
            "severity_distribution": severity_counts,
            "confidence_distribution": confidence_breakdown,
        }

    return result


def run_validation(data: dict, output_path: str, fix: bool) -> bool:
    """Run built-in validation logic (mirrors data_validator) without importing it."""
    # Import dynamically to avoid hard dependency
    try:
        import data_validator as dv
        errors, warnings = dv.validate(data, fix=fix)
    except Exception as e:
        print(f"[WARN] Could not import data_validator.py ({e}). Running built-in light validation.", file=sys.stderr)
        errors, warnings = _light_validate(data)

    if warnings:
        print("\n[WARNINGS]")
        for w in warnings:
            print(f"  - {w}")

    if errors:
        print("\n[ERRORS]")
        for e in errors:
            print(f"  - {e}")
        print(f"\nValidation failed: {len(errors)} error(s), {len(warnings)} warning(s).")
        return False
    else:
        print(f"\nValidation passed: 0 error(s), {len(warnings)} warning(s).")
        return True


def _light_validate(data: dict) -> tuple:
    errors = []
    warnings = []
    required_top = ["name", "institution", "investigation_date", "basic_profile", "academic_outputs",
                    "quality_assessment", "relationship_network", "anomalies", "confidence_ratings"]
    for f in required_top:
        if f not in data:
            errors.append(f"[MISSING] Required top-level field: '{f}'")
    bp = data.get("basic_profile", {})
    for f in ["name", "institution", "current_title", "education_background", "career_timeline"]:
        if f not in bp:
            errors.append(f"[MISSING] basic_profile missing: '{f}'")
    ao = data.get("academic_outputs", {})
    for f in ["claimed_papers", "verified_papers", "claimed_monographs", "verified_monographs", "source_databases", "recent_3yr_papers"]:
        if f not in ao:
            errors.append(f"[MISSING] academic_outputs missing: '{f}'")
    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description="Build unified scholar_data.json from config and script outputs")
    parser.add_argument("--config", "-c", required=True, help="Path to config.yaml")
    parser.add_argument("--data-dir", "-d", default="./data", help="Directory containing script output JSONs")
    parser.add_argument("--output", "-o", required=True, help="Path to output scholar_data.json")
    parser.add_argument("--fix", action="store_true", help="Auto-fill missing defaults and validate")
    args = parser.parse_args()

    print(f"[INFO] Loading config: {args.config}")
    config = load_yaml(args.config)
    if not config:
        print("[ERROR] Failed to parse config.yaml", file=sys.stderr)
        sys.exit(1)

    data_dir = Path(args.data_dir)
    print(f"[INFO] Scanning data directory: {data_dir}")

    data = build_scholar_data(config, data_dir)

    if args.fix:
        try:
            import data_validator as dv
            data = dv.auto_fix(data)
            print("[INFO] Applied auto-fix rules from data_validator.")
        except Exception:
            print("[WARN] data_validator.py not available; auto-fix skipped.", file=sys.stderr)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[INFO] scholar_data.json written to: {args.output}")

    print("[INFO] Running validation...")
    ok = run_validation(data, args.output, fix=args.fix)
    if not ok:
        sys.exit(1)

    # Auto-generate network visualization if relationship data exists
    _maybe_generate_network(data, args.output)


def _has_relationship_data(rel: dict) -> bool:
    """Check if relationship_network contains any non-empty entries."""
    if not rel or not isinstance(rel, dict):
        return False
    for key in ["advisor", "key_collaborators", "editorial_connections", "institutional_dependencies"]:
        val = rel.get(key)
        if val and str(val).strip() and str(val).strip() != "[TO BE FILLED]":
            return True
    citation = rel.get("citation_analysis", {})
    if isinstance(citation, dict) and citation.get("status") == "loaded" and citation.get("red_flags_detail"):
        return True
    return False


def _maybe_generate_network(data: dict, output_path: str):
    rel = data.get("relationship_network", {})
    if not _has_relationship_data(rel):
        print("[INFO] relationship_network is empty; skipping network visualization.")
        return

    viz_script = Path(__file__).parent / "network_visualizer.py"
    if not viz_script.exists():
        viz_script = Path("scripts/network_visualizer.py")
    if not viz_script.exists():
        print("[WARN] network_visualizer.py not found; skipping network visualization.", file=sys.stderr)
        return

    out_dir = Path(output_path).parent / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = data.get("name", "scholar")

    cmd = [
        sys.executable, str(viz_script),
        "--input", output_path,
        "--output-dir", str(out_dir),
        "--prefix", prefix,
    ]
    print(f"[INFO] Auto-generating relationship network visualization...")
    print(f"  Command: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode == 0:
        print(f"[OK] Network visualization saved: {out_dir}/{prefix}_network.html")
    else:
        print("[WARN] network_visualizer.py exited with errors; manual run may be needed.", file=sys.stderr)


if __name__ == "__main__":
    main()
