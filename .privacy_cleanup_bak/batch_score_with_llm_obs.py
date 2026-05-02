#!/usr/bin/env python3
"""
batch_score_with_llm_obs.py

Batch-run paper_quality_rubric with LLM-generated observations.
Compares results against the no-obs baseline.
"""

import os
import sys
import json
import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.resolve()
RUBRIC = SCRIPTS_DIR / "paper_quality_rubric.py"

INPUT_FOLDER = Path("/Users/xiaoy/Downloads/调查名单/汤铎铎/quality_scores")
OUTPUT_FOLDER = Path("/Users/xiaoy/Downloads/调查名单/汤铎铎/quality_scores_llm")

# LLM-crafted observations for each paper (key = filename stem)
LLM_OBS = {
    "2010年宏观经济形势回顾与2011年展望_中国社科院经济所宏观分析课题组": {
        "originality_score": 55,
        "data_reproducibility": "medium",
        "conclusion_robustness": "medium",
        "validity_concerns": ["课题组署名作品，个人原创性难以评估"],
    },
    "“新三期叠加”下中国经济的新发展和新变化_汤铎铎": {
        "originality_score": 72,
        "data_reproducibility": "medium",
        "conclusion_robustness": "medium",
    },
    "两个经典宏观经济关系在中国的检验_汤铎铎": {
        "originality_score": 70,
        "data_reproducibility": "medium",
        "statistical_rigor": "high",
        "conclusion_robustness": "medium",
        "validity_concerns": ["期刊论文格式无独立参考文献章节，脚本识别为0引用，实际应有引注"],
    },
    "中国主权资产负债表及其风险评估(上)_李扬": {
        "originality_score": 75,
        "data_reproducibility": "high",
        "statistical_rigor": "high",
        "conclusion_robustness": "high",
        "validity_concerns": ["合著论文，汤铎铎位列第四作者，个人核心贡献有限"],
    },
    "中国主权资产负债表及其风险评估(下)_李扬": {
        "originality_score": 75,
        "data_reproducibility": "high",
        "statistical_rigor": "high",
        "conclusion_robustness": "high",
        "validity_concerns": ["合著论文，汤铎铎位列第四作者，个人核心贡献有限"],
    },
    "中国宏观经济治理现代化：经验、挑战和任务_汤铎铎": {
        "originality_score": 75,
        "data_reproducibility": "medium",
        "conclusion_robustness": "medium-high",
    },
    "中国的债务风险在可控范围之内_国家金融与发展实验室课题组...__曾刚__蔡真__黎紫莹": {
        "originality_score": 55,
        "data_reproducibility": "medium",
        "conclusion_robustness": "medium",
        "validity_concerns": ["课题组集体作品，汤铎铎仅为成员之一，个人原创性难以评估"],
    },
    "中国经济_硬着陆还是软着陆__汤铎铎": {
        "originality_score": 58,
        "data_reproducibility": "low",
        "conclusion_robustness": "medium",
    },
    "中国经济周期波动的经验研究：描述性事实和特征事实（1949～2006）_汤铎铎": {
        "originality_score": 85,
        "data_reproducibility": "medium",
        "statistical_rigor": "high",
        "conclusion_robustness": "high",
    },
    "从增长与通胀的多重组合看我国的滞胀风险_张晓晶": {
        "originality_score": 68,
        "data_reproducibility": "medium",
        "conclusion_robustness": "medium",
        "validity_concerns": ["合著论文，张晓晶为第一作者，汤铎铎贡献占比需审慎评估"],
    },
    "从西斯蒙第到普雷斯科特——经济周期理论200年_汤铎铎": {
        "originality_score": 65,
        "data_reproducibility": "na",
        "statistical_rigor": "na",
        "conclusion_robustness": "high",
    },
    "全球复苏、杠杆背离与金融风险——2018年中国宏观经济报告_汤铎铎": {
        "originality_score": 72,
        "data_reproducibility": "medium",
        "conclusion_robustness": "medium-high",
    },
    "全球失衡、金融危机与中国经济的复苏_中国经济增长与宏观稳定课题组": {
        "originality_score": 58,
        "data_reproducibility": "medium",
        "conclusion_robustness": "medium",
        "validity_concerns": ["课题组署名作品，个人原创性难以评估"],
    },
    "全球经济大变局、中国潜在增长率与后疫情时期高质量发展_汤铎铎": {
        "originality_score": 75,
        "data_reproducibility": "medium",
        "conclusion_robustness": "medium-high",
    },
    "反思潜在产出——2020年中国宏观经济展望_汤铎铎": {
        "originality_score": 72,
        "data_reproducibility": "medium",
        "conclusion_robustness": "medium-high",
    },
    "外部冲击频发期的宏观经济政策空间_中国宏观经济形势分析与展望课题组__": {
        "originality_score": 58,
        "data_reproducibility": "medium",
        "conclusion_robustness": "medium",
        "validity_concerns": ["课题组署名作品，个人原创性难以评估"],
    },
    "外部冲击频发期的宏观经济政策空间_汤铎铎": {
        "originality_score": 60,
        "data_reproducibility": "low",
        "conclusion_robustness": "medium",
    },
    "大国经济崛起与双循环：国际经验_汤铎铎": {
        "originality_score": 72,
        "data_reproducibility": "medium",
        "conclusion_robustness": "medium-high",
    },
    "宏观调控目标的“十一五”分析与“十二五”展望_中国社会科学院经济研究所宏观经济调控课题组": {
        "originality_score": 58,
        "data_reproducibility": "medium",
        "conclusion_robustness": "medium",
        "validity_concerns": ["课题组署名作品，个人原创性难以评估"],
    },
    "实体经济低波动与金融去杠杆——2017年中国宏观经济中期报告_汤铎铎": {
        "originality_score": 72,
        "data_reproducibility": "medium",
        "conclusion_robustness": "medium-high",
    },
    "居民财富、金融监管与贸易摩擦——2018年中国宏观经济中期报告_李成": {
        "originality_score": 70,
        "data_reproducibility": "medium",
        "conclusion_robustness": "medium-high",
        "validity_concerns": ["合著论文，李成第一作者，汤铎铎为课题组负责人，个人核心贡献占比需审慎评估"],
    },
    "山寨文化纵横谈_白烨": {
        "originality_score": 45,
        "data_reproducibility": "na",
        "conclusion_robustness": "low",
        "validity_concerns": ["学术研讨会对话整理稿，非系统研究，学科属性与调查对象主领域不符"],
    },
    "我国宽松的货币政策是否需要微调_汤铎铎": {
        "originality_score": 55,
        "data_reproducibility": "low",
        "conclusion_robustness": "medium",
    },
    "政策退出效应显现__谨防经济减速过快_中国社科院经济所宏观分析课题组": {
        "originality_score": 55,
        "data_reproducibility": "medium",
        "conclusion_robustness": "medium",
        "validity_concerns": ["课题组署名作品，个人原创性难以评估"],
    },
    "新开放经济宏观经济学_理论和问题_汤铎铎": {
        "originality_score": 68,
        "data_reproducibility": "na",
        "statistical_rigor": "na",
        "conclusion_robustness": "high",
    },
    "沃尔特·白芝浩_19世纪伦巴第街的思想者_汤铎铎": {
        "originality_score": 58,
        "data_reproducibility": "na",
        "conclusion_robustness": "medium",
    },
    "紧缩银根出手偏慢__通胀形势总体可控_汤铎铎": {
        "originality_score": 55,
        "data_reproducibility": "low",
        "conclusion_robustness": "medium",
    },
    "经济政策正常化与未来增长情景_中国社科院经济所宏观分析课题组": {
        "originality_score": 55,
        "data_reproducibility": "medium",
        "conclusion_robustness": "medium",
        "validity_concerns": ["课题组署名作品，个人原创性难以评估"],
    },
    "金融去杠杆、竞争中性与政策转型——2019年中国宏观经济展望_汤铎铎": {
        "originality_score": 72,
        "data_reproducibility": "medium",
        "conclusion_robustness": "medium-high",
    },
    "长期停滞还是金融周期——中国宏观经济形势分析与展望_汤铎铎": {
        "originality_score": 72,
        "data_reproducibility": "medium",
        "conclusion_robustness": "medium-high",
    },
    "高质量发展背景下的现代化经济体系建设_一个逻辑框架_高培勇": {
        "originality_score": 70,
        "data_reproducibility": "medium",
        "conclusion_robustness": "high",
        "validity_concerns": ["合著论文，汤铎铎为第五作者且为课题组成员，个人核心贡献有限"],
    },
}


def run_rubric(profile_path: Path, obs_path: Path, output_path: Path) -> tuple:
    cmd = [
        sys.executable, str(RUBRIC),
        "--profile", str(profile_path),
        "--observations", str(obs_path),
        "--output", str(output_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return proc.returncode, proc.stdout, proc.stderr


def main():
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    profile_files = sorted(INPUT_FOLDER.glob("*_profile.json"))
    papers = [f for f in profile_files if "(1)" not in f.stem]

    # Filter out empty-source files already excluded in first run
    results = []
    for paper in papers:
        stem = paper.stem.replace("_profile", "")
        obs = LLM_OBS.get(stem, {})
        obs_path = OUTPUT_FOLDER / f"{stem}_obs.json"
        out_path = OUTPUT_FOLDER / f"{stem}_quality.json"
        base_path = INPUT_FOLDER / f"{stem}_quality.json"

        with open(obs_path, "w", encoding="utf-8") as f:
            json.dump(obs, f, ensure_ascii=False, indent=2)

        rc, out, err = run_rubric(paper, obs_path, out_path)
        if rc != 0:
            print(f"[ERROR] {stem}: {err}")
            continue

        with open(out_path, "r", encoding="utf-8") as f:
            llm_report = json.load(f)
        with open(base_path, "r", encoding="utf-8") as f:
            base_report = json.load(f)

        results.append({
            "stem": stem,
            "base_score": base_report["overall_score"],
            "base_rating": base_report["overall_rating"],
            "llm_score": llm_report["overall_score"],
            "llm_rating": llm_report["overall_rating"],
            "delta": round(llm_report["overall_score"] - base_report["overall_score"], 1),
            "llm_verdict": llm_report["verdict"],
            "red_flags": len(llm_report["red_flags"]),
        })
        print(f"[{len(results)}/{len(papers)}] {stem[:40]:<40}  Base {base_report['overall_rating']}({base_report['overall_score']}) -> LLM {llm_report['overall_rating']}({llm_report['overall_score']})  Δ={round(llm_report['overall_score'] - base_report['overall_score'], 1):+.1f}")

    # Summary stats
    deltas = [r["delta"] for r in results]
    avg_base = sum(r["base_score"] for r in results) / len(results)
    avg_llm = sum(r["llm_score"] for r in results) / len(results)

    print("\n" + "=" * 80)
    print(f"对比完成: {len(results)} 篇")
    print(f"纯脚本平均分: {avg_base:.1f}  |  LLM介入平均分: {avg_llm:.1f}  |  平均变化: {sum(deltas)/len(deltas):+.1f}")
    print(f"最大上调: +{max(deltas):.1f}  |  最大下调: {min(deltas):.1f}")

    # Save comparison JSON
    summary_path = OUTPUT_FOLDER / "_llm_comparison.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "avg_base": round(avg_base, 1),
            "avg_llm": round(avg_llm, 1),
            "avg_delta": round(sum(deltas)/len(deltas), 1),
            "max_up": max(deltas),
            "max_down": min(deltas),
            "details": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"对比报告已保存: {summary_path}")

    # Print top changes
    print("\n评分变化最大的10篇:")
    sorted_by_delta = sorted(results, key=lambda x: abs(x["delta"]), reverse=True)
    print(f"{'#':>3} {'Base':>5} {'LLM':>5} {'Δ':>6}  论文标题")
    for r in sorted_by_delta[:10]:
        print(f"  {sorted_by_delta.index(r)+1:>2} {r['base_score']:>5.1f} {r['llm_score']:>5.1f} {r['delta']:>+6.1f}  {r['stem'][:55]}")

    # Distribution table
    print("\n评级变化分布:")
    changes = {}
    for r in results:
        k = f"{r['base_rating']} -> {r['llm_rating']}"
        changes[k] = changes.get(k, 0) + 1
    for k, v in sorted(changes.items(), key=lambda x: -x[1]):
        print(f"  {k:>10} : {v:>2} 篇")


if __name__ == "__main__":
    main()
