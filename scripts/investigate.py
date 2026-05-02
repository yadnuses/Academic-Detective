#!/usr/bin/env python3
"""
investigate.py

Lightweight CLI orchestrator for the academic investigation workflow.
Provides case directory initialization, step-by-step guidance, and pre-flight checks.

Usage:
    python investigate.py init --config ./config.yaml
    python investigate.py step
    python investigate.py validate
    python investigate.py prompt --llm claude
    python investigate.py status
"""

import json
import os
import sys
import shutil
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

from core.utils import get_logger, ensure_dirs, load_config
from core.db import InvestigationDB
from core.router import detect_investigation_type, get_track_scripts, get_step_definitions, InvestigationType
from core.case_manager import CaseStateMachine
from core.recommendation_engine import RuleEngine


STEPS = [
    {
        "id": "init",
        "title": "初始化案件目录",
        "description": "复制 config.template.yaml，填写学者信息，创建标准目录结构。",
        "checklist": ["config.yaml 已存在且已填写", "data/ 目录已创建"],
        "next": "collect"
    },
    {
        "id": "collect",
        "title": "人工数据采集",
        "description": "登录知网/万方/WoS，导出学者论文列表；保存机构官网快照；获取专著/学位论文PDF。",
        "checklist": ["CNKI导出文件已放入 data/", "机构官网快照已保存", "关键PDF已放入 pdfs/"],
        "next": "profile"
    },
    {
        "id": "profile",
        "title": "运行脚本分析",
        "description": "对采集的PDF和数据库输出运行分析脚本。",
        "commands": [
            "python scripts/text_profiler.py --input ./pdfs/xxx.pdf --output ./data/xxx_profile.json",
            "python scripts/citation_profiler.py --input ./data/citations.json --output ./data/citation_report.json",
            "python scripts/stylometry_profiler.py --manifest ./data/style_manifest.json --output ./data/style_report.json",
            "python scripts/review_matcher.py ..."
        ],
        "checklist": ["data/ 中存在 *_profile.json", "（如适用）citation_report.json 已生成"],
        "next": "build"
    },
    {
        "id": "hybrid_score",
        "title": "混合评分（脚本+LLM）",
        "description": "对论文文件夹批量运行脚本提取+LLM深度评分，输出结构化排名表。",
        "commands": [
            "python scripts/hybrid_scorer.py prepare -i ./pdfs -o ./data/hybrid_scores",
            "# 将 llm_review_request.md 提交给 LLM，获取 llm_observations_batch.json",
            "python scripts/hybrid_scorer.py apply -i ./pdfs -o ./data/hybrid_scores"
        ],
        "checklist": ["hybrid_scores/_final_ranked_report.json 已生成"],
        "next": "build"
    },
    {
        "id": "build",
        "title": "构建 scholar_data.json",
        "description": "使用 scholar_data_builder.py 聚合 config.yaml 和各脚本输出。若 relationship_network 非空，会自动生成交互式网络图谱。",
        "command": "python scripts/scholar_data_builder.py --config ./config.yaml --data-dir ./data --output ./scholar_data.json --fix",
        "checklist": ["scholar_data.json 已生成", "文件已通过 validation", "（如适用）reports/*_network.html 已生成"],
        "next": "validate"
    },
    {
        "id": "validate",
        "title": "数据验证",
        "description": "运行 data_validator.py 检查字段完整性和逻辑一致性。",
        "command": "python scripts/data_validator.py --input ./scholar_data.json",
        "checklist": ["0 errors", "所有 warning 已审查"],
        "next": "llm"
    },
    {
        "id": "llm",
        "title": "LLM 辅助填充与定性分析",
        "description": "将 scholar_data.json 和文本片段提供给 LLM，补充 [TO BE FILLED] 字段，进行质量评估和异常解释。",
        "checklist": ["basic_profile 已补全", "quality_assessment 已完成", "anomalies 已列出"],
        "next": "prompt"
    },
    {
        "id": "prompt",
        "title": "生成报告 Prompt",
        "description": "使用 report_prompt_optimizer.py 为指定 LLM 生成优化后的报告 prompt。",
        "command": "python scripts/report_prompt_optimizer.py --data ./scholar_data.json --template ./scripts/report_template.md --llm claude --output ./report_prompt.md",
        "checklist": ["report_prompt.md 已生成"],
        "next": "report"
    },
    {
        "id": "report",
        "title": "生成最终 Markdown 报告",
        "description": "将优化后的 prompt 提交给 LLM，获取 Markdown 深度报告。人工审阅后保存。",
        "checklist": ["报告已通过人工审阅", "两面性分析平衡", "证据链完整", "免责声明已包含"],
        "next": "done"
    },
    {
        "id": "done",
        "title": "调查完成",
        "description": "所有步骤已完成。建议将证据链和报告归档。",
        "checklist": [],
        "next": None
    }
]


def _get_script_env() -> dict:
    """Return environment dict with scripts dir in PYTHONPATH for subprocess calls."""
    env = os.environ.copy()
    scripts_dir = str(Path(__file__).parent)
    current = env.get("PYTHONPATH", "")
    if current:
        env["PYTHONPATH"] = f"{scripts_dir}:{current}"
    else:
        env["PYTHONPATH"] = scripts_dir
    return env


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


def _get_steps_for_state(state: dict) -> list:
    """Return the appropriate step list based on investigation type."""
    inv_type_str = state.get("investigation_type", "domestic")
    try:
        inv_type = InvestigationType(inv_type_str)
    except ValueError:
        return STEPS
    custom_steps = get_step_definitions(inv_type)
    return custom_steps if custom_steps else STEPS


PHASE_GUIDANCE = {
    "initialized": {"title": "初始化", "desc": "配置案件目录和 config.yaml。", "next": "collected"},
    "collected": {"title": "数据采集", "desc": "导入论文、机构快照、PDF。", "next": "validated"},
    "validated": {"title": "数据验证", "desc": "运行验证器检查 scholar_data.json。", "next": "analyzed"},
    "analyzed": {"title": "分析完成", "desc": "运行评分、画像、匹配脚本。", "next": "deep_evidence"},
    "deep_evidence": {"title": "深度证据", "desc": "运行动态推荐的深度取证工具。", "next": "aggregated"},
    "aggregated": {"title": "聚合", "desc": "运行信号聚合器。", "next": "reported"},
    "reported": {"title": "报告生成", "desc": "生成最终 Markdown 报告。", "next": "reviewed"},
    "reviewed": {"title": "审阅", "desc": "人工审阅报告质量。", "next": "collected"},
    "collected": {"title": "素材收集", "desc": "小糖豆收集并分类所有Agent产出。", "next": "generated"},
    "generated": {"title": "报告生成", "desc": "小金金生成报告并执行自检。", "next": "archived"},
    "archived": {"title": "归档", "desc": "案件已完成。", "next": None},
}


def _run_recommended_tool(case_dir: Path, tool_path: str, logger):
    script = Path(__file__).parent / "deep_evidence" / f"{tool_path}.py"
    if not script.exists():
        script = Path("scripts/deep_evidence") / f"{tool_path}.py"
    if not script.exists():
        logger.error("Script not found: %s", tool_path)
        return subprocess.run([sys.executable, "missing"], capture_output=True)
    cmd = [sys.executable, str(script), "--output", str(case_dir / "data" / f"{tool_path.replace('/', '_')}.json")]
    if "preprint_monitor" in tool_path:
        try:
            name = load_config(case_dir, "config.yaml").get("scholar", {}).get("name", "")
            if name: cmd.extend(["--name", name])
        except Exception: pass
    elif "image_metadata" in tool_path:
        pdfs = case_dir / "pdfs"
        if pdfs.is_dir(): cmd.extend(["--pdfs", str(pdfs)])
    else:
        for cand in [case_dir/"data"/"unified_papers.json", case_dir/"data"/"papers.json", case_dir/"scholar_data.json"]:
            if cand.exists(): cmd.extend(["--papers", str(cand)]); break
    print(f"[INFO] Running: {' '.join(cmd)}")
    return subprocess.run(cmd, env=_get_script_env())


def _find_template() -> Path | None:
    """Find config.template.yaml from multiple likely locations."""
    candidates = [
        Path("scripts/config.template.yaml"),
        Path("config.template.yaml"),
        Path(__file__).parent / "config.template.yaml",
        Path(__file__).parent.parent / "scripts" / "config.template.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def cmd_init(args):
    case_dir = get_case_dir(args)
    case_dir.mkdir(parents=True, exist_ok=True)
    logger = get_logger("investigate", case_dir=case_dir)
    config_path = case_dir / (args.config or "config.yaml")
    if not config_path.exists():
        template = _find_template()
        if template:
            shutil.copy(template, config_path)
            logger.info("Copied template to: %s", config_path)
        else:
            logger.error("config.template.yaml not found.")
            sys.exit(1)

    # Create standard directories
    ensure_dirs(case_dir, extra=["guides"])
    logger.info("Ensured standard directories in %s", case_dir)

    # Copy CHECKLIST.md from templates
    checklist_template = Path(__file__).parent / "templates" / "CHECKLIST.md"
    checklist_dest = case_dir / "CHECKLIST.md"
    if checklist_template.exists() and not checklist_dest.exists():
        shutil.copy(checklist_template, checklist_dest)
        logger.info("Copied CHECKLIST.md to: %s", checklist_dest)
        print(f"  [OK] 已复制检查清单: {checklist_dest}")

    # Initialize SQLite database
    db = InvestigationDB(case_dir)
    db.init_schema()
    logger.info("Database initialized: %s", db.db_path)

    case_name = args.name or f"case_{datetime.now().strftime('%Y%m%d')}"

    # Detect investigation type (allow --type override)
    config_data = load_config(case_dir, args.config or "config.yaml")
    if args.type:
        inv_type = InvestigationType(args.type)
        logger.info("Investigation type overridden by --type: %s", inv_type.value)
    else:
        inv_type = detect_investigation_type(config_data)
        logger.info("Detected investigation type: %s", inv_type.value)

    # Upsert investigation record
    db.upsert_investigation({
        "case_name": case_name,
        "investigation_type": inv_type.value,
        "status": "init",
        "current_step": "collect" if inv_type == InvestigationType.DOMESTIC else "auto_fetch",
        "started_at": datetime.now().isoformat(),
    })

    state = {
        "current_step": "collect" if inv_type == InvestigationType.DOMESTIC else "auto_fetch",
        "history": [{"step": "init", "timestamp": datetime.now().isoformat()}],
        "config_path": str(config_path),
        "case_name": case_name,
        "case_dir": str(case_dir),
        "investigation_type": inv_type.value,
    }
    save_state(state, get_state_path(args))
    csm = CaseStateMachine(case_dir)
    csm.write_state_md(phase="initialized")
    logger.info("案件初始化完成: %s", case_dir)
    print(f"\n[OK] 案件初始化完成: {case_dir}")
    print("  下一步：")
    print("  1. 编辑 config.yaml，填写学者基本信息和待验证声明")
    print(f"  2. 运行: python investigate.py --case-dir '{case_dir}' step")


def cmd_step(args):
    case_dir = get_case_dir(args); csm = CaseStateMachine(case_dir)
    phase = csm.get_current_phase()
    print(f"\n{'='*60}\n{case_dir.resolve().name} / phase: {phase}\n{'='*60}")
    if phase == "archived":
        print("\n调查已完成。所有步骤已归档。"); return
    if phase == "deep_evidence":
        recs = RuleEngine().evaluate(case_dir)
        if not recs:
            print("\n暂无动态推荐。运行 advance 进入下一阶段。"); return
        print("\n推荐工具 (Top 3):")
        for i, r in enumerate(recs[:3], 1):
            print(f"  {i}. [P{r.priority}] {', '.join(r.tools)}\n     原因: {r.reason}")
        c = input("\n输入编号运行对应工具，或 0/skip 跳过: ").strip().lower()
        if c not in ("0", "skip", "") and c.isdigit():
            idx = int(c) - 1
            if 0 <= idx < len(recs):
                _run_recommended_tool(case_dir, recs[idx].tools[0], get_logger("investigate"))
    else:
        g = PHASE_GUIDANCE.get(phase, {})
        print(f"\n{g.get('title', phase)}\n{g.get('desc', '')}")
        if g.get('next'):
            print("\n完成后运行: python investigate.py advance")


def cmd_advance(args):
    case_dir = get_case_dir(args); csm = CaseStateMachine(case_dir)
    phase = csm.get_current_phase()
    target = getattr(args, "to", None)
    if target:
        if target not in csm.PHASES:
            print(f"[ERROR] Unknown phase: {target}", file=sys.stderr); sys.exit(1)
        csm.write_state_md(phase=target)
        csm._record_transition(phase, target, override=True)
        print(f"[OK] 已跳转到阶段: {target}")
        cmd_step(args); return
    can, reason = csm.can_advance()
    if not can:
        print(f"[INFO] 无法从 {phase} 推进: {reason}"); return
    if phase == "deep_evidence" and getattr(args, "auto", False):
        skips = set(getattr(args, "skip", []) or [])
        for r in RuleEngine().evaluate(case_dir):
            for t in r.tools:
                if t in skips: print(f"[SKIP] {t}"); continue
                print(f"\n[RUN] {t} (P{r.priority})")
                res = _run_recommended_tool(case_dir, t, get_logger("investigate"))
                if res.returncode != 0:
                    print(f"[ERROR] 工具失败: {t}"); return
                csm.write_state_md()
                if csm.read_state_md().get("critical"):
                    print("[CRITICAL] 检测到关键信号，停止。"); return
        print("\n[OK] 所有推荐工具已执行。")
    csm.advance()
    print(f"[OK] 已推进到阶段: {csm.get_current_phase()}")
    cmd_step(args)


def cmd_status(args):
    case_dir = get_case_dir(args); csm = CaseStateMachine(case_dir)
    phase = csm.get_current_phase()
    print(f"\n案件: {case_dir.resolve().name}\n当前阶段: {phase}")
    history = csm.get_phase_history()
    if history:
        print(f"阶段历史: {' -> '.join([h.get('to', h.get('from', '')) for h in history])}")
    recs = RuleEngine().evaluate(case_dir)
    if recs:
        print(f"\n待处理推荐 ({len(recs)}):")
        for r in recs[:5]:
            print(f"  [P{r.priority}] {', '.join(r.tools)}: {r.reason}")
    crit = [c for c in csm.read_state_md().get("critical", []) if c != "(none)"]
    if crit:
        print(f"\n⚠️ CRITICAL 信号:"); [print(f"  - {c}") for c in crit]
    checks = {"config.yaml": (case_dir/"config.yaml").exists(), "data/": (case_dir/"data").is_dir(), "pdfs/": (case_dir/"pdfs").is_dir(), "scholar_data.json": (case_dir/"scholar_data.json").exists()}
    print("\n环境检查:")
    for n, o in checks.items():
        print(f"  [{'OK' if o else 'MISS'}] {n}")
    nets = list((case_dir/"reports").glob("*_network.html")) if (case_dir/"reports").is_dir() else []
    print(f"  [{'OK' if nets else 'MISS'}] 网络图谱")


def cmd_regress(args):
    csm = CaseStateMachine(get_case_dir(args))
    if args.force:
        cur = csm.get_current_phase(); csm.write_state_md(phase=args.to); csm._record_transition(cur, args.to, override=True); print(f"[OK] 强制回退到: {args.to}")
    else:
        csm.regress(args.to); print(f"[OK] 已回退到: {args.to}")


def cmd_add_task(args):
    case_dir = get_case_dir(args); tool, extra = args.tool, args.tool_args or []
    cmd = [sys.executable, tool] + extra
    print(f"[INFO] Running: {' '.join(cmd)}")
    res = subprocess.run(cmd, env=_get_script_env())
    db = InvestigationDB(case_dir); db.init_schema()
    db.log_decision(case_dir.name, f"add-task: {tool} {' '.join(extra)}", made_by="human")
    if res.returncode == 0: CaseStateMachine(case_dir).write_state_md()
    print(f"[{'OK' if res.returncode == 0 else 'ERROR'}] {'完成' if res.returncode == 0 else '失败'}: {tool}")
    sys.exit(res.returncode)


def cmd_collect(args):
    """Run Xiaotangdou to collect and classify all agent outputs."""
    case_dir = get_case_dir(args)
    logger = get_logger("investigate", case_dir=case_dir)

    try:
        from delivery import Xiaotangdou
        agent = Xiaotangdou(case_dir)
        result = agent.run()
        logger.info("Xiaotangdou collection complete: %s", result)
        print(f"\n[OK] 素材收集完成 ({result.get('chapters_ready', 0)}/9 章就绪)")
        if result.get("critical"):
            print(f"⚠️ 检测到 {result.get('gaps_count', 0)} 个信息缺口和 {result.get('conflicts_count', 0)} 个矛盾点")
            print("   查看 delivery/gaps_and_conflicts.md 了解详情")
        print(f"\n   交付目录: {case_dir / 'delivery'}")
        print("   下一步: python investigate.py generate")
    except Exception as e:
        logger.error("Xiaotangdou failed: %s", e)
        print(f"[ERROR] 素材收集失败: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_generate(args):
    """Run Xiaojinjing to generate final report and self-check."""
    case_dir = get_case_dir(args)
    logger = get_logger("investigate", case_dir=case_dir)

    # Check if collection checkpoint exists
    checkpoint_path = case_dir / "delivery" / "collection_checkpoint.json"
    if not checkpoint_path.exists():
        print("[ERROR] 未找到素材包。请先运行: python investigate.py collect", file=sys.stderr)
        sys.exit(1)

    try:
        from delivery import Xiaojinjing
        agent = Xiaojinjing(case_dir)
        result = agent.run()
        logger.info("Xiaojinjing generation complete: %s", result)

        sc = result.get("self_check", {})
        total_issues = (
            sc.get("ban_rules", {}).get("failed", 0) +
            sc.get("format_rules", {}).get("failed", 0) +
            sc.get("content_rules", {}).get("failed", 0)
        )

        print(f"\n[OK] 报告生成完成")
        print(f"   Markdown: {result['deliverables']['markdown_report']}")
        if result["deliverables"]["network_html"]:
            print(f"   HTML网络图: {result['deliverables']['network_html']}")

        if result.get("pass_status"):
            print(f"\n✅ 自检全部通过，报告可交付")
        else:
            print(f"\n⚠️ 自检发现 {total_issues} 个问题")
            print("   查看 reports/self_check_report.md 了解详情")
            if not args.force:
                print("   使用 --force 强制交付")
                sys.exit(1)

        # Update state machine
        csm = CaseStateMachine(case_dir)
        csm.write_state_md(phase="generated")
    except Exception as e:
        logger.error("Xiaojinjing failed: %s", e)
        print(f"[ERROR] 报告生成失败: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_unify(args):
    case_dir = get_case_dir(args); phase = args.phase
    print(f"--- UNIFY 阶段: {phase} ---")
    planned = input("计划做什么? ").strip()
    actual = input("实际做了什么? ").strip()
    deviations = input("偏差及原因? ").strip()
    decisions = input("关键决策? ").strip()
    db = InvestigationDB(case_dir); db.init_schema()
    db.add_unify_record(case_dir.name, phase, planned, actual, deviations, decisions)
    csm = CaseStateMachine(case_dir)
    content = csm.state_file.read_text(encoding="utf-8")
    block = f"### {phase}\n- planned: {planned}\n- actual: {actual}\n- deviations: {deviations}\n- decisions: {decisions}\n"
    if "## UNIFY Records" in content:
        content = content.replace("## UNIFY Records\n", f"## UNIFY Records\n{block}")
        content = content.replace("- (none)\n", "")
    else:
        content += f"\n## UNIFY Records\n{block}"
    csm.state_file.write_text(content, encoding="utf-8")
    print(f"[OK] UNIFY 记录已保存: {phase}")


def _load_validator_for_type(inv_type: str):
    """Dynamically import the correct validator module based on investigation type."""
    from core.utils import is_corruption_network

    if inv_type == "international":
        from international import data_validator as dv
        return dv, is_corruption_network
    elif inv_type == "cross_border":
        from cross_border import validator as dv
        # cross_border.validator doesn't have is_corruption_network; use core.utils
        return dv, is_corruption_network
    else:
        # Default: domestic (also handles old data without investigation_type)
        from domestic import data_validator as dv
        return dv, dv.is_corruption_network


def cmd_validate(args):
    case_dir = get_case_dir(args)
    logger = get_logger("investigate", case_dir=case_dir)
    scholar_data = case_dir / args.input if args.input else case_dir / "scholar_data.json"
    if not scholar_data.exists():
        logger.error("%s not found. Run 'python investigate.py step' and follow build instructions.", scholar_data)
        sys.exit(1)

    try:
        with open(scholar_data, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Determine investigation type from data, state, or args
        inv_type = data.get("investigation_type")
        if not inv_type:
            state = load_state(get_state_path(args))
            inv_type = state.get("investigation_type", "domestic")
        if args.type:
            inv_type = args.type

        dv, is_corruption_network_fn = _load_validator_for_type(inv_type)
        mode = "corruption_network" if is_corruption_network_fn(data) else "scholar_data"
        logger.info("Detected data mode: %s, investigation_type: %s", mode, inv_type)

        # cross_border.validator.validate() doesn't accept fix= parameter
        if inv_type == "cross_border":
            errors, warnings = dv.validate(data)
        else:
            errors, warnings = dv.validate(data, fix=False)

        if warnings:
            for w in warnings:
                logger.warning("%s", w)
        if errors:
            for e in errors:
                logger.error("%s", e)
            logger.error("Validation failed: %d error(s), %d warning(s).", len(errors), len(warnings))
            sys.exit(1)
        else:
            logger.info("Validation passed: 0 error(s), %d warning(s).", len(warnings))
            # Auto-import into SQLite for downstream use
            if mode == "scholar_data":
                db = InvestigationDB(case_dir)
                db.init_schema()
                db.import_scholar_data(data)
                logger.info("Imported scholar_data into SQLite")
    except Exception as e:
        logger.error("Validation failed: %s", e)
        sys.exit(1)


def cmd_score(args):
    hybrid_script = Path(__file__).parent / "hybrid_scorer.py"
    if not hybrid_script.exists():
        hybrid_script = Path("scripts/hybrid_scorer.py")
    if not hybrid_script.exists():
        print("[ERROR] hybrid_scorer.py not found.", file=sys.stderr)
        sys.exit(1)

    out_dir = args.output_dir or str(get_case_dir(args) / "reports")
    if args.apply:
        cmd = [
            sys.executable, str(hybrid_script), "apply",
            "--input-folder", args.input_folder,
            "--output-dir", out_dir,
        ]
        print(f"[INFO] Running: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        sys.exit(result.returncode)
    else:
        cmd = [
            sys.executable, str(hybrid_script), "prepare",
            "--input-folder", args.input_folder,
            "--output-dir", out_dir,
            "--excerpt", str(args.excerpt),
        ]
        print(f"[INFO] Running: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            sys.exit(result.returncode)
        out_path = Path(out_dir)
        print(f"\n[OK] 脚本分析完成。下一步：")
        print(f"  1. 将 {out_path}/llm_review_request.md 提交给 LLM")
        print(f"  2. 将 LLM 返回的 JSON 保存为 {out_path}/llm_observations_batch.json")
        print(f"  3. 运行: python investigate.py score -i {args.input_folder} -o {out_dir} --apply")


def _find_report_template(fallback: str) -> Path | None:
    candidates = [
        Path(fallback),
        Path("scripts/report_template.md"),
        Path("report/report_template.md"),
        Path("report_template.md"),
        Path(__file__).parent / "report" / "report_template.md",
        Path(__file__).parent / "report_template.md",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _find_international_template() -> Path | None:
    candidates = [
        Path("scripts/report/international_template.md"),
        Path("report/international_template.md"),
        Path(__file__).parent / "report" / "international_template.md",
        Path(__file__).parent / "international_template.md",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def cmd_prompt(args):
    case_dir = get_case_dir(args)
    data_path = case_dir / args.data if args.data else case_dir / "scholar_data.json"

    # Auto-select template based on investigation type
    if args.template:
        template = _find_report_template(args.template)
    else:
        # Check investigation type from scholar_data
        inv_type = "domestic"
        if data_path.exists():
            try:
                with open(data_path, "r", encoding="utf-8") as f:
                    sd = json.load(f)
                inv_type = sd.get("investigation_type", "domestic")
            except Exception:
                pass
        if inv_type == "international":
            template = _find_international_template()
            if not template:
                template = _find_report_template("scripts/report_template.md")
        else:
            template = _find_report_template("scripts/report_template.md")

    if not template:
        template = Path("report_template.md")

    if not data_path.exists():
        print(f"[ERROR] {data_path} not found.", file=sys.stderr)
        sys.exit(1)
    if not template or not template.exists():
        print("[ERROR] Report template not found.", file=sys.stderr)
        sys.exit(1)

    output = args.output or str(case_dir / "report_prompt.md")
    optimizer_script = Path(__file__).parent / "report" / "report_prompt_optimizer.py"
    if not optimizer_script.exists():
        optimizer_script = Path("scripts/report_prompt_optimizer.py")
    if not optimizer_script.exists():
        optimizer_script = Path("report/report_prompt_optimizer.py")
    if not optimizer_script.exists():
        print("[ERROR] report_prompt_optimizer.py not found.", file=sys.stderr)
        sys.exit(1)

    cmd = [
        sys.executable, str(optimizer_script),
        "--data", str(data_path),
        "--template", str(template),
        "--llm", args.llm,
        "--output", output
    ]
    print(f"[INFO] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


def _camoufox_available() -> bool:
    try:
        import camoufox
        return True
    except ImportError:
        return False


def cmd_wechat(args):
    wechat_script = Path(__file__).parent / "wechat_search.py"
    if not wechat_script.exists():
        wechat_script = Path("scripts/wechat_search.py")
    if not wechat_script.exists():
        print("[ERROR] wechat_search.py not found.", file=sys.stderr)
        sys.exit(1)

    output = args.output or str(get_case_dir(args) / "data" / "wechat_articles")

    # If camoufox is not in the current interpreter, try uv tool run wrapper
    if not _camoufox_available():
        cmd = [
            "uv", "tool", "run", "--from", "wechat-article-to-markdown",
            "python", str(wechat_script),
            "--keyword", args.keyword,
            "--limit", str(args.limit),
            "--output", output,
            "--download",
        ]
        print("[INFO] Camoufox not found in current Python environment; switching to uv tool run wrapper.")
    else:
        cmd = [
            sys.executable, str(wechat_script),
            "--keyword", args.keyword,
            "--limit", str(args.limit),
            "--output", output,
            "--download",
        ]

    print(f"[INFO] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("\n[HINT] If camoufox/playwright are missing, install wechat-article-to-markdown via uv:")
        print("  uv tool install wechat-article-to-markdown")
        print("Then re-run the command.")
    sys.exit(result.returncode)


def cmd_xiaohongshu(args):
    case_dir = get_case_dir(args)
    logger = get_logger("investigate", case_dir=case_dir)
    xhs_script = Path(__file__).parent / "international" / "xiaohongshu_client.py"
    if not xhs_script.exists():
        xhs_script = Path("scripts/international/xiaohongshu_client.py")
    if not xhs_script.exists():
        print("[ERROR] international/xiaohongshu_client.py not found.", file=sys.stderr)
        sys.exit(1)

    # Resolve name/institution from args or config
    name = args.name
    institution = args.institution
    if not name or not institution:
        config_path = case_dir / "config.yaml"
        if config_path.exists():
            try:
                config_data = load_config(case_dir, "config.yaml")
                scholar = config_data.get("scholar", {})
                if not name:
                    name = scholar.get("name") or scholar.get("name_en")
                if not institution:
                    institution = scholar.get("institution") or scholar.get("institution_en")
            except Exception as e:
                logger.warning("Could not read config.yaml: %s", e)

    if not name or not institution:
        print("[ERROR] --name and --institution are required (or set them in config.yaml).", file=sys.stderr)
        sys.exit(1)

    output = args.output or str(case_dir / "data" / "xiaohongshu_reviews.json")
    Path(output).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, str(xhs_script),
        "--name", name,
        "--institution", institution,
        "--output", output,
        "--max-results", str(args.limit),
    ]
    if args.api_mode:
        cmd.append("--api-mode")
    if args.cookie:
        cmd.extend(["--cookie", args.cookie])

    print(f"[INFO] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=_get_script_env())
    if result.returncode == 0:
        print(f"\n[OK] 小红书评价采集完成: {output}")
    sys.exit(result.returncode)


def cmd_visualize(args):
    viz_script = Path(__file__).parent / "network_visualizer.py"
    if not viz_script.exists():
        viz_script = Path("scripts/network_visualizer.py")
    if not viz_script.exists():
        print("[ERROR] network_visualizer.py not found.", file=sys.stderr)
        sys.exit(1)

    case_dir = get_case_dir(args)
    data_path = case_dir / args.data if args.data else case_dir / "scholar_data.json"
    if not data_path.exists():
        print(f"[ERROR] {data_path} not found. Run 'python investigate.py build' first.", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.output_dir) if args.output_dir else (case_dir / "reports")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Derive prefix from scholar name or network name if not provided
    prefix = args.prefix
    if not prefix:
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            prefix = d.get("name") or d.get("network_name", "scholar")
        except Exception:
            prefix = "scholar"

    cmd = [
        sys.executable, str(viz_script),
        "--input", str(data_path),
        "--output-dir", str(out_dir),
        "--prefix", prefix,
    ]
    print(f"[INFO] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode == 0:
        print(f"\n[OK] 网络图谱已生成: {out_dir}/{prefix}_network.html")
        print(f"     原始数据: {out_dir}/{prefix}_network.json")
    sys.exit(result.returncode)


def cmd_timeline(args):
    script = Path(__file__).parent / "timeline_weaver.py"
    if not script.exists():
        script = Path("scripts/timeline_weaver.py")
    if not script.exists():
        print("[ERROR] timeline_weaver.py not found.", file=sys.stderr)
        sys.exit(1)

    case_dir = get_case_dir(args)
    output = args.output or str(case_dir / "reports")

    cmd = [
        sys.executable, str(script),
        "--network", args.network,
        "--output", output,
        "--window-months", str(args.window_months),
        "--min-nodes", str(args.min_nodes),
    ]
    print(f"[INFO] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


def cmd_grants(args):
    script = Path(__file__).parent / "grant_linker.py"
    if not script.exists():
        script = Path("scripts/grant_linker.py")
    if not script.exists():
        print("[ERROR] grant_linker.py not found.", file=sys.stderr)
        sys.exit(1)

    case_dir = get_case_dir(args)
    output = args.output or str(case_dir / "reports")

    cmd = [
        sys.executable, str(script),
        "--network", args.network,
        "--output", output,
    ]
    if args.pi_table:
        cmd.extend(["--pi-table", args.pi_table])
    if args.papers:
        cmd.extend(["--papers", args.papers])
    print(f"[INFO] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


def cmd_negative(args):
    script = Path(__file__).parent / "negative_space_analyzer.py"
    if not script.exists():
        script = Path("scripts/negative_space_analyzer.py")
    if not script.exists():
        print("[ERROR] negative_space_analyzer.py not found.", file=sys.stderr)
        sys.exit(1)

    case_dir = get_case_dir(args)
    output = args.output or str(case_dir / "reports")

    cmd = [
        sys.executable, str(script),
        "--network", args.network,
        "--output", output,
    ]
    if args.questions:
        cmd.extend(["--questions", args.questions])
    if args.statements:
        cmd.extend(["--statements", args.statements])
    print(f"[INFO] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


def cmd_retrospect(args):
    script = Path(__file__).parent / "investigation_retrospector.py"
    if not script.exists():
        script = Path("scripts/investigation_retrospector.py")
    if not script.exists():
        print("[ERROR] investigation_retrospector.py not found.", file=sys.stderr)
        sys.exit(1)

    case_dir = get_case_dir(args)
    data_path = case_dir / args.data if args.data else case_dir / "corruption_network.json"
    output = args.output or str(case_dir / "retrospective_summary.md")

    cmd = [
        sys.executable, str(script),
        "--data", str(data_path),
        "--output", output,
    ]
    if args.report:
        cmd.extend(["--report", args.report])
    if args.notes:
        cmd.extend(["--notes", args.notes])
    if args.apply:
        cmd.append("--apply")
    print(f"[INFO] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(description="Academic investigation CLI orchestrator")
    parser.add_argument("--case-dir", "-C", default=None, help="Case working directory (default: current directory)")
    parser.add_argument("--type", choices=["domestic", "international", "cross_border"], default=None,
                        help="Override investigation type (default: auto-detect from config)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_init = subparsers.add_parser("init", help="Initialize case directory")
    p_init.add_argument("--config", "-c", default="config.yaml", help="Path to config.yaml (will copy from template if missing)")
    p_init.add_argument("--name", "-n", help="Case name")

    p_step = subparsers.add_parser("step", help="Show current step guidance")

    p_advance = subparsers.add_parser("advance", help="Advance to next phase")
    p_advance.add_argument("--to", help="Target phase")
    p_advance.add_argument("--auto", action="store_true", help="Auto-run deep_evidence recommendations")
    p_advance.add_argument("--skip", action="append", help="Skip a recommended tool (can repeat)")

    p_status = subparsers.add_parser("status", help="Show case status and file checks")

    p_validate = subparsers.add_parser("validate", help="Run data validation")
    p_validate.add_argument("--input", "-i", default="scholar_data.json", help="Path to scholar_data.json")

    p_score = subparsers.add_parser("score", help="Run hybrid script+LLM scoring on a folder of papers")
    p_score.add_argument("--input-folder", "-i", required=True, help="Folder containing papers (PDF/md/txt)")
    p_score.add_argument("--output-dir", "-o", default=None, help="Output directory for scores (default: <case-dir>/reports)")
    p_score.add_argument("--excerpt", "-e", type=int, default=3000, help="Max chars for text excerpt sent to LLM")
    p_score.add_argument("--apply", action="store_true", help="Skip prepare and go straight to apply (observations must already exist)")

    p_prompt = subparsers.add_parser("prompt", help="Generate optimized report prompt")
    p_prompt.add_argument("--data", "-d", default="scholar_data.json")
    p_prompt.add_argument("--template", "-t", default="scripts/report_template.md")
    p_prompt.add_argument("--llm", default="claude", choices=["claude", "gpt", "kimi"])
    p_prompt.add_argument("--output", "-o", default=None, help="Output path (default: <case-dir>/report_prompt.md)")

    p_wechat = subparsers.add_parser("wechat", help="Search and download WeChat articles as supplementary leads")
    p_wechat.add_argument("--keyword", "-k", required=True, help="Search keyword (usually scholar name)")
    p_wechat.add_argument("--limit", "-l", type=int, default=10, help="Max results")
    p_wechat.add_argument("--output", "-o", default=None, help="Output directory (default: <case-dir>/data/wechat_articles)")

    p_xiaohongshu = subparsers.add_parser("xiaohongshu", help="Search Xiaohongshu for Chinese student reviews of foreign advisors")
    p_xiaohongshu.add_argument("--name", "-n", default=None, help="Advisor name (default: from config.yaml)")
    p_xiaohongshu.add_argument("--institution", "-i", default=None, help="Institution name (default: from config.yaml)")
    p_xiaohongshu.add_argument("--output", "-o", default=None, help="Output JSON path (default: <case-dir>/data/xiaohongshu_reviews.json)")
    p_xiaohongshu.add_argument("--api-mode", action="store_true", help="Use API mode with xhshow signature (requires cookie)")
    p_xiaohongshu.add_argument("--cookie", "-c", default=None, help="Xiaohongshu cookie string for API mode")
    p_xiaohongshu.add_argument("--limit", "-l", type=int, default=20, help="Max results")

    p_visualize = subparsers.add_parser("visualize", help="Generate interactive relationship network graph from scholar_data.json or corruption_network.json")
    p_visualize.add_argument("--data", "-d", default="scholar_data.json", help="Path to scholar_data.json or corruption_network.json")
    p_visualize.add_argument("--output-dir", "-o", default=None, help="Output directory for HTML and JSON (default: <case-dir>/reports)")
    p_visualize.add_argument("--prefix", "-p", default="", help="Filename prefix (defaults to name/network_name)")

    p_timeline = subparsers.add_parser("timeline", help="Weave unified timeline and detect coupling windows from corruption_network.json")
    p_timeline.add_argument("--network", "-n", required=True, help="Path to corruption_network.json")
    p_timeline.add_argument("--output", "-o", default=None, help="Output directory (default: <case-dir>/reports)")
    p_timeline.add_argument("--window-months", type=int, default=6, help="Coupling window in months")
    p_timeline.add_argument("--min-nodes", type=int, default=2, help="Minimum unique nodes for coupling window")

    p_grants = subparsers.add_parser("grants", help="Analyze grant linkages across papers and events")
    p_grants.add_argument("--network", "-n", required=True, help="Path to corruption_network.json")
    p_grants.add_argument("--output", "-o", default=None, help="Output directory (default: <case-dir>/reports)")
    p_grants.add_argument("--pi-table", help="Path to PI table JSON")
    p_grants.add_argument("--papers", "-p", help="Directory containing paper texts")

    p_negative = subparsers.add_parser("negative", help="Run negative-space analysis on official statements")
    p_negative.add_argument("--network", "-n", required=True, help="Path to corruption_network.json")
    p_negative.add_argument("--output", "-o", default=None, help="Output directory (default: <case-dir>/reports)")
    p_negative.add_argument("--questions", "-q", help="Path to questions JSON")
    p_negative.add_argument("--statements", "-s", help="Directory containing official statement texts")

    p_retrospect = subparsers.add_parser("retrospect", help="Run post-mortem analysis and extract heuristics")
    p_retrospect.add_argument("--data", "-d", default="corruption_network.json", help="Path to corruption_network.json or scholar_data.json")
    p_retrospect.add_argument("--report", "-r", help="Path to final report markdown")
    p_retrospect.add_argument("--notes", "-n", help="Path to user retrospective notes")
    p_retrospect.add_argument("--output", "-o", default=None, help="Output path (default: <case-dir>/retrospective_summary.md)")
    p_retrospect.add_argument("--apply", action="store_true", help="Write project memory and print heuristic proposals")

    p_intl_fetch = subparsers.add_parser("international-fetch", help="Auto-fetch international scholar data from free APIs")
    p_intl_fetch.add_argument("--config", "-c", default="config.yaml", help="Path to config.yaml")
    p_intl_fetch.add_argument("--output", "-o", default=None, help="Output auto_fetched.json path (default: <case-dir>/data/auto_fetched.json)")
    p_intl_fetch.add_argument("--sources", "-s", nargs="+", default=["openalex", "semantic_scholar", "orcid", "arxiv"],
                              help="Sources to fetch from")

    p_intl_build = subparsers.add_parser("international-build", help="Build international scholar_data.json from auto-fetched data")
    p_intl_build.add_argument("--config", "-c", default="config.yaml", help="Path to config.yaml")
    p_intl_build.add_argument("--auto-data", "-a", default=None, help="Path to auto_fetched.json")
    p_intl_build.add_argument("--xiaohongshu", "-x", default=None, help="Path to xiaohongshu_reviews.json")
    p_intl_build.add_argument("--output", "-o", default="scholar_data.json", help="Output scholar_data.json path")
    p_intl_build.add_argument("--fix", action="store_true", help="Auto-fix missing fields")

    p_missing = subparsers.add_parser("missing-report", help="Generate missing information report for manual lookup")
    p_missing.add_argument("--scholar-data", "-s", default="scholar_data.json", help="Path to scholar_data.json")
    p_missing.add_argument("--config", "-c", default="config.yaml", help="Path to config.yaml")
    p_missing.add_argument("--output", "-o", default=None, help="Output markdown path (default: <case-dir>/reports/missing_report.md)")

    p_review_agg = subparsers.add_parser("review-aggregate", help="Aggregate multi-source reviews (domestic + xiaohongshu + RMP)")
    p_review_agg.add_argument("--domestic", "-d", help="Path to domestic review_matcher output JSON")
    p_review_agg.add_argument("--xiaohongshu", "-x", help="Path to xiaohongshu_client output JSON")
    p_review_agg.add_argument("--ratemyprofessors", "-r", help="Path to RateMyProfessors JSON")
    p_review_agg.add_argument("--output", "-o", required=True, help="Output merged JSON path")

    p_cb_merge = subparsers.add_parser("cross-border-merge", help="Merge domestic + international scholar_data")
    p_cb_merge.add_argument("--domestic", "-d", required=True, help="Path to domestic scholar_data.json")
    p_cb_merge.add_argument("--international", "-i", required=True, help="Path to international scholar_data.json")
    p_cb_merge.add_argument("--output", "-o", required=True, help="Output merged JSON path")

    p_regress = subparsers.add_parser("regress", help="Regress to a previous phase")
    p_regress.add_argument("--to", required=True, help="Target phase")
    p_regress.add_argument("--force", action="store_true", help="Bypass validation")

    p_add_task = subparsers.add_parser("add-task", help="Manually run a tool in the workflow")
    p_add_task.add_argument("--tool", required=True, help="Path to tool script")
    p_add_task.add_argument("tool_args", nargs=argparse.REMAINDER, help="Extra arguments for the tool")

    p_unify = subparsers.add_parser("unify", help="Record phase post-mortem UNIFY data")
    p_unify.add_argument("--phase", required=True, help="Phase to unify")

    p_watermark = subparsers.add_parser("watermark", help="Embed or extract invisible watermark from report")
    p_watermark.add_argument("--input", "-i", required=True, help="Input report markdown file")
    p_watermark.add_argument("--output", "-o", help="Output watermarked file (default: input + _wm.md)")
    p_watermark.add_argument("--case-id", "-c", help="Case identifier for embedding")
    p_watermark.add_argument("--client", "-cl", help="Client identifier for embedding")
    p_watermark.add_argument("--extract", "-e", action="store_true", help="Extract watermark instead of embedding")
    p_watermark.add_argument("--strategy", "-s", default="header", choices=["header", "paragraph", "every_period"])

    # v3.0 Deep Evidence layer
    p_preprint = subparsers.add_parser("preprint-monitor", help="Monitor preprint servers for duplicate submission signals (v3.0)")
    p_preprint.add_argument("--name", required=True, help="Author name")
    p_preprint.add_argument("--arxiv-name", help="Author name for arXiv query")
    p_preprint.add_argument("--journal-papers", type=Path, help="Path to unified_papers.json")
    p_preprint.add_argument("--output", "-o", type=Path, default=Path("./data/preprints.json"))
    p_preprint.add_argument("--sources", nargs="+", default=["arxiv", "biorxiv", "medrxiv"])

    p_cycle = subparsers.add_parser("review-cycle", help="Analyze review cycle anomalies using Crossref (v3.0)")
    p_cycle.add_argument("--papers", type=Path, required=True, help="Path to unified_papers.json")
    p_cycle.add_argument("--output", "-o", type=Path, default=Path("./data/cycle_analysis.json"))
    p_cycle.add_argument("--journal-benchmarks", type=Path, help="Cached benchmarks JSON")
    p_cycle.add_argument("--save-benchmarks", type=Path, help="Save fetched benchmarks")

    # v3.0 deep_evidence layer — additional CLI entries
    p_stats = subparsers.add_parser("stats-reverse-engineer", help="Reverse-engineer reported statistics for consistency (v3.0)")
    p_stats.add_argument("--papers", type=Path, required=True, help="Path to papers JSON")
    p_stats.add_argument("--output", "-o", type=Path, default=Path("./data/stats_audit.json"))
    p_stats.add_argument("--threshold", type=float, default=0.1, help="Relative error threshold")

    p_img = subparsers.add_parser("image-metadata", help="Extract image metadata from PDFs (v3.0)")
    p_img.add_argument("--pdfs", type=Path, help="Directory containing PDFs")
    p_img.add_argument("--pdf-list", type=Path, help="JSON array of PDF paths")
    p_img.add_argument("--output", "-o", type=Path, default=Path("./data/image_audit.json"))

    p_ethics = subparsers.add_parser("ethics-parse", help="Parse ethics statements from papers (v3.0)")
    p_ethics.add_argument("--papers", type=Path, required=True, help="Path to papers JSON")
    p_ethics.add_argument("--output", "-o", type=Path, default=Path("./data/ethics_audit.json"))
    p_ethics.add_argument("--check-clinical", action="store_true", help="Enable clinical trial cross-check")

    p_trial = subparsers.add_parser("trial-registry", help="Check clinical trial registration (v3.0)")
    p_trial.add_argument("--papers", type=Path, required=True, help="Path to papers JSON")
    p_trial.add_argument("--output", "-o", type=Path, default=Path("./data/trial_registry.json"))

    p_conf = subparsers.add_parser("conference-map", help="Map conference papers to journal papers (v3.0)")
    p_conf.add_argument("--papers", type=Path, required=True, help="Path to unified papers JSON")
    p_conf.add_argument("--output", "-o", type=Path, default=Path("./data/conference_map.json"))

    p_bilingual = subparsers.add_parser("bilingual-detect", help="Detect undisclosed bilingual publication (v3.0)")
    p_bilingual.add_argument("--papers", type=Path, required=True, help="Path to unified papers JSON")
    p_bilingual.add_argument("--output", "-o", type=Path, default=Path("./data/bilingual_detect.json"))

    p_events = subparsers.add_parser("crossref-events", help="Track Crossref Event Data for papers (v3.0)")
    p_events.add_argument("--papers", type=Path, required=True, help="Path to papers JSON")
    p_events.add_argument("--output", "-o", type=Path, default=Path("./data/crossref_events.json"))
    p_events.add_argument("--delay", type=float, default=1.0, help="Seconds between API calls")

    p_edsp = subparsers.add_parser("editorial-selfpub", help="Detect editorial self-publishing (v3.0)")
    p_edsp.add_argument("--papers", type=Path, required=True, help="Path to papers JSON")
    p_edsp.add_argument("--editor-journals", type=Path, help="JSON mapping editor to journal ISSN")
    p_edsp.add_argument("--output", "-o", type=Path, default=Path("./data/editorial_audit.json"))

    p_revnet = subparsers.add_parser("reviewer-network", help="Analyze recommended reviewer networks (v3.0)")
    p_revnet.add_argument("--papers", type=Path, required=True, help="Path to papers JSON")
    p_revnet.add_argument("--output", "-o", type=Path, default=Path("./data/reviewer_network.json"))

    p_retract = subparsers.add_parser("retraction-history", help="Analyze journal retraction history (v3.0)")
    p_retract.add_argument("--papers", type=Path, required=True, help="Path to papers JSON")
    p_retract.add_argument("--output", "-o", type=Path, default=Path("./data/retraction_history.json"))
    p_retract.add_argument("--retraction-watch-csv", type=Path, help="Local Retraction Watch CSV")

    # v3.2 Multi-agent collaboration layer
    p_orchestrate = subparsers.add_parser("orchestrate", help="Run multi-agent collaborative investigation (v3.2)")
    p_orchestrate.add_argument("--case-dir", type=Path, help="Case directory")
    p_orchestrate.add_argument("--mode", choices=["manual", "auto"], default="manual", help="Execution mode")
    p_orchestrate.add_argument("--agents", default="all", help="Comma-separated agent list (default: all)")
    p_orchestrate.add_argument("--max-rounds", type=int, default=20, help="Maximum rounds (safety limit)")

    # v3.2 Delivery layer
    p_collect = subparsers.add_parser("collect", help="Run Xiaotangdou to collect and classify agent outputs (v3.2)")
    p_collect.add_argument("--case-dir", type=Path, help="Case directory")

    p_generate = subparsers.add_parser("generate", help="Run Xiaojinjing to generate final report (v3.2)")
    p_generate.add_argument("--case-dir", type=Path, help="Case directory")
    p_generate.add_argument("--force", action="store_true", help="Force deliver even if self-check fails")

    # v3.2+ Free tool integrations
    p_journal_check = subparsers.add_parser("journal-check", help="Check journal credibility via free APIs (DOAJ/SCImago/COPE/OASPA/RetractionWatch)")
    p_journal_check.add_argument("--issn", default="", help="Journal ISSN")
    p_journal_check.add_argument("--journal-name", default="", help="Journal name")
    p_journal_check.add_argument("--publisher", default="", help="Publisher name")
    p_journal_check.add_argument("--input", type=Path, help="JSON array of journals [{issn, name, publisher}]")
    p_journal_check.add_argument("--output", "-o", type=Path, default=None, help="Output JSON path")

    p_citation_analysis = subparsers.add_parser("citation-analysis", help="Analyze citation constellation via OpenAlex (free)")
    p_citation_analysis.add_argument("--name", required=True, help="Author name")
    p_citation_analysis.add_argument("--institution", default="", help="Author institution")
    p_citation_analysis.add_argument("--orcid", default="", help="Author ORCID")
    p_citation_analysis.add_argument("--max-works", type=int, default=50, help="Max works to fetch")
    p_citation_analysis.add_argument("--max-citations", type=int, default=100, help="Max citations per work")
    p_citation_analysis.add_argument("--output", "-o", type=Path, default=None, help="Output directory")

    p_source_eval = subparsers.add_parser("source-eval", help="Evaluate source credibility via CRAAP Test")
    p_source_eval.add_argument("--source-type", required=True, choices=["journal", "website", "news", "social_media", "government", "wiki", "other"], help="Source type")
    p_source_eval.add_argument("--title", default="", help="Source title")
    p_source_eval.add_argument("--url", default="", help="Source URL")
    p_source_eval.add_argument("--currency", type=int, default=3, help="Currency score 1-5")
    p_source_eval.add_argument("--relevance", type=int, default=3, help="Relevance score 1-5")
    p_source_eval.add_argument("--authority", type=int, default=3, help="Authority score 1-5")
    p_source_eval.add_argument("--accuracy", type=int, default=3, help="Accuracy score 1-5")
    p_source_eval.add_argument("--purpose", type=int, default=3, help="Purpose score 1-5")
    p_source_eval.add_argument("--output", "-o", type=Path, default=None, help="Output JSON path")

    p_domestic_enrich = subparsers.add_parser("domestic-enrich", help="Enrich domestic scholar data with OpenAlex English papers (free)")
    p_domestic_enrich.add_argument("--name", required=True, help="Scholar name")
    p_domestic_enrich.add_argument("--institution", default="", help="Scholar institution")
    p_domestic_enrich.add_argument("--input", "-i", type=Path, required=True, help="Input scholar_data.json")
    p_domestic_enrich.add_argument("--output", "-o", type=Path, default=None, help="Output enriched JSON path")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "step":
        cmd_step(args)
    elif args.command == "advance":
        cmd_advance(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "regress":
        cmd_regress(args)
    elif args.command == "add-task":
        cmd_add_task(args)
    elif args.command == "unify":
        cmd_unify(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "score":
        cmd_score(args)
    elif args.command == "prompt":
        cmd_prompt(args)
    elif args.command == "wechat":
        cmd_wechat(args)
    elif args.command == "xiaohongshu":
        cmd_xiaohongshu(args)
    elif args.command == "visualize":
        cmd_visualize(args)
    elif args.command == "timeline":
        cmd_timeline(args)
    elif args.command == "grants":
        cmd_grants(args)
    elif args.command == "negative":
        cmd_negative(args)
    elif args.command == "retrospect":
        cmd_retrospect(args)
    elif args.command == "international-fetch":
        cmd_international_fetch(args)
    elif args.command == "international-build":
        cmd_international_build(args)
    elif args.command == "missing-report":
        cmd_missing_report(args)
    elif args.command == "review-aggregate":
        cmd_review_aggregate(args)
    elif args.command == "cross-border-merge":
        cmd_cross_border_merge(args)
    elif args.command == "watermark":
        cmd_watermark(args)
    elif args.command == "preprint-monitor":
        cmd_preprint_monitor(args)
    elif args.command == "review-cycle":
        cmd_review_cycle(args)
    elif args.command == "stats-reverse-engineer":
        cmd_stats_reverse_engineer(args)
    elif args.command == "image-metadata":
        cmd_image_metadata(args)
    elif args.command == "ethics-parse":
        cmd_ethics_parse(args)
    elif args.command == "trial-registry":
        cmd_trial_registry(args)
    elif args.command == "conference-map":
        cmd_conference_map(args)
    elif args.command == "bilingual-detect":
        cmd_bilingual_detect(args)
    elif args.command == "crossref-events":
        cmd_crossref_events(args)
    elif args.command == "editorial-selfpub":
        cmd_editorial_selfpub(args)
    elif args.command == "reviewer-network":
        cmd_reviewer_network(args)
    elif args.command == "retraction-history":
        cmd_retraction_history(args)
    elif args.command == "orchestrate":
        cmd_orchestrate(args)
    elif args.command == "collect":
        cmd_collect(args)
    elif args.command == "generate":
        cmd_generate(args)
    elif args.command == "journal-check":
        cmd_journal_check(args)
    elif args.command == "citation-analysis":
        cmd_citation_analysis(args)
    elif args.command == "source-eval":
        cmd_source_eval(args)
    elif args.command == "domestic-enrich":
        cmd_domestic_enrich(args)


def _run_deep_evidence_script(script_name: str, args, extra_args: list = None):
    """Generic helper to run a deep_evidence script via subprocess."""
    logger = get_logger("investigate")
    script = Path(__file__).parent / "deep_evidence" / script_name
    if not script.exists():
        alt = Path("scripts") / "deep_evidence" / script_name
        if alt.exists():
            script = alt
    if not script.exists():
        print(f"[ERROR] {script_name} not found.", file=sys.stderr)
        sys.exit(1)

    cmd = [sys.executable, str(script)]
    if extra_args:
        cmd.extend(extra_args)
    print(f"[INFO] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=_get_script_env())
    sys.exit(result.returncode)


def cmd_stats_reverse_engineer(args):
    extra = ["--papers", str(args.papers), "--output", str(args.output), "--threshold", str(args.threshold)]
    _run_deep_evidence_script("data_forensics/stats_reverse_engineer.py", args, extra)


def cmd_image_metadata(args):
    extra = ["--output", str(args.output)]
    if args.pdfs:
        extra.extend(["--pdfs", str(args.pdfs)])
    if args.pdf_list:
        extra.extend(["--pdf-list", str(args.pdf_list)])
    _run_deep_evidence_script("data_forensics/image_metadata_extractor.py", args, extra)


def cmd_ethics_parse(args):
    extra = ["--papers", str(args.papers), "--output", str(args.output)]
    if args.check_clinical:
        extra.append("--check-clinical")
    _run_deep_evidence_script("ethics_audit/ethics_statement_parser.py", args, extra)


def cmd_trial_registry(args):
    extra = ["--papers", str(args.papers), "--output", str(args.output)]
    _run_deep_evidence_script("ethics_audit/clinical_trial_registry_checker.py", args, extra)


def cmd_conference_map(args):
    extra = ["--papers", str(args.papers), "--output", str(args.output)]
    _run_deep_evidence_script("publication_trace/conference_paper_mapper.py", args, extra)


def cmd_bilingual_detect(args):
    extra = ["--papers", str(args.papers), "--output", str(args.output)]
    _run_deep_evidence_script("publication_trace/bilingual_publication_detector.py", args, extra)


def cmd_crossref_events(args):
    extra = ["--papers", str(args.papers), "--output", str(args.output), "--delay", str(args.delay)]
    _run_deep_evidence_script("publication_trace/crossref_event_tracker.py", args, extra)


def cmd_editorial_selfpub(args):
    extra = ["--papers", str(args.papers), "--output", str(args.output)]
    if args.editor_journals:
        extra.extend(["--editor-journals", str(args.editor_journals)])
    _run_deep_evidence_script("peer_review_intel/editorial_self_publishing_detector.py", args, extra)


def cmd_reviewer_network(args):
    extra = ["--papers", str(args.papers), "--output", str(args.output)]
    _run_deep_evidence_script("peer_review_intel/recommended_reviewer_network.py", args, extra)


def cmd_retraction_history(args):
    extra = ["--papers", str(args.papers), "--output", str(args.output)]
    if args.retraction_watch_csv:
        extra.extend(["--retraction-watch-csv", str(args.retraction_watch_csv)])
    _run_deep_evidence_script("peer_review_intel/journal_retraction_history.py", args, extra)


def cmd_preprint_monitor(args):
    logger = get_logger("investigate")
    script = Path(__file__).parent / "deep_evidence" / "publication_trace" / "preprint_monitor.py"
    if not script.exists():
        script = Path("scripts/deep_evidence/publication_trace/preprint_monitor.py")
    if not script.exists():
        print("[ERROR] deep_evidence/publication_trace/preprint_monitor.py not found.", file=sys.stderr)
        sys.exit(1)

    cmd = [sys.executable, str(script), "--name", args.name]
    if args.arxiv_name:
        cmd.extend(["--arxiv-name", args.arxiv_name])
    if args.journal_papers:
        cmd.extend(["--journal-papers", str(args.journal_papers)])
    if args.output:
        cmd.extend(["--output", str(args.output)])
    if args.sources:
        cmd.extend(["--sources"] + list(args.sources))
    print(f"[INFO] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=_get_script_env())
    sys.exit(result.returncode)


def cmd_review_cycle(args):
    logger = get_logger("investigate")
    script = Path(__file__).parent / "deep_evidence" / "peer_review_intel" / "review_cycle_analyzer.py"
    if not script.exists():
        script = Path("scripts/deep_evidence/peer_review_intel/review_cycle_analyzer.py")
    if not script.exists():
        print("[ERROR] deep_evidence/peer_review_intel/review_cycle_analyzer.py not found.", file=sys.stderr)
        sys.exit(1)

    cmd = [sys.executable, str(script), "--papers", str(args.papers), "--output", str(args.output)]
    if args.journal_benchmarks:
        cmd.extend(["--journal-benchmarks", str(args.journal_benchmarks)])
    if args.save_benchmarks:
        cmd.extend(["--save-benchmarks", str(args.save_benchmarks)])
    print(f"[INFO] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=_get_script_env())
    sys.exit(result.returncode)


def cmd_international_fetch(args):
    case_dir = get_case_dir(args)
    logger = get_logger("investigate", case_dir=case_dir)
    fetcher_script = Path(__file__).parent / "international" / "data_fetcher.py"
    if not fetcher_script.exists():
        fetcher_script = Path("scripts/international/data_fetcher.py")
    if not fetcher_script.exists():
        print("[ERROR] international/data_fetcher.py not found.", file=sys.stderr)
        sys.exit(1)

    config_path = case_dir / args.config if args.config else case_dir / "config.yaml"
    output = args.output or str(case_dir / "data" / "auto_fetched.json")
    Path(output).parent.mkdir(parents=True, exist_ok=True)

    # Read scholar name and ORCID from config
    name = ""
    institution = ""
    orcid = ""
    if config_path.exists():
        try:
            config_data = load_config(case_dir, args.config or "config.yaml")
            scholar = config_data.get("scholar", {})
            name = scholar.get("name") or scholar.get("name_en", "")
            institution = scholar.get("institution") or scholar.get("institution_en", "")
            orcid = scholar.get("orcid", "")
        except Exception as e:
            logger.warning("Could not read config.yaml: %s", e)

    if not name:
        print("[ERROR] Scholar name not found in config.yaml. Please set scholar.name.", file=sys.stderr)
        sys.exit(1)

    cmd = [
        sys.executable, str(fetcher_script),
        "--name", name,
        "--output", output,
    ]
    if institution:
        cmd.extend(["--institution", institution])
    if orcid:
        cmd.extend(["--orcid", orcid])
    # data_fetcher.py main() only supports single --source; use 'all' for multiple
    if len(args.sources) == 1 and args.sources[0] != "all":
        cmd.extend(["--source", args.sources[0]])
    # else: default is 'all' which covers all enabled sources
    print(f"[INFO] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=_get_script_env())
    if result.returncode == 0:
        print(f"\n[OK] 国际数据抓取完成: {output}")
    sys.exit(result.returncode)


def cmd_international_build(args):
    case_dir = get_case_dir(args)
    logger = get_logger("investigate", case_dir=case_dir)
    builder_script = Path(__file__).parent / "international" / "scholar_data_builder.py"
    if not builder_script.exists():
        builder_script = Path("scripts/international/scholar_data_builder.py")
    if not builder_script.exists():
        print("[ERROR] international/scholar_data_builder.py not found.", file=sys.stderr)
        sys.exit(1)

    config_path = case_dir / args.config if args.config else case_dir / "config.yaml"
    auto_data = args.auto_data or str(case_dir / "data" / "auto_fetched.json")
    xhs_data = args.xiaohongshu or str(case_dir / "data" / "xiaohongshu_reviews.json")
    output = case_dir / args.output if args.output else case_dir / "scholar_data.json"

    cmd = [
        sys.executable, str(builder_script),
        "--config", str(config_path),
        "--auto-data", auto_data,
        "--output", str(output),
    ]
    if Path(xhs_data).exists():
        cmd.extend(["--xiaohongshu", xhs_data])
    if args.fix:
        cmd.append("--fix")
    print(f"[INFO] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=_get_script_env())
    if result.returncode == 0:
        print(f"\n[OK] 国际版 scholar_data.json 构建完成: {output}")
    sys.exit(result.returncode)


def cmd_missing_report(args):
    case_dir = get_case_dir(args)
    logger = get_logger("investigate", case_dir=case_dir)
    reporter_script = Path(__file__).parent / "international" / "missing_reporter.py"
    if not reporter_script.exists():
        reporter_script = Path("scripts/international/missing_reporter.py")
    if not reporter_script.exists():
        print("[ERROR] international/missing_reporter.py not found.", file=sys.stderr)
        sys.exit(1)

    scholar_data = case_dir / args.scholar_data if args.scholar_data else case_dir / "scholar_data.json"
    output = args.output or str(case_dir / "reports" / "missing_report.md")
    Path(output).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, str(reporter_script),
        "--case-dir", str(case_dir),
        "--output", output,
    ]
    print(f"[INFO] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=_get_script_env())
    if result.returncode == 0:
        print(f"\n[OK] 缺失信息报告已生成: {output}")
    sys.exit(result.returncode)


def cmd_review_aggregate(args):
    logger = get_logger("investigate")
    agg_script = Path(__file__).parent / "analysis" / "review_aggregator.py"
    if not agg_script.exists():
        agg_script = Path("scripts/analysis/review_aggregator.py")
    if not agg_script.exists():
        print("[ERROR] analysis/review_aggregator.py not found.", file=sys.stderr)
        sys.exit(1)

    cmd = [
        sys.executable, str(agg_script),
        "--output", args.output,
    ]
    if args.domestic:
        cmd.extend(["--domestic", args.domestic])
    if args.xiaohongshu:
        cmd.extend(["--xiaohongshu", args.xiaohongshu])
    if args.ratemyprofessors:
        cmd.extend(["--ratemyprofessors", args.ratemyprofessors])
    print(f"[INFO] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=_get_script_env())
    sys.exit(result.returncode)


def cmd_cross_border_merge(args):
    logger = get_logger("investigate")
    merge_script = Path(__file__).parent / "cross_border" / "merger.py"
    if not merge_script.exists():
        merge_script = Path("scripts/cross_border/merger.py")
    if not merge_script.exists():
        print("[ERROR] cross_border/merger.py not found.", file=sys.stderr)
        sys.exit(1)

    cmd = [
        sys.executable, str(merge_script),
        "--domestic", args.domestic,
        "--international", args.international,
        "--output", args.output,
    ]
    print(f"[INFO] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=_get_script_env())
    sys.exit(result.returncode)


def cmd_orchestrate(args):
    case_dir = get_case_dir(args)
    from agents.orchestrator import Orchestrator
    orch = Orchestrator(case_dir, mode=args.mode)
    orch.register_agents()

    if args.agents != "all":
        enabled = set(a.strip() for a in args.agents.split(","))
        orch.agents = {k: v for k, v in orch.agents.items() if k in enabled}

    orch.max_rounds = args.max_rounds

    print(f"\n{'='*60}")
    print(f"多Agent协作调查模式 (v3.2)")
    print(f"案件: {case_dir.name}")
    print(f"模式: {args.mode}")
    print(f"Agent: {', '.join(orch.agents.keys())}")
    print(f"{'='*60}\n")

    if args.mode == "manual":
        result = orch.run_until_human_decision()
        # If critical detected, pause and show decision request
        lao = orch.agents.get("laozhoumo")
        if lao and lao.detect_critical():
            crit = lao.detect_critical()
            print("\n⚠️ CRITICAL 信号检测到，任务流已暂停。")
            for c in crit:
                print(f"  - {c.get('agent')}: {c.get('context', {}).get('description', '...')}")
        else:
            print("\n本轮完成。运行 'investigate.py step' 查看推荐，或 'investigate.py advance' 推进。")
    else:
        result = orch.run_full_investigation()
        print("\n调查完成或达到最大轮次。")

    orch.cleanup()


def cmd_watermark(args):
    case_dir = get_case_dir(args)
    logger = get_logger("investigate", case_dir=case_dir)
    import watermark as wm

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("Input file not found: %s", input_path)
        sys.exit(1)

    if args.extract:
        text = input_path.read_text(encoding="utf-8")
        payload = wm.decode_watermark(text)
        if payload:
            try:
                data = json.loads(payload)
                print(f"Case ID:      {data.get('c', 'N/A')}")
                print(f"Client:       {data.get('cl', 'N/A')}")
                print(f"Timestamp:    {data.get('t', 'N/A')}")
            except json.JSONDecodeError:
                print(f"Raw payload: {payload}")
        else:
            print("No watermark found.")
    else:
        output_path = Path(args.output) if args.output else input_path.with_suffix("_wm.md")
        case_id = args.case_id or input_path.stem
        client = args.client or "unknown"

        text = input_path.read_text(encoding="utf-8")
        payload = wm.build_watermark_payload(case_id=case_id, client=client)
        watermark_zw = wm.encode_watermark(payload)
        watermarked = wm.embed_in_markdown(text, watermark_zw, strategy=args.strategy)
        output_path.write_text(watermarked, encoding="utf-8")
        logger.info("Watermarked report saved: %s", output_path)
        print(f"[OK] Watermarked: {output_path}")


def cmd_journal_check(args):
    script = Path(__file__).parent / "analysis" / "journal_credibility_checker.py"
    if not script.exists():
        script = Path("scripts/analysis/journal_credibility_checker.py")
    if not script.exists():
        print("[ERROR] journal_credibility_checker.py not found.", file=sys.stderr)
        sys.exit(1)
    cmd = [sys.executable, str(script)]
    if args.issn:
        cmd.extend(["--issn", args.issn])
    if args.journal_name:
        cmd.extend(["--journal-name", args.journal_name])
    if args.publisher:
        cmd.extend(["--publisher", args.publisher])
    if args.input:
        cmd.extend(["--input", str(args.input)])
    output = args.output or (get_case_dir(args) / "reports" / "journal_credibility_report.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd.extend(["--output", str(output)])
    print(f"[INFO] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=_get_script_env())
    sys.exit(result.returncode)


def cmd_citation_analysis(args):
    script = Path(__file__).parent / "network" / "citation_constellation.py"
    if not script.exists():
        script = Path("scripts/network/citation_constellation.py")
    if not script.exists():
        print("[ERROR] citation_constellation.py not found.", file=sys.stderr)
        sys.exit(1)
    cmd = [sys.executable, str(script), "--name", args.name]
    if args.institution:
        cmd.extend(["--institution", args.institution])
    if args.orcid:
        cmd.extend(["--orcid", args.orcid])
    if args.max_works:
        cmd.extend(["--max-works", str(args.max_works)])
    if args.max_citations:
        cmd.extend(["--max-citations", str(args.max_citations)])
    output = args.output or (get_case_dir(args) / "reports")
    output.mkdir(parents=True, exist_ok=True)
    cmd.extend(["--output", str(output)])
    print(f"[INFO] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=_get_script_env())
    sys.exit(result.returncode)


def cmd_source_eval(args):
    script = Path(__file__).parent / "analysis" / "source_evaluation.py"
    if not script.exists():
        script = Path("scripts/analysis/source_evaluation.py")
    if not script.exists():
        print("[ERROR] source_evaluation.py not found.", file=sys.stderr)
        sys.exit(1)
    cmd = [
        sys.executable, str(script),
        "--source-type", args.source_type,
        "--currency", str(args.currency),
        "--relevance", str(args.relevance),
        "--authority", str(args.authority),
        "--accuracy", str(args.accuracy),
        "--purpose", str(args.purpose),
    ]
    if args.title:
        cmd.extend(["--title", args.title])
    if args.url:
        cmd.extend(["--url", args.url])
    output = args.output or (get_case_dir(args) / "reports" / "source_evaluation.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd.extend(["--output", str(output)])
    print(f"[INFO] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=_get_script_env())
    sys.exit(result.returncode)


def cmd_domestic_enrich(args):
    script = Path(__file__).parent / "domestic" / "openalex_enricher.py"
    if not script.exists():
        script = Path("scripts/domestic/openalex_enricher.py")
    if not script.exists():
        print("[ERROR] openalex_enricher.py not found.", file=sys.stderr)
        sys.exit(1)
    cmd = [
        sys.executable, str(script),
        "--name", args.name,
        "--input", str(args.input),
    ]
    if args.institution:
        cmd.extend(["--institution", args.institution])
    output = args.output or args.input.with_stem(args.input.stem + "_enriched")
    cmd.extend(["--output", str(output)])
    print(f"[INFO] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=_get_script_env())
    if result.returncode == 0:
        print(f"\n[OK] Enriched data saved: {output}")
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
