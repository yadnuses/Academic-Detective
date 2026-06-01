#!/usr/bin/env python3
"""
data_integrity_checker.py

Detect potential data fabrication in experimental datasets using statistical
fingerprinting methods adapted from the "Geng methodology" (耿同学方法论).

Three independent detection methods:
    1. Tail-digit distribution analysis — last digits should be ~uniform (0-9)
    2. Decimal-place consistency — repeated decimal patterns suggest manual formatting
    3. Exact-value duplication — identical values in independent experiments are rare

Each method produces independent signals; convergence across all three is strong
evidence of fabrication.

Flag patterns:
    tail_digit_anomaly, decimal_consistency_anomaly, data_duplication_anomaly

Usage:
    python data_integrity_checker.py --input paper_data.xlsx --output ./data/integrity_audit.json
    python data_integrity_checker.py --input paper_data.csv --output ./data/integrity_audit.json --verbose
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.utils import get_logger, save_json

logger = get_logger("data_integrity_checker")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class IntegrityConfig:
    """Detection thresholds and parameters."""
    significance_threshold: float = 0.05   # p-value cutoff for chi-square
    effect_size_threshold: float = 0.3     # Cramer's V threshold
    min_duplicate_count: int = 3           # exact-value repeat count to flag
    decimal_places: list = field(default_factory=lambda: [2, 3])
    min_sample_size: int = 10              # skip columns with fewer values


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class IntegrityFinding:
    """A single detection finding."""
    sheet: str
    column: str
    method: str          # tail_digit | decimal_consistency | data_duplication
    severity: str        # HIGH | MEDIUM | LOW
    description: str
    confidence: float
    p_value: Optional[float] = None
    effect_size: Optional[float] = None
    statistics: Optional[dict] = None


# ---------------------------------------------------------------------------
# Method 1: Tail-digit distribution analysis
# ---------------------------------------------------------------------------


def _check_tail_distribution(
    sheet: str, col: str, values: np.ndarray, cfg: IntegrityConfig
) -> Optional[IntegrityFinding]:
    """Last digit of each value should be approximately uniform 0-9."""
    tails = []
    for v in values:
        s = f"{v:.6f}"
        dec_part = s.split(".")[-1]
        tails.append(int(dec_part[-1]) if dec_part else 0)

    observed = pd.Series(tails).value_counts().sort_index()
    expected_freq = pd.Series([len(tails) / 10] * 10, index=range(10))

    # Align indices
    contingency = pd.DataFrame({"observed": observed, "expected": expected_freq}).fillna(0).T
    chi2, p_value = sp_stats.chi2_contingency(contingency)[0:2]

    n = len(tails)
    k = 10
    v = np.sqrt(chi2 / (n * (k - 1)))  # Cramer's V

    if p_value >= cfg.significance_threshold:
        return None

    tail_counts = pd.Series(tails).value_counts()
    max_tail = int(tail_counts.idxmax())
    max_count = int(tail_counts.max())
    expected_count = n / 10
    deviation_ratio = max_count / expected_count

    if v > 0.5 or deviation_ratio > 3:
        severity = "HIGH"
    elif v > cfg.effect_size_threshold:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    return IntegrityFinding(
        sheet=sheet, column=col, method="tail_digit",
        severity=severity, confidence=min(0.95, 0.5 + v),
        description=f"尾数分布异常: 尾数{max_tail}出现{max_count}次(期望{expected_count:.1f}), "
                    f"偏差比{deviation_ratio:.1f}x, p={p_value:.4f}",
        p_value=p_value, effect_size=v,
        statistics={
            "chi2": round(chi2, 2), "p_value": round(p_value, 4),
            "cramers_v": round(v, 3), "sample_size": n,
            "max_tail": max_tail, "max_count": max_count,
            "expected_count": round(expected_count, 1),
            "deviation_ratio": round(deviation_ratio, 1),
            "tail_distribution": {int(k): int(v) for k, v in tail_counts.items()},
        },
    )


# ---------------------------------------------------------------------------
# Method 2: Decimal-place consistency
# ---------------------------------------------------------------------------


def _check_decimal_consistency(
    sheet: str, col: str, values: np.ndarray, decimal_place: int, cfg: IntegrityConfig
) -> Optional[IntegrityFinding]:
    """Repeated decimal suffixes suggest manual data construction."""
    decimals = []
    for v in values:
        s = f"{v:.6f}"
        dec_part = s.split(".")[-1]
        if len(dec_part) >= decimal_place:
            decimals.append(dec_part[:decimal_place])

    if not decimals:
        return None

    dec_series = pd.Series(decimals)
    value_counts = dec_series.value_counts()
    duplicate_groups = int((value_counts >= 2).sum())
    max_count = int(value_counts.max())
    duplicate_rate = duplicate_groups / len(value_counts) if len(value_counts) > 0 else 0

    is_anomaly = duplicate_groups >= 5 or max_count >= 3 or duplicate_rate > 0.15
    if not is_anomaly:
        return None

    if max_count >= 3:
        severity = "HIGH"
    elif duplicate_groups >= 5:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    return IntegrityFinding(
        sheet=sheet, column=col, method="decimal_consistency",
        severity=severity, confidence=min(0.9, 0.4 + duplicate_rate * 2),
        description=f"小数点后{decimal_place}位重复: {duplicate_groups}组重复, "
                    f"最高{max_count}次, 重复率{duplicate_rate:.1%}",
        statistics={
            "decimal_place": decimal_place, "total_values": len(values),
            "duplicate_groups": duplicate_groups, "max_repeat": max_count,
            "duplicate_rate": f"{duplicate_rate:.1%}",
            "top5": {str(k): int(v) for k, v in value_counts.head(5).items()},
        },
    )


# ---------------------------------------------------------------------------
# Method 3: Exact-value duplication
# ---------------------------------------------------------------------------


def _check_data_duplication(
    sheet: str, col: str, values: np.ndarray, cfg: IntegrityConfig
) -> Optional[IntegrityFinding]:
    """Exact repeated values in independent experiments are suspicious."""
    value_counts = pd.Series(values).value_counts()
    duplicate_values = int((value_counts >= 2).sum())
    max_count = int(value_counts.max())

    is_anomaly = duplicate_values >= 5 or max_count >= cfg.min_duplicate_count
    if not is_anomaly:
        return None

    if max_count >= 4:
        severity = "HIGH"
    elif max_count >= 3:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    return IntegrityFinding(
        sheet=sheet, column=col, method="data_duplication",
        severity=severity, confidence=min(0.95, 0.3 + max_count * 0.15),
        description=f"数据重复: {duplicate_values}个重复值, 最高出现{max_count}次",
        statistics={
            "duplicate_value_count": duplicate_values,
            "max_repeat": max_count,
            "top5": {str(k): int(v) for k, v in value_counts.head(5).items()},
        },
    )


# ---------------------------------------------------------------------------
# Risk scoring
# ---------------------------------------------------------------------------


def _calculate_risk_score(findings: list[IntegrityFinding]) -> tuple[int, str]:
    """Compute 0-100 risk score from findings. Returns (score, level)."""
    score = 0
    methods = set(f.method for f in findings)

    # Base: +3 per finding
    score += len(findings) * 3

    # Single method with >=3 findings: +10
    for m in methods:
        count = sum(1 for f in findings if f.method == m)
        if count >= 3:
            score += 10

    # Multiple methods: +5 per additional method
    if len(methods) >= 2:
        score += 5 * (len(methods) - 1)

    # High-severity finding: +5 each
    high_count = sum(1 for f in findings if f.severity == "HIGH")
    score += high_count * 5

    score = min(score, 100)

    if score >= 81:
        level = "实锤造假"
    elif score >= 61:
        level = "中度异常"
    elif score >= 31:
        level = "轻度异常"
    else:
        level = "正常"

    return score, level


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def check_file(file_path: str, cfg: Optional[IntegrityConfig] = None) -> dict:
    """
    Run all three integrity checks on an Excel or CSV file.

    Returns a dict with keys: risk_score, risk_level, findings, summary.
    """
    cfg = cfg or IntegrityConfig()
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # Load data
    if path.suffix in (".xlsx", ".xls"):
        sheets = pd.read_excel(path, sheet_name=None)
    elif path.suffix == ".csv":
        sheets = {"data": pd.read_csv(path)}
    else:
        raise ValueError(f"Unsupported format: {path.suffix}")

    findings: list[IntegrityFinding] = []

    for sheet_name, df in sheets.items():
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        for col in numeric_cols:
            values = df[col].dropna().values
            if len(values) < cfg.min_sample_size:
                continue

            logger.debug("Checking %s / %s (%d values)", sheet_name, col, len(values))

            f1 = _check_tail_distribution(sheet_name, col, values, cfg)
            if f1:
                findings.append(f1)

            for dp in cfg.decimal_places:
                f2 = _check_decimal_consistency(sheet_name, col, values, dp, cfg)
                if f2:
                    findings.append(f2)

            f3 = _check_data_duplication(sheet_name, col, values, cfg)
            if f3:
                findings.append(f3)

    risk_score, risk_level = _calculate_risk_score(findings)

    methods_involved = list(set(f.method for f in findings))
    columns_involved = list(set(f"{f.sheet}/{f.column}" for f in findings))

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "findings": [asdict(f) for f in findings],
        "summary": {
            "total_findings": len(findings),
            "methods_involved": methods_involved,
            "columns_involved": columns_involved,
            "high_severity": sum(1 for f in findings if f.severity == "HIGH"),
            "medium_severity": sum(1 for f in findings if f.severity == "MEDIUM"),
            "low_severity": sum(1 for f in findings if f.severity == "LOW"),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Detect potential data fabrication via statistical fingerprinting"
    )
    p.add_argument("--input", type=Path, required=True, help="Excel (.xlsx) or CSV file")
    p.add_argument("--output", type=Path, default=Path("./data/integrity_audit.json"),
                   help="Output JSON path")
    p.add_argument("--significance", type=float, default=0.05,
                   help="p-value threshold (default 0.05)")
    p.add_argument("--min-dup", type=int, default=3,
                   help="Min exact-value repeat count to flag (default 3)")
    p.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return p


def main():
    args = build_parser().parse_args()
    if args.verbose:
        logger.setLevel(10)

    cfg = IntegrityConfig(
        significance_threshold=args.significance,
        min_duplicate_count=args.min_dup,
    )

    result = check_file(str(args.input), cfg)

    # Wrap in standard signal format compatible with deep_evidence pipeline
    output = {
        "meta": {
            "script": "data_integrity_checker",
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "input_file": str(args.input),
            "risk_score": result["risk_score"],
            "risk_level": result["risk_level"],
        },
        "signals": [
            {
                "type": f["method"],
                "description": f["description"],
                "confidence": f["confidence"],
                "source": "data_integrity_checker",
                "evidence": f["statistics"] or {},
            }
            for f in result["findings"]
        ],
        "details": result,
    }

    save_json(output, args.output)
    logger.info("Saved integrity audit to %s", args.output)

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"Data Integrity Checker — Summary")
    print(f"{'=' * 60}")
    print(f"Input:          {args.input}")
    print(f"Risk score:     {result['risk_score']}/100 ({result['risk_level']})")
    print(f"Findings:       {result['summary']['total_findings']}")
    print(f"  HIGH:         {result['summary']['high_severity']}")
    print(f"  MEDIUM:       {result['summary']['medium_severity']}")
    print(f"  LOW:          {result['summary']['low_severity']}")
    print(f"Methods:        {', '.join(result['summary']['methods_involved']) or 'none'}")
    print(f"Columns:        {len(result['summary']['columns_involved'])}")
    print(f"Output:         {args.output}")


if __name__ == "__main__":
    main()
