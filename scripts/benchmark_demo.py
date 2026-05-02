#!/usr/bin/env python3
"""
benchmark_demo.py — 学科基准线数据库演示脚本

完整演示流程：
  1. 初始化数据库（五层表结构 + 10条预设异常规则）
  2. 从学者档案库导入46条研究者基线
  3. 按学科（department）创建学科基线（Layer 1）
  4. 批量计算所有研究者的综合异常指数（Layer 4+5）
  5. 输出 Top 异常案例、风险分布、规则触发统计
  6. 为指定案例生成详细报告

使用方法：
    python3 scripts/benchmark_demo.py

输出：
    - 控制台报告
    - data/benchmark_results.json（批量结果导出）
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from benchmark_engine import BenchmarkEngine

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "benchmark.db")
RESULT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "benchmark_results.json")


def create_discipline_baselines(engine: BenchmarkEngine) -> int:
    """
    从已导入的研究者数据中按 department 分组创建学科基线。
    如果分组后样本不足，则创建全局基线（所有数据合并）。
    返回创建的基线数量。
    """
    cursor = engine.conn.cursor()
    cursor.execute(
        "SELECT discipline_id, COUNT(*) FROM researcher_baseline GROUP BY discipline_id"
    )
    disciplines = [(r[0], r[1]) for r in cursor.fetchall()]

    created = 0
    for discipline_id, count in disciplines:
        if not discipline_id or count < 2:
            continue

        # 收集该学科下所有可用的数值字段
        metrics = {
            "avg_papers_per_year": [],
            "h_index": [],
            "median_citations_per_paper": [],
            "coauthor_count": [],
            "cross_discipline_count": [],
        }

        for metric in metrics:
            cursor.execute(
                f"SELECT {metric} FROM researcher_baseline WHERE discipline_id = ? AND {metric} IS NOT NULL AND {metric} > 0",
                (discipline_id,),
            )
            vals = [float(r[0]) for r in cursor.fetchall() if r[0] is not None]
            metrics[metric] = vals

        # 只有当至少有一个指标有2个以上样本时才创建基线
        total_vals = sum(len(v) for v in metrics.values())
        if total_vals < 2:
            continue

        engine.create_discipline_baseline(
            discipline_id=discipline_id,
            discipline_name=discipline_id,
            researcher_values=metrics,
            region="CN",
        )
        created += 1
        print(f"  Created baseline for '{discipline_id}' (n={count}, metrics={total_vals})")

    # 如果按学科创建的基线少于2个，补充全局基线
    if created < 2:
        print("  学科基线不足，创建全局基线...")
        metrics = {
            "avg_papers_per_year": [],
            "h_index": [],
            "median_citations_per_paper": [],
            "coauthor_count": [],
            "cross_discipline_count": [],
        }
        for metric in metrics:
            cursor.execute(
                f"SELECT {metric} FROM researcher_baseline WHERE {metric} IS NOT NULL AND {metric} > 0"
            )
            vals = [float(r[0]) for r in cursor.fetchall() if r[0] is not None]
            metrics[metric] = vals

        total_vals = sum(len(v) for v in metrics.values())
        if total_vals >= 2:
            engine.create_discipline_baseline(
                discipline_id="GLOBAL",
                discipline_name="全局基线",
                researcher_values=metrics,
                region="GLOBAL",
            )
            created += 1
            print(f"  Created global baseline (metrics={total_vals})")

    return created


def print_summary(engine: BenchmarkEngine, results: list) -> None:
    """打印批量计算结果摘要"""
    print("\n" + "=" * 60)
    print("学科基准线数据库 — 批量计算结果摘要")
    print("=" * 60)

    # 总体统计
    total = len(results)
    if total == 0:
        print("无计算结果。可能原因：基线数据不足或所有指标缺失。")
        return

    risk_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for r in results:
        risk_counts[r.risk_level] = risk_counts.get(r.risk_level, 0) + 1

    confirmed = [r for r in results if r.active_feature_count > 0]

    print(f"\n总计算案例数：{total}")
    print(f"触发至少1条规则：{len(confirmed)} ({len(confirmed)/total*100:.1f}%)")
    print(f"风险分布：")
    for level in ["low", "medium", "high", "critical"]:
        print(f"  {level:10s}: {risk_counts[level]} ({risk_counts[level]/total*100:.1f}%)")

    # Top N 异常
    print(f"\n【Top 10 异常案例】")
    top = sorted(results, key=lambda x: x.composite_score, reverse=True)[:10]
    for i, r in enumerate(top, 1):
        badge = "🚨" if r.risk_level in ("high", "critical") else "⚠️" if r.risk_level == "medium" else "  "
        print(f"  {i:2d}. {badge} {r.name:20s} score={r.composite_score:7.2f} ({r.risk_level:8s}) rules={r.active_feature_count}")

    # 确认不端案例中的最高分
    print(f"\n【确认不端案例异常指数】")
    misconduct = [r for r in results if r.case_id.startswith("CASE_")]
    # 尝试从数据库中查询状态
    cursor = engine.conn.cursor()
    cursor.execute(
        "SELECT researcher_id, name, investigation_status FROM researcher_baseline WHERE is_confirmed_misconduct = 1"
    )
    misconduct_ids = {r[0]: (r[1], r[2]) for r in cursor.fetchall()}
    misconduct_results = [r for r in results if r.case_id in misconduct_ids]
    for r in sorted(misconduct_results, key=lambda x: x.composite_score, reverse=True)[:10]:
        name, status = misconduct_ids[r.case_id]
        print(f"  {name:20s} score={r.composite_score:7.2f} ({r.risk_level:8s}) rules={r.active_feature_count}")

    # 规则触发统计
    print(f"\n【规则触发统计】")
    stats = engine.get_rule_stats()
    for s in stats:
        if s["trigger_count"] > 0:
            print(f"  {s['rule_id']:5s} {s['rule_name_zh'] or s['rule_name']:20s}: 触发{s['trigger_count']}次, 平均概率{s['avg_probability']*100:.1f}%")

    print("=" * 60)


def main():
    print("学科基准线数据库 — 演示脚本")
    print("-" * 60)

    # 1. 初始化
    engine = BenchmarkEngine(DB_PATH)
    print(f"\n[1/5] 初始化数据库: {DB_PATH}")
    engine.init_schema()
    # 优先从CSV导入规则（万能服务器提供的更新版），如不存在则使用默认规则
    rules_csv = os.path.join(os.path.dirname(__file__), "..", "data", "anomaly_rules.csv")
    if os.path.exists(rules_csv):
        engine.import_anomaly_rules(rules_csv)
    else:
        engine.seed_default_rules()

    # 2. 导入档案库
    print(f"\n[2/5] 从学者档案库导入研究者基线...")
    count = engine.import_from_profile_db()
    if count == 0:
        print("导入失败，请检查 CSV 文件路径和格式。")
        return

    # 3. 导入学科基线（从万能服务器提供的大样本CSV）
    print(f"\n[3/5] 导入学科基线...")
    baseline_csv = os.path.join(os.path.dirname(__file__), "..", "data", "discipline_benchmarks.csv")
    if os.path.exists(baseline_csv):
        baseline_count = engine.import_discipline_baselines(baseline_csv)
    else:
        print(f"  大样本基线CSV未找到: {baseline_csv}，尝试从已有数据计算...")
        baseline_count = create_discipline_baselines(engine)
    print(f"导入了 {baseline_count} 个学科基线。")

    # 4. 批量计算
    print(f"\n[4/5] 批量计算异常指数（mode=individual）...")
    results = engine.batch_calculate(mode="individual")
    print(f"计算完成：{len(results)} 条结果")

    # 5. 输出摘要
    print(f"\n[5/5] 输出结果摘要...")
    print_summary(engine, results)

    # 导出 JSON
    if results:
        engine.export_results_to_json(results, RESULT_PATH)

    # 为最高分案例生成详细报告
    if results:
        top_case = max(results, key=lambda x: x.composite_score)
        report_path = os.path.join(os.path.dirname(__file__), "..", "data", f"report_{top_case.case_id}.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(engine.generate_report(top_case))
        print(f"\n详细报告已保存: {report_path}")

    engine.close()
    print("\n演示完成。")


if __name__ == "__main__":
    main()
