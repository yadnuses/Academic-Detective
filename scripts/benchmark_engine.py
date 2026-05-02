#!/usr/bin/env python3
"""
benchmark_engine.py — 学科基准线数据库核心引擎 v1.0

五层架构：
  Layer 1: 学科维度基线 (discipline_benchmarks)
  Layer 2: 期刊维度基线 (journal_benchmarks)
  Layer 3: 个体研究者基线 (researcher_baseline)
  Layer 4: 异常模式规则 (anomaly_rules)
  Layer 5: 案例-异常关联 (case_anomaly_links)

核心能力：
  1. 偏离度计算（individual / peer_group / global 三种模式）
  2. 稳健统计量（中位数 + IQR + MAD）
  3. 对数正态分布（处理右偏学术指标）
  4. 异常概率与置信区间
  5. 综合异常指数（加权聚合）
  6. 与现有学者档案库（scholar_profile_database.csv）联动

三种比较模式：
  individual   — 与学科基线比较
  peer_group   — 与同群（同年龄段、同职称、同领域）比较
  global       — 全局百分位

使用示例：
    from benchmark_engine import BenchmarkEngine
    engine = BenchmarkEngine("data/benchmark.db")
    result = engine.calculate_anomaly("CASE_001", mode="individual")
    print(result.composite_score, result.risk_level)
"""

from __future__ import annotations

import csv
import json
import math
import os
import sqlite3
import sys
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


# ---------------------------------------------------------------------------
# 常量与配置
# ---------------------------------------------------------------------------

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "benchmark.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "benchmark_schema.sql")
PROFILE_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "scholar_profile_database.csv")

# 学术指标到字段的映射（用于自动从档案库提取）
METRIC_MAP = {
    "h_index": "h_index",
    "avg_papers_per_year": "avg_papers_per_year",
    "total_citations": "total_citations",
    "first_author_ratio": "first_author_ratio",
    "coauthor_count": "coauthor_count",
    "coauthor_concentration": "coauthor_concentration",
    "cross_discipline_count": "cross_discipline_count",
    "funding_hit_rate": "funding_hit_rate",
    "median_review_days": "median_review_days",
    "retraction_count": "retraction_count",
    "median_citations_per_paper": "median_citations_per_paper",
}

# 17维不端特征标签（与 scholar_profile_database.csv 对齐）
FEATURE_TAG_COLS = [
    "feat_data_fabrication", "feat_data_falsification", "feat_image_manipulation",
    "feat_plagiarism", "feat_self_plagiarism", "feat_translation_plagiarism",
    "feat_ghostwriting", "feat_fake_peer_review", "feat_paper_mill",
    "feat_data_trading", "feat_authorship_misconduct", "feat_fund_misconduct",
    "feat_duplicate_publication", "feat_citation_manipulation",
    "feat_ethical_violation", "feat_systemic_fraud", "feat_supervisor_abuse",
]

FEATURE_TAG_WEIGHTS = {
    "feat_systemic_fraud": 2.0,
    "feat_data_fabrication": 1.8,
    "feat_data_falsification": 1.5,
    "feat_image_manipulation": 1.5,
    "feat_paper_mill": 1.5,
    "feat_plagiarism": 1.2,
    "feat_ghostwriting": 1.2,
    "feat_fake_peer_review": 1.5,
    "feat_data_trading": 1.5,
    "feat_authorship_misconduct": 1.0,
    "feat_fund_misconduct": 1.0,
    "feat_duplicate_publication": 0.8,
    "feat_citation_manipulation": 0.8,
    "feat_ethical_violation": 1.0,
    "feat_supervisor_abuse": 1.0,
    "feat_translation_plagiarism": 1.2,
    "feat_self_plagiarism": 0.8,
}

# 学科粗分桶映射：细颗粒 discipline_id → 粗分桶
# HSS = 人文社科, STEM = 理工, MED = 医学
BUCKET_MAP = {
    "COMM_CN_2020_2024": "HSS",
    "CS_CN_2020_2024": "STEM",
    "CHEM_CN_2020_2024": "STEM",
    "MED_CN_2020_2024": "MED",
}

# 预设的10种异常规则（Phase 0 启动包）
DEFAULT_RULES = [
    {
        "rule_id": "A001",
        "rule_name": "Hyper_production",
        "rule_name_zh": "超高产",
        "rule_description": "年均发文量显著高于学科基线，可能暗示论文工厂或数据交易",
        "detection_logic": "avg_papers_per_year > benchmark_median + z_threshold * benchmark_mad",
        "comparison_mode": "individual",
        "threshold_params": json.dumps({"z_threshold": 1.5, "direction": "high"}),
        "distribution_assumption": "lognormal",
        "weight": 1.0,
        "severity_level": 2,
        "applicable_disciplines": json.dumps(["ALL"]),
        "reference_cases": json.dumps(["CASE_001", "CASE_002"]),
    },
    {
        "rule_id": "A002",
        "rule_name": "Citation_anomaly",
        "rule_name_zh": "引用异常",
        "rule_description": "h_index或单篇被引中位数异常低/高，可能暗示引用操纵或质量低下",
        "detection_logic": "h_index < benchmark_median - z_threshold * benchmark_mad OR median_citations_per_paper < benchmark_median - z_threshold * benchmark_mad",
        "comparison_mode": "individual",
        "threshold_params": json.dumps({"z_threshold": 1.5, "direction": "low"}),
        "distribution_assumption": "lognormal",
        "weight": 1.0,
        "severity_level": 2,
        "applicable_disciplines": json.dumps(["ALL"]),
        "reference_cases": json.dumps(["CASE_002", "CASE_003"]),
    },
    {
        "rule_id": "A003",
        "rule_name": "Coauthor_concentration",
        "rule_name_zh": "合作者高度集中",
        "rule_description": "top3合作者发文占比过高，可能暗示导师霸凌、挂名或系统性造假",
        "detection_logic": "coauthor_concentration > threshold",
        "comparison_mode": "individual",
        "threshold_params": json.dumps({"threshold": 0.70, "direction": "high"}),
        "distribution_assumption": "normal",
        "weight": 1.2,
        "severity_level": 3,
        "applicable_disciplines": json.dumps(["ALL"]),
        "reference_cases": json.dumps(["CASE_001", "CASE_004"]),
    },
    {
        "rule_id": "A004",
        "rule_name": "Fast_publication",
        "rule_name_zh": "异常快速发表",
        "rule_description": "投稿到发表的中位数审稿天数显著低于期刊基线，可能暗示假同行评审",
        "detection_logic": "median_review_days < benchmark_median - z_threshold * benchmark_mad AND suspicious_fast_track_count >= 2",
        "comparison_mode": "individual",
        "threshold_params": json.dumps({"z_threshold": 1.5, "min_count": 2}),
        "distribution_assumption": "normal",
        "weight": 1.5,
        "severity_level": 3,
        "applicable_disciplines": json.dumps(["ALL"]),
        "reference_cases": json.dumps(["CASE_005"]),
    },
    {
        "rule_id": "A005",
        "rule_name": "Retraction_history",
        "rule_name_zh": "撤稿历史",
        "rule_description": "存在撤稿记录或关注表达式，直接触发",
        "detection_logic": "retraction_count > 0 OR expression_of_concern_count > 0",
        "comparison_mode": "global",
        "threshold_params": json.dumps({"threshold": 0}),
        "distribution_assumption": "normal",
        "weight": 2.0,
        "severity_level": 3,
        "applicable_disciplines": json.dumps(["ALL"]),
        "reference_cases": json.dumps(["CASE_006", "CASE_007"]),
    },
    {
        "rule_id": "A006",
        "rule_name": "Cross_discipline_overreach",
        "rule_name_zh": "跨领域过度延伸",
        "rule_description": "跨学科数量显著高于同群基线，可能暗示挂名或论文工厂",
        "detection_logic": "cross_discipline_count > benchmark_median + z_threshold * benchmark_mad",
        "comparison_mode": "peer_group",
        "threshold_params": json.dumps({"z_threshold": 1.5}),
        "distribution_assumption": "normal",
        "weight": 0.8,
        "severity_level": 2,
        "applicable_disciplines": json.dumps(["ALL"]),
        "reference_cases": json.dumps(["CASE_008"]),
    },
    {
        "rule_id": "A007",
        "rule_name": "First_author_discrepancy",
        "rule_name_zh": "一作比例异常",
        "rule_description": "一作比例异常低（导师霸凌、挂名）或异常高（孤立研究者）",
        "detection_logic": "first_author_ratio < low_threshold OR first_author_ratio > high_threshold",
        "comparison_mode": "individual",
        "threshold_params": json.dumps({"low_threshold": 0.10, "high_threshold": 0.90}),
        "distribution_assumption": "normal",
        "weight": 0.8,
        "severity_level": 1,
        "applicable_disciplines": json.dumps(["ALL"]),
        "reference_cases": json.dumps([]),
    },
    {
        "rule_id": "A008",
        "rule_name": "Funding_anomaly",
        "rule_name_zh": "基金命中率异常",
        "rule_description": "基金命中率显著高于学科基线，可能暗示数据交易或关系网络",
        "detection_logic": "funding_hit_rate > benchmark_median + z_threshold * benchmark_mad",
        "comparison_mode": "individual",
        "threshold_params": json.dumps({"z_threshold": 1.5}),
        "distribution_assumption": "normal",
        "weight": 0.8,
        "severity_level": 2,
        "applicable_disciplines": json.dumps(["ALL"]),
        "reference_cases": json.dumps([]),
    },
    {
        "rule_id": "A009",
        "rule_name": "Self_citation_spike",
        "rule_name_zh": "自引率突增",
        "rule_description": "自引率显著高于学科基线，可能暗示引用操纵",
        "detection_logic": "self_citation_rate > benchmark_median + z_threshold * benchmark_mad",
        "comparison_mode": "individual",
        "threshold_params": json.dumps({"z_threshold": 1.5}),
        "distribution_assumption": "normal",
        "weight": 0.8,
        "severity_level": 2,
        "applicable_disciplines": json.dumps(["ALL"]),
        "reference_cases": json.dumps([]),
    },
    {
        "rule_id": "A010",
        "rule_name": "Journal_tier_mismatch",
        "rule_name_zh": "期刊层级错配",
        "rule_description": "长期发表期刊层级与机构层级不匹配，可能暗示买卖论文",
        "detection_logic": "avg_journal_tier > institution_tier + 2",
        "comparison_mode": "peer_group",
        "threshold_params": json.dumps({"tier_gap": 2}),
        "distribution_assumption": "normal",
        "weight": 0.6,
        "severity_level": 1,
        "applicable_disciplines": json.dumps(["ALL"]),
        "reference_cases": json.dumps([]),
    },
]


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class DeviationResult:
    """单次偏离度计算结果"""
    metric: str
    observed_value: float
    benchmark_value: float
    deviation_score: float          # Z-score or standardized deviation
    deviation_direction: str        # "high" / "low"
    deviation_magnitude: float      # |observed - benchmark|
    anomaly_probability: float      # P(anomaly | observed)
    ci_lower: float
    ci_upper: float
    distribution: str               # normal / lognormal / t
    comparison_mode: str            # individual / peer_group / global
    peer_group_size: int = 0


@dataclass
class RuleTrigger:
    """单条规则的触发结果"""
    rule_id: str
    rule_name: str
    rule_name_zh: str
    severity_level: int
    weight: float
    deviation: DeviationResult
    triggered: bool = False
    raw_score: float = 0.0          # 原始异常分
    weighted_score: float = 0.0     # 加权后异常分


@dataclass
class CompositeResult:
    """综合异常指数结果"""
    case_id: str
    name: str
    discipline_id: str
    calculation_date: str

    individual_score: float
    peer_group_score: float
    global_score: float
    composite_score: float
    score_formula: str

    confidence_level: float
    ci_lower: float
    ci_upper: float

    percentile_in_discipline: float
    risk_level: str                 # low / medium / high / critical

    triggered_rules: List[RuleTrigger] = field(default_factory=list)
    active_feature_count: int = 0

    # 17维特征标签贡献
    feature_tag_score: float = 0.0          # 特征标签对综合异常的独立贡献分
    feature_tag_detail: List[Dict] = field(default_factory=list)  # 每个激活特征的详情
    misconduct_pattern_similarity: float = 0.0  # 与已知不端案例的模式相似度
    closest_misconduct_case: str = ""        # 最接近的不端案例名
    bucket_id: str = ""                      # 学科粗分桶 (HSS/STEM/MED)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["triggered_rules"] = [
            {
                "rule_id": r.rule_id,
                "rule_name": r.rule_name,
                "rule_name_zh": r.rule_name_zh,
                "severity_level": r.severity_level,
                "weight": r.weight,
                "triggered": r.triggered,
                "raw_score": round(r.raw_score, 4),
                "weighted_score": round(r.weighted_score, 4),
                "deviation": {
                    "metric": r.deviation.metric,
                    "observed_value": round(r.deviation.observed_value, 4),
                    "benchmark_value": round(r.deviation.benchmark_value, 4),
                    "deviation_score": round(r.deviation.deviation_score, 4),
                    "deviation_direction": r.deviation.deviation_direction,
                    "anomaly_probability": round(r.deviation.anomaly_probability, 4),
                },
            }
            for r in self.triggered_rules
        ]
        d["feature_tag_detail"] = self.feature_tag_detail
        return d


# ---------------------------------------------------------------------------
# 统计工具
# ---------------------------------------------------------------------------

class RobustStats:
    """稳健统计工具箱"""

    @staticmethod
    def median(values: List[float]) -> float:
        if not values:
            return 0.0
        s = sorted(v for v in values if v is not None and not math.isnan(v))
        n = len(s)
        if n == 0:
            return 0.0
        if n % 2 == 1:
            return s[n // 2]
        return (s[n // 2 - 1] + s[n // 2]) / 2.0

    @staticmethod
    def iqr(values: List[float]) -> float:
        if not values:
            return 0.0
        s = sorted(v for v in values if v is not None and not math.isnan(v))
        n = len(s)
        if n < 2:
            return 0.0
        q1 = s[n // 4] if n >= 4 else s[0]
        q3 = s[(3 * n) // 4] if n >= 4 else s[-1]
        return q3 - q1

    @staticmethod
    def mad(values: List[float]) -> float:
        """Median Absolute Deviation"""
        m = RobustStats.median(values)
        abs_devs = [abs(v - m) for v in values if v is not None and not math.isnan(v)]
        return RobustStats.median(abs_devs)

    @staticmethod
    def mean(values: List[float]) -> float:
        clean = [v for v in values if v is not None and not math.isnan(v)]
        return sum(clean) / len(clean) if clean else 0.0

    @staticmethod
    def std(values: List[float]) -> float:
        clean = [v for v in values if v is not None and not math.isnan(v)]
        if len(clean) < 2:
            return 0.0
        m = sum(clean) / len(clean)
        var = sum((x - m) ** 2 for x in clean) / (len(clean) - 1)
        return math.sqrt(var)

    @staticmethod
    def log_mean(values: List[float]) -> float:
        """对数均值（用于对数正态分布参数估计）"""
        clean = [v for v in values if v is not None and v > 0 and not math.isnan(v)]
        if not clean:
            return 0.0
        return sum(math.log(v) for v in clean) / len(clean)

    @staticmethod
    def log_std(values: List[float]) -> float:
        """对数标准差"""
        clean = [v for v in values if v is not None and v > 0 and not math.isnan(v)]
        if len(clean) < 2:
            return 0.0
        lm = RobustStats.log_mean(values)
        var = sum((math.log(v) - lm) ** 2 for v in clean) / (len(clean) - 1)
        return math.sqrt(var)


class DistributionModel:
    """统计分布模型：正态 / 对数正态 / t分布"""

    @staticmethod
    def normal_pdf(x: float, mu: float, sigma: float) -> float:
        if sigma <= 0:
            return 0.0
        return (1.0 / (sigma * math.sqrt(2 * math.pi))) * math.exp(-0.5 * ((x - mu) / sigma) ** 2)

    @staticmethod
    def normal_cdf_approx(z: float) -> float:
        """标准正态CDF的近似（Hastings近似）"""
        if z < -6:
            return 0.0
        if z > 6:
            return 1.0
        # 使用 error function
        return 0.5 * (1 + math.erf(z / math.sqrt(2)))

    @staticmethod
    def z_score(value: float, median: float, mad: float) -> float:
        """基于MAD的稳健Z-score"""
        if mad == 0:
            return 0.0
        # MAD 到标准差的转换系数：1.4826
        return (value - median) / (mad * 1.4826)

    @staticmethod
    def lognormal_z_score(value: float, log_mean: float, log_std: float) -> float:
        """对数正态分布的Z-score"""
        if value <= 0 or log_std <= 0:
            return 0.0
        return (math.log(value) - log_mean) / log_std

    @staticmethod
    def anomaly_probability(z: float, two_sided: bool = True) -> float:
        """
        计算异常概率。
        two_sided=True: 双侧检验（偏离基线，无论高低）
        two_sided=False: 单侧检验（仅偏离方向）
        """
        if two_sided:
            return 2 * (1 - DistributionModel.normal_cdf_approx(abs(z)))
        return 1 - DistributionModel.normal_cdf_approx(z)

    @staticmethod
    def confidence_interval(median: float, mad: float, n: int, confidence: float = 0.95) -> Tuple[float, float]:
        """
        基于稳健统计量的置信区间。
        使用正态近似（大样本）或 t 分布（小样本）。
        """
        if n < 2 or mad <= 0:
            return median, median
        sigma = mad * 1.4826
        if n >= 30:
            z_val = 1.96 if confidence >= 0.95 else 1.645
            margin = z_val * (sigma / math.sqrt(n))
        else:
            # 小样本使用 t 分布近似（简化：自由度=n-1, t_0.025 ≈ 2.0 for df<30）
            t_val = 2.0 if n < 10 else 2.042 if n < 15 else 2.009 if n < 20 else 1.96
            margin = t_val * (sigma / math.sqrt(n))
        return median - margin, median + margin


# ---------------------------------------------------------------------------
# 核心引擎
# ---------------------------------------------------------------------------

class BenchmarkEngine:
    """
    学科基准线数据库核心引擎。

    使用示例：
        engine = BenchmarkEngine()
        engine.init_schema()
        engine.seed_default_rules()
        result = engine.calculate_anomaly("CASE_001", mode="individual")
        print(result.to_dict())
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.stats = RobustStats()
        self.dist = DistributionModel()
        self._profile_db_cache: Optional[List[Dict]] = None

    # ------------------------------------------------------------------
    # 数据库初始化
    # ------------------------------------------------------------------

    def init_schema(self) -> None:
        """从 SQL 文件初始化数据库 Schema"""
        if not os.path.exists(SCHEMA_PATH):
            raise FileNotFoundError(f"Schema file not found: {SCHEMA_PATH}")
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            sql = f.read()
        self.conn.executescript(sql)
        self.conn.commit()
        print(f"Schema initialized: {self.db_path}")

    def seed_default_rules(self) -> None:
        """插入预设的 10 条异常检测规则"""
        cursor = self.conn.cursor()
        for rule in DEFAULT_RULES:
            cursor.execute(
                """
                INSERT OR REPLACE INTO anomaly_rules (
                    rule_id, rule_name, rule_name_zh, rule_description,
                    detection_logic, comparison_mode, threshold_params,
                    distribution_assumption, weight, severity_level,
                    applicable_disciplines, reference_cases,
                    created_date, version, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), '1.0', 1)
                """,
                (
                    rule["rule_id"], rule["rule_name"], rule.get("rule_name_zh", ""),
                    rule["rule_description"], rule["detection_logic"],
                    rule["comparison_mode"], rule["threshold_params"],
                    rule["distribution_assumption"], rule["weight"],
                    rule["severity_level"], rule["applicable_disciplines"],
                    rule["reference_cases"],
                ),
            )
        self.conn.commit()
        print(f"Seeded {len(DEFAULT_RULES)} default anomaly rules")

    def close(self) -> None:
        if self.conn:
            self.conn.close()

    # ------------------------------------------------------------------
    # 数据导入（从现有学者档案库）
    # ------------------------------------------------------------------

    def import_from_profile_db(self, csv_path: Optional[str] = None) -> int:
        """
        从 scholar_profile_database.csv（合并版，含17维特征标签+定量指标）导入个体研究者基线数据。
        支持完整字段映射，包括万能服务器回填的数值字段。
        返回导入的记录数。
        """
        csv_path = csv_path or PROFILE_DB_PATH
        if not os.path.exists(csv_path):
            print(f"Profile DB not found: {csv_path}")
            return 0

        count = 0
        cursor = self.conn.cursor()
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 处理可能的 BOM 前缀
                first_key = list(row.keys())[0] if row else ""
                if first_key.startswith("\ufeff"):
                    row = {k.lstrip("\ufeff"): v for k, v in row.items()}

                researcher_id = row.get("researcher_id", "") or row.get("profile_id", "")
                if not researcher_id:
                    continue

                def _float(val: str) -> Optional[float]:
                    try:
                        return float(val) if val and val.strip() else None
                    except ValueError:
                        return None

                def _int(val: str) -> Optional[int]:
                    try:
                        return int(float(val)) if val and val.strip() else None
                    except ValueError:
                        return None

                investigation_status = row.get("investigation_status", "normal")
                is_misconduct = 1 if investigation_status == "confirmed_misconduct" else 0

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO researcher_baseline (
                        researcher_id, profile_id, name, institution, department,
                        current_title, career_stage, discipline_id,
                        h_index, total_citations,
                        avg_papers_per_year, first_author_ratio, corresponding_author_ratio,
                        coauthor_count, coauthor_concentration, median_coauthor_per_paper, solo_author_ratio,
                        cross_discipline_count, primary_discipline, secondary_disciplines,
                        funding_hit_rate, total_grants, total_grant_amount,
                        median_review_days, min_review_days, max_review_days, suspicious_fast_track_count,
                        retraction_count, expression_of_concern_count,
                        median_citations_per_paper, highly_cited_paper_count, self_citation_rate,
                        is_confirmed_misconduct, investigation_status, data_path, notes, career_tier, update_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """,
                    (
                        researcher_id, row.get("profile_id", researcher_id),
                        row.get("name", ""), row.get("institution", ""),
                        row.get("department", ""), row.get("current_title", ""),
                        row.get("career_stage", ""), row.get("discipline_id", ""),
                        _float(row.get("h_index", "")), _int(row.get("total_citations", "")),
                        _float(row.get("avg_papers_per_year", "")), _float(row.get("first_author_ratio", "")), _float(row.get("corresponding_author_ratio", "")),
                        _int(row.get("coauthor_count", "")), _float(row.get("coauthor_concentration", "")), _float(row.get("median_coauthor_per_paper", "")), _float(row.get("solo_author_ratio", "")),
                        _int(row.get("cross_discipline_count", "")), row.get("primary_discipline", ""), row.get("secondary_disciplines", ""),
                        _float(row.get("funding_hit_rate", "")), _int(row.get("total_grants", "")), _float(row.get("total_grant_amount", "")),
                        _float(row.get("median_review_days", "")), _int(row.get("min_review_days", "")), _int(row.get("max_review_days", "")), _int(row.get("suspicious_fast_track_count", "")),
                        _int(row.get("retraction_count", "")), _int(row.get("expression_of_concern_count", "")),
                        _float(row.get("median_citations_per_paper", "")), _int(row.get("highly_cited_paper_count", "")), _float(row.get("self_citation_rate", "")),
                        is_misconduct, investigation_status,
                        row.get("data_path", ""), row.get("notes", ""), row.get("career_tier", "normal"),
                    ),
                )
                count += 1

        self.conn.commit()
        print(f"Imported {count} researchers from {csv_path}")
        return count

    def import_discipline_baselines(self, csv_path: str) -> int:
        """从CSV导入学科基线数据（万能服务器提供的大样本基线）"""
        if not os.path.exists(csv_path):
            print(f"Discipline baseline CSV not found: {csv_path}")
            return 0
        count = 0
        cursor = self.conn.cursor()
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                first_key = list(row.keys())[0] if row else ""
                if first_key.startswith("\ufeff"):
                    row = {k.lstrip("\ufeff"): v for k, v in row.items()}
                
                def _float(val):
                    try:
                        return float(val) if val and val.strip() else None
                    except ValueError:
                        return None
                
                def _int(val):
                    try:
                        return int(float(val)) if val and val.strip() else None
                    except ValueError:
                        return None
                
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO discipline_benchmarks (
                        discipline_id, discipline_name, discipline_code, region,
                        period_start, period_end,
                        avg_papers_per_year, median_papers_per_year, std_papers_per_year, iqr_papers_per_year, mad_papers_per_year,
                        median_h_index, mean_h_index, std_h_index,
                        median_citations_per_paper, mean_citations_per_paper,
                        median_coauthor_count, avg_coauthor_count, coauthor_concentration_threshold,
                        median_cross_discipline_count, cross_discipline_rate,
                        avg_funding_rate, median_funding_rate,
                        median_review_days, mean_review_days, std_review_days,
                        retraction_rate, sample_size, data_source, update_date, notes,
                        p95_papers_per_year, p99_papers_per_year, p95_h_index, p99_h_index
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("discipline_id", ""), row.get("discipline_name", ""), row.get("discipline_code", ""), row.get("region", ""),
                        row.get("period_start", ""), row.get("period_end", ""),
                        _float(row.get("avg_papers_per_year", "")), _float(row.get("median_papers_per_year", "")), _float(row.get("std_papers_per_year", "")), _float(row.get("iqr_papers_per_year", "")), _float(row.get("mad_papers_per_year", "")),
                        _float(row.get("median_h_index", "")), _float(row.get("mean_h_index", "")), _float(row.get("std_h_index", "")),
                        _float(row.get("median_citations_per_paper", "")), _float(row.get("mean_citations_per_paper", "")),
                        _float(row.get("median_coauthor_count", "")), _float(row.get("avg_coauthor_count", "")), _float(row.get("coauthor_concentration_threshold", "")),
                        _float(row.get("median_cross_discipline_count", "")), _float(row.get("cross_discipline_rate", "")),
                        _float(row.get("avg_funding_rate", "")), _float(row.get("median_funding_rate", "")),
                        _float(row.get("median_review_days", "")), _float(row.get("mean_review_days", "")), _float(row.get("std_review_days", "")),
                        _float(row.get("retraction_rate", "")), _int(row.get("sample_size", "")), row.get("data_source", ""), row.get("update_date", ""), row.get("notes", ""),
                        _float(row.get("p95_papers_per_year", "")), _float(row.get("p99_papers_per_year", "")), _float(row.get("p95_h_index", "")), _float(row.get("p99_h_index", "")),
                    ),
                )
                count += 1
        self.conn.commit()
        print(f"Imported {count} discipline baselines from {csv_path}")
        return count

    def import_anomaly_rules(self, csv_path: str) -> int:
        """从CSV导入异常规则（覆盖默认规则）"""
        if not os.path.exists(csv_path):
            print(f"Anomaly rules CSV not found: {csv_path}")
            return 0
        count = 0
        cursor = self.conn.cursor()
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                first_key = list(row.keys())[0] if row else ""
                if first_key.startswith("\ufeff"):
                    row = {k.lstrip("\ufeff"): v for k, v in row.items()}
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO anomaly_rules (
                        rule_id, rule_name, rule_name_zh, rule_description,
                        detection_logic, comparison_mode, threshold_params,
                        distribution_assumption, confidence_level, weight, severity_level,
                        applicable_disciplines, excluded_disciplines, reference_cases,
                        false_positive_rate, created_date, updated_date, version, is_active, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("rule_id", ""), row.get("rule_name", ""), row.get("rule_name_zh", ""), row.get("rule_description", ""),
                        row.get("detection_logic", ""), row.get("comparison_mode", ""), row.get("threshold_params", ""),
                        row.get("distribution_assumption", ""), row.get("confidence_level", "0.95"), row.get("weight", "1.0"), row.get("severity_level", "2"),
                        row.get("applicable_disciplines", ""), row.get("excluded_disciplines", ""), row.get("reference_cases", ""),
                        row.get("false_positive_rate", ""), row.get("created_date", ""), row.get("updated_date", ""), row.get("version", "1.0"), row.get("is_active", "1"), row.get("notes", ""),
                    ),
                )
                count += 1
        self.conn.commit()
        print(f"Imported {count} anomaly rules from {csv_path}")
        return count

    # ------------------------------------------------------------------
    # 基线管理
    # ------------------------------------------------------------------

    def create_discipline_baseline(
        self,
        discipline_id: str,
        discipline_name: str,
        researcher_values: Dict[str, List[float]],
        region: str = "GLOBAL",
    ) -> None:
        """
        从一组研究者数据创建学科基线。
        researcher_values: {"avg_papers_per_year": [1.2, 3.4, ...], "h_index": [...], ...}
        """
        cursor = self.conn.cursor()

        def _calc(metric: str) -> Dict[str, float]:
            vals = researcher_values.get(metric, [])
            if not vals:
                return {"median": 0.0, "mean": 0.0, "std": 0.0, "iqr": 0.0, "mad": 0.0}
            return {
                "median": self.stats.median(vals),
                "mean": self.stats.mean(vals),
                "std": self.stats.std(vals),
                "iqr": self.stats.iqr(vals),
                "mad": self.stats.mad(vals),
            }

        papers = _calc("avg_papers_per_year")
        hidx = _calc("h_index")
        cites = _calc("median_citations_per_paper")
        coauth = _calc("coauthor_count")
        cross = _calc("cross_discipline_count")

        cursor.execute(
            """
            INSERT OR REPLACE INTO discipline_benchmarks (
                discipline_id, discipline_name, region,
                avg_papers_per_year, median_papers_per_year, std_papers_per_year, iqr_papers_per_year, mad_papers_per_year,
                median_h_index, mean_h_index, std_h_index,
                median_citations_per_paper, mean_citations_per_paper,
                median_coauthor_count, avg_coauthor_count,
                median_cross_discipline_count,
                sample_size, update_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                discipline_id, discipline_name, region,
                papers["mean"], papers["median"], papers["std"], papers["iqr"], papers["mad"],
                hidx["median"], hidx["mean"], hidx["std"],
                cites["median"], cites["mean"],
                coauth["median"], coauth["mean"],
                cross["median"],
                sum(1 for v in researcher_values.values() if v),
            ),
        )
        self.conn.commit()
        print(f"Created discipline baseline: {discipline_id} ({discipline_name})")

    # ------------------------------------------------------------------
    # 核心计算：偏离度
    # ------------------------------------------------------------------

    def calculate_deviation(
        self,
        researcher_id: str,
        metric: str,
        comparison_mode: str = "individual",
        peer_group_id: Optional[str] = None,
        confidence: float = 0.95,
    ) -> Optional[DeviationResult]:
        """
        计算某个研究者在某个指标上的偏离度。

        Args:
            researcher_id: 研究者ID
            metric: 指标名（如 "avg_papers_per_year", "h_index"）
            comparison_mode: individual / peer_group / global
            peer_group_id: 同群ID（comparison_mode=peer_group 时使用）
            confidence: 置信水平

        Returns:
            DeviationResult 或 None（如果数据不足）
        """
        cursor = self.conn.cursor()

        # 1. 获取研究者观测值
        cursor.execute(
            f"SELECT {metric}, discipline_id FROM researcher_baseline WHERE researcher_id = ?",
            (researcher_id,),
        )
        row = cursor.fetchone()
        if not row or row[0] is None:
            return None
        observed = float(row[0])
        discipline_id = row[1] or "UNKNOWN"

        # 2. 获取基线
        benchmark_median = 0.0
        benchmark_mad = 0.0
        benchmark_mean = 0.0
        benchmark_std = 0.0
        distribution = "normal"
        peer_group_size = 0
        fallback_to_global = False

        if comparison_mode == "individual":
            # 与学科基线比较
            # 指标到学科基线表的列名映射
            METRIC_TO_BASELINE_COL = {
                "avg_papers_per_year": ("median_papers_per_year", "mad_papers_per_year", "avg_papers_per_year", "std_papers_per_year"),
                "h_index": ("median_h_index", None, "mean_h_index", "std_h_index"),
                "total_citations": ("median_citations_per_paper", None, "mean_citations_per_paper", None),
                "median_citations_per_paper": ("median_citations_per_paper", None, "mean_citations_per_paper", None),
                "coauthor_count": ("median_coauthor_count", None, "avg_coauthor_count", None),
                "coauthor_concentration": ("coauthor_concentration_threshold", None, None, None),
                "cross_discipline_count": ("median_cross_discipline_count", None, None, None),
                "funding_hit_rate": ("median_funding_rate", None, "avg_funding_rate", None),
                "median_review_days": ("median_review_days", None, "mean_review_days", "std_review_days"),
                "retraction_count": ("retraction_rate", None, None, None),
            }
            cols = METRIC_TO_BASELINE_COL.get(metric)
            if not cols:
                return None
            med_col, mad_col, mean_col, std_col = cols
            select_cols = [c for c in [med_col, mad_col, mean_col, std_col] if c]
            if not select_cols:
                return None
            sql = f"SELECT {', '.join(select_cols)} FROM discipline_benchmarks WHERE discipline_id = ?"
            cursor.execute(sql, (discipline_id,))
            bench = cursor.fetchone()
            if not bench:
                # 学科基线不存在，尝试全局基线
                cursor.execute(sql, ("GLOBAL",))
                bench = cursor.fetchone()
                if not bench:
                    return None
            # 使用 select_cols 索引映射，避免 mad_col=None 时 mean_col 被错位读取为 mad
            benchmark_median = bench[select_cols.index(med_col)] if med_col in select_cols else 0.0
            benchmark_mad = bench[select_cols.index(mad_col)] if mad_col in select_cols else 0.0
            benchmark_mean = bench[select_cols.index(mean_col)] if mean_col in select_cols else 0.0
            benchmark_std = bench[select_cols.index(std_col)] if std_col in select_cols else 0.0
            # 基线有效性检查：如果基线中位数为0且标准差也为0，说明基线数据缺失，跳过
            if benchmark_median == 0 and benchmark_std == 0 and benchmark_mad == 0:
                return None
            # MAD退化防护：当 MAD=0 时 fallback 到 std / IQR
            if benchmark_mad == 0:
                if benchmark_std > 0:
                    benchmark_mad = benchmark_std / 1.4826  # 近似转换
                else:
                    # 尝试从数据库获取 IQR
                    iqr_col = sql.replace("median_", "iqr_").replace(", mad_", ", iqr_")
                    if "iqr_" in iqr_col and iqr_col != sql:
                        try:
                            cursor.execute(iqr_col, (discipline_id,))
                            iqr_row = cursor.fetchone()
                            if iqr_row and iqr_row[0] and iqr_row[0] > 0:
                                benchmark_mad = iqr_row[0] / 1.349  # IQR 到 MAD 的近似转换
                        except sqlite3.OperationalError:
                            pass  # IQR列不存在，忽略
                        if benchmark_mad == 0:
                            # 当基线缺少MAD/STD时，使用中位数的30%作为替代MAD
                            benchmark_mad = max(benchmark_median * 0.3, 0.001)

        elif comparison_mode == "peer_group":
            # 与同群比较
            if not peer_group_id:
                # 自动构建同群：同领域 + 同职业阶段
                cursor.execute(
                    "SELECT career_stage FROM researcher_baseline WHERE researcher_id = ?",
                    (researcher_id,),
                )
                career = cursor.fetchone()
                career_stage = career[0] if career else None
                cursor.execute(
                    """
                    SELECT {metric} FROM researcher_baseline
                    WHERE discipline_id = ? AND career_stage = ? AND researcher_id != ?
                    AND {metric} IS NOT NULL
                    """.format(metric=metric),
                    (discipline_id, career_stage, researcher_id),
                )
            else:
                cursor.execute(
                    """
                    SELECT {metric} FROM researcher_baseline
                    WHERE researcher_id IN (
                        SELECT json_each.value FROM peer_groups, json_each(member_ids)
                        WHERE group_id = ?
                    ) AND {metric} IS NOT NULL
                    """.format(metric=metric),
                    (peer_group_id,),
                )
            peers = [r[0] for r in cursor.fetchall()]
            peer_group_size = len(peers)
            if peer_group_size < 5:
                return None  # 同群样本不足
            benchmark_median = self.stats.median(peers)
            benchmark_mad = self.stats.mad(peers)
            benchmark_mean = self.stats.mean(peers)
            benchmark_std = self.stats.std(peers)

        elif comparison_mode == "global":
            # 全局比较
            cursor.execute(
                f"SELECT {metric} FROM researcher_baseline WHERE {metric} IS NOT NULL",
            )
            all_vals = [r[0] for r in cursor.fetchall()]
            peer_group_size = len(all_vals)
            if peer_group_size < 10:
                return None
            benchmark_median = self.stats.median(all_vals)
            benchmark_mad = self.stats.mad(all_vals)
            benchmark_mean = self.stats.mean(all_vals)
            benchmark_std = self.stats.std(all_vals)

        # 3. 确定分布假设
        # 右偏指标使用对数正态
        LOGNORMAL_METRICS = {"avg_papers_per_year", "h_index", "total_citations", "median_citations_per_paper"}
        if metric in LOGNORMAL_METRICS:
            distribution = "lognormal"

        # 4. 计算偏离度
        if distribution == "lognormal" and observed > 0 and benchmark_median > 0:
            # 对数正态参数估计（从样本）
            if comparison_mode == "individual":
                cursor.execute(
                    f"SELECT {metric} FROM researcher_baseline WHERE discipline_id = ? AND {metric} > 0",
                    (discipline_id,),
                )
                sample = [float(r[0]) for r in cursor.fetchall()]
                # 学科样本不足时 fallback 到全局
                if len(sample) < 3:
                    cursor.execute(
                        f"SELECT {metric} FROM researcher_baseline WHERE {metric} > 0",
                    )
                    sample = [float(r[0]) for r in cursor.fetchall()]
            elif comparison_mode == "peer_group":
                sample = peers  # type: ignore
            else:
                sample = all_vals  # type: ignore

            log_mu = self.stats.log_mean(sample)
            log_sigma = self.stats.log_std(sample)
            # log_std 退化防护：样本不足或标准差为0时 fallback 到正态Z-score
            if log_sigma <= 0 or len(sample) < 3:
                z = self.dist.z_score(observed, benchmark_median, benchmark_mad)
            else:
                z = self.dist.lognormal_z_score(observed, log_mu, log_sigma)
        else:
            z = self.dist.z_score(observed, benchmark_median, benchmark_mad)

        # 5. 计算异常概率（双侧）
        prob = self.dist.anomaly_probability(z, two_sided=True)
        direction = "high" if observed > benchmark_median else "low"

        # 6. 计算置信区间
        ci_low, ci_high = self.dist.confidence_interval(
            benchmark_median, benchmark_mad, peer_group_size or 30, confidence
        )

        return DeviationResult(
            metric=metric,
            observed_value=observed,
            benchmark_value=benchmark_median,
            deviation_score=round(z, 4),
            deviation_direction=direction,
            deviation_magnitude=round(abs(observed - benchmark_median), 4),
            anomaly_probability=round(prob, 4),
            ci_lower=round(ci_low, 4),
            ci_upper=round(ci_high, 4),
            distribution=distribution,
            comparison_mode=comparison_mode,
            peer_group_size=peer_group_size,
        )

    # ------------------------------------------------------------------
    # 核心计算：综合异常指数
    # ------------------------------------------------------------------

    def calculate_anomaly(
        self,
        researcher_id: str,
        mode: str = "individual",
        peer_group_id: Optional[str] = None,
        confidence: float = 0.95,
        custom_weights: Optional[Dict[str, float]] = None,
    ) -> Optional[CompositeResult]:
        """
        计算某个研究者的综合异常指数。

        Args:
            researcher_id: 研究者ID
            mode: 计算模式（individual / peer_group / global）
            peer_group_id: 同群ID
            confidence: 置信水平
            custom_weights: 自定义规则权重 {rule_id: weight}

        Returns:
            CompositeResult 或 None
        """
        cursor = self.conn.cursor()

        # 获取研究者基本信息
        cursor.execute(
            "SELECT name, discipline_id FROM researcher_baseline WHERE researcher_id = ?",
            (researcher_id,),
        )
        info = cursor.fetchone()
        if not info:
            print(f"Researcher not found: {researcher_id}")
            return None
        name, discipline_id = info[0], info[1] or "UNKNOWN"

        # 获取所有活跃的异常规则
        cursor.execute(
            "SELECT * FROM anomaly_rules WHERE is_active = 1 ORDER BY severity_level DESC, weight DESC",
        )
        rules = cursor.fetchall()

        triggered_rules: List[RuleTrigger] = []
        individual_scores = []
        peer_scores = []
        global_scores = []
        active_count = 0

        for rule in rules:
            rule_id = rule["rule_id"]
            rule_name = rule["rule_name"]
            rule_name_zh = rule["rule_name_zh"] or ""
            severity = rule["severity_level"]
            weight = rule["weight"]
            comparison_mode = rule["comparison_mode"]
            detection_logic = rule["detection_logic"]
            distribution = rule["distribution_assumption"] or "normal"

            # 应用自定义权重
            if custom_weights and rule_id in custom_weights:
                weight = custom_weights[rule_id]

            # career_tier 过滤：检测逻辑中包含 career_tier 条件的规则
            if "career_tier" in detection_logic:
                cursor.execute(
                    "SELECT career_tier FROM researcher_baseline WHERE researcher_id = ?",
                    (researcher_id,),
                )
                ct_row = cursor.fetchone()
                career_tier = ct_row[0] if ct_row else "normal"
                # 如果检测逻辑要求排除 top 学者，且当前学者是 top，则跳过
                if "career_tier != 'top'" in detection_logic and career_tier == "top":
                    continue

            # 解析阈值参数
            try:
                threshold_params = json.loads(rule["threshold_params"] or "{}")
            except json.JSONDecodeError:
                threshold_params = {}

            # 确定需要计算的指标
            # 简化：从 detection_logic 中提取指标名
            metric = self._extract_metric_from_logic(detection_logic)
            if not metric:
                continue

            # 计算偏离度
            deviation = self.calculate_deviation(
                researcher_id, metric, comparison_mode, peer_group_id, confidence
            )
            if not deviation:
                continue

            # 判断是否触发
            triggered = self._evaluate_trigger(deviation, threshold_params, detection_logic)

            # 计算原始异常分
            if triggered:
                # A005特殊处理：使用观测值而非z-score，避免小数基线导致分数爆炸
                if rule_id == "A005":
                    raw_score = deviation.observed_value * severity * 0.1  # 缩放因子0.1
                else:
                    raw_score = abs(deviation.deviation_score) * severity
                weighted_score = raw_score * weight
                active_count += 1
            else:
                raw_score = 0.0
                weighted_score = 0.0

            rt = RuleTrigger(
                rule_id=rule_id,
                rule_name=rule_name,
                rule_name_zh=rule_name_zh,
                severity_level=severity,
                weight=weight,
                deviation=deviation,
                triggered=triggered,
                raw_score=raw_score,
                weighted_score=weighted_score,
            )
            triggered_rules.append(rt)

            if triggered:
                if comparison_mode == "individual":
                    individual_scores.append(weighted_score)
                elif comparison_mode == "peer_group":
                    peer_scores.append(weighted_score)
                elif comparison_mode == "global":
                    global_scores.append(weighted_score)

        # 计算各模式得分
        individual_score = sum(individual_scores) / max(len(individual_scores), 1) if individual_scores else 0.0
        peer_group_score = sum(peer_scores) / max(len(peer_scores), 1) if peer_scores else 0.0
        global_score = sum(global_scores) / max(len(global_scores), 1) if global_scores else 0.0

        # 加权综合
        # 默认公式：individual 50% + peer_group 30% + global 20%
        formula = "individual*0.5 + peer_group*0.3 + global*0.2"
        raw_composite = individual_score * 0.5 + peer_group_score * 0.3 + global_score * 0.2

        # —— 17维特征标签贡献 ——
        feature_tag_score = 0.0
        feature_tag_detail = []

        # 从 researcher_baseline 的 notes 字段或直接查 CSV 获取特征标签
        # 优先：通过同名的 researcher_id 在同一个表里加 feat_* 列？
        # 当前 schema 的 researcher_baseline 没有 feat_* 列。
        # 通过直接查询 CSV 来加载特征
        feature_tag_score, feature_tag_detail = self._calculate_feature_tag_score(researcher_id, name)

        # 把特征标签分按 0.7 倍率与 composite 合并（保留数值异常的主导地位）
        raw_composite = raw_composite + feature_tag_score * 0.7

        # —— 学科分桶 ——
        bucket_id = BUCKET_MAP.get(discipline_id, "HSS")  # 默认 HSS

        # —— 模式相似度 ——
        misconduct_pattern_similarity = 0.0
        closest_misconduct_case = ""
        if feature_tag_detail:
            sim_result = self._calculate_misconduct_pattern_similarity(researcher_id, name)
            if sim_result:
                misconduct_pattern_similarity = sim_result["similarity"]
                closest_misconduct_case = sim_result["closest_case"]

        # 对数压缩标准化：将原始分数映射到 0-20 区间
        # 避免极端值压缩其他案例的区分度，同时保持高分区区分度
        composite = 5.0 * math.log1p(raw_composite) if raw_composite > 0 else 0.0

        # 计算学科内百分位
        percentile = self._calculate_percentile(composite, discipline_id)

        # 风险等级
        risk_level = self._risk_level_from_score(composite)

        # 置信区间（基于触发的规则数）
        n_rules = len([r for r in triggered_rules if r.triggered])
        ci_low, ci_high = self.dist.confidence_interval(composite, composite * 0.3, max(n_rules, 2), confidence)

        result = CompositeResult(
            case_id=researcher_id,
            name=name,
            discipline_id=discipline_id,
            calculation_date=sqlite3.datetime.datetime.now().isoformat(),
            individual_score=round(individual_score, 4),
            peer_group_score=round(peer_group_score, 4),
            global_score=round(global_score, 4),
            composite_score=round(composite, 4),
            score_formula=formula,
            confidence_level=confidence,
            ci_lower=round(max(ci_low, 0), 4),
            ci_upper=round(ci_high, 4),
            percentile_in_discipline=round(percentile, 4),
            risk_level=risk_level,
            triggered_rules=triggered_rules,
            active_feature_count=active_count,
            feature_tag_score=round(feature_tag_score, 4),
            feature_tag_detail=feature_tag_detail,
            misconduct_pattern_similarity=round(misconduct_pattern_similarity, 4),
            closest_misconduct_case=closest_misconduct_case,
            bucket_id=bucket_id,
        )

        # 持久化到数据库
        self._save_composite_result(result)
        self._save_case_anomaly_links(result)

        return result

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _extract_metric_from_logic(self, logic: str) -> Optional[str]:
        """从检测逻辑字符串中提取指标名（简化实现）"""
        KNOWN_METRICS = [
            "avg_papers_per_year", "h_index", "total_citations",
            "median_citations_per_paper", "coauthor_concentration",
            "coauthor_count", "cross_discipline_count",
            "median_review_days", "retraction_count",
            "first_author_ratio", "funding_hit_rate",
            "self_citation_rate", "expression_of_concern_count",
        ]
        for m in KNOWN_METRICS:
            if m in logic:
                return m
        return None

    def _calculate_feature_tag_score(self, researcher_id: str, name: str) -> tuple:
        """
        从 CSV 加载17维特征标签，计算特征标签贡献分和详情。
        返回 (feature_tag_score, feature_tag_detail_list)
        """
        # 尝试从 profile DB CSV 加载特征
        csv_path = PROFILE_DB_PATH
        detail = []
        total_score = 0.0

        try:
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rid = row.get("researcher_id", "") or row.get("profile_id", "")
                    if rid == researcher_id or row.get("name", "") == name:
                        for col in FEATURE_TAG_COLS:
                            val = row.get(col, "0")
                            if val == "1":
                                weight = FEATURE_TAG_WEIGHTS.get(col, 1.0)
                                total_score += weight
                                detail.append({
                                    "tag": col,
                                    "weight": weight,
                                    "description": col.replace("feat_", ""),
                                })
                        break
        except FileNotFoundError:
            pass
        except Exception:
            pass

        return total_score, detail

    def _calculate_misconduct_pattern_similarity(self, researcher_id: str, name: str) -> Optional[dict]:
        """
        将17维特征与已知不端案例比对，计算模式相似度。
        使用 Jaccard 相似度 + Cosine 相似度的加权组合（与 scholar_profile_matcher_v2 一致）。
        """
        csv_path = PROFILE_DB_PATH
        target_vec = None
        misconduct_profiles = []

        try:
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rid = row.get("researcher_id", "") or row.get("profile_id", "")
                    status = row.get("investigation_status", "")
                    vec = [1 if row.get(c, "0") == "1" else 0 for c in FEATURE_TAG_COLS]

                    if rid == researcher_id or row.get("name", "") == name:
                        target_vec = vec
                    elif status == "confirmed_misconduct":
                        misconduct_profiles.append((row, vec))
        except (FileNotFoundError, Exception):
            return None

        if target_vec is None or not misconduct_profiles:
            return None

        target_active = sum(target_vec)
        if target_active == 0:
            return None

        best_sim = 0.0
        best_name = ""
        for p_row, p_vec in misconduct_profiles:
            # Jaccard
            intersection = sum(1 for a, b in zip(target_vec, p_vec) if a == 1 and b == 1)
            union = sum(1 for a, b in zip(target_vec, p_vec) if a == 1 or b == 1)
            jaccard = intersection / union if union > 0 else 0.0

            # Cosine
            dot = sum(a * b for a, b in zip(target_vec, p_vec))
            norm_t = math.sqrt(sum(a * a for a in target_vec))
            norm_p = math.sqrt(sum(b * b for b in p_vec))
            cosine = dot / (norm_t * norm_p) if norm_t > 0 and norm_p > 0 else 0.0

            sim = jaccard * 0.7 + cosine * 0.3
            if sim > best_sim:
                best_sim = sim
                best_name = p_row.get("name", "")

        return {
            "similarity": best_sim,
            "closest_case": best_name,
        }

    def _evaluate_trigger(
        self,
        deviation: DeviationResult,
        threshold_params: Dict,
        detection_logic: str,
    ) -> bool:
        """根据偏离度和阈值判断是否触发异常规则"""
        z = deviation.deviation_score
        direction = deviation.deviation_direction
        obs = deviation.observed_value

        # 解析 z_threshold
        z_threshold = threshold_params.get("z_threshold", 2.0)
        threshold = threshold_params.get("threshold", None)

        # 1. 直接阈值比较（如 coauthor_concentration > threshold）
        if threshold is not None and "> threshold" in detection_logic:
            return obs > threshold
        if threshold is not None and "< threshold" in detection_logic:
            return obs < threshold

        # 2. 撤稿历史、快速发表等直接触发规则（布尔条件，不依赖z-score）
        if "retraction_count > 0" in detection_logic or "expression_of_concern_count > 0" in detection_logic:
            return obs > 0
        if "suspicious_fast_track_count > 0" in detection_logic:
            return obs > 0

        # 3. 如果检测逻辑包含 ">" 且 direction 是 high（与基线比较）
        # 注意：排除 >= 的误匹配
        clean_logic = detection_logic.replace(">=", "##GE##")
        if ">" in clean_logic and "benchmark" in clean_logic:
            return z > z_threshold and direction == "high"
        # 4. 如果检测逻辑包含 "<" 且 direction 是 low（与基线比较）
        # 注意：排除 <= 的误匹配
        clean_logic = detection_logic.replace("<=", "##LE##")
        if "<" in clean_logic and "benchmark" in clean_logic:
            return z < -z_threshold and direction == "low"
        # 5. 如果检测逻辑包含 "OR"（双向阈值，如 low < obs < high）
        if "OR" in detection_logic.upper():
            low_t = threshold_params.get("low_threshold")
            high_t = threshold_params.get("high_threshold")
            if low_t is not None and high_t is not None:
                return obs < low_t or obs > high_t
            return abs(z) > z_threshold
        # 6. 方向性检查：如果规则有明确方向，但当前偏离方向不匹配，则不触发
        clean_logic = detection_logic.replace(">=", "##GE##").replace("<=", "##LE##")
        if ">" in clean_logic and direction != "high":
            return False
        if "<" in clean_logic and direction != "low":
            return False
        # 7. 默认：双侧检验（仅用于无明确方向的规则）
        return abs(z) > z_threshold

    def _calculate_percentile(self, composite_score: float, discipline_id: str) -> float:
        """计算在学科内的百分位"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT composite_score FROM composite_scores cs "
            "JOIN researcher_baseline rb ON cs.case_id = rb.researcher_id "
            "WHERE rb.discipline_id = ? AND cs.composite_score IS NOT NULL",
            (discipline_id,),
        )
        scores = [r[0] for r in cursor.fetchall()]
        if not scores:
            return 0.5
        scores.append(composite_score)
        scores.sort()
        idx = scores.index(composite_score)
        return idx / (len(scores) - 1) if len(scores) > 1 else 0.5

    def _risk_level_from_score(self, score: float) -> str:
        """根据综合异常分判定风险等级"""
        # 基于实际案例的经验阈值
        # 正常学者: 0.0 ~ 2.0
        # 可疑: 2.0 ~ 5.0
        # 高风险: 5.0 ~ 10.0
        # 极高风险: > 10.0
        if score < 2.0:
            return "low"
        if score < 5.0:
            return "medium"
        if score < 10.0:
            return "high"
        return "critical"

    def _save_composite_result(self, result: CompositeResult) -> None:
        """保存综合异常指数到数据库"""
        cursor = self.conn.cursor()
        triggered_json = json.dumps([
            {"rule_id": r.rule_id, "prob": r.deviation.anomaly_probability}
            for r in result.triggered_rules if r.triggered
        ])
        cursor.execute(
            """
            INSERT OR REPLACE INTO composite_scores (
                score_id, case_id, calculation_date,
                individual_score, peer_group_score, global_score,
                composite_score, score_formula,
                confidence_level, confidence_interval_lower, confidence_interval_upper,
                percentile_in_discipline, risk_level,
                triggered_rules, active_feature_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"SCORE_{result.case_id}", result.case_id, result.calculation_date,
                result.individual_score, result.peer_group_score, result.global_score,
                result.composite_score, result.score_formula,
                result.confidence_level, result.ci_lower, result.ci_upper,
                result.percentile_in_discipline, result.risk_level,
                triggered_json, result.active_feature_count,
            ),
        )
        self.conn.commit()

    def _save_case_anomaly_links(self, result: CompositeResult) -> None:
        """保存案例-异常关联到 Layer 5"""
        cursor = self.conn.cursor()
        for rt in result.triggered_rules:
            if not rt.triggered:
                continue
            link_id = f"LINK_{result.case_id}_{rt.rule_id}"
            cursor.execute(
                """
                INSERT OR REPLACE INTO case_anomaly_links (
                    link_id, case_id, rule_id,
                    observed_value, benchmark_value,
                    deviation_score, deviation_direction, deviation_magnitude,
                    anomaly_probability,
                    confidence_interval_lower, confidence_interval_upper, confidence_level,
                    comparison_mode, peer_group_size,
                    calculation_date, algorithm_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    link_id, result.case_id, rt.rule_id,
                    rt.deviation.observed_value, rt.deviation.benchmark_value,
                    rt.deviation.deviation_score, rt.deviation.deviation_direction,
                    rt.deviation.deviation_magnitude,
                    rt.deviation.anomaly_probability,
                    rt.deviation.ci_lower, rt.deviation.ci_upper,
                    result.confidence_level,
                    rt.deviation.comparison_mode, rt.deviation.peer_group_size,
                    result.calculation_date, "benchmark_engine_v1.0",
                ),
            )
        self.conn.commit()

    # ------------------------------------------------------------------
    # 批量计算
    # ------------------------------------------------------------------

    def batch_calculate(
        self,
        researcher_ids: Optional[List[str]] = None,
        mode: str = "individual",
        confidence: float = 0.95,
    ) -> List[CompositeResult]:
        """
        批量计算异常指数。
        如果不提供 researcher_ids，则计算数据库中所有研究者。
        """
        cursor = self.conn.cursor()
        if researcher_ids:
            results = []
            for rid in researcher_ids:
                r = self.calculate_anomaly(rid, mode=mode, confidence=confidence)
                if r:
                    results.append(r)
            return results

        cursor.execute("SELECT researcher_id FROM researcher_baseline")
        all_ids = [r[0] for r in cursor.fetchall()]
        return self.batch_calculate(all_ids, mode, confidence)

    # ------------------------------------------------------------------
    # 报告生成
    # ------------------------------------------------------------------

    def generate_report(self, result: CompositeResult) -> str:
        """生成人类可读的异常指数报告"""
        lines = []
        lines.append("=" * 60)
        lines.append(f"学术异常指数报告")
        lines.append(f"学者：{result.name} ({result.case_id})")
        lines.append(f"计算时间：{result.calculation_date}")
        lines.append(f"比较模式：{result.score_formula}")
        lines.append("=" * 60)
        lines.append("")

        lines.append(f"【综合异常指数】{result.composite_score:.2f}")
        lines.append(f"  风险等级：{result.risk_level.upper()}")
        lines.append(f"  学科分桶：{result.bucket_id}")
        lines.append(f"  学科百分位：{result.percentile_in_discipline * 100:.1f}%")
        lines.append(f"  置信区间（{result.confidence_level * 100:.0f}%）：[{result.ci_lower:.2f}, {result.ci_upper:.2f}]")
        lines.append("")

        lines.append(f"【分项得分】")
        lines.append(f"  学科偏离度（individual）：{result.individual_score:.2f}")
        lines.append(f"  同群偏离度（peer_group）：{result.peer_group_score:.2f}")
        lines.append(f"  全局偏离度（global）：    {result.global_score:.2f}")
        lines.append(f"  特征标签贡献：{result.feature_tag_score:.2f}")
        if result.misconduct_pattern_similarity > 0:
            lines.append(f"  与不端案例模式相似度：{result.misconduct_pattern_similarity:.2%}")
            lines.append(f"  最接近的不端案例：{result.closest_misconduct_case}")
        lines.append("")

        lines.append(f"【触发规则】{result.active_feature_count} 条")
        for rt in result.triggered_rules:
            if not rt.triggered:
                continue
            d = rt.deviation
            lines.append(f"  · [{rt.rule_id}] {rt.rule_name_zh or rt.rule_name} (严重度{rt.severity_level})")
            lines.append(f"    观测值：{d.observed_value:.2f} | 基线：{d.benchmark_value:.2f}")
            lines.append(f"    偏离度：{d.deviation_score:+.2f}σ | 异常概率：{d.anomaly_probability * 100:.1f}%")
            lines.append(f"    方向：{d.deviation_direction} | 分布假设：{d.distribution}")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)

    def export_results_to_json(self, results: List[CompositeResult], path: str) -> None:
        """导出批量结果到 JSON"""
        data = [r.to_dict() for r in results]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Exported {len(results)} results to {path}")

    # ------------------------------------------------------------------
    # 查询与统计
    # ------------------------------------------------------------------

    def get_top_anomalies(self, discipline_id: Optional[str] = None, top_n: int = 10) -> List[Dict]:
        """获取异常指数最高的案例"""
        cursor = self.conn.cursor()
        if discipline_id:
            cursor.execute(
                """
                SELECT * FROM v_anomaly_overview
                WHERE discipline_id = ?
                ORDER BY composite_score DESC
                LIMIT ?
                """,
                (discipline_id, top_n),
            )
        else:
            cursor.execute(
                "SELECT * FROM v_anomaly_overview ORDER BY composite_score DESC LIMIT ?",
                (top_n,),
            )
        return [dict(r) for r in cursor.fetchall()]

    def get_rule_stats(self) -> List[Dict]:
        """获取规则触发统计"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM v_rule_trigger_stats")
        return [dict(r) for r in cursor.fetchall()]


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="学科基准线数据库引擎")
    parser.add_argument("--init", action="store_true", help="初始化数据库 Schema")
    parser.add_argument("--import-profiles", action="store_true", help="从学者档案库导入研究者基线")
    parser.add_argument("--calc", type=str, help="计算指定研究者的异常指数（researcher_id）")
    parser.add_argument("--batch", action="store_true", help="批量计算所有研究者")
    parser.add_argument("--mode", type=str, default="individual", choices=["individual", "peer_group", "global"])
    parser.add_argument("--top", type=int, default=10, help="显示Top N异常案例")
    parser.add_argument("--report", action="store_true", help="生成报告")
    parser.add_argument("--export", type=str, help="导出结果到JSON路径")
    parser.add_argument("--db", type=str, help="数据库路径")
    args = parser.parse_args()

    engine = BenchmarkEngine(args.db)

    if args.init:
        engine.init_schema()
        engine.seed_default_rules()
        print("Database initialized successfully.")

    if args.import_profiles:
        engine.import_from_profile_db()

    if args.calc:
        result = engine.calculate_anomaly(args.calc, mode=args.mode)
        if result:
            if args.report:
                print(engine.generate_report(result))
            else:
                print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(f"Failed to calculate anomaly for {args.calc}")

    if args.batch:
        results = engine.batch_calculate(mode=args.mode)
        print(f"Calculated anomaly scores for {len(results)} researchers")
        if args.export:
            engine.export_results_to_json(results, args.export)
        # 打印Top N
        for r in sorted(results, key=lambda x: x.composite_score, reverse=True)[:args.top]:
            status = ""
            print(f"  {r.case_id}: {r.name} = {r.composite_score:.2f} ({r.risk_level}) {status}")

    if not any([args.init, args.import_profiles, args.calc, args.batch]):
        parser.print_help()

    engine.close()


if __name__ == "__main__":
    main()
