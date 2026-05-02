"""
Xiaotangdou (Delivery Collector)

Collects, categorizes, sorts, and structures raw agent outputs
into a structured delivery package organized by report chapters.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
from collections import defaultdict

from .delivery_base import BaseDeliveryAgent


CHAPTER_MAP = {
    "chapter_01_executive_summary": "执行摘要",
    "chapter_02_basic_profile": "基本档案与时间线",
    "chapter_03_output_quantity": "产出数量验证",
    "chapter_04_quality_assessment": "质量评估",
    "chapter_05_network_analysis": "关系网络分析",
    "chapter_06_anomaly_detection": "异常检测",
    "chapter_07_multi_source_validation": "多源交叉验证",
    "chapter_08_conclusions": "平衡结论",
    "chapter_09_appendix": "附录",
}


class Xiaotangdou(BaseDeliveryAgent):
    """
    Delivery Collector Agent.

    Personality: meticulous, organized, archive-manager-like rigor.
    Does not modify raw content; only categorizes, sorts, deduplicates.
    """

    def __init__(self, case_dir: Path):
        super().__init__(case_dir, "xiaotangdou")

    def run(self) -> Dict[str, Any]:
        """
        Execute the full collection pipeline (C01-C05).
        Returns a checkpoint dict for handoff to Xiaojinjing.
        """
        self.log("Starting collection pipeline C01-C05")

        # C01: Gather raw materials
        raw_materials = self._gather_raw_materials()
        self.log(f"C01 complete: {len(raw_materials)} source files found")

        # C02: Categorize by chapter
        categorized = self._categorize_by_chapter(raw_materials)
        self.log(f"C02 complete: {len(categorized)} chapters prepared")

        # C03: Identify gaps and conflicts
        gaps, conflicts = self._identify_gaps_and_conflicts(categorized)
        self.log(f"C03 complete: {len(gaps)} gaps, {len(conflicts)} conflicts")

        # C04: Sort and deduplicate
        structured = self._sort_and_deduplicate(categorized)
        self.log("C04 complete: sorting and deduplication done")

        # C05: Validate against framework
        checklist = self._validate_framework(structured)
        self.log(f"C05 complete: {checklist['passed']}/{checklist['total']} checks passed")

        # Write outputs
        self._write_outputs(structured, gaps, conflicts, checklist)

        # Return checkpoint
        checkpoint = {
            "agent": "xiaotangdou",
            "task": "collection_complete",
            "status": "ready_for_generation",
            "chapters_ready": len([c for c in structured.values() if c.strip()]),
            "gaps_count": len(gaps),
            "conflicts_count": len(conflicts),
            "framework_checks": checklist,
            "critical": len(gaps) > 3 or len(conflicts) > 1,
        }
        self.write_json(checkpoint, self.delivery_dir / "collection_checkpoint.json")
        self.log("Collection checkpoint written")
        return checkpoint

    def _gather_raw_materials(self) -> Dict[str, str]:
        """C01: Traverse all agent logs and outputs."""
        materials = {}

        # Agent logs
        for agent_name in ["zhu_xiansheng", "dududu", "huangmao", "laozhoumo"]:
            log_dir = self.case_dir / "agent_logs" / agent_name
            if log_dir.exists():
                for f in log_dir.glob("*.json"):
                    materials[f"agent:{agent_name}/{f.name}"] = self.read_text(f)
                for f in log_dir.glob("*.md"):
                    materials[f"agent:{agent_name}/{f.name}"] = self.read_text(f)

        # STATE.md
        state_path = self.case_dir / ".cases" / "AD-2026-04-21-001" / "STATE.md"
        if not state_path.exists():
            # Try to find any STATE.md
            states = list(self.case_dir.rglob("STATE.md"))
            if states:
                state_path = states[0]
        if state_path.exists():
            materials["STATE.md"] = self.read_text(state_path)

        # Existing reports
        for f in self.case_dir.glob("*报告*.md"):
            materials[f"report:{f.name}"] = self.read_text(f)

        # JSON data files
        for f in self.case_dir.glob("*.json"):
            materials[f"data:{f.name}"] = self.read_text(f)

        return materials

    def _categorize_by_chapter(self, materials: Dict[str, str]) -> Dict[str, str]:
        """C02: Categorize materials into 9 report chapters."""
        chapters = {key: "" for key in CHAPTER_MAP.keys()}

        # Parse STATE.md for structured data
        state_content = materials.get("STATE.md", "")

        # Chapter 1: Executive Summary (from STATE overview + cross-module links)
        chapters["chapter_01_executive_summary"] = self._extract_executive_summary(state_content)

        # Chapter 2: Basic Profile (from STATE scholar info + timeline)
        chapters["chapter_02_basic_profile"] = self._extract_basic_profile(state_content)

        # Chapter 3: Output Quantity (from STATE output list + paper details)
        chapters["chapter_03_output_quantity"] = self._extract_output_quantity(state_content)

        # Chapter 4: Quality Assessment (from paper review reports)
        chapters["chapter_04_quality_assessment"] = self._extract_quality_assessment(materials)

        # Chapter 5: Network Analysis (from dududu analysis + network data)
        chapters["chapter_05_network_analysis"] = self._extract_network_analysis(materials)

        # Chapter 6: Anomaly Detection (from STATE anomaly list + verification results)
        chapters["chapter_06_anomaly_detection"] = self._extract_anomaly_detection(state_content)

        # Chapter 7: Multi-Source Validation (from cross-reference tables)
        chapters["chapter_07_multi_source_validation"] = self._extract_validation(state_content)

        # Chapter 8: Conclusions (from STATE risk ratings + findings)
        chapters["chapter_08_conclusions"] = self._extract_conclusions(state_content)

        # Chapter 9: Appendix (from agent logs + methodology)
        chapters["chapter_09_appendix"] = self._extract_appendix(materials)

        return chapters

    def _extract_executive_summary(self, state: str) -> str:
        lines = ["## 素材来源：STATE.md 总览\n"]
        # Extract scholar info
        if "Scholar" in state:
            lines.append(state.split("## Scholar")[1].split("##")[0] if "## Scholar" in state else "")
        # Extract risk ratings
        if "风险评级" in state or "risk" in state.lower():
            lines.append("\n## 风险评级汇总\n")
            lines.append(self._extract_section(state, "风险评级", "##"))
        return "\n".join(lines)

    def _extract_basic_profile(self, state: str) -> str:
        lines = ["## 素材来源：STATE.md 基本信息 + 时间线\n"]
        lines.append(self._extract_section(state, "基本信息", "##"))
        lines.append("\n")
        lines.append(self._extract_section(state, "职业时间线", "##"))
        return "\n".join(lines)

    def _extract_output_quantity(self, state: str) -> str:
        lines = ["## 素材来源：STATE.md 产出清单 + 期刊门槛\n"]
        lines.append(self._extract_section(state, "产出清单", "##"))
        lines.append("\n")
        lines.append(self._extract_section(state, "期刊门槛", "##"))
        return "\n".join(lines)

    def _extract_quality_assessment(self, materials: Dict[str, str]) -> str:
        lines = ["## 素材来源：论文审查报告 + 六维评估\n"]
        for key, content in materials.items():
            if "论文审查" in key or "quality" in key.lower():
                lines.append(f"\n### 来自 {key}\n")
                lines.append(content[:3000])
        return "\n".join(lines)

    def _extract_network_analysis(self, materials: Dict[str, str]) -> str:
        lines = ["## 素材来源：嘟嘟嘟网络分析 + network.json\n"]
        for key, content in materials.items():
            if "网络" in key or "network" in key.lower() or "dududu" in key:
                lines.append(f"\n### 来自 {key}\n")
                lines.append(content[:3000])
        return "\n".join(lines)

    def _extract_anomaly_detection(self, state: str) -> str:
        lines = ["## 素材来源：STATE.md 疑点清单 + CRITICAL标记\n"]
        lines.append(self._extract_section(state, "疑点清单", "##"))
        lines.append("\n")
        lines.append(self._extract_section(state, "CRITICAL", "##"))
        return "\n".join(lines)

    def _extract_validation(self, state: str) -> str:
        lines = ["## 素材来源：STATE.md 多源交叉验证\n"]
        lines.append(self._extract_section(state, "验证", "##"))
        return "\n".join(lines)

    def _extract_conclusions(self, state: str) -> str:
        lines = ["## 素材来源：STATE.md 结论与评级\n"]
        lines.append(self._extract_section(state, "结论", "##"))
        lines.append("\n")
        lines.append(self._extract_section(state, "评级", "##"))
        return "\n".join(lines)

    def _extract_appendix(self, materials: Dict[str, str]) -> str:
        lines = ["## 素材来源：Agent日志 + 调查方法\n"]
        for key, content in materials.items():
            if "agent:" in key:
                lines.append(f"\n### {key}\n")
                # Summarize JSON content
                if content.strip().startswith("{"):
                    try:
                        data = json.loads(content)
                        lines.append(f"- 类型: {data.get('agent', 'unknown')}\n")
                        lines.append(f"- 任务: {data.get('task', 'unknown')}\n")
                        lines.append(f"- 状态: {data.get('status', 'unknown')}\n")
                    except Exception:
                        lines.append(content[:500])
                else:
                    lines.append(content[:1000])
        return "\n".join(lines)

    def _extract_section(self, text: str, section_name: str, delimiter: str = "##") -> str:
        """Extract a section from markdown text."""
        if section_name not in text:
            return f"[待补充: {section_name}]\n"
        parts = text.split(f"{delimiter} ")
        for part in parts:
            if part.startswith(section_name) or section_name in part.split("\n")[0]:
                return f"{delimiter} {part.split(delimiter)[0].strip()}"
        return f"[待补充: {section_name}]\n"

    def _identify_gaps_and_conflicts(self, chapters: Dict[str, str]) -> Tuple[List[str], List[str]]:
        """C03: Mark information gaps and contradictions."""
        gaps = []
        conflicts = []

        for chapter_key, content in chapters.items():
            if "[待补充" in content:
                gaps.append(f"{CHAPTER_MAP[chapter_key]}: 存在未填充素材")
            if len(content) < 200:
                gaps.append(f"{CHAPTER_MAP[chapter_key]}: 内容过少（{len(content)}字符）")

        # Check for contradictions between chapters
        # Example: basic profile says 2014 graduation, anomaly says 2015 student
        basic = chapters.get("chapter_02_basic_profile", "")
        anomaly = chapters.get("chapter_06_anomaly_detection", "")
        if "2014" in basic and "2015" in anomaly and "学生" in anomaly:
            conflicts.append("基本档案称2014年毕业，异常检测提到2015年学生身份，时间线需澄清")

        return gaps, conflicts

    def _sort_and_deduplicate(self, chapters: Dict[str, str]) -> Dict[str, str]:
        """C04: Sort and deduplicate within each chapter."""
        result = {}
        for key, content in chapters.items():
            # Simple dedup: remove duplicate lines
            lines = content.split("\n")
            seen = set()
            unique_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped and stripped not in seen:
                    seen.add(stripped)
                    unique_lines.append(line)
            result[key] = "\n".join(unique_lines)
        return result

    def _validate_framework(self, chapters: Dict[str, str]) -> Dict[str, Any]:
        """C05: Validate material coverage against report framework."""
        checks = []
        for key, name in CHAPTER_MAP.items():
            content = chapters.get(key, "")
            has_content = len(content) > 100 and "[待补充" not in content
            checks.append({
                "chapter": name,
                "key": key,
                "has_content": has_content,
                "char_count": len(content),
            })

        passed = sum(1 for c in checks if c["has_content"])
        return {
            "total": len(checks),
            "passed": passed,
            "details": checks,
        }

    def _write_outputs(
        self,
        chapters: Dict[str, str],
        gaps: List[str],
        conflicts: List[str],
        checklist: Dict,
    ):
        """Write all delivery outputs."""
        # Chapter materials
        for key, content in chapters.items():
            self.write_text(content, self.delivery_dir / f"{key}.md")

        # Gaps and conflicts
        gaps_text = "# 信息缺口与矛盾点\n\n"
        if gaps:
            gaps_text += "## 信息缺口\n" + "\n".join(f"- {g}" for g in gaps) + "\n\n"
        else:
            gaps_text += "## 信息缺口\n无\n\n"
        if conflicts:
            gaps_text += "## 矛盾点\n" + "\n".join(f"- {c}" for c in conflicts) + "\n\n"
        else:
            gaps_text += "## 矛盾点\n无\n\n"
        self.write_text(gaps_text, self.delivery_dir / "gaps_and_conflicts.md")

        # Collection manifest
        manifest = {
            "agent": "xiaotangdou",
            "generated_at": "2026-04-21T13:00:00",
            "chapters": {k: len(v) for k, v in chapters.items()},
            "gaps": gaps,
            "conflicts": conflicts,
            "framework_check": checklist,
        }
        self.write_json(manifest, self.delivery_dir / "collection_manifest.json")


if __name__ == "__main__":
    import sys
    case_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    agent = Xiaotangdou(case_dir)
    result = agent.run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
