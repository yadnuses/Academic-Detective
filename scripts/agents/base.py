#!/usr/bin/env python3
"""
base.py — Agent base class for multi-agent collaboration.

All agents inherit from BaseAgent and communicate via the filesystem:
- Read from: case_dir / outputs / *.json, case_dir / agent_logs / other_agent / *.json
- Write to: case_dir / agent_logs / self.name / *.json
- Central state: case_dir / .case / STATE.md (only laozhoumo writes)
"""

import json
import sys
from pathlib import Path
from typing import Any
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.utils import get_logger, save_json


class BaseAgent:
    """Base class for all investigation agents."""

    def __init__(self, case_dir: Path, name: str):
        self.case_dir = Path(case_dir)
        self.name = name
        self.logger = get_logger(f"agent.{name}")
        self.log_dir = self.case_dir / "agent_logs" / name
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir = self.case_dir / "outputs"
        self.state_file = self.case_dir / ".case" / "STATE.md"

    # ------------------------------------------------------------------
    # I/O helpers
    # ------------------------------------------------------------------

    def read_json(self, rel_path: str) -> dict:
        """Read a JSON file relative to case_dir."""
        path = self.case_dir / rel_path
        if not path.exists():
            self.logger.warning("File not found: %s", path)
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            self.logger.error("JSON decode error in %s: %s", path, e)
            return {}

    def write_json(self, data: dict, filename: str = "output.json") -> Path:
        """Write JSON to agent_logs/{name}/{filename}."""
        path = self.log_dir / filename
        save_json(data, path)
        self.logger.info("Wrote %s (%d keys)", path, len(data))
        return path

    def write_text(self, text: str, filename: str = "output.md") -> Path:
        """Write text to agent_logs/{name}/{filename}."""
        path = self.log_dir / filename
        path.write_text(text, encoding="utf-8")
        return path

    def read_other_agent(self, agent_name: str, filename: str = "output.json") -> dict:
        """Read another agent's output."""
        return self.read_json(f"agent_logs/{agent_name}/{filename}")

    def list_outputs(self) -> list[Path]:
        """List all JSON files in outputs/ directory."""
        if not self.outputs_dir.exists():
            return []
        return sorted(self.outputs_dir.glob("*.json"))

    # ------------------------------------------------------------------
    # Critical marker
    # ------------------------------------------------------------------

    def mark_critical(self, context: dict) -> Path:
        """Write a CRITICAL marker for laozhoumo to detect."""
        data = {
            "agent": self.name,
            "timestamp": datetime.now().isoformat(),
            "critical": True,
            "context": context,
        }
        return self.write_json(data, "critical.json")

    def clear_critical(self):
        """Remove CRITICAL marker if present."""
        path = self.log_dir / "critical.json"
        if path.exists():
            path.unlink()

    def has_critical(self) -> bool:
        """Check if this agent has an active CRITICAL marker."""
        return (self.log_dir / "critical.json").exists()

    # ------------------------------------------------------------------
    # Logging helpers
    # ------------------------------------------------------------------

    def log_activity(self, action: str, detail: str = ""):
        """Append to activity log."""
        path = self.log_dir / "activity.log"
        line = f"{datetime.now().isoformat()} | {self.name} | {action}"
        if detail:
            line += f" | {detail}"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    # ------------------------------------------------------------------
    # Main entry point (subclasses override)
    # ------------------------------------------------------------------

    def run(self, context: dict | None = None) -> dict:
        """Execute one unit of work. Must be overridden by subclasses."""
        raise NotImplementedError(f"Agent '{self.name}' must implement run()")
