#!/usr/bin/env python3
"""Tests for cross_border/merger.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cross_border.merger import (
    normalize_doi,
    normalize_title,
    titles_similar,
    deduplicate_papers,
    detect_conflicts,
    merge_profiles,
    _merge_timelines,
    merge_scholar_data,
    _merge_lists,
)


class TestNormalizeDoi:
    def test_plain_doi(self):
        assert normalize_doi("10.1234/abc") == "10.1234/abc"

    def test_https_prefix(self):
        assert normalize_doi("https://doi.org/10.1234/abc") == "10.1234/abc"

    def test_doi_colon_prefix(self):
        assert normalize_doi("doi:10.1234/ABC") == "10.1234/abc"

    def test_empty(self):
        assert normalize_doi("") == ""
        assert normalize_doi(None) == ""


class TestNormalizeTitle:
    def test_basic(self):
        assert normalize_title("Hello World!") == "hello world"

    def test_punctuation_removed(self):
        assert normalize_title("A: B, C.") == "a b c"

    def test_whitespace_normalized(self):
        assert normalize_title("  A   B  ") == "a b"


class TestTitlesSimilar:
    def test_exact_match(self):
        assert titles_similar("Hello World", "Hello World") is True

    def test_similar(self):
        assert titles_similar("Deep Learning for Image Recognition", "Deep Learning for Image Recognition") is True

    def test_different(self):
        assert titles_similar("Quantum Computing", "Biology of Plants") is False

    def test_empty(self):
        assert titles_similar("", "Test") is False

    def test_custom_threshold(self):
        assert titles_similar("A B C D E", "A B C D F", threshold=0.5) is True


class TestDeduplicatePapers:
    def test_no_duplicates(self):
        intl = [{"title": "T1", "doi": "10.1/a"}, {"title": "T2", "doi": "10.1/b"}]
        dom = [{"title": "T3", "doi": "10.1/c"}]
        merged, dups = deduplicate_papers(dom, intl)
        assert len(merged) == 3
        assert len(dups) == 0

    def test_exact_doi_duplicate(self):
        intl = [{"title": "T1", "doi": "10.1/a"}]
        dom = [{"title": "T1 Domestic", "doi": "10.1/a"}]
        merged, dups = deduplicate_papers(dom, intl)
        assert len(merged) == 1  # international kept
        assert len(dups) == 1
        assert dups[0]["type"] == "exact_doi_match"

    def test_title_similarity_duplicate(self):
        intl = [{"title": "Deep Neural Networks for Vision", "doi": ""}]
        dom = [{"title": "Deep Neural Networks for Vision", "doi": ""}]
        merged, dups = deduplicate_papers(dom, intl)
        assert len(dups) == 1
        assert dups[0]["type"] == "title_similarity_match"

    def test_prefers_international(self):
        intl = [{"title": "T1", "doi": "", "journal": "Nature"}]
        dom = [{"title": "T1", "doi": "", "journal": "Nature", "citation_count_cn": 50}]
        merged, dups = deduplicate_papers(dom, intl)
        assert len(merged) == 1
        assert merged[0].get("citation_count_cn") == 50  # merged from domestic


class TestDetectConflicts:
    def test_no_conflicts(self):
            domestic = {
                "name": "张三",
                "basic_profile": {"institution": "清华", "tenure_status": "tenured", "current_title": "教授"},
                "academic_outputs": {"verified_papers": 50},
            }
            international = {
                "name": "张三",
                "basic_profile": {"institution": "MIT", "tenure_status": "", "current_title": ""},
                "academic_outputs": {"verified_papers": 50},
            }
            conflicts = detect_conflicts(domestic, international)
            assert len(conflicts) == 0

    def test_name_mismatch(self):
        domestic = {"name": "张三", "basic_profile": {}}
        international = {"name": "李四", "basic_profile": {}}
        conflicts = detect_conflicts(domestic, international)
        assert any(c["type"] == "name_mismatch" for c in conflicts)

    def test_simultaneous_fulltime(self):
        domestic = {
            "name": "张三",
            "basic_profile": {"institution": "清华", "tenure_status": "tenured", "current_title": "教授"},
            "academic_outputs": {},
        }
        international = {
            "name": "张三",
            "basic_profile": {"institution": "MIT", "tenure_status": "tenured", "current_title": "Professor"},
            "academic_outputs": {},
        }
        conflicts = detect_conflicts(domestic, international)
        assert any(c["type"] == "simultaneous_fulltime" for c in conflicts)

    def test_title_inconsistency(self):
        domestic = {
            "name": "张三",
            "basic_profile": {"current_title": "教授"},
            "academic_outputs": {},
        }
        international = {
            "name": "张三",
            "basic_profile": {"current_title": "assistant professor"},
            "academic_outputs": {},
        }
        conflicts = detect_conflicts(domestic, international)
        assert any(c["type"] == "title_inconsistency" for c in conflicts)

    def test_paper_count_discrepancy(self):
        domestic = {"name": "张三", "basic_profile": {}, "academic_outputs": {"verified_papers": 100}}
        international = {"name": "张三", "basic_profile": {}, "academic_outputs": {"verified_papers": 50}}
        conflicts = detect_conflicts(domestic, international)
        assert any(c["type"] == "paper_count_discrepancy" for c in conflicts)


class TestMergeProfiles:
    def test_merge_basic(self):
        domestic = {
            "basic_profile": {
                "name": "张三",
                "institution": "清华",
                "current_title": "教授",
                "orcid": "",
            }
        }
        international = {
            "basic_profile": {
                "name": "Zhang San",
                "institution": "MIT",
                "current_title": "Professor",
                "orcid": "0000-0001-0000-0001",
            }
        }
        merged = merge_profiles(domestic, international)
        assert merged["name"] == "张三"
        assert merged["name_en"] == "Zhang San"
        assert merged["orcid"] == "0000-0001-0000-0001"

    def test_merge_timelines(self):
        domestic = {
            "basic_profile": {
                "career_timeline": [{"year": 2010, "event": "Joined Tsinghua", "institution": "清华"}]
            }
        }
        international = {
            "basic_profile": {
                "career_timeline": [{"year": 2015, "event": "Joined MIT", "institution": "MIT"}]
            }
        }
        merged = merge_profiles(domestic, international)
        assert isinstance(merged["career_timeline"], list)
        assert len(merged["career_timeline"]) == 2


class TestMergeTimelines:
    def test_merge_lists(self):
        dom = [{"year": 2010, "event": "E1"}]
        intl = [{"year": 2015, "event": "E2"}]
        result = _merge_timelines(dom, intl)
        assert len(result) == 2
        assert result[0]["year"] == 2010

    def test_deduplicate(self):
        dom = [{"year": 2010, "event": "E1"}]
        intl = [{"year": 2010, "event": "E1"}]
        result = _merge_timelines(dom, intl)
        assert len(result) == 1

    def test_string_timeline(self):
        dom = "Worked at Tsinghua"
        intl = []
        result = _merge_timelines(dom, intl)
        assert len(result) == 1
        assert result[0]["event"] == "Worked at Tsinghua"


class TestMergeLists:
    def test_basic(self):
        a = [{"name": "A"}, {"name": "B"}]
        b = [{"name": "B"}, {"name": "C"}]
        result = _merge_lists(a, b)
        assert len(result) == 3
        names = [r["name"] for r in result]
        assert "A" in names and "B" in names and "C" in names

    def test_non_dict_items(self):
        a = [{"name": "A"}, "bad"]
        b = [{"name": "B"}]
        result = _merge_lists(a, b)
        assert len(result) == 2


import json


class TestMergeScholarData:
    def test_basic_merge(self, tmp_path):
        domestic = {
            "name": "张三",
            "basic_profile": {
                "name": "张三", "institution": "清华", "current_title": "教授",
                "education_background": "PhD", "career_timeline": [],
            },
            "academic_outputs": {
                "claimed_papers": 50, "verified_papers": 45,
                "paper_list": [{"title": "D1", "doi": "10.1/d1"}],
                "source_databases": ["cnki"],
            },
            "anomalies": [],
            "student_reviews": {},
            "relationship_network": {"advisors": [], "collaborators": []},
        }
        international = {
            "name": "张三",
            "basic_profile": {
                "name": "Zhang San", "institution": "MIT", "current_title": "Professor",
                "education_background": "PhD MIT", "career_timeline": [],
            },
            "academic_outputs": {
                "claimed_papers": 40, "verified_papers": 38,
                "paper_list": [{"title": "I1", "doi": "10.1/i1"}],
                "source_databases": ["openalex"],
            },
            "anomalies": [],
            "student_reviews": {"xiaohongshu": {}},
            "relationship_network": {"advisors": [], "collaborators": []},
        }
        dom_path = tmp_path / "domestic.json"
        intl_path = tmp_path / "international.json"
        dom_path.write_text(json.dumps(domestic, ensure_ascii=False))
        intl_path.write_text(json.dumps(international, ensure_ascii=False))

        result = merge_scholar_data(str(dom_path), str(intl_path))
        assert result["investigation_type"] == "cross_border"
        assert result["cross_border_info"]["timeline_consistency"] is True
        assert len(result["academic_outputs"]["paper_list"]) == 2
        assert "openalex" in result["academic_outputs"]["source_databases"]
        assert "cnki" in result["academic_outputs"]["source_databases"]

    def test_with_conflicts(self, tmp_path):
        domestic = {
            "name": "张三",
            "basic_profile": {
                "name": "张三", "institution": "清华", "current_title": "教授",
                "education_background": "PhD", "career_timeline": [],
                "tenure_status": "tenured",
            },
            "academic_outputs": {"paper_list": [], "source_databases": []},
            "anomalies": [],
            "student_reviews": {},
            "relationship_network": {},
        }
        international = {
            "name": "张三",
            "basic_profile": {
                "name": "Zhang San", "institution": "MIT", "current_title": "Professor",
                "education_background": "PhD", "career_timeline": [],
                "tenure_status": "tenured",
            },
            "academic_outputs": {"paper_list": [], "source_databases": []},
            "anomalies": [],
            "student_reviews": {},
            "relationship_network": {},
        }
        dom_path = tmp_path / "domestic.json"
        intl_path = tmp_path / "international.json"
        dom_path.write_text(json.dumps(domestic, ensure_ascii=False))
        intl_path.write_text(json.dumps(international, ensure_ascii=False))

        result = merge_scholar_data(str(dom_path), str(intl_path))
        assert len(result["cross_border_info"]["conflicts"]) > 0
        assert result["cross_border_info"]["timeline_consistency"] is False
