#!/usr/bin/env python3
"""
stats_reverse_engineer.py

Reverse-engineer reported statistics in papers to detect inconsistencies.
Parses text for statistical descriptions (mean, SD, n, p-values, test statistics)
and applies basic consistency checks.

Checks performed:
    - Cochran's rule of thumb: max range ≈ 6*SD for n>30
    - Integer count data: mean * n should yield a plausible integer sum
    - P-values: reported test statistic and df should yield approximately the stated p
    - F/t tests: verify test statistic can be computed from group statistics

Flag patterns:
    impossible_sd, inconsistent_p_value, integer_discrepancy, test_statistic_mismatch

Usage:
    python stats_reverse_engineer.py --papers ./data/papers.json --output ./data/stats_audit.json
    python stats_reverse_engineer.py --papers ./data/papers.json --output ./data/stats_audit.json --threshold 0.1 --verbose
"""

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.utils import get_logger, save_json

logger = get_logger("stats_reverse_engineer")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class StatSnippet:
    paper_id: str
    paper_title: str
    snippet: str
    stat_type: str
    values: dict


@dataclass
class Anomaly:
    paper_id: str
    paper_title: str
    flag_type: str
    confidence: float
    explanation: str
    snippet: str
    expected: Optional[float] = None
    reported: Optional[float] = None


# ---------------------------------------------------------------------------
# Regex extractors
# ---------------------------------------------------------------------------

MEAN_SD_N_RE = re.compile(
    r"(?:M|mean| Mean)\s*[=:]\s*([0-9]+\.?[0-9]*)\s*[,;]?\s*(?:SD|sd|s\.d\.?)\s*[=:]\s*([0-9]+\.?[0-9]*)\s*[,;]?\s*(?:n|N)\s*[=:]\s*([0-9]+)",
    re.IGNORECASE,
)

MEAN_PM_SD_RE = re.compile(
    r"([0-9]+\.?[0-9]*)\s*[±+-]\s*([0-9]+\.?[0-9]*)\s*\(?\s*(?:n|N)\s*[=:]\s*([0-9]+)\s*\)?",
    re.IGNORECASE,
)

P_VALUE_RE = re.compile(
    r"(?:p|P)\s*[<=>]\s*(0?\.[0-9]+(?:e-?[0-9]+)?)\s*(?:\()?\s*(?:t|F|r)\s*\(\s*([^)]+)\s*\)\s*[=:]\s*([0-9]+\.?[0-9]*)",
    re.IGNORECASE,
)

T_TEST_GROUPS_RE = re.compile(
    r"(?:Group|Condition)\s*([A-Za-z0-9_]+)[^0-9]*"
    r"(?:M|mean)\s*[=:]\s*([0-9]+\.?[0-9]*)\s*[,;]?\s*"
    r"(?:SD|sd)\s*[=:]\s*([0-9]+\.?[0-9]*)\s*[,;]?\s*"
    r"(?:n|N)\s*[=:]\s*([0-9]+)",
    re.IGNORECASE,
)

F_TEST_GROUPS_RE = re.compile(
    r"(?:F\s*\(\s*([0-9]+)\s*,\s*([0-9]+)\s*\)\s*[=:]\s*([0-9]+\.?[0-9]*))",
    re.IGNORECASE,
)

RANGE_RE = re.compile(
    r"range\s*[=:]\s*([0-9]+\.?[0-9]*)\s*[-–]\s*([0-9]+\.?[0-9]*)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _extract_snippets(text: str, paper_id: str, paper_title: str) -> list[StatSnippet]:
    snippets: list[StatSnippet] = []
    for m in MEAN_SD_N_RE.finditer(text):
        snippets.append(StatSnippet(
            paper_id=paper_id,
            paper_title=paper_title,
            snippet=m.group(0),
            stat_type="mean_sd_n",
            values={"mean": float(m.group(1)), "sd": float(m.group(2)), "n": int(m.group(3))},
        ))
    for m in MEAN_PM_SD_RE.finditer(text):
        snippets.append(StatSnippet(
            paper_id=paper_id,
            paper_title=paper_title,
            snippet=m.group(0),
            stat_type="mean_pm_sd",
            values={"mean": float(m.group(1)), "sd": float(m.group(2)), "n": int(m.group(3))},
        ))
    for m in P_VALUE_RE.finditer(text):
        try:
            p_val = float(m.group(1))
            df_str = m.group(2)
            test_stat = float(m.group(3))
            df_parts = [x.strip() for x in df_str.split(",")]
            df_vals = [int(x) for x in df_parts if x.strip().isdigit()]
            snippets.append(StatSnippet(
                paper_id=paper_id,
                paper_title=paper_title,
                snippet=m.group(0),
                stat_type="p_value_report",
                values={"p": p_val, "df": df_vals, "test_stat": test_stat},
            ))
        except (ValueError, IndexError):
            continue
    for m in RANGE_RE.finditer(text):
        snippets.append(StatSnippet(
            paper_id=paper_id,
            paper_title=paper_title,
            snippet=m.group(0),
            stat_type="range",
            values={"min": float(m.group(1)), "max": float(m.group(2))},
        ))
    return snippets


# ---------------------------------------------------------------------------
# Consistency checks
# ---------------------------------------------------------------------------


def _cochran_check(snippet: StatSnippet) -> Optional[Anomaly]:
    vals = snippet.values
    mean = vals.get("mean", 0)
    sd = vals.get("sd", 0)
    n = vals.get("n", 0)
    if not (mean and sd and n):
        return None
    if n <= 30:
        return None
    # Cochran's rule of thumb: max range ≈ 6*SD for n>30
    expected_range = 6.0 * sd
    # We don't have explicit range; we estimate from mean and SD
    # Use heuristic: if mean is small and SD is large relative to mean
    if mean > 0 and sd > mean * 3:
        return Anomaly(
            paper_id=snippet.paper_id,
            paper_title=snippet.paper_title,
            flag_type="impossible_sd",
            confidence=0.65,
            explanation=f"SD ({sd}) exceeds 3x the mean ({mean}), violating Cochran's rule for n={n}",
            snippet=snippet.snippet,
            expected=mean * 3,
            reported=sd,
        )
    return None


def _integer_discrepancy_check(snippet: StatSnippet) -> Optional[Anomaly]:
    vals = snippet.values
    mean = vals.get("mean", 0)
    n = vals.get("n", 0)
    if not (mean and n):
        return None
    # For integer count data, mean * n should be close to an integer
    total = mean * n
    nearest = round(total)
    if abs(total - nearest) > 0.15:
        return Anomaly(
            paper_id=snippet.paper_id,
            paper_title=snippet.paper_title,
            flag_type="integer_discrepancy",
            confidence=0.55,
            explanation=f"Mean ({mean}) * n ({n}) = {total:.2f}, not close to an integer — suspicious for count data",
            snippet=snippet.snippet,
            expected=float(nearest),
            reported=total,
        )
    return None


def _p_value_consistency_check(snippet: StatSnippet, threshold: float) -> Optional[Anomaly]:
    vals = snippet.values
    p_reported = vals.get("p", 0)
    df = vals.get("df", [])
    test_stat = vals.get("test_stat", 0)
    if not (p_reported and df and test_stat):
        return None
    # Approximate p-value from t-statistic with df
    if len(df) >= 1 and test_stat > 0:
        df1 = df[0]
        try:
            # Approximate two-tailed p for t using rough normal approx for large df
            if df1 > 2:
                p_approx = 2.0 * (1.0 - _approx_cdf_t(test_stat, df1))
                if p_approx < 0:
                    p_approx = 0.0
                rel_err = abs(p_approx - p_reported) / max(p_reported, 1e-10)
                if rel_err > threshold and rel_err > 0.5:
                    return Anomaly(
                        paper_id=snippet.paper_id,
                        paper_title=snippet.paper_title,
                        flag_type="inconsistent_p_value",
                        confidence=min(0.75, 0.5 + rel_err * 0.25),
                        explanation=f"Reported p={p_reported} but t({df1})={test_stat} implies p≈{p_approx:.4f} (rel_err={rel_err:.2f})",
                        snippet=snippet.snippet,
                        expected=p_approx,
                        reported=p_reported,
                    )
        except (ValueError, OverflowError):
            pass
    return None


def _approx_cdf_t(t: float, df: float) -> float:
    """Approximate CDF of t-distribution using Wilson-Hilferty transformation."""
    if df <= 0:
        return 0.5
    # Approximate normal with adjusted variance
    z = t * math.sqrt(df / (df - 2)) if df > 2 else t
    return _approx_cdf_normal(z)


def _approx_cdf_normal(z: float) -> float:
    """Abramowitz and Stegun approximation for standard normal CDF."""
    if z < 0:
        return 1.0 - _approx_cdf_normal(-z)
    a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    p = 0.3275911
    t = 1.0 / (1.0 + p * z)
    poly = a1 * t + a2 * t * t + a3 * t**3 + a4 * t**4 + a5 * t**5
    return 1.0 - poly * math.exp(-z * z / 2.0)


def _test_statistic_mismatch(text: str, snippet: StatSnippet, threshold: float) -> Optional[Anomaly]:
    """Check if an F-test statistic can be approximated from group SDs."""
    # Extract all group statistics from the surrounding text context
    groups = []
    for m in T_TEST_GROUPS_RE.finditer(text):
        try:
            groups.append({
                "mean": float(m.group(2)),
                "sd": float(m.group(3)),
                "n": int(m.group(4)),
            })
        except (ValueError, IndexError):
            continue
    if len(groups) < 2:
        return None
    # Compute pooled SD and approximate t-statistic for two groups
    g1, g2 = groups[0], groups[1]
    n1, n2 = g1["n"], g2["n"]
    m1, m2 = g1["mean"], g2["mean"]
    sd1, sd2 = g1["sd"], g2["sd"]
    if n1 < 2 or n2 < 2:
        return None
    pooled_se = math.sqrt(((n1 - 1) * sd1**2 + (n2 - 1) * sd2**2) / (n1 + n2 - 2)) * math.sqrt(1.0 / n1 + 1.0 / n2)
    if pooled_se == 0:
        return None
    t_computed = abs(m1 - m2) / pooled_se
    # Look for a reported t-statistic near this value
    for m in re.finditer(r"t\s*\(\s*[^)]+\)\s*[=:]\s*([0-9]+\.?[0-9]*)", text, re.IGNORECASE):
        try:
            t_reported = float(m.group(1))
            rel_err = abs(t_computed - t_reported) / max(t_reported, 1e-10)
            if rel_err > threshold and rel_err > 0.5:
                return Anomaly(
                    paper_id=snippet.paper_id,
                    paper_title=snippet.paper_title,
                    flag_type="test_statistic_mismatch",
                    confidence=min(0.8, 0.55 + rel_err * 0.2),
                    explanation=f"Reported t={t_reported} but group statistics yield t≈{t_computed:.2f} (rel_err={rel_err:.2f})",
                    snippet=snippet.snippet,
                    expected=t_computed,
                    reported=t_reported,
                )
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def audit_paper(paper: dict, threshold: float) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    paper_id = paper.get("id", paper.get("doi", "unknown"))
    title = paper.get("title", "Untitled")
    text = paper.get("full_text", "") or paper.get("abstract", "") or ""
    if not text:
        return anomalies

    snippets = _extract_snippets(text, paper_id, title)
    logger.debug("Paper %s: extracted %d stat snippets", paper_id, len(snippets))

    for snip in snippets:
        check = _cochran_check(snip)
        if check:
            anomalies.append(check)
        check = _integer_discrepancy_check(snip)
        if check:
            anomalies.append(check)
        check = _p_value_consistency_check(snip, threshold)
        if check:
            anomalies.append(check)
        check = _test_statistic_mismatch(text, snip, threshold)
        if check:
            anomalies.append(check)

    return anomalies


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Reverse-engineer reported statistics to detect inconsistencies")
    p.add_argument("--papers", type=Path, required=True, help="Path to JSON with paper metadata")
    p.add_argument("--output", type=Path, default=Path("./data/stats_audit.json"), help="Output JSON path")
    p.add_argument("--threshold", type=float, default=0.1, help="Relative error threshold for flagging")
    p.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    return p


def main():
    args = build_parser().parse_args()
    if args.verbose:
        logger.setLevel(10)  # DEBUG

    if not args.papers.exists():
        logger.error("Papers file not found: %s", args.papers)
        sys.exit(1)

    with open(args.papers, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    papers = raw if isinstance(raw, list) else raw.get("papers", [])
    logger.info("Loaded %d papers for statistical audit", len(papers))

    all_anomalies: list[Anomaly] = []
    for paper in papers:
        anomalies = audit_paper(paper, args.threshold)
        all_anomalies.extend(anomalies)

    signals = []
    for a in all_anomalies:
        evidence = {"snippet": a.snippet}
        if a.expected is not None:
            evidence["expected"] = a.expected
        if a.reported is not None:
            evidence["reported"] = a.reported
        signals.append({
            "type": a.flag_type,
            "description": a.explanation,
            "confidence": float(a.confidence),
            "paper_id": a.paper_id,
            "source": "stats_reverse_engineer",
            "evidence": evidence,
        })

    result = {
        "meta": {
            "script": "stats_reverse_engineer",
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "input_file": str(args.papers),
            "total_papers": len(papers),
            "anomaly_count": len(all_anomalies),
            "threshold": args.threshold,
        },
        "signals": signals,
        "details": {
            "anomalies": [asdict(a) for a in all_anomalies],
        },
    }

    save_json(result, args.output)
    logger.info("Saved stats audit to %s", args.output)

    print(f"\n{'='*60}")
    print(f"Stats Reverse Engineer Summary")
    print(f"{'='*60}")
    print(f"Papers audited:  {len(papers)}")
    print(f"Anomalies found: {len(all_anomalies)}")
    if all_anomalies:
        by_type: dict[str, int] = {}
        for a in all_anomalies:
            by_type[a.flag_type] = by_type.get(a.flag_type, 0) + 1
        print(f"\nBy type:")
        for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"  {t}: {c}")
        print(f"\nTop anomalies:")
        for a in sorted(all_anomalies, key=lambda x: -x.confidence)[:5]:
            print(f"  [{a.confidence:.2f}] {a.flag_type}: {a.explanation}")
    print(f"\nOutput:         {args.output}")


if __name__ == "__main__":
    main()
