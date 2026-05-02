#!/usr/bin/env python3
"""Tests for international/evaluator.py"""

import json
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from international.evaluator import InternationalEvaluator, _ANNUAL_OUTPUT_BENCHMARKS, _H_INDEX_BENCHMARKS, _TENURE_EXPECTATIONS


class TestEvaluateJournal:
    def test_top_tier_inference(self):
        ev = InternationalEvaluator()
        result = ev.evaluate_journal("Nature Communications")
        assert result["category"] == "top_tier"
        assert result["jcr_quartile"] == 1
        assert result["inference_method"] == "name_heuristic"

    def test_established_publisher(self):
        ev = InternationalEvaluator()
        result = ev.evaluate_journal("IEEE Conference on Computer Vision")
        assert result["category"] == "established_publisher"
        assert result["inference_method"] == "publisher_heuristic"

    def test_oa_publisher(self):
        ev = InternationalEvaluator()
        result = ev.evaluate_journal("Frontiers in Psychology")
        assert result["category"] == "open_access"
        assert result["inference_method"] == "publisher_heuristic"

    def test_unknown_journal(self):
        ev = InternationalEvaluator()
        result = ev.evaluate_journal("Some Unknown Journal XYZ")
        assert result["category"] == "unknown"
        assert result["jcr_quartile"] is None

    def test_cache_hit(self):
        ev = InternationalEvaluator()
        r1 = ev.evaluate_journal("Nature", "1234-5678")
        r2 = ev.evaluate_journal("Nature", "1234-5678")
        assert r1 == r2  # Should be cached


class TestEvaluateTenureBenchmark:
    def test_meets_expectations(self):
        ev = InternationalEvaluator()
        papers = [
            {"year": 2020, "author_position": "first", "jcr_quartile": 1, "citation_count": 50},
            {"year": 2021, "author_position": "first", "jcr_quartile": 1, "citation_count": 40},
            {"year": 2022, "author_position": "first", "jcr_quartile": 1, "citation_count": 30},
            {"year": 2023, "author_position": "first", "jcr_quartile": 2, "citation_count": 20},
            {"year": 2024, "author_position": "last", "jcr_quartile": 1, "citation_count": 10},
        ] * 4  # 20 papers
        result = ev.evaluate_tenure_benchmark(papers, years_since_phd=6, institution_tier="r1", field="computer_science")
        assert result["metrics"]["total_papers"] == 20
        assert result["metrics"]["q1_papers"] >= 3

    def test_gaps_detected(self):
        ev = InternationalEvaluator()
        papers = [
            {"year": 2020, "author_position": "last", "jcr_quartile": 3, "citation_count": 2},
        ] * 3
        result = ev.evaluate_tenure_benchmark(papers, years_since_phd=6, institution_tier="r1", field="computer_science")
        assert result["meets_expectations"] is False
        assert len(result["gaps"]) > 0

    def test_liberal_arts_lower_bar(self):
        ev = InternationalEvaluator()
        papers = [
            {"year": 2020, "author_position": "first", "jcr_quartile": 1, "citation_count": 10},
        ] * 8
        result = ev.evaluate_tenure_benchmark(papers, years_since_phd=6, institution_tier="liberal_arts", field="humanities")
        assert result["metrics"]["total_papers"] == 8


class TestEvaluateGrantPortfolio:
    def test_has_major_grant(self):
        ev = InternationalEvaluator()
        grants = [
            {"funding_agency": "NSF", "amount_usd": 600000},
        ]
        result = ev.evaluate_grant_portfolio(grants, "computer_science")
        assert result["has_major_grant"] is True
        assert result["total_funding_usd"] == 600000

    def test_no_grants(self):
        ev = InternationalEvaluator()
        result = ev.evaluate_grant_portfolio([], "humanities")
        assert result["total_funding_usd"] == 0
        assert result["assessment"] == "无已知基金项目"

    def test_funding_by_source(self):
        ev = InternationalEvaluator()
        grants = [
            {"funding_agency": "NSF", "amount_usd": 300000},
            {"funding_agency": "NSF", "amount_usd": 200000},
            {"funding_agency": "NIH", "amount_usd": 400000},
        ]
        result = ev.evaluate_grant_portfolio(grants, "life_sciences")
        assert result["funding_by_source"]["NSF"] == 500000
        assert result["funding_by_source"]["NIH"] == 400000


class TestEvaluatePaperDistribution:
    def test_concentration_high(self):
        ev = InternationalEvaluator()
        papers = [{"journal": "Same Journal", "year": 2020 + i % 3} for i in range(10)]
        result = ev.evaluate_paper_distribution(papers)
        assert result["concentration_risk"] == "high"

    def test_concentration_low(self):
        ev = InternationalEvaluator()
        papers = [{"journal": f"Journal {i}", "year": 2020 + i} for i in range(10)]
        result = ev.evaluate_paper_distribution(papers)
        assert result["concentration_risk"] == "low"

    def test_quartile_distribution(self):
        ev = InternationalEvaluator()
        papers = [
            {"journal": "J1", "year": 2020, "jcr_quartile": 1},
            {"journal": "J2", "year": 2020, "jcr_quartile": 2},
            {"journal": "J3", "year": 2021, "jcr_quartile": None},
        ]
        result = ev.evaluate_paper_distribution(papers)
        assert result["quartile_distribution"]["Q1"] == 1
        assert result["quartile_distribution"]["Q2"] == 1
        assert result["quartile_distribution"]["Unknown"] == 1
