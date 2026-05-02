"""
Delivery layer shared base classes and utilities.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime


class BaseDeliveryAgent:
    """Base class for delivery agents (Xiaotangdou & Xiaojinjing)."""

    def __init__(self, case_dir: Path, name: str):
        self.case_dir = Path(case_dir)
        self.name = name
        self.log_dir = self.case_dir / "agent_logs" / name
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.delivery_dir = self.case_dir / "delivery"
        self.reports_dir = self.case_dir / "reports"
        self.delivery_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def read_json(self, path: Path) -> dict:
        """Read a JSON file safely."""
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def write_json(self, data: dict, path: Path):
        """Write data to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def write_text(self, text: str, path: Path):
        """Write text to a file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def read_text(self, path: Path) -> str:
        """Read text from a file."""
        if not path.exists():
            return ""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def log(self, message: str):
        """Log a message to the agent's log file."""
        log_file = self.log_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {message}\n")

    def find_files(self, pattern: str, directory: Path = None) -> List[Path]:
        """Find files matching a glob pattern."""
        directory = directory or self.case_dir
        return list(directory.rglob(pattern))


class ChecklistRunner:
    """Runs checklists against content."""

    def __init__(self, checklists_dir: Path):
        self.checklists_dir = Path(checklists_dir)
        self.results = []

    def load_checklist(self, name: str) -> List[Dict[str, Any]]:
        """Load a checklist JSON file."""
        path = self.checklists_dir / f"{name}.json"
        data = self._load_json(path)
        return data.get("rules", [])

    def _load_json(self, path: Path) -> dict:
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def run_ban_rules(self, content: str) -> Tuple[int, List[Dict]]:
        """Run ban rules against content. Returns (fail_count, details)."""
        rules = self.load_checklist("ban_rules")
        fails = []
        for rule in rules:
            result = self._check_rule(rule, content)
            if not result["passed"]:
                fails.append(result)
        self.results.extend(fails)
        return len(fails), fails

    def run_format_rules(self, content: str) -> Tuple[int, List[Dict]]:
        """Run format rules against content."""
        rules = self.load_checklist("format_rules")
        fails = []
        for rule in rules:
            result = self._check_rule(rule, content)
            if not result["passed"]:
                fails.append(result)
        self.results.extend(fails)
        return len(fails), fails

    def run_content_rules(self, content: str, chapters: List[str] = None) -> Tuple[int, List[Dict]]:
        """Run content rules against content."""
        rules = self.load_checklist("content_rules")
        fails = []
        for rule in rules:
            result = self._check_rule(rule, content, chapters)
            if not result["passed"]:
                fails.append(result)
        self.results.extend(fails)
        return len(fails), fails

    def _check_rule(self, rule: Dict, content: str, chapters: List[str] = None) -> Dict:
        """Check a single rule against content."""
        rule_id = rule.get("id", "UNKNOWN")
        rule_name = rule.get("name", "")
        severity = rule.get("severity", "warning")

        passed = True
        detail = ""

        # Check forbidden keywords
        if "forbidden_keywords" in rule:
            found = []
            for kw in rule["forbidden_keywords"]:
                if kw in content:
                    found.append(kw)
            if found:
                passed = False
                detail = f"发现禁用关键词: {', '.join(found)}"

        # Check regex pattern
        elif "pattern" in rule:
            pattern = rule["pattern"]
            matches = re.findall(pattern, content)
            max_count = rule.get("max_count")
            max_per_1000 = rule.get("max_per_1000_chars")
            max_per_chapter = rule.get("max_per_chapter")

            if max_count is not None and len(matches) > max_count:
                passed = False
                detail = f"发现 {len(matches)} 处匹配（上限 {max_count}）"
            elif max_per_1000 is not None:
                count = len(matches)
                chars = len(content)
                limit = max(1, chars // 1000) * max_per_1000
                if count > limit:
                    passed = False
                    detail = f"发现 {count} 处匹配（每千字上限 {max_per_1000}）"
            elif max_per_chapter is not None and chapters:
                # Simplified: count per chapter not implemented
                pass

        # Check required chapters
        elif "required_chapters" in rule and chapters:
            if len(chapters) < rule["required_chapters"]:
                passed = False
                detail = f"仅发现 {len(chapters)} 章（需 {rule['required_chapters']} 章）"

        # Manual check placeholder
        elif rule.get("check_method") == "manual":
            detail = "需人工复核"

        return {
            "rule_id": rule_id,
            "rule_name": rule_name,
            "severity": severity,
            "passed": passed,
            "detail": detail,
        }

    def generate_report(self) -> str:
        """Generate a self-check report from results."""
        lines = ["# 自检报告\n", f"检查时间: {datetime.now().isoformat()}\n", "---\n"]
        errors = [r for r in self.results if r["severity"] == "error" and not r["passed"]]
        warnings = [r for r in self.results if r["severity"] == "warning" and not r["passed"]]
        passed = [r for r in self.results if r["passed"]]

        lines.append(f"## 结果汇总\n")
        lines.append(f"- 错误: {len(errors)} 项\n")
        lines.append(f"- 警告: {len(warnings)} 项\n")
        lines.append(f"- 通过: {len(passed)} 项\n\n")

        if errors:
            lines.append("## 错误项\n")
            for r in errors:
                lines.append(f"- **{r['rule_id']}** {r['rule_name']}: {r['detail']}\n")
            lines.append("\n")

        if warnings:
            lines.append("## 警告项\n")
            for r in warnings:
                lines.append(f"- **{r['rule_id']}** {r['rule_name']}: {r['detail']}\n")
            lines.append("\n")

        if not errors and not warnings:
            lines.append("## 结论\n\n所有检查项全部通过，报告可交付。\n")
        else:
            lines.append("## 结论\n\n存在未通过项，请修复后重新自检。\n")

        return "".join(lines)
