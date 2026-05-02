#!/usr/bin/env python3
"""Tests for analysis/common_heuristics.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from analysis.common_heuristics import CommonHeuristicsClassifier, HeuristicRule


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------

def _make_papers(count: int, year: int = 2020, journal: str = "Nature", **kwargs):
    """Generate a list of paper dicts."""
    papers = []
    for i in range(count):
        p = {
            "title": f"Paper {i}",
            "year": year,
            "journal": journal,
            "authors": ["A", "B", "C"],
            "citation_count": kwargs.get("citation_count", 10),
            "author_position": kwargs.get("author_position", "first"),
        }
        papers.append(p)
    return papers


# ---------------------------------------------------------------------------
# classify_output_quantity (C01)
# ---------------------------------------------------------------------------

class TestClassifyOutputQuantity:
    def test_no_papers(self):
        classifier = CommonHeuristicsClassifier()
        flags = classifier.classify_output_quantity([], "computer_science", 10)
        assert flags == []

    def test_zero_years(self):
        classifier = CommonHeuristicsClassifier()
        flags = classifier.classify_output_quantity(
            _make_papers(5), "computer_science", 0
        )
        assert flags == []

    def test_normal_output_no_flag(self):
        classifier = CommonHeuristicsClassifier()
        # 20 papers over 10 years = 2/year, within CS range (2-6)
        flags = classifier.classify_output_quantity(
            _make_papers(20, year=2020), "computer_science", 10
        )
        assert len(flags) == 0

    def test_high_output_flag(self):
        classifier = CommonHeuristicsClassifier()
        # 120 papers over 5 years = 24/year, > 2x CS max (6*2=12)
        flags = classifier.classify_output_quantity(
            _make_papers(120, year=2020), "computer_science", 5
        )
        assert len(flags) == 1
        assert flags[0]["rule_id"] == "C01"
        assert flags[0]["severity"] == "medium"
        assert "异常偏高" in flags[0]["rule_name"]

    def test_low_output_flag(self):
        classifier = CommonHeuristicsClassifier()
        # 1 paper over 10 years = 0.1/year, < 0.3x CS min (2*0.3=0.6)
        flags = classifier.classify_output_quantity(
            _make_papers(1, year=2020), "computer_science", 10
        )
        assert len(flags) == 1
        assert flags[0]["rule_id"] == "C01"
        assert "异常偏低" in flags[0]["rule_name"]
        assert flags[0]["severity"] == "low"

    def test_unknown_discipline_uses_default(self):
        classifier = CommonHeuristicsClassifier()
        # 20 papers / 10 years = 2/year, default range (1-5), no flag
        flags = classifier.classify_output_quantity(
            _make_papers(20, year=2020), "unknown_field", 10
        )
        assert len(flags) == 0


# ---------------------------------------------------------------------------
# classify_journal_concentration (C02)
# ---------------------------------------------------------------------------

class TestClassifyJournalConcentration:
    def test_few_papers_no_flag(self):
        classifier = CommonHeuristicsClassifier()
        papers = _make_papers(4, journal="Nature")
        flags = classifier.classify_journal_concentration(papers)
        assert flags == []

    def test_high_concentration(self):
        classifier = CommonHeuristicsClassifier()
        papers = _make_papers(12, journal="Same Journal")
        flags = classifier.classify_journal_concentration(papers)
        assert len(flags) == 1
        assert flags[0]["rule_id"] == "C02"
        assert flags[0]["severity"] == "medium"
        assert "集中度异常" in flags[0]["rule_name"]
        assert 0.99 < flags[0]["evidence"][0]["concentration"] <= 1.0

    def test_moderate_concentration(self):
        classifier = CommonHeuristicsClassifier()
        papers = (
            _make_papers(5, journal="Journal A")
            + _make_papers(5, journal="Journal B")
        )
        flags = classifier.classify_journal_concentration(papers)
        assert len(flags) == 1
        assert flags[0]["rule_id"] == "C02"
        assert flags[0]["severity"] == "low"

    def test_diverse_journals_no_flag(self):
        classifier = CommonHeuristicsClassifier()
        papers = [ {"title": f"P{i}", "journal": f"Journal {i}"} for i in range(10) ]
        flags = classifier.classify_journal_concentration(papers)
        assert flags == []


# ---------------------------------------------------------------------------
# classify_citation_pattern (C03, C04)
# ---------------------------------------------------------------------------

class TestClassifyCitationPattern:
    def test_insufficient_papers(self):
        classifier = CommonHeuristicsClassifier()
        flags = classifier.classify_citation_pattern(
            _make_papers(2, citation_count=0), {}
        )
        assert flags == []

    def test_zero_citation_flag(self):
        classifier = CommonHeuristicsClassifier()
        papers = _make_papers(15, citation_count=0)
        flags = classifier.classify_citation_pattern(papers, {})
        assert len(flags) == 1
        assert flags[0]["rule_id"] == "C03"
        assert "零引用" in flags[0]["rule_name"]

    def test_normal_citations_no_flag(self):
        classifier = CommonHeuristicsClassifier()
        papers = _make_papers(15, citation_count=20)
        flags = classifier.classify_citation_pattern(papers, {})
        assert len(flags) == 0

    def test_self_citation_flag(self):
        classifier = CommonHeuristicsClassifier()
        papers = _make_papers(5, citation_count=10)
        profile = {"self_citation_ratio": 0.35}
        flags = classifier.classify_citation_pattern(papers, profile)
        assert len(flags) == 1
        assert flags[0]["rule_id"] == "C04"
        assert "自引率" in flags[0]["rule_name"]
        assert flags[0]["severity"] == "medium"

    def test_normal_self_citation_no_flag(self):
        classifier = CommonHeuristicsClassifier()
        papers = _make_papers(5, citation_count=10)
        profile = {"self_citation_ratio": 0.15}
        flags = classifier.classify_citation_pattern(papers, profile)
        assert len(flags) == 0


# ---------------------------------------------------------------------------
# classify_author_position_pattern (C05)
# ---------------------------------------------------------------------------

class TestClassifyAuthorPositionPattern:
    def test_few_papers_no_flag(self):
        classifier = CommonHeuristicsClassifier()
        papers = [{"title": "P1", "author_position": "first"} for _ in range(4)]
        flags = classifier.classify_author_position_pattern(papers)
        assert flags == []

    def test_low_first_author_ratio(self):
        classifier = CommonHeuristicsClassifier()
        papers = [
            {"title": f"P{i}", "author_position": "last", "authors": ["A", "B", "C"]}
            for i in range(15)
        ]
        flags = classifier.classify_author_position_pattern(papers)
        rule_ids = [f["rule_id"] for f in flags]
        assert "C05" in rule_ids
        assert "一作比例异常偏低" in flags[0]["rule_name"]

    def test_last_author_monopoly(self):
        classifier = CommonHeuristicsClassifier()
        papers = [
            {"title": f"P{i}", "author_position": "last", "authors": ["A", "B", "C"]}
            for i in range(8)
        ]
        flags = classifier.classify_author_position_pattern(papers)
        # Should also flag C05b if >90% multi-author papers are last author
        rule_ids = [f["rule_id"] for f in flags]
        assert "C05b" in rule_ids

    def test_normal_positions_no_flag(self):
        classifier = CommonHeuristicsClassifier()
        papers = [
            {"title": f"P{i}", "author_position": "first" if i % 2 == 0 else "last", "authors": ["A", "B", "C"]}
            for i in range(12)
        ]
        flags = classifier.classify_author_position_pattern(papers)
        assert len(flags) == 0


# ---------------------------------------------------------------------------
# classify_publication_burst (C06)
# ---------------------------------------------------------------------------

class TestClassifyPublicationBurst:
    def test_insufficient_papers(self):
        classifier = CommonHeuristicsClassifier()
        papers = [{"title": f"P{i}", "year": 2020 + i} for i in range(5)]
        flags = classifier.classify_publication_burst(papers)
        assert flags == []

    def test_no_burst(self):
        classifier = CommonHeuristicsClassifier()
        papers = [{"title": f"P{i}", "year": 2020 + i % 4} for i in range(12)]
        flags = classifier.classify_publication_burst(papers)
        assert len(flags) == 0

    def test_burst_detected(self):
        classifier = CommonHeuristicsClassifier()
        papers = []
        # Steady baseline: 1 paper per year for 5 years
        for y in range(2019, 2024):
            papers.append({"title": f"P{y}", "year": y})
        # Burst year: 10 papers
        for i in range(10):
            papers.append({"title": f"Burst{i}", "year": 2024})
        flags = classifier.classify_publication_burst(papers)
        assert len(flags) == 1
        assert flags[0]["rule_id"] == "C06"
        assert "突增" in flags[0]["rule_name"]


# ---------------------------------------------------------------------------
# classify_h_index_anomaly (C07)
# ---------------------------------------------------------------------------

class TestClassifyHIndexAnomaly:
    def test_no_h_index(self):
        classifier = CommonHeuristicsClassifier()
        flags = classifier.classify_h_index_anomaly({}, 10)
        assert flags == []

    def test_zero_years(self):
        classifier = CommonHeuristicsClassifier()
        flags = classifier.classify_h_index_anomaly({"h_index": 50}, 0)
        assert flags == []

    def test_high_h_index(self):
        classifier = CommonHeuristicsClassifier()
        # 10 years -> expected max 25, 2x = 50
        flags = classifier.classify_h_index_anomaly({"h_index": 60}, 10)
        assert len(flags) == 1
        assert flags[0]["rule_id"] == "C07"
        assert "偏高" in flags[0]["rule_name"]

    def test_low_h_index(self):
        classifier = CommonHeuristicsClassifier()
        # 10 years -> expected min 8, 0.3x = 2.4
        flags = classifier.classify_h_index_anomaly({"h_index": 1}, 10)
        assert len(flags) == 1
        assert flags[0]["rule_id"] == "C07b"
        assert "偏低" in flags[0]["rule_name"]

    def test_normal_h_index(self):
        classifier = CommonHeuristicsClassifier()
        flags = classifier.classify_h_index_anomaly({"h_index": 15}, 10)
        assert len(flags) == 0


# ---------------------------------------------------------------------------
# Main classify() integration
# ---------------------------------------------------------------------------

class TestMainClassify:
    def test_full_classification(self):
        classifier = CommonHeuristicsClassifier()
        # 120 papers / 5 years = 24/year, > 2x CS max (6*2=12) -> C01
        papers = _make_papers(120, year=2020, journal="Nature", citation_count=5)
        profile = {"h_index": 100, "self_citation_ratio": 0.40}
        flags = classifier.classify(papers, profile, "computer_science", 5)
        rule_ids = [f["rule_id"] for f in flags]
        # Should flag: C01 (high output), C02 (journal concentration), C04 (self-citation), C07 (h-index)
        assert "C01" in rule_ids
        assert "C02" in rule_ids
        assert "C04" in rule_ids
        assert "C07" in rule_ids

    def test_empty_input(self):
        classifier = CommonHeuristicsClassifier()
        flags = classifier.classify([], {}, "computer_science", 0)
        assert flags == []

    def test_returns_list_of_dicts(self):
        classifier = CommonHeuristicsClassifier()
        papers = _make_papers(20, year=2020, journal="Nature")
        flags = classifier.classify(papers, {}, "computer_science", 10)
        assert isinstance(flags, list)
        for f in flags:
            assert "rule_id" in f
            assert "rule_name" in f
            assert "severity" in f
            assert "confidence" in f
            assert "description" in f
            assert "evidence" in f
