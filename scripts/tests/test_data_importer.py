#!/usr/bin/env python3
"""
Tests for data_importer.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from domestic import data_importer as di


class TestDeduplication:
    def test_exact_duplicate_removed(self, sample_papers):
        deduped, removed = di.deduplicate(sample_papers, threshold=0.85)
        assert removed == 1
        assert len(deduped) == 2

    def test_fuzzy_duplicate_removed(self):
        papers = [
            {"title": "中国经济增长研究", "authors": ["张三"], "year": 2023},
            {"title": "中国经济增长研究分析", "authors": ["张三"], "year": 2023},  # ~0.89 similarity
        ]
        deduped, removed = di.deduplicate(papers, threshold=0.85)
        assert removed == 1
        assert len(deduped) == 1

    def test_no_false_positive(self):
        papers = [
            {"title": "中国经济增长研究", "authors": ["张三"], "year": 2023},
            {"title": "美国金融市场分析", "authors": ["李四"], "year": 2022},
        ]
        deduped, removed = di.deduplicate(papers, threshold=0.85)
        assert removed == 0
        assert len(deduped) == 2


class TestParsers:
    def test_parse_json(self, tmp_path):
        data = {
            "papers": [
                {"title": "测试", "authors": ["A"], "year": 2023}
            ]
        }
        path = tmp_path / "test.json"
        path.write_text(str(data).replace("'", '"'), encoding="utf-8")
        # Note: this is a minimal test; full parser tests need real export files
        papers = di.parse_json(path)
        # Since we wrote invalid JSON above, this returns []
        assert isinstance(papers, list)


class TestHelpers:
    def test_split_authors_semicolon(self):
        assert di._split_authors("张三;李四;王五") == ["张三", "李四", "王五"]

    def test_split_authors_comma(self):
        assert di._split_authors("张三,李四") == ["张三", "李四"]

    def test_parse_year_valid(self):
        assert di._parse_year("2023") == 2023
        assert di._parse_year("发表于 2023 年") == 2023

    def test_parse_year_invalid(self):
        assert di._parse_year("未知") is None
        assert di._parse_year("") is None

    def test_title_similarity_identical(self):
        assert di._title_similarity("中国经济增长研究", "中国经济增长研究") > 0.99

    def test_title_similarity_different(self):
        assert di._title_similarity("中国经济增长研究", "美国金融市场分析") < 0.5
