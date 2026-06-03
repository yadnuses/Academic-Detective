#!/usr/bin/env python3
"""
data_integrity_checker.py

Detect potential data fabrication in experimental datasets using statistical
fingerprinting. Six independent detection methods:

    1. Tail-digit uniformity — last decimal digits should be ~uniform (0-9)
    2. Leading-digit conformity — first digits should follow Benford's law
    3. Decimal-suffix clustering — repeated suffix patterns suggest manual formatting
    4. Value-level duplication — identical values in independent experiments are rare
    5. Distribution shape — kurtosis/skewness anomalies suggest artificial construction
    6. Cross-column consistency — CV outliers within same sheet suggest fabrication

Convergence across methods strengthens the signal.

Usage:
    python data_integrity_checker.py --input paper_data.xlsx --output ./data/integrity_audit.json
    python data_integrity_checker.py --input paper_data.csv --output ./data/integrity_audit.json --verbose
"""

import argparse
import json
import math
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
    method: str          # tail_digit | leading_digit | decimal_consistency | data_duplication | distribution_shape | cross_column
    severity: str        # HIGH | MEDIUM | LOW
    description: str
    confidence: float
    confidence_level: str = "L2"   # L2=线索 | L3=疑似 | L4=高度可能 | L5=确凿
    p_value: Optional[float] = None
    effect_size: Optional[float] = None
    statistics: Optional[dict] = None


# ---------------------------------------------------------------------------
# Sample-size calibration
# ---------------------------------------------------------------------------


def _effective_cutoff(n: int, base_cutoff: float) -> float:
    """Adjust p-value cutoff based on sample size.

    Small samples lack statistical power → widen cutoff to avoid missing real signals.
    Large samples are over-sensitive → tighten cutoff to reduce false positives.
    """
    if n < 20:
        return base_cutoff * 1.3
    if n > 200:
        return base_cutoff * 0.7
    return base_cutoff


def _confidence_cap(n: int) -> float:
    """Cap confidence based on sample size — small samples can't support high confidence."""
    if n < 15:
        return 0.45
    if n < 30:
        return 0.65
    return 1.0  # no cap


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

    last_digits = []
    for v in values:
        s = f"{v:.{precision}f}"
        dec_part = s.split(".")[-1]
        last_digits.append(int(dec_part[-1]) if dec_part else 0)

    n = len(last_digits)
    k = 10
    observed = np.zeros(k)
    for d in last_digits:
        observed[d] += 1
    expected = np.full(k, n / k)

    chi_sq, p_val = sp_stats.chisquare(observed, f_exp=expected)
    phi = np.sqrt(chi_sq / n)

    cutoff = _effective_cutoff(n, cfg.p_cutoff)
    if p_val >= cutoff:
        return None

    digit_freq = pd.Series(last_digits).value_counts()
    peak_digit = int(digit_freq.idxmax())
    peak_freq = int(digit_freq.max())
    uniform_expect = n / k
    overrep = peak_freq / uniform_expect

    if phi > 0.5 or overrep > 3:
        severity = "HIGH"
    elif phi > cfg.effect_floor:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    cap = _confidence_cap(n)
    return IntegrityFinding(
        sheet=sheet, column=col, method="tail_digit",
        severity=severity, confidence=min(cap, 0.45 + phi * 0.6),
        description=f"尾数分布异常: 尾数{peak_digit}出现{peak_freq}次(期望{uniform_expect:.1f}), "
                    f"过表达{overrep:.1f}x, p={p_val:.4f}",
        p_value=p_val, effect_size=phi,
        statistics={
            "chi_sq": round(chi_sq, 2), "p_value": round(p_val, 4),
            "phi": round(phi, 3), "n": n,
            "peak_digit": peak_digit, "peak_freq": peak_freq,
            "uniform_expect": round(uniform_expect, 1),
            "overrepresentation": round(overrep, 1),
            "digit_freq": {int(k): int(v) for k, v in digit_freq.items()},
        },
    )


# ---------------------------------------------------------------------------
# Method 2: Leading-digit conformity (Benford's law)
# ---------------------------------------------------------------------------

# Benford's law: P(d) = log10(1 + 1/d) for d in 1..9
_BENFORD = {d: math.log10(1 + 1 / d) for d in range(1, 10)}


def _check_leading_digit(
    sheet: str, col: str, values: np.ndarray, cfg: IntegrityConfig
) -> Optional[IntegrityFinding]:
    """First significant digit should follow Benford's law.

    Fabricated datasets often deviate from Benford's distribution because
    humans pick "round" numbers or have digit preferences. Works best with
    data spanning multiple orders of magnitude.
    """
    abs_vals = np.abs(values[values != 0])
    if len(abs_vals) < 30:
        return None  # Benford needs reasonable sample and magnitude spread

    # Check if data spans at least 1 order of magnitude
    log_range = np.log10(abs_vals.max()) - np.log10(abs_vals.min())
    if log_range < 0.8:
        return None  # narrow range → Benford doesn't apply

    # Extract leading digits
    leading = []
    for v in abs_vals:
        d = int(str(v).lstrip("0").lstrip(".").lstrip("0")[0])
        if 1 <= d <= 9:
            leading.append(d)

    n = len(leading)
    if n < 30:
        return None

    observed = np.zeros(9)
    for d in leading:
        observed[d - 1] += 1
    expected = np.array([_BENFORD[d] * n for d in range(1, 10)])

    chi_sq, p_val = sp_stats.chisquare(observed, f_exp=expected)
    phi = np.sqrt(chi_sq / n)

    cutoff = _effective_cutoff(n, cfg.p_cutoff)
    if p_val >= cutoff:
        return None

    digit_freq = {}
    for d in range(1, 10):
        digit_freq[d] = int(observed[d - 1])

    # Find the most over-represented digit
    ratios = {d: observed[d - 1] / (expected[d - 1] if expected[d - 1] > 0 else 1)
              for d in range(1, 10)}
    peak_digit = max(ratios, key=ratios.get)
    peak_ratio = ratios[peak_digit]

    if phi > 0.4 or peak_ratio > 2.5:
        severity = "HIGH"
    elif phi > 0.25:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    cap = _confidence_cap(n)
    return IntegrityFinding(
        sheet=sheet, column=col, method="leading_digit",
        severity=severity, confidence=min(cap, 0.40 + phi * 0.55),
        description=f"首位数字偏离Benford定律: 数字{peak_digit}过表达{peak_ratio:.1f}x, "
                    f"p={p_val:.4f}",
        p_value=p_val, effect_size=phi,
        statistics={
            "chi_sq": round(chi_sq, 2), "p_value": round(p_val, 4),
            "phi": round(phi, 3), "n": n,
            "peak_digit": peak_digit, "peak_ratio": round(peak_ratio, 2),
            "digit_freq": digit_freq,
            "benford_expected": {d: round(_BENFORD[d], 4) for d in range(1, 10)},
            "log_range": round(log_range, 2),
        },
    )


# ---------------------------------------------------------------------------
# Method 3: Decimal-place consistency
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

    suffixes = []
    for v in values:
        s = f"{v:.{precision}f}"
        dec_part = s.split(".")[-1]
        if len(dec_part) >= decimal_place:
            suffixes.append(dec_part[:decimal_place])

    if not suffixes:
        return None

    n = len(suffixes)
    bin_count = 10 ** decimal_place
    baseline_rate = _expected_duplicate_rate(n, bin_count)

    freq = pd.Series(suffixes).value_counts()
    repeat_bins = int((freq >= 2).sum())
    peak_hits = int(freq.max())
    distinct_bins = len(freq)
    observed_rate = repeat_bins / distinct_bins if distinct_bins > 0 else 0

    if baseline_rate > 0:
        inflation = observed_rate / baseline_rate
    else:
        inflation = observed_rate * 100

    expect_per_bin = n / bin_count
    peak_ratio = peak_hits / max(expect_per_bin, 1)

    # Simulation: for 100 draws from 100 bins, P(peak>=4)=87%, P(peak>=5)=30%, P(peak>=6)=5%
    is_anomaly = (inflation > 2.5 and observed_rate > baseline_rate) or peak_ratio > 5
    if not is_anomaly:
        return None

    if peak_ratio > 8 or inflation > 5:
        severity = "HIGH"
    elif peak_ratio > 6 or inflation > 3:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    cap = _confidence_cap(n)
    return IntegrityFinding(
        sheet=sheet, column=col, method="decimal_consistency",
        severity=severity, confidence=min(cap, 0.35 + min(inflation / 12, 0.5)),
        description=f"小数点后{decimal_place}位重复: {repeat_bins}组重复, "
                    f"最高{peak_hits}次, 通胀{inflation:.1f}x "
                    f"(基线{baseline_rate:.1%}, 实际{observed_rate:.1%})",
        statistics={
            "decimal_place": decimal_place, "n": n,
            "repeat_bins": repeat_bins, "peak_hits": peak_hits,
            "observed_rate": f"{observed_rate:.1%}",
            "baseline_rate": f"{baseline_rate:.1%}",
            "inflation": round(inflation, 1),
            "top5": {str(k): int(v) for k, v in freq.head(5).items()},
        },
    )


# ---------------------------------------------------------------------------
# Method 4: Exact-value duplication
# ---------------------------------------------------------------------------


def _check_data_duplication(
    sheet: str, col: str, values: np.ndarray, cfg: IntegrityConfig
) -> Optional[IntegrityFinding]:
    """Exact repeated values in independent experiments are suspicious."""
    freq = pd.Series(values).value_counts()
    repeated_vals = int((freq >= 2).sum())
    peak_count = int(freq.max())

    is_anomaly = repeated_vals >= 5 or peak_count >= cfg.repeat_floor
    if not is_anomaly:
        return None

    if peak_count >= 4:
        severity = "HIGH"
    elif peak_count >= 3:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    n = len(values)
    cap = _confidence_cap(n)
    return IntegrityFinding(
        sheet=sheet, column=col, method="data_duplication",
        severity=severity, confidence=min(cap, 0.25 + peak_count * 0.18),
        description=f"数据重复: {repeated_vals}个重复值, 最高出现{peak_count}次",
        statistics={
            "repeated_count": repeated_vals,
            "peak_count": peak_count,
            "top5": {str(k): int(v) for k, v in freq.head(5).items()},
        },
    )


# ---------------------------------------------------------------------------
# Method 5: Distribution shape (kurtosis / skewness)
# ---------------------------------------------------------------------------


def _check_distribution_shape(
    sheet: str, col: str, values: np.ndarray, cfg: IntegrityConfig
) -> Optional[IntegrityFinding]:
    """Detect anomalous kurtosis or skewness in the data.

    Real experimental measurements typically show moderate skew and kurtosis.
    Fabricated data often shows:
      - Excess kurtosis near 0 (too "perfectly normal")
      - Excess kurtosis extremely high (suspicious outliers)
      - Skewness near 0 when combined with other anomalies
    Requires n >= 20 for reliable higher-moment statistics.
    """
    n = len(values)
    if n < 20:
        return None

    # Constant or near-constant data → skip (kurtosis/skew undefined)
    if np.std(values) < 1e-10:
        return None

    kurt = sp_stats.kurtosis(values)  # excess kurtosis (normal = 0)
    skew = sp_stats.skew(values)

    # Two-tailed test: is kurtosis significantly different from normal?
    try:
        _, p_kurt = sp_stats.kurtosistest(values)
    except Exception:
        p_kurt = 1.0
    try:
        _, p_skew = sp_stats.skewtest(values)
    except Exception:
        p_skew = 1.0

    cutoff = _effective_cutoff(n, cfg.p_cutoff)

    # Flag if EITHER kurtosis or skewness is significantly abnormal
    kurt_flag = p_kurt < cutoff and abs(kurt) > 1.0
    skew_flag = p_skew < cutoff and abs(skew) > 1.5

    if not kurt_flag and not skew_flag:
        return None

    # "Suspiciously normal" — kurtosis near 0 with low skew, combined with other signals
    # is itself a signal (real data rarely has excess kurtosis in [-0.5, 0.5])
    suspiciously_normal = abs(kurt) < 0.5 and abs(skew) < 0.3

    signals = []
    if kurt_flag:
        signals.append(f"峰度={kurt:.2f}(p={p_kurt:.4f})")
    if skew_flag:
        signals.append(f"偏度={skew:.2f}(p={p_skew:.4f})")
    if suspiciously_normal:
        signals.append("分布过于完美(峰度≈0,偏度≈0)")

    if kurt_flag and skew_flag:
        severity = "HIGH"
    elif kurt_flag or skew_flag:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    cap = _confidence_cap(n)
    effect = max(abs(kurt) / 3, abs(skew) / 2)  # normalized deviation

    return IntegrityFinding(
        sheet=sheet, column=col, method="distribution_shape",
        severity=severity, confidence=min(cap, 0.30 + effect * 0.4),
        description=f"分布形态异常: {'; '.join(signals)}",
        p_value=min(p_kurt, p_skew),
        effect_size=round(effect, 3),
        statistics={
            "excess_kurtosis": round(kurt, 3),
            "skewness": round(skew, 3),
            "p_kurtosis": round(p_kurt, 4),
            "p_skewness": round(p_skew, 4),
            "n": n,
            "suspiciously_normal": suspiciously_normal,
        },
    )


# ---------------------------------------------------------------------------
# Method 6: Cross-column consistency (sheet-level)
# ---------------------------------------------------------------------------


def _check_cross_column_consistency(
    sheet_name: str, col_stats: dict[str, dict], cfg: IntegrityConfig
) -> list[IntegrityFinding]:
    """Detect columns whose variance structure deviates from peers.

    If multiple columns come from the same experiment, their coefficient of
    variation (CV = std/mean) should be in a similar range. A column with
    CV far from the group median suggests different noise characteristics
    (possibly fabricated).
    """
    findings = []
    if len(col_stats) < 3:
        return findings  # need at least 3 columns for meaningful comparison

    cvs = {}
    for col, st in col_stats.items():
        mean_abs = abs(st["mean"])
        if mean_abs > 0:
            cvs[col] = st["std"] / mean_abs

    if len(cvs) < 3:
        return findings

    cv_values = np.array(list(cvs.values()))
    median_cv = np.median(cv_values)
    mad_cv = np.median(np.abs(cv_values - median_cv))
    if mad_cv < 1e-10:
        return findings  # all CVs identical, no outlier

    for col, cv in cvs.items():
        # Modified z-score using MAD (robust to outliers)
        z = 0.6745 * (cv - median_cv) / mad_cv
        if abs(z) > 3.0:
            direction = "过高" if cv > median_cv else "过低"
            severity = "HIGH" if abs(z) > 4.0 else "MEDIUM"
            findings.append(IntegrityFinding(
                sheet=sheet_name, column=col, method="cross_column",
                severity=severity,
                confidence=min(0.70, 0.35 + abs(z) * 0.05),
                description=f"变异系数(CV)偏离同表其他列: CV={cv:.3f}, "
                            f"中位数={median_cv:.3f}, z={z:.1f} ({direction})",
                effect_size=round(abs(z) / 5, 3),
                statistics={
                    "cv": round(cv, 4), "median_cv": round(median_cv, 4),
                    "mad_cv": round(mad_cv, 4), "z_score": round(z, 2),
                    "n_columns": len(cvs),
                },
            ))

    return findings


# ---------------------------------------------------------------------------
# Risk scoring
# ---------------------------------------------------------------------------


def _calculate_risk_score(findings: list[IntegrityFinding]) -> tuple[int, str]:
    """Compute 0-100 risk score from findings. Returns (score, level).

    Also assigns confidence_level (L2-L5) to each finding based on
    cross-method convergence — the strongest signal in forensic analysis.
    """
    if not findings:
        return 0, "low"

    from collections import defaultdict

    # --- Build convergence map: which methods hit each column? ---
    col_methods: dict[str, set] = defaultdict(set)
    col_max_severity: dict[str, str] = {}
    sev_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    for f in findings:
        key = f"{f.sheet}/{f.column}"
        col_methods[key].add(f.method)
        prev = col_max_severity.get(key, "LOW")
        if sev_rank.get(f.severity, 0) > sev_rank.get(prev, 0):
            col_max_severity[key] = f.severity

    # --- Assign confidence_level per finding ---
    for f in findings:
        key = f"{f.sheet}/{f.column}"
        n_methods = len(col_methods[key])
        if n_methods >= 3 and col_max_severity[key] == "HIGH":
            f.confidence_level = "L5"
        elif n_methods >= 2:
            f.confidence_level = "L4"
        elif n_methods == 1 and f.severity == "HIGH" and f.p_value is not None and f.p_value < 0.01:
            f.confidence_level = "L3"
        else:
            f.confidence_level = "L2"

    # --- Severity-weighted base score with decay ---
    # Same method flagging 3+ columns: weight halves after 3rd (prevents score inflation)
    weight_map = {"HIGH": 4, "MEDIUM": 2, "LOW": 1}
    method_col_order: dict[str, list] = defaultdict(list)
    for f in findings:
        method_col_order[f.method].append(f"{f.sheet}/{f.column}")

    score = 0.0
    for f in findings:
        base = weight_map.get(f.severity, 1)
        key = f"{f.sheet}/{f.column}"
        rank = method_col_order[f.method].index(key)
        if rank >= 3:
            base *= 0.5  # decay after 3rd column per method
        score += base

    # --- Method diversity bonus ---
    # 3 different methods each hitting 1 column > 1 method hitting 3 columns
    unique_methods = len(method_col_order)
    if unique_methods >= 4:
        score += 12
    elif unique_methods >= 3:
        score += 8

    # --- Cross-method convergence on same column (strongest signal) ---
    for _col, methods_on_col in col_methods.items():
        if len(methods_on_col) >= 3:
            score += 15
        elif len(methods_on_col) == 2:
            score += 7

    score = min(score, 100)

    if score >= 75:
        level = "critical"
    elif score >= 50:
        level = "high"
    elif score >= 25:
        level = "medium"
    else:
        level = "low"

    return score, level


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def check_file(file_path: str, cfg: Optional[IntegrityConfig] = None) -> dict:
    """
    Run all integrity checks on an Excel or CSV file.

    Returns a dict with keys: risk_score, risk_level, confidence_level, findings, summary.
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
        col_stats: dict[str, dict] = {}  # collect for cross-column check

        for col in numeric_cols:
            values = df[col].dropna().values
            if len(values) < cfg.min_rows:
                continue

            is_integer = np.issubdtype(df[col].dtype, np.integer)
            logger.debug("Checking %s / %s (%d values, int=%s)", sheet_name, col, len(values), is_integer)

            # Collect basic stats for cross-column comparison
            col_stats[col] = {"mean": float(np.mean(values)), "std": float(np.std(values))}

            # Method 1: Exact-value duplication (works on any numeric type)
            f1 = _check_data_duplication(sheet_name, col, values, cfg)
            if f1:
                findings.append(f1)

            # Method 2: Leading-digit conformity (Benford's law — works on integers too)
            f2 = _check_leading_digit(sheet_name, col, values, cfg)
            if f2:
                findings.append(f2)

            # Methods 3-4: Decimal-based checks (skip pure integers)
            if not is_integer:
                f3 = _check_tail_distribution(sheet_name, col, values, cfg)
                if f3:
                    findings.append(f3)

                for dp in cfg.decimal_depths:
                    f4 = _check_decimal_consistency(sheet_name, col, values, dp, cfg)
                    if f4:
                        findings.append(f4)

            # Method 5: Distribution shape (works on any numeric type)
            f5 = _check_distribution_shape(sheet_name, col, values, cfg)
            if f5:
                findings.append(f5)

        # Method 6: Cross-column consistency (sheet-level, after all columns)
        if len(col_stats) >= 3:
            findings.extend(_check_cross_column_consistency(sheet_name, col_stats, cfg))

    risk_score, risk_level = _calculate_risk_score(findings)

    methods_involved = list(set(f.method for f in findings))
    columns_involved = list(set(f"{f.sheet}/{f.column}" for f in findings))
    # Highest confidence level across all findings
    level_rank = {"L2": 2, "L3": 3, "L4": 4, "L5": 5}
    max_conf_level = max((level_rank.get(f.confidence_level, 2) for f in findings), default=2)
    max_conf_label = {v: k for k, v in level_rank.items()}[max_conf_level]

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "confidence_level": max_conf_label,
        "findings": [asdict(f) for f in findings],
        "summary": {
            "total_findings": len(findings),
            "methods_involved": methods_involved,
            "columns_involved": columns_involved,
            "confidence_level": max_conf_label,
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
            "version": "2.0",
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
                "confidence_level": f.get("confidence_level", "L2"),
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
    print(f"Confidence:     {result['confidence_level']}")
    print(f"Findings:       {result['summary']['total_findings']}")
    print(f"  HIGH:         {result['summary']['high_severity']}")
    print(f"  MEDIUM:       {result['summary']['medium_severity']}")
    print(f"  LOW:          {result['summary']['low_severity']}")
    print(f"Methods:        {', '.join(result['summary']['methods_involved']) or 'none'}")
    print(f"Columns:        {len(result['summary']['columns_involved'])}")
    print(f"Output:         {args.output}")


if __name__ == "__main__":
    main()
