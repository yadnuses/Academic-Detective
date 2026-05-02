#!/usr/bin/env python3
"""
agents/laozhoumo.py — Coordinator / Supervisor Agent (老周末)

Persona: 沉稳、全局观、不说废话、只在关键时刻开口。
Responsibilities:
    - Monitor all agents via agent_logs/.
    - Detect CRITICAL markers and escalate to human.
    - Interface with 周老师 for decisions (exclusive human I/O).
    - Write and maintain STATE.md (exclusive authority).
    - Broadcast task updates to other agents.
    - Pause / resume the entire system.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.case_manager import CaseStateMachine
from core.recommendation_engine import RuleEngine
from core.utils import get_logger

from agents.base import BaseAgent

AGENT_NAMES = ["zhu_xiansheng", "dududu", "huangmao", "laozhoumo"]


class LaoZhoumo(BaseAgent):
    """Coordinator agent — monitors all agents, interfaces with human, intercepts decisions."""

    def __init__(self, case_dir: Path):
        super().__init__(case_dir, "laozhoumo")
        self.state_machine = CaseStateMachine(case_dir)
        self.rule_engine = RuleEngine()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, context: dict | None = None) -> dict:
        """Main entry point for a coordinator round."""
        context = context or {}
        self.log_activity("coordinator_round", "started")
        status = self.monitor_all_agents()
        critical = self.detect_critical()
        updates: dict[str, Any] = {
            "agent_status": status,
            "critical_count": len(critical),
            "timestamp": datetime.now().isoformat(),
        }
        if critical:
            updates["critical_items"] = critical
            recs = self.rule_engine.evaluate(self.case_dir)
            updates["recommendations"] = [
                {"priority": r.priority, "tools": r.tools, "reason": r.reason, "rule_id": r.rule_id}
                for r in recs
            ]
        self.update_state_md(updates)
        result = {
            "agent": self.name,
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "critical": critical,
            "paused": self._is_paused(),
            "phase": self.state_machine.get_current_phase(),
        }
        self.write_json(result, "coordinator_summary.json")
        self.log_activity("coordinator_round", f"complete critical={len(critical)}")
        return result

    # ------------------------------------------------------------------
    # Monitoring
    # ------------------------------------------------------------------

    def monitor_all_agents(self) -> dict:
        """Check all agent log directories for status and critical markers."""
        status: dict[str, dict] = {}
        for agent in AGENT_NAMES:
            agent_log_dir = self.case_dir / "agent_logs" / agent
            last_output, has_critical, agent_status = "", False, "idle"
            if agent_log_dir.exists():
                json_files = sorted(agent_log_dir.glob("*.json"))
                if json_files:
                    latest = json_files[-1]
                    try:
                        data = json.loads(latest.read_text(encoding="utf-8"))
                        last_output = latest.name
                        agent_status = data.get("status", "completed") if isinstance(data, dict) else "completed"
                    except (json.JSONDecodeError, OSError):
                        last_output = latest.name
                        agent_status = "error"
                has_critical = (agent_log_dir / "critical.json").exists()
                if has_critical:
                    agent_status = "critical"
            status[agent] = {"status": agent_status, "last_output": last_output, "has_critical": has_critical}
        self.logger.info("Monitored %d agents", len(AGENT_NAMES))
        return status

    def detect_critical(self) -> list[dict]:
        """Scan all agent log directories for critical.json markers."""
        items: list[dict] = []
        for agent in AGENT_NAMES:
            path = self.case_dir / "agent_logs" / agent / "critical.json"
            if path.exists():
                data = self.read_json(f"agent_logs/{agent}/critical.json")
                if data and data.get("critical"):
                    items.append({
                        "agent": agent,
                        "timestamp": data.get("timestamp", datetime.now().isoformat()),
                        "context": data.get("context", {}),
                    })
                    self.logger.warning("CRITICAL from %s: %s", agent, data.get("context", {}))
        return items

    # ------------------------------------------------------------------
    # Human interface
    # ------------------------------------------------------------------

    def request_decision(self, context: dict) -> str:
        """Format a decision request for the human and persist it."""
        case_id = self.case_dir.name
        phase = self.state_machine.get_current_phase()
        key_finding = context.get("key_finding", "需要人工判断")
        impact = context.get("impact", "影响当前调查走向")
        options = context.get("options", ["继续", "暂停", "回退"])
        while len(options) < 3:
            options.append("待定")
        lines = [
            "=" * 43,
            f"决策请求: {case_id} / {phase}",
            "=" * 43,
            "",
            f"发现: {key_finding}",
            "",
            f"影响评估: {impact}",
            "",
            "建议选项:",
        ]
        for idx, opt in enumerate(options[:3], start=1):
            lines.append(f"{chr(64 + idx)}. {opt}")
        lines.extend(["", "请回复选项字母，或描述您的决策:"])
        text = "\n".join(lines)
        print(text)
        self.write_json({
            "case_id": case_id, "phase": phase, "key_finding": key_finding,
            "impact": impact, "options": options[:3],
            "timestamp": datetime.now().isoformat(),
        }, "decision_request.json")
        self.log_activity("request_decision", key_finding)
        return text

    def parse_human_response(self, response: str, context: dict) -> dict:
        """Parse human's response into structured decision."""
        response = response.strip()
        decision = {"decision": response, "action": "unknown", "tool": "", "reason": "human_choice"}
        upper = response.upper()
        if upper in ("A", "B", "C"):
            options = context.get("options", ["继续", "暂停", "回退"])
            idx = ord(upper) - ord("A")
            chosen = options[idx] if idx < len(options) else "unknown"
            decision.update({"decision": upper, "action": "choose_option", "tool": chosen})
        elif upper == "SKIP":
            decision["action"] = "skip"
        elif upper.startswith("RUN "):
            decision.update({"action": "run_tool", "tool": response[4:].strip()})
        elif upper in ("PAUSE", "STOP"):
            decision["action"] = "pause"
        elif upper in ("RESUME", "GO"):
            decision["action"] = "resume"
        else:
            decision.update({"action": "custom", "tool": response})
        self.log_activity("parse_human_response", f"{decision['action']}:{decision.get('tool', '')}")
        self.write_json(decision, "human_decision.json")
        return decision

    def generate_decision_context(self, critical_items: list[dict], recommendations: list[dict]) -> dict:
        """Build the full context needed for a decision request."""
        case_id = self.case_dir.name
        phase = self.state_machine.get_current_phase()
        findings: list[str] = []
        for item in critical_items:
            ctx = item.get("context", {})
            if isinstance(ctx, dict):
                tool = ctx.get("tool", "unknown")
                reason = ctx.get("reason", ctx.get("alert_types", "critical signal"))
                findings.append(f"[{item['agent']}] {tool}: {reason}")
            else:
                findings.append(f"[{item['agent']}] {str(ctx)}")
        key_finding = "; ".join(findings) if findings else "检测到异常信号"
        impact = "可能导致后续分析方向偏差，需要人工确认"
        options = ["接受建议并继续", "暂停调查，等待进一步指示", "回退到上一阶段重新分析"]
        if recommendations:
            top = recommendations[0]
            options[0] = f"执行推荐工具: {', '.join(top.get('tools', ['continue']))}"
        return {
            "case_id": case_id, "phase": phase, "key_finding": key_finding,
            "impact": impact, "options": options,
            "critical_count": len(critical_items), "recommendation_count": len(recommendations),
        }

    # ------------------------------------------------------------------
    # Task broadcast
    # ------------------------------------------------------------------

    def broadcast_task_update(self, tasks: list[dict]) -> Path:
        """Write updated task list as the official assignment for other agents."""
        path = self.write_json({
            "broadcast_by": self.name,
            "timestamp": datetime.now().isoformat(),
            "tasks": tasks,
        }, "broadcast.json")
        self.log_activity("broadcast_tasks", f"count={len(tasks)}")
        return path

    # ------------------------------------------------------------------
    # STATE.md management (exclusive authority)
    # ------------------------------------------------------------------

    def update_state_md(self, updates: dict) -> Path:
        """Read existing STATE.md, apply updates, and write back."""
        state_file = self.state_file
        existing: dict[str, Any] = self.state_machine.read_state_md() if state_file.exists() else {}
        phase = updates.get("phase", existing.get("phase", "initialized"))
        case_id = self.case_dir.name
        if "agent_status" in updates:
            progress_rows = self._build_progress_rows(updates["agent_status"], phase)
        else:
            progress_rows = self._table_dicts_to_rows(existing.get("progress", []), ["Stage", "Status", "Tool", "Output", "Signals"])
        if "recommendations" in updates:
            rec_rows = self._build_recommendation_rows(updates["recommendations"])
        else:
            rec_rows = self._table_dicts_to_rows(existing.get("recommendations", []), ["Priority", "Tool", "Rule", "Reason"])
        critical_items: list[str] = existing.get("critical", [])
        if "critical_items" in updates:
            critical_items = self._build_critical_items(updates["critical_items"])
        human_decisions: list[str] = existing.get("human_decisions", [])
        if "human_decision" in updates:
            human_decisions.append(f"{datetime.now().isoformat()} — {updates['human_decision']}")
        unify_records = existing.get("unify_records", "")
        lines: list[str] = [
            f"# Case State: {case_id}", "", "## Phase", phase, "", "## Progress",
        ]
        lines.extend(self._render_table(["Stage", "Status", "Tool", "Output", "Signals"], [":---", ":---:", ":---", ":---", ":---:"], progress_rows))
        lines.extend(["", "## Recommendations"])
        lines.extend(self._render_table(["Priority", "Tool", "Rule", "Reason"], [":---", ":---", ":---", ":---"], rec_rows))
        lines.extend(["", "## CRITICAL"])
        for item in critical_items:
            lines.append(f"- [ ] {item}")
        if not critical_items:
            lines.append("- [ ] (none)")
        lines.extend(["", "## Human Decisions"])
        for item in human_decisions:
            lines.append(f"- {item}")
        if not human_decisions:
            lines.append("- (none)")
        lines.extend(["", "## UNIFY Records"])
        if unify_records:
            lines.append(unify_records)
        else:
            lines.extend(["### S01", "- (none)"])
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.logger.info("Updated STATE.md (%s)", state_file)
        self.log_activity("update_state_md", f"phase={phase}")
        return state_file

    # ------------------------------------------------------------------
    # Pause / resume
    # ------------------------------------------------------------------

    def pause_all(self):
        """Write a pause signal."""
        flag = self.log_dir / "pause.flag"
        flag.write_text(datetime.now().isoformat(), encoding="utf-8")
        self.log_activity("pause_all", "system paused")
        self.logger.warning("System paused by %s", self.name)

    def resume_all(self):
        """Remove pause signal if present."""
        flag = self.log_dir / "pause.flag"
        if flag.exists():
            flag.unlink()
            self.log_activity("resume_all", "system resumed")
            self.logger.info("System resumed by %s", self.name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_paused(self) -> bool:
        return (self.log_dir / "pause.flag").exists()

    def _build_progress_rows(self, agent_status: dict, phase: str) -> list[list[str]]:
        rows: list[list[str]] = []
        for agent, info in agent_status.items():
            status_icon = "✅" if info["status"] == "completed" else ("🔄" if info["status"] in ("running", "critical") else "⏳")
            signal_icon = "⚠️" if info["has_critical"] else "-"
            rows.append([agent, status_icon, info["last_output"], "-", signal_icon])
        rows.append(["phase", phase, "-", "-", "-"])
        return rows

    def _build_recommendation_rows(self, recs: list[dict]) -> list[list[str]]:
        return [[str(r.get("priority", "-")), ", ".join(r.get("tools", [])), r.get("rule_id", "-"), r.get("reason", "")] for r in recs]

    def _build_critical_items(self, items: list[dict]) -> list[str]:
        results: list[str] = []
        for item in items:
            ctx = item.get("context", {})
            if isinstance(ctx, dict):
                tool = ctx.get("tool", "unknown")
                reason = ctx.get("reason", ctx.get("alert_types", "critical signal"))
                results.append(f"[{item['agent']}] {tool}: {reason}")
            else:
                results.append(f"[{item['agent']}] {str(ctx)}")
        return results

    @staticmethod
    def _table_dicts_to_rows(dicts: list[dict], headers: list[str]) -> list[list[str]]:
        return [[str(d.get(h, "-")) for h in headers] for d in dicts]

    @staticmethod
    def _render_table(headers: list[str], aligns: list[str], rows: list[list[str]]) -> list[str]:
        lines = [f"| {' | '.join(headers)} |", f"|{'|'.join(aligns)}|"]
        for row in rows:
            lines.append(f"| {' | '.join(str(c) for c in row)} |")
        return lines
