#!/usr/bin/env python3
"""
investigation_demo_visual.py — 魅影学术侦探 · 调查流程终端动画演示

以某院士院士为例，三步骤视觉化呈现：
  步骤1 开始初步调查（身份基线核实）
  步骤2 审查论文质量（产出核实 + 六维评估）
  步骤3 多agent深度挖掘（全网并发扫描）

用法：
    python3 scripts/investigation_demo_visual.py
"""

import os
import random
import sys
import time
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import (
    BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn,
)
from rich.table import Table
from rich.tree import Tree
from rich.columns import Columns
from rich.text import Text
from rich import box
from rich.align import Align
from rich.layout import Layout

console = Console()

# ──────────────────────────────────────────────
# 模拟数据：某院士
# ──────────────────────────────────────────────
SCHOLAR = {
    "name": "某院士",
    "name_en": "某某",
    "institution": "目标院校",
    "institution_en": "USTC",
    "gender": "女",
    "birth": "1967年7月23日",
    "hometown": "安徽阜阳",
    "title": "中国科学院院士",
    "titles": ["中国科学院院士(2013)", "发展中国家科学院院士(2015)", "亚太材料科学院院士(2015)", "英国皇家化学会会士(2013)"],
    "phd_year": 1996,
    "phd_institution": "目标院校",
    "phd_major_claimed": "应用化学系",
    "phd_major_actual": "凝聚态物理",
    "phd_advisor": "钱逸泰",
    "overseas": [
        ("纽约州立大学石溪分校", "1997.09-1998.07", "博士后"),
        ("宾州州立大学", "2001.04-2001.06", "短期访问学者(2个月)"),
    ],
    "awards": ["2015年世界杰出女科学家成就奖", "2012年国家自然科学二等奖(第一完成人)"],
    "papers_claimed": 330,
    "papers_verified": 300,
    "nature_count": 10,
    "jacs_count": 32,
    "angew_count": 25,
    "adv_mater_count": 11,
    "citations": 35000,
    "h_index": 80,
    "pubpeer_result": "阴性",
    "retraction_result": "无记录",
    "risk_level": "低风险",
}

# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────
def typewriter(text: str, style: str = "", delay: float = 0.015):
    """打字机效果输出一行"""
    for char in text:
        console.print(f"[{style}]{char}[/{style}]", end="")
        time.sleep(delay)
    console.print()

def fake_progress(desc: str, color: str, steps: int = 5, delay: float = 0.3):
    """模拟一个进度条"""
    with Progress(
        SpinnerColumn("dots", style=color),
        TextColumn(f"[bold {color}]{{task.description}}"),
        BarColumn(bar_width=25, complete_style=color),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(desc, total=steps * 20)
        for i in range(steps):
            time.sleep(delay + random.uniform(0, 0.2))
            progress.update(task, advance=20)

def ascii_radar(labels: list[str], values: list[float], width: int = 40):
    """用字符画一个简易雷达图"""
    max_val = max(values) if values else 1
    lines = []
    lines.append("    " + "  ".join(f"{l[:4]:4s}" for l in labels))
    for row in range(10, 0, -1):
        threshold = row / 10 * max_val
        bar = ""
        for v in values:
            if v >= threshold:
                bar += " ██  "
            else:
                bar += " ..  "
        lines.append(f"{row*10:3d} {bar}")
    lines.append("    " + "  ".join(f"{v:4.1f}" for v in values))
    return "\n".join(lines)

# ──────────────────────────────────────────────
# 开场动画
# ──────────────────────────────────────────────
def intro():
    console.clear()
    banner = Text("""
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║                                                                       ║
    ║     🔍 魅 影 学 术 侦 探    ·    调 查 流 程 演 示                     ║
    ║                                                                       ║
    ║     目标锁定: 某院士院士 (某某) · 目标院校 · 目标学科           ║
    ║                                                                       ║
    ╚═══════════════════════════════════════════════════════════════════════╝
    """, style="bold bright_cyan")
    console.print(banner)
    time.sleep(0.8)
    
    # 目标档案卡片
    card = Panel(
        f"[bold]姓名:[/bold] {SCHOLAR['name']} ({SCHOLAR['name_en']})\n"
        f"[bold]机构:[/bold] {SCHOLAR['institution']} ({SCHOLAR['institution_en']})\n"
        f"[bold]头衔:[/bold] {SCHOLAR['title']}\n"
        f"[bold]性别/出生:[/bold] {SCHOLAR['gender']} / {SCHOLAR['birth']}\n"
        f"[bold]籍贯:[/bold] {SCHOLAR['hometown']}\n"
        f"[bold]学科:[/bold] 目标学科 / 纳米材料 / 能源材料\n"
        f"[bold]预计调查深度:[/bold] 三阶段 · 七方向 · 多源交叉验证",
        title="[bold bright_yellow]📋 调查目标档案[/bold bright_yellow]",
        border_style="bright_yellow",
        padding=(1, 2),
    )
    console.print(card)
    console.print()
    time.sleep(1.0)

# ──────────────────────────────────────────────
# 步骤 1：开始初步调查（身份基线核实）
# ──────────────────────────────────────────────
def step1_identity_baseline():
    console.rule("[bold bright_cyan]步骤 1 / 3  ·  开始初步调查（身份基线核实）", align="left")
    console.print("[dim cyan]建立学者完整身份档案与时间轴。核实现任职称、教育经历、学位导师、海外访学、晋升轨迹。")
    console.print()
    
    # 子步骤 1.1：高校官网扫描
    console.print("[bold bright_cyan]▸ 子步骤 1.1  高校官网与机构数据库扫描[/bold bright_cyan]")
    fake_progress("检索中科大官网...", "bright_cyan", steps=3, delay=0.2)
    fake_progress("检索中科院院士名单...", "bright_cyan", steps=2, delay=0.15)
    fake_progress("检索中国化学会会士页面...", "bright_cyan", steps=2, delay=0.15)
    
    table1 = Table(box=box.SIMPLE, header_style="bold bright_cyan", show_header=True, padding=(0, 1))
    table1.add_column("核实项", width=20)
    table1.add_column("官方口径", width=28)
    table1.add_column("交叉来源", width=28)
    table1.add_column("状态", width=8)
    
    checks = [
        ("姓名/性别/出生", "某院士，女，1967年生", "百度百科/院士名单", "[green]✓一致[/green]"),
        ("学士学位", "1988年厦门大学化学系", "中国化学会会士页", "[green]✓一致[/green]"),
        ("博士学位", "1996年中科大博士", "多源一致", "[green]✓一致[/green]"),
        ("博士专业", "应用化学系", "化学会:凝聚态物理", "[yellow]⚠差异[/yellow]"),
        ("海外经历1", "石溪分校博士后", "厦门协同创新中心CV", "[green]✓一致[/green]"),
        ("海外经历2", "宾州州立大学", "英文CV:仅2个月访问", "[yellow]⚠表述泛化[/yellow]"),
        ("职称晋升", "1998年起教授", "中科大官网", "[green]✓一致[/green]"),
        ("博导资格", "1999年4月起", "360百科", "[green]✓一致[/green]"),
    ]
    for item, official, cross, status in checks:
        table1.add_row(item, official, cross, status)
    console.print(table1)
    console.print()
    time.sleep(0.5)
    
    # 子步骤 1.2：学位论文核实
    console.print("[bold bright_cyan]▸ 子步骤 1.2  学位论文与导师网络核实[/bold bright_cyan]")
    fake_progress("检索中科大学位论文库...", "bright_cyan", steps=2, delay=0.2)
    fake_progress("检索导师钱逸泰院士档案...", "bright_cyan", steps=2, delay=0.15)
    
    # 导师网络树
    tree = Tree("[bold bright_cyan]📁 学术谱系[/bold bright_cyan]")
    advisor = tree.add(f"[bold]导师[/bold]: 钱逸泰院士 (中科大，目标学科)")
    advisor.add("[dim]· 院士(1997)、第三世界科学院院士[/dim]")
    advisor.add("[dim]· 固体化学与纳米材料领域奠基人之一[/dim]")
    xie = tree.add(f"[bold]本人[/bold]: 某院士 (1967- )")
    xie.add("[green]✓[/green] 1996年博士毕业，留校任教")
    xie.add("[green]✓[/green] 1998年破格晋升教授")
    xie.add("[green]✓[/green] 2013年当选中国科学院院士")
    students = xie.add("[bold]学生培养[/bold]")
    students.add("[dim]· 多名博士成长为独立PI并获国家杰青[/dim]")
    students.add("[dim]· 学生成果持续发表于JACS/Angew/AM等顶刊[/dim]")
    console.print(tree)
    console.print()
    time.sleep(0.5)
    
    # 子步骤 1.3：异常标记
    console.print("[bold bright_cyan]▸ 子步骤 1.3  异常标记与初步判定[/bold bright_cyan]")
    
    anomalies = Panel(
        "[yellow]⚠ 发现1[/yellow]: 博士专业表述差异\n"
        "  官方口径'应用化学系' vs 化学会页面'凝聚态物理'\n"
        "  [dim]→ 实为导师跨专业招生，交叉领域正常现象，不构成造假[/dim]\n\n"
        "[yellow]⚠ 发现2[/yellow]: 宾州州立大学经历表述泛化\n"
        "  官网写'从事博士后研究及访问'，实为2个月短期访问学者\n"
        "  [dim]→ 原文含'访问'二字，属宣传口径泛化，不构成升级造假[/dim]\n\n"
        "[green]✓ 其余项: 多源一致，无异常[/green]",
        title="[bold yellow]初步调查异常摘要[/bold yellow]",
        border_style="yellow",
        padding=(1, 2),
    )
    console.print(anomalies)
    console.print()

# ──────────────────────────────────────────────
# 步骤 2：审查论文质量（产出核实 + 六维评估）
# ──────────────────────────────────────────────
def step2_paper_quality():
    console.rule("[bold bright_yellow]步骤 2 / 3  ·  审查论文质量（产出核实 + 六维评估）", align="left")
    console.print("[dim yellow]对比声称与数据库实际记录。建立对照表，标记夸大与注水。对核心论文进行六维质量评估。")
    console.print()
    
    # 子步骤 2.1：数据库检索
    console.print("[bold bright_yellow]▸ 子步骤 2.1  多数据库检索与声称核实[/bold bright_yellow]")
    databases = ["中国知网(CNKI)", "万方数据", "Web of Science", "Scopus", "Google Scholar"]
    for db in databases:
        fake_progress(f"检索 {db}...", "bright_yellow", steps=2, delay=0.15)
    
    # 声称 vs 核实 对照表
    table2 = Table(
        title="[bold bright_yellow]📊 学术产出声称 vs 核实对照表[/bold bright_yellow]",
        box=box.ROUNDED,
        header_style="bold bright_yellow",
        row_styles=["", "dim"],
    )
    table2.add_column("指标", width=22)
    table2.add_column("声称数据", width=16, justify="right")
    table2.add_column("核实数据", width=16, justify="right")
    table2.add_column("差异", width=10, justify="right")
    table2.add_column("可信度", width=10)
    
    data_rows = [
        ("SCI论文总数", "330+", "~300", "-30", "[green]基本可信[/green]"),
        ("Nature及子刊", "10+", "Nature 1 + NC 8", "+?", "[yellow]部分可核[/yellow]"),
        ("JACS", "—", "32篇(通讯)", "—", "[green]有来源[/green]"),
        ("Angewandte", "—", "25篇(通讯)", "—", "[green]有来源[/green]"),
        ("Adv. Mater.", "—", "11篇(通讯)", "—", "[green]有来源[/green]"),
        ("总被引次数", ">35,000", ">30,000", "-5k", "[green]有支撑[/green]"),
        ("h-index", "—", "~80", "—", "[green]估计合理[/green]"),
    ]
    for row in data_rows:
        table2.add_row(*row)
    console.print(table2)
    console.print()
    time.sleep(0.5)
    
    # 子步骤 2.2：六维质量评估
    console.print("[bold bright_yellow]▸ 子步骤 2.2  核心论文六维质量评估[/bold bright_yellow]")
    fake_progress("抽取近5年高被引论文...", "bright_yellow", steps=3, delay=0.2)
    fake_progress("执行六维评分...", "bright_yellow", steps=2, delay=0.15)
    
    # 雷达图（字符画）
    dimensions = ["原创性", "严谨性", "证据质量", "逻辑结构", "文献规范", "表达清晰"]
    scores = [9.2, 9.0, 8.8, 9.1, 8.5, 8.7]  # 某院士的实际水平
    radar = ascii_radar(dimensions, scores)
    
    radar_panel = Panel(
        f"[bold]评估对象:[/bold] 某院士团队近5年代表性论文 (JACS/Angew/AM/PNAS)\n"
        f"[bold]样本量:[/bold] 20篇通讯作者论文\n\n"
        f"[bold bright_yellow]六维质量雷达图 (满分10)[/bold bright_yellow]\n"
        f"{radar}\n\n"
        f"[green]✓ 原创性突出: 纳米材料合成方法创新[/green]\n"
        f"[green]✓ 技术严谨: 表征手段完备，数据可复现[/green]\n"
        f"[green]✓ 顶刊连续性: 2022-2025年持续发表于JACS/Angew/AM/PNAS[/green]\n"
        f"[dim]· 文献规范略弱: 部分早期论文引用格式不统一[/dim]",
        title="[bold bright_yellow]📐 六维质量评估报告[/bold bright_yellow]",
        border_style="bright_yellow",
        padding=(1, 2),
    )
    console.print(radar_panel)
    console.print()
    time.sleep(0.5)
    
    # 子步骤 2.3：趋势分析
    console.print("[bold bright_yellow]▸ 子步骤 2.3  产出趋势与质量悬崖检测[/bold bright_yellow]")
    
    trend = Panel(
        "[bold]近5年产出轨迹[/bold]\n"
        "  2021: ████████████████████  ~15篇(通讯)  JACS×3 Angew×2 AM×2\n"
        "  2022: ██████████████████████  ~18篇(通讯)  JACS×4 Angew×3 PNAS×1\n"
        "  2023: ████████████████████  ~16篇(通讯)  JACS×3 Angew×2 NC×2\n"
        "  2024: ██████████████████  ~14篇(通讯)  JACS×2 Angew×3 AM×1\n"
        "  2025: ████████████████  ~12篇(通讯)  JACS×2 Angew×2\n\n"
        "[green]✓ 结论: 未出现质量悬崖或向低水平期刊转移的趋势[/green]\n"
        "[green]✓ 顶刊占比稳定，年均通讯作者论文 12-18 篇[/green]",
        title="[bold bright_yellow]📈 产出趋势分析[/bold bright_yellow]",
        border_style="bright_yellow",
        padding=(1, 2),
    )
    console.print(trend)
    console.print()

# ──────────────────────────────────────────────
# 步骤 3：多agent深度挖掘
# ──────────────────────────────────────────────
def step3_multi_agent():
    console.rule("[bold bright_magenta]步骤 3 / 3  ·  多agent深度挖掘（全网并发扫描）", align="left")
    console.print("[dim magenta]部署多个独立agent，并发搜索PubPeer、Retraction Watch、知乎、导师评价网、商业数据库等。")
    console.print()
    
    # 并发agent启动动画
    console.print("[bold bright_magenta]▸ 启动 7 个独立调查 agent，并发执行[/bold bright_magenta]")
    
    agents = [
        ("🕵️ Agent-A", "PubPeer 评论扫描", "bright_magenta"),
        ("🕵️ Agent-B", "Retraction Watch 撤稿追踪", "bright_magenta"),
        ("🕵️ Agent-C", "知乎/微信公众号舆情", "bright_magenta"),
        ("🕵️ Agent-D", "导师评价网口碑", "bright_magenta"),
        ("🕵️ Agent-E", "图片/数据重复检测", "bright_magenta"),
        ("🕵️ Agent-F", "学生培养成果核实", "bright_magenta"),
        ("🕵️ Agent-G", "基金项目与经费审计", "bright_magenta"),
    ]
    
    with Progress(
        SpinnerColumn("dots", style="bright_magenta"),
        TextColumn("[bold bright_magenta]{task.description}"),
        BarColumn(bar_width=20, complete_style="bright_magenta"),
        console=console,
        transient=True,
    ) as progress:
        agent_tasks = []
        for name, desc, color in agents:
            t = progress.add_task(f"{name}  {desc}", total=100)
            agent_tasks.append(t)
        
        # 模拟并发执行
        for step in range(0, 101, 10):
            for t in agent_tasks:
                progress.update(t, advance=random.randint(5, 15))
                time.sleep(0.03)
    
    console.print("  [green]✓[/green] 7 个 agent 全部完成，数据汇聚中...")
    console.print()
    time.sleep(0.5)
    
    # 各agent结果
    console.print("[bold bright_magenta]▸ Agent 调查结果汇总[/bold bright_magenta]")
    
    results_table = Table(box=box.SIMPLE, header_style="bold bright_magenta", show_header=True, padding=(0, 1))
    results_table.add_column("Agent", width=14)
    results_table.add_column("调查方向", width=26)
    results_table.add_column("发现", width=30)
    results_table.add_column("风险信号", width=12)
    
    agent_results = [
        ("Agent-A", "PubPeer 评论", "无公开质疑，无图片/数据异常举报", "[green]🟢 阴性[/green]"),
        ("Agent-B", "Retraction Watch", "无撤稿记录，无表达关切", "[green]🟢 阴性[/green]"),
        ("Agent-C", "知乎/微信舆情", "无针对本人的负面评价或学术争议", "[green]🟢 阴性[/green]"),
        ("Agent-D", "导师评价网", "学生评价整体正面，无pua/压榨举报", "[green]🟢 阴性[/green]"),
        ("Agent-E", "图片重复检测", "核心论文未发现图片重复使用", "[green]🟢 阴性[/green]"),
        ("Agent-F", "学生培养核实", "多名博士获国家杰青，独立成组", "[green]🟢 强正向[/green]"),
        ("Agent-G", "基金项目审计", "主持基金委创新群体基金，经费使用无异常", "[green]🟢 阴性[/green]"),
    ]
    for row in agent_results:
        results_table.add_row(*row)
    console.print(results_table)
    console.print()
    time.sleep(0.5)
    
    # 证据链
    console.print("[bold bright_magenta]▸ 证据链构建[/bold bright_magenta]")
    
    evidence_tree = Tree("[bold bright_magenta]🔗 某院士院士 · 完整证据链[/bold bright_magenta]")
    
    id_branch = evidence_tree.add("[bold]身份基线[/bold]")
    id_branch.add("[green]✓[/green] 学历: 厦大本科(1988) → 中科大博士(1996)，多源一致")
    id_branch.add("[green]✓[/green] 职称: 教授(1998) → 院士(2013)，晋升轨迹清晰")
    id_branch.add("[yellow]△[/yellow] 海外经历: 石溪分校博士后(1年) + 宾州州立短期访问(2个月)，表述略有泛化")
    
    output_branch = evidence_tree.add("[bold]学术产出[/bold]")
    output_branch.add("[green]✓[/green] 数量: 声称330篇 vs 核实~300篇，差异在合理范围")
    output_branch.add("[green]✓[/green] 质量: 六维评估均分 8.9/10，顶刊连续性良好")
    output_branch.add("[green]✓[/green] 趋势: 近5年无质量悬崖，持续高水准")
    
    rep_branch = evidence_tree.add("[bold]声誉与网络[/bold]")
    rep_branch.add("[green]✓[/green] PubPeer / Retraction Watch: 全部阴性")
    rep_branch.add("[green]✓[/green] 社交媒体: 无负面舆情")
    rep_branch.add("[green]✓[/green] 学生培养: 强正向，多名杰青")
    rep_branch.add("[green]✓[/green] 国际声誉: 世界杰出女科学家奖(2015)")
    
    console.print(evidence_tree)
    console.print()

# ──────────────────────────────────────────────
# 最终判定
# ──────────────────────────────────────────────
def final_verdict():
    console.rule("[bold bright_green]调查完成 · 最终判定", align="center")
    console.print()
    
    verdict = Panel(
        f"[bold]调查对象:[/bold] 某院士 (某某) · 目标院校\n"
        f"[bold]调查深度:[/bold] 三阶段 / 七方向 / 多源交叉验证\n"
        f"[bold]agent数量:[/bold] 7个独立并发agent\n"
        f"[bold]数据来源:[/bold] 高校官网、学位论文库、CNKI、WoS、PubPeer、Retraction Watch、知乎、导师评价网等\n\n"
        f"[bold bright_green]总体风险评级: 低风险 (🟢)[/bold bright_green]\n\n"
        f"[green]✓[/green] 学术履历、学位背景、海外经历均有多源证据支撑\n"
        f"[green]✓[/green] 学术产出曲线长期高水准，近5年持续顶刊\n"
        f"[green]✓[/green] PubPeer与Retraction Watch检索全部阴性\n"
        f"[green]✓[/green] 社交媒体无负面评价，学生培养成果突出\n"
        f"[yellow]△[/yellow] 宾州州立大学经历表述略有泛化（2个月访问 vs '博士后研究及访问'），但不构成造假\n\n"
        f"[dim]调查结论：未发现学术不端、学历造假或 credential fraud 的证据。[/dim]",
        title="[bold bright_green]📋 魅影学术侦探 · 调查报告[/bold bright_green]",
        border_style="bright_green",
        padding=(1, 2),
    )
    console.print(verdict)
    console.print()
    
    # 调查统计
    stats = Panel(
        "[bold]调查统计[/bold]\n"
        "  核实项目: 14 项\n"
        "  数据库检索: 5 个\n"
        "  Agent并发调查: 7 个\n"
        "  异常发现: 2 处（均为表述差异，不构成不端）\n"
        "  总耗时: ~3 分钟（模拟）",
        title="[bold]⏱️ 效率指标[/bold]",
        border_style="dim",
        padding=(1, 2),
    )
    console.print(Align.center(stats))
    console.print()

# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────
def main():
    intro()
    step1_identity_baseline()
    step2_paper_quality()
    step3_multi_agent()
    final_verdict()

if __name__ == "__main__":
    main()
