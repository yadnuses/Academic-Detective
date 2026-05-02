#!/usr/bin/env python3
"""
timeline_weaver.py

Multi-source event timeline merger and coupling analyzer for corruption investigations.
Reads event files (CSV/JSON) or a corruption_network.json, weaves a unified timeline,
detects high-coupling windows, and outputs a structured report.

Usage:
    python timeline_weaver.py --network ./corruption_network.json --output ./reports
    python timeline_weaver.py --events ./events_liu.csv ./events_luo.csv --output ./reports
"""

import json
import sys
import argparse
import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict


def _parse_date(date_str: str) -> datetime:
    """Parse fuzzy dates like '2014-09', '2024-05-08', '2021-04-20'."""
    s = str(date_str).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {s}")


def _date_to_sort_key(dt: datetime) -> str:
    """Normalize to ISO-like string for grouping."""
    if dt.day == 1 and dt.month == 1:
        return dt.strftime("%Y")
    if dt.day == 1:
        return dt.strftime("%Y-%m")
    return dt.strftime("%Y-%m-%d")


def load_events_csv(path: Path) -> list:
    events = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            events.append({
                "date": row["date"],
                "node_ids": [n.strip() for n in row.get("node", "").split(",") if n.strip()],
                "event": row["event"],
                "category": row.get("category", ""),
                "source": row.get("source", ""),
            })
    return events


def load_events_json(path: Path) -> list:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "timelines" in data:
        events = []
        for tl in data["timelines"]:
            for ev in tl.get("events", []):
                events.append(ev)
        return events
    return []


def extract_events_from_network(network: dict) -> list:
    events = []
    for tl in network.get("timelines", []):
        for ev in tl.get("events", []):
            events.append(ev)
    # Also infer events from cases
    for case in network.get("cases", []):
        if case.get("date"):
            events.append({
                "date": case["date"],
                "node_ids": [],
                "event": f"【案件节点】{case['name']}",
                "category": "case",
                "source": case.get("official_source", ""),
                "is_anchor": True,
            })
    # Infer institutional affiliations from links as soft events
    node_types = {n["id"]: n["type"] for n in network.get("nodes", [])}
    for link in network.get("links", []):
        if link.get("type") == "affiliated_with":
            # These are structural, not timeline events; skip
            continue
    return events


def build_timeline(events: list) -> list:
    """Sort and normalize events."""
    parsed = []
    for ev in events:
        try:
            dt = _parse_date(ev["date"])
        except ValueError:
            continue
        parsed.append({
            "dt": dt,
            "date_str": _date_to_sort_key(dt),
            "node_ids": ev.get("node_ids", []),
            "event": ev.get("event", ""),
            "category": ev.get("category", ""),
            "source": ev.get("source", ""),
            "is_anchor": ev.get("is_anchor", False),
        })
    parsed.sort(key=lambda x: x["dt"])
    return parsed


def detect_coupling_windows(timeline: list, window_months: int = 6, min_nodes: int = 2) -> list:
    """Detect time windows where multiple nodes have key events."""
    windows = []
    n = len(timeline)
    for i in range(n):
        anchor = timeline[i]
        window_events = [anchor]
        anchor_dt = anchor["dt"]
        for j in range(i + 1, n):
            delta = (timeline[j]["dt"].year - anchor_dt.year) * 12 + (timeline[j]["dt"].month - anchor_dt.month)
            if delta > window_months:
                break
            window_events.append(timeline[j])
        # Count unique non-institution nodes
        unique_nodes = set()
        for ev in window_events:
            for nid in ev.get("node_ids", []):
                unique_nodes.add(nid)
        if len(unique_nodes) >= min_nodes and len(window_events) >= 2:
            windows.append({
                "start": anchor["date_str"],
                "end": window_events[-1]["date_str"],
                "events": [dict((k, v) for k, v in e.items() if k != "dt") for e in window_events],
                "unique_nodes": sorted(unique_nodes),
                "event_count": len(window_events),
            })
    # Deduplicate by start date and node set signature
    seen = set()
    deduped = []
    for w in windows:
        sig = (w["start"], tuple(w["unique_nodes"]))
        if sig not in seen:
            seen.add(sig)
            deduped.append(w)
    return deduped


def generate_report(network_name: str, timeline: list, windows: list) -> str:
    lines = [
        f"# {network_name} — 时间线编织与耦合分析报告",
        "",
        "## 一、统一时间线总览",
        "",
    ]
    for ev in timeline:
        nodes = ", ".join(ev.get("node_ids", [])) or "—"
        anchor_mark = "【锚点】" if ev.get("is_anchor") else ""
        lines.append(f"- **{ev['date_str']}** {anchor_mark}{nodes} — {ev['event']}")
    lines.append("")

    lines.extend([
        "## 二、高耦合窗口分析",
        "",
        f"检测参数：滑动窗口 {6} 个月，最少 {2} 个不同节点参与。",
        "",
    ])
    if not windows:
        lines.append("未检测到显著的高耦合窗口。")
    else:
        for idx, w in enumerate(windows, 1):
            lines.append(f"### 窗口 {idx}：{w['start']} ~ {w['end']}")
            lines.append(f"参与节点：{', '.join(w['unique_nodes'])}")
            lines.append("")
            lines.append("| 日期 | 节点 | 事件 | 类型 |")
            lines.append("|:---|:---|:---|:---|")
            for e in w["events"]:
                nodes = ", ".join(e.get("node_ids", [])) or "—"
                lines.append(f"| {e['date_str']} | {nodes} | {e['event']} | {e.get('category', '')} |")
            lines.append("")

    # Yearly summary
    lines.extend([
        "## 三、年度事件密度",
        "",
        "| 年份 | 事件数 | 锚点数 |",
        "|:---|:---:|:---:|",
    ])
    year_stats = defaultdict(lambda: {"count": 0, "anchors": 0})
    for ev in timeline:
        y = str(ev["dt"].year)
        year_stats[y]["count"] += 1
        if ev.get("is_anchor"):
            year_stats[y]["anchors"] += 1
    for y in sorted(year_stats.keys()):
        s = year_stats[y]
        lines.append(f"| {y} | {s['count']} | {s['anchors']} |")
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Timeline weaver for corruption network investigations")
    parser.add_argument("--network", "-n", help="Path to corruption_network.json")
    parser.add_argument("--events", "-e", nargs="+", help="Paths to event CSV/JSON files")
    parser.add_argument("--output", "-o", default="./reports", help="Output directory")
    parser.add_argument("--window-months", type=int, default=6, help="Coupling window in months")
    parser.add_argument("--min-nodes", type=int, default=2, help="Minimum unique nodes for coupling window")
    args = parser.parse_args()

    if not args.network and not args.events:
        print("[ERROR] Must provide --network or --events", file=sys.stderr)
        sys.exit(1)

    events = []
    network_name = "调查网络"

    if args.network:
        with open(args.network, "r", encoding="utf-8") as f:
            network = json.load(f)
        network_name = network.get("network_name", network_name)
        events.extend(extract_events_from_network(network))

    if args.events:
        for p_str in args.events:
            p = Path(p_str)
            if not p.exists():
                print(f"[WARN] Event file not found: {p}", file=sys.stderr)
                continue
            if p.suffix.lower() == ".csv":
                events.extend(load_events_csv(p))
            elif p.suffix.lower() == ".json":
                events.extend(load_events_json(p))
            else:
                print(f"[WARN] Unsupported event file format: {p.suffix}", file=sys.stderr)

    if not events:
        print("[ERROR] No events loaded.", file=sys.stderr)
        sys.exit(1)

    timeline = build_timeline(events)
    windows = detect_coupling_windows(timeline, window_months=args.window_months, min_nodes=args.min_nodes)

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    # JSON output
    json_path = out_dir / "timeline_woven.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "network_name": network_name,
            "generated_at": datetime.now().isoformat(),
            "event_count": len(timeline),
            "coupling_windows": len(windows),
            "timeline": [dict((k, v) for k, v in e.items() if k != "dt") for e in timeline],
            "windows": windows,
        }, f, ensure_ascii=False, indent=2)
    print(f"[OK] Timeline JSON saved: {json_path}")

    # Markdown report
    md_path = out_dir / "timeline_coupling_report.md"
    report = generate_report(network_name, timeline, windows)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[OK] Timeline report saved: {md_path}")


if __name__ == "__main__":
    main()
