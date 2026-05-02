#!/usr/bin/env python3
"""Tests for international/scholar_data_builder.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from international.scholar_data_builder import build_international_scholar_data


class TestBuildInternationalScholarData:
    def test_basic_build(self):
        config = {
            "scholar": {
                "name": "Prof. Test",
                "institution": "MIT",
                "discipline": "computer_science",
            }
        }
        auto_data = {
            "author_profile": {
                "openalex": {"orcid": "0000-0001-2345-6789", "works_count": 42},
            },
            "papers": [
                {"title": "T1", "year": 2023, "journal": "Nature"},
                {"title": "T2", "year": 2022, "journal": "Science"},
            ],
            "source_metadata": {"openalex": {}},
            "metrics": {"h_index": 28, "total_citations": 1500},
        }
        result = build_international_scholar_data(config, auto_data)

        assert result["name"] == "Prof. Test"
        assert result["institution"] == "MIT"
        assert result["investigation_type"] == "international"
        assert result["basic_profile"]["orcid"] == "0000-0001-2345-6789"
        assert result["academic_outputs"]["verified_papers"] == 2
        assert result["quality_assessment"]["metrics_summary"]["h_index"] == 28

    def test_with_xiaohongshu_data(self):
        config = {"scholar": {"name": "Prof. Test", "institution": "MIT"}}
        auto_data = {
            "author_profile": {},
            "papers": [],
            "source_metadata": {},
            "metrics": {},
        }
        xhs = {"matched": True, "review_count": 5, "red_flags": []}
        result = build_international_scholar_data(config, auto_data, xhs)

        assert result["student_reviews"]["status"] == "loaded"
        assert result["student_reviews"]["xiaohongshu"]["matched"] is True
        assert result["confidence_ratings"]["student_reviews"] == "medium"

    def test_no_xiaohongshu(self):
        config = {"scholar": {"name": "Prof. Test", "institution": "MIT"}}
        auto_data = {"author_profile": {}, "papers": [], "source_metadata": {}, "metrics": {}}
        result = build_international_scholar_data(config, auto_data)

        assert result["student_reviews"]["status"] == "no_report_found"
        assert result["confidence_ratings"]["student_reviews"] == "low"

    def test_recent_3yr_papers(self):
        import datetime
        current_year = datetime.datetime.now().year
        config = {"scholar": {"name": "Prof. Test", "institution": "MIT"}}
        auto_data = {
            "author_profile": {},
            "papers": [
                {"title": "Recent", "year": current_year},
                {"title": "Old", "year": current_year - 5},
            ],
            "source_metadata": {},
            "metrics": {},
        }
        result = build_international_scholar_data(config, auto_data)
        assert result["academic_outputs"]["recent_3yr_papers"] == 1

    def test_collaborators_extracted(self):
        config = {"scholar": {"name": "Alice", "institution": "MIT"}}
        auto_data = {
            "author_profile": {},
            "papers": [],
            "source_metadata": {
                "openalex": {
                    "works": [
                        {"authorships": [
                            {"author_name": "Alice"},
                            {"author_name": "Bob"},
                            {"author_name": "Charlie"},
                        ]},
                        {"authorships": [
                            {"author_name": "Alice"},
                            {"author_name": "Bob"},
                        ]},
                    ]
                }
            },
            "metrics": {},
        }
        result = build_international_scholar_data(config, auto_data)
        collabs = result["relationship_network"]["collaborators"]
        assert len(collabs) == 2
        # Bob should have count 2
        bob = next(c for c in collabs if c["name"] == "Bob")
        assert bob["co_paper_count"] == 2

    def test_required_fields_present(self):
        config = {"scholar": {"name": "Test", "institution": "MIT"}}
        auto_data = {"author_profile": {}, "papers": [], "source_metadata": {}, "metrics": {}}
        result = build_international_scholar_data(config, auto_data)

        required = [
            "name", "institution", "investigation_date", "investigation_type",
            "basic_profile", "academic_outputs", "quality_assessment",
            "relationship_network", "anomalies", "confidence_ratings", "student_reviews",
        ]
        for field in required:
            assert field in result, f"Missing field: {field}"

    def test_metadata_fields(self):
        config = {"scholar": {"name": "Test", "institution": "MIT"}}
        auto_data = {"author_profile": {}, "papers": [], "source_metadata": {"openalex": {}}, "metrics": {}}
        result = build_international_scholar_data(config, auto_data)

        meta = result.get("metadata", {})
        assert "auto_fetched_at" in meta
        assert "sources_used" in meta
        assert meta["total_api_calls"] == 1
