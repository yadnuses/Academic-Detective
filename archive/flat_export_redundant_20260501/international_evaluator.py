#!/usr/bin/env python3
"""
international/evaluator.py

International academic evaluation system.
Maps papers to journal metrics (JCR quartile, CiteScore) and evaluates
career benchmarks against tenure-track norms.

Usage:
    from international.evaluator import InternationalEvaluator

    evaluator = InternationalEvaluator()
    metrics = evaluator.evaluate_author(author_data, papers)
"""

import json
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional

from core_utils import get_logger

logger = get_logger("international_evaluator")


# ---------------------------------------------------------------------------
# Discipline-specific benchmarks (simplified, can be expanded)
# ---------------------------------------------------------------------------

# Normal annual paper output by discipline and career stage
_ANNUAL_OUTPUT_BENCHMARKS = {
    "computer_science": {
        "assistant_prof": (2.0, 4.0),      # min, max per year
        "associate_prof": (3.0, 6.0),
        "full_prof": (3.0, 7.0),
    },
    "life_sciences": {
        "assistant_prof": (3.0, 6.0),
        "associate_prof": (4.0, 8.0),
        "full_prof": (4.0, 10.0),
    },
    "physics_math": {
        "assistant_prof": (1.5, 4.0),
        "associate_prof": (2.0, 5.0),
        "full_prof": (2.0, 6.0),
    },
    "social_sciences": {
        "assistant_prof": (1.0, 3.0),
        "associate_prof": (1.5, 4.0),
        "full_prof": (1.5, 5.0),
    },
    "humanities": {
        "assistant_prof": (0.5, 2.0),
        "associate_prof": (1.0, 3.0),
        "full_prof": (1.0, 4.0),
    },
    "engineering": {
        "assistant_prof": (2.0, 5.0),
        "associate_prof": (3.0, 7.0),
        "full_prof": (3.0, 8.0),
    },
}

# h-index benchmarks by years since PhD and discipline
_H_INDEX_BENCHMARKS = {
    "computer_science": {
        5: (5, 12),    # year 5: min, expected
        10: (12, 25),
        15: (20, 40),
        20: (30, 55),
    },
    "life_sciences": {
        5: (8, 18),
        10: (20, 40),
        15: (35, 60),
        20: (50, 80),
    },
    "physics_math": {
        5: (5, 12),
        10: (12, 25),
        15: (20, 40),
        20: (30, 55),
    },
    "social_sciences": {
        5: (3, 8),
        10: (8, 18),
        15: (15, 30),
        20: (25, 45),
    },
    "humanities": {
        5: (1, 4),
        10: (4, 10),
        15: (8, 18),
        20: (15, 30),
    },
    "engineering": {
        5: (5, 12),
        10: (12, 25),
        15: (20, 40),
        20: (30, 55),
    },
}

# Tenure clock expectations by institution tier
_TENURE_EXPECTATIONS = {
    "r1": {  # Carnegie R1 (very high research)
        "years_to_tenure": 6,
        "min_papers": 15,
        "min_first_author": 8,
        "min_high_impact": 3,  # Q1 or equivalent
        "min_grants": 1,
        "expected_h_index_at_review": 12,
    },
    "r2": {  # Carnegie R2 (high research)
        "years_to_tenure": 6,
        "min_papers": 10,
        "min_first_author": 5,
        "min_high_impact": 2,
        "min_grants": 1,
        "expected_h_index_at_review": 8,
    },
    "liberal_arts": {  # Liberal arts college
        "years_to_tenure": 6,
        "min_papers": 6,
        "min_first_author": 3,
        "min_high_impact": 1,
        "min_grants": 0,  # Grants less important
        "expected_h_index_at_review": 5,
    },
    "international_top": {  # Top non-US institutions (Oxford, Cambridge, ETH, etc.)
        "years_to_tenure": 5,
        "min_papers": 12,
        "min_first_author": 6,
        "min_high_impact": 3,
        "min_grants": 1,
        "expected_h_index_at_review": 10,
    },
}


class InternationalEvaluator:
    """
    Evaluate international scholars against discipline-specific benchmarks.
    """

    def __init__(self):
        self._journal_cache = {}  # Cache journal metric lookups

    def evaluate_journal(self, journal_name: str, issn: str = "") -> dict:
        """
        Look up journal metrics.

        Returns:
            {
                "jcr_quartile": int or None,  # 1-4
                "cite_score": float or None,
                "sjr": float or None,
                "snip": float or None,
                "category": str,
            }
        """
        cache_key = f"{journal_name}:{issn}"
        if cache_key in self._journal_cache:
            return self._journal_cache[cache_key]

        # TODO: Implement actual Scopus/WoS journal lookup
        # For now, return placeholder with inference heuristics
        result = self._infer_journal_tier(journal_name)
        self._journal_cache[cache_key] = result
        return result

    def _infer_journal_tier(self, journal_name: str) -> dict:
        """Infer journal tier from name heuristics (fallback)."""
        name_lower = journal_name.lower()

        # Top-tier indicators
        top_indicators = ["nature", "science", "cell", "pnas", "lancet", "ieee transactions",
                         "acm transactions", "journal of the acm", "physical review letters"]
        if any(ind in name_lower for ind in top_indicators):
            return {
                "jcr_quartile": 1,
                "cite_score": 15.0,
                "sjr": 5.0,
                "snip": 3.0,
                "category": "top_tier",
                "inference_method": "name_heuristic",
            }

        # Well-known publisher indicators
        good_publishers = ["ieee", "acm", "springer", "elsevier", "wiley", "oxford university press"]
        if any(pub in name_lower for pub in good_publishers):
            return {
                "jcr_quartile": None,
                "cite_score": 5.0,
                "sjr": 1.5,
                "snip": 1.2,
                "category": "established_publisher",
                "inference_method": "publisher_heuristic",
            }

        # Open access / potential predatory indicators
        oa_indicators = ["open access", "frontiers", "mdpi", "hindawi"]
        if any(ind in name_lower for ind in oa_indicators):
            return {
                "jcr_quartile": None,
                "cite_score": 3.0,
                "sjr": 0.8,
                "snip": 0.9,
                "category": "open_access",
                "inference_method": "publisher_heuristic",
            }

        return {
            "jcr_quartile": None,
            "cite_score": None,
            "sjr": None,
            "snip": None,
            "category": "unknown",
            "inference_method": "none",
        }

    def evaluate_tenure_benchmark(
        self,
        papers: list,
        years_since_phd: int,
        institution_tier: str,
        field: str,
    ) -> dict:
        """
        Evaluate whether output meets tenure-track expectations.

        Args:
            papers: List of paper dicts with year, journal, citation_count
            years_since_phd: Years since PhD completion
            institution_tier: "r1", "r2", "liberal_arts", "international_top"
            field: Discipline key

        Returns:
            {
                "meets_expectations": bool,
                "assessment": str,
                "gaps": [str],
                "metrics": {...},
            }
        """
        expectations = _TENURE_EXPECTATIONS.get(institution_tier, _TENURE_EXPECTATIONS["r2"])
        benchmarks = _H_INDEX_BENCHMARKS.get(field, _H_INDEX_BENCHMARKS["computer_science"])
        output_bench = _ANNUAL_OUTPUT_BENCHMARKS.get(field, _ANNUAL_OUTPUT_BENCHMARKS["computer_science"])

        # Calculate metrics
        total_papers = len(papers)
        first_author_papers = len([p for p in papers if p.get("author_position") == "first"])
        q1_papers = len([p for p in papers if (p.get("jcr_quartile") or 5) <= 1])

        # Calculate h-index (simplified)
        citations = sorted([p.get("citation_count", 0) for p in papers], reverse=True)
        h_index = 0
        for i, c in enumerate(citations, 1):
            if c >= i:
                h_index = i
            else:
                break

        # Expected h-index at current career stage
        expected_h = 0
        for year_threshold, (min_h, expected) in sorted(benchmarks.items()):
            if years_since_phd >= year_threshold:
                expected_h = expected

        # Annual output rate
        current_title = "assistant_prof"  # Simplified
        expected_annual = output_bench.get(current_title, (2.0, 4.0))
        actual_annual = total_papers / max(years_since_phd, 1)

        # Assessment
        gaps = []
        if total_papers < expectations["min_papers"]:
            gaps.append(f"论文总数不足: {total_papers} < {expectations['min_papers']} (预期)")
        if first_author_papers < expectations["min_first_author"]:
            gaps.append(f"一作论文不足: {first_author_papers} < {expectations['min_first_author']}")
        if q1_papers < expectations["min_high_impact"]:
            gaps.append(f"高影响力论文不足: {q1_papers} < {expectations['min_high_impact']}")
        if h_index < expected_h * 0.7:
            gaps.append(f"h-index偏低: {h_index} < {expected_h} (预期)")
        if actual_annual < expected_annual[0]:
            gaps.append(f"年均产出偏低: {actual_annual:.1f} < {expected_annual[0]} (预期)")

        meets = len(gaps) == 0

        return {
            "meets_expectations": meets,
            "assessment": (
                "产出符合tenure-track预期" if meets
                else f"存在 {len(gaps)} 项未达标指标"
            ),
            "gaps": gaps,
            "metrics": {
                "total_papers": total_papers,
                "first_author_papers": first_author_papers,
                "q1_papers": q1_papers,
                "h_index": h_index,
                "expected_h_index": expected_h,
                "actual_annual_output": actual_annual,
                "expected_annual_output": expected_annual,
                "years_since_phd": years_since_phd,
                "institution_tier": institution_tier,
                "field": field,
            },
        }

    def evaluate_grant_portfolio(self, grants: list, discipline: str) -> dict:
        """
        Evaluate grant portfolio strength.

        Returns:
            {
                "total_funding": float,
                "funding_by_source": dict,
                "assessment": str,
                "has_major_grant": bool,
            }
        """
        total = sum(g.get("amount_usd", 0) or 0 for g in grants)

        sources = {}
        for g in grants:
            src = g.get("funding_agency", "unknown")
            sources[src] = sources.get(src, 0) + (g.get("amount_usd", 0) or 0)

        # Major grant thresholds by discipline
        major_thresholds = {
            "computer_science": 500000,
            "life_sciences": 1000000,
            "physics_math": 800000,
            "social_sciences": 300000,
            "humanities": 150000,
            "engineering": 600000,
        }
        threshold = major_thresholds.get(discipline, 500000)
        has_major = any(g.get("amount_usd", 0) >= threshold for g in grants)

        assessment = "基金实力强" if has_major else "基金规模一般"
        if total == 0:
            assessment = "无已知基金项目"

        return {
            "total_funding_usd": total,
            "funding_by_source": sources,
            "grant_count": len(grants),
            "has_major_grant": has_major,
            "major_grant_threshold": threshold,
            "assessment": assessment,
        }

    def evaluate_paper_distribution(self, papers: list) -> dict:
        """
        Analyze paper distribution across journals and years.

        Returns:
            {
                "journal_distribution": {journal: count},
                "year_distribution": {year: count},
                "q_distribution": {"Q1": n, "Q2": n, ...},
                "concentration_risk": str,  # "high" / "medium" / "low"
            }
        """
        journals = {}
        years = {}
        quartiles = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0, "Unknown": 0}

        for p in papers:
            j = p.get("journal", "Unknown")
            journals[j] = journals.get(j, 0) + 1

            y = p.get("year")
            if y:
                years[y] = years.get(y, 0) + 1

            q = p.get("jcr_quartile")
            if q == 1:
                quartiles["Q1"] += 1
            elif q == 2:
                quartiles["Q2"] += 1
            elif q == 3:
                quartiles["Q3"] += 1
            elif q == 4:
                quartiles["Q4"] += 1
            else:
                quartiles["Unknown"] += 1

        # Concentration risk
        if papers:
            top_journal_pct = max(journals.values()) / len(papers)
            if top_journal_pct > 0.4:
                concentration = "high"
            elif top_journal_pct > 0.25:
                concentration = "medium"
            else:
                concentration = "low"
        else:
            concentration = "unknown"

        return {
            "journal_distribution": dict(sorted(journals.items(), key=lambda x: x[1], reverse=True)[:10]),
            "year_distribution": dict(sorted(years.items())),
            "quartile_distribution": quartiles,
            "concentration_risk": concentration,
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="International academic evaluator")
    parser.add_argument("--papers", "-p", help="Path to papers JSON file")
    parser.add_argument("--grants", "-g", help="Path to grants JSON file")
    parser.add_argument("--years-since-phd", "-y", type=int, default=5)
    parser.add_argument("--tier", "-t", default="r1", choices=["r1", "r2", "liberal_arts", "international_top"])
    parser.add_argument("--field", "-f", default="computer_science",
                        choices=["computer_science", "life_sciences", "physics_math",
                                 "social_sciences", "humanities", "engineering"])
    parser.add_argument("--output", "-o", help="Output JSON file")
    args = parser.parse_args()

    evaluator = InternationalEvaluator()

    papers = []
    if args.papers:
        with open(args.papers, "r", encoding="utf-8") as f:
            papers = json.load(f)

    grants = []
    if args.grants:
        with open(args.grants, "r", encoding="utf-8") as f:
            grants = json.load(f)

    tenure_eval = evaluator.evaluate_tenure_benchmark(
        papers, args.years_since_phd, args.tier, args.field
    )
    grant_eval = evaluator.evaluate_grant_portfolio(grants, args.field)
    dist_eval = evaluator.evaluate_paper_distribution(papers)

    result = {
        "tenure_benchmark": tenure_eval,
        "grant_portfolio": grant_eval,
        "paper_distribution": dist_eval,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info("Saved to: %s", args.output)


if __name__ == "__main__":
    main()
