#!/usr/bin/env python3
"""
conftest.py

pytest fixtures for academic investigation tests.
"""

import json
import tempfile
from pathlib import Path

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def valid_scholar():
    with open(FIXTURES_DIR / "valid_scholar.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def valid_corruption_network():
    with open(FIXTURES_DIR / "valid_corruption_network.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def invalid_scholar():
    """Missing required fields."""
    return {
        "name": "",
        "institution": "北京大学",
        # Missing: investigation_date, basic_profile, academic_outputs, etc.
    }


@pytest.fixture
def temp_case_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_papers():
    return [
        {"title": "中国经济增长研究", "authors": ["张三", "李四"], "journal": "经济研究", "year": 2023, "source_db": "cnki"},
        {"title": "金融市场波动分析", "authors": ["张三", "王五"], "journal": "管理世界", "year": 2022, "source_db": "wanfang"},
        {"title": "中国经济增长研究", "authors": ["张三", "李四"], "journal": "经济研究", "year": 2023, "source_db": "cnki"},  # duplicate
    ]
