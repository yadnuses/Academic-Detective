#!/usr/bin/env python3
"""
analysis/review_aggregator.py

Merge multi-source student reviews into a unified schema compatible with
domestic/review_matcher.py v2.0 output.

Supported sources:
- Domestic: 导师评价网 (XLSX) via review_matcher.py v2.0
- International: 小红书 via xiaohongshu_client.py
- International: RateMyProfessors (optional, manual)

Usage:
    python analysis/review_aggregator.py \
        --domestic ./data/domestic_reviews.json \
        --xiaohongshu ./data/xhs_reviews.json \
        --output ./data/merged_reviews.json
"""

import argparse
import json
from pathlib import Path
from collections import Counter
from typing import Optional

from core_utils import get_logger, save_json

logger = get_logger("review_aggregator")


# ---------------------------------------------------------------------------
# Source weight map (credibility weight for averaging)
# ---------------------------------------------------------------------------

SOURCE_WEIGHTS = {
    "domestic": 1.0,        # 导师评价网 structured reviews
    "xiaohongshu": 0.7,     # Social media, higher bias risk
    "ratemyprofessors": 0.8, # Western counterpart
}

DIMENSION_NAME_MAP = {
    # Xiaohongshu -> Unified
    "graduation_difficulty_avg": "毕业难度",
    "workload_avg": "工作强度",
    "supportiveness_avg": "导师支持度",
    # Domestic -> Unified (already in Chinese)
    "导师辨识特征": "导师辨识特征",
    "学术水平": "学术水平",
    "科研经费": "科研经费",
    "学生补助": "学生补助",
    "师生关系": "师生关系",
    "工作时间": "工作时间",
    "学生前途": "学生前途",
    "自证认识导师": "自证认识导师",
    "毕业要求与论文署名": "毕业要求与论文署名",
    "组会与指导方式": "组会与指导方式",
    "人品与性格": "人品与性格",
    "实习与就业支持": "实习与就业支持",
    "推荐意愿": "推荐意愿",
    "实验室氛围": "实验室氛围",
}


def load_source(path: str | Path) -> dict:
    """Load a review source JSON."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def merge_dimension_summaries(sources: dict[str, dict]) -> dict:
    """Merge dimension summaries from multiple sources."""
    merged = {}
    source_weights = []

    for src_name, data in sources.items():
        weight = SOURCE_WEIGHTS.get(src_name, 0.5)
        dim_summary = data.get("dimension_summary", {})

        for raw_key, info in dim_summary.items():
            unified_key = DIMENSION_NAME_MAP.get(raw_key, raw_key)
            if unified_key not in merged:
                merged[unified_key] = {
                    "mention_count": 0,
                    "sentiment_distribution": Counter(),
                    "sample_quotes": [],
                    "sources": [],
                }

            # Handle different source formats
            if isinstance(info, dict):
                merged[unified_key]["mention_count"] += info.get("mention_count", 0)
                dist = info.get("sentiment_distribution", {})
                for k, v in dist.items():
                    merged[unified_key]["sentiment_distribution"][k] += v
                quotes = info.get("sample_quotes", [])
                merged[unified_key]["sample_quotes"].extend(quotes[:2])
                merged[unified_key]["sources"].append(src_name)
            elif isinstance(info, (int, float)):
                # Xiaohongshu numeric dimension (e.g., graduation_difficulty_avg)
                merged[unified_key]["numeric_value"] = info
                merged[unified_key]["sources"].append(src_name)

    # Normalize
    for key, val in merged.items():
        total = sum(val["sentiment_distribution"].values())
        if total > 0:
            dominant = val["sentiment_distribution"].most_common(1)[0][0]
        else:
            dominant = "neutral"
        val["dominant_sentiment"] = dominant
        val["sentiment_distribution"] = dict(val["sentiment_distribution"])
        val["sample_quotes"] = val["sample_quotes"][:5]
        val["sources"] = list(set(val["sources"]))

    return merged


def merge_leads(sources: dict[str, dict]) -> list[dict]:
    """Merge investigation leads from multiple sources, deduplicating by id."""
    seen = {}
    for src_name, data in sources.items():
        leads = data.get("investigation_leads", [])
        for lead in leads:
            lid = lead.get("id")
            if not lid:
                continue
            if lid in seen:
                # Merge: sum mention counts, upgrade severity if needed
                seen[lid]["mention_count"] += lead.get("mention_count", 0)
                seen[lid]["affected_reviews"] += lead.get("affected_reviews", 0)
                # Upgrade severity
                sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
                old_sev = seen[lid].get("severity", "low")
                new_sev = lead.get("severity", "low")
                if sev_order.get(new_sev, 99) < sev_order.get(old_sev, 99):
                    seen[lid]["severity"] = new_sev
                # Merge evidence quotes
                existing_quotes = set(seen[lid].get("evidence_quotes", []))
                new_quotes = lead.get("evidence_quotes", [])
                for q in new_quotes:
                    if q not in existing_quotes:
                        existing_quotes.add(q)
                        seen[lid].setdefault("evidence_quotes", []).append(q)
                # Track sources
                seen[lid].setdefault("sources", []).append(src_name)
            else:
                seen[lid] = dict(lead)
                seen[lid]["sources"] = [src_name]

    leads = list(seen.values())
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    leads.sort(key=lambda x: (sev_order.get(x.get("severity", "low"), 99), -x.get("mention_count", 0)))
    return leads


def merge_anomalies(sources: dict[str, dict]) -> list[dict]:
    """Merge cross-dimensional anomalies from multiple sources."""
    merged = []
    seen_patterns = set()
    for src_name, data in sources.items():
        anomalies = data.get("cross_dimensional_anomalies", [])
        for a in anomalies:
            pattern = a.get("pattern", "")
            if pattern and pattern not in seen_patterns:
                seen_patterns.add(pattern)
                a["source"] = src_name
                merged.append(a)
    return merged


def merge_overall_risk(sources: dict[str, dict]) -> dict:
    """Compute merged overall risk assessment."""
    critical = 0
    high = 0
    medium = 0

    for src_name, data in sources.items():
        risk = data.get("overall_risk_assessment", {})
        critical += risk.get("critical_leads", 0)
        high += risk.get("high_leads", 0)
        medium += risk.get("medium_leads", 0)

    if critical >= 1:
        level = "critical"
    elif high >= 2:
        level = "high"
    elif high >= 1 or medium >= 3:
        level = "medium"
    else:
        level = "low"

    source_names = list(sources.keys())
    return {
        "level": level,
        "critical_leads": critical,
        "high_leads": high,
        "medium_leads": medium,
        "summary": (
            f"合并 {len(source_names)} 个数据源，"
            f"发现 critical {critical} 条、high {high} 条、medium {medium} 条线索。"
            f"整体风险等级: {level}。"
        ),
    }


def aggregate_reviews(source_files: dict[str, str | Path]) -> dict:
    """
    Aggregate multiple review sources into a unified output.

    Args:
        source_files: Dict mapping source name to file path,
                      e.g., {"domestic": "./reviews.json", "xiaohongshu": "./xhs.json"}

    Returns:
        Unified review dict compatible with review_matcher.py v2.0 schema
    """
    sources = {}
    for src_name, path in source_files.items():
        if path and Path(path).exists():
            sources[src_name] = load_source(path)
            logger.info("Loaded source '%s' from %s", src_name, path)
        else:
            logger.warning("Source '%s' file not found: %s", src_name, path)

    if not sources:
        return {
            "matched": False,
            "status": "no_sources_loaded",
            "message": "未找到任何评价数据源",
        }

    # Total review count
    total_reviews = sum(
        s.get("review_count", 0)
        for s in sources.values()
    )

    # Average rating (weighted by source credibility)
    weighted_sum = 0.0
    weight_total = 0.0
    for src_name, data in sources.items():
        weight = SOURCE_WEIGHTS.get(src_name, 0.5)
        avg = data.get("rating_stats", {}).get("average")
        if avg is None:
            # Xiaohongshu uses different structure
            rec_ratio = data.get("recommendation_ratio")
            if rec_ratio is not None:
                avg = rec_ratio * 5  # Scale to 5-point
        if avg is not None:
            weighted_sum += avg * weight
            weight_total += weight

    merged_rating = round(weighted_sum / weight_total, 2) if weight_total > 0 else None

    # Merge dimension summaries
    dim_summary = merge_dimension_summaries(sources)

    # Merge leads
    leads = merge_leads(sources)

    # Merge anomalies
    anomalies = merge_anomalies(sources)

    # Overall risk
    risk = merge_overall_risk(sources)

    # Radar data (rebuild from merged dimension summary)
    radar = build_radar_from_summary(dim_summary)

    # Source metadata
    source_meta = {
        src: {
            "review_count": data.get("review_count", 0),
            "matched": data.get("matched", False),
            "weight": SOURCE_WEIGHTS.get(src, 0.5),
        }
        for src, data in sources.items()
    }

    return {
        "matched": total_reviews > 0,
        "status": "merged",
        "review_count": total_reviews,
        "source_count": len(sources),
        "sources": source_meta,
        "rating_stats": {
            "average": merged_rating,
            "source_weights": {k: SOURCE_WEIGHTS.get(k, 0.5) for k in sources.keys()},
        },
        "dimension_summary": dim_summary,
        "radar_data": radar,
        "cross_dimensional_anomalies": anomalies,
        "investigation_leads": leads,
        "overall_risk_assessment": risk,
        "disclaimer": (
            "本分析合并了多个匿名第三方学生评价数据源。所有线索均为假设生成器，"
            "必须通过可验证的公开记录交叉验证后才能纳入最终调查报告。"
            "各数据源可信度权重已标注，社交媒体来源（小红书）因样本偏差风险权重较低。"
        ),
    }


def build_radar_from_summary(dim_summary: dict) -> list[dict]:
    """Build radar chart data from merged dimension summary."""
    radar = []
    sentiment_score = {
        "positive": 5, "neutral": 3, "negative": 2,
        "strong_negative": 1, "intense_negative": 0,
    }
    for dim_name, data in dim_summary.items():
        dist = data.get("sentiment_distribution", {})
        total = sum(dist.values())
        if total == 0:
            # Numeric dimension (e.g., from Xiaohongshu)
            numeric = data.get("numeric_value")
            if numeric is not None:
                radar.append({
                    "dimension": dim_name,
                    "score": round(numeric, 2),
                    "max": 5,
                    "mention_count": data.get("mention_count", 1),
                    "dominant_sentiment": "neutral",
                })
            continue
        weighted = sum(sentiment_score.get(s, 3) * c for s, c in dist.items()) / total
        radar.append({
            "dimension": dim_name,
            "score": round(weighted, 2),
            "max": 5,
            "mention_count": data.get("mention_count", 0),
            "dominant_sentiment": data.get("dominant_sentiment", "neutral"),
        })
    return radar


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Multi-source review aggregator")
    parser.add_argument("--domestic", "-d", help="Path to domestic review_matcher output JSON")
    parser.add_argument("--xiaohongshu", "-x", help="Path to xiaohongshu_client output JSON")
    parser.add_argument("--ratemyprofessors", "-r", help="Path to RateMyProfessors JSON")
    parser.add_argument("--output", "-o", required=True, help="Output merged JSON")
    args = parser.parse_args()

    sources = {}
    if args.domestic:
        sources["domestic"] = args.domestic
    if args.xiaohongshu:
        sources["xiaohongshu"] = args.xiaohongshu
    if args.ratemyprofessors:
        sources["ratemyprofessors"] = args.ratemyprofessors

    if not sources:
        print("[ERROR] At least one source required")
        return

    result = aggregate_reviews(sources)
    save_json(result, Path(args.output))
    logger.info("Merged reviews saved to: %s", args.output)

    print(f"[OK] Merged {result['source_count']} sources, {result['review_count']} reviews")
    risk = result.get("overall_risk_assessment", {})
    print(f"     Risk level: {risk.get('level', 'unknown')}")
    print(f"     Leads: {len(result.get('investigation_leads', []))}")
    print(f"     Saved to: {args.output}")


if __name__ == "__main__":
    main()
