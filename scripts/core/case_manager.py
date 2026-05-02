#!/usr/bin/env python3
"""
case_manager.py

Lightweight case registry for Academic Detective.
Generates unique case IDs based on client name and date.

Case ID format: AD-YYYY-MM-DD-NNN
  - AD = Academic Detective
  - YYYY-MM-DD = creation date
  - NNN = daily sequence number (001, 002, ...)

Registry file: cases/cases_registry.json

Usage:
    from case_manager import CaseManager

    cm = CaseManager()
    case_id = cm.register("张三")  # -> "AD-2026-0418-001"
    info = cm.get("AD-2026-0418-001")
    all_cases = cm.list_cases()
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from core.utils import get_logger

logger = get_logger("case_manager")

REGISTRY_PATH = Path(__file__).parent.parent / "cases" / "cases_registry.json"


class CaseManager:
    """Manage case registration and ID generation."""

    def __init__(self, registry_path: Optional[Path] = None):
        self.registry_path = registry_path or REGISTRY_PATH
        self._ensure_registry()

    def _ensure_registry(self):
        """Create registry file and directory if not exists."""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.registry_path.exists():
            self._save({"cases": [], "last_updated": datetime.now().isoformat()})

    def _load(self) -> dict:
        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"cases": [], "last_updated": datetime.now().isoformat()}

    def _save(self, data: dict):
        data["last_updated"] = datetime.now().isoformat()
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _next_sequence(self, date_str: str) -> int:
        """Get next sequence number for given date."""
        data = self._load()
        prefix = f"AD-{date_str}"
        pattern = re.compile(rf"{re.escape(prefix)}-(\d{{3}})")

        max_seq = 0
        for case in data.get("cases", []):
            cid = case.get("case_id", "")
            m = pattern.match(cid)
            if m:
                max_seq = max(max_seq, int(m.group(1)))

        return max_seq + 1

    def register(self, client_name: str, notes: str = "") -> str:
        """
        Register a new case for a client.
        If client already has an active case today, return existing ID.
        Otherwise, generate a new one.

        Args:
            client_name: Client / 甲方 name
            notes: Optional notes

        Returns:
            case_id: e.g. "AD-2026-0418-001"
        """
        data = self._load()
        today = datetime.now().strftime("%Y-%m-%d")

        # Check if client already has a case today
        for case in data.get("cases", []):
            if (case.get("client_name") == client_name
                and case.get("case_id", "").startswith(f"AD-{today}")
                and case.get("status") == "active"):
                logger.info("Found existing case for '%s': %s", client_name, case["case_id"])
                return case["case_id"]

        # Generate new case ID
        seq = self._next_sequence(today)
        case_id = f"AD-{today}-{seq:03d}"

        case = {
            "case_id": case_id,
            "client_name": client_name,
            "created_at": datetime.now().isoformat(),
            "status": "active",
            "notes": notes,
        }

        data["cases"].append(case)
        self._save(data)

        logger.info("Registered new case: %s for client '%s'", case_id, client_name)
        return case_id

    def get(self, case_id: str) -> Optional[dict]:
        """Get case info by ID."""
        data = self._load()
        for case in data.get("cases", []):
            if case.get("case_id") == case_id:
                return case
        return None

    def find_by_client(self, client_name: str) -> list[dict]:
        """Find all cases for a client."""
        data = self._load()
        return [c for c in data.get("cases", []) if c.get("client_name") == client_name]

    def list_cases(self, status: Optional[str] = None) -> list[dict]:
        """List all cases, optionally filtered by status."""
        data = self._load()
        cases = data.get("cases", [])
        if status:
            cases = [c for c in cases if c.get("status") == status]
        # Sort by creation time, newest first
        return sorted(cases, key=lambda x: x.get("created_at", ""), reverse=True)

    def update_status(self, case_id: str, status: str) -> bool:
        """Update case status."""
        data = self._load()
        for case in data.get("cases", []):
            if case.get("case_id") == case_id:
                case["status"] = status
                case["updated_at"] = datetime.now().isoformat()
                self._save(data)
                logger.info("Updated case %s status to %s", case_id, status)
                return True
        logger.warning("Case %s not found", case_id)
        return False

    def close_case(self, case_id: str) -> bool:
        """Close a case."""
        return self.update_status(case_id, "closed")

    def get_state_machine(self, case_id: str) -> "CaseStateMachine":
        """Return a CaseStateMachine for the given case.

        Args:
            case_id: Case identifier.

        Returns:
            CaseStateMachine initialized with the case directory.
        """
        case_dir = self.registry_path.parent / case_id
        return CaseStateMachine(case_dir)


class CaseStateMachine:
    """9-phase state machine for investigation workflow.

    Manages phase transitions for a single case directory.
    State is persisted in ``.case/STATE.md`` and ``.case/phase_history.json``.
    """

    PHASES = [
        "initialized", "collected", "validated", "analyzed",
        "deep_evidence", "aggregated", "reported", "reviewed",
        "generated", "archived",
    ]

    PHASE_TRANSITIONS = {
        "initialized": {"next": "collected", "condition": "config.yaml exists and is valid"},
        "collected": {"next": "validated", "condition": "at least one data source file exists"},
        "validated": {"next": "analyzed", "condition": "scholar_data.json passes schema validation"},
        "analyzed": {"next": "deep_evidence", "condition": "all enabled analysis modules have run"},
        "deep_evidence": {"next": "aggregated", "condition": "all recommended deep_evidence tools have run"},
        "aggregated": {"next": "reported", "condition": "signal_aggregator has run"},
        "reported": {"next": "reviewed", "condition": "report file has been generated"},
        "reviewed": {"next": "generated", "condition": "human confirms report quality"},
        "generated": {"next": "archived", "condition": "delivery agent has generated final report"},
        "archived": {"next": None, "condition": "case is complete"},
    }

    def __init__(self, case_dir: Path):
        self.case_dir = Path(case_dir)
        self.state_dir = self.case_dir / ".case"
        self.state_file = self.state_dir / "STATE.md"
        self.history_file = self.state_dir / "phase_history.json"
        self._ensure_state_dir()

    def _ensure_state_dir(self):
        """Create .case directory if missing."""
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def get_current_phase(self) -> str:
        """Read current phase from STATE.md or default to 'initialized'."""
        if not self.state_file.exists():
            return "initialized"
        state = self.read_state_md()
        return state.get("phase", "initialized")

    def can_advance(self) -> tuple[bool, str]:
        """Check if current phase can advance to next.

        Returns:
            (can_advance, reason): bool and human-readable explanation.
        """
        phase = self.get_current_phase()
        if phase not in self.PHASE_TRANSITIONS:
            return False, f"Unknown phase: {phase}"
        rule = self.PHASE_TRANSITIONS[phase]
        if rule["next"] is None:
            return False, "Terminal phase (archived), no next phase"
        return True, rule["condition"]

    def advance(self) -> str:
        """Advance to the next phase, record history, and update STATE.md.

        Returns:
            The new phase name.

        Raises:
            RuntimeError: If phase cannot advance.
        """
        can, reason = self.can_advance()
        if not can:
            raise RuntimeError(
                f"Cannot advance from {self.get_current_phase()}: {reason}"
            )
        current = self.get_current_phase()
        next_phase = self.PHASE_TRANSITIONS[current]["next"]
        self._record_transition(current, next_phase)
        self.write_state_md(phase=next_phase)
        logger.info(
            "Case %s advanced: %s -> %s", self.case_dir.name, current, next_phase
        )
        return next_phase

    def regress(self, target_phase: str) -> str:
        """Regress to a previous phase (human override).

        Args:
            target_phase: Phase to regress to.

        Returns:
            The new phase name.

        Raises:
            ValueError: If target_phase is invalid or not before current.
        """
        current = self.get_current_phase()
        if target_phase not in self.PHASES:
            raise ValueError(f"Invalid phase: {target_phase}")
        current_idx = self.PHASES.index(current)
        target_idx = self.PHASES.index(target_phase)
        if target_idx >= current_idx:
            raise ValueError(
                f"Target phase {target_phase} is not before current phase {current}"
            )
        self._record_transition(current, target_phase, override=True)
        self.write_state_md(phase=target_phase)
        logger.info(
            "Case %s regressed: %s -> %s", self.case_dir.name, current, target_phase
        )
        return target_phase

    def get_phase_history(self) -> list[dict]:
        """Return list of phase transitions with timestamps."""
        if not self.history_file.exists():
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _record_transition(self, from_phase: str, to_phase: str, override: bool = False):
        """Append a transition entry to phase_history.json."""
        history = self.get_phase_history()
        entry = {
            "from": from_phase,
            "to": to_phase,
            "timestamp": datetime.now().isoformat(),
            "override": override,
        }
        history.append(entry)
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _parse_md_table(body: str) -> list[dict]:
        """Parse a markdown table into a list of row dicts."""
        lines = [line.strip() for line in body.splitlines() if line.strip()]
        if len(lines) < 2:
            return []
        headers = [h.strip() for h in lines[0].split("|") if h.strip()]
        rows: list[dict] = []
        for line in lines[2:]:
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if not cells:
                continue
            row = {}
            for i, h in enumerate(headers):
                row[h] = cells[i] if i < len(cells) else ""
            rows.append(row)
        return rows

    def read_state_md(self) -> dict:
        """Parse ``.case/STATE.md`` into structured data.

        Returns:
            Dict with keys such as phase, progress, recommendations,
            critical, human_decisions, unify_records.
        """
        if not self.state_file.exists():
            return {"phase": "initialized"}

        with open(self.state_file, "r", encoding="utf-8") as f:
            content = f.read()

        result: dict[str, Any] = {"phase": "initialized"}
        parts = re.split(r"\n## ", content)
        for part in parts[1:]:
            lines = part.splitlines()
            if not lines:
                continue
            header = lines[0].strip()
            body = "\n".join(lines[1:]).strip()

            if header == "Phase":
                result["phase"] = body
            elif header == "Progress":
                result["progress"] = self._parse_md_table(body)
            elif header == "Recommendations":
                result["recommendations"] = self._parse_md_table(body)
            elif header == "CRITICAL":
                result["critical"] = [
                    re.sub(r"^-\s*\[\s*\]\s*", "", line).strip()
                    for line in body.splitlines()
                    if line.strip().startswith("-")
                ]
            elif header == "Human Decisions":
                result["human_decisions"] = [
                    re.sub(r"^-\s*", "", line).strip()
                    for line in body.splitlines()
                    if line.strip().startswith("-")
                ]
            elif header.startswith("UNIFY Records"):
                result["unify_records"] = body
        return result

    @staticmethod
    def _render_table(headers: list[str], aligns: list[str], rows: list[list[str]]) -> list[str]:
        """Render a markdown table as a list of lines."""
        lines = [f"| {' | '.join(headers)} |"]
        lines.append(f"|{'|'.join(aligns)}|")
        for row in rows:
            cells = [str(c) for c in row]
            lines.append(f"| {' | '.join(cells)} |")
        return lines

    def write_state_md(self, phase: Optional[str] = None):
        """Write/update ``.case/STATE.md`` human-readable snapshot."""
        phase = phase or self.get_current_phase()
        case_id = self.case_dir.name
        current_idx = self.PHASES.index(phase)
        existing = self.read_state_md() if self.state_file.exists() else {}

        progress_headers = ["Stage", "Status", "Tool", "Output", "Signals"]
        progress_align = [":---", ":---:", ":---", ":---", ":---:"]
        progress_rows: list[list[str]] = []
        for i, p in enumerate(self.PHASES):
            status = "✅" if i < current_idx else ("🔄" if i == current_idx else "⏳")
            tool = "dynamic" if p == "deep_evidence" else "-"
            progress_rows.append([p, status, tool, "-", "-"])

        rec_headers = ["Priority", "Tool", "Rule", "Reason"]
        rec_align = [":---", ":---", ":---", ":---"]
        rec_rows: list[list[str]] = []
        if phase == "deep_evidence":
            rec_rows.append(["P1", "-", "-", "dynamic tool recommendations"])

        lines: list[str] = [
            f"# Case State: {case_id}",
            "",
            "## Phase",
            phase,
            "",
            "## Progress",
        ]
        lines.extend(self._render_table(progress_headers, progress_align, progress_rows))

        lines.extend(["", "## Recommendations"])
        lines.extend(self._render_table(rec_headers, rec_align, rec_rows))

        critical_items = existing.get("critical", [])
        lines.extend(["", "## CRITICAL"])
        for item in critical_items:
            lines.append(f"- [ ] {item}")
        if not critical_items:
            lines.append("- [ ] (none)")

        human_items = existing.get("human_decisions", [])
        lines.extend(["", "## Human Decisions"])
        for item in human_items:
            lines.append(f"- {item}")
        if not human_items:
            lines.append("- (none)")

        unify_body = existing.get("unify_records", "")
        lines.extend(["", "## UNIFY Records"])
        if unify_body:
            lines.append(unify_body)
        else:
            lines.extend(["### S01", "- (none)"])

        self.state_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Case manager for Academic Detective")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_reg = subparsers.add_parser("register", help="Register a new case")
    p_reg.add_argument("client", help="Client / 甲方 name")
    p_reg.add_argument("--notes", "-n", default="", help="Optional notes")

    p_get = subparsers.add_parser("get", help="Get case by ID")
    p_get.add_argument("case_id", help="Case ID")

    p_find = subparsers.add_parser("find", help="Find cases by client name")
    p_find.add_argument("client", help="Client name")

    p_list = subparsers.add_parser("list", help="List all cases")
    p_list.add_argument("--status", "-s", choices=["active", "closed", "all"], default="all")

    p_close = subparsers.add_parser("close", help="Close a case")
    p_close.add_argument("case_id", help="Case ID to close")

    args = parser.parse_args()
    cm = CaseManager()

    if args.command == "register":
        case_id = cm.register(args.client, args.notes)
        print(case_id)

    elif args.command == "get":
        case = cm.get(args.case_id)
        if case:
            for k, v in case.items():
                print(f"{k}: {v}")
        else:
            print("Case not found")

    elif args.command == "find":
        cases = cm.find_by_client(args.client)
        for c in cases:
            print(f"{c['case_id']} | {c['client_name']} | {c['status']} | {c['created_at']}")

    elif args.command == "list":
        status = None if args.status == "all" else args.status
        cases = cm.list_cases(status=status)
        for c in cases:
            print(f"{c['case_id']} | {c['client_name']} | {c['status']} | {c['created_at']}")

    elif args.command == "close":
        if cm.close_case(args.case_id):
            print(f"Closed: {args.case_id}")
        else:
            print("Case not found")


if __name__ == "__main__":
    main()
