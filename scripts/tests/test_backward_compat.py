#!/usr/bin/env python3
"""
tests/test_backward_compat.py

Verify backward compatibility after radical refactor:
- All original CLI commands remain functional
- Old scholar_data.json format still validates
- review_matcher.py CLI signature unchanged
- Shim files work correctly
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure scripts/ is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

PROJECT_ROOT = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestOriginalCLISignature:
    """Verify original CLI commands still work."""

    def test_investigate_init_help(self):
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "investigate.py"), "init", "--help"],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "--config" in result.stdout

    def test_investigate_step_help(self):
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "investigate.py"), "step", "--help"],
            capture_output=True, text=True
        )
        assert result.returncode == 0

    def test_investigate_validate_help(self):
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "investigate.py"), "validate", "--help"],
            capture_output=True, text=True
        )
        assert result.returncode == 0

    def test_investigate_prompt_help(self):
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "investigate.py"), "prompt", "--help"],
            capture_output=True, text=True
        )
        assert result.returncode == 0

    def test_investigate_visualize_help(self):
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "investigate.py"), "visualize", "--help"],
            capture_output=True, text=True
        )
        assert result.returncode == 0

    def test_investigate_new_commands_exist(self):
        """New international subcommands should exist."""
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "investigate.py"), "--help"],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "international-fetch" in result.stdout
        assert "international-build" in result.stdout
        assert "missing-report" in result.stdout
        assert "review-aggregate" in result.stdout
        assert "cross-border-merge" in result.stdout


class TestShimImports:
    """Verify shim files at original locations still work."""

    def test_utils_shim_imports(self):
        """scripts/utils.py should still be importable."""
        import utils
        assert hasattr(utils, "get_logger")
        assert hasattr(utils, "load_json")

    def test_data_importer_shim_imports(self):
        """scripts/data_importer.py should still be importable."""
        import data_importer as di
        assert hasattr(di, "parse_cnki_xlsx")
        assert hasattr(di, "deduplicate")

    def test_data_validator_shim_imports(self):
        """scripts/data_validator.py should still be importable."""
        import data_validator as dv
        assert hasattr(dv, "validate")
        assert hasattr(dv, "is_corruption_network")

    def test_core_imports_directly(self):
        """New core/ modules should be directly importable."""
        from core import utils, db, router, config_loader
        assert hasattr(utils, "get_logger")
        assert hasattr(db, "InvestigationDB")
        assert hasattr(router, "detect_investigation_type")
        assert hasattr(config_loader, "load_config_with_defaults")

    def test_domestic_imports_directly(self):
        """New domestic/ modules should be directly importable."""
        from domestic import data_importer, data_validator, review_matcher
        assert hasattr(data_importer, "parse_cnki_xlsx")
        assert hasattr(data_validator, "validate")
        assert hasattr(review_matcher, "main")

    def test_international_imports_directly(self):
        """New international/ modules should be directly importable."""
        from international import data_fetcher, evaluator, xiaohongshu_client
        from international import scholar_data_builder, data_validator, heuristics_classifier
        from international import missing_reporter
        assert hasattr(evaluator, "InternationalEvaluator")
        assert hasattr(xiaohongshu_client, "XiaohongshuClient")
        assert hasattr(heuristics_classifier, "InternationalHeuristicsClassifier")
        assert hasattr(missing_reporter, "generate_missing_report")


class TestOldDataFormat:
    """Verify old format scholar_data.json still validates."""

    def test_valid_scholar_passes(self):
        import data_validator as dv
        with open(FIXTURES_DIR / "valid_scholar.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        errors, warnings = dv.validate(data)
        assert len(errors) == 0

    def test_international_scholar_passes(self):
        """International format should also validate (has extra fields)."""
        import data_validator as dv
        with open(FIXTURES_DIR / "valid_international_scholar.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        errors, warnings = dv.validate(data)
        # International format has investigation_type which domestic validator
        # may warn about but should not error
        assert len(errors) == 0

    def test_old_format_without_investigation_type(self):
        """Pre-refactor scholar_data without investigation_type should still validate."""
        import data_validator as dv
        with open(FIXTURES_DIR / "valid_scholar.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        # Remove investigation_type if present
        data.pop("investigation_type", None)
        errors, warnings = dv.validate(data)
        assert len(errors) == 0


class TestRouterBackwardCompat:
    """Verify router correctly handles old configs."""

    def test_old_domestic_config_detected(self):
        from core.router import detect_investigation_type, InvestigationType
        config = {
            "scholar": {
                "name": "张三",
                "institution": "北京大学",
            }
        }
        result = detect_investigation_type(config)
        assert result == InvestigationType.DOMESTIC

    def test_new_international_config_detected(self):
        from core.router import detect_investigation_type, InvestigationType
        config = {
            "scholar": {
                "name": "Alice Smith",
                "institution": "MIT",
                "institution_en": "Massachusetts Institute of Technology",
            }
        }
        result = detect_investigation_type(config)
        assert result == InvestigationType.INTERNATIONAL


class TestSchemaCompatibility:
    """Verify schema files are valid JSON Schema."""

    def test_scholar_data_schema_is_valid_json(self):
        with open(PROJECT_ROOT / "schema" / "scholar_data.schema.json", "r", encoding="utf-8") as f:
            schema = json.load(f)
        assert schema["title"] == "Scholar Investigation Data Schema"
        assert "investigation_type" in schema["properties"]

    def test_international_schema_is_valid_json(self):
        with open(PROJECT_ROOT / "schema" / "international_scholar.schema.json", "r", encoding="utf-8") as f:
            schema = json.load(f)
        assert "international" in schema["properties"]["investigation_type"]["enum"]
