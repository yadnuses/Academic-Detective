#!/usr/bin/env python3
"""
negative_space_analyzer.py

Analyzes what official statements *do not* answer.
Given a list of questions and official statement texts, produces a matrix
scoring evasion/avoidance for each question.

Usage:
    python negative_space_analyzer.py --questions ./questions.json --statements ./statements/ --output ./reports
    python negative_space_analyzer.py --network ./corruption_network.json --output ./reports
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime


def load_questions(path: Path) -> list:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "questions" in data:
        return data["questions"]
    return []


def load_statements(statements_dir: Path) -> list:
    stmts = []
    if not statements_dir.exists():
        return stmts
    for p in sorted(statements_dir.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() not in (".md", ".txt"):
            continue
        with open(p, "r", encoding="utf-8") as f:
            text = f.read()
        stmts.append({
            "file": p.name,
            "title": p.stem,
            "text": text,
        })
    return stmts


def assess_question(question: str, statements: list) -> dict:
    """Naive keyword-based assessment. Human-in-the-loop by design."""
    combined = "\n".join(s["text"] for s in statements)
    # Extract keywords from question (simple heuristic)
    keywords = [w.strip("？?") for w in question.split() if len(w.strip("？?")) >= 2]

    # Check if any keyword appears in statements
    hits = sum(1 for kw in keywords if kw in combined)
    hit_ratio = hits / len(keywords) if keywords else 0

    if hit_ratio >= 0.6:
        status = "部分回应"
        score = 0.5
        evidence_level = "中"
    elif hit_ratio >= 0.2:
        status = "模糊回应"
        score = 0.25
        evidence_level = "低"
    else:
        status = "未回应"
        score = 0.0
        evidence_level = "无"

    # Refinement: look for explicit negation patterns
    negations = ["不存在", "未收到", "未查询到", "无记录", "不涉及", "没有", "not found"]
    has_negation = any(neg in combined for neg in negations)

    note = ""
    if status == "未回应" and has_negation:
        status = "否认但未解释"
        score = 0.15
        note = "官方文本中出现否认性表述，但未提供具体解释或证据。"

    return {
        "question": question,
        "status": status,
        "score": score,
        "evidence_level": evidence_level,
        "note": note,
        "keywords_matched": hits,
    }


def build_matrix(questions: list, statements: list) -> dict:
    rows = []
    total_score = 0.0
    for q in questions:
        if isinstance(q, dict):
            qtext = q.get("question", "")
            severity = q.get("severity", "medium")
        else:
            qtext = str(q)
            severity = "medium"
        result = assess_question(qtext, statements)
        result["severity"] = severity
        rows.append(result)
        total_score += result["score"]

    evasion_score = 1.0 - (total_score / len(rows)) if rows else 0.0
    return {
        "matrix": rows,
        "evasion_score": round(evasion_score, 2),
        "fully_answered": sum(1 for r in rows if r["score"] >= 0.5),
        "partially_answered": sum(1 for r in rows if 0 < r["score"] < 0.5),
        "unanswered": sum(1 for r in rows if r["score"] == 0.0),
    }


def generate_report(network_name: str, matrix_data: dict, statements: list) -> str:
    lines = [
        f"# {network_name} — 负面空间矩阵分析报告",
        "",
        "## 一、总体回避度评估",
        "",
        f"- **信息回避度评分**：{matrix_data['evasion_score']:.2f} / 1.0（越高表示官方通报回避的问题越多）",
        f"- **完全回应**：{matrix_data['fully_answered']} 项",
        f"- **部分/模糊回应**：{matrix_data['partially_answered']} 项",
        f"- **未回应**：{matrix_data['unanswered']} 项",
        "",
        "## 二、问题-回应矩阵",
        "",
        "| 问题 | 回应状态 | 证据等级 | 严重度 | 备注 |",
        "|:---|:---|:---:|:---:|:---|",
    ]
    for r in matrix_data["matrix"]:
        note = r.get("note", "")
        lines.append(
            f"| {r['question']} | {r['status']} | {r['evidence_level']} | {r['severity']} | {note} |"
        )
    lines.append("")

    if statements:
        lines.extend([
            "## 三、分析依据（官方文本来源）",
            "",
        ])
        for s in statements:
            lines.append(f"- `{s['file']}` — {s['title']}")
        lines.append("")

    lines.extend([
        "## 四、关键未解问题",
        "",
    ])
    unanswered = [r for r in matrix_data["matrix"] if r["score"] == 0.0]
    if unanswered:
        for r in unanswered:
            lines.append(f"- **{r['question']}**（严重度：{r['severity']}）")
    else:
        lines.append("无完全未回应的问题。")
    lines.append("")
    return "\n".join(lines)


def extract_questions_from_network(network: dict) -> list:
    """Infer high-value questions from network anomalies and cases."""
    questions = []
    for case in network.get("cases", []):
        if case.get("type") == "death_event":
            questions.append({
                "question": f"{case['name']}的死亡原因是否经过独立第三方复核？",
                "severity": "critical"
            })
            questions.append({
                "question": f"{case['name']}死亡前是否有异常通讯记录，官方如何解释？",
                "severity": "critical"
            })
        if case.get("type") == "criminal_case":
            questions.append({
                "question": f"{case['name']}的上级责任人员是否被追责？",
                "severity": "high"
            })
    # Anomalies related to formal punishment
    for node in network.get("nodes", []):
        if node.get("type") == "protector":
            questions.append({
                "question": f"{node['name']}是否受到公开问责，具体处分内容是什么？",
                "severity": "high"
            })
    return questions


def main():
    parser = argparse.ArgumentParser(description="Negative space analyzer for official statements")
    parser.add_argument("--questions", "-q", help="Path to questions JSON")
    parser.add_argument("--statements", "-s", help="Directory containing official statement md/txt files")
    parser.add_argument("--network", "-n", help="Path to corruption_network.json (auto-infers questions)")
    parser.add_argument("--output", "-o", default="./reports", help="Output directory")
    args = parser.parse_args()

    if not args.network and (not args.questions or not args.statements):
        print("[ERROR] Must provide --network OR both --questions and --statements", file=sys.stderr)
        sys.exit(1)

    network_name = "调查网络"
    questions = []
    statements = []

    network = None
    if args.network:
        with open(args.network, "r", encoding="utf-8") as f:
            network = json.load(f)
        network_name = network.get("network_name", network_name)
        # If network already embeds negative_space matrix, use it directly
        prebuilt = network.get("negative_space")
        if prebuilt and prebuilt.get("matrix"):
            matrix = prebuilt["matrix"]
            result = {
                "matrix": matrix,
                "evasion_score": prebuilt.get("evasion_score", 0.0),
                "fully_answered": sum(1 for r in matrix if r.get("score", 0) >= 0.5),
                "partially_answered": sum(1 for r in matrix if 0 < r.get("score", 0) < 0.5),
                "unanswered": sum(1 for r in matrix if r.get("score", 0) == 0.0),
            }
            # Try to load statements for report attribution only
            stmt_dir = Path(args.network).parent / "official_statements"
            if stmt_dir.is_dir():
                statements = load_statements(stmt_dir)
                print(f"[INFO] Loaded {len(statements)} official statements from {stmt_dir}")
            out_dir = Path(args.output)
            out_dir.mkdir(parents=True, exist_ok=True)
            json_path = out_dir / "negative_space_matrix.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump({
                    "network_name": network_name,
                    "generated_at": datetime.now().isoformat(),
                    **result,
                }, f, ensure_ascii=False, indent=2)
            print(f"[OK] Negative space JSON saved: {json_path}")
            md_path = out_dir / "negative_space_report.md"
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(generate_report(network_name, result, statements))
            print(f"[OK] Negative space report saved: {md_path}")
            return

        questions.extend(extract_questions_from_network(network))
        # Try to load statements from network directory if present
        stmt_dir = Path(args.network).parent / "official_statements"
        if stmt_dir.is_dir():
            statements = load_statements(stmt_dir)
            print(f"[INFO] Loaded {len(statements)} official statements from {stmt_dir}")

    if args.questions:
        questions.extend(load_questions(Path(args.questions)))
    if args.statements:
        statements.extend(load_statements(Path(args.statements)))

    if not questions:
        print("[ERROR] No questions loaded.", file=sys.stderr)
        sys.exit(1)

    # Deduplicate questions by text
    seen = set()
    unique_questions = []
    for q in questions:
        key = q["question"] if isinstance(q, dict) else str(q)
        if key not in seen:
            seen.add(key)
            unique_questions.append(q)

    result = build_matrix(unique_questions, statements)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "negative_space_matrix.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "network_name": network_name,
            "generated_at": datetime.now().isoformat(),
            **result,
        }, f, ensure_ascii=False, indent=2)
    print(f"[OK] Negative space JSON saved: {json_path}")

    md_path = out_dir / "negative_space_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(generate_report(network_name, result, statements))
    print(f"[OK] Negative space report saved: {md_path}")


if __name__ == "__main__":
    main()
