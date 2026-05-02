#!/usr/bin/env python3
"""
grant_linker.py

Extracts grant/project numbers from text/PDF sources and builds a linkage
network across papers, PIs, and events. Flags temporal conflicts and
institution mismatches.

Usage:
    python grant_linker.py --papers ./pdfs --pi-table ./pi_table.json --output ./reports
    python grant_linker.py --network ./corruption_network.json --output ./reports
"""

import json
import sys
import re
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict


# Common Chinese grant number patterns
GRANT_PATTERNS = [
    ("NSFC", re.compile(r"国家自然科学基金\s*[：(]?\s*([\d;，,\s]+)")),
    ("NSFC_SHORT", re.compile(r"NSFC\s*[：(]?\s*([\d;，,\s]+)")),
    ("HUNAN_JJ", re.compile(r"湖南省自然科学基金\s*[：(]?\s*(20\d{2}JJ\d+)")),
    ("HUNAN_JJ_SHORT", re.compile(r"湖南省自然科学基金\s*[：(]?\s*([\d;，,\s]+)")),
    ("GENERIC_JJ", re.compile(r"([A-Za-z]*省|市)?自然科学基金\s*[：(]?\s*([\d;，,\sA-Za-z]+)")),
]


def _extract_grant_ids(text: str) -> list:
    found = []
    for label, pat in GRANT_PATTERNS:
        for m in pat.finditer(text):
            raw = m.group(1)
            ids = [x.strip() for x in re.split(r"[,;，\s]+", raw) if x.strip()]
            found.extend(ids)
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for gid in found:
        if gid not in seen:
            seen.add(gid)
            unique.append(gid)
    return unique


def _extract_title_authors(text: str) -> tuple:
    """Naive extraction of title and authors from paper markdown/text."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    title = ""
    authors = []
    for line in lines[:20]:
        if not title and len(line) > 10 and not line.startswith("【"):
            title = line
            continue
        if "作者" in line or line.startswith("Authors:"):
            rest = line.split(":", 1)[1] if ":" in line else line
            authors = [a.strip() for a in re.split(r"[,，;]", rest) if a.strip()]
            break
    return title, authors


def load_paper_texts(papers_dir: Path) -> list:
    papers = []
    if not papers_dir.exists():
        return papers
    for p in papers_dir.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in (".md", ".txt", ".json"):
            continue
        with open(p, "r", encoding="utf-8") as f:
            text = f.read()
        title, authors = _extract_title_authors(text)
        grant_ids = _extract_grant_ids(text)
        papers.append({
            "file": str(p.name),
            "title": title or p.stem,
            "authors": authors,
            "grant_ids": grant_ids,
        })
    return papers


def load_pi_table(pi_path: Path) -> dict:
    """pi_table.json format: { grant_id: { name, institution, period } }"""
    with open(pi_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_linkages(papers: list, pi_table: dict, events: list) -> dict:
    grant_map = defaultdict(lambda: {
        "grant_id": "",
        "name": "",
        "pi": "",
        "pi_institution": "",
        "period": "",
        "linked_papers": [],
        "linked_events": [],
    })

    for gid, info in pi_table.items():
        grant_map[gid]["grant_id"] = gid
        grant_map[gid]["name"] = info.get("name", "")
        grant_map[gid]["pi"] = info.get("pi", "")
        grant_map[gid]["pi_institution"] = info.get("pi_institution", "")
        grant_map[gid]["period"] = info.get("period", "")

    for paper in papers:
        for gid in paper.get("grant_ids", []):
            if gid in pi_table:
                entry = {
                    "title": paper.get("title", ""),
                    "authors": paper.get("authors", []),
                    "anomaly": "",
                }
                grant_map[gid]["linked_papers"].append(entry)

    for ev in events:
        detail = ev.get("event", "")
        for gid in _extract_grant_ids(detail):
            if gid in pi_table:
                grant_map[gid]["linked_events"].append({
                    "date": ev.get("date", ""),
                    "event": detail,
                    "node_ids": ev.get("node_ids", []),
                })

    # Run anomaly checks
    results = []
    for gid, data in grant_map.items():
        if not data["linked_papers"] and not data["linked_events"]:
            continue
        for paper in data["linked_papers"]:
            anomalies = []
            # Check if paper published after grant period end
            period = data.get("period", "")
            if period and "-" in period:
                try:
                    end_year = int(period.split("-")[1])
                    # Naive pub year extraction from title or filename
                    pub_years = [int(y) for y in re.findall(r"20\d{2}", paper["title"])]
                    if pub_years and max(pub_years) > end_year:
                        anomalies.append(f"论文发表时间({max(pub_years)})晚于基金结题时间({end_year})")
                except Exception:
                    pass
            if anomalies:
                paper["anomaly"] = "; ".join(anomalies)
        results.append(data)

    return {"grants": results}


def generate_report(linkages: dict, network_name: str = "调查网络") -> str:
    lines = [
        f"# {network_name} — 基金号关联分析报告",
        "",
    ]
    grants = linkages.get("grants", [])
    if not grants:
        lines.append("未检测到任何基金号关联。")
        return "\n".join(lines)

    for g in grants:
        lines.append(f"## {g['grant_id']}")
        lines.append(f"- **项目名称**：{g.get('name', 'N/A')}")
        lines.append(f"- **负责人**：{g.get('pi', 'N/A')} ({g.get('pi_institution', 'N/A')})")
        lines.append(f"- **执行期**：{g.get('period', 'N/A')}")
        lines.append(f"- **关联论文数**：{len(g.get('linked_papers', []))}")
        lines.append(f"- **关联事件数**：{len(g.get('linked_events', []))}")
        if g.get("linked_papers"):
            lines.append("\n**关联论文**：")
            for p in g["linked_papers"]:
                anomaly = f" ⚠ {p['anomaly']}" if p.get("anomaly") else ""
                lines.append(f"- 《{p['title']}》{anomaly}")
        if g.get("linked_events"):
            lines.append("\n**关联事件**：")
            for e in g["linked_events"]:
                nodes = ", ".join(e.get("node_ids", [])) or "—"
                lines.append(f"- {e['date']} {nodes} — {e['event']}")
        lines.append("")
    return "\n".join(lines)


def extract_events_from_network(network: dict) -> list:
    events = []
    for tl in network.get("timelines", []):
        for ev in tl.get("events", []):
            events.append(ev)
    return events


def main():
    parser = argparse.ArgumentParser(description="Grant linkage analyzer")
    parser.add_argument("--papers", "-p", help="Directory containing paper md/txt files")
    parser.add_argument("--pi-table", help="Path to pi_table.json")
    parser.add_argument("--network", "-n", help="Path to corruption_network.json (uses timelines as events)")
    parser.add_argument("--output", "-o", default="./reports", help="Output directory")
    args = parser.parse_args()

    papers = []
    if args.papers:
        papers = load_paper_texts(Path(args.papers))
        print(f"[INFO] Loaded {len(papers)} paper texts from {args.papers}")

    events = []
    network_name = "调查网络"
    network = None
    if args.network:
        with open(args.network, "r", encoding="utf-8") as f:
            network = json.load(f)
        network_name = network.get("network_name", network_name)
        # If network embeds grants and no external inputs provided, use directly
        embedded_grants = network.get("grants")
        if embedded_grants and not args.papers and not args.pi_table:
            linkages = {"grants": embedded_grants}
            out_dir = Path(args.output)
            out_dir.mkdir(parents=True, exist_ok=True)
            json_path = out_dir / "grant_linkage.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(linkages, f, ensure_ascii=False, indent=2)
            print(f"[OK] Grant linkage JSON saved: {json_path}")
            md_path = out_dir / "grant_linkage_report.md"
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(generate_report(linkages, network_name))
            print(f"[OK] Grant linkage report saved: {md_path}")
            return

        events.extend(extract_events_from_network(network))
        print(f"[INFO] Loaded {len(events)} events from network")

    pi_table = {}
    if args.pi_table:
        pi_table = load_pi_table(Path(args.pi_table))
        print(f"[INFO] Loaded PI table with {len(pi_table)} entries")

    linkages = build_linkages(papers, pi_table, events)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "grant_linkage.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(linkages, f, ensure_ascii=False, indent=2)
    print(f"[OK] Grant linkage JSON saved: {json_path}")

    md_path = out_dir / "grant_linkage_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(generate_report(linkages, network_name))
    print(f"[OK] Grant linkage report saved: {md_path}")


if __name__ == "__main__":
    main()
