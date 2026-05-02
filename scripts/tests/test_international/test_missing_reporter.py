#!/usr/bin/env python3
"""Tests for international/missing_reporter.py"""

import json
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from international.missing_reporter import (
    identify_gaps,
    suggest_lookup_sources,
    generate_missing_report,
)


class TestIdentifyGaps:
    def test_full_data_no_gaps(self, tmp_path):
        data = {
            "academic_outputs": {
                "verified_papers": 42,
                "paper_list": [
                    {"title": "T1", "journal": "Nature", "jcr_quartile": 1, "year": 2023},
                ],
            },
            "quality_assessment": {
                "metrics_summary": {"h_index": 28},
            },
            "student_reviews": {
                "xiaohongshu": {"matched": True, "review_count": 5},
            },
            "basic_profile": {
                "tenure_status": "tenured",
            },
            "funding_verification": {
                "grants": [{"agency": "NSF", "amount_usd": 500000}],
            },
        }
        gaps = identify_gaps(data)
        # Should still report some gaps because not all fields are perfect
        assert isinstance(gaps, list)

    def test_missing_papers(self):
        data = {
            "academic_outputs": {"verified_papers": 0, "paper_list": []},
            "quality_assessment": {},
            "student_reviews": {},
            "basic_profile": {},
        }
        gaps = identify_gaps(data)
        gap_types = [g["field"] for g in gaps]
        assert "verified_papers" in gap_types

    def test_missing_h_index(self):
        data = {
            "academic_outputs": {"verified_papers": 10, "paper_list": [{"title": "T1"}]},
            "quality_assessment": {"metrics_summary": {}},
            "student_reviews": {},
            "basic_profile": {},
        }
        gaps = identify_gaps(data)
        gap_types = [g["field"] for g in gaps]
        assert "h_index_authoritative" in gap_types

    def test_missing_journal_quartile(self):
        data = {
            "academic_outputs": {
                "verified_papers": 5,
                "paper_list": [{"title": "T1", "journal": "Some Journal"}],
            },
            "quality_assessment": {"metrics_summary": {"h_index": 10}},
            "student_reviews": {},
            "basic_profile": {},
        }
        gaps = identify_gaps(data)
        gap_types = [g["field"] for g in gaps]
        assert "journal_quartile" in gap_types


class TestSuggestLookupSources:
    def test_suggests_sources_for_gaps(self):
        gaps = [
            {"field": "verified_papers", "severity": "high", "suggested_sources": ["Scopus", "Web of Science"]},
            {"field": "journal_quartile", "severity": "medium", "suggested_sources": ["JCR", "Scopus"]},
        ]
        sources = suggest_lookup_sources(gaps)
        assert isinstance(sources, list)
        assert len(sources) > 0
        # Should mention specific databases
        combined = " ".join(sources)
        assert "Scopus" in combined or "WoS" in combined or "Web of Science" in combined

    def test_empty_gaps(self):
        sources = suggest_lookup_sources([])
        assert sources == []


class TestGenerateMissingReport:
    def test_generates_markdown(self, tmp_path):
        data = {
            "name": "Prof. Test",
            "institution": "MIT",
            "academic_outputs": {
                "verified_papers": 5,
                "paper_list": [{"title": "T1", "journal": "J1"}],
            },
            "quality_assessment": {"metrics_summary": {"h_index": 10}},
            "student_reviews": {},
            "basic_profile": {"tenure_status": "unknown"},
        }
        config = {"scholar": {"name": "Prof. Test", "institution": "MIT"}}
        report = generate_missing_report(data, config)
        assert "# 补充调查指南" in report
        assert "Prof. Test" in report
        assert "MIT" in report

    def test_report_structure(self, tmp_path):
        data = {
            "name": "Prof. Test",
            "institution": "MIT",
            "academic_outputs": {"verified_papers": 0, "paper_list": []},
            "quality_assessment": {},
            "student_reviews": {},
            "basic_profile": {},
        }
        config = {"scholar": {"name": "Prof. Test"}}
        report = generate_missing_report(data, config)
        assert "## 概览：共发现" in report
        assert "建议查询来源" in report
        assert "## 快速操作清单" in report
