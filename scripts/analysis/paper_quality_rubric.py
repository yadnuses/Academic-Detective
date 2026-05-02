#!/usr/bin/env python3
"""
paper_quality_rubric.py

Peer-review-aligned paper quality assessment tool.
Maps `text_profiler.py` outputs and manual observations onto an international
standard rubric derived from Nature, Springer, and ACM/IEEE review criteria.

Usage:
    python paper_quality_rubric.py --profile ./data/paper_profile.json --output ./data/paper_quality.json
    python paper_quality_rubric.py --profile ./data/paper_profile.json --observations ./observations.json --output ./data/paper_quality.json

Input JSON schemas:
- `profile`: output from `text_profiler.py`
- `observations` (optional): human-coded observations for dimensions not detectable by text mining
  {
    "originality_score": 85,      # 0-100
    "validity_concerns": ["..."], # list of strings or empty
    "data_reproducibility": "high", # high/medium/low/unknown
    "conclusion_robustness": "medium", # high/medium/low
    "statistical_rigor": "high",   # high/medium/low/na
    "structure_score": 80,         # 0-100 optional override
    "structure_quality": "medium", # high/medium/low
    "has_fatal_flaw": false,
    "ethical_flags": []
  }

Output JSON:
  {
    "dimensions": { ... },
    "overall_rating": "B+",
    "overall_score": 78.5,
    "verdict": "Good — solid work, minor revisions needed.",
    "red_flags": [ ... ]
  }
"""

import json
import sys
import math
import argparse
from pathlib import Path
from typing import Any


DIMENSIONS = {
    "originality_significance": {
        "name": "原创性与重要性",
        "weight": 0.25,
        "description": "论文是否提出了新的理解、方法或证据，足以影响该领域的思考方向（Nature标准）。",
    },
    "validity_rigor": {
        "name": "技术严谨性",
        "weight": 0.20,
        "description": "研究方法是否适当，是否存在应禁止发表的致命缺陷（fatal flaws）。",
    },
    "data_evidence": {
        "name": "数据与证据质量",
        "weight": 0.20,
        "description": "数据质量、方法透明度、结果可重复性、统计处理适当性（Nature+Springer标准）。",
    },
    "structure_conclusions": {
        "name": "逻辑结构与结论稳健性",
        "weight": 0.15,
        "description": "结构是否清晰，结论与数据是否匹配，解释是否稳健可靠。",
    },
    "literature_engagement": {
        "name": "文献综述与引用规范",
        "weight": 0.10,
        "description": "是否恰当引用前人工作，是否存在过度自引或遗漏关键文献。",
    },
    "clarity_accessibility": {
        "name": "表达清晰度与可及性",
        "weight": 0.10,
        "description": "写作是否清晰，摘要是否准确可及，图表是否自明（Nature标准）。",
    },
}


def score_to_rating(score: float) -> str:
    if score >= 85:
        return "A"
    elif score >= 75:
        return "B+"
    elif score >= 65:
        return "B"
    elif score >= 55:
        return "C"
    else:
        return "D"


def rating_to_verdict(rating: str) -> str:
    mapping = {
        "A": "Excellent — major advance, Nature-level visibility.",
        "B+": "Good — solid work, minor revisions needed.",
        "B": "Moderate — publishable in specialist journal with revisions.",
        "C": "Poor — major concerns, extensive revision or rejection likely.",
        "D": "Unacceptable — fatal flaws, should not be published.",
    }
    return mapping.get(rating, "Unknown")


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_originality(profile: dict, obs: dict) -> dict:
    """Infer originality from originality_markers, term novelty, and human score."""
    base = 60.0
    markers = profile.get("originality_markers", {})
    marker_total = markers.get("total", 0)
    chars = profile.get("basic_stats", {}).get("total_characters", 1) or 1

    # Density of first-person scholarly claims per 1000 chars
    density = (marker_total / chars) * 1000
    if density >= 8:
        base += 10
    elif density >= 4:
        base += 5
    else:
        base -= 5

    # Human override takes precedence if provided
    if "originality_score" in obs:
        base = obs["originality_score"] * 0.7 + base * 0.3

    base = max(0, min(100, base))
    return {"score": round(base, 1), "notes": f"原创性标记密度: {density:.2f}/1000字"}


def compute_validity(profile: dict, obs: dict) -> dict:
    base = 70.0
    fatal = obs.get("has_fatal_flaw", False)
    concerns = obs.get("validity_concerns", [])

    if fatal:
        base = 30.0
    elif concerns:
        base -= len(concerns) * 8

    base = max(0, min(100, base))
    note = "存在致命缺陷" if fatal else (f"发现 {len(concerns)} 项有效性疑点" if concerns else "未发现明显有效性缺陷")
    return {"score": round(base, 1), "notes": note}


def compute_data_evidence(profile: dict, obs: dict) -> dict:
    base = 65.0
    refs = profile.get("references", {})
    ref_count = refs.get("count", 0)

    # Reference count as a weak proxy for data engagement depth
    if ref_count >= 40:
        base += 5
    elif ref_count < 10:
        base -= 10

    # Human observation overrides
    repro = obs.get("data_reproducibility", "unknown")
    if repro == "high":
        base += 10
    elif repro == "low":
        base -= 15

    stat = obs.get("statistical_rigor", "na")
    if stat == "high":
        base += 5
    elif stat == "low":
        base -= 10

    base = max(0, min(100, base))
    return {"score": round(base, 1), "notes": f"参考文献数: {ref_count}; 可重复性: {repro}; 统计严谨性: {stat}"}


def compute_structure_conclusions(profile: dict, obs: dict) -> dict:
    # Human override takes highest precedence
    if "structure_score" in obs:
        base = obs["structure_score"]
        return {"score": round(base, 1), "notes": f"结构评分由LLM/专家覆盖: {base}"}

    base = 70.0
    chapters = profile.get("chapter_structure", [])
    if len(chapters) >= 4:
        base += 5
    elif len(chapters) < 2:
        base -= 5

    robustness = obs.get("conclusion_robustness", "medium")
    if robustness == "high":
        base += 10
    elif robustness == "low":
        base -= 15

    structure_qual = obs.get("structure_quality", "medium")
    if structure_qual == "high":
        base += 5
    elif structure_qual == "low":
        base -= 10

    base = max(0, min(100, base))
    return {"score": round(base, 1), "notes": f"章节/小节数: {len(chapters)}; 结论稳健性: {robustness}; 结构质量: {structure_qual}"}


def compute_literature(profile: dict, obs: dict) -> dict:
    base = 70.0
    refs = profile.get("references", {})
    foreign_ratio = refs.get("foreign_ratio")
    latest_year = refs.get("latest_year")

    if foreign_ratio is not None:
        if foreign_ratio >= 0.3:
            base += 5
        elif foreign_ratio < 0.05:
            base -= 5

    if latest_year:
        current_year = 2026  # Approximate
        if current_year - latest_year <= 3:
            base += 5
        elif current_year - latest_year >= 10:
            base -= 10

    base = max(0, min(100, base))
    return {"score": round(base, 1), "notes": f"外文引用比: {foreign_ratio}; 最新引用年份: {latest_year}"}


def compute_clarity(profile: dict, obs: dict) -> dict:
    base = 70.0
    stats = profile.get("basic_stats", {})
    chars = stats.get("total_characters", 0)
    # Very short papers may lack exposition depth
    if chars < 3000:
        base -= 10
    elif chars > 15000:
        base += 5

    base = max(0, min(100, base))
    return {"score": round(base, 1), "notes": f"总字符数: {chars}"}


def generate_red_flags(dimensions: dict, overall_score: float, obs: dict) -> list:
    flags = []

    if overall_score < 55:
        flags.append({"signal": "Overall quality below acceptable threshold", "severity": "high"})

    if dimensions["validity_rigor"]["score"] < 50:
        flags.append({"signal": "Serious validity concerns or fatal flaws detected", "severity": "high"})

    if dimensions["originality_significance"]["score"] < 50:
        flags.append({"signal": "Lack of originality or significant advance", "severity": "high"})

    if dimensions["data_evidence"]["score"] < 55:
        flags.append({"signal": "Weak data quality or poor reproducibility", "severity": "medium-high"})

    if obs.get("has_fatal_flaw"):
        flags.append({"signal": "Fatal flaw explicitly flagged by reviewer", "severity": "high"})

    if not flags:
        flags.append({"signal": "No major red flags", "severity": "low"})

    return flags


def main():
    parser = argparse.ArgumentParser(description="Peer-review-aligned paper quality rubric")
    parser.add_argument("--profile", "-p", required=True, help="Path to text_profiler JSON output")
    parser.add_argument("--observations", "-o", help="Path to human observations JSON")
    parser.add_argument("--output", "-O", required=True, help="Path to output JSON")
    args = parser.parse_args()

    print(f"[INFO] Loading profile: {args.profile}")
    profile = load_json(args.profile)

    obs = {}
    if args.observations:
        print(f"[INFO] Loading observations: {args.observations}")
        obs = load_json(args.observations)

    print("[INFO] Computing dimension scores...")
    dims = {
        "originality_significance": compute_originality(profile, obs),
        "validity_rigor": compute_validity(profile, obs),
        "data_evidence": compute_data_evidence(profile, obs),
        "structure_conclusions": compute_structure_conclusions(profile, obs),
        "literature_engagement": compute_literature(profile, obs),
        "clarity_accessibility": compute_clarity(profile, obs),
    }

    overall = sum(dims[k]["score"] * DIMENSIONS[k]["weight"] for k in DIMENSIONS)
    rating = score_to_rating(overall)

    report = {
        "source_file": profile.get("source_file") or profile.get("source_pdf", "unknown"),
        "dimensions": {
            k: {
                "name": DIMENSIONS[k]["name"],
                "weight": DIMENSIONS[k]["weight"],
                "score": dims[k]["score"],
                "rating": score_to_rating(dims[k]["score"]),
                "notes": dims[k]["notes"],
            }
            for k in DIMENSIONS
        },
        "overall_score": round(overall, 1),
        "overall_rating": rating,
        "verdict": rating_to_verdict(rating),
        "red_flags": generate_red_flags(dims, overall, obs),
        "observations_used": bool(obs),
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"[INFO] Report saved to: {args.output}")
    print(f"[SUMMARY] Overall: {rating} ({overall:.1f}/100) — {report['verdict']}")
    for k in DIMENSIONS:
        d = report["dimensions"][k]
        print(f"  {d['name']}: {d['rating']} ({d['score']})")


if __name__ == "__main__":
    main()
