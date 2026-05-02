#!/usr/bin/env python3
"""
analysis/source_evaluation.py

CRAAP Test 信息源评估框架实现。

评估每个信息源在五个维度上的可信度：
  Currency（时效性）, Relevance（相关性）, Authority（权威性）,
  Accuracy（准确性）, Purpose（目的性）。

支持通过预设模板快速初始化常见学术信息源类型的权重与基准评分，
最终输出结构化 JSON 评估报告。

Usage (Python API):
    from analysis.source_evaluation import SourceEvaluator, SourceType

    evaluator = SourceEvaluator()
    report = evaluator.evaluate(
        source_desc="https://www.nature.com/articles/s41586-023-06012-9",
        source_type=SourceType.JOURNAL_ARTICLE,
        scores={"currency": 5, "relevance": 5, "authority": 5, "accuracy": 5, "purpose": 5},
    )

Usage (CLI):
    python source_evaluation.py \
        --source "https://www.nature.com/articles/s41586-023-06012-9" \
        --type journal_article \
        --currency 5 --relevance 5 --authority 5 --accuracy 5 --purpose 5 \
        --output report.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

# Allow direct execution from analysis/ subdir
if __name__ == "__main__":
    _script_dir = Path(__file__).parent.resolve()
    _project_root = _script_dir.parent
    if str(_project_root) not in sys.path:
        sys.path.insert(0, str(_project_root))

from core.utils import get_logger

logger = get_logger("source_evaluation")


# ---------------------------------------------------------------------------
# Constants & enums
# ---------------------------------------------------------------------------

class SourceType(str, Enum):
    """预设的学术信息源类型。"""

    JOURNAL_ARTICLE = "journal_article"          # 期刊论文
    OFFICIAL_WEBSITE = "official_website"        # 官方网站
    NEWS_REPORT = "news_report"                  # 新闻报道
    BAIDU_BAIKE = "baidu_baike"                  # 百度百科
    SOCIAL_ORG_DISCLOSURE = "social_org_disclosure"  # 社会组织公示
    PREPRINT = "preprint"                        # 预印本
    THESIS = "thesis"                            # 学位论文
    CONFERENCE_PAPER = "conference_paper"        # 会议论文
    GOVERNMENT_DOC = "government_doc"            # 政府文件
    BLOG_OPINION = "blog_opinion"                # 博客/观点文章
    CUSTOM = "custom"                            # 自定义


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CRAAPScores:
    """CRAAP 五个维度的原始评分（1-5）。"""

    currency: int      # 时效性
    relevance: int     # 相关性
    authority: int     # 权威性
    accuracy: int      # 准确性
    purpose: int       # 目的性

    def __post_init__(self):
        for k, v in asdict(self).items():
            if not isinstance(v, int) or not 1 <= v <= 5:
                raise ValueError(f"{k} 评分必须在 1-5 之间，收到: {v}")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DimensionWeight:
    """单个维度的权重与说明。"""

    weight: float
    description: str


@dataclass
class SourceTemplate:
    """信息源类型评估模板。"""

    name: str
    name_zh: str
    default_weights: dict[str, float]      # 维度 -> 权重
    baseline_scores: dict[str, int]        # 维度 -> 基准评分（用于风险对比）
    description: str
    typical_use_cases: list[str]


# ---------------------------------------------------------------------------
# Preset templates
# ---------------------------------------------------------------------------

_SOURCE_TEMPLATES: dict[SourceType, SourceTemplate] = {
    SourceType.JOURNAL_ARTICLE: SourceTemplate(
        name="journal_article",
        name_zh="期刊论文",
        default_weights={
            "currency": 0.15,
            "relevance": 0.25,
            "authority": 0.25,
            "accuracy": 0.25,
            "purpose": 0.10,
        },
        baseline_scores={
            "currency": 4,
            "relevance": 4,
            "authority": 5,
            "accuracy": 5,
            "purpose": 4,
        },
        description="经同行评审的学术期刊论文，通常权威性、准确性较高。",
        typical_use_cases=["核心证据", "理论支撑", "方法学参考"],
    ),
    SourceType.OFFICIAL_WEBSITE: SourceTemplate(
        name="official_website",
        name_zh="官方网站",
        default_weights={
            "currency": 0.20,
            "relevance": 0.25,
            "authority": 0.25,
            "accuracy": 0.20,
            "purpose": 0.10,
        },
        baseline_scores={
            "currency": 4,
            "relevance": 4,
            "authority": 4,
            "accuracy": 4,
            "purpose": 4,
        },
        description="高校、研究机构、政府部门等官方站点发布的信息。",
        typical_use_cases=["机构背景核实", "官方数据", "人员履历验证"],
    ),
    SourceType.NEWS_REPORT: SourceTemplate(
        name="news_report",
        name_zh="新闻报道",
        default_weights={
            "currency": 0.25,
            "relevance": 0.20,
            "authority": 0.15,
            "accuracy": 0.20,
            "purpose": 0.20,
        },
        baseline_scores={
            "currency": 5,
            "relevance": 3,
            "authority": 3,
            "accuracy": 3,
            "purpose": 3,
        },
        description="主流媒体或行业媒体的新闻报道，时效性强但权威性参差不齐。",
        typical_use_cases=["事件追踪", "舆论动态", "初步线索收集"],
    ),
    SourceType.BAIDU_BAIKE: SourceTemplate(
        name="baidu_baike",
        name_zh="百度百科",
        default_weights={
            "currency": 0.15,
            "relevance": 0.20,
            "authority": 0.15,
            "accuracy": 0.20,
            "purpose": 0.30,
        },
        baseline_scores={
            "currency": 3,
            "relevance": 3,
            "authority": 2,
            "accuracy": 2,
            "purpose": 2,
        },
        description="开放式网络百科，任何人可编辑，权威性与准确性风险较高。",
        typical_use_cases=["快速背景了解", "初步概念梳理", "非核心信息参考"],
    ),
    SourceType.SOCIAL_ORG_DISCLOSURE: SourceTemplate(
        name="social_org_disclosure",
        name_zh="社会组织公示",
        default_weights={
            "currency": 0.20,
            "relevance": 0.25,
            "authority": 0.20,
            "accuracy": 0.20,
            "purpose": 0.15,
        },
        baseline_scores={
            "currency": 3,
            "relevance": 4,
            "authority": 3,
            "accuracy": 3,
            "purpose": 3,
        },
        description="社会组织、行业协会、基金会等公示的信息，需核实组织公信力。",
        typical_use_cases=["项目信息", "成员名单", "活动记录"],
    ),
    SourceType.PREPRINT: SourceTemplate(
        name="preprint",
        name_zh="预印本",
        default_weights={
            "currency": 0.20,
            "relevance": 0.25,
            "authority": 0.20,
            "accuracy": 0.20,
            "purpose": 0.15,
        },
        baseline_scores={
            "currency": 5,
            "relevance": 4,
            "authority": 3,
            "accuracy": 3,
            "purpose": 4,
        },
        description="未经同行评审的预印本文章，时效性强但准确性待验证。",
        typical_use_cases=["前沿进展追踪", "初步结果参考"],
    ),
    SourceType.THESIS: SourceTemplate(
        name="thesis",
        name_zh="学位论文",
        default_weights={
            "currency": 0.15,
            "relevance": 0.25,
            "authority": 0.20,
            "accuracy": 0.25,
            "purpose": 0.15,
        },
        baseline_scores={
            "currency": 3,
            "relevance": 4,
            "authority": 3,
            "accuracy": 4,
            "purpose": 4,
        },
        description="博士或硕士学位论文，通常经过导师审核但未经期刊同行评审。",
        typical_use_cases=["系统综述参考", "方法学细节", "研究背景"],
    ),
    SourceType.CONFERENCE_PAPER: SourceTemplate(
        name="conference_paper",
        name_zh="会议论文",
        default_weights={
            "currency": 0.20,
            "relevance": 0.25,
            "authority": 0.20,
            "accuracy": 0.20,
            "purpose": 0.15,
        },
        baseline_scores={
            "currency": 4,
            "relevance": 4,
            "authority": 3,
            "accuracy": 3,
            "purpose": 4,
        },
        description="学术会议论文，质量取决于会议声誉与审稿严格程度。",
        typical_use_cases=["前沿成果", "方法学参考"],
    ),
    SourceType.GOVERNMENT_DOC: SourceTemplate(
        name="government_doc",
        name_zh="政府文件",
        default_weights={
            "currency": 0.20,
            "relevance": 0.25,
            "authority": 0.25,
            "accuracy": 0.20,
            "purpose": 0.10,
        },
        baseline_scores={
            "currency": 4,
            "relevance": 4,
            "authority": 5,
            "accuracy": 4,
            "purpose": 4,
        },
        description="政府发布的政策文件、统计数据、官方公告等。",
        typical_use_cases=["政策法规依据", "官方统计数据", "权威背书"],
    ),
    SourceType.BLOG_OPINION: SourceTemplate(
        name="blog_opinion",
        name_zh="博客/观点文章",
        default_weights={
            "currency": 0.20,
            "relevance": 0.20,
            "authority": 0.15,
            "accuracy": 0.15,
            "purpose": 0.30,
        },
        baseline_scores={
            "currency": 3,
            "relevance": 3,
            "authority": 2,
            "accuracy": 2,
            "purpose": 2,
        },
        description="个人博客、专栏文章或观点性内容，主观性强，需交叉验证。",
        typical_use_cases=["观点参考", "初步线索", "非核心信息"],
    ),
    SourceType.CUSTOM: SourceTemplate(
        name="custom",
        name_zh="自定义",
        default_weights={
            "currency": 0.20,
            "relevance": 0.20,
            "authority": 0.20,
            "accuracy": 0.20,
            "purpose": 0.20,
        },
        baseline_scores={
            "currency": 3,
            "relevance": 3,
            "authority": 3,
            "accuracy": 3,
            "purpose": 3,
        },
        description="用户自定义信息源，使用均等权重作为起点。",
        typical_use_cases=["特殊来源", "混合来源"],
    ),
}


# ---------------------------------------------------------------------------
# Risk thresholds
# ---------------------------------------------------------------------------

_TOTAL_SCORE_LEVELS = {
    "excellent": (4.5, 5.0),    # 高度可信
    "good": (3.5, 4.5),         # 基本可信
    "fair": (2.5, 3.5),         # 需谨慎使用
    "poor": (1.5, 2.5),         # 可信度低
    "unreliable": (1.0, 1.5),   # 不建议使用
}

_DIM_SCORE_LEVELS = {
    "high": (4, 5),
    "medium": (3, 4),
    "low": (1, 3),
}


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

class SourceEvaluator:
    """CRAAP Test 信息源评估器。"""

    def __init__(self, custom_weights: Optional[dict[str, float]] = None):
        self.custom_weights = custom_weights

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        source_desc: str,
        source_type: SourceType | str = SourceType.CUSTOM,
        scores: dict[str, int] | None = None,
        investigation_time_range: Optional[tuple[int, int]] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """
        对单个信息源执行 CRAAP 评估。

        Args:
            source_desc: 信息源描述（URL、文献标题、声明等）。
            source_type: 信息源类型，可使用 SourceType 枚举或字符串。
            scores: 五个维度的评分字典，键为 currency/relevance/authority/accuracy/purpose，值为 1-5。
            investigation_time_range: 调查关注的时间范围 (start_year, end_year)，用于时效性分析。
            notes: 评估备注。

        Returns:
            结构化 JSON 评估报告字典。
        """
        if scores is None:
            scores = {}

        # 标准化 source_type
        if isinstance(source_type, str):
            source_type = SourceType(source_type)

        # 构建 CRAAPScores
        template = _SOURCE_TEMPLATES.get(source_type, _SOURCE_TEMPLATES[SourceType.CUSTOM])
        craap = self._build_craap_scores(scores, template)

        # 确定权重
        weights = self.custom_weights if self.custom_weights else template.default_weights
        weights = self._normalize_weights(weights)

        # 计算加权总分
        total_score = self._compute_total_score(craap, weights)

        # 风险分析
        risk_analysis = self._analyze_risks(craap, template, weights)

        # 生成建议
        recommendations = self._generate_recommendations(craap, risk_analysis, total_score)

        report = {
            "meta": {
                "version": "1.0.0",
                "framework": "CRAAP Test",
                "evaluated_at": datetime.now().isoformat(timespec="seconds"),
            },
            "source": {
                "description": source_desc,
                "type": source_type.value,
                "type_name_zh": template.name_zh,
                "investigation_time_range": list(investigation_time_range) if investigation_time_range else None,
                "notes": notes,
            },
            "scores": {
                "currency": {
                    "score": craap.currency,
                    "max": 5,
                    "weight": round(weights["currency"], 3),
                    "weighted_contribution": round(craap.currency * weights["currency"], 3),
                    "dimension": "时效性",
                    "description": "信息是否新近，是否符合调查时间范围",
                },
                "relevance": {
                    "score": craap.relevance,
                    "max": 5,
                    "weight": round(weights["relevance"], 3),
                    "weighted_contribution": round(craap.relevance * weights["relevance"], 3),
                    "dimension": "相关性",
                    "description": "信息是否直接回答调查问题",
                },
                "authority": {
                    "score": craap.authority,
                    "max": 5,
                    "weight": round(weights["authority"], 3),
                    "weighted_contribution": round(craap.authority * weights["authority"], 3),
                    "dimension": "权威性",
                    "description": "作者资质、发表平台、机构背书",
                },
                "accuracy": {
                    "score": craap.accuracy,
                    "max": 5,
                    "weight": round(weights["accuracy"], 3),
                    "weighted_contribution": round(craap.accuracy * weights["accuracy"], 3),
                    "dimension": "准确性",
                    "description": "是否有证据支撑，是否与其他来源一致",
                },
                "purpose": {
                    "score": craap.purpose,
                    "max": 5,
                    "weight": round(weights["purpose"], 3),
                    "weighted_contribution": round(craap.purpose * weights["purpose"], 3),
                    "dimension": "目的性",
                    "description": "目的是科学/教育还是宣传/商业",
                },
            },
            "summary": {
                "total_score": round(total_score, 2),
                "max_possible": 5.0,
                "level": self._total_score_level(total_score),
                "level_zh": self._total_score_level_zh(total_score),
                "risk_flags": risk_analysis["flags"],
                "risk_count": len(risk_analysis["flags"]),
            },
            "risk_analysis": risk_analysis,
            "recommendations": recommendations,
            "template_info": {
                "name": template.name,
                "name_zh": template.name_zh,
                "description": template.description,
                "typical_use_cases": template.typical_use_cases,
                "baseline_scores": template.baseline_scores,
            },
        }

        logger.info(
            "Evaluated source '%s' (%s): total=%.2f, level=%s, risks=%d",
            source_desc[:60],
            source_type.value,
            total_score,
            report["summary"]["level"],
            len(risk_analysis["flags"]),
        )
        return report

    def batch_evaluate(
        self,
        items: list[dict],
    ) -> list[dict]:
        """
        批量评估多个信息源。

        Args:
            items: 每个元素为 dict，包含 source_desc, source_type, scores 等键，
                   与 evaluate() 的参数对应。

        Returns:
            评估报告列表。
        """
        reports = []
        for idx, item in enumerate(items, 1):
            try:
                report = self.evaluate(
                    source_desc=item["source_desc"],
                    source_type=item.get("source_type", SourceType.CUSTOM),
                    scores=item.get("scores", {}),
                    investigation_time_range=item.get("investigation_time_range"),
                    notes=item.get("notes"),
                )
                reports.append(report)
            except Exception as exc:
                logger.error("Batch item %d failed: %s", idx, exc)
                reports.append({
                    "meta": {"evaluated_at": datetime.now().isoformat(timespec="seconds"), "error": str(exc)},
                    "source": {"description": item.get("source_desc", ""), "type": item.get("source_type", "")},
                })
        return reports

    @staticmethod
    def list_templates() -> list[dict]:
        """列出所有预设模板的基本信息。"""
        return [
            {
                "type": t.name,
                "name_zh": t.name_zh,
                "description": t.description,
                "typical_use_cases": t.typical_use_cases,
            }
            for t in _SOURCE_TEMPLATES.values()
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_craap_scores(
        self, scores: dict[str, int], template: SourceTemplate
    ) -> CRAAPScores:
        """用用户输入填充缺失维度，缺失时使用模板基准分。"""
        filled = {}
        for dim in ("currency", "relevance", "authority", "accuracy", "purpose"):
            val = scores.get(dim)
            if val is None:
                val = template.baseline_scores.get(dim, 3)
                logger.debug("Score for '%s' missing, using baseline %d", dim, val)
            filled[dim] = val
        return CRAAPScores(**filled)

    def _normalize_weights(self, weights: dict[str, float]) -> dict[str, float]:
        """将权重归一化为和为 1.0。"""
        total = sum(weights.get(d, 0.2) for d in ("currency", "relevance", "authority", "accuracy", "purpose"))
        if total == 0:
            return {d: 0.2 for d in ("currency", "relevance", "authority", "accuracy", "purpose")}
        return {d: weights.get(d, 0.2) / total for d in ("currency", "relevance", "authority", "accuracy", "purpose")}

    def _compute_total_score(self, craap: CRAAPScores, weights: dict[str, float]) -> float:
        return sum(
            getattr(craap, dim) * weights[dim]
            for dim in ("currency", "relevance", "authority", "accuracy", "purpose")
        )

    def _total_score_level(self, score: float) -> str:
        for level, (low, high) in _TOTAL_SCORE_LEVELS.items():
            if low <= score <= high:
                return level
        return "unknown"

    def _total_score_level_zh(self, score: float) -> str:
        mapping = {
            "excellent": "高度可信",
            "good": "基本可信",
            "fair": "需谨慎使用",
            "poor": "可信度低",
            "unreliable": "不建议使用",
        }
        return mapping.get(self._total_score_level(score), "未知")

    def _analyze_risks(
        self, craap: CRAAPScores, template: SourceTemplate, weights: dict[str, float]
    ) -> dict:
        """逐维度对比基准分，生成风险标记。"""
        flags = []
        dim_scores = craap.to_dict()
        baseline = template.baseline_scores

        for dim in ("currency", "relevance", "authority", "accuracy", "purpose"):
            score = dim_scores[dim]
            base = baseline.get(dim, 3)
            dim_weight = weights[dim]

            # 低于基准 2 分及以上，且权重较高
            if score <= base - 2 and dim_weight >= 0.2:
                flags.append({
                    "dimension": dim,
                    "severity": "high",
                    "severity_zh": "高",
                    "message": f"{dim} 评分 {score} 远低于该类型基准 {base}，权重较高，显著拉低可信度",
                    "score": score,
                    "baseline": base,
                })
            # 低于基准 1 分
            elif score <= base - 1:
                flags.append({
                    "dimension": dim,
                    "severity": "medium",
                    "severity_zh": "中",
                    "message": f"{dim} 评分 {score} 低于该类型基准 {base}",
                    "score": score,
                    "baseline": base,
                })
            # 单项极低（<=2）
            elif score <= 2:
                flags.append({
                    "dimension": dim,
                    "severity": "medium",
                    "severity_zh": "中",
                    "message": f"{dim} 评分仅 {score}，存在明显缺陷",
                    "score": score,
                    "baseline": base,
                })

        # 整体极低分额外标记
        if all(v <= 2 for v in dim_scores.values()):
            flags.append({
                "dimension": "overall",
                "severity": "critical",
                "severity_zh": "严重",
                "message": "所有维度评分均低于等于 2，该信息源可信度极低",
                "score": None,
                "baseline": None,
            })

        # 风险等级汇总
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for f in flags:
            severity_counts[f["severity"]] = severity_counts.get(f["severity"], 0) + 1

        overall_risk = "low"
        if severity_counts["critical"] > 0:
            overall_risk = "critical"
        elif severity_counts["high"] > 0:
            overall_risk = "high"
        elif severity_counts["medium"] > 0:
            overall_risk = "medium"

        return {
            "flags": flags,
            "severity_counts": severity_counts,
            "overall_risk": overall_risk,
            "overall_risk_zh": {"critical": "严重", "high": "高", "medium": "中", "low": "低"}.get(overall_risk, "低"),
        }

    def _generate_recommendations(
        self, craap: CRAAPScores, risk_analysis: dict, total_score: float
    ) -> list[dict]:
        """基于评分与风险生成行动建议。"""
        recs = []
        dim_scores = craap.to_dict()

        # 基于总分
        level = self._total_score_level(total_score)
        if level == "excellent":
            recs.append({
                "priority": "info",
                "message": "该信息源可信度优秀，可作为核心证据使用。",
            })
        elif level == "good":
            recs.append({
                "priority": "info",
                "message": "该信息源基本可信，建议在关键结论处补充其他来源交叉验证。",
            })
        elif level == "fair":
            recs.append({
                "priority": "warning",
                "message": "该信息源需谨慎使用，建议仅作为辅助参考，核心论点需更强来源支撑。",
            })
        elif level in ("poor", "unreliable"):
            recs.append({
                "priority": "critical",
                "message": "该信息源可信度低，不建议作为调查依据，应寻找替代来源。",
            })

        # 基于单项弱点
        for dim, score in dim_scores.items():
            if score <= 2:
                dim_names = {
                    "currency": "时效性",
                    "relevance": "相关性",
                    "authority": "权威性",
                    "accuracy": "准确性",
                    "purpose": "目的性",
                }
                recs.append({
                    "priority": "warning",
                    "message": f"{dim_names[dim]}维度评分较低，建议重点核查该维度对应的信息质量。",
                })

        # 基于风险标记
        for flag in risk_analysis["flags"]:
            if flag["severity"] == "critical":
                recs.append({
                    "priority": "critical",
                    "message": flag["message"],
                })

        return recs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CRAAP Test 信息源可信度评估工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 单条评估
  python source_evaluation.py \\
      --source "https://example.com/paper" \\
      --type journal_article \\
      --currency 5 --relevance 5 --authority 5 --accuracy 5 --purpose 5

  # 批量评估（JSON 输入文件）
  python source_evaluation.py --batch items.json --output reports.json

  # 列出所有预设模板
  python source_evaluation.py --list-templates
        """,
    )

    parser.add_argument("--source", "-s", help="信息源描述（URL/文献标题/声明）")
    parser.add_argument(
        "--type", "-t",
        default="custom",
        choices=[t.value for t in SourceType],
        help="信息源类型（默认: custom）",
    )
    parser.add_argument("--currency", "-c", type=int, help="时效性评分 1-5")
    parser.add_argument("--relevance", "-r", type=int, help="相关性评分 1-5")
    parser.add_argument("--authority", "-a", type=int, help="权威性评分 1-5")
    parser.add_argument("--accuracy", type=int, help="准确性评分 1-5")
    parser.add_argument("--purpose", "-p", type=int, help="目的性评分 1-5")
    parser.add_argument("--notes", "-n", help="评估备注")
    parser.add_argument("--output", "-o", help="输出 JSON 文件路径")
    parser.add_argument(
        "--batch",
        metavar="FILE",
        help="批量评估输入 JSON 文件（每行或数组格式）",
    )
    parser.add_argument(
        "--list-templates",
        action="store_true",
        help="列出所有预设模板并退出",
    )
    return parser


def _parse_batch_file(path: Path) -> list[dict]:
    """解析批量评估输入文件，支持 JSON 数组或 JSON Lines 格式。"""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if content.startswith("["):
        return json.loads(content)
    # JSON Lines
    items = []
    for line in content.splitlines():
        line = line.strip()
        if line:
            items.append(json.loads(line))
    return items


def main():
    # Redirect logger stdout to stderr so JSON output stays clean
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream is sys.stdout:
            handler.stream = sys.stderr

    parser = _build_argparser()
    args = parser.parse_args()

    # 列出模板
    if args.list_templates:
        templates = SourceEvaluator.list_templates()
        print(json.dumps(templates, ensure_ascii=False, indent=2))
        sys.exit(0)

    evaluator = SourceEvaluator()

    # 批量模式
    if args.batch:
        batch_path = Path(args.batch)
        if not batch_path.exists():
            logger.error("Batch file not found: %s", batch_path)
            sys.exit(1)
        items = _parse_batch_file(batch_path)
        reports = evaluator.batch_evaluate(items)
        result = {
            "meta": {
                "batch_size": len(items),
                "evaluated_at": datetime.now().isoformat(timespec="seconds"),
            },
            "reports": reports,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info("Saved batch report to: %s", out_path)
        sys.exit(0)

    # 单条模式
    if not args.source:
        parser.error("--source 为必填项（或使用 --batch/--list-templates）")

    scores = {}
    for dim in ("currency", "relevance", "authority", "accuracy", "purpose"):
        val = getattr(args, dim)
        if val is not None:
            scores[dim] = val

    report = evaluator.evaluate(
        source_desc=args.source,
        source_type=args.type,
        scores=scores,
        notes=args.notes,
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info("Saved report to: %s", out_path)


if __name__ == "__main__":
    main()
