#!/usr/bin/env python3
"""
analysis/common_heuristics.py

Shared anomaly detection heuristics applicable to both domestic and international
scholar investigations. These rules operate on normalized paper/author data and
are not tied to any specific country's academic system.

Usage:
    from analysis.common_heuristics import CommonHeuristicsClassifier

    classifier = CommonHeuristicsClassifier()
    flags = classifier.classify(papers, author_profile, discipline="computer_science")
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from core.utils import get_logger

logger = get_logger("common_heuristics")


# ---------------------------------------------------------------------------
# Shared detection rules
# ---------------------------------------------------------------------------

@dataclass
class HeuristicRule:
    id: str
    name: str
    description: str
    severity_threshold: str  # low / medium / high / critical
    confidence_level: str    # L2 - L5


# Discipline-specific normal ranges for annual paper output
_ANNUAL_OUTPUT_BENCHMARKS = {
    "computer_science": (2.0, 6.0),
    "life_sciences": (3.0, 8.0),
    "physics_math": (1.5, 5.0),
    "social_sciences": (1.0, 3.5),
    "humanities": (0.5, 2.5),
    "engineering": (2.0, 6.0),
    "medicine": (3.0, 8.0),
}

# Normal h-index by years since PhD (simplified cross-disciplinary baseline)
_H_INDEX_BASELINE = {
    3: (1, 4),
    5: (3, 10),
    10: (8, 25),
    15: (15, 45),
    20: (25, 65),
}


class CommonHeuristicsClassifier:
    """Classify common academic anomalies shared across domestic and international contexts."""

    def classify(
        self,
        papers: list,
        author_profile: dict = None,
        discipline: str = "computer_science",
        years_active: int = 10,
    ) -> list[dict]:
        """
        Run all common heuristics and return flags.

        Args:
            papers: List of paper dicts with year, journal, authors, citation_count
            author_profile: Dict with h_index, total_citations, etc.
            discipline: Discipline key for benchmark selection
            years_active: Years since first publication

        Returns:
            List of anomaly dicts with rule_id, rule_name, severity, confidence, description, evidence
        """
        flags = []
        author_profile = author_profile or {}

        flags.extend(self.classify_output_quantity(papers, discipline, years_active))
        flags.extend(self.classify_journal_concentration(papers))
        flags.extend(self.classify_citation_pattern(papers, author_profile))
        flags.extend(self.classify_author_position_pattern(papers))
        flags.extend(self.classify_publication_burst(papers))
        flags.extend(self.classify_h_index_anomaly(author_profile, years_active))

        logger.info("Common heuristics complete: %d flags", len(flags))
        return flags

    def classify_output_quantity(
        self, papers: list, discipline: str, years_active: int
    ) -> list[dict]:
        """Flag unusually high or low paper output relative to discipline norms."""
        flags = []
        if not papers or years_active <= 0:
            return flags

        bench = _ANNUAL_OUTPUT_BENCHMARKS.get(discipline, (1.0, 5.0))
        total = len(papers)
        annual = total / years_active

        if annual > bench[1] * 2:
            flags.append({
                "rule_id": "C01",
                "rule_name": "产出数量异常偏高",
                "severity": "medium",
                "confidence": "L3",
                "description": (
                    f"年均发表 {annual:.1f} 篇，"
                    f"远超 {discipline} 正常区间 ({bench[0]:.1f}-{bench[1]:.1f} 篇/年)"
                ),
                "evidence": [
                    {"total_papers": total, "years_active": years_active, "annual_rate": annual},
                ],
            })
        elif annual < bench[0] * 0.3 and years_active >= 5:
            flags.append({
                "rule_id": "C01",
                "rule_name": "产出数量异常偏低",
                "severity": "low",
                "confidence": "L2",
                "description": (
                    f"年均发表 {annual:.1f} 篇，"
                    f"低于 {discipline} 正常区间 ({bench[0]:.1f}-{bench[1]:.1f} 篇/年)"
                ),
                "evidence": [
                    {"total_papers": total, "years_active": years_active, "annual_rate": annual},
                ],
            })

        return flags

    def classify_journal_concentration(self, papers: list) -> list[dict]:
        """Flag excessive concentration of papers in a single journal."""
        flags = []
        if len(papers) < 5:
            return flags

        journal_counts = Counter()
        for p in papers:
            j = p.get("journal", "Unknown")
            if j and j != "Unknown":
                journal_counts[j] += 1

        if not journal_counts:
            return flags

        top_journal, top_count = journal_counts.most_common(1)[0]
        concentration = top_count / len(papers)

        if concentration > 0.5:
            flags.append({
                "rule_id": "C02",
                "rule_name": "期刊集中度异常",
                "severity": "medium",
                "confidence": "L3",
                "description": (
                    f"{top_count}/{len(papers)} 篇论文发表于同一期刊 "
                    f"'{top_journal}'，占比 {concentration*100:.0f}%"
                ),
                "evidence": [
                    {"journal": top_journal, "count": top_count, "concentration": concentration},
                ],
            })
        elif concentration > 0.35:
            flags.append({
                "rule_id": "C02",
                "rule_name": "期刊集中度异常",
                "severity": "low",
                "confidence": "L2",
                "description": (
                    f"{top_count}/{len(papers)} 篇论文发表于同一期刊 "
                    f"'{top_journal}'，占比 {concentration*100:.0f}%"
                ),
                "evidence": [
                    {"journal": top_journal, "count": top_count, "concentration": concentration},
                ],
            })

        return flags

    def classify_citation_pattern(self, papers: list, author_profile: dict) -> list[dict]:
        """Flag suspicious citation patterns (self-citation, zero-citation clusters)."""
        flags = []
        if len(papers) < 3:
            return flags

        # Zero-citation papers check
        zero_cit = [p for p in papers if p.get("citation_count", 0) == 0]
        if len(papers) >= 10 and len(zero_cit) / len(papers) > 0.7:
            flags.append({
                "rule_id": "C03",
                "rule_name": "零引用论文比例异常",
                "severity": "medium",
                "confidence": "L3",
                "description": (
                    f"{len(zero_cit)}/{len(papers)} 篇论文零引用，"
                    f"占比 {len(zero_cit)/len(papers)*100:.0f}%"
                ),
                "evidence": [
                    {"zero_citation_count": len(zero_cit), "total": len(papers)},
                ],
            })

        # Self-citation ratio from profile
        self_cit_ratio = author_profile.get("self_citation_ratio", 0)
        if self_cit_ratio > 0.30:
            flags.append({
                "rule_id": "C04",
                "rule_name": "自引率偏高",
                "severity": "medium",
                "confidence": "L3",
                "description": f"自引率 {self_cit_ratio*100:.1f}%，超过正常阈值（15-20%）",
                "evidence": [{"self_citation_ratio": self_cit_ratio}],
            })

        return flags

    def classify_author_position_pattern(self, papers: list) -> list[dict]:
        """Flag unusual author position patterns (e.g., always last author, never first)."""
        flags = []
        if len(papers) < 5:
            return flags

        positions = Counter()
        for p in papers:
            pos = p.get("author_position", "unknown")
            if pos:
                positions[pos] += 1

        total = sum(positions.values())
        if total == 0:
            return flags

        # Check: extremely low first-author rate (suggests gift authorship or senior-only)
        first_count = positions.get("first", 0)
        first_ratio = first_count / total
        if total >= 10 and first_ratio < 0.1:
            flags.append({
                "rule_id": "C05",
                "rule_name": "一作比例异常偏低",
                "severity": "low",
                "confidence": "L2",
                "description": (
                    f"一作论文仅 {first_count}/{total} 篇（{first_ratio*100:.0f}%），"
                    f"可能反映挂名或仅挂通讯作者身份"
                ),
                "evidence": [{"first_author_ratio": first_ratio, "position_distribution": dict(positions)}],
            })

        # Check: always last author in multi-author papers
        last_count = positions.get("last", 0)
        multi_author = [p for p in papers if len(p.get("authors", [])) > 2]
        if multi_author and last_count / len(multi_author) > 0.9 and len(multi_author) >= 5:
            flags.append({
                "rule_id": "C05b",
                "rule_name": "通讯作者垄断",
                "severity": "low",
                "confidence": "L2",
                "description": (
                    f"多作者论文中 {last_count}/{len(multi_author)} 篇为末位作者，"
                    f"可能存在通讯作者身份滥用"
                ),
                "evidence": [{"last_author_ratio": last_count / len(multi_author)}],
            })

        return flags

    def classify_publication_burst(self, papers: list) -> list[dict]:
        """Flag sudden bursts in publication rate that deviate from career trend."""
        flags = []
        if len(papers) < 8:
            return flags

        year_counts = Counter()
        for p in papers:
            y = p.get("year")
            if isinstance(y, int):
                year_counts[y] += 1

        if len(year_counts) < 3:
            return flags

        sorted_years = sorted(year_counts.items())
        counts = [c for _, c in sorted_years]
        avg_count = sum(counts) / len(counts)

        # Find years with >3x average
        bursts = []
        for year, count in sorted_years:
            if count > avg_count * 3 and count >= 5:
                bursts.append((year, count))

        if bursts:
            flags.append({
                "rule_id": "C06",
                "rule_name": "发表量突增",
                "severity": "medium",
                "confidence": "L3",
                "description": (
                    f"检测到 {len(bursts)} 个发表量异常突增年份，"
                    f"最高为 {bursts[0][1]} 篇（年均 {avg_count:.1f} 篇的 "
                    f"{bursts[0][1]/avg_count:.1f} 倍）"
                ),
                "evidence": [{"year": y, "count": c} for y, c in bursts],
            })

        return flags

    def classify_h_index_anomaly(self, author_profile: dict, years_active: int) -> list[dict]:
        """Flag h-index that is inconsistent with years of activity."""
        flags = []
        h_index = author_profile.get("h_index", 0)
        if not h_index or years_active <= 0:
            return flags

        # Find expected range
        expected_min = 0
        expected_max = 0
        for yr, (mn, mx) in sorted(_H_INDEX_BASELINE.items()):
            if years_active >= yr:
                expected_min = mn
                expected_max = mx

        if expected_max > 0:
            if h_index > expected_max * 2:
                flags.append({
                    "rule_id": "C07",
                    "rule_name": "h-index异常偏高",
                    "severity": "medium",
                    "confidence": "L3",
                    "description": (
                        f"h-index {h_index}，远超从业 {years_active} 年的正常预期 "
                        f"({expected_min}-{expected_max})"
                    ),
                    "evidence": [
                        {"h_index": h_index, "years_active": years_active,
                         "expected_range": [expected_min, expected_max]},
                    ],
                })
            elif h_index < expected_min * 0.3 and years_active >= 10:
                flags.append({
                    "rule_id": "C07b",
                    "rule_name": "h-index异常偏低",
                    "severity": "low",
                    "confidence": "L2",
                    "description": (
                        f"h-index {h_index}，低于从业 {years_active} 年的正常预期 "
                        f"({expected_min}-{expected_max})"
                    ),
                    "evidence": [
                        {"h_index": h_index, "years_active": years_active,
                         "expected_range": [expected_min, expected_max]},
                    ],
                })

        return flags


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Common heuristics classifier")
    parser.add_argument("--papers", "-p", required=True, help="Path to papers JSON")
    parser.add_argument("--profile", help="Path to author profile JSON")
    parser.add_argument("--discipline", "-d", default="computer_science")
    parser.add_argument("--years", "-y", type=int, default=10)
    parser.add_argument("--output", "-o", help="Output JSON file")
    args = parser.parse_args()

    with open(args.papers, "r", encoding="utf-8") as f:
        papers = json.load(f)

    profile = {}
    if args.profile:
        with open(args.profile, "r", encoding="utf-8") as f:
            profile = json.load(f)

    classifier = CommonHeuristicsClassifier()
    flags = classifier.classify(papers, profile, args.discipline, args.years)

    result = {"total_papers": len(papers), "flags": flags, "flag_count": len(flags)}
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info("Saved to: %s", args.output)


if __name__ == "__main__":
    main()
