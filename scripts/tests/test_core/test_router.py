#!/usr/bin/env python3
"""Tests for core/router.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.router import (
    detect_investigation_type,
    get_track_scripts,
    get_step_definitions,
    InvestigationType,
)


class TestDetectInvestigationType:
    def test_explicit_domestic(self):
        config = {"investigation": {"investigation_type": "domestic"}}
        assert detect_investigation_type(config) == InvestigationType.DOMESTIC

    def test_explicit_international(self):
        config = {"investigation": {"investigation_type": "international"}}
        assert detect_investigation_type(config) == InvestigationType.INTERNATIONAL

    def test_explicit_cross_border(self):
        config = {"investigation": {"investigation_type": "cross_border"}}
        assert detect_investigation_type(config) == InvestigationType.CROSS_BORDER

    def test_infer_from_institution_international(self):
        config = {"scholar": {"institution": "MIT"}}
        assert detect_investigation_type(config) == InvestigationType.INTERNATIONAL

    def test_infer_from_institution_domestic(self):
        config = {"scholar": {"institution": "北京大学"}}
        assert detect_investigation_type(config) == InvestigationType.DOMESTIC

    def test_infer_from_international_sources(self):
        config = {"scholar": {"institution": "某机构"}, "international_sources": {"openalex": {}}}
        assert detect_investigation_type(config) == InvestigationType.INTERNATIONAL

    def test_default_domestic(self):
        config = {"scholar": {"institution": "某不知名机构"}}
        assert detect_investigation_type(config) == InvestigationType.DOMESTIC

    def test_chinese_institution_with_english_name(self):
        # 只有中文名，没有英文名 → domestic
        config = {"scholar": {"institution": "清华大学"}}
        assert detect_investigation_type(config) == InvestigationType.DOMESTIC

    def test_chinese_institution_with_en_suffix(self):
        # 有英文名但主体是中文 → domestic
        config = {"scholar": {"institution": "清华大学", "institution_en": "Tsinghua University"}}
        # 这个会匹配到 "university" 关键字，所以会返回 INTERNATIONAL
        # 但根据业务逻辑，有中文大学标识的应该优先判定为 domestic
        result = detect_investigation_type(config)
        assert result == InvestigationType.DOMESTIC


class TestGetTrackScripts:
    def test_domestic_has_key_scripts(self):
        scripts = get_track_scripts(InvestigationType.DOMESTIC)
        assert "data_importer" in scripts
        assert "data_validator" in scripts
        assert "scholar_data_builder" in scripts
        assert "review_matcher" in scripts
        assert "report_template" in scripts

    def test_international_has_key_scripts(self):
        scripts = get_track_scripts(InvestigationType.INTERNATIONAL)
        assert "data_fetcher" in scripts
        assert "data_validator" in scripts
        assert "scholar_data_builder" in scripts
        assert "evaluator" in scripts
        assert "xiaohongshu_client" in scripts
        assert "missing_reporter" in scripts
        assert "report_template" in scripts

    def test_cross_border_has_merger(self):
        scripts = get_track_scripts(InvestigationType.CROSS_BORDER)
        assert "cross_border_merger" in scripts
        assert "cross_border_validator" in scripts

    def test_scripts_exist_on_disk(self):
        for track in InvestigationType:
            # Skip international/cross_border track scripts that haven't been created yet (Phase 5)
            if track in (InvestigationType.INTERNATIONAL, InvestigationType.CROSS_BORDER):
                continue
            scripts = get_track_scripts(track)
            for key, path in scripts.items():
                assert path.exists(), f"{track.value}/{key}: {path} not found"


class TestGetStepDefinitions:
    def test_domestic_returns_none(self):
        assert get_step_definitions(InvestigationType.DOMESTIC) is None

    def test_international_returns_steps(self):
        steps = get_step_definitions(InvestigationType.INTERNATIONAL)
        assert steps is not None
        assert len(steps) > 0
        ids = [s["id"] for s in steps]
        assert "init" in ids
        assert "auto_fetch" in ids
        assert "xiaohongshu" in ids
        assert "manual_supplement" in ids  # step where missing_reporter is used
        assert "build" in ids
        assert "validate" in ids

    def test_cross_border_returns_none(self):
        assert get_step_definitions(InvestigationType.CROSS_BORDER) is None
