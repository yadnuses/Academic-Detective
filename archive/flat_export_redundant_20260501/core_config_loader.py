#!/usr/bin/env python3
"""
core/config_loader.py

Unified configuration loading with automatic v1→v2 migration
and investigation type inference.

Usage:
    from core_config_loader import load_config_with_defaults

    config = load_config_with_defaults("./cases/test/config.yaml")
"""

import yaml
from pathlib import Path
from typing import Optional

from core_router import detect_investigation_type, InvestigationType


CONFIG_VERSION = "2.0"


def load_config_with_defaults(path: Path | str) -> dict:
    """
    Load config.yaml with automatic defaults and version migration.

    - If config lacks `investigation.investigation_type`, auto-infer and inject.
    - If config lacks `config_version`, treat as v1 and migrate.
    - Returns a fully populated config dict.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    # Version migration
    version = config.get("config_version", "1.0")
    if version == "1.0":
        config = _migrate_v1_to_v2(config)

    # Ensure investigation section exists
    if "investigation" not in config:
        config["investigation"] = {}

    # Auto-infer investigation_type if missing
    if "investigation_type" not in config["investigation"]:
        inv_type = detect_investigation_type(config)
        config["investigation"]["investigation_type"] = inv_type.value

    # Ensure config_version
    config["config_version"] = CONFIG_VERSION

    return config


def _migrate_v1_to_v2(config: dict) -> dict:
    """
    Migrate v1 config to v2 format.

    v1 → v2 changes:
    - Add investigation_type: domestic (default for v1 configs)
    - Add empty international_sources section
    - Add empty xiaohongshu section
    """
    config = config.copy()

    if "investigation" not in config:
        config["investigation"] = {}

    config["investigation"]["investigation_type"] = "domestic"

    # Add empty international section for forward compatibility
    if "international_sources" not in config:
        config["international_sources"] = {
            "openalex": {"enabled": True},
            "orcid": {"enabled": True},
            "semantic_scholar": {"enabled": True},
            "google_scholar": {"enabled": True},
            "pubpeer": {"enabled": True},
            "retraction_watch": {"enabled": True},
            "arxiv": {"enabled": True},
        }

    if "xiaohongshu" not in config:
        config["xiaohongshu"] = {
            "enabled": True,
            "max_results": 50,
        }

    config["config_version"] = CONFIG_VERSION
    return config


def save_config(config: dict, path: Path | str):
    """Save config to YAML file."""
    path = Path(path)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False)
