#!/usr/bin/env python3
"""Tests for core/config_loader.py"""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.config_loader import load_config_with_defaults, _migrate_v1_to_v2, CONFIG_VERSION


class TestMigrateV1ToV2:
    def test_adds_investigation_type(self):
        v1 = {"scholar": {"name": "张三"}}
        v2 = _migrate_v1_to_v2(v1)
        assert v2["investigation"]["investigation_type"] == "domestic"

    def test_adds_international_sources(self):
        v1 = {"scholar": {"name": "张三"}}
        v2 = _migrate_v1_to_v2(v1)
        assert "international_sources" in v2
        assert v2["international_sources"]["openalex"]["enabled"] is True

    def test_adds_xiaohongshu(self):
        v1 = {"scholar": {"name": "张三"}}
        v2 = _migrate_v1_to_v2(v1)
        assert "xiaohongshu" in v2
        assert v2["xiaohongshu"]["enabled"] is True

    def test_sets_config_version(self):
        v1 = {"scholar": {"name": "张三"}}
        v2 = _migrate_v1_to_v2(v1)
        assert v2["config_version"] == CONFIG_VERSION

    def test_preserves_existing_data(self):
        v1 = {"scholar": {"name": "张三", "institution": "北大"}, "claims": {"papers": 10}}
        v2 = _migrate_v1_to_v2(v1)
        assert v2["scholar"]["institution"] == "北大"
        assert v2["claims"]["papers"] == 10


class TestLoadConfigWithDefaults:
    def test_loads_v2_config_unchanged(self, tmp_path):
        config = {
            "config_version": "2.0",
            "scholar": {"name": "张三", "institution": "北京大学"},
            "investigation": {"investigation_type": "domestic"},
        }
        path = tmp_path / "config.yaml"
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(config, f)

        result = load_config_with_defaults(path)
        assert result["investigation"]["investigation_type"] == "domestic"
        assert result["config_version"] == CONFIG_VERSION

    def test_auto_infers_international(self, tmp_path):
        config = {
            "config_version": "2.0",
            "scholar": {"name": "Prof. Smith", "institution": "MIT"},
        }
        path = tmp_path / "config.yaml"
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(config, f)

        result = load_config_with_defaults(path)
        assert result["investigation"]["investigation_type"] == "international"

    def test_auto_infers_domestic(self, tmp_path):
        config = {
            "config_version": "2.0",
            "scholar": {"name": "张三", "institution": "北京大学"},
        }
        path = tmp_path / "config.yaml"
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(config, f)

        result = load_config_with_defaults(path)
        assert result["investigation"]["investigation_type"] == "domestic"

    def test_migrates_v1_config(self, tmp_path):
        v1_config = {
            "scholar": {"name": "张三", "institution": "北京大学"},
            "investigation": {"date": "2026-04-19", "depth": "standard"},
        }
        path = tmp_path / "config.yaml"
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(v1_config, f)

        result = load_config_with_defaults(path)
        assert result["config_version"] == CONFIG_VERSION
        assert result["investigation"]["investigation_type"] == "domestic"
        assert "international_sources" in result
        assert "xiaohongshu" in result
