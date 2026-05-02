#!/usr/bin/env python3
"""
agents/zhu_xiansheng.py — Executor Agent (朱先生)

Persona: 沉默寡言、执行利落、只信任输出。不自己做判断，只执行和记录。

Responsibilities:
    - Run deep_evidence scripts via subprocess.
    - Monitor data chain integrity (Schema v1.0).
    - Extract summaries from script outputs.
    - Detect anomalies and mark CRITICAL when confidence >= 0.85.
    - Stop queue execution on CRITICAL signals.

Communication:
    - Reads pending tasks from STATE.md or incoming context.
    - Writes execution logs to agent_logs/zhu_xiansheng/.
    - Consumes outputs from case_dir/outputs/.
"""

import re
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.utils import get_logger, load_config

from agents.base import BaseAgent


class ZhuXiansheng(BaseAgent):
    """Executor agent — runs scripts, monitors data chain, reports anomalies."""

    def __init__(self, case_dir: Path):
        super().__init__(case_dir, "zhu_xiansheng")
        self.outputs_dir = self.case_dir / "outputs"
        self.outputs_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, context: dict | None = None) -> dict:
        """Main entry. Expects context['tasks'] list; falls back to STATE.md."""
        context = context or {}
        tasks: list[dict] = context.get("tasks", [])
        if not tasks:
            tasks = self._read_pending_tasks_from_state()
            self.logger.info("Loaded %d pending tasks from STATE.md", len(tasks))

        results = self.run_queue(tasks)
        overall = {
            "agent": self.name,
            "timestamp": datetime.now().isoformat(),
            "tasks_total": len(tasks),
            "tasks_executed": len(results),
            "critical": self.has_critical(),
            "results": results,
        }
        self.write_json(overall, "summary.json")
        self.log_activity("run_complete", f"executed={len(results)} critical={self.has_critical()}")
        return overall

    # ------------------------------------------------------------------
    # Task queue
    # ------------------------------------------------------------------

    def run_queue(self, tasks: list[dict]) -> list[dict]:
        """Sequentially execute tasks. Stop if CRITICAL detected."""
        summaries: list[dict] = []
        for idx, task in enumerate(tasks):
            self.logger.info("Queue %d/%d — %s", idx + 1, len(tasks), task.get("tool", "?"))
            summary = self.run_task(task)
            summaries.append(summary)
            self.write_json(
                {
                    "progress": f"{idx + 1}/{len(tasks)}",
                    "last_task": summary,
                    "critical": self.has_critical(),
                },
                f"intermediate_{idx + 1:03d}.json",
            )
            if self.has_critical():
                self.logger.warning("CRITICAL after task %d. Stopping queue.", idx + 1)
                break
        return summaries

    def run_task(self, task: dict) -> dict:
        """Execute a single tool. task keys: tool, args (optional)."""
        tool: str = task.get("tool", "")
        extra_args: dict = task.get("args", {})
        if not tool:
            self.logger.error("Task missing 'tool'")
            return self._error_summary(task, "missing_tool")

        tool_name = Path(tool).name
        script_path = self.case_dir.parent / "deep_evidence" / f"{tool}.py"
        if not script_path.exists():
            self.logger.error("Script not found: %s", script_path)
            return self._error_summary(task, "script_not_found")

        output_json = self.outputs_dir / f"{tool_name}.json"
        cmd = [sys.executable, str(script_path), "--output", str(output_json)]

        # Auto-infer common args
        inferred = self._infer_args(tool_name, output_json)
        for key, value in inferred.items():
            cmd.extend([f"--{key}", str(value)])
        for key, value in extra_args.items():
            flag = f"--{key}"
            if flag in cmd:
                i = cmd.index(flag)
                cmd.pop(i)
                if i < len(cmd) and not cmd[i].startswith("--"):
                    cmd.pop(i)
            cmd.extend([flag, str(value)])

        self.logger.info("Executing: %s", " ".join(cmd))
        self.log_activity("execute", tool)

        start = datetime.now()
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired:
            self.logger.error("Timeout: %s", tool)
            return self._error_summary(task, "timeout")
        except Exception as e:
            self.logger.error("Subprocess error: %s", e)
            return self._error_summary(task, f"subprocess_error: {e}")
        runtime = (datetime.now() - start).total_seconds()

        anomalies: list[str] = []
        if proc.returncode != 0:
            anomalies.append(f"non_zero_exit:{proc.returncode}")
            if proc.stderr:
                self.logger.warning("stderr: %s", proc.stderr[:500])

        if not output_json.exists():
            anomalies.append("missing_output")
        elif output_json.stat().st_size == 0:
            anomalies.append("empty_output")
        elif not self.monitor_data_chain(Path("."), output_json):
            anomalies.append("schema_mismatch")

        summary = self.extract_summary(output_json) if output_json.exists() else {}
        max_conf = summary.get("max_confidence", 0.0)
        if max_conf >= 0.85:
            self.mark_critical({"tool": tool, "max_confidence": max_conf, "alert_types": summary.get("alert_types", [])})
            self.logger.warning("CRITICAL marked for %s (confidence %.2f)", tool, max_conf)

        task_summary = {
            "tool": tool,
            "timestamp": datetime.now().isoformat(),
            "returncode": proc.returncode,
            "runtime_seconds": round(runtime, 2),
            "output_file": str(output_json) if output_json.exists() else None,
            "anomalies": anomalies,
            "summary": summary,
            "stdout_preview": proc.stdout[:1000] if proc.stdout else "",
            "stderr_preview": proc.stderr[:1000] if proc.stderr else "",
        }
        self.write_json(task_summary, f"task_{tool_name}.json")
        self.log_activity("task_complete", f"{tool} rc={proc.returncode}")
        return task_summary

    # ------------------------------------------------------------------
    # Data chain monitoring
    # ------------------------------------------------------------------

    def monitor_data_chain(self, input_file: Path, output_file: Path) -> bool:
        """Verify output_file exists and is valid Schema v1.0 JSON (meta, signals, details)."""
        if not output_file.exists():
            self.logger.warning("output missing — %s", output_file)
            return False
        try:
            data = self.read_json(str(output_file.relative_to(self.case_dir)))
        except Exception as e:
            self.logger.warning("read error — %s", e)
            return False
        if not isinstance(data, dict):
            return False
        missing = {"meta", "signals", "details"} - set(data.keys())
        if missing:
            self.logger.warning("missing keys %s — %s", missing, output_file)
            return False
        if not isinstance(data.get("meta"), dict) or not isinstance(data.get("signals"), list):
            return False
        self.logger.info("valid schema — %s", output_file)
        return True

    # ------------------------------------------------------------------
    # Summary extraction
    # ------------------------------------------------------------------

    def extract_summary(self, output_json: Path) -> dict:
        """Extract signals_count, alert_types, max_confidence, has_errors."""
        if not output_json.exists():
            return {"signals_count": 0, "alert_types": [], "max_confidence": 0.0, "has_errors": True}
        data = self.read_json(str(output_json.relative_to(self.case_dir)))
        if not isinstance(data, dict):
            return {"signals_count": 0, "alert_types": [], "max_confidence": 0.0, "has_errors": True}
        signals = data.get("signals", [])
        if not isinstance(signals, list):
            signals = []
        alert_types = sorted({str(s.get("type", "")) for s in signals if s.get("type")})
        confs = [float(s.get("confidence", 0.0)) for s in signals if isinstance(s, dict) and "confidence" in s]
        max_conf = max(confs) if confs else 0.0
        return {
            "signals_count": len(signals),
            "alert_types": alert_types,
            "max_confidence": round(max_conf, 3),
            "has_errors": False,
        }

    # ------------------------------------------------------------------
    # Web search placeholder
    # ------------------------------------------------------------------

    def search_web(self, query: str) -> dict:
        """
        Placeholder for future web search integration.

        Currently logs the query and returns empty results.
        Documented clearly as a stub awaiting real search API wiring.
        """
        self.logger.info("search_web placeholder: query='%s'", query)
        self.log_activity("search_web_placeholder", query)
        return {
            "query": query,
            "results": [],
            "note": "Placeholder. Integrate real search API here.",
            "timestamp": datetime.now().isoformat(),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _infer_args(self, tool_name: str, output_json: Path) -> dict[str, Any]:
        """Auto-infer common CLI arguments based on tool name."""
        inferred: dict[str, Any] = {}
        if tool_name == "preprint_monitor":
            config = load_config(self.case_dir, "config.yaml")
            name = config.get("scholar", {}).get("name", "")
            if name:
                inferred["name"] = name
            for cand in ["unified_papers.json", "papers.json", "scholar_data.json"]:
                p = self.case_dir / "outputs" / cand
                if not p.exists():
                    p = self.case_dir / cand
                if p.exists():
                    inferred["journal-papers"] = str(p)
                    break
        elif tool_name == "image_metadata_extractor":
            pdfs = self.case_dir / "pdfs"
            if pdfs.is_dir():
                inferred["pdfs"] = str(pdfs)
        else:
            for cand in ["unified_papers.json", "papers.json", "scholar_data.json"]:
                p = self.case_dir / "outputs" / cand
                if not p.exists():
                    p = self.case_dir / cand
                if p.exists():
                    inferred["papers"] = str(p)
                    break
        return inferred

    def _read_pending_tasks_from_state(self) -> list[dict]:
        """Parse STATE.md for pending PAUSED tasks assigned to 朱先生."""
        if not self.state_file.exists():
            return []
        try:
            content = self.state_file.read_text(encoding="utf-8")
        except Exception as e:
            self.logger.warning("Failed to read STATE.md: %s", e)
            return []
        tasks: list[dict] = []
        in_queue = False
        for line in content.splitlines():
            s = line.strip()
            if "Agent 任务队列" in s or "任务队列" in s:
                in_queue = True
                continue
            if in_queue and s.startswith("## "):
                break
            if in_queue and s.startswith("|") and "---" not in s:
                cells = [c.strip() for c in s.split("|") if c.strip() != ""]
                if len(cells) >= 4 and "朱" in cells[2] and ("PAUSED" in cells[3] or "等待" in cells[3] or "⏸" in cells[3]):
                    tasks.append({"tool": cells[1]})
        return tasks

    def _error_summary(self, task: dict, reason: str) -> dict:
        return {
            "tool": task.get("tool", "unknown"),
            "timestamp": datetime.now().isoformat(),
            "returncode": -1,
            "runtime_seconds": 0.0,
            "output_file": None,
            "anomalies": [reason],
            "summary": {"signals_count": 0, "alert_types": [], "max_confidence": 0.0, "has_errors": True},
            "stdout_preview": "",
            "stderr_preview": "",
        }
