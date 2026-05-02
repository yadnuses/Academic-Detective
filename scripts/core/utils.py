#!/usr/bin/env python3
"""
utils.py

Shared utilities for the academic investigation toolkit.
Provides unified logging, configuration loading, case directory resolution,
and standard path helpers.

Usage:
    from utils import get_logger, get_case_dir, load_config, ensure_dirs

    logger = get_logger("data_validator", case_dir="./cases/zhangsan")
    logger.info("Validation started")
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

class ModulePrefixFilter(logging.Filter):
    """Inject module name into log records."""
    def __init__(self, module_name: str):
        super().__init__()
        self.module_name = module_name

    def filter(self, record: logging.LogRecord) -> bool:
        record.module_name = self.module_name
        return True


def get_logger(
    name: str,
    case_dir: Optional[Path | str] = None,
    level: int = logging.INFO,
    json_format: bool = False,
) -> logging.Logger:
    """
    Return a configured logger.

    Args:
        name: Module / script name (e.g. "data_validator").
        case_dir: If provided, logs are also written to
                  <case_dir>/logs/investigation_YYYY-MM-DD.log
        level: Logging level.
        json_format: If True, file output uses JSON Lines format.

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)

    if json_format:
        console_fmt = logging.Formatter(
            '%(asctime)s %(levelname)s %(module_name)s %(message)s',
            datefmt='%Y-%m-%dT%H:%M:%S',
        )
    else:
        console_fmt = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(module_name)s] %(message)s',
            datefmt='%H:%M:%S',
        )
    console.setFormatter(console_fmt)
    console.addFilter(ModulePrefixFilter(name))
    logger.addHandler(console)

    # File handler (optional, per-case)
    if case_dir:
        case_path = Path(case_dir)
        log_dir = case_path / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / f"investigation_{datetime.now().strftime('%Y-%m-%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)

        if json_format:
            file_fmt = logging.Formatter(
                '{"time":"%(asctime)s","level":"%(levelname)s","module":"%(module_name)s","message":"%(message)s"}',
                datefmt='%Y-%m-%dT%H:%M:%S',
            )
        else:
            file_fmt = logging.Formatter(
                '[%(asctime)s] [%(levelname)s] [%(module_name)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S',
            )
        file_handler.setFormatter(file_fmt)
        file_handler.addFilter(ModulePrefixFilter(name))
        logger.addHandler(file_handler)

    return logger


# ---------------------------------------------------------------------------
# Case directory & configuration
# ---------------------------------------------------------------------------

STD_DIRS = ["data", "pdfs", "reports", "screenshots", "logs"]


def get_case_dir(args_case_dir: Optional[str] = None, fallback: Optional[Path | str] = None) -> Path:
    """
    Resolve case working directory.

    Priority:
        1. args_case_dir (from CLI --case-dir)
        2. fallback (e.g. environment variable or default)
        3. Current working directory

    Returns:
        Absolute Path to case directory.
    """
    if args_case_dir:
        d = Path(args_case_dir)
    elif fallback:
        d = Path(fallback)
    else:
        d = Path.cwd()
    return d.resolve()


def ensure_dirs(case_dir: Path | str, extra: Optional[list[str]] = None) -> Path:
    """
    Create standard case directory structure.

    Args:
        case_dir: Root case directory.
        extra: Additional directory names to create.

    Returns:
        Resolved case_dir Path.
    """
    root = Path(case_dir).resolve()
    dirs = STD_DIRS.copy()
    if extra:
        dirs.extend(extra)
    for d in dirs:
        (root / d).mkdir(parents=True, exist_ok=True)
    return root


def load_config(case_dir: Path | str, filename: str = "config.yaml") -> dict:
    """
    Load YAML config from case directory.

    Args:
        case_dir: Case directory path.
        filename: Config filename (default: config.yaml).

    Returns:
        Parsed dict. Returns {} if file not found or parse error.
    """
    import yaml
    config_path = Path(case_dir) / filename
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def load_json(path: Path | str) -> Optional[dict]:
    """Safely load JSON file. Returns None on error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_json(data: dict, path: Path | str, indent: int = 2) -> bool:
    """Safely save JSON file. Returns True on success."""
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def is_corruption_network(data: dict) -> bool:
    """Quick heuristic to detect corruption_network schema."""
    return bool(
        data
        and isinstance(data, dict)
        and ("network" in data or "cases" in data or "negative_space" in data)
    )


def now_iso() -> str:
    """Current timestamp in ISO format."""
    return datetime.now().isoformat(timespec="seconds")
