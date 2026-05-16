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
from typing import Optional

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
