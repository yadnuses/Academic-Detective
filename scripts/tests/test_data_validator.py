#!/usr/bin/env python3
"""
Tests for data_validator.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from domestic import data_validator as dv


class TestIsCorruptionNetwork:
    def test_detects_corruption_network(self, valid_corruption_network):
        assert dv.is_corruption_network(valid_corruption_network) is True

    def test_detects_scholar_data(self, valid_scholar):
        assert dv.is_corruption_network(valid_scholar) is False

    def test_empty_dict(self):
        assert dv.is_corruption_network({}) is False


class TestValidateScholarData:
    def test_valid_scholar_passes(self, valid_scholar):
        errors, warnings = dv.validate_scholar_data(valid_scholar, fix=False)
        assert len(errors) == 0, f"Unexpected errors: {errors}"

    def test_invalid_scholar_fails(self, invalid_scholar):
        errors, warnings = dv.validate_scholar_data(invalid_scholar, fix=False)
        assert len(errors) > 0
        assert any("name" in str(e).lower() or "missing" in str(e).lower() for e in errors)

    def test_missing_required_field(self, valid_scholar):
        data = valid_scholar.copy()
        del data["name"]
        errors, warnings = dv.validate_scholar_data(data, fix=False)
        assert any("name" in str(e).lower() for e in errors)


class TestValidateCorruptionNetwork:
    def test_valid_network_passes(self, valid_corruption_network):
        errors, warnings = dv.validate_corruption_network(valid_corruption_network, fix=False)
        assert len(errors) == 0, f"Unexpected errors: {errors}"

    def test_missing_nodes_fails(self, valid_corruption_network):
        data = valid_corruption_network.copy()
        del data["nodes"]
        errors, warnings = dv.validate_corruption_network(data, fix=False)
        assert len(errors) > 0

    def test_broken_link_fails(self, valid_corruption_network):
        data = valid_corruption_network.copy()
        data["links"][0]["source"] = "nonexistent_node"
        errors, warnings = dv.validate_corruption_network(data, fix=False)
        assert any("link" in str(e).lower() or "source" in str(e).lower() or "target" in str(e).lower() for e in errors)


class TestAutoFix:
    def test_fixes_missing_fields(self, invalid_scholar):
        fixed = dv.auto_fix_scholar_data(invalid_scholar.copy())
        assert "investigation_date" in fixed
        assert "basic_profile" in fixed

    def test_fix_missing_top_level(self):
        data = {"institution": "Test"}  # Missing most fields
        fixed = dv.auto_fix_scholar_data(data)
        # Top-level missing fields get empty string, not [TO BE FILLED]
        assert fixed.get("name") == ""
        assert "basic_profile" in fixed
        assert fixed["basic_profile"].get("name") == "[TO BE FILLED]"
