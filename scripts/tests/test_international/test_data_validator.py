#!/usr/bin/env python3
"""Tests for international/data_validator.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from international.data_validator import validate, auto_fix, is_corruption_network


class TestValidate:
    def test_valid_data(self):
        data = {
            "name": "Prof. Test",
            "institution": "MIT",
            "investigation_date": "2024-01-01",
            "investigation_type": "international",
            "basic_profile": {
                "name": "Prof. Test",
                "institution": "MIT",
                "current_title": "Professor",
                "education_background": "PhD",
                "career_timeline": [],
            },
            "academic_outputs": {
                "claimed_papers": 50,
                "verified_papers": 45,
            },
            "quality_assessment": {"metrics_summary": {"h_index": 28}},
            "relationship_network": {},
            "anomalies": [],
            "confidence_ratings": {},
            "student_reviews": {},
        }
        errors, warnings = validate(data)
        assert errors == []

    def test_missing_required_fields(self):
        data = {"name": "Test"}
        errors, warnings = validate(data)
        missing = [e for e in errors if "MISSING" in e]
        assert len(missing) > 0
        assert any("investigation_date" in e for e in missing)

    def test_wrong_investigation_type(self):
        data = {
            "name": "Test",
            "institution": "MIT",
            "investigation_date": "2024-01-01",
            "investigation_type": "domestic",
            "basic_profile": {
                "name": "Test", "institution": "MIT", "current_title": "Prof",
                "education_background": "PhD", "career_timeline": [],
            },
            "academic_outputs": {},
            "quality_assessment": {},
            "relationship_network": {},
            "anomalies": [],
            "confidence_ratings": {},
            "student_reviews": {},
        }
        errors, warnings = validate(data)
        assert any("domestic" in w for w in warnings)

    def test_paper_discrepancy_red_flag(self):
        data = {
            "name": "Test", "institution": "MIT",
            "investigation_date": "2024-01-01", "investigation_type": "international",
            "basic_profile": {
                "name": "Test", "institution": "MIT", "current_title": "Prof",
                "education_background": "PhD", "career_timeline": [],
            },
            "academic_outputs": {
                "claimed_papers": 100,
                "verified_papers": 50,
            },
            "quality_assessment": {},
            "relationship_network": {},
            "anomalies": [],
            "confidence_ratings": {},
            "student_reviews": {},
        }
        errors, warnings = validate(data)
        assert any("50%" in w for w in warnings)

    def test_verified_gt_claimed(self):
        data = {
            "name": "Test", "institution": "MIT",
            "investigation_date": "2024-01-01", "investigation_type": "international",
            "basic_profile": {
                "name": "Test", "institution": "MIT", "current_title": "Prof",
                "education_background": "PhD", "career_timeline": [],
            },
            "academic_outputs": {
                "claimed_papers": 10,
                "verified_papers": 15,
            },
            "quality_assessment": {},
            "relationship_network": {},
            "anomalies": [],
            "confidence_ratings": {},
            "student_reviews": {},
        }
        errors, warnings = validate(data)
        assert any("verified_papers" in w for w in warnings)

    def test_zero_recent_papers(self):
        data = {
            "name": "Test", "institution": "MIT",
            "investigation_date": "2024-01-01", "investigation_type": "international",
            "basic_profile": {
                "name": "Test", "institution": "MIT", "current_title": "Prof",
                "education_background": "PhD", "career_timeline": [],
            },
            "academic_outputs": {
                "recent_3yr_papers": 0,
            },
            "quality_assessment": {},
            "relationship_network": {},
            "anomalies": [],
            "confidence_ratings": {},
            "student_reviews": {},
        }
        errors, warnings = validate(data)
        assert any("No papers" in w or "stagnation" in w for w in warnings)

    def test_xiaohongshu_red_flags(self):
        data = {
            "name": "Test", "institution": "MIT",
            "investigation_date": "2024-01-01", "investigation_type": "international",
            "basic_profile": {
                "name": "Test", "institution": "MIT", "current_title": "Prof",
                "education_background": "PhD", "career_timeline": [],
            },
            "academic_outputs": {},
            "quality_assessment": {},
            "relationship_network": {},
            "anomalies": [],
            "confidence_ratings": {},
            "student_reviews": {
                "xiaohongshu": {
                    "matched": True,
                    "red_flags": [{"issue": "A"}, {"issue": "B"}, {"issue": "C"}],
                }
            },
        }
        errors, warnings = validate(data)
        assert any("red flags" in w for w in warnings)

    def test_missing_orcid_warning(self):
        data = {
            "name": "Test", "institution": "MIT",
            "investigation_date": "2024-01-01", "investigation_type": "international",
            "basic_profile": {
                "name": "Test", "institution": "MIT", "current_title": "Prof",
                "education_background": "PhD", "career_timeline": [],
                "orcid": "",
            },
            "academic_outputs": {},
            "quality_assessment": {},
            "relationship_network": {},
            "anomalies": [],
            "confidence_ratings": {},
            "student_reviews": {},
        }
        errors, warnings = validate(data)
        assert any("ORCID" in w for w in warnings)


class TestAutoFix:
    def test_adds_missing_fields(self):
        data = {"name": "Test"}
        fixed = auto_fix(data)
        assert "investigation_date" in fixed
        assert fixed["investigation_type"] == "international"
        assert "basic_profile" in fixed

    def test_fills_profile_defaults(self):
        data = {"name": "Test", "basic_profile": {}}
        fixed = auto_fix(data)
        assert fixed["basic_profile"]["education_background"] == "[TO BE FILLED]"
        assert fixed["basic_profile"]["career_timeline"] == "[TO BE FILLED]"

    def test_preserves_existing_values(self):
        data = {
            "name": "Test",
            "investigation_type": "cross_border",
            "basic_profile": {"name": "Test", "education_background": "PhD MIT"},
        }
        fixed = auto_fix(data)
        assert fixed["investigation_type"] == "cross_border"
        assert fixed["basic_profile"]["education_background"] == "PhD MIT"


class TestIsCorruptionNetwork:
    def test_true_for_network(self):
        data = {"network_name": "Test", "nodes": [{"id": 1}]}
        assert is_corruption_network(data) is True

    def test_false_for_scholar(self):
        data = {"name": "Test", "institution": "MIT"}
        assert is_corruption_network(data) is False

    def test_false_for_non_dict(self):
        assert is_corruption_network("string") is False
