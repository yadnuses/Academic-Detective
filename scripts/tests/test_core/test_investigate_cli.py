#!/usr/bin/env python3
"""Tests for investigate.py CLI routing enhancements."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from investigate import (
    _get_steps_for_state,
    cmd_init,
    cmd_validate,
    STEPS,
)
from core.router import InvestigationType, get_step_definitions


class MockArgs:
    """Lightweight args mock."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestGetStepsForState:
    def test_domestic_uses_default_steps(self):
        state = {"investigation_type": "domestic"}
        steps = _get_steps_for_state(state)
        assert steps == STEPS

    def test_international_uses_custom_steps(self):
        state = {"investigation_type": "international"}
        steps = _get_steps_for_state(state)
        assert steps is not None
        assert steps != STEPS
        ids = [s["id"] for s in steps]
        assert "auto_fetch" in ids
        assert "xiaohongshu" in ids

    def test_unknown_type_falls_back(self):
        state = {"investigation_type": "unknown_type"}
        steps = _get_steps_for_state(state)
        assert steps == STEPS

    def test_missing_type_defaults_to_domestic(self):
        state = {}
        steps = _get_steps_for_state(state)
        assert steps == STEPS


class TestInitTypeOverride:
    def test_type_override_international(self, tmp_path):
        case_dir = tmp_path / "case"
        config_path = case_dir / "config.yaml"
        case_dir.mkdir()
        # Write a minimal config that would auto-detect as domestic
        config_path.write_text(
            "scholar:\n  name: Test\n  institution: 某机构\n",
            encoding="utf-8",
        )
        # Copy template to avoid lookup failure
        template = Path(__file__).parent.parent.parent / "config.template.yaml"
        if template.exists():
            import shutil
            shutil.copy(template, case_dir / "config.template.yaml")

        args = MockArgs(
            case_dir=str(case_dir),
            config="config.yaml",
            name="test_case",
            type="international",
        )
        cmd_init(args)

        state_path = case_dir / ".state.json"
        assert state_path.exists()
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["investigation_type"] == "international"
        assert state["current_step"] == "auto_fetch"

    def test_type_override_cross_border(self, tmp_path):
        case_dir = tmp_path / "case"
        config_path = case_dir / "config.yaml"
        case_dir.mkdir()
        config_path.write_text(
            "scholar:\n  name: Test\n  institution: 某机构\n",
            encoding="utf-8",
        )
        template = Path(__file__).parent.parent.parent / "config.template.yaml"
        if template.exists():
            import shutil
            shutil.copy(template, case_dir / "config.template.yaml")

        args = MockArgs(
            case_dir=str(case_dir),
            config="config.yaml",
            name="test_case",
            type="cross_border",
        )
        cmd_init(args)

        state_path = case_dir / ".state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["investigation_type"] == "cross_border"

    def test_no_override_uses_auto_detect(self, tmp_path):
        case_dir = tmp_path / "case"
        config_path = case_dir / "config.yaml"
        case_dir.mkdir()
        # MIT should auto-detect as international
        config_path.write_text(
            "scholar:\n  name: Test\n  institution: MIT\n",
            encoding="utf-8",
        )
        template = Path(__file__).parent.parent.parent / "config.template.yaml"
        if template.exists():
            import shutil
            shutil.copy(template, case_dir / "config.template.yaml")

        args = MockArgs(
            case_dir=str(case_dir),
            config="config.yaml",
            name="test_case",
            type=None,
        )
        cmd_init(args)

        state_path = case_dir / ".state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["investigation_type"] == "international"


class TestValidateRouting:
    def test_routes_to_domestic_validator(self, tmp_path):
        case_dir = tmp_path / "case"
        case_dir.mkdir()
        scholar_data = {
            "investigation_type": "domestic",
            "name": "Test",
            "institution": "某大学",
            "investigation_date": "2024-01-01",
            "investigation_type": "domestic",
            "basic_profile": {
                "name": "Test",
                "institution": "某大学",
                "current_title": "教授",
                "education_background": "博士",
                "career_timeline": [],
            },
            "academic_outputs": {
                "claimed_papers": 0,
                "verified_papers": 0,
                "claimed_monographs": 0,
                "verified_monographs": 0,
                "source_databases": [],
                "recent_3yr_papers": 0,
            },
            "quality_assessment": {},
            "relationship_network": {},
            "anomalies": [],
            "confidence_ratings": {},
            "student_reviews": {},
        }
        sd_path = case_dir / "scholar_data.json"
        sd_path.write_text(json.dumps(scholar_data, ensure_ascii=False), encoding="utf-8")

        args = MockArgs(case_dir=str(case_dir), input="scholar_data.json", type=None)
        # Should not raise / exit
        cmd_validate(args)

    def test_routes_to_international_validator(self, tmp_path):
        case_dir = tmp_path / "case"
        case_dir.mkdir()
        scholar_data = {
            "investigation_type": "international",
            "name": "Prof. Test",
            "institution": "MIT",
            "investigation_date": "2024-01-01",
            "basic_profile": {
                "name": "Prof. Test",
                "institution": "MIT",
                "current_title": "Professor",
                "education_background": "PhD",
                "career_timeline": [],
            },
            "academic_outputs": {
                "claimed_papers": 0,
                "verified_papers": 0,
                "claimed_monographs": 0,
                "verified_monographs": 0,
                "source_databases": [],
                "recent_3yr_papers": 0,
            },
            "quality_assessment": {},
            "relationship_network": {},
            "anomalies": [],
            "confidence_ratings": {},
            "student_reviews": {},
        }
        sd_path = case_dir / "scholar_data.json"
        sd_path.write_text(json.dumps(scholar_data, ensure_ascii=False), encoding="utf-8")

        args = MockArgs(case_dir=str(case_dir), input="scholar_data.json", type=None)
        cmd_validate(args)

    def test_type_arg_overrides_data_type(self, tmp_path):
        case_dir = tmp_path / "case"
        case_dir.mkdir()
        # Data says domestic, but --type says international
        scholar_data = {
            "investigation_type": "domestic",
            "name": "Prof. Test",
            "institution": "MIT",
            "investigation_date": "2024-01-01",
            "basic_profile": {
                "name": "Prof. Test",
                "institution": "MIT",
                "current_title": "Professor",
                "education_background": "PhD",
                "career_timeline": [],
            },
            "academic_outputs": {
                "claimed_papers": 0,
                "verified_papers": 0,
                "claimed_monographs": 0,
                "verified_monographs": 0,
                "source_databases": [],
                "recent_3yr_papers": 0,
            },
            "quality_assessment": {},
            "relationship_network": {},
            "anomalies": [],
            "confidence_ratings": {},
            "student_reviews": {},
        }
        sd_path = case_dir / "scholar_data.json"
        sd_path.write_text(json.dumps(scholar_data, ensure_ascii=False), encoding="utf-8")

        args = MockArgs(case_dir=str(case_dir), input="scholar_data.json", type="international")
        # international validator requires different fields; this tests the routing path
        cmd_validate(args)

    def test_cross_border_validator(self, tmp_path):
        case_dir = tmp_path / "case"
        case_dir.mkdir()
        scholar_data = {
            "investigation_type": "cross_border",
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
        sd_path = case_dir / "scholar_data.json"
        sd_path.write_text(json.dumps(scholar_data, ensure_ascii=False), encoding="utf-8")

        args = MockArgs(case_dir=str(case_dir), input="scholar_data.json", type=None)
        cmd_validate(args)
