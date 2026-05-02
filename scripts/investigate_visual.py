#!/usr/bin/env python3
"""
investigate_visual.py — 魅影学术侦探 · Rich 可视化包装层

对 investigate.py 的核心流程进行 Rich 终端可视化包装：
  - 每个阶段有彩色开场面板、进度条、实时输出捕获
  - 人工干预点用 Rich Prompt 替代 raw input
  - 案件状态用树状图 + 表格呈现
  - 子脚本输出实时渲染到 Rich Live 面板

用法（与 investigate.py 一致）：
    python3 scripts/investigate_visual.py init --case-dir ./cases/xxx --name 谢毅
    python3 scripts/investigate_visual.py step --case-dir ./cases/xxx
    python3 scripts/investigate_visual.py advance --case-dir ./cases/xxx
    python3 scripts/investigate_visual.py status --case-dir ./cases/xxx
    python3 scripts/investigate_visual.py collect --case-dir ./cases/xxx
    python3 scripts/investigate_visual.py validate --case-dir ./cases/xxx
    python3 scripts/investigate_visual.py generate --case-dir ./cases/xxx
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# 把 scripts/ 加入路径，以便导入 investigate.py 中的模块
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import (
    BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn,
)
from rich.table import Table
from rich.tree import Tree
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.live import Live
from rich.align import Align
from rich import box

# 导入 investigate.py 的底层模块（复用业务逻辑）
from core.case_manager import CaseStateMachine, CaseManager
from core.db import InvestigationDB
from core.recommendation_engine import RuleEngine
from core.router import detect_investigation_type, InvestigationType, get_step_definitions
from core.utils import get_logger, ensure_dirs, load_config

console = Console()

# ──────────────────────────────────────────────
# 主题与颜色映射
# ──────────────────────────────────────────────
PHASE_COLORS = {
    "initialized": "bright_cyan",
    "collected": "bright_yellow",
    "validated": "bright_green",
    "analyzed": "bright_blue",
    "deep_evidence": "bright_magenta",
    "aggregated": "bright_cyan",
    "reported": "bright_yellow",
    "reviewed": "bright_green",
    "generated": "bright_red",
    "archived": "dim",
}

PHASE_ICONS = {
    "initialized": "🚀",
    "collected": "📥",
    "validated": "✅",
    "analyzed": "🔬",
    "deep_evidence": "🔍",
    "aggregated": "📊",
    "reported": "📝",
    "reviewed": "👁️",
    "generated": "📄",
    "archived": "📦",
}

STEP_COLORS = ["bright_cyan", "bright_yellow", "bright_green", "bright_blue",
               "bright_magenta", "bright_red", "bright_cyan", "bright_yellow"]

# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────
def get_case_dir(args) -> Path:
    return Path(args.case_dir) if getattr(args, "case_dir", None) else Path.cwd()


def get_state_path(args) -> Path:
    return get_case_dir(args) / ".state.json"


def load_state(state_path: Path) -> dict:
    if state_path.exists():
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"current_step": "init", "history": [], "config_path": None}


def save_state(state: dict, state_path: Path):
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _find_template() -> Optional[Path]:
    """Locate config.template.yaml."""
    candidates = [
        SCRIPT_DIR / "config.template.yaml",
        SCRIPT_DIR / ".." / "config.template.yaml",
        Path("scripts/config.template.yaml"),
    ]
    for c in candidates:
        if c.exists():
            return c.resolve()
    return None


def _get_script_env() -> dict:
    env = os.environ.copy()
    env["PYTHONIOENCING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def run_subprocess_live(
    cmd: list[str],
    title: str = "运行中",
    color: str = "bright_white",
    max_display_lines: int = 30,
) -> tuple[int, list[str]]:
    """运行子进程，实时捕获输出，返回 (returncode, lines)。"""
    all_lines: list[str] = []
    
    # 启动子进程
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=_get_script_env(),
        cwd=str(SCRIPT_DIR),
    )
    
    # 使用 Rich Live 显示实时输出
    output_text = Text(f"[等待输出...]\n", style="dim")
    
    with Live(output_text, console=console, refresh_per_second=10, transient=True) as live:
        for line in process.stdout:
            line_stripped = line.rstrip()
            if line_stripped:
                all_lines.append(line_stripped)
                # 只保留最近 max_display_lines 行
                display_lines = all_lines[-max_display_lines:]
                text = Text()
                text.append(f"[{title}]\n", style=f"bold {color}")
                for dl in display_lines:
                    text.append(dl + "\n", style="white")
                live.update(text)
    
    process.wait()
    return process.returncode, all_lines


def run_subprocess_with_spinner(
    cmd: list[str],
    desc: str,
    color: str = "bright_white",
) -> tuple[int, list[str]]:
    """轻量版：用进度条包裹子进程，完成后显示关键输出。"""
    all_lines: list[str] = []
    
    with Progress(
        SpinnerColumn("dots", style=color),
        TextColumn(f"[bold {color}]{{task.description}}"),
        BarColumn(bar_width=20, complete_style=color),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(desc, total=None)
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=_get_script_env(),
            cwd=str(SCRIPT_DIR),
        )
        for line in process.stdout:
            line_stripped = line.rstrip()
            if line_stripped:
                all_lines.append(line_stripped)
                progress.update(task, description=f"{desc} ({len(all_lines)} lines)")
        process.wait()
    
    return process.returncode, all_lines


def show_phase_banner(phase: str, case_name: str):
    """显示阶段开场面板。"""
    color = PHASE_COLORS.get(phase, "white")
    icon = PHASE_ICONS.get(phase, "📋")
    
    phase_titles = {
        "initialized": "初始化案件目录与配置",
        "collected": "人工数据采集",
        "validated": "数据验证",
        "analyzed": "运行脚本分析",
        "deep_evidence": "深度证据挖掘",
        "aggregated": "信号聚合",
        "reported": "报告生成",
        "reviewed": "人工审阅",
        "generated": "最终报告交付",
        "archived": "案件归档",
    }
    
    title = phase_titles.get(phase, phase)
    banner = Panel(
        f"[bold {color}]{icon} 当前阶段: {title}[/bold {color}]\n"
        f"[dim]案件: {case_name}[/dim]",
        border_style=color,
        padding=(1, 2),
    )
    console.print(banner)


def show_phase_progress(current_phase: str):
    """显示所有阶段的进度条。"""
    phases = CaseStateMachine.PHASES
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("阶段", width=18)
    table.add_column("状态", width=6)
    
    current_idx = phases.index(current_phase) if current_phase in phases else -1
    for i, p in enumerate(phases):
        color = PHASE_COLORS.get(p, "white")
        icon = PHASE_ICONS.get(p, "")
        if i < current_idx:
            status = f"[green]✓[/green]"
            style = "dim"
        elif i == current_idx:
            status = f"[{color}]🔄[/{color}]"
            style = f"bold {color}"
        else:
            status = "⏳"
            style = "dim"
        table.add_row(f"[{style}]{icon} {p}[/{style}]", status)
    
    console.print(table)
    console.print()


def show_recommendation_table(recs: list, color: str = "bright_magenta"):
    """显示动态推荐工具表格。"""
    if not recs:
        console.print("[dim]暂无动态推荐。[/dim]")
        return None
    
    table = Table(
        title=f"[bold {color}]🔧 动态推荐工具 (Top {min(5, len(recs))})[/bold {color}]",
        box=box.ROUNDED,
        header_style=f"bold {color}",
        row_styles=["", "dim"],
    )
    table.add_column("序号", justify="center", width=4)
    table.add_column("优先级", justify="center", width=6)
    table.add_column("工具", width=30)
    table.add_column("原因", width=36)
    
    for i, r in enumerate(recs[:5], 1):
        prio = f"P{r.priority}"
        tools = ", ".join(r.tools)
        table.add_row(str(i), prio, tools, r.reason)
    
    console.print(table)
    console.print()
    
    # 交互式选择
    choices = [str(i) for i in range(1, min(6, len(recs) + 1))] + ["0", "skip"]
    choice = Prompt.ask(
        f"[bold {color}]输入编号运行对应工具[/bold {color}]",
        choices=choices,
        default="0",
        show_choices=True,
    )
    if choice in ("0", "skip"):
        return None
    return recs[int(choice) - 1]


# ──────────────────────────────────────────────
# 核心命令（Rich 包装版）
# ──────────────────────────────────────────────
def visual_init(args):
    """初始化案件 — 青色主题。"""
    console.rule("[bold bright_cyan]🚀 初始化案件", align="left")
    
    case_dir = get_case_dir(args)
    case_dir.mkdir(parents=True, exist_ok=True)
    
    # 配置模板
    config_path = case_dir / (getattr(args, "config", None) or "config.yaml")
    if not config_path.exists():
        template = _find_template()
        if template:
            shutil.copy(template, config_path)
            console.print(f"  [green]✓[/green] 已复制配置模板: {config_path}")
        else:
            console.print("[red]✗ 未找到 config.template.yaml[/red]")
            sys.exit(1)
    else:
        console.print(f"  [yellow]△[/yellow] 配置文件已存在: {config_path}")
    
    # 创建标准目录
    ensure_dirs(case_dir, extra=["guides"])
    for sub in ["data", "pdfs", "reports", "screenshots", "delivery"]:
        (case_dir / sub).mkdir(exist_ok=True)
    console.print(f"  [green]✓[/green] 标准目录结构已创建")
    
    # 检查清单
    checklist_template = SCRIPT_DIR / "templates" / "CHECKLIST.md"
    checklist_dest = case_dir / "CHECKLIST.md"
    if checklist_template.exists() and not checklist_dest.exists():
        shutil.copy(checklist_template, checklist_dest)
        console.print(f"  [green]✓[/green] 已复制检查清单")
    
    # 数据库初始化
    db = InvestigationDB(case_dir)
    db.init_schema()
    console.print(f"  [green]✓[/green] SQLite 数据库已初始化")
    
    # 调查类型检测
    case_name = getattr(args, "name", None) or f"case_{datetime.now().strftime('%Y%m%d')}"
    config_data = load_config(case_dir, getattr(args, "config", None) or "config.yaml")
    inv_type = detect_investigation_type(config_data)
    if getattr(args, "type", None):
        inv_type = InvestigationType(args.type)
    
    db.upsert_investigation({
        "case_name": case_name,
        "investigation_type": inv_type.value,
        "status": "init",
        "current_step": "collect" if inv_type == InvestigationType.DOMESTIC else "auto_fetch",
        "started_at": datetime.now().isoformat(),
    })
    
    # 状态机
    csm = CaseStateMachine(case_dir)
    csm.write_state_md(phase="initialized")
    
    # 保存状态
    state = {
        "current_step": "collect" if inv_type == InvestigationType.DOMESTIC else "auto_fetch",
        "history": [{"step": "init", "timestamp": datetime.now().isoformat()}],
        "config_path": str(config_path),
        "case_name": case_name,
        "case_dir": str(case_dir),
        "investigation_type": inv_type.value,
    }
    save_state(state, get_state_path(args))
    
    # 完成面板
    console.print()
    panel = Panel(
        f"[bold green]✓ 案件初始化完成[/bold green]\n\n"
        f"[bold]案件目录:[/bold] {case_dir}\n"
        f"[bold]案件名称:[/bold] {case_name}\n"
        f"[bold]调查类型:[/bold] {inv_type.value}\n\n"
        f"[bold bright_yellow]下一步操作:[/bold bright_yellow]\n"
        f"  1. 编辑 [cyan]{config_path}[/cyan]，填写学者基本信息\n"
        f"  2. 运行: [cyan]python investigate_visual.py step --case-dir '{case_dir}'[/cyan]",
        border_style="bright_green",
        padding=(1, 2),
    )
    console.print(panel)


def visual_step(args):
    """查看当前阶段 — 黄色主题。"""
    case_dir = get_case_dir(args)
    csm = CaseStateMachine(case_dir)
    phase = csm.get_current_phase()
    case_name = case_dir.resolve().name
    
    if phase == "archived":
        console.print("[dim]📦 调查已完成。所有步骤已归档。[/dim]")
        return
    
    console.rule(f"[bold bright_yellow]步骤查看 · {case_name}", align="left")
    show_phase_banner(phase, case_name)
    show_phase_progress(phase)
    
    if phase == "deep_evidence":
        recs = RuleEngine().evaluate(case_dir)
        selected = show_recommendation_table(recs, color="bright_magenta")
        if selected:
            tool = selected.tools[0]
            console.print(f"\n[bold bright_magenta]▸ 运行工具: {tool}[/bold bright_magenta]")
            _run_tool_visual(case_dir, tool)
    else:
        guidance = {
            "initialized": {"title": "初始化", "desc": "配置案件目录和 config.yaml。", "action": "编辑 config.yaml 后运行 advance"},
            "collected": {"title": "数据采集", "desc": "导入论文、机构快照、PDF。", "action": "运行 collect 或 advance"},
            "validated": {"title": "数据验证", "desc": "运行验证器检查 scholar_data.json。", "action": "运行 validate 或 advance"},
            "analyzed": {"title": "分析完成", "desc": "运行评分、画像、匹配脚本。", "action": "运行 advance"},
            "aggregated": {"title": "聚合", "desc": "运行信号聚合器。", "action": "运行 advance"},
            "reported": {"title": "报告生成", "desc": "生成最终 Markdown 报告。", "action": "运行 generate 或 advance"},
            "reviewed": {"title": "审阅", "desc": "人工审阅报告质量。", "action": "确认后运行 advance"},
            "generated": {"title": "报告生成", "desc": "小金金生成报告并执行自检。", "action": "运行 advance 归档"},
        }
        g = guidance.get(phase, {})
        if g:
            panel = Panel(
                f"[bold]{g.get('title', phase)}[/bold]\n"
                f"{g.get('desc', '')}\n\n"
                f"[bold bright_yellow]建议操作:[/bold bright_yellow] {g.get('action', '运行 advance')}",
                border_style="bright_yellow",
                padding=(1, 2),
            )
            console.print(panel)


def _run_tool_visual(case_dir: Path, tool_path: str):
    """可视化运行单个深度取证工具。"""
    script = SCRIPT_DIR / "deep_evidence" / f"{tool_path}.py"
    if not script.exists():
        script = Path("scripts/deep_evidence") / f"{tool_path}.py"
    if not script.exists():
        console.print(f"[red]✗ 工具脚本未找到: {tool_path}[/red]")
        return
    
    cmd = [sys.executable, str(script), "--output", str(case_dir / "data" / f"{tool_path.replace('/', '_')}.json")]
    if "preprint_monitor" in tool_path:
        try:
            name = load_config(case_dir, "config.yaml").get("scholar", {}).get("name", "")
            if name:
                cmd.extend(["--name", name])
        except Exception:
            pass
    
    returncode, lines = run_subprocess_live(cmd, title=f"🔧 {tool_path}", color="bright_magenta")
    
    if returncode == 0:
        console.print(f"  [green]✓[/green] 工具执行成功: {tool_path}")
    else:
        console.print(f"  [red]✗[/red] 工具执行失败 (exit={returncode}): {tool_path}")
        if lines:
            console.print(Panel("\n".join(lines[-10:]), title="错误输出", border_style="red"))


def visual_advance(args):
    """推进阶段 — 绿色主题。"""
    case_dir = get_case_dir(args)
    csm = CaseStateMachine(case_dir)
    phase = csm.get_current_phase()
    case_name = case_dir.resolve().name
    
    console.rule(f"[bold bright_green]阶段推进 · {case_name}", align="left")
    show_phase_banner(phase, case_name)
    
    target = getattr(args, "to", None)
    if target:
        if target not in csm.PHASES:
            console.print(f"[red]✗ 未知阶段: {target}[/red]")
            sys.exit(1)
        csm.write_state_md(phase=target)
        csm._record_transition(phase, target, override=True)
        console.print(f"[green]✓[/green] 已跳转到阶段: {target}")
        visual_step(args)
        return
    
    can, reason = csm.can_advance()
    if not can:
        console.print(f"[yellow]⚠ 无法从 {phase} 推进: {reason}[/yellow]")
        return
    
    # deep_evidence 阶段的自动运行
    if phase == "deep_evidence" and getattr(args, "auto", False):
        skips = set(getattr(args, "skip", []) or [])
        recs = RuleEngine().evaluate(case_dir)
        for r in recs:
            for t in r.tools:
                if t in skips:
                    console.print(f"[dim]⏭ 跳过: {t}[/dim]")
                    continue
                _run_tool_visual(case_dir, t)
                csm.write_state_md()
                if csm.read_state_md().get("critical"):
                    console.print("[red bold]🚨 检测到关键信号，停止推进。[/red bold]")
                    return
        console.print("[green]✓[/green] 所有推荐工具已执行。")
    
    # 推进到下一阶段
    old_phase = phase
    new_phase = csm.advance()
    console.print(f"[green]✓[/green] 阶段推进: [dim]{old_phase}[/dim] → [bold green]{new_phase}[/bold green]")
    console.print()
    
    # 自动显示新阶段信息
    visual_step(args)


def visual_status(args):
    """案件状态 — 蓝色主题。"""
    case_dir = get_case_dir(args)
    csm = CaseStateMachine(case_dir)
    phase = csm.get_current_phase()
    case_name = case_dir.resolve().name
    history = csm.get_phase_history()
    
    console.rule(f"[bold bright_blue]📊 案件状态 · {case_name}", align="left")
    
    # 阶段历史
    if history:
        tree = Tree(f"[bold bright_blue]阶段流转历史[/bold bright_blue]")
        for h in history[-10:]:
            arrow = "→" if not h.get("override") else "↺(回退)"
            ts = h.get("timestamp", "")[:19]
            tree.add(f"[dim]{ts}[/dim] {arrow} {h.get('to', '?')}")
        console.print(tree)
        console.print()
    
    # 当前阶段详情
    show_phase_banner(phase, case_name)
    show_phase_progress(phase)
    
    # 文件检查
    files_to_check = [
        ("config.yaml", case_dir / "config.yaml"),
        ("scholar_data.json", case_dir / "scholar_data.json"),
        ("STATE.md", case_dir / ".case" / "STATE.md"),
    ]
    table = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
    table.add_column("文件", width=22)
    table.add_column("状态", width=10)
    table.add_column("路径", width=40)
    for name, path in files_to_check:
        status = "[green]✓ 存在[/green]" if path.exists() else "[red]✗ 缺失[/red]"
        table.add_row(name, status, str(path))
    console.print(table)


def visual_collect(args):
    """数据采集 — 紫色主题。"""
    case_dir = get_case_dir(args)
    case_name = case_dir.resolve().name
    
    console.rule(f"[bold bright_magenta]📥 数据采集 · {case_name}", align="left")
    console.print("[dim]此步骤需要人工操作：登录知网/万方/WoS，导出学者论文列表；保存机构官网快照；获取专著/学位论文PDF。[/dim]")
    console.print()
    
    # 检查清单
    checklist = [
        ("CNKI导出文件已放入 data/", case_dir / "data"),
        ("机构官网快照已保存", case_dir / "screenshots"),
        ("关键PDF已放入 pdfs/", case_dir / "pdfs"),
        ("config.yaml 已填写学者信息", case_dir / "config.yaml"),
    ]
    
    table = Table(box=box.ROUNDED, header_style="bold bright_magenta", show_header=False)
    table.add_column("检查项", width=40)
    table.add_column("状态", width=10)
    for item, path in checklist:
        exists = path.exists() and (path.is_dir() and any(path.iterdir()) or path.is_file())
        status = "[green]✓[/green]" if exists else "[red]✗[/red]"
        table.add_row(item, status)
    console.print(table)
    console.print()
    
    # 更新状态机
    if Confirm.ask("[bold bright_magenta]是否标记数据采集阶段为完成？[/bold bright_magenta]", default=False):
        csm = CaseStateMachine(case_dir)
        csm.write_state_md(phase="collected")
        csm._record_transition(csm.get_current_phase(), "collected")
        console.print("[green]✓[/green] 已标记为 collected，可运行 advance 推进。")
    else:
        console.print("[dim]数据采集未完成，请继续收集后重试。[/dim]")


def visual_validate(args):
    """数据验证 — 橙色主题。"""
    case_dir = get_case_dir(args)
    case_name = case_dir.resolve().name
    scholar_data = case_dir / (getattr(args, "input", None) or "scholar_data.json")
    
    console.rule(f"[bold bright_yellow]✅ 数据验证 · {case_name}", align="left")
    
    if not scholar_data.exists():
        console.print(f"[red]✗ 未找到 {scholar_data}[/red]")
        console.print("[dim]请先运行 scholar_data_builder.py 生成 scholar_data.json[/dim]")
        sys.exit(1)
    
    # 运行验证器
    state = load_state(get_state_path(args))
    inv_type = state.get("investigation_type", "domestic")
    
    # 动态导入验证器
    if inv_type == "international":
        validator_module = "international.data_validator"
    elif inv_type == "cross_border":
        validator_module = "cross_border.validator"
    else:
        validator_module = "domestic.data_validator"
    
    console.print(f"[dim]使用验证器: {validator_module}[/dim]")
    
    # 由于验证器通常是函数调用而非 CLI，这里显示指导信息
    panel = Panel(
        f"[bold]验证脚本[/bold]: {validator_module}\n"
        f"[bold]输入文件[/bold]: {scholar_data}\n\n"
        f"[yellow]请手动运行验证:[/yellow]\n"
        f"  python scripts/{validator_module.replace('.', '/')}.py validate --input {scholar_data}\n\n"
        f"[green]验证通过后，运行:[/green]\n"
        f"  python investigate_visual.py advance --case-dir '{case_dir}'",
        border_style="bright_yellow",
        padding=(1, 2),
    )
    console.print(panel)


def visual_generate(args):
    """报告生成 — 红色主题。"""
    case_dir = get_case_dir(args)
    case_name = case_dir.resolve().name
    
    console.rule(f"[bold bright_red]📄 报告生成 · {case_name}", align="left")
    
    checkpoint = case_dir / "delivery" / "collection_checkpoint.json"
    if not checkpoint.exists():
        console.print("[red]✗ 未找到素材包。请先运行 collect。[/red]")
        sys.exit(1)
    
    try:
        from delivery import Xiaojinjing
        agent = Xiaojinjing(case_dir)
        
        console.print("[bold bright_red]▸ 启动小金金报告生成...[/bold bright_red]")
        result = agent.run()
        
        sc = result.get("self_check", {})
        total_issues = (
            sc.get("ban_rules", {}).get("failed", 0) +
            sc.get("format_rules", {}).get("failed", 0) +
            sc.get("content_rules", {}).get("failed", 0)
        )
        
        console.print()
        if result.get("pass_status"):
            panel = Panel(
                f"[bold green]✅ 自检全部通过，报告可交付[/bold green]\n\n"
                f"[bold]Markdown:[/bold] {result['deliverables']['markdown_report']}\n"
                f"[bold]HTML网络图:[/bold] {result['deliverables']['network_html'] or 'N/A'}",
                border_style="bright_green",
                padding=(1, 2),
            )
            console.print(panel)
        else:
            panel = Panel(
                f"[bold yellow]⚠️ 自检发现 {total_issues} 个问题[/bold yellow]\n\n"
                f"[bold]Markdown:[/bold] {result['deliverables']['markdown_report']}\n"
                f"[dim]查看 reports/self_check_report.md 了解详情[/dim]\n\n"
                f"使用 --force 强制交付",
                border_style="bright_yellow",
                padding=(1, 2),
            )
            console.print(panel)
            if not getattr(args, "force", False):
                sys.exit(1)
        
        csm = CaseStateMachine(case_dir)
        csm.write_state_md(phase="generated")
        
        # 如果指定了 --pdf，生成 PDF 版
        if getattr(args, "pdf", False):
            console.print()
            console.print("[bold bright_red]▸ 正在生成 PDF 版报告...[/bold bright_red]")
            
            md_path = case_dir / "reports" / f"{case_name}_报告.md"
            if not md_path.exists():
                # 尝试查找 reports 目录下的第一个 .md 文件
                md_files = list((case_dir / "reports").glob("*.md"))
                if md_files:
                    md_path = md_files[0]
            
            if md_path.exists():
                pdf_path = md_path.with_suffix('.pdf')
                md_to_pdf_script = SCRIPT_DIR / "md_to_pdf.py"
                if md_to_pdf_script.exists():
                    cmd = [
                        sys.executable, str(md_to_pdf_script),
                        "--input", str(md_path),
                        "--output", str(pdf_path),
                        "--case-dir", str(case_dir),
                    ]
                    returncode, lines = run_subprocess_with_spinner(
                        cmd, desc="生成 PDF", color="bright_red"
                    )
                    if returncode == 0:
                        console.print(f"  [green]✓[/green] PDF 报告: {pdf_path}")
                    else:
                        console.print(f"  [red]✗[/red] PDF 生成失败")
                        if lines:
                            console.print(Panel("\n".join(lines[-5:]), title="错误", border_style="red"))
                else:
                    console.print(f"  [yellow]△[/yellow] 未找到 md_to_pdf.py，跳过 PDF 生成")
            else:
                console.print(f"  [yellow]△[/yellow] 未找到 Markdown 报告文件，跳过 PDF 生成")
        
    except Exception as e:
        console.print(f"[red]✗ 报告生成失败: {e}[/red]")
        sys.exit(1)


# ──────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────
def visual_smart_step(args):
    """智能辅助推进 — 检查条件后询问用户是否自动推进。"""
    case_dir = get_case_dir(args)
    csm = CaseStateMachine(case_dir)
    phase = csm.get_current_phase()
    case_name = case_dir.resolve().name
    
    console.rule(f"[bold bright_green]🤖 智能辅助推进 · {case_name}", align="left")
    
    # 步骤 1：显示当前阶段
    visual_step(args)
    console.print()
    
    if phase == "archived":
        console.print("[dim]📦 案件已归档，无需推进。[/dim]")
        return
    
    # 步骤 2：检查阶段完成条件
    console.print("[bold bright_green]▸ 检查阶段完成条件...[/bold bright_green]")
    
    checks = []
    can_advance, reason = csm.can_advance()
    
    # 基础条件
    checks.append(("状态机条件", can_advance, reason if not can_advance else "满足"))
    
    # 文件条件（按阶段定制）
    config_path = case_dir / "config.yaml"
    scholar_data = case_dir / "scholar_data.json"
    data_dir = case_dir / "data"
    pdfs_dir = case_dir / "pdfs"
    screenshots_dir = case_dir / "screenshots"
    reports_dir = case_dir / "reports"
    delivery_dir = case_dir / "delivery"
    
    if phase == "initialized":
        has_config = config_path.exists() and config_path.stat().st_size > 50
        checks.append(("config.yaml 存在", has_config, "请编辑 config.yaml" if not has_config else "OK"))
    
    elif phase == "collected":
        has_data = data_dir.exists() and any(data_dir.iterdir())
        has_pdfs = pdfs_dir.exists() and any(pdfs_dir.iterdir())
        has_screenshots = screenshots_dir.exists() and any(screenshots_dir.iterdir())
        checks.append(("data/ 有文件", has_data, "请放入数据库导出文件" if not has_data else "OK"))
        checks.append(("pdfs/ 有文件", has_pdfs, "请放入关键PDF" if not has_pdfs else "OK"))
        checks.append(("screenshots/ 有文件", has_screenshots, "请保存机构官网快照" if not has_screenshots else "OK"))
    
    elif phase == "validated":
        has_scholar_data = scholar_data.exists()
        checks.append(("scholar_data.json 存在", has_scholar_data, "请运行 scholar_data_builder.py" if not has_scholar_data else "OK"))
    
    elif phase == "analyzed":
        has_analysis = data_dir.exists() and any(data_dir.glob("*_profile.json"))
        checks.append(("分析输出存在", has_analysis, "请运行分析脚本" if not has_analysis else "OK"))
    
    elif phase == "deep_evidence":
        has_evidence = data_dir.exists() and any(data_dir.glob("*_evidence.json"))
        checks.append(("深度证据输出存在", has_evidence, "请运行推荐工具" if not has_evidence else "OK"))
    
    elif phase == "aggregated":
        has_agg = data_dir.exists() and any(data_dir.glob("*aggregated*"))
        checks.append(("聚合输出存在", has_agg, "请运行信号聚合器" if not has_agg else "OK"))
    
    elif phase == "reported":
        has_report = reports_dir.exists() and any(reports_dir.iterdir())
        checks.append(("报告文件存在", has_report, "请运行报告生成" if not has_report else "OK"))
    
    elif phase == "reviewed":
        checks.append(("人工审阅确认", False, "需要人工确认报告质量"))
    
    elif phase == "generated":
        has_delivery = delivery_dir.exists() and any(delivery_dir.iterdir())
        checks.append(("交付物存在", has_delivery, "请运行报告交付" if not has_delivery else "OK"))
    
    # 展示检查结果
    table = Table(box=box.ROUNDED, header_style="bold bright_green", show_header=True)
    table.add_column("检查项", width=28)
    table.add_column("状态", width=10)
    table.add_column("说明", width=36)
    
    all_pass = True
    for item, status, note in checks:
        icon = "[green]✓[/green]" if status else "[red]✗[/red]"
        all_pass = all_pass and status
        table.add_row(item, icon, note)
    
    console.print(table)
    console.print()
    
    # 步骤 3：决策
    if not all_pass:
        console.print(Panel(
            "[yellow]⚠ 阶段条件未全部满足，无法自动推进。[/yellow]\n"
            "[dim]请根据上表中的 ✗ 项完成相应操作后重试。[/dim]",
            title="[bold yellow]推进受阻[/bold yellow]",
            border_style="yellow",
            padding=(1, 2),
        ))
        return
    
    # 条件满足，询问用户
    next_phase = csm.PHASE_TRANSITIONS[phase]["next"] if phase in csm.PHASE_TRANSITIONS else "?"
    if Confirm.ask(
        f"[bold bright_green]条件已满足，是否推进到下一阶段 [{next_phase}]？[/bold bright_green]",
        default=True,
    ):
        console.print()
        visual_advance(args)
    else:
        console.print("[dim]已取消推进。可随时运行 smart-step 重试。[/dim]")


def main():
    parser = argparse.ArgumentParser(
        description="魅影学术侦探 · Rich 可视化调查流程",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python investigate_visual.py init --case-dir ./cases/xieyi --name 谢毅
  python investigate_visual.py step --case-dir ./cases/xieyi
  python investigate_visual.py advance --case-dir ./cases/xieyi
  python investigate_visual.py status --case-dir ./cases/xieyi
  python investigate_visual.py collect --case-dir ./cases/xieyi
  python investigate_visual.py validate --case-dir ./cases/xieyi
  python investigate_visual.py generate --case-dir ./cases/xieyi
        """,
    )
    parser.add_argument("--case-dir", "-d", default=".", help="案件目录路径")
    sub = parser.add_subparsers(dest="command", required=True)
    
    # init
    p_init = sub.add_parser("init", help="初始化案件目录")
    p_init.add_argument("--name", "-n", help="案件名称")
    p_init.add_argument("--config", "-c", default="config.yaml", help="配置文件名")
    p_init.add_argument("--type", choices=["domestic", "international", "cross_border"], help="调查类型")
    
    # step
    p_step = sub.add_parser("step", help="查看当前阶段")
    
    # advance
    p_advance = sub.add_parser("advance", help="推进到下一阶段")
    p_advance.add_argument("--to", help="跳转到指定阶段")
    p_advance.add_argument("--auto", action="store_true", help="自动运行 deep_evidence 推荐工具")
    p_advance.add_argument("--skip", nargs="+", help="跳过的工具列表")
    
    # status
    p_status = sub.add_parser("status", help="查看案件状态")
    
    # collect
    p_collect = sub.add_parser("collect", help="数据采集检查")
    
    # validate
    p_validate = sub.add_parser("validate", help="数据验证")
    p_validate.add_argument("--input", "-i", help="输入的 scholar_data.json 路径")
    
    # generate
    p_generate = sub.add_parser("generate", help="生成最终报告")
    p_generate.add_argument("--force", action="store_true", help="强制交付（忽略自检问题）")
    p_generate.add_argument("--pdf", action="store_true", help="同时生成 PDF 版报告（调用 md_to_pdf.py）")
    
    # smart-step
    p_smart = sub.add_parser("smart-step", help="智能辅助推进：检查条件后询问是否自动推进")
    
    args = parser.parse_args()
    
    # 路由到对应的视觉化函数
    cmd_map = {
        "init": visual_init,
        "step": visual_step,
        "advance": visual_advance,
        "status": visual_status,
        "collect": visual_collect,
        "validate": visual_validate,
        "generate": visual_generate,
        "smart-step": visual_smart_step,
    }
    
    func = cmd_map.get(args.command)
    if func:
        func(args)
    else:
        console.print(f"[red]未知命令: {args.command}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
