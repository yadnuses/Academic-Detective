#!/usr/bin/env python3
"""
international/missing_reporter.py

Auto-generates a "manual lookup guide" after automatic API fetching.
Tells the investigator what information is still missing and where to find it.

Usage:
    python international/missing_reporter.py --case-dir ./cases/test/
    python international/missing_reporter.py --scholar-data ./scholar_data.json --output ./missing_report.md
"""

import argparse
import json
from pathlib import Path
from typing import Optional

from core_utils import get_logger, load_json

logger = get_logger("missing_reporter")

# ---------------------------------------------------------------------------
# Gap definitions
# ---------------------------------------------------------------------------

GAPS = [
    {
        "field": "verified_papers",
        "description": "经 Scopus / WoS 验证的权威论文列表",
        "severity": "critical",
        "suggested_sources": [
            "Scopus（机构VPN访问）→ 导出 CSV（全字段）",
            "Web of Science → 导出 Plain Text（Full Record）",
        ],
        "check": lambda data: bool(data.get("academic_outputs", {}).get("verified_papers") and data["academic_outputs"]["verified_papers"] != "[TO BE FILLED]"),
    },
    {
        "field": "journal_quartile",
        "description": "期刊 JCR Q分区 / CiteScore",
        "severity": "high",
        "suggested_sources": [
            "Scopus → 查看每篇论文的 CiteScore 和 SJR",
            "Journal Citation Reports (JCR) → 查看 Q1-Q4 分区",
        ],
        "check": lambda data: any(
            p.get("jcr_quartile") or p.get("cite_score")
            for p in data.get("papers", [])
        ),
    },
    {
        "field": "full_text_pdfs",
        "description": "代表性论文的全文PDF",
        "severity": "high",
        "suggested_sources": [
            "ScienceDirect / Springer / Wiley（机构IP直接下载）",
            "Unpaywall API（检查开放获取链接）",
            "机构图书馆馆际互借",
        ],
        "check": lambda data: any(
            p.get("pdf_path") and Path(p["pdf_path"]).exists()
            for p in data.get("papers", [])
        ),
    },
    {
        "field": "h_index_authoritative",
        "description": "权威的 h-index（Scopus / WoS）",
        "severity": "medium",
        "suggested_sources": [
            "Scopus 作者档案页",
            "Web of Science 作者检索",
        ],
        "check": lambda data: bool(
            data.get("metrics", {}).get("h_index_scopus") or data.get("metrics", {}).get("h_index_wos")
        ),
    },
    {
        "field": "tenure_status",
        "description": "Tenure 状态确认",
        "severity": "medium",
        "suggested_sources": [
            "学校官网 Faculty Directory",
            "院系官网 → Faculty → 查看是否有 'Tenured' 标记",
        ],
        "check": lambda data: bool(
            data.get("basic_profile", {}).get("tenure_status")
        ),
    },
    {
        "field": "funding_grants",
        "description": "主持的研究基金项目",
        "severity": "medium",
        "suggested_sources": [
            "NSF Award Search（美国）→ https://www.nsf.gov/awardsearch/",
            "NIH Reporter（生物医学）→ https://reporter.nih.gov/",
            "ERC 项目数据库（欧洲）",
            "学校官网 Research → Grants",
        ],
        "check": lambda data: len(data.get("grants", [])) > 0,
    },
    {
        "field": "student_reviews_rmp",
        "description": "RateMyProfessors 学生评价",
        "severity": "low",
        "suggested_sources": [
            "https://www.ratemyprofessors.com/ → 搜索导师姓名+学校",
        ],
        "check": lambda data: bool(
            data.get("reviews", {}).get("ratemyprofessors")
        ),
    },
    {
        "field": "phd_thesis",
        "description": "博士学位论文信息",
        "severity": "medium",
        "suggested_sources": [
            "ProQuest Dissertations & Theses（机构订阅）",
            "学校图书馆 Digital Repository",
            "OpenAlex → 搜索最早期的低被引论文（通常是学位论文拆分）",
        ],
        "check": lambda data: bool(
            data.get("basic_profile", {}).get("phd_thesis_title")
        ),
    },
    {
        "field": "ethical_compliance",
        "description": "伦理审查记录（如涉及人体/动物实验）",
        "severity": "low",
        "suggested_sources": [
            "学校 IRB / Ethics Office 公示",
            "ClinicalTrials.gov（医学研究）",
        ],
        "check": lambda data: True,  # Optional, skip if not applicable
    },
]


def identify_gaps(data: dict) -> list[dict]:
    """Identify missing fields in scholar_data."""
    gaps = []
    for gap in GAPS:
        try:
            filled = gap["check"](data)
        except Exception:
            filled = False
        if not filled:
            gaps.append({
                "field": gap["field"],
                "description": gap["description"],
                "severity": gap["severity"],
                "suggested_sources": gap["suggested_sources"],
            })
    return gaps


def suggest_lookup_sources(gaps: list[dict]) -> list[str]:
    """Flatten suggested sources from all gaps."""
    sources = []
    for gap in gaps:
        sources.extend(gap["suggested_sources"])
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for s in sources:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


def generate_missing_report(scholar_data: dict, config: dict = None) -> str:
    """
    Generate a Markdown report listing missing information and lookup guides.
    """
    config = config or {}
    name = scholar_data.get("name", "Unknown Scholar")
    institution = scholar_data.get("institution", "")
    gaps = identify_gaps(scholar_data)

    lines = [
        f"# 补充调查指南：{name}",
        "",
        f"**机构**: {institution}",
        f"**生成时间**: {__import__('datetime').datetime.now().isoformat()}",
        "",
        "> 本报告由 `missing_reporter.py` 自动生成，列出机器自动调查后仍需手动补充的信息。",
        "",
        "---",
        "",
        f"## 概览：共发现 {len(gaps)} 项待补充信息",
        "",
    ]

    # Severity summary
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for gap in gaps:
        severity_counts[gap["severity"]] += 1

    lines.append("| 优先级 | 数量 |")
    lines.append("|:---|:---:|")
    for sev in ["critical", "high", "medium", "low"]:
        if severity_counts[sev] > 0:
            label = {"critical": "🔴 关键", "high": "🟠 高", "medium": "🟡 中", "low": "🟢 低"}[sev]
            lines.append(f"| {label} | {severity_counts[sev]} |")
    lines.append("")

    # Detailed gaps
    for idx, gap in enumerate(gaps, 1):
        sev_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}[gap["severity"]]
        lines.append(f"### {idx}. {sev_emoji} {gap['description']}")
        lines.append("")
        lines.append("**建议查询来源**：")
        for src in gap["suggested_sources"]:
            lines.append(f"- {src}")
        lines.append("")

    # Quick action checklist
    lines.append("---")
    lines.append("")
    lines.append("## 快速操作清单")
    lines.append("")
    lines.append("```bash")
    lines.append("# 1. 连接机构VPN")
    lines.append("# 2. 访问 Scopus → 搜索导师姓名 → 导出 CSV")
    lines.append("# 3. 访问 Web of Science → 导出 Plain Text")
    lines.append("# 4. 将导出文件放入 ./cases/<甲方>/raw/")
    lines.append("# 5. 运行：python scripts/data_importer.py --scopus ./raw/scopus.csv --wos ./raw/wos.txt")
    lines.append("# 6. 按 DOI 清单逐个下载 PDF → 放入 ./pdfs/")
    lines.append("# 7. 运行：python scripts/international/missing_reporter.py --case-dir ./cases/<甲方>/")
    lines.append("```")
    lines.append("")

    # Tips
    lines.append("---")
    lines.append("")
    lines.append("## 调查技巧")
    lines.append("")
    lines.append("1. **Scopus 导出设置**：选择 'All fields'，包含作者ID、引用数、期刊信息")
    lines.append("2. **WoS 导出设置**：选择 'Full Record'，格式为 'Plain Text'")
    lines.append("3. **PDF 下载**：通过机构IP直接访问出版社网站，DOI链接通常可直接下载")
    lines.append("4. **Google Scholar 补充**：用于发现早期论文和预印本，但引用数不如 Scopus 准确")
    lines.append("5. **时间线一致性**：检查导师声称的任职时间与公开记录是否吻合")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate missing information lookup guide")
    parser.add_argument("--case-dir", "-C", help="Case directory containing scholar_data.json")
    parser.add_argument("--scholar-data", "-d", help="Path to scholar_data.json")
    parser.add_argument("--output", "-o", help="Output Markdown file path (default: ./missing_report.md)")
    args = parser.parse_args()

    # Resolve scholar_data path
    if args.scholar_data:
        data_path = Path(args.scholar_data)
    elif args.case_dir:
        data_path = Path(args.case_dir) / "scholar_data.json"
    else:
        data_path = Path("scholar_data.json")

    if not data_path.exists():
        logger.error("scholar_data.json not found: %s", data_path)
        # Generate a template report with all gaps
        scholar_data = {"name": "[Unknown]", "institution": "", "papers": [], "grants": []}
    else:
        scholar_data = load_json(data_path)

    report = generate_missing_report(scholar_data)

    output_path = Path(args.output) if args.output else (Path(args.case_dir) if args.case_dir else Path(".")) / "missing_report.md"
    output_path.write_text(report, encoding="utf-8")
    logger.info("Missing report saved: %s", output_path)
    print(f"[OK] 补充调查指南已生成: {output_path}")


if __name__ == "__main__":
    main()
