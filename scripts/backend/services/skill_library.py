"""SKILL.md chapter library for on-demand loading via function calling."""
import re
from pathlib import Path

SKILL_PATH = Path("/Users/xiaoy/.local/share/uv/tools/kimi-cli/lib/python3.13/site-packages/kimi_cli/skills/academic-investigation-skill/SKILL.md")

# Map section display names to regex patterns for finding the section
SECTIONS = {
    # Core workflow
    "overview": "^## Overview",
    "when_to_use": "^## When to Use",
    "workflow_philosophy": "^## Semi-Automatic Workflow Philosophy",
    "7_step_framework": "^## 7-Step Investigation Framework",
    "step_1_basic_profile": "^### Step 1: Basic Profile Establishment",
    "step_2_output_quantity": "^### Step 2: Academic Output Quantity Verification",
    "step_3_quality_assessment": "^### Step 3: Academic Quality Assessment",
    "step_4_relationship_network": "^### Step 4: Relationship Network",
    "step_5_anomaly_detection": "^### Step 5: Anomaly Detection",
    "step_6_cross_validation": "^### Step 6: Multi-Source Cross-Validation",
    "step_7_report_generation": "^### Step 7: Synthesis & Report Generation",
    "investigation_checklist": "^## Investigation Checklist",
    "special_investigation_types": "^## Special Investigation Types",
    "case_studies": "^## Case Studies",
    # Extension modules
    "module_a_admin_output": "^## 扩展调查模块 A",
    "module_b_home_advantage": "^## 扩展调查模块 B",
    "module_c_paper_upstream": "^## 扩展调查模块 C",
    "module_d_influence_fraud": "^## 扩展调查模块 D",
    "module_e_ghostwriting": "^## 扩展调查模块 E",
    "module_f_funding_network": "^## 扩展调查模块 F",
    "module_g_digital_archaeology": "^## 扩展调查模块 G",
    "module_h_corruption_network": "^## 扩展调查模块 H",
    # v3.x architecture
    "v3_deep_evidence": "^## v3.0 架构扩充：深度证据层",
    "v3_state_machine": "^## v3.1 架构扩充：反应式案件状态机",
    "v3_multi_agent": "^## v3.2 架构扩充：多智能体协作调查层",
    "full_architecture": "^## 完整架构总览",
}

# Human-readable names for function calling schema
SECTION_NAMES = list(SECTIONS.keys())


def _load_skill_text() -> str:
    if not SKILL_PATH.exists():
        return "[SKILL.md not found]"
    return SKILL_PATH.read_text(encoding="utf-8")


def get_section(name: str, max_chars: int = 8000) -> str:
    """Extract a section from SKILL.md by its key name."""
    if name not in SECTIONS:
        available = ", ".join(SECTION_NAMES)
        return f"[Error: section '{name}' not found. Available: {available}]"

    text = _load_skill_text()
    pattern = SECTIONS[name]

    # Find the start of the section
    start_match = re.search(pattern, text, re.MULTILINE)
    if not start_match:
        return f"[Error: could not locate section '{name}' in SKILL.md]"

    start = start_match.start()

    # Find the end: next heading at same or higher level
    # Get the heading level of our section
    heading_line = text[start:text.find("\n", start)]
    level = len(heading_line) - len(heading_line.lstrip("#"))

    # Search for next heading at same or higher level (fewer #)
    end_pattern = rf"^#{{1,{level}}}\s"
    end_match = re.search(end_pattern, text[start + 1 :], re.MULTILINE)
    if end_match:
        end = start + 1 + end_match.start()
    else:
        end = len(text)

    content = text[start:end].strip()
    if len(content) > max_chars:
        content = content[:max_chars] + "\n\n[内容已截断，该章节较长]"
    return content


def list_sections() -> list:
    """Return all available section names."""
    return SECTION_NAMES


# Convenience: get multiple sections concatenated
def get_sections(names: list, max_chars: int = 12000) -> str:
    """Get multiple sections concatenated."""
    parts = []
    total = 0
    for name in names:
        part = get_section(name, max_chars=max_chars // len(names))
        if total + len(part) > max_chars:
            break
        parts.append(part)
        total += len(part)
    return "\n\n---\n\n".join(parts)
