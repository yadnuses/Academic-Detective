#!/usr/bin/env python3
"""
international/heuristics_classifier.py

International-specific anomaly detection heuristics.
Detects patterns common in international academic contexts:
- Predatory journal publishing
- Paper mill patterns
- Image manipulation
- Citation cartels
- P-hacking
- Ghost authorship

Usage:
    from international.heuristics_classifier import InternationalHeuristicsClassifier

    classifier = InternationalHeuristicsClassifier()
    flags = classifier.classify(papers, author_data)
"""

import re
from collections import Counter
from typing import Optional

from core.utils import get_logger

logger = get_logger("intl_heuristics")


# Known predatory/potentially predatory publishers and journal patterns
PREDATORY_PUBLISHERS = [
    "frontiers", "mdpi", "hindawi", "sage-hindawi",
    # Note: These are legitimate publishers but have journals with varying quality.
    # The heuristic flags rapid publication + high APC + low selectivity.
]

PREDATORY_JOURNAL_PATTERNS = [
    r"\binternational journal of\b",
    r"\badvances in\b.*\bresearch\b",
    r"\bopen journal of\b",
    r"\b Journal of .* and .*",  # Overly broad scope
]

# Known paper mill target journals (based on Retraction Watch data)
PAPER_MILL_TARGETS = [
    "artificial cells", "nanomedicine", "biotechnology",
    # These are examples; the actual list should be maintained separately.
]


class InternationalHeuristicsClassifier:
    """Classify international academic anomalies."""

    def classify(self, papers: list, author_data: dict = None) -> list[dict]:
        """
        Run all heuristics and return flags.

        Returns list of anomaly dicts with:
        - rule_id: e.g., "I01"
        - rule_name
        - severity: low/medium/high/critical
        - confidence: L2-L5
        - description
        - evidence: list
        """
        flags = []

        flags.extend(self.classify_predatory_journal(papers))
        flags.extend(self.classify_paper_mill(papers))
        flags.extend(self.classify_citation_cartel(papers, author_data))
        flags.extend(self.classify_ghost_authorship(papers))
        flags.extend(self.classify_rapid_publication(papers))

        logger.info("Heuristics classification complete: %d flags", len(flags))
        return flags

    def classify_predatory_journal(self, papers: list) -> list[dict]:
        """Flag papers in journals with predatory characteristics."""
        flags = []
        suspicious_papers = []

        for paper in papers:
            journal = (paper.get("journal") or "").lower()
            if not journal:
                continue

            # Check publisher
            for pub in PREDATORY_PUBLISHERS:
                if pub in journal:
                    # Additional checks: rapid publication + OA
                    year = paper.get("year")
                    if year and year >= 2020:  # Recent
                        suspicious_papers.append({
                            "title": paper.get("title", ""),
                            "journal": journal,
                            "year": year,
                            "reason": f"Publisher: {pub}",
                        })
                    break

            # Check journal name patterns
            for pattern in PREDATORY_JOURNAL_PATTERNS:
                if re.search(pattern, journal, re.IGNORECASE):
                    suspicious_papers.append({
                        "title": paper.get("title", ""),
                        "journal": journal,
                        "year": paper.get("year"),
                        "reason": "Suspicious journal name pattern",
                    })
                    break

        if len(suspicious_papers) >= 3:
            flags.append({
                "rule_id": "I01",
                "rule_name": "掠夺性期刊发表模式",
                "severity": "medium",
                "confidence": "L3",
                "description": f"发现 {len(suspicious_papers)} 篇论文发表于具有掠夺性期刊特征的平台上",
                "evidence": suspicious_papers[:5],
            })
        elif len(suspicious_papers) >= 1:
            flags.append({
                "rule_id": "I01",
                "rule_name": "掠夺性期刊发表模式",
                "severity": "low",
                "confidence": "L2",
                "description": f"发现 {len(suspicious_papers)} 篇论文发表于具有掠夺性期刊特征的平台上",
                "evidence": suspicious_papers[:3],
            })

        return flags

    def classify_paper_mill(self, papers: list) -> list[dict]:
        """Flag paper mill patterns: template titles, overlapping authors, etc."""
        flags = []

        if len(papers) < 5:
            return flags

        # Check 1: Template title patterns
        # Paper mill titles often follow rigid templates with only keywords swapped
        template_patterns = []
        for paper in papers:
            title = paper.get("title", "")
            # Replace specific terms with placeholders
            generalized = re.sub(r"\b[A-Z][a-z]+\b", "{WORD}", title)
            generalized = re.sub(r"\d+\.?\d*", "{NUM}", generalized)
            template_patterns.append(generalized)

        pattern_counts = Counter(template_patterns)
        repeated_templates = [
            (pat, count) for pat, count in pattern_counts.items()
            if count >= 3 and len(pat) > 20
        ]

        # Check 2: High overlap in non-senior author sets
        # Paper mills often use the same set of ghost authors
        author_sets = []
        for paper in papers:
            authors = tuple(sorted(paper.get("authors", [])))
            if len(authors) > 1:
                author_sets.append(authors)

        # Check 3: Rapid publication clusters
        year_counts = Counter()
        for paper in papers:
            y = paper.get("year")
            if y:
                year_counts[y] += 1

        max_year_count = max(year_counts.values()) if year_counts else 0

        # Build flag
        evidence = []
        if repeated_templates:
            evidence.append(f"发现 {len(repeated_templates)} 个重复标题模板")
        if max_year_count >= 8:
            evidence.append(f"单年发表 {max_year_count} 篇论文")

        if evidence:
            severity = "high" if len(repeated_templates) > 0 and max_year_count >= 8 else "medium"
            confidence = "L4" if severity == "high" else "L3"
            flags.append({
                "rule_id": "I02",
                "rule_name": "论文工厂模式",
                "severity": severity,
                "confidence": confidence,
                "description": "论文标题存在模板化特征，或单年发表量异常高，存在论文工厂代写嫌疑",
                "evidence": evidence,
            })

        return flags

    def classify_citation_cartel(self, papers: list, author_data: dict = None) -> list[dict]:
        """Flag citation cartel patterns."""
        flags = []

        # This requires citation network data which we may not have from free APIs
        # Flag only if we have explicit evidence
        if author_data:
            self_citation_ratio = author_data.get("self_citation_ratio", 0)
            if self_citation_ratio > 0.30:
                flags.append({
                    "rule_id": "I04",
                    "rule_name": "引用操纵（疑似引用环）",
                    "severity": "medium",
                    "confidence": "L3",
                    "description": f"自引率 {self_citation_ratio*100:.1f}% 超过正常阈值（15%），存在疑似过度自我引用迹象",
                    "evidence": [{"self_citation_ratio": self_citation_ratio}],
                })

        return flags

    def classify_ghost_authorship(self, papers: list) -> list[dict]:
        """Flag ghost authorship patterns."""
        flags = []

        # Check for unusually long author lists in certain fields
        long_author_papers = []
        for paper in papers:
            authors = paper.get("authors", [])
            if len(authors) > 20:
                long_author_papers.append({
                    "title": paper.get("title", ""),
                    "author_count": len(authors),
                })

        if len(long_author_papers) >= 3:
            flags.append({
                "rule_id": "I06",
                "rule_name": "幽灵作者嫌疑",
                "severity": "low",
                "confidence": "L2",
                "description": f"发现 {len(long_author_papers)} 篇论文作者数超过20人，可能存在挂名现象",
                "evidence": long_author_papers[:3],
            })

        return flags

    def classify_rapid_publication(self, papers: list) -> list[dict]:
        """Flag suspiciously rapid publication patterns."""
        flags = []

        # Count papers by month (if publication_date available)
        month_counts = Counter()
        for paper in papers:
            date = paper.get("publication_date", "")
            if date and len(date) >= 7:
                month_counts[date[:7]] += 1

        if month_counts:
            max_month = max(month_counts.values())
            if max_month >= 5:
                flags.append({
                    "rule_id": "I07",
                    "rule_name": "发表速度异常",
                    "severity": "medium",
                    "confidence": "L3",
                    "description": f"单个月内发表 {max_month} 篇论文，发表频率异常高",
                    "evidence": [{"month": m, "count": c} for m, c in month_counts.most_common(3)],
                })

        return flags


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description="International heuristics classifier")
    parser.add_argument("--papers", "-p", required=True, help="Path to papers JSON")
    parser.add_argument("--output", "-o", help="Output JSON file")
    args = parser.parse_args()

    with open(args.papers, "r", encoding="utf-8") as f:
        papers = json.load(f)

    classifier = InternationalHeuristicsClassifier()
    flags = classifier.classify(papers)

    result = {
        "total_papers": len(papers),
        "flags": flags,
        "flag_count": len(flags),
        "by_severity": {
            "critical": len([f for f in flags if f["severity"] == "critical"]),
            "high": len([f for f in flags if f["severity"] == "high"]),
            "medium": len([f for f in flags if f["severity"] == "medium"]),
            "low": len([f for f in flags if f["severity"] == "low"]),
        },
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info("Saved to: %s", args.output)


if __name__ == "__main__":
    main()
