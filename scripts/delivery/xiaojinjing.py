"""
Xiaojinjing (Delivery Generator)

Reads structured material package from Xiaotangdou,
generates final deliverables (Markdown report + HTML network graph),
and performs self-check against ban rules, format rules, and content rules.
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime

from .delivery_base import BaseDeliveryAgent, ChecklistRunner


class Xiaojinjing(BaseDeliveryAgent):
    """
    Delivery Generator Agent.

    Personality: rigorous, perfectionist, format-obsessed.
    Does not read raw agent logs; only reads Xiaotangdou's material package.
    """

    def __init__(self, case_dir: Path):
        super().__init__(case_dir, "xiaojinjing")
        self.checklist_dir = Path(__file__).parent / "checklists"

    def run(self) -> Dict[str, Any]:
        """
        Execute the full generation pipeline (G01-G06).
        Returns delivery manifest.
        """
        self.log("Starting generation pipeline G01-G06")

        # Check Xiaotangdou checkpoint
        checkpoint = self._read_checkpoint()
        if not checkpoint:
            raise RuntimeError("Xiaotangdou checkpoint not found. Run collect first.")
        if checkpoint.get("critical"):
            self.log("WARNING: Xiaotangdou reported critical gaps. Proceeding with caution.")

        # G01: Read material package
        materials = self._read_material_package()
        self.log(f"G01 complete: {len(materials)} chapters loaded")

        # G02: Generate Markdown report
        md_report = self._generate_markdown_report(materials)
        md_path = self.reports_dir / f"{self._get_scholar_name()}_学术档案调查报告_FINAL.md"
        self.write_text(md_report, md_path)
        self.log(f"G02 complete: Markdown report generated ({len(md_report)} chars)")

        # G03: Generate HTML network graph
        html_path = self._generate_network_html()
        self.log(f"G03 complete: HTML network graph generated")

        # G04-G05: Self-check
        ban_fails, ban_details = self._check_ban_rules(md_report)
        fmt_fails, fmt_details = self._check_format_rules(md_report)
        content_fails, content_details = self._check_content_rules(md_report)
        self.log(f"G04-G05 complete: {ban_fails} ban, {fmt_fails} format, {content_fails} content issues")

        # G06: Write delivery manifest
        manifest = {
            "agent": "xiaojinjing",
            "generated_at": datetime.now().isoformat(),
            "deliverables": {
                "markdown_report": str(md_path.relative_to(self.case_dir)),
                "network_html": str(html_path.relative_to(self.case_dir)) if html_path else None,
            },
            "self_check": {
                "ban_rules": {"failed": ban_fails, "details": ban_details},
                "format_rules": {"failed": fmt_fails, "details": fmt_details},
                "content_rules": {"failed": content_fails, "details": content_details},
            },
            "pass_status": ban_fails == 0 and fmt_fails == 0 and content_fails == 0,
        }
        manifest_path = self.reports_dir / "delivery_manifest.json"
        self.write_json(manifest, manifest_path)

        # Write self-check report
        self_check_report = self._generate_self_check_report(
            ban_details, fmt_details, content_details
        )
        self.write_text(self_check_report, self.reports_dir / "self_check_report.md")

        self.log("Generation complete")
        return manifest

    def _read_checkpoint(self) -> Dict:
        """Read Xiaotangdou's collection checkpoint."""
        path = self.delivery_dir / "collection_checkpoint.json"
        return self.read_json(path)

    def _read_material_package(self) -> Dict[str, str]:
        """G01: Read structured material package from delivery/ directory."""
        materials = {}
        for f in sorted(self.delivery_dir.glob("chapter_*.md")):
            key = f.stem
            materials[key] = self.read_text(f)
        return materials

    def _get_scholar_name(self) -> str:
        """Extract scholar name from STATE.md or directory name."""
        state_paths = list(self.case_dir.rglob("STATE.md"))
        if state_paths:
            text = self.read_text(state_paths[0])
            match = re.search(r"\| 姓名 \| (.+?) \|", text)
            if match:
                return match.group(1).strip()
        return self.case_dir.name

    def _generate_markdown_report(self, materials: Dict[str, str]) -> str:
        """G02: Generate final Markdown report from materials."""
        lines = []

        # Title
        name = self._get_scholar_name()
        lines.append(f"# {name}学术档案调查报告\n")
        lines.append(f"\n> 报告编号: {self._get_case_id()}\n")
        lines.append("> 数据来源: 学校官网、期刊数据库、社会组织公示、新闻报道\n")
        lines.append("\n---\n")

        # Assemble chapters in order
        chapter_order = [
            "chapter_01_executive_summary",
            "chapter_02_basic_profile",
            "chapter_03_output_quantity",
            "chapter_04_quality_assessment",
            "chapter_05_network_analysis",
            "chapter_06_anomaly_detection",
            "chapter_07_multi_source_validation",
            "chapter_08_conclusions",
            "chapter_09_appendix",
        ]

        for key in chapter_order:
            content = materials.get(key, "")
            if not content or "[待补充" in content:
                content = f"\n[本章素材待补充: {key}]\n"
            lines.append(content)
            lines.append("\n---\n")

        # Disclaimer (must be present)
        lines.append("\n## 免责声明\n")
        lines.append("\n1. 本报告基于公开网络信息和学术数据库进行独立调查，所有结论均来自可验证的公开来源。\n")
        lines.append("2. 本报告不构成法律意见、专业鉴定或官方定性。\n")
        lines.append("3. 报告中标注为待确认、存疑的信息属于信息缺口，在获得进一步证据之前不应作为定论使用。\n")
        lines.append("4. 本调查未进行实地走访，未直接向当事人或相关机构进行询问核实。\n")
        lines.append("5. 本报告版权归委托方所有，仅供委托方内部参考使用。\n")
        lines.append("6. 调查者不对因使用本报告而产生的任何直接或间接损失承担责任。\n")

        report = "\n".join(lines)

        # Post-process: remove time stamps and identity markers
        report = self._sanitize_for_delivery(report)
        return report

    def _sanitize_for_delivery(self, text: str) -> str:
        """Remove time stamps, agent names, client references, and banned patterns."""
        # Remove generation timestamps and date references
        text = re.sub(r"\*报告生成时间:.*\*\n?", "", text)
        text = re.sub(r"\*调查架构:.*\*\n?", "", text)
        text = re.sub(r"\*协作模式:.*\*\n?", "", text)
        text = re.sub(r"\*最终审批:.*\*\n?", "", text)
        text = re.sub(r"> 调查日期:.*\n?", "", text)
        text = re.sub(r"报告生成时间|生成日期|调查日期|报告日期|完成日期", "", text)

        # Remove agent names and identities
        text = re.sub(r"\*分析者:.*\*\n?", "", text)
        text = re.sub(r"\*报告生成.*", "", text)
        text = re.sub(r"小y|Agent|调查者|分析者|报告生成者", "", text)

        # Remove client references
        text = re.sub(r"周老师", "委托方", text)

        # Replace dashes with periods
        text = text.replace("——", "。")
        # Replace common negative expressions with neutral alternatives
        text = text.replace("没有", "未见")

        # Remove empty lines created by removal
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _generate_network_html(self) -> Path:
        """G03: Generate HTML network graph by calling network_visualizer."""
        # Find scholar_data JSON
        json_files = list(self.case_dir.glob("scholar_data*.json")) + list(self.case_dir.glob("*_network.json"))
        if not json_files:
            self.log("WARNING: No scholar_data JSON found, skipping HTML generation")
            return None

        input_json = json_files[0]
        prefix = self._get_scholar_name()

        # Call network_visualizer
        nv_path = Path(__file__).parent.parent / "network" / "network_visualizer.py"
        if nv_path.exists():
            try:
                result = subprocess.run(
                    [
                        "python3", str(nv_path),
                        "--input", str(input_json),
                        "--output-dir", str(self.reports_dir),
                        "--prefix", prefix,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                self.log(f"network_visualizer output: {result.stdout}")
                if result.returncode != 0:
                    self.log(f"network_visualizer error: {result.stderr}")
                html_path = self.reports_dir / f"{prefix}_network.html"
                return html_path if html_path.exists() else None
            except Exception as e:
                self.log(f"HTML generation failed: {e}")
                return None
        else:
            self.log(f"network_visualizer.py not found at {nv_path}")
            return None

    def _check_ban_rules(self, content: str) -> Tuple[int, List[Dict]]:
        """G04: Run ban rules self-check."""
        runner = ChecklistRunner(self.checklist_dir)
        fails, details = runner.run_ban_rules(content)
        return fails, details

    def _check_format_rules(self, content: str) -> Tuple[int, List[Dict]]:
        """G04: Run format rules self-check."""
        runner = ChecklistRunner(self.checklist_dir)
        fails, details = runner.run_format_rules(content)
        return fails, details

    def _check_content_rules(self, content: str) -> Tuple[int, List[Dict]]:
        """G04: Run content rules self-check."""
        # Extract chapters for chapter counting
        chapters = re.findall(r"^## .+$", content, re.MULTILINE)
        runner = ChecklistRunner(self.checklist_dir)
        fails, details = runner.run_content_rules(content, chapters)
        return fails, details

    def _generate_self_check_report(
        self,
        ban_details: List[Dict],
        fmt_details: List[Dict],
        content_details: List[Dict],
    ) -> str:
        """G05: Generate human-readable self-check report."""
        lines = ["# 自检报告\n\n"]
        lines.append(f"检查时间: 2026年4月\n\n")
        lines.append("---\n\n")

        all_issues = ban_details + fmt_details + content_details
        errors = [d for d in all_issues if d.get("severity") == "error" and not d.get("passed", True)]
        warnings = [d for d in all_issues if d.get("severity") == "warning" and not d.get("passed", True)]

        lines.append("## 结果汇总\n\n")
        lines.append(f"- 错误: {len(errors)} 项\n")
        lines.append(f"- 警告: {len(warnings)} 项\n")
        lines.append(f"- 通过: {len(all_issues) - len(errors) - len(warnings)} 项\n\n")

        if errors:
            lines.append("## 错误项（必须修复）\n\n")
            for d in errors:
                lines.append(f"- **{d['rule_id']}** {d['rule_name']}: {d['detail']}\n")
            lines.append("\n")

        if warnings:
            lines.append("## 警告项（建议修复）\n\n")
            for d in warnings:
                lines.append(f"- **{d['rule_id']}** {d['rule_name']}: {d['detail']}\n")
            lines.append("\n")

        if not errors:
            lines.append("## 结论\n\n所有错误项已清零，报告可交付。\n")
        else:
            lines.append("## 结论\n\n存在未修复的错误项，请修复后重新自检。\n")

        return "".join(lines)

    def _get_case_id(self) -> str:
        """Extract case ID from directory structure."""
        case_dirs = list(self.case_dir.glob(".cases/*"))
        if case_dirs:
            return case_dirs[0].name
        return "AD-2026-04-21-001"


if __name__ == "__main__":
    import sys
    case_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    agent = Xiaojinjing(case_dir)
    result = agent.run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
