#!/usr/bin/env python3
"""Tests for analysis/review_aggregator.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from analysis.review_aggregator import (
    merge_dimension_summaries,
    merge_leads,
    merge_anomalies,
    merge_overall_risk,
    aggregate_reviews,
    build_radar_from_summary,
)


class TestMergeDimensionSummaries:
    def test_single_source(self):
        sources = {
            "domestic": {
                "dimension_summary": {
                    "学术水平": {
                        "mention_count": 10,
                        "sentiment_distribution": {"positive": 8, "negative": 2},
                        "sample_quotes": ["很好"],
                    }
                }
            }
        }
        result = merge_dimension_summaries(sources)
        assert "学术水平" in result
        assert result["学术水平"]["mention_count"] == 10

    def test_multiple_sources_merge(self):
        sources = {
            "domestic": {
                "dimension_summary": {
                    "学术水平": {
                        "mention_count": 5,
                        "sentiment_distribution": {"positive": 4, "negative": 1},
                        "sample_quotes": ["A"],
                    }
                }
            },
            "xiaohongshu": {
                "dimension_summary": {
                    "graduation_difficulty_avg": 4.0,
                }
            },
        }
        result = merge_dimension_summaries(sources)
        assert "学术水平" in result
        assert "毕业难度" in result  # mapped from graduation_difficulty_avg
        assert result["学术水平"]["mention_count"] == 5

    def test_numeric_dimension(self):
        sources = {
            "xiaohongshu": {
                "dimension_summary": {
                    "workload_avg": 3.5,
                }
            }
        }
        result = merge_dimension_summaries(sources)
        assert "工作强度" in result
        assert result["工作强度"].get("numeric_value") == 3.5

    def test_empty_sources(self):
        result = merge_dimension_summaries({})
        assert result == {}


class TestMergeLeads:
    def test_single_source(self):
        sources = {
            "domestic": {
                "investigation_leads": [
                    {"id": "L1", "label": "压榨学生", "mention_count": 5, "severity": "high", "affected_reviews": 3}
                ]
            }
        }
        result = merge_leads(sources)
        assert len(result) == 1
        assert result[0]["id"] == "L1"

    def test_deduplicate_by_id(self):
        sources = {
            "domestic": {
                "investigation_leads": [
                    {"id": "L1", "label": "压榨", "mention_count": 3, "severity": "high", "affected_reviews": 2}
                ]
            },
            "xiaohongshu": {
                "investigation_leads": [
                    {"id": "L1", "label": "push", "mention_count": 2, "severity": "medium", "affected_reviews": 1}
                ]
            },
        }
        result = merge_leads(sources)
        assert len(result) == 1
        assert result[0]["mention_count"] == 5  # 3 + 2
        assert result[0]["severity"] == "high"  # upgraded

    def test_empty_leads(self):
        sources = {"domestic": {"investigation_leads": []}}
        result = merge_leads(sources)
        assert result == []

    def test_sort_by_severity(self):
        sources = {
            "domestic": {
                "investigation_leads": [
                    {"id": "L2", "label": "小问题", "mention_count": 1, "severity": "low", "affected_reviews": 1},
                    {"id": "L1", "label": "严重", "mention_count": 10, "severity": "critical", "affected_reviews": 5},
                ]
            }
        }
        result = merge_leads(sources)
        assert result[0]["severity"] == "critical"


class TestMergeAnomalies:
    def test_merge_unique(self):
        sources = {
            "domestic": {
                "cross_dimensional_anomalies": [
                    {"pattern": "P1", "description": "Desc1"}
                ]
            },
            "xiaohongshu": {
                "cross_dimensional_anomalies": [
                    {"pattern": "P2", "description": "Desc2"}
                ]
            },
        }
        result = merge_anomalies(sources)
        assert len(result) == 2

    def test_dedup_patterns(self):
        sources = {
            "domestic": {
                "cross_dimensional_anomalies": [
                    {"pattern": "P1", "description": "Desc1"}
                ]
            },
            "xiaohongshu": {
                "cross_dimensional_anomalies": [
                    {"pattern": "P1", "description": "Desc2"}  # same pattern
                ]
            },
        }
        result = merge_anomalies(sources)
        assert len(result) == 1

    def test_empty(self):
        assert merge_anomalies({}) == []


class TestMergeOverallRisk:
    def test_critical(self):
        sources = {
            "domestic": {"overall_risk_assessment": {"critical_leads": 1, "high_leads": 0, "medium_leads": 0}},
        }
        result = merge_overall_risk(sources)
        assert result["level"] == "critical"

    def test_high(self):
        sources = {
            "domestic": {"overall_risk_assessment": {"critical_leads": 0, "high_leads": 2, "medium_leads": 0}},
        }
        result = merge_overall_risk(sources)
        assert result["level"] == "high"

    def test_medium(self):
        sources = {
            "domestic": {"overall_risk_assessment": {"critical_leads": 0, "high_leads": 1, "medium_leads": 0}},
        }
        result = merge_overall_risk(sources)
        assert result["level"] == "medium"

    def test_low(self):
        sources = {
            "domestic": {"overall_risk_assessment": {"critical_leads": 0, "high_leads": 0, "medium_leads": 0}},
        }
        result = merge_overall_risk(sources)
        assert result["level"] == "low"

    def test_multi_source_sum(self):
        sources = {
            "a": {"overall_risk_assessment": {"critical_leads": 0, "high_leads": 1, "medium_leads": 2}},
            "b": {"overall_risk_assessment": {"critical_leads": 0, "high_leads": 1, "medium_leads": 1}},
        }
        result = merge_overall_risk(sources)
        assert result["high_leads"] == 2
        assert result["medium_leads"] == 3
        assert result["level"] == "high"


class TestAggregateReviews:
    def test_no_sources(self):
        result = aggregate_reviews({})
        assert result["matched"] is False
        assert result["status"] == "no_sources_loaded"

    def test_single_source(self):
        result = aggregate_reviews({
            "domestic": Path(__file__).parent.parent / "fixtures" / "valid_scholar.json",
        })
        # valid_scholar.json is not a review file, so it won't have review_count
        # This tests the loading path
        assert "status" in result

    def test_radar_from_numeric_dimension(self):
        dim_summary = {
            "毕业难度": {
                "numeric_value": 4.0,
                "mention_count": 5,
            }
        }
        radar = build_radar_from_summary(dim_summary)
        assert len(radar) == 1
        assert radar[0]["dimension"] == "毕业难度"
        assert radar[0]["score"] == 4.0
        assert radar[0]["max"] == 5

    def test_radar_from_sentiment(self):
        dim_summary = {
            "学术水平": {
                "mention_count": 10,
                "sentiment_distribution": {"positive": 7, "neutral": 2, "negative": 1},
                "dominant_sentiment": "positive",
            }
        }
        radar = build_radar_from_summary(dim_summary)
        assert len(radar) == 1
        assert radar[0]["dimension"] == "学术水平"
        # (5*7 + 3*2 + 2*1) / 10 = 4.3
        assert radar[0]["score"] == 4.3

    def test_radar_empty(self):
        radar = build_radar_from_summary({})
        assert radar == []
