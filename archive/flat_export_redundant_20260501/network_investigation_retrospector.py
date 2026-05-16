#!/usr/bin/env python3
"""
investigation_retrospector.py

Post-mortem analyzer for academic/corruption investigations.
Extracts structural signatures, generates a retrospective summary,
and optionally writes learnings to memory (L2 project) and heuristics (L3 skill).

Usage:
    python investigation_retrospector.py --data ./corruption_network.json --mode auto
    python investigation_retrospector.py --data ./corruption_network.json --report ./final_report.md --notes ./my_notes.md --apply
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# Signature detectors
# ---------------------------------------------------------------------------

def detect_s1_double_layer_shelter(data: dict) -> list:
    """Detect protector nodes with both hospital and department affiliations."""
    findings = []
    nodes = data.get("nodes", [])
    links = data.get("links", [])
    node_types = {n["id"]: n.get("type") for n in nodes if isinstance(n, dict)}

    # Build adjacency: protector -> affiliated_with targets
    protector_targets = {}
    for link in links:
        if not isinstance(link, dict):
            continue
        src = link.get("source")
        ltype = link.get("type")
        tgt = link.get("target")
        if node_types.get(src) == "protector" and ltype == "affiliated_with" and node_types.get(tgt) == "institution":
            protector_targets.setdefault(src, []).append(tgt)

    # Check for shelter edges
    has_shelter = set()
    for link in links:
        if link.get("type") == "shelter" and node_types.get(link.get("source")) == "protector":
            has_shelter.add(link.get("source"))

    for pid, targets in protector_targets.items():
        if len(targets) >= 2:
            node_name = next((n.get("name", pid) for n in nodes if n.get("id") == pid), pid)
            confidence = "L4" if pid in has_shelter else "L2"
            findings.append({
                "signature": "S1: 双层职务掩护",
                "node": node_name,
                "detail": f"该节点同时挂靠 {len(targets)} 个机构/科室: {', '.join(targets)}",
                "confidence": confidence,
                "reason": "存在 shelter 边" if pid in has_shelter else "仅有 affiliated_with 边",
            })
    return findings


def detect_s2_academic_packaging(data: dict) -> list:
    """Detect academic packaging edges and bridge nodes."""
    findings = []
    nodes = data.get("nodes", [])
    links = data.get("links", [])
    node_types = {n["id"]: n.get("type") for n in nodes if isinstance(n, dict)}

    for link in links:
        if not isinstance(link, dict):
            continue
        if link.get("type") == "academic_packaging":
            src = link.get("source")
            tgt = link.get("target")
            src_name = next((n.get("name", src) for n in nodes if n.get("id") == src), src)
            tgt_name = next((n.get("name", tgt) for n in nodes if n.get("id") == tgt), tgt)
            # Check if target also has shelter from a protector
            has_protector_shelter = any(
                l.get("type") == "shelter" and node_types.get(l.get("source")) == "protector" and l.get("target") == tgt
                for l in links
            )
            confidence = "L4" if has_protector_shelter else "L3"
            findings.append({
                "signature": "S2: 学术真空期后的突兀包装",
                "node": f"{src_name} → {tgt_name}",
                "detail": link.get("detail", ""),
                "confidence": confidence,
                "reason": "同时存在 protector 的 shelter 边" if has_protector_shelter else "仅有 academic_packaging 边",
            })
    return findings


def detect_s3_death_event_anomaly(data: dict) -> list:
    """Detect death events with high evasion scores."""
    findings = []
    cases = data.get("cases", [])
    negative_space = data.get("negative_space", {})
    evasion_score = negative_space.get("evasion_score")
    matrix = negative_space.get("matrix", [])

    for case in cases:
        if not isinstance(case, dict):
            continue
        if case.get("type") == "death_event":
            case_name = case.get("name", "未命名死亡事件")
            # Look for unanswered communication-related questions
            unanswered_comm = [m for m in matrix if m.get("score", 0) == 0.0 and any(kw in m.get("question", "") for kw in ["短信", "通讯", "报警", "录音", "手机"])]
            confidence = "L4" if unanswered_comm else "L3"
            if evasion_score is not None and evasion_score > 0.6:
                confidence = "L4"
            findings.append({
                "signature": "S3: 死亡事件后的通讯异常与官方回避",
                "node": case_name,
                "detail": f"官方通报回避度评分: {evasion_score}",
                "confidence": confidence,
                "reason": f"存在 {len(unanswered_comm)} 条未回应的通讯/异常记录问题" if unanswered_comm else "death_event 存在但无明确通讯异常记录",
            })
    return findings


def detect_s4_unlicensed_cross_institution(data: dict) -> list:
    """Detect project_collab to institutions without proper licenses."""
    findings = []
    nodes = data.get("nodes", [])
    links = data.get("links", [])
    node_types = {n["id"]: n.get("type") for n in nodes if isinstance(n, dict)}
    node_details = {n["id"]: n.get("detail", "") for n in nodes if isinstance(n, dict)}

    for link in links:
        if not isinstance(link, dict):
            continue
        if link.get("type") == "project_collab":
            src = link.get("source")
            tgt = link.get("target")
            for nid in (src, tgt):
                detail = node_details.get(nid, "")
                if any(kw in detail for kw in ["无器官移植资质", "无资质", "无伦理审批", "民营医院"]):
                    node_name = next((n.get("name", nid) for n in nodes if n.get("id") == nid), nid)
                    # Check for money laundering
                    has_money_laundering = any(
                        l.get("type") == "money_laundering" for l in links
                    )
                    confidence = "接近 L5" if has_money_laundering else "L4"
                    findings.append({
                        "signature": "S4: 跨机构无资质科研合作",
                        "node": node_name,
                        "detail": f"节点详情中提及资质缺失: {detail[:80]}...",
                        "confidence": confidence,
                        "reason": "同时存在资金中转迹象" if has_money_laundering else "外部机构无资质但参与合作",
                    })
    return findings


def detect_s5_performance_laundering(data: dict) -> list:
    """Detect money laundering edges involving trainee accounts."""
    findings = []
    nodes = data.get("nodes", [])
    links = data.get("links", [])
    node_types = {n["id"]: n.get("type") for n in nodes if isinstance(n, dict)}

    for link in links:
        if not isinstance(link, dict):
            continue
        if link.get("type") == "money_laundering":
            src = link.get("source")
            tgt = link.get("target")
            src_type = node_types.get(src, "unknown")
            tgt_type = node_types.get(tgt, "unknown")
            src_name = next((n.get("name", src) for n in nodes if n.get("id") == src), src)
            tgt_name = next((n.get("name", tgt) for n in nodes if n.get("id") == tgt), tgt)
            findings.append({
                "signature": "S5: 绩效/资金洗钱链（研究生账户中转）",
                "node": f"{src_name} → {tgt_name}",
                "detail": link.get("detail", ""),
                "confidence": "L4" if src_type in ("core_subject", "academic") and tgt_type in ("accomplice", "protector") else "L3",
                "reason": "资金从学生/初级账户流向科室管理人员",
            })
    return findings


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------

def generate_retrospective(data: dict, findings: list, report_path: Path | None, notes_path: Path | None) -> str:
    network_name = data.get("network_name", data.get("name", "未命名调查"))
    nodes = data.get("nodes", [])
    links = data.get("links", [])
    cases = data.get("cases", [])
    negative_space = data.get("negative_space", {})

    lines = [
        f"# 调查回顾摘要：{network_name}",
        "",
        f"- **生成时间**: {datetime.now().isoformat()}",
        f"- **节点数**: {len(nodes)}",
        f"- **关系边数**: {len(links)}",
        f"- **案件数**: {len(cases)}",
        f"- **负面空间回避度**: {negative_space.get('evasion_score', 'N/A')}",
        "",
        "## 检测到的结构签名",
        "",
    ]

    if findings:
        for f in findings:
            lines.append(f"### {f['signature']}")
            lines.append(f"- **涉及节点**: {f['node']}")
            lines.append(f"- **详情**: {f['detail']}")
            lines.append(f"- **置信度**: {f['confidence']}")
            lines.append(f"- **判断依据**: {f['reason']}")
            lines.append("")
    else:
        lines.append("未自动检测到已知的结构签名。本次调查可能具有独特性，建议手动审阅网络拓扑。")
        lines.append("")

    # Top 3 unexpected structural facts
    lines.extend([
        "## 本案最值得固化的 3 个发现",
        "",
    ])
    sig_names = [f["signature"] for f in findings]
    if sig_names:
        lines.append(f"1. **{sig_names[0]}** — 自动检测到，建议纳入未来同类调查的默认检查清单。")
        if len(sig_names) > 1:
            lines.append(f"2. **{sig_names[1]}** — 与已有启发式规则匹配，可作为横向对比基准。")
        if len(sig_names) > 2:
            lines.append(f"3. **{sig_names[2]}** — 需要关注其是否在未来案件中重复出现。")
    else:
        lines.append("1. （待填写）")
        lines.append("2. （待填写）")
        lines.append("3. （待填写）")
    lines.append("")

    lines.extend([
        "## 建议写入启发式规则库（heuristics.md）的候选",
        "",
    ])
    for f in findings:
        if f["confidence"] in ("L4", "接近 L5"):
            lines.append(f"- **{f['signature']}** → 建议提升为通用规则（置信度已达 {f['confidence']}）")
    if not any(f["confidence"] in ("L4", "接近 L5") for f in findings):
        lines.append("- 本次自动检测未发现高置信度（L4+）的通用结构签名，暂不建议写入 heuristics.md。")
    lines.append("")

    if report_path and report_path.exists():
        lines.append(f"- **参考报告**: {report_path}")
    if notes_path and notes_path.exists():
        lines.append(f"- **人工批注**: {notes_path}")

    lines.append("")
    lines.append("---")
    lines.append("*本文件由 investigation_retrospector.py 自动生成。请审阅后决定是否将候选规则写入 heuristics.md。*")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Memory / heuristics writers
# ---------------------------------------------------------------------------

def write_project_memory(case_name: str, findings: list, output_dir: Path) -> Path:
    """Write L2 project memory."""
    memory_dir = Path.home() / ".claude" / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in case_name)
    path = memory_dir / f"project_{safe_name}.md"

    lines = [
        "---",
        f"name: 项目记忆 - {case_name}",
        f"description: 从 {case_name} 调查中萃取的案件模式与结构性发现",
        "type: project",
        "---",
        "",
        f"## {case_name} 结构发现",
        "",
    ]
    for f in findings:
        lines.append(f"- **{f['signature']}**：{f['node']} — {f['detail']}（置信度：{f['confidence']}）")
    lines.append("")
    lines.append("**Why:** 这些结构在本次调查中反复出现，可能是该领域腐败网络的典型模式。")
    lines.append("**How to apply:** 未来调查同类机构/领域时，优先检查上述签名是否存在。")
    lines.append("")

    content = "\n".join(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def propose_heuristic_updates(findings: list, heuristics_path: Path) -> list:
    """Return list of proposed heuristic entries that are not already in heuristics.md."""
    if not heuristics_path.exists():
        return findings

    existing = heuristics_path.read_text(encoding="utf-8")
    proposed = []
    for f in findings:
        if f["confidence"] in ("L4", "接近 L5") and f["signature"] not in existing:
            proposed.append(f)
    return proposed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Investigation retrospector and evolution loop")
    parser.add_argument("--data", "-d", required=True, help="Path to corruption_network.json or scholar_data.json")
    parser.add_argument("--report", "-r", help="Path to final report markdown (optional)")
    parser.add_argument("--notes", "-n", help="Path to user retrospective notes (optional)")
    parser.add_argument("--output", "-o", default="./retrospective_summary.md", help="Output path for retrospective summary")
    parser.add_argument("--apply", action="store_true", help="Write project memory and print heuristic proposals")
    parser.add_argument("--mode", default="auto", choices=["auto", "interactive"], help="Analysis mode")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"[ERROR] Data file not found: {data_path}", file=sys.stderr)
        sys.exit(1)

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict) or ("nodes" not in data and "basic_profile" not in data):
        print("[ERROR] Unrecognized data format. Expected corruption_network or scholar_data.", file=sys.stderr)
        sys.exit(1)

    is_network = "nodes" in data

    print(f"[INFO] Running retrospector on: {data_path}")
    print(f"[INFO] Detected mode: {'corruption_network' if is_network else 'scholar_data'}")

    findings = []
    if is_network:
        findings.extend(detect_s1_double_layer_shelter(data))
        findings.extend(detect_s2_academic_packaging(data))
        findings.extend(detect_s3_death_event_anomaly(data))
        findings.extend(detect_s4_unlicensed_cross_institution(data))
        findings.extend(detect_s5_performance_laundering(data))
    else:
        # scholar_data mode: minimal signature detection (future expansion)
        print("[INFO] Scholar-data retrospective is currently limited to basic summary.")

    report_path = Path(args.report) if args.report else None
    notes_path = Path(args.notes) if args.notes else None
    summary = generate_retrospective(data, findings, report_path, notes_path)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(summary)
    print(f"[OK] Retrospective summary saved: {out_path}")

    if args.apply:
        network_name = data.get("network_name", data.get("name", "unnamed_case"))
        memory_path = write_project_memory(network_name, findings, out_path.parent)
        print(f"[OK] Project memory saved: {memory_path}")

        script_dir = Path(__file__).parent.resolve()
        heuristics_path = script_dir / "heuristics.md"
        proposed = propose_heuristic_updates(findings, heuristics_path)
        if proposed:
            print("\n[PROPOSED HEURISTICS] The following high-confidence signatures are candidates for heuristics.md:")
            for p in proposed:
                print(f"  - {p['signature']} ({p['node']}) — {p['confidence']}")
            print(f"\nTo add them, manually append to {heuristics_path} or re-run with an editor.")
        else:
            print("\n[INFO] No new high-confidence heuristic signatures to propose.")


if __name__ == "__main__":
    main()
