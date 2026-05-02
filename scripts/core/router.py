#!/usr/bin/env python3
"""
core/router.py

Investigation type detection and track resolution.
Routes investigations to the correct pipeline based on config and metadata.

Usage:
    from core.router import detect_investigation_type, get_track_scripts, InvestigationType

    inv_type = detect_investigation_type(config)
    scripts = get_track_scripts(inv_type)
"""

from enum import Enum
from pathlib import Path
from typing import Optional


class InvestigationType(Enum):
    DOMESTIC = "domestic"
    INTERNATIONAL = "international"
    CROSS_BORDER = "cross_border"


# Keywords that strongly suggest an international institution
_INTERNATIONAL_KEYWORDS = [
    "university", "college", "institute", "mit", "stanford", "harvard",
    "oxford", "cambridge", "yale", "princeton", "columbia", "chicago",
    "berkeley", "caltech", "eth", "epfl", "imperial", "ucl", "tsinghua",
    "peking", "fudan", "zhejiang", "shanghai jiao tong", "nanjing",
    "universität", "université", "università",
]


def detect_investigation_type(config: dict) -> InvestigationType:
    """
    Detect investigation type from configuration.

    Priority:
    1. Explicit `investigation.investigation_type` field
    2. Presence of `international_sources` in config
    3. Institution name contains international keywords
    4. Default to DOMESTIC
    """
    # 1. Explicit declaration
    explicit = config.get("investigation", {}).get("investigation_type")
    if explicit:
        try:
            return InvestigationType(explicit)
        except ValueError:
            pass

    # 2. International sources configured
    if config.get("international_sources"):
        return InvestigationType.INTERNATIONAL

    # 3. Institution inference
    scholar = config.get("scholar", {})
    institution = scholar.get("institution", "").lower()
    institution_en = scholar.get("institution_en", "").lower()
    combined = f"{institution} {institution_en}"

    if any(kw in combined for kw in _INTERNATIONAL_KEYWORDS):
        # If the primary institution name has Chinese indicators, it's domestic
        # (even if it also has an English translation name)
        chinese_indicators = ["大学", "学院", "研究所", "中科院", "社科院"]
        if any(ind in institution for ind in chinese_indicators):
            return InvestigationType.DOMESTIC
        return InvestigationType.INTERNATIONAL

    # 4. Default
    return InvestigationType.DOMESTIC


def get_track_scripts(track: InvestigationType) -> dict[str, Path]:
    """
    Get the script paths for a given investigation track.

    Returns a dict mapping script roles to their Path objects.
    """
    scripts_dir = Path(__file__).parent.parent

    common = {
        "text_profiler": scripts_dir / "analysis" / "text_profiler.py",
        "paper_quality_rubric": scripts_dir / "analysis" / "paper_quality_rubric.py",
        "hybrid_scorer": scripts_dir / "analysis" / "hybrid_scorer.py",
        "stylometry_profiler": scripts_dir / "analysis" / "stylometry_profiler.py",
        "citation_profiler": scripts_dir / "analysis" / "citation_profiler.py",
        "network_visualizer": scripts_dir / "network" / "network_visualizer.py",
        "timeline_weaver": scripts_dir / "network" / "timeline_weaver.py",
        "report_prompt_optimizer": scripts_dir / "report" / "report_prompt_optimizer.py",
        "watermark": scripts_dir / "core" / "watermark.py",
    }

    if track == InvestigationType.DOMESTIC:
        return {
            **common,
            "data_importer": scripts_dir / "domestic" / "data_importer.py",
            "data_validator": scripts_dir / "domestic" / "data_validator.py",
            "scholar_data_builder": scripts_dir / "domestic" / "scholar_data_builder.py",
            "review_matcher": scripts_dir / "domestic" / "review_matcher.py",
            "wechat_search": scripts_dir / "domestic" / "wechat_search.py",
            "report_template": scripts_dir / "report" / "report_template.md",
        }

    elif track == InvestigationType.INTERNATIONAL:
        return {
            **common,
            "data_fetcher": scripts_dir / "international" / "data_fetcher.py",
            "data_validator": scripts_dir / "international" / "data_validator.py",
            "scholar_data_builder": scripts_dir / "international" / "scholar_data_builder.py",
            "evaluator": scripts_dir / "international" / "evaluator.py",
            "xiaohongshu_client": scripts_dir / "international" / "xiaohongshu_client.py",
            "heuristics_classifier": scripts_dir / "international" / "heuristics_classifier.py",
            "missing_reporter": scripts_dir / "international" / "missing_reporter.py",
            "report_template": scripts_dir / "report" / "international_template.md",
        }

    elif track == InvestigationType.CROSS_BORDER:
        return {
            **common,
            "domestic_builder": scripts_dir / "domestic" / "scholar_data_builder.py",
            "international_fetcher": scripts_dir / "international" / "data_fetcher.py",
            "cross_border_merger": scripts_dir / "cross_border" / "merger.py",
            "cross_border_validator": scripts_dir / "cross_border" / "validator.py",
            "report_template": scripts_dir / "report" / "report_template.md",
        }

    raise ValueError(f"Unknown track: {track}")


def get_step_definitions(track: InvestigationType) -> list[dict]:
    """
    Get step definitions for a given investigation track.

    Returns a list of step dicts compatible with investigate.py's STEPS format.
    """
    if track == InvestigationType.INTERNATIONAL:
        return [
            {
                "id": "init",
                "title": "初始化案件目录",
                "description": "复制 config.template.yaml，填写学者信息，创建标准目录结构。",
                "checklist": ["config.yaml 已存在且已填写", "data/ 目录已创建"],
                "next": "auto_fetch"
            },
            {
                "id": "auto_fetch",
                "title": "自动数据采集（免费API）",
                "description": "调用 OpenAlex/ORCID/Semantic Scholar 等免费API自动采集学者公开信息。",
                "command": "python scripts/international/data_fetcher.py --config ./config.yaml --output ./data/auto_fetched.json",
                "checklist": ["data/auto_fetched.json 已生成", "论文列表已获取", "合作者网络已构建"],
                "next": "xiaohongshu"
            },
            {
                "id": "xiaohongshu",
                "title": "小红书评价采集",
                "description": "搜索中国留学生对该导师的评价。",
                "command": "python scripts/international/xiaohongshu_client.py --name '导师姓名' --institution '学校' --output ./data/xiaohongshu_reviews.json",
                "checklist": ["data/xiaohongshu_reviews.json 已生成（如找到评价）"],
                "next": "manual_supplement"
            },
            {
                "id": "manual_supplement",
                "title": "手动补充调查",
                "description": "根据 missing_reporter 生成的指南，手动在 Scopus/WoS/机构官网补充缺失信息。",
                "command": "python scripts/international/missing_reporter.py --case-dir .",
                "checklist": ["missing_report.md 已阅读", "关键缺失信息已手动补充"],
                "next": "build"
            },
            {
                "id": "build",
                "title": "构建 scholar_data.json",
                "description": "使用 international/scholar_data_builder.py 聚合所有数据源。",
                "command": "python scripts/international/scholar_data_builder.py --config ./config.yaml --data-dir ./data --output ./scholar_data.json",
                "checklist": ["scholar_data.json 已生成", "文件已通过 validation"],
                "next": "validate"
            },
            {
                "id": "validate",
                "title": "数据验证",
                "description": "运行 international/data_validator.py 检查字段完整性。",
                "command": "python scripts/international/data_validator.py --input ./scholar_data.json",
                "checklist": ["0 errors", "所有 warning 已审查"],
                "next": "llm"
            },
            {
                "id": "llm",
                "title": "LLM 辅助填充与定性分析",
                "description": "将 scholar_data.json 提供给 LLM，补充缺失字段，进行质量评估。",
                "checklist": ["basic_profile 已补全", "quality_assessment 已完成", "anomalies 已列出"],
                "next": "prompt"
            },
            {
                "id": "prompt",
                "title": "生成报告 Prompt",
                "description": "使用 report_prompt_optimizer.py 生成优化后的报告 prompt。",
                "command": "python scripts/report/report_prompt_optimizer.py --data ./scholar_data.json --template ./scripts/report/international_template.md --llm claude --output ./report_prompt.md",
                "checklist": ["report_prompt.md 已生成"],
                "next": "report"
            },
            {
                "id": "report",
                "title": "生成最终 Markdown 报告",
                "description": "将优化后的 prompt 提交给 LLM，获取 Markdown 深度报告。",
                "checklist": ["报告已通过人工审阅", "两面性分析平衡", "证据链完整", "免责声明已包含"],
                "next": "done"
            },
            {
                "id": "done",
                "title": "调查完成",
                "description": "所有步骤已完成。",
                "checklist": [],
                "next": None
            },
        ]

    # Default: return None so investigate.py falls back to existing STEPS
    return None
