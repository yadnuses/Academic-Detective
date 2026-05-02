#!/usr/bin/env python3
"""
report_prompt_optimizer.py

Adapts the generic report_template.md into an LLM-optimized prompt,
injecting:
  - Summarized scholar_data context
  - Report language specification (confidence levels, prohibited phrases)
  - Discipline-specific evaluation baselines (normal ranges, red/yellow flags)

This ensures LLM output adheres to legal-safe phrasing and uses consistent,
benchmarked judgment standards instead of arbitrary relative assessments.

Supported targets:
  - claude : Full template with evidence-standard preamble and balanced-tone emphasis.
  - gpt    : Split into System Prompt (role + rules) and User Prompt (template + data context).
  - kimi   : Condensed template with top-loaded data summary.

Usage:
    python report_prompt_optimizer.py --data ./scholar_data.json --template ./report_template.md --llm claude --output ./report_prompt.md
    python report_prompt_optimizer.py --data ./corruption_network.json --template ./corruption_network_report_template.md --llm claude --output ./report_prompt.md
"""

import json
import sys
import argparse
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def find_file(name: str, search_dirs: list[Path]) -> Path | None:
    """Search for a file in multiple candidate directories."""
    for d in search_dirs:
        candidate = d / name
        if candidate.exists():
            return candidate
    return None


def is_corruption_network(data: dict) -> bool:
    return "network_name" in data and "nodes" in data and "links" in data


# ---------------------------------------------------------------------------
# Data summary builders
# ---------------------------------------------------------------------------

def build_data_summary(data: dict) -> str:
    """Extract a compact, top-level summary of scholar_data for prompt injection."""
    bp = data.get("basic_profile", {})
    ao = data.get("academic_outputs", {})
    qa = data.get("quality_assessment", {})
    anomalies = data.get("anomalies", [])
    reviews = data.get("student_reviews", {})
    ratings = data.get("confidence_ratings", {})
    hybrid = qa.get("hybrid_score_summary", {})

    lines = [
        "## 调查对象摘要",
        f"- 姓名: {bp.get('name', 'N/A')}",
        f"- 机构: {bp.get('institution', 'N/A')}",
        f"- 现任职称: {bp.get('current_title', 'N/A')}",
        f"- 学术头衔: {bp.get('academic_title', 'N/A')}",
        f"- 学科领域: {bp.get('discipline', '未指定')}",
        "",
        "## 学术产出（声称 vs 核实）",
        f"- 声称论文总数: {ao.get('claimed_papers', 'N/A')}",
        f"- 核实论文总数: {ao.get('verified_papers', 'N/A')}",
        f"- 声称专著数: {ao.get('claimed_monographs', 'N/A')}",
        f"- 核实专著数: {ao.get('verified_monographs', 'N/A')}",
        f"- 近三年论文声称: {ao.get('recent_3yr_papers', 'N/A')}",
        "",
        "## 批量论文质量评分摘要（hybrid_scorer）",
    ]
    if hybrid.get("status", "").startswith("loaded"):
        lines.extend([
            f"- 评分论文数: {hybrid.get('status', 'N/A')}",
            f"- 平均分: {hybrid.get('avg_score', 'N/A')}",
            f"- 最高分: {hybrid.get('max_score', 'N/A')}",
            f"- 最低分: {hybrid.get('min_score', 'N/A')}",
            f"- 评级分布: {hybrid.get('rating_distribution', {})}",
        ])
        top = hybrid.get("top_papers", [])
        if top:
            lines.append("- 评分最高论文:")
            for t in top[:3]:
                lines.append(f"  - {t.get('title', 'N/A')}: {t.get('score')} ({t.get('rating')})")
    else:
        lines.append("- 尚未生成混合评分报告")

    lines.extend(["", "## 关键异常信号"])
    if anomalies:
        for i, a in enumerate(anomalies[:5], 1):
            lines.append(f"{i}. [{a.get('severity', 'N/A')}] {a.get('description', 'N/A')}")
    else:
        lines.append("（尚无已录入异常）")

    # Network summary
    rel = data.get("relationship_network", {})
    lines.extend(["", "## 学术关系网络摘要"])
    advisor = rel.get("advisor")
    collabs = rel.get("key_collaborators", [])
    editorial = rel.get("editorial_connections", [])
    inst_deps = rel.get("institutional_dependencies", [])
    citation = rel.get("citation_analysis", {})
    has_advisor = advisor and str(advisor).strip() and str(advisor).strip() != "[TO BE FILLED]"
    collab_count = len(collabs) if isinstance(collabs, list) else (1 if collabs else 0)
    edit_count = len(editorial) if isinstance(editorial, list) else (1 if editorial else 0)
    inst_count = len(inst_deps) if isinstance(inst_deps, list) else (1 if inst_deps else 0)
    citation_loaded = isinstance(citation, dict) and citation.get("status") == "loaded"
    red_flag_count = len(citation.get("red_flags_detail", [])) if citation_loaded else 0
    lines.append(f"- 导师节点: {'有' if has_advisor else '无'}")
    lines.append(f"- 关键合作者: {collab_count} 人/机构")
    lines.append(f"- 编委/期刊关联: {edit_count} 个")
    lines.append(f"- 机构依附关系: {inst_count} 个")
    lines.append(f"- 引用异常信号: {red_flag_count} 条")
    if red_flag_count > 0:
        lines.append("  - 引用分析红旗明细:")
        for rf in citation.get("red_flags_detail", [])[:3]:
            lines.append(f"    - {rf.get('signal', 'N/A')}: {rf.get('detail', '')}")

    lines.extend([
        "",
        "## 学生评价摘要",
        f"- 匹配状态: {reviews.get('status', 'N/A')}",
        f"- 评价数量: {reviews.get('count', 'N/A')}",
        f"- 平均评分: {reviews.get('average_rating', 'N/A')}",
        "",
        "## 置信度评级",
    ])
    for k, v in ratings.items():
        lines.append(f"- {k}: {v}")

    lines.append("")
    return "\n".join(lines)


def build_network_summary(data: dict) -> str:
    """Extract a compact summary of corruption_network for prompt injection."""
    network_name = data.get("network_name", "N/A")
    nodes = data.get("nodes", [])
    links = data.get("links", [])
    cases = data.get("cases", [])
    timelines = data.get("timelines", [])
    grants = data.get("grants", [])
    negative_space = data.get("negative_space", {})

    node_types = {}
    for n in nodes:
        t = n.get("type", "unknown")
        node_types[t] = node_types.get(t, 0) + 1

    anomaly_links = [l for l in links if l.get("is_anomaly")]
    protector_nodes = [n for n in nodes if n.get("type") == "protector"]
    core_nodes = [n for n in nodes if n.get("type") == "core_subject"]

    lines = [
        f"## 腐败网络调查摘要: {network_name}",
        f"- 网络名称: {network_name}",
        f"- 节点总数: {len(nodes)}",
        f"- 关系边总数: {len(links)}",
        f"- 异常关系边数: {len(anomaly_links)}",
        f"- 案件节点数: {len(cases)}",
        f"- 时间线数: {len(timelines)}",
        f"- 基金关联数: {len(grants)}",
        "",
        "## 节点类型分布",
    ]
    for t, c in sorted(node_types.items()):
        lines.append(f"- {t}: {c}")

    lines.extend(["", "## 核心调查对象"])
    if core_nodes:
        for n in core_nodes[:5]:
            lines.append(f"- {n.get('name', 'N/A')} ({n.get('institution', 'N/A')}): {n.get('detail', '')}")
    else:
        lines.append("- 未标记核心调查对象")

    lines.extend(["", "## 关键结构性庇护节点"])
    if protector_nodes:
        for p in protector_nodes[:5]:
            lines.append(f"- {p.get('name', 'N/A')} ({p.get('institution', 'N/A')}): {p.get('detail', '')}")
    else:
        lines.append("- 未检测到结构性庇护节点")

    lines.extend(["", "## 异常关系信号（前5条）"])
    if anomaly_links:
        for l in anomaly_links[:5]:
            lines.append(f"- {l.get('source', '')} → {l.get('target', '')} ({l.get('type', '')}): {l.get('detail', '')}")
    else:
        lines.append("- 无异常关系标记")

    if cases:
        lines.extend(["", "## 案件节点"])
        for case in cases[:5]:
            lines.append(f"- {case.get('name', 'N/A')} ({case.get('type', '')} / {case.get('date', 'N/A')}): {case.get('detail', '')}")

    if timelines:
        lines.extend(["", "## 时间线统计"])
        for tl in timelines[:3]:
            ev_count = len(tl.get("events", []))
            lines.append(f"- {tl.get('name', 'N/A')}: {ev_count} 个事件")

    if grants:
        lines.extend(["", "## 基金关联摘要"])
        for g in grants[:3]:
            lines.append(f"- {g.get('grant_id', 'N/A')}: {g.get('name', 'N/A')} (PI: {g.get('pi', 'N/A')})")

    if negative_space:
        lines.extend([
            "",
            f"## 官方通报负面空间分析",
            f"- 信息回避度评分: {negative_space.get('evasion_score', 'N/A')} / 1.0",
        ])
        matrix = negative_space.get("matrix", [])
        unanswered = [m for m in matrix if m.get("score", 0) == 0.0]
        partial = [m for m in matrix if 0 < m.get("score", 0) < 0.5]
        if unanswered:
            lines.append(f"- 完全未回应问题: {len(unanswered)} 项")
            lines.append("- 关键未解问题:")
            for m in unanswered[:5]:
                lines.append(f"  - {m.get('question', '')} (严重度: {m.get('severity', '')})")
        if partial:
            lines.append(f"- 模糊/否认性回应: {len(partial)} 项")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Baseline extractor
# ---------------------------------------------------------------------------

def extract_relevant_baselines(baselines_text: str, discipline: str, title: str) -> str:
    """Extract baseline sections relevant to the scholar's discipline and title."""
    lines = baselines_text.splitlines()
    extracted = []
    in_relevant_section = False
    current_section_score = 0

    scholar_keywords = set()
    discipline_lower = (discipline or "").lower()
    title_lower = (title or "").lower()

    if any(k in discipline_lower for k in ["人文", "社科", "文学", "历史", "哲学", "经济", "管理", "法学", "教育", "艺术", "hss"]):
        scholar_keywords.add("人文社科")
    elif any(k in discipline_lower for k in ["医学", "生命", "临床", "生物", "med"]):
        scholar_keywords.add("医学/生命科学")
    else:
        scholar_keywords.add("理工科")

    if any(k in title_lower for k in ["副", "associate", "副教授"]):
        scholar_keywords.add("副教授")
    elif any(k in title_lower for k in ["资深", "院士", "长江", "杰青", "首席", "distinguished"]):
        scholar_keywords.add("资深教授")
    else:
        scholar_keywords.add("教授")

    general_sections = {
        "一、基准线使用说明",
        "二、学术产出数量基准",
        "三、研究聚焦度基准",
        "四、作者署名基准",
        "五、学生培养基准",
        "六、经费与项目基准",
        "七、质量评分基准",
        "八、快速参考",
    }

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") or stripped.startswith("### "):
            header = stripped.lstrip("# ").strip()
            in_relevant_section = False
            current_section_score = 0

            if any(g in header for g in general_sections):
                in_relevant_section = True
                current_section_score = 1

            for kw in scholar_keywords:
                if kw in header:
                    in_relevant_section = True
                    current_section_score = 2
                    break

            if in_relevant_section:
                extracted.append(line)
        elif in_relevant_section:
            extracted.append(line)

    result = "\n".join(extracted)
    if len(result) < 500:
        result = "\n".join(lines[:120])

    return result


# ---------------------------------------------------------------------------
# Language spec extractor
# ---------------------------------------------------------------------------

def extract_language_spec(spec_text: str) -> str:
    """Extract the most critical parts of the language spec for prompt injection."""
    lines = spec_text.splitlines()
    extracted = []
    in_priority_section = False
    priority_sections = {
        "一、置信度五级体系",
        "二、定性表述措辞模板",
        "三、禁用词清单",
        "四、正面对比示例",
        "五、学科差异调整规则",
    }

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") or stripped.startswith("### "):
            header = stripped.lstrip("# ").strip()
            in_priority_section = any(p in header for p in priority_sections)
            if in_priority_section:
                extracted.append(line)
        elif in_priority_section:
            extracted.append(line)

    result = "\n".join(extracted)
    if len(result) < 500:
        result = "\n".join(lines[:150])
    return result


# ---------------------------------------------------------------------------
# Prompt builders per LLM
# ---------------------------------------------------------------------------

def build_language_preamble() -> str:
    return (
        "## 语言规范（强制性）\n\n"
        "你生成的每一条定性判断都必须遵守以下规范。违规内容将被视为不合格输出。\n\n"
        "### 置信度五级体系\n"
        "| 等级 | 措辞要求 |\n"
        "|:---:|:---|\n"
        "| L5 确认 | '经查证''可确认''记录显示' —— 需≥2个独立权威来源 |\n"
        "| L4 高度可能 | '极有可能''高度疑似''强烈暗示' —— 强证据+少量推断 |\n"
        "| L3 疑似 | '疑似''存在…迹象''有…嫌疑''可能涉及' —— 单一可靠来源 |\n"
        "| L2 线索 | '有…传言''评价中提及…''部分受访者反映' —— 匿名/非权威来源 |\n"
        "| L1 无证据 | 不表述，或明确说'未找到相关证据' |\n\n"
        "### 绝对禁用词（出现即违规）\n"
        "- '学术造假''学术腐败''学术骗子''学阀''水货''学术垃圾'\n"
        "- '典型的…''毫无疑问''结论是…''属于…（负面类型）'\n"
        "- '无耻''卑鄙''阴险''黑心''恶毒''人渣'等情绪化词汇\n"
        "- '导致…'（推断因果）→ 改为'与…存在关联'\n"
        "- '说明了…'（推断）→ 改为'这可能暗示…'\n\n"
        "### 正面示例（必须模仿的风格）\n"
        "- Bad: '该学者研究过于单一，缺乏视野，只会炒冷饭。'\n"
        "- Good: '其近10年研究集中于'金融周期'领域（约占总产出78%），在人文学科属于正常范围（基准：60-90%），符合'专精'而非'狭隘'的界定。'\n"
        "- Bad: '该导师抢学生一作，剥削学生成果。'\n"
        "- Good: '在其团队2020-2025年发表的23篇论文中，导师作为第一作者的有11篇（47.8%）。在理工科领域，资深导师routine一作比例应<20%，当前比例超出基准上限，存在署名权分配异常迹象（置信度：L3）。'\n\n"
    )


def build_baseline_preamble(baselines_text: str, discipline: str, title: str) -> str:
    relevant = extract_relevant_baselines(baselines_text, discipline, title)
    return (
        f"## 学科基准线参考（{discipline or '未指定学科'} / {title or '未指定职称'}）\n\n"
        "在做出任何'是否正常'的判断前，必须先对照以下基准线。无基准线的判断都是无效输出。\n\n"
        f"{relevant}\n\n"
        "### 关键判断流程（生成报告前必须执行）\n"
        "1. 计算学者的实际指标（如聚焦度、年均论文数、一作比例等）\n"
        "2. 在上方基准线表格中找到对应的'正常区间'\n"
        "3. 如果落在正常区间内 → 评价为'正常'，并引用基准线作为依据\n"
        "4. 如果落在黄色信号区间 → 标注为'值得关注'，说明需要进一步调查的因素\n"
        "5. 如果落在红色信号区间 → 标注为'异常'，但仍需使用L3/L4级措辞\n"
        "6. 严禁越过基准线直接做主观评价（如'研究单一''跨度太大'）\n\n"
    )


def build_network_baseline_preamble(heuristics_text: str = "") -> str:
    base = (
        "## 腐败网络分析基准（强制性）\n\n"
        "本报告为腐败网络/多人物关系调查，不适用单一学者的学术产出基准线。"
        "请遵循以下分析原则：\n\n"
        "1. **结构性庇护（S→C）**：当存在'protector'类型节点向'core_subject'提供"
        "手术签名、学术通信作者、职位庇护时，必须标注为'结构性庇护'并给出置信度。\n"
        "2. **异常关系边**：所有标记为 `is_anomaly: true` 的边必须重点分析，"
        "说明其异常性（如时间冲突、资质缺失、资金流向不明等）。\n"
        "3. **时间线耦合**：若存在高耦合时间窗口（6个月内多个关键节点发生事件），"
        "必须解释其潜在关联，但严禁推断因果。\n"
        "4. **负面空间分析**：对官方通报中完全未回应或模糊回应的问题，"
        "必须逐条列出并评估其信息回避度。\n"
        "5. **两面性原则**：即使调查对象涉及严重违规，仍需指出其"
        "学术贡献、职务合法性或程序正义的一面。\n\n"
    )
    if heuristics_text and len(heuristics_text.strip()) > 50:
        base += (
            "### 从历史调查中萃取的启发式规则\n\n"
            "以下规则来自以往案件的后验分析，若当前网络数据与某条规则匹配，"
            "请在报告中明确引用该规则并评估置信度。\n\n"
            f"{heuristics_text}\n\n"
        )
    return base


def optimize_for_claude(template: str, data_summary: str, language_spec: str, baselines_text: str,
                        discipline: str, title: str, is_network: bool, heuristics_text: str = "") -> str:
    if is_network:
        preamble = (
            "你是一位严谨的学术/腐败网络调查分析师。你的任务是依据下方提供的结构化数据、"
            "语言规范和腐败网络分析基准，生成一份平衡、客观、证据链完整的腐败网络调查报告（Markdown格式）。\n\n"
            "### 角色与约束\n"
            "1. 你不是评论家，你是证据分析师。每一条判断必须有数据或来源支撑。\n"
            "2. 你不是法官，你不能定罪。所有负面发现只能停留在'疑似'层面，除非有≥2个独立权威来源。\n"
            "3. 你必须先对照腐败网络分析基准，再给出评价。\n"
            "4. 两面性原则：每指出一个系统性问题，必须同时指出一个可确认的正面事实。\n"
            "5. 格式：严格遵循模板中的章节结构，不要删减章节。\n"
            "6. 免责声明：必须在末尾保留完整的免责声明。\n\n"
        )
        baseline_preamble = build_network_baseline_preamble(heuristics_text)
    else:
        preamble = (
            "你是一位严谨的学术调查分析师。你的任务是依据下方提供的结构化数据、"
            "语言规范和学科基准线，生成一份平衡、客观、证据链完整的学术档案调查报告（Markdown格式）。\n\n"
            "### 角色与约束\n"
            "1. 你不是评论家，你是证据分析师。每一条判断必须有数据或来源支撑。\n"
            "2. 你不是法官，你不能定罪。所有负面发现只能停留在'疑似'层面，除非有≥2个独立权威来源。\n"
            "3. 你必须先对照基准线，再给出评价。没有基准线的评价是不被接受的。\n"
            "4. 两面性原则：每指出一个问题，必须同时指出一个可确认的优点。\n"
            "5. 格式：严格遵循模板中的章节结构，不要删减章节。\n"
            "6. 免责声明：必须在末尾保留完整的免责声明。\n\n"
        )
        baseline_preamble = build_baseline_preamble(baselines_text, discipline, title)

    lang_preamble = build_language_preamble()

    return (
        f"{preamble}"
        f"{lang_preamble}"
        f"---\n\n"
        f"{baseline_preamble}"
        f"---\n\n"
        f"{data_summary}\n"
        f"---\n\n"
        f"# 报告模板\n\n"
        f"请根据以上数据、语言规范和基准线，填充以下模板，生成完整报告。\n\n"
        f"{template}"
    )


def optimize_for_gpt(template: str, data_summary: str, language_spec: str, baselines_text: str,
                     discipline: str, title: str, is_network: bool, heuristics_text: str = "") -> str:
    system_prompt = (
        "You are an impartial academic investigation analyst. "
        "You write balanced, evidence-based reports in Chinese (academic/formal tone).\n\n"
        "CRITICAL RULES (violations will be rejected):\n"
        "1. Every negative claim must cite a verifiable source.\n"
        "2. For every weakness, mention a confirmed strength.\n"
        "3. Do not omit any section from the template.\n"
        "4. All subjective qualitative conclusions must use confidence-level hedging:\n"
        "   - L5 (confirmed): '经查证''可确认' —— ≥2 independent authoritative sources\n"
        "   - L4 (highly likely): '极有可能''高度疑似'\n"
        "   - L3 (suspected): '疑似''存在…迹象''有…嫌疑'\n"
        "   - L2 (rumor): '有…传言''评价中提及'\n"
        "   - L1 (no evidence): state '未找到相关证据' or omit\n"
        "5. NEVER use: '学术造假''学术腐败''学术骗子''学阀''水货''典型的''毫无疑问''结论是…''属于…（负面）'\n"
        "6. Before judging if something is 'normal' or 'abnormal', you MUST consult the evaluation baselines provided in the user prompt.\n"
        "7. Include the full disclaimer at the end."
    )

    lang_preamble = build_language_preamble()
    if is_network:
        baseline_preamble = build_network_baseline_preamble(heuristics_text)
    else:
        baseline_preamble = build_baseline_preamble(baselines_text, discipline, title)

    user_prompt = (
        f"{lang_preamble}\n"
        f"---\n\n"
        f"{baseline_preamble}\n"
        f"---\n\n"
        f"{data_summary}\n"
        f"---\n\n"
        f"请根据以上数据、语言规范和基准线，填充以下模板，生成完整的 Markdown 调查报告。\n"
        f"用 `{{{{placeholder}}}}` 标记的模板字段需要你根据数据摘要和合理推断来填充。\n\n"
        f"{template}"
    )

    return (
        "# SYSTEM PROMPT\n\n"
        f"```\n{system_prompt}\n```\n\n"
        "# USER PROMPT\n\n"
        f"{user_prompt}"
    )


def optimize_for_kimi(template: str, data_summary: str, language_spec: str, baselines_text: str,
                      discipline: str, title: str, is_network: bool, heuristics_text: str = "") -> str:
    lang_preamble = build_language_preamble()
    if is_network:
        baseline_preamble = build_network_baseline_preamble(heuristics_text)
    else:
        baseline_preamble = build_baseline_preamble(baselines_text, discipline, title)

    condensed_instructions = (
        "任务：生成一份调查报告（Markdown）。\n"
        "语气：冷静、客观、克制。\n"
        "核心约束：\n"
        "- 使用下方模板中的章节标题，不删减。\n"
        "- 每个负面结论必须有证据来源，且使用置信度分级措辞（疑似/存在迹象/高度疑似/经查证）。\n"
        "- 所有定性推断严禁一锤定音（禁用'是典型的''属于''结论为'）。\n"
        "- 必须先对照基准线/腐败网络分析基准，再判断是否正常。\n"
        "- 必须包含两面性分析（优点+问题）。\n"
        "- 保留免责声明。\n\n"
    )
    return (
        f"{condensed_instructions}"
        f"{lang_preamble}\n"
        f"---\n\n"
        f"{baseline_preamble}\n"
        f"---\n\n"
        f"{data_summary}\n"
        f"---\n\n"
        f"{template}"
    )


def optimize_prompt(template: str, data: dict, llm: str, language_spec: str, baselines_text: str, heuristics_text: str = "") -> str:
    is_network = is_corruption_network(data)
    if is_network:
        summary = build_network_summary(data)
        discipline = ""
        title = ""
    else:
        summary = build_data_summary(data)
        bp = data.get("basic_profile", {})
        discipline = bp.get("discipline", "")
        title = bp.get("current_title", "")

    if llm == "claude":
        return optimize_for_claude(template, summary, language_spec, baselines_text, discipline, title, is_network, heuristics_text)
    elif llm == "gpt":
        return optimize_for_gpt(template, summary, language_spec, baselines_text, discipline, title, is_network, heuristics_text)
    elif llm == "kimi":
        return optimize_for_kimi(template, summary, language_spec, baselines_text, discipline, title, is_network, heuristics_text)
    else:
        return optimize_for_claude(template, summary, language_spec, baselines_text, discipline, title, is_network, heuristics_text)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Optimize report prompt for a target LLM")
    parser.add_argument("--data", "-d", required=True, help="Path to scholar_data.json or corruption_network.json")
    parser.add_argument("--template", "-t", required=True, help="Path to report_template.md")
    parser.add_argument("--llm", "-l", default="claude", choices=["claude", "gpt", "kimi"], help="Target LLM")
    parser.add_argument("--output", "-o", required=True, help="Path to output prompt markdown")
    parser.add_argument("--spec", "-s", default=None, help="Path to report_language_spec.md (auto-detected if omitted)")
    parser.add_argument("--baselines", "-b", default=None, help="Path to evaluation_baselines.md (auto-detected if omitted)")
    parser.add_argument("--heuristics", default=None, help="Path to heuristics.md (auto-detected if omitted)")
    args = parser.parse_args()

    # Resolve spec and baselines paths
    script_dir = Path(__file__).parent.resolve()
    search_dirs = [script_dir, script_dir.parent, Path.cwd()]

    spec_path = Path(args.spec) if args.spec else find_file("report_language_spec.md", search_dirs)
    baselines_path = Path(args.baselines) if args.baselines else find_file("evaluation_baselines.md", search_dirs)
    heuristics_path = Path(args.heuristics) if args.heuristics else find_file("heuristics.md", search_dirs)

    print(f"[INFO] Loading data: {args.data}")
    data = load_json(args.data)
    mode = "corruption_network" if is_corruption_network(data) else "scholar_data"
    print(f"[INFO] Detected mode: {mode}")

    print(f"[INFO] Loading template: {args.template}")
    template = load_text(args.template)

    language_spec = ""
    if spec_path and spec_path.exists():
        print(f"[INFO] Loading language spec: {spec_path}")
        language_spec = load_text(str(spec_path))
    else:
        print("[WARN] report_language_spec.md not found. Language constraints will be basic.")

    baselines_text = ""
    if baselines_path and baselines_path.exists():
        print(f"[INFO] Loading evaluation baselines: {baselines_path}")
        baselines_text = load_text(str(baselines_path))
    else:
        print("[WARN] evaluation_baselines.md not found. Baseline calibration will be skipped.")

    heuristics_text = ""
    if heuristics_path and heuristics_path.exists():
        print(f"[INFO] Loading heuristics: {heuristics_path}")
        heuristics_text = load_text(str(heuristics_path))
    else:
        print("[WARN] heuristics.md not found. Heuristic injection will be skipped.")

    print(f"[INFO] Optimizing for LLM: {args.llm}")
    optimized = optimize_prompt(template, data, args.llm, language_spec, baselines_text, heuristics_text)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(optimized)

    print(f"[INFO] Optimized prompt saved to: {args.output}")
    print(f"[SUMMARY] LLM target: {args.llm}, Prompt length: {len(optimized)} chars")
    print(f"[SUMMARY] Language spec: {'loaded' if language_spec else 'not found'}")
    print(f"[SUMMARY] Baselines: {'loaded' if baselines_text else 'not found'}")
    print(f"[SUMMARY] Heuristics: {'loaded' if heuristics_text else 'not found'}")
    print(f"[SUMMARY] Mode: {mode}")


if __name__ == "__main__":
    main()
