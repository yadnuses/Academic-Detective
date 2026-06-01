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
    p_cutoff: float = 0.05                 # p-value cutoff for chi-square
    effect_floor: float = 0.3              # minimum effect size to report
    repeat_floor: int = 3                  # exact-value repeat count to flag
    decimal_depths: list = field(default_factory=lambda: [2, 3])
    min_rows: int = 10                     # skip columns with fewer values


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


def _detect_precision(values: np.ndarray) -> int:
    """Detect the actual decimal precision of a numeric array.

    Returns the most common number of significant decimal places (0 = integers).
    """
    precisions = []
    for v in values[:200]:  # sample for speed
        s = f"{v:.10f}".rstrip("0")
        dec_part = s.split(".")[-1]
        precisions.append(len(dec_part) if dec_part else 0)
    if not precisions:
        return 0
    # Use the mode (most common precision)
    counts = pd.Series(precisions).value_counts()
    return int(counts.index[0])


def _check_tail_distribution(
    sheet: str, col: str, values: np.ndarray, cfg: IntegrityConfig
) -> Optional[IntegrityFinding]:
    """Last digit of each value should be approximately uniform 0-9."""
    precision = _detect_precision(values)
    if precision == 0:
        return None  # integers have no meaningful tail digit

    tails = []
    for v in values:
        s = f"{v:.{precision}f}"
        dec_part = s.split(".")[-1]
        tails.append(int(dec_part[-1]) if dec_part else 0)

    n = len(tails)
    k = 10
    # Build observed counts for digits 0-9
    observed_counts = np.zeros(k)
    for t in tails:
        observed_counts[t] += 1
    expected_counts = np.full(k, n / k)

    # Goodness-of-fit chi-square test (correct for single-variable uniformity)
    chi2, p_value = sp_stats.chisquare(observed_counts, f_exp=expected_counts)

    # For 1-d goodness-of-fit, effect size = sqrt(chi2 / n)
    v_effect = np.sqrt(chi2 / n)

    if p_value >= cfg.p_cutoff:
        return None

    tail_counts = pd.Series(tails).value_counts()
    max_tail = int(tail_counts.idxmax())
    max_count = int(tail_counts.max())
    expected_count = n / k
    deviation_ratio = max_count / expected_count

    if v_effect > 0.5 or deviation_ratio > 3:
        severity = "HIGH"
    elif v_effect > cfg.effect_floor:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    return IntegrityFinding(
        sheet=sheet, column=col, method="tail_digit",
        severity=severity, confidence=min(0.95, 0.5 + v_effect),
        description=f"尾数分布异常: 尾数{max_tail}出现{max_count}次(期望{expected_count:.1f}), "
                    f"偏差比{deviation_ratio:.1f}x, p={p_value:.4f}",
        p_value=p_value, effect_size=v_effect,
        statistics={
            "chi2": round(chi2, 2), "p_value": round(p_value, 4),
            "effect_size": round(v_effect, 3), "sample_size": n,
            "max_tail": max_tail, "max_count": max_count,
            "expected_count": round(expected_count, 1),
            "deviation_ratio": round(deviation_ratio, 1),
            "tail_distribution": {int(k): int(v) for k, v in tail_counts.items()},
        },
    )


# ---------------------------------------------------------------------------
# Method 2: Decimal-place consistency
# ---------------------------------------------------------------------------


def _expected_duplicate_rate(n: int, possible_values: int) -> float:
    """Birthday-problem expected duplicate group rate for n draws from possible_values slots."""
    if possible_values <= 0 or n <= 1:
        return 0.0
    # Expected number of slots with >=2 hits: possible_values * (1 - ((pv-1)/pv)^n - n/pv * ((pv-1)/pv)^(n-1))
    # Simplified approximation for large possible_values:
    # E[collisions] ≈ n^2 / (2 * possible_values)
    expected_collisions = (n * (n - 1)) / (2 * possible_values)
    # Convert to rate: how many slots have duplicates vs total unique slots
    expected_unique = possible_values * (1 - (1 - 1 / possible_values) ** n)
    if expected_unique == 0:
        return 0.0
    expected_dup_slots = min(expected_collisions, expected_unique)
    return expected_dup_slots / expected_unique


def _check_decimal_consistency(
    sheet: str, col: str, values: np.ndarray, decimal_place: int, cfg: IntegrityConfig
) -> Optional[IntegrityFinding]:
    """Repeated decimal suffixes suggest manual data construction."""
    precision = _detect_precision(values)
    if precision < decimal_place:
        return None  # data doesn't actually have this many decimal places

    decimals = []
    for v in values:
        s = f"{v:.{precision}f}"
        dec_part = s.split(".")[-1]
        if len(dec_part) >= decimal_place:
            decimals.append(dec_part[:decimal_place])

    if not decimals:
        return None

    n = len(decimals)
    possible_values = 10 ** decimal_place  # e.g. 100 for 2-digit, 1000 for 3-digit
    expected_rate = _expected_duplicate_rate(n, possible_values)

    dec_series = pd.Series(decimals)
    value_counts = dec_series.value_counts()
    duplicate_groups = int((value_counts >= 2).sum())
    max_count = int(value_counts.max())
    unique_count = len(value_counts)
    observed_rate = duplicate_groups / unique_count if unique_count > 0 else 0

    # Use deviation ratio from expected baseline instead of absolute threshold
    # Only flag when observed EXCEEDS expected (ratio > 1 means more repetition than random)
    if expected_rate > 0:
        deviation_ratio = observed_rate / expected_rate
    else:
        deviation_ratio = observed_rate * 100  # no expected duplicates → any is suspicious

    # Expected count per bin: n / possible_values
    # max_count is suspicious only if it greatly exceeds what birthday problem predicts
    # Simulation shows: for 100 draws from 100 bins, P(max>=4)=87%, P(max>=5)=30%, P(max>=6)=5%
    # So we need max_count_ratio > 5 to reach ~95% confidence
    expected_per_bin = n / possible_values
    max_count_ratio = max_count / max(expected_per_bin, 1)

    # deviation_ratio < 1 means LESS repetition than random → not suspicious
    # max_count_ratio must exceed 5x expected to be noteworthy (≈95th percentile)
    is_anomaly = (deviation_ratio > 2.5 and observed_rate > expected_rate) or max_count_ratio > 5
    if not is_anomaly:
        return None

    if max_count_ratio > 8 or deviation_ratio > 5:
        severity = "HIGH"
    elif max_count_ratio > 6 or deviation_ratio > 3:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    return IntegrityFinding(
        sheet=sheet, column=col, method="decimal_consistency",
        severity=severity, confidence=min(0.9, 0.4 + min(deviation_ratio / 10, 0.5)),
        description=f"小数点后{decimal_place}位重复: {duplicate_groups}组重复, "
                    f"最高{max_count}次, 偏离期望{deviation_ratio:.1f}x "
                    f"(期望重复率{expected_rate:.1%}, 实际{observed_rate:.1%})",
        statistics={
            "decimal_place": decimal_place, "total_values": n,
            "duplicate_groups": duplicate_groups, "max_repeat": max_count,
            "observed_rate": f"{observed_rate:.1%}",
            "expected_rate": f"{expected_rate:.1%}",
            "deviation_ratio": round(deviation_ratio, 1),
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

    is_anomaly = duplicate_values >= 5 or max_count >= cfg.repeat_floor
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
    """Compute 0-100 risk score from findings. Returns (score, level).

    Key insight: multiple methods flagging the SAME column is much stronger
    evidence than methods flagging different columns independently.
    """
    if not findings:
        return 0, "low"

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

    # --- Cross-method convergence on same column (strongest signal) ---
    from collections import defaultdict
    col_methods = defaultdict(set)
    for f in findings:
        key = f"{f.sheet}/{f.column}"
        col_methods[key].add(f.method)

    for col_key, col_m in col_methods.items():
        if len(col_m) >= 3:
            score += 20  # all three methods converge on one column
        elif len(col_m) == 2:
            score += 10  # two methods converge

    score = min(score, 100)

    # Align with project-wide L1-L5 confidence system and benchmark_engine risk levels
    if score >= 75:
        level = "critical"   # L5: 多方法交叉验证，数据造假证据确凿
    elif score >= 50:
        level = "high"       # L4: 强信号，高度可能存在数据造假
    elif score >= 25:
        level = "medium"     # L3: 有异常迹象，存在其他解释空间
    else:
        level = "low"        # L2: 微弱信号或正常范围

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
            # Skip pure integer columns (sample IDs, years, counts)
            if df[col].dropna().apply(lambda x: x == int(x)).all():
                logger.debug("Skipping integer column: %s / %s", sheet_name, col)
                continue
            values = df[col].dropna().values
            if len(values) < cfg.min_rows:
                continue

            logger.debug("Checking %s / %s (%d values)", sheet_name, col, len(values))

            # Method 1: Exact-value duplication (simplest, most direct signal)
            f1 = _check_data_duplication(sheet_name, col, values, cfg)
            if f1:
                findings.append(f1)

            # Method 2: Tail-digit distribution
            f2 = _check_tail_distribution(sheet_name, col, values, cfg)
            if f2:
                findings.append(f2)

            # Method 3: Decimal-place consistency
            for dp in cfg.decimal_depths:
                f3 = _check_decimal_consistency(sheet_name, col, values, dp, cfg)
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
        p_cutoff=args.significance,
        repeat_floor=args.min_dup,
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
