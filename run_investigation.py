#!/usr/bin/env python3
"""
学术侦探 — 一键调查入口
========================

用法：
    python run_investigation.py --name "导师姓名" --school "学校名称" [选项]

示例：
    python run_investigation.py --name "贾冀川" --school "南京师范大学"
    python run_investigation.py --name "贾冀川" --school "南京师范大学" --depth deep
    python run_investigation.py --list-tools

说明：
    本脚本是学术侦探系统的统一入口。它会自动定位所有预装脚本，
    按七步调查框架依次执行，无需手动调用各个工具。

    所有脚本预装在 archive/flat_export_redundant_20260501/ 目录下。
    本入口脚本负责路径映射和调用顺序，LLM 或其他用户只需要知道这一个命令。

选项：
    --name        导师姓名（必填）
    --school      所在学校（必填）
    --depth       调查深度：quick（快速筛查）/ standard（标准）/ deep（深度）
                  默认：standard
    --output      输出目录（可选，默认 ./output/导师名_学校/）
    --list-tools  列出所有可用工具
    --help        显示帮助信息
"""

import sys
import os
import argparse
import subprocess
from pathlib import Path

# 预装脚本根目录
SCRIPTS_DIR = Path(__file__).parent / "archive" / "flat_export_redundant_20260501"

# 所有可用工具及其路径
TOOLS = {
    # 核心
    "text_profiler": SCRIPTS_DIR / "analysis_text_profiler.py",
    "stylometry_profiler": SCRIPTS_DIR / "analysis_stylometry_profiler.py",
    "paper_quality_rubric": SCRIPTS_DIR / "analysis_paper_quality_rubric.py",
    "hybrid_scorer": SCRIPTS_DIR / "analysis_hybrid_scorer.py",
    "citation_profiler": SCRIPTS_DIR / "analysis_citation_profiler.py",
    "common_heuristics": SCRIPTS_DIR / "analysis_common_heuristics.py",
    
    # 数据
    "data_importer": SCRIPTS_DIR / "domestic_data_importer.py",
    "data_validator": SCRIPTS_DIR / "domestic_data_validator.py",
    "scholar_data_builder": SCRIPTS_DIR / "domestic_scholar_data_builder.py",
    
    # 网络
    "network_visualizer": SCRIPTS_DIR / "network_network_visualizer.py",
    "timeline_weaver": SCRIPTS_DIR / "network_timeline_weaver.py",
    
    # 报告
    "report_prompt_optimizer": SCRIPTS_DIR / "report_report_prompt_optimizer.py",
    
    # 基准线引擎
    "benchmark_engine": SCRIPTS_DIR / "benchmark_engine.py",
    "profile_matcher": SCRIPTS_DIR / "scholar_profile_matcher_v2.py",
}


def list_tools():
    """列出所有可用工具及其状态"""
    print("=" * 60)
    print("学术侦探 — 可用工具清单")
    print("=" * 60)
    for name, path in sorted(TOOLS.items()):
        status = "✅" if path.exists() else "❌ 未找到"
        print(f"  {status} {name:25s}  {path.name}")
    print("=" * 60)


def run_tool(tool_name: str, args: list = None) -> bool:
    """运行指定工具，返回成功/失败"""
    path = TOOLS.get(tool_name)
    if not path or not path.exists():
        print(f"[错误] 工具 '{tool_name}' 未找到: {path}")
        return False
    
    cmd = [sys.executable, str(path)]
    if args:
        cmd.extend(args)
    
    print(f"\n{'='*60}")
    print(f"[运行] {tool_name}")
    print(f"[命令] {' '.join(cmd)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(f"[stderr] {result.stderr[:2000]}", file=sys.stderr)
        if result.returncode != 0:
            print(f"[警告] {tool_name} 返回非零退出码: {result.returncode}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f"[超时] {tool_name} 运行超过600秒")
        return False
    except Exception as e:
        print(f"[错误] 运行 {tool_name} 时发生异常: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="学术侦探 — 一键调查入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python run_investigation.py --name "贾冀川" --school "南京师范大学"
  python run_investigation.py --name "贾冀川" --school "南京师范大学" --depth deep
  python run_investigation.py --list-tools
        """,
    )
    parser.add_argument("--name", help="导师姓名")
    parser.add_argument("--school", help="所在学校")
    parser.add_argument("--depth", choices=["quick", "standard", "deep"], default="standard",
                        help="调查深度（默认: standard）")
    parser.add_argument("--output", help="输出目录（可选）")
    parser.add_argument("--list-tools", action="store_true", help="列出所有可用工具")

    args = parser.parse_args()

    # 列出工具
    if args.list_tools:
        list_tools()
        return

    # 检查必填参数
    if not args.name or not args.school:
        parser.print_help()
        print("\n[错误] --name 和 --school 为必填参数")
        sys.exit(1)

    # 设置输出目录
    output_dir = args.output or f"./output/{args.name}_{args.school}"
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(f"{output_dir}/data", exist_ok=True)
    os.makedirs(f"{output_dir}/pdfs", exist_ok=True)
    os.makedirs(f"{output_dir}/reports", exist_ok=True)

    print("=" * 60)
    print(f"学术侦探 — 调查启动")
    print(f"导师: {args.name}")
    print(f"学校: {args.school}")
    print(f"深度: {args.depth}")
    print(f"输出: {output_dir}")
    print("=" * 60)

    # ================================================================
    # 七步调查框架
    # ================================================================

    # Step 1: 基本信息建立（由 LLM + 人工完成）
    print(f"\n📋 Step 1/7: 基本信息建立")
    print("  需人工收集：官方网页、CV、知网搜索结果")
    print("  输出：结构化身份信息JSON")

    # Step 2: 产出数量核实
    print(f"\n📋 Step 2/7: 产出数量核实")
    print("  需人工从知网/万方/WoS导出数据")
    print("  可用脚本：data_importer.py（导入导出数据）")

    # Step 3: 质量评估
    print(f"\n📋 Step 3/7: 论文质量评估")
    print(f"  可用脚本：")
    print(f"    - text_profiler.py（文本特征分析）")
    print(f"    - stylometry_profiler.py（文风计量）")
    print(f"    - paper_quality_rubric.py（六维评分）")

    # Step 4: 关系网络分析
    print(f"\n📋 Step 4/7: 关系网络分析")
    print(f"  可用脚本：")
    print(f"    - network_visualizer.py（交互式关系图）")
    print(f"    - timeline_weaver.py（时间线编织）")

    # Step 5: 异常检测（含基准线比对）
    print(f"\n📋 Step 5/7: 异常检测与基准线比对")
    print(f"  可用脚本：")
    print(f"    - data_validator.py（数据逻辑验证）")
    print(f"    - common_heuristics.py（通用异常规则）")
    print(f"    - benchmark_engine.py（学科基准线偏差计算）")
    if SCRIPTS_DIR.joinpath("scholar_profile_matcher_v2.py").exists():
        print(f"    - scholar_profile_matcher_v2.py（与已知案例的模式比对）")

    # Step 6: 多源交叉验证
    print(f"\n📋 Step 6/7: 多源交叉验证")
    print("  需人工：至少2个独立来源确认每个结论")
    print("  可用脚本：scholar_data_builder.py（统一数据构建）")

    # Step 7: 报告生成
    print(f"\n📋 Step 7/7: 报告生成")
    print(f"  可用脚本：")
    print(f"    - report_prompt_optimizer.py（报告提示词优化）")
    print(f"  模板：report_report_template.md")

    # ================================================================
    # 总结
    # ================================================================
    print("\n" + "=" * 60)
    print("调查框架已输出。具体执行步骤：")
    print(f"  1. 人工收集数据（知网导出、官网截图、PDF下载）→ 放入 {output_dir}/data/")
    print(f"  2. 按需运行上述脚本 → 输出到 {output_dir}/data/")
    print(f"  3. 运行 scholar_data_builder.py 合并数据")
    print(f"  4. 运行 data_validator.py 验证")
    print(f"  5. 生成最终报告 → 保存到 {output_dir}/reports/")
    print("=" * 60)


if __name__ == "__main__":
    main()
