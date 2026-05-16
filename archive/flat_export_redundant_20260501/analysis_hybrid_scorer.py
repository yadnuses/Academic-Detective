#!/usr/bin/env python3
"""
hybrid_scorer.py

Hybrid script+LLM scoring pipeline for academic paper quality assessment.

Workflow:
  1. PREPARE: scripts extract profiles and text excerpts -> llm_review_pack.json
  2. LLM REVIEW: human/LLM reads the pack and writes llm_observations_batch.json
  3. APPLY: script runs rubric with LLM observations and outputs ranked table

Usage:
  python hybrid_scorer.py prepare --input-folder ./papers --output-dir ./scores
  python hybrid_scorer.py apply --input-folder ./papers --output-dir ./scores
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List

SCRIPTS_DIR = Path(__file__).parent.resolve()
TEXT_PROFILER = SCRIPTS_DIR / "text_profiler.py"
RUBRIC = SCRIPTS_DIR / "paper_quality_rubric.py"


def run_text_profiler(input_path: Path, output_path: Path) -> bool:
    rc = subprocess.run(
        [sys.executable, str(TEXT_PROFILER), "--input", str(input_path), "--output", str(output_path)],
        capture_output=True,
    ).returncode
    return rc == 0


def run_rubric(profile_path: Path, obs_path: Path, output_path: Path) -> bool:
    rc = subprocess.run(
        [sys.executable, str(RUBRIC), "--profile", str(profile_path), "--observations", str(obs_path), "--output", str(output_path)],
        capture_output=True,
    ).returncode
    return rc == 0


def extract_excerpt(file_path: Path, max_chars: int = 3000) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read(max_chars * 3)
        # Simple truncation to nearest sentence boundary
        if len(text) > max_chars:
            cut = text.rfind("。", max_chars // 2, max_chars)
            if cut == -1:
                cut = max_chars
            text = text[:cut] + "。\n[... 节选截断 ...]"
        return text
    except Exception as e:
        return f"[Error reading file: {e}]"


def cmd_prepare(args):
    input_folder = Path(args.input_folder)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    papers = sorted([
        f for ext in ("*.md", "*.txt", "*.pdf")
        for f in input_folder.glob(ext)
        if f.stat().st_size > 0 and "(1)" not in f.stem
    ])

    review_items: List[dict] = []
    for paper in papers:
        profile_path = output_dir / f"{paper.stem}_profile.json"
        if not profile_path.exists() or args.force:
            print(f"[PROFILER] {paper.name}")
            ok = run_text_profiler(paper, profile_path)
            if not ok:
                print(f"  [SKIP] profiler failed")
                continue

        with open(profile_path, "r", encoding="utf-8") as f:
            profile = json.load(f)

        chars = profile.get("basic_stats", {}).get("total_characters", 0)
        refs = profile.get("references", {}).get("count", 0)
        chaps = len(profile.get("chapter_structure", []))
        markers = profile.get("originality_markers", {}).get("total", 0)
        density = round((markers / chars * 1000), 2) if chars else 0.0

        excerpt = extract_excerpt(paper, max_chars=args.excerpt)

        review_items.append({
            "file_name": paper.name,
            "file_path": str(paper),
            "profile_path": str(profile_path),
            "basic_stats": {
                "total_characters": chars,
                "references": refs,
                "chapters": chaps,
                "originality_marker_density": density,
            },
            "text_excerpt": excerpt,
        })

    pack_path = output_dir / "llm_review_pack.json"
    with open(pack_path, "w", encoding="utf-8") as f:
        json.dump(review_items, f, ensure_ascii=False, indent=2)

    # Also emit a readable markdown summary for quick LLM scanning
    md_path = output_dir / "llm_review_request.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# LLM 深度评分请求书\n\n")
        f.write("请基于每篇论文的基础统计信息和文本节选，输出对应的 observations JSON。\n\n")
        f.write("## 期望输出格式\n\n")
        f.write("请生成一个 JSON 对象，键为 `file_name`，值为 observations 对象。\n\n")
        f.write("```json\n")
        f.write(json.dumps({
            "示例文件名.md": {
                "originality_score": 70,
                "validity_concerns": [],
                "data_reproducibility": "medium",
                "statistical_rigor": "medium",
                "conclusion_robustness": "medium",
                "structure_score": 70,
                "structure_quality": "medium",
                "has_fatal_flaw": False,
                "ethical_flags": [],
                "paper_type": "journal_article",
                "authorship_role": "solo",
                "llm_reasoning": "简要说明评分依据"
            }
        }, ensure_ascii=False, indent=2))
        f.write("\n```\n\n")
        f.write("## 字段说明\n\n")
        f.write("- `originality_score`: 0-100，原创性与重要性整体评分\n")
        f.write("- `data_reproducibility`: high / medium / low / unknown / na\n")
        f.write("- `statistical_rigor`: high / medium / low / na\n")
        f.write("- `conclusion_robustness`: high / medium / low\n")
        f.write("- `structure_score`: 0-100，可选直接覆盖结构维度得分\n")
        f.write("- `structure_quality`: high / medium / low，在缺少直接覆盖时微调结构分\n")
        f.write("- `paper_type`: dissertation / monograph / journal_article / review / report / commentary / dialogue\n")
        f.write("- `authorship_role`: solo / first_author / coauthor / group_member\n")
        f.write("- `validity_concerns`: 字符串列表，如存在致命缺陷则设 `has_fatal_flaw: true`\n\n")
        f.write("---\n\n")

        for item in review_items:
            f.write(f"## {item['file_name']}\n\n")
            bs = item["basic_stats"]
            f.write(f"- **字符数**: {bs['total_characters']}  |  **参考文献**: {bs['references']}  |  **章节数**: {bs['chapters']}  |  **原创标记密度**: {bs['originality_marker_density']}/1000字\n\n")
            f.write("### 文本节选\n\n")
            f.write(item["text_excerpt"])
            f.write("\n\n---\n\n")

    print(f"[DONE] Prepared {len(review_items)} papers.")
    print(f"  JSON pack: {pack_path}")
    print(f"  Markdown : {md_path}")
    print(f"\nNext step:请LLM审阅后生成 {output_dir}/llm_observations_batch.json")


def cmd_apply(args):
    input_folder = Path(args.input_folder)
    output_dir = Path(args.output_dir)
    pack_path = output_dir / "llm_review_pack.json"
    obs_path = output_dir / "llm_observations_batch.json"

    if not pack_path.exists():
        print(f"[ERROR] Pack not found: {pack_path}. Run 'prepare' first.")
        sys.exit(1)
    if not obs_path.exists():
        print(f"[ERROR] Observations not found: {obs_path}. Please generate it after LLM review.")
        sys.exit(1)

    with open(pack_path, "r", encoding="utf-8") as f:
        pack = json.load(f)
    with open(obs_path, "r", encoding="utf-8") as f:
        obs_batch = json.load(f)

    results = []
    for item in pack:
        fname = item["file_name"]
        stem = Path(fname).stem
        profile_path = output_dir / f"{stem}_profile.json"
        base_quality_path = output_dir / f"{stem}_quality.json"
        llm_quality_path = output_dir / f"{stem}_quality_llm.json"
        single_obs_path = output_dir / f"{stem}_obs_llm.json"

        obs = obs_batch.get(fname, {})
        with open(single_obs_path, "w", encoding="utf-8") as f:
            json.dump(obs, f, ensure_ascii=False, indent=2)

        ok = run_rubric(profile_path, single_obs_path, llm_quality_path)
        if not ok:
            print(f"[ERROR] Rubric failed for {fname}")
            continue

        with open(llm_quality_path, "r", encoding="utf-8") as f:
            llm_report = json.load(f)

        base_score = base_rating = None
        if base_quality_path.exists():
            with open(base_quality_path, "r", encoding="utf-8") as f:
                base_report = json.load(f)
            base_score = base_report.get("overall_score")
            base_rating = base_report.get("overall_rating")

        dims = llm_report.get("dimensions", {})
        results.append({
            "file_name": fname,
            "llm_score": llm_report["overall_score"],
            "llm_rating": llm_report["overall_rating"],
            "llm_verdict": llm_report["verdict"],
            "base_score": base_score,
            "base_rating": base_rating,
            "delta": round(llm_report["overall_score"] - base_score, 1) if base_score is not None else None,
            "red_flags": llm_report.get("red_flags", []),
            "chars": item["basic_stats"]["total_characters"],
            "refs": item["basic_stats"]["references"],
            "dimensions": dims,
            "llm_reasoning": obs.get("llm_reasoning", ""),
        })

    # Rank by LLM score descending
    results.sort(key=lambda x: x["llm_score"], reverse=True)

    # Print table
    print("\n" + "=" * 110)
    print(f"{'排名':>4} {'评分':>6} {'评级':>4} {'基线':>6} {'Δ':>6} {'字符':>8} {'参考文献':>8}  {'论文标题':<50}")
    print("-" * 110)
    for idx, r in enumerate(results, 1):
        base = f"{r['base_score']:.1f}" if r['base_score'] is not None else "-"
        delta = f"{r['delta']:+.1f}" if r['delta'] is not None else "-"
        title = r["file_name"].replace(".md", "")[:48]
        print(f"{idx:>4} {r['llm_score']:>6.1f} {r['llm_rating']:>4} {base:>6} {delta:>6} {r['chars']:>8} {r['refs']:>8}  {title}")

    # Summary
    scores = [r["llm_score"] for r in results]
    avg_llm = sum(scores) / len(scores)
    base_scores = [r["base_score"] for r in results if r["base_score"] is not None]
    avg_base = sum(base_scores) / len(base_scores) if base_scores else None
    deltas = [r["delta"] for r in results if r["delta"] is not None]

    print("=" * 110)
    print(f"统计摘要: 共 {len(results)} 篇 | LLM平均分 {avg_llm:.1f}" + (f" | 基线平均分 {avg_base:.1f}" if avg_base else ""))
    if deltas:
        print(f"变化范围: {min(deltas):+.1f} ~ {max(deltas):+.1f} | 平均变化: {sum(deltas)/len(deltas):+.1f}")

    # Distribution
    dist = {}
    for r in results:
        dist[r["llm_rating"]] = dist.get(r["llm_rating"], 0) + 1
    print("评级分布:", " | ".join(f"{k}:{v}" for k, v in sorted(dist.items(), key=lambda x: -x[1])))

    # Save final ranked report
    final_path = output_dir / "_final_ranked_report.json"
    with open(final_path, "w", encoding="utf-8") as f:
        json.dump({
            "avg_llm": round(avg_llm, 1),
            "avg_base": round(avg_base, 1) if avg_base else None,
            "papers": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n最终排序报告已保存: {final_path}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Hybrid script+LLM paper scorer")
    sub = parser.add_subparsers(dest="command", required=True)

    p_prep = sub.add_parser("prepare", help="Extract profiles and build LLM review pack")
    p_prep.add_argument("--input-folder", "-i", required=True, help="Folder containing .md/.txt/.pdf papers")
    p_prep.add_argument("--output-dir", "-o", required=True, help="Output directory for profiles and packs")
    p_prep.add_argument("--excerpt", "-e", type=int, default=3000, help="Max chars for text excerpt")
    p_prep.add_argument("--force", action="store_true", help="Re-run profiler even if profile exists")

    p_apply = sub.add_parser("apply", help="Apply LLM observations and generate ranked table")
    p_apply.add_argument("--input-folder", "-i", required=True, help="Same input folder used in prepare")
    p_apply.add_argument("--output-dir", "-o", required=True, help="Same output directory used in prepare")

    args = parser.parse_args()
    if args.command == "prepare":
        cmd_prepare(args)
    elif args.command == "apply":
        cmd_apply(args)


if __name__ == "__main__":
    main()
