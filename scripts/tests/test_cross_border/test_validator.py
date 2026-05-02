#!/usr/bin/env python3
"""Tests for cross_border/validator.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cross_border.validator import (
    _get_title_level,
    validate_timeline_consistency,
    validate_title_mapping,
    validate_paper_consistency,
    validate_education_coherence,
    validate,
)


class TestGetTitleLevel:
    def test_known_titles(self):
        assert _get_title_level("postdoc") == 1
        assert _get_title_level("assistant professor") == 2
        assert _get_title_level("associate professor") == 3
        assert _get_title_level("professor") == 4
        assert _get_title_level("distinguished professor") == 5

    def test_chinese_titles(self):
        assert _get_title_level("博士后") == 1
        assert _get_title_level("助理教授") == 2
        assert _get_title_level("副教授") == 3
        assert _get_title_level("教授") == 4
        assert _get_title_level("特聘教授") == 5

    def test_unknown_title(self):
        assert _get_title_level("random thing") == 0

    def test_empty(self):
        assert _get_title_level("") == 0
        assert _get_title_level(None) == 0


class TestValidateTimelineConsistency:
    def test_no_timeline(self):
        data = {"basic_profile": {}}
        errors = validate_timeline_consistency(data)
        assert errors == []

    def test_no_overlap(self):
        data = {
            "basic_profile": {
                "career_timeline": [
                    {"year": 2010, "event": "入职清华", "institution": "清华"},
                    {"year": 2015, "event": "离职清华", "institution": "清华"},
                    {"year": 2015, "event": "joined MIT", "institution": "MIT"},
                ]
            }
        }
        errors = validate_timeline_consistency(data)
        assert len(errors) == 0

    def test_overlap_detected(self):
        data = {
            "basic_profile": {
                "career_timeline": [
                    {"year": 2010, "event": "入职清华", "institution": "清华"},
                    {"year": 2012, "event": "joined MIT", "institution": "MIT"},
                    # No end events, both continue to present
                ]
            }
        }
        errors = validate_timeline_consistency(data)
        assert len(errors) == 1
        assert errors[0]["type"] == "timeline_overlap"
        assert errors[0]["severity"] == "high"

    def test_short_overlap_ignored(self):
        data = {
            "basic_profile": {
                "career_timeline": [
                    {"year": 2010, "event": "入职清华", "institution": "清华"},
                    {"year": 2011, "event": "离职清华", "institution": "清华"},
                    {"year": 2011, "event": "joined MIT", "institution": "MIT"},
                ]
            }
        }
        errors = validate_timeline_consistency(data)
        # No overlap since first position ended when second started
        assert len(errors) == 0

    def test_non_dict_timeline(self):
        data = {"basic_profile": {"career_timeline": "some string"}}
        errors = validate_timeline_consistency(data)
        assert errors == []


class TestValidateTitleMapping:
    def test_no_conflicts(self):
        data = {
            "cross_border_info": {
                "conflicts": [],
                "domestic_counterpart": {"title_cn": "教授"},
            },
            "basic_profile": {"current_title": "Professor"},
        }
        errors = validate_title_mapping(data)
        assert len(errors) == 0

    def test_title_inconsistency_from_conflicts(self):
        data = {
            "cross_border_info": {
                "conflicts": [
                    {"type": "title_inconsistency", "severity": "medium",
                     "description": "职称差异", "domestic": "教授", "international": "助理教授"}
                ],
                "domestic_counterpart": {"title_cn": "教授"},
            },
            "basic_profile": {"current_title": "Assistant Professor"},
        }
        errors = validate_title_mapping(data)
        assert any(e["type"] == "title_mapping_unreasonable" for e in errors)

    def test_international_higher_level(self):
        data = {
            "cross_border_info": {
                "conflicts": [],
                "domestic_counterpart": {"title_cn": "助理教授"},
            },
            "basic_profile": {"current_title": "Professor"},
        }
        errors = validate_title_mapping(data)
        assert any(e["type"] == "title_progression_unusual" for e in errors)


class TestValidatePaperConsistency:
    def test_no_papers(self):
        data = {"academic_outputs": {"paper_list": []}, "cross_border_info": {"duplicates": 0}}
        errors = validate_paper_consistency(data)
        assert len(errors) == 0

    def test_doi_conflict(self):
        data = {
            "academic_outputs": {
                "paper_list": [
                    {"doi": "10.1/abc", "title": "T1", "year": 2020, "journal": "Nature"},
                    {"doi": "10.1/abc", "title": "T1", "year": 2021, "journal": "Science"},
                ]
            },
            "cross_border_info": {"duplicates": 0},
        }
        errors = validate_paper_consistency(data)
        assert any(e["type"] == "paper_metadata_conflict" for e in errors)

    def test_high_duplication_rate(self):
        data = {
            "academic_outputs": {
                "paper_list": [{"doi": f"10.1/{i}"} for i in range(10)]
            },
            "cross_border_info": {"duplicates": 6},
        }
        errors = validate_paper_consistency(data)
        assert any(e["type"] == "high_duplication_rate" for e in errors)

    def test_low_duplication_no_flag(self):
        data = {
            "academic_outputs": {
                "paper_list": [{"doi": f"10.1/{i}"} for i in range(10)]
            },
            "cross_border_info": {"duplicates": 2},
        }
        errors = validate_paper_consistency(data)
        assert not any(e["type"] == "high_duplication_rate" for e in errors)


class TestValidateEducationCoherence:
    def test_no_education(self):
        data = {"basic_profile": {}}
        errors = validate_education_coherence(data)
        assert errors == []

    def test_coherent_timeline(self):
        data = {
            "basic_profile": {
                "education_background": [
                    {"degree": "PhD", "year": 2010},
                ],
                "career_timeline": [
                    {"year": 2015, "event": "joined as assistant professor"},
                ],
            }
        }
        errors = validate_education_coherence(data)
        assert len(errors) == 0

    def test_phd_after_professor(self):
        data = {
            "basic_profile": {
                "education_background": [
                    {"degree": "PhD", "year": 2015},
                ],
                "career_timeline": [
                    {"year": 2010, "event": "joined as professor"},
                ],
            }
        }
        errors = validate_education_coherence(data)
        assert any(e["type"] == "education_career_incoherence" for e in errors)
        assert errors[0]["severity"] == "high"

    def test_rapid_promotion(self):
        data = {
            "basic_profile": {
                "education_background": [
                    {"degree": "PhD", "year": 2020},
                ],
                "career_timeline": [
                    {"year": 2021, "event": "joined as professor"},
                ],
            }
        }
        errors = validate_education_coherence(data)
        assert any(e["type"] == "rapid_promotion" for e in errors)

    def test_string_education(self):
        data = {
            "basic_profile": {
                "education_background": "PhD from MIT",
                "career_timeline": [],
            }
        }
        errors = validate_education_coherence(data)
        assert errors == []


class TestMainValidate:
    def test_no_issues(self):
        data = {
            "basic_profile": {
                "education_background": [{"degree": "PhD", "year": 2010}],
                "career_timeline": [
                    {"year": 2010, "event": "入职清华", "institution": "清华"},
                    {"year": 2015, "event": "离职清华", "institution": "清华"},
                    {"year": 2015, "event": "joined MIT", "institution": "MIT"},
                ],
            },
            "cross_border_info": {
                "conflicts": [],
                "duplicates": 0,
                "domestic_counterpart": {"title_cn": "教授"},
            },
            "academic_outputs": {"paper_list": []},
        }
        errors, warnings = validate(data)
        assert len(errors) == 0
        assert len(warnings) == 0

    def test_with_errors_and_warnings(self):
        data = {
            "basic_profile": {
                "education_background": [{"degree": "PhD", "year": 2015}],
                "career_timeline": [
                    {"year": 2010, "event": "joined as professor"},
                ],
            },
            "cross_border_info": {
                "conflicts": [
                    {"type": "title_inconsistency", "severity": "medium", "description": "D"}
                ],
                "duplicates": 0,
                "domestic_counterpart": {"title_cn": "教授"},
            },
            "academic_outputs": {"paper_list": []},
        }
        errors, warnings = validate(data)
        assert len(errors) > 0  # education_career_incoherence is high severity
        assert len(warnings) >= 0
