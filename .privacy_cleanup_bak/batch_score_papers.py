#!/usr/bin/env python3
"""
batch_score_papers.py

Batch-run text_profiler + paper_quality_rubric on a folder of papers.
Filters: skip empty files and duplicate files with '(1)' in name.
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.resolve()
TEXT_PROFILER = SCRIPTS_DIR / "text_profiler.py"
RUBRIC = SCRIPTS_DIR / "paper_quality_rubric.py"

INPUT_FOLDER = Path("/Users/xiaoy/Downloads/调查名单/汤铎铎/汤铎铎论文")
OUTPUT_FOLDER = Path("/Users/xiaoy/Downloads/调查名单/汤铎铎/quality_scores")


def run_command(cmd: list) -> tuple:
    start = time.time()
    proc = subprocess.run(
        [sys.executable, *cmd],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    elapsed = time.time() - start
    return proc.returncode, proc.stdout, proc.stderr, elapsed


def main():
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    md_files = sorted(INPUT_FOLDER.glob("*.md"))
    # Filter: non-empty and not duplicate (no '(1)' in stem)
    papers = [
        f for f in md_files
        if f.stat().st_size > 0 and "(1)" not in f.stem
    ]

    print(f"[INFO] Found {len(md_files)} .md files, {len(papers)} eligible for scoring.")
    print(f"[INFO] Output folder: {OUTPUT_FOLDER}\n")

    results = []
    total_text_time = 0.0
    total_rubric_time = 0.0

    for idx, paper_path in enumerate(papers, 1):
        name = paper_path.stem
        profile_path = OUTPUT_FOLDER / f"{name}_profile.json"
        score_path = OUTPUT_FOLDER / f"{name}_quality.json"

        print(f"[{idx}/{len(papers)}] {name}")

        # Step 1: text profiler
        rc, out, err, t1 = run_command([
            str(TEXT_PROFILER),
            "--input", str(paper_path),
            "--output", str(profile_path),
        ])
        total_text_time += t1
        if rc != 0:
            print(f"  [ERROR] text_profiler failed: {err}")
            continue

        # Step 2: quality rubric
        rc, out, err, t2 = run_command([
            str(RUBRIC),
            "--profile", str(profile_path),
            "--output", str(score_path),
        ])
        total_rubric_time += t2
        if rc != 0:
            print(f"  [ERROR] rubric failed: {err}")
            continue

        # Parse result
        try:
            with open(score_path, "r", encoding="utf-8") as f:
                report = json.load(f)
        except Exception as e:
            print(f"  [ERROR] Cannot parse JSON: {e}")
            continue

        dims = report.get("dimensions", {})
        row = {
            "idx": idx,
            "name": name,
            "overall_score": report.get("overall_score", 0),
            "overall_rating": report.get("overall_rating", "?"),
            "verdict": report.get("verdict", ""),
            "chars": 0,
            "refs": 0,
            "time_text": round(t1, 2),
            "time_rubric": round(t2, 2),
        }

        # Load profile for extra stats
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                profile = json.load(f)
            row["chars"] = profile.get("basic_stats", {}).get("total_characters", 0)
            row["refs"] = profile.get("references", {}).get("count", 0)
        except Exception:
            pass

        results.append(row)
        print(f"  -> {report['overall_rating']} ({report['overall_score']}) in {t1+t2:.2f}s")

    total_time = total_text_time + total_rubric_time

    # Summary
    print("\n" + "=" * 70)
    print(f"评分完成: {len(results)} / {len(papers)} 篇")
    print(f"总耗时: {total_time:.2f}s (text profiler: {total_text_time:.2f}s, rubric: {total_rubric_time:.2f}s)")

    if results:
        scores = [r["overall_score"] for r in results]
        avg_score = sum(scores) / len(scores)
        ratings = {}
        for r in results:
            ratings[r["overall_rating"]] = ratings.get(r["overall_rating"], 0) + 1

        print(f"平均分: {avg_score:.1f}")
        print("评级分布:")
        for rating in ["A", "B+", "B", "C", "D"]:
            count = ratings.get(rating, 0)
            bar = "█" * count
            print(f"  {rating:>2}: {count:>2} {bar}")

    # Save summary JSON
    summary_path = OUTPUT_FOLDER / "_batch_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_papers": len(papers),
            "scored": len(results),
            "total_time_sec": round(total_time, 2),
            "avg_score": round(avg_score, 1) if results else None,
            "rating_distribution": ratings if results else {},
            "details": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n汇总报告已保存: {summary_path}")

    # Print table
    print("\n详细评分表:")
    print(f"{'#':>3} {'评分':>5} {'评级':>3} {'字符':>7} {'参考文献':>6} {'耗时(s)':>7}  论文标题")
    for r in results:
        print(f"{r['idx']:>3} {r['overall_score']:>5.1f} {r['overall_rating']:>3} {r['chars']:>7} {r['refs']:>6} {r['time_text']+r['time_rubric']:>7.2f}  {r['name'][:60]}")


if __name__ == "__main__":
    main()
