#!/usr/bin/env python3
"""
network_visualizer.py

Relationship network visualizer for scholar investigation data.
Reads scholar_data.json and generates:
  1. An interactive HTML force-directed graph (D3.js)
  2. A raw JSON network data file for downstream use

Supported network layers:
  - Advisor lineage
  - Key collaborator map
  - Editorial board connections
  - Institutional dependencies
  - Citation network (from citation_profiler output)

Usage:
    python network_visualizer.py --input ./scholar_data.json --output-dir ./reports/
"""

import json
import sys
import argparse
import math
from pathlib import Path
from datetime import datetime
from collections import defaultdict


# ── Color & type palette ────────────────────────────────────────
NODE_TYPES = {
    # single-scholar legacy types
    "scholar":       {"label": "调查对象",   "color": "#e74c3c", "radius": 24},
    "advisor":       {"label": "导师",       "color": "#2980b9", "radius": 18},
    "collaborator":  {"label": "合作者",     "color": "#27ae60", "radius": 16},
    "editorial":     {"label": "编委/期刊",  "color": "#8e44ad", "radius": 16},
    "citer":         {"label": "引用者",     "color": "#1abc9c", "radius": 12},
    # corruption-network types
    "core_subject":  {"label": "核心调查对象", "color": "#c0392b", "radius": 26},
    "protector":     {"label": "庇护者/保护伞", "color": "#2980b9", "radius": 20},
    "accomplice":    {"label": "共犯/执行者",   "color": "#e67e22", "radius": 16},
    "external":      {"label": "外部合作者",    "color": "#27ae60", "radius": 16},
    "academic":      {"label": "学术关联者",    "color": "#8e44ad", "radius": 15},
    "family":        {"label": "亲属关系",      "color": "#e84393", "radius": 14},
    "victim":        {"label": "受害者",        "color": "#6c5ce7", "radius": 16},
    "official":      {"label": "官方/调查组",    "color": "#636e72", "radius": 18},
    # shared
    "institution":   {"label": "机构",          "color": "#95a5a6", "radius": 18},
    "unknown":       {"label": "未知",          "color": "#95a5a6", "radius": 10},
}

LINK_TYPES = {
    # single-scholar legacy
    "advisor_of":        {"label": "导师",      "color": "#2980b9", "width": 3},
    "collaborates_with": {"label": "合作",      "color": "#27ae60", "width": 2},
    "editorial_board":   {"label": "编委",      "color": "#8e44ad", "width": 2},
    "cites":             {"label": "引用",      "color": "#1abc9c", "width": 1},
    "mutual_cite":       {"label": "互引",      "color": "#e67e22", "width": 2, "dash": True},
    # corruption-network
    "shelter":           {"label": "结构性庇护",   "color": "#c0392b", "width": 3},
    "academic_packaging":{"label": "学术包装",     "color": "#8e44ad", "width": 2},
    "money_laundering":  {"label": "资金中转",     "color": "#e67e22", "width": 3},
    "project_collab":    {"label": "项目合作",     "color": "#27ae60", "width": 2},
    "clinical":          {"label": "临床协作",     "color": "#636e72", "width": 1.5},
    "accomplice_link":   {"label": "同案犯",       "color": "#e67e22", "width": 2},
    "victimization":     {"label": "受害者关系",   "color": "#6c5ce7", "width": 3},
    "family":            {"label": "亲属关系",     "color": "#e84393", "width": 1.5},
    "formal_punishment": {"label": "象征性问责",   "color": "#636e72", "width": 2, "dash": True},
    # shared
    "affiliated_with":   {"label": "机构关联",     "color": "#95a5a6", "width": 1},
}


def _is_empty(val) -> bool:
    if val is None:
        return True
    if isinstance(val, str):
        return val.strip() == "" or val.strip() == "[TO BE FILLED]"
    if isinstance(val, list):
        return len(val) == 0
    if isinstance(val, dict):
        return len(val) == 0
    return False


def _safe_get(data: dict, *keys, default=None):
    """Safely traverse nested dicts."""
    for k in keys:
        if not isinstance(data, dict):
            return default
        data = data.get(k, default)
        if data is None:
            return default
    return data


# ── Network builders ────────────────────────────────────────────

def build_advisor_node(scholar_name: str, advisor_data) -> list:
    """Build nodes/links for advisor relationship."""
    nodes, links = [], []
    if _is_empty(advisor_data):
        return nodes, links

    if isinstance(advisor_data, str):
        advisor_data = {"name": advisor_data.strip()}
    elif isinstance(advisor_data, list) and advisor_data:
        # If list, take first or iterate
        advisor_data = advisor_data[0] if isinstance(advisor_data[0], dict) else {"name": str(advisor_data[0])}

    if isinstance(advisor_data, dict):
        name = advisor_data.get("name", "未知导师")
        institution = advisor_data.get("institution", "")
    else:
        name = str(advisor_data).strip()
        institution = ""

    if not name or name == "未知导师":
        return nodes, links

    node_id = f"advisor_{name}"
    nodes.append({
        "id": node_id,
        "name": name,
        "type": "advisor",
        "institution": institution,
        "detail": f"导师: {name}" + (f" ({institution})" if institution else ""),
    })
    links.append({
        "source": "scholar",
        "target": node_id,
        "type": "advisor_of",
        "detail": f"{scholar_name} 的导师是 {name}",
    })
    return nodes, links


def build_collaborator_nodes(scholar_name: str, collab_data) -> list:
    """Build nodes/links for key collaborators."""
    nodes, links = [], []
    if _is_empty(collab_data):
        return nodes, links

    if isinstance(collab_data, str):
        # Try comma-separated
        names = [n.strip() for n in collab_data.split(",") if n.strip()]
        collab_data = [{"name": n} for n in names]
    elif isinstance(collab_data, dict):
        collab_data = [collab_data]
    elif not isinstance(collab_data, list):
        return nodes, links

    for i, item in enumerate(collab_data):
        if isinstance(item, str):
            item = {"name": item.strip()}
        if not isinstance(item, dict):
            continue
        name = item.get("name", "").strip()
        if not name:
            continue
        node_id = f"collab_{i}_{name}"
        institution = item.get("institution", "")
        co_paper_count = item.get("co_paper_count", item.get("paper_count"))
        co_year_range = item.get("year_range", "")

        detail_parts = [f"合作者: {name}"]
        if institution:
            detail_parts.append(f"机构: {institution}")
        if co_paper_count is not None:
            detail_parts.append(f"合作论文: {co_paper_count} 篇")
        if co_year_range:
            detail_parts.append(f"合作时段: {co_year_range}")

        nodes.append({
            "id": node_id,
            "name": name,
            "type": "collaborator",
            "institution": institution,
            "co_paper_count": co_paper_count,
            "detail": " | ".join(detail_parts),
        })
        links.append({
            "source": "scholar",
            "target": node_id,
            "type": "collaborates_with",
            "detail": f"{scholar_name} 与 {name} 存在合作关系",
            "weight": co_paper_count or 1,
        })
    return nodes, links


def build_editorial_nodes(scholar_name: str, editorial_data) -> list:
    """Build nodes/links for editorial board connections."""
    nodes, links = [], []
    if _is_empty(editorial_data):
        return nodes, links

    if isinstance(editorial_data, str):
        names = [n.strip() for n in editorial_data.split(",") if n.strip()]
        editorial_data = [{"journal": n} for n in names]
    elif isinstance(editorial_data, dict):
        editorial_data = [editorial_data]
    elif not isinstance(editorial_data, list):
        return nodes, links

    for i, item in enumerate(editorial_data):
        if isinstance(item, str):
            item = {"journal": item.strip()}
        if not isinstance(item, dict):
            continue
        journal = item.get("journal", item.get("name", "")).strip()
        if not journal:
            continue
        node_id = f"edit_{i}_{journal}"
        role = item.get("role", "编委")
        since = item.get("since", "")

        detail_parts = [f"期刊: {journal}", f"职务: {role}"]
        if since:
            detail_parts.append(f"起始: {since}")

        nodes.append({
            "id": node_id,
            "name": journal,
            "type": "editorial",
            "role": role,
            "since": since,
            "detail": " | ".join(detail_parts),
        })
        links.append({
            "source": "scholar",
            "target": node_id,
            "type": "editorial_board",
            "detail": f"{scholar_name} 担任 {journal} 的 {role}",
        })
    return nodes, links


def build_institution_nodes(scholar_name: str, inst_data) -> list:
    """Build nodes/links for institutional dependencies."""
    nodes, links = [], []
    if _is_empty(inst_data):
        return nodes, links

    if isinstance(inst_data, str):
        names = [n.strip() for n in inst_data.split(",") if n.strip()]
        inst_data = [{"name": n} for n in names]
    elif isinstance(inst_data, dict):
        inst_data = [inst_data]
    elif not isinstance(inst_data, list):
        return nodes, links

    for i, item in enumerate(inst_data):
        if isinstance(item, str):
            item = {"name": item.strip()}
        if not isinstance(item, dict):
            continue
        name = item.get("name", item.get("institution", "")).strip()
        if not name:
            continue
        node_id = f"inst_{i}_{name}"
        relationship = item.get("relationship", item.get("type", "关联"))
        detail_parts = [f"机构: {name}", f"关系: {relationship}"]

        nodes.append({
            "id": node_id,
            "name": name,
            "type": "institution",
            "relationship": relationship,
            "detail": " | ".join(detail_parts),
        })
        links.append({
            "source": "scholar",
            "target": node_id,
            "type": "affiliated_with",
            "detail": f"{scholar_name} 与 {name} 存在 {relationship} 关系",
        })
    return nodes, links


def build_citation_nodes(scholar_name: str, citation_analysis: dict) -> list:
    """Build nodes/links from citation_profiler output summary."""
    nodes, links = [], []
    if _is_empty(citation_analysis) or citation_analysis.get("status") != "loaded":
        return nodes, links

    # Red flags from citation analysis may name persistent citers
    red_flags = citation_analysis.get("red_flags", [])
    for flag in red_flags:
        signal = flag.get("signal", "")
        detail = flag.get("detail", "")
        # Extract author name from "Author 'XXX' cited N times"
        if "Author '" in detail or "author '" in detail:
            import re
            m = re.search(r"[Aa]uthor ['\"](.+?)['\"]", detail)
            if m:
                author = m.group(1)
                node_id = f"citer_{author}"
                if not any(n["id"] == node_id for n in nodes):
                    nodes.append({
                        "id": node_id,
                        "name": author,
                        "type": "citer",
                        "detail": f"高频引用者: {author} | {detail}",
                        "signal": signal,
                    })
                    links.append({
                        "source": "scholar",
                        "target": node_id,
                        "type": "cites",
                        "detail": detail,
                        "is_anomaly": True,
                    })
    return nodes, links


def _is_corruption_network(data: dict) -> bool:
    """Detect if input follows corruption_network schema."""
    return "network_name" in data and "nodes" in data and "links" in data


# ── Main builder ────────────────────────────────────────────────

def build_network(data: dict) -> dict:
    """Build network from either scholar_data.json or corruption_network.json."""
    if _is_corruption_network(data):
        return _build_corruption_network(data)
    return _build_scholar_network(data)


def _build_corruption_network(data: dict) -> dict:
    """Build directly from corruption_network schema."""
    network_name = data.get("network_name", "腐败网络")
    nodes = []
    links = []

    for n in data.get("nodes", []):
        nodes.append({
            "id": n["id"],
            "name": n["name"],
            "type": n.get("type", "unknown"),
            "institution": n.get("institution", ""),
            "detail": n.get("detail", ""),
        })

    for l in data.get("links", []):
        links.append({
            "source": l["source"],
            "target": l["target"],
            "type": l.get("type", "affiliated_with"),
            "detail": l.get("detail", ""),
            "weight": l.get("weight", 1),
            "is_anomaly": l.get("is_anomaly", False),
        })

    seen = {}
    unique_nodes = []
    for n in nodes:
        if n["id"] not in seen:
            seen[n["id"]] = n
            unique_nodes.append(n)

    seen_links = set()
    unique_links = []
    for l in links:
        key = (l["source"], l["target"], l["type"])
        if key not in seen_links:
            seen_links.add(key)
            unique_links.append(l)

    return {
        "network_name": network_name,
        "generated_at": datetime.now().isoformat(),
        "node_count": len(unique_nodes),
        "link_count": len(unique_links),
        "nodes": unique_nodes,
        "links": unique_links,
    }


def _build_scholar_network(data: dict) -> dict:
    """Original single-scholar network builder."""
    scholar_name = data.get("name", "未知学者")
    institution = data.get("institution", "")
    rel = data.get("relationship_network", {})

    nodes = []
    links = []

    # Central scholar node
    nodes.append({
        "id": "scholar",
        "name": scholar_name,
        "type": "scholar",
        "institution": institution,
        "detail": f"调查对象: {scholar_name}" + (f" ({institution})" if institution else ""),
    })

    # Layer 1: Advisor
    n, l = build_advisor_node(scholar_name, rel.get("advisor"))
    nodes.extend(n)
    links.extend(l)

    # Layer 2: Collaborators
    n, l = build_collaborator_nodes(scholar_name, rel.get("key_collaborators"))
    nodes.extend(n)
    links.extend(l)

    # Layer 3: Editorial
    n, l = build_editorial_nodes(scholar_name, rel.get("editorial_connections"))
    nodes.extend(n)
    links.extend(l)

    # Layer 4: Institutions
    n, l = build_institution_nodes(scholar_name, rel.get("institutional_dependencies"))
    nodes.extend(n)
    links.extend(l)

    # Layer 5: Citation network
    n, l = build_citation_nodes(scholar_name, rel.get("citation_analysis"))
    nodes.extend(n)
    links.extend(l)

    # Deduplicate nodes by id
    seen = {}
    unique_nodes = []
    for n in nodes:
        if n["id"] not in seen:
            seen[n["id"]] = n
            unique_nodes.append(n)

    # Deduplicate links by (source, target, type)
    seen_links = set()
    unique_links = []
    for l in links:
        key = (l["source"], l["target"], l["type"])
        if key not in seen_links:
            seen_links.add(key)
            unique_links.append(l)

    return {
        "network_name": scholar_name,
        "generated_at": datetime.now().isoformat(),
        "node_count": len(unique_nodes),
        "link_count": len(unique_links),
        "nodes": unique_nodes,
        "links": unique_links,
    }


def compute_stats(network: dict) -> dict:
    """Compute network statistics."""
    nodes = network["nodes"]
    links = network["links"]

    type_counts = defaultdict(int)
    for n in nodes:
        type_counts[n.get("type", "unknown")] += 1

    link_type_counts = defaultdict(int)
    for l in links:
        link_type_counts[l.get("type", "unknown")] += 1

    # Degree centrality (simple count)
    degree = defaultdict(int)
    for l in links:
        degree[l["source"]] += 1
        degree[l["target"]] += 1

    max_degree = max(degree.values()) if degree else 0
    isolated = [n["name"] for n in nodes if degree.get(n["id"], 0) == 0 and n["type"] != "scholar"]

    # Anomaly links (from citation red flags)
    anomaly_links = [l for l in links if l.get("is_anomaly")]

    return {
        "type_distribution": dict(type_counts),
        "link_type_distribution": dict(link_type_counts),
        "max_degree": max_degree,
        "isolated_nodes": isolated,
        "anomaly_link_count": len(anomaly_links),
        "density": len(links) / (len(nodes) * (len(nodes) - 1)) if len(nodes) > 1 else 0,
    }


# ── HTML generator ──────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{network_name}} - 学术关系网络图谱</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    background: #f5f6fa;
    color: #2c3e50;
    overflow: hidden;
  }
  .header {
    position: fixed; top: 0; left: 0; right: 0; height: 56px;
    background: #fff; border-bottom: 1px solid #e1e4e8;
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 24px; z-index: 100;
  }
  .header h1 { font-size: 18px; font-weight: 600; }
  .header .badge {
    background: #e74c3c; color: #fff; font-size: 12px; padding: 3px 10px;
    border-radius: 12px; font-weight: 500;
  }
  .sidebar {
    position: fixed; top: 56px; left: 0; bottom: 0; width: 280px;
    background: #fff; border-right: 1px solid #e1e4e8;
    padding: 20px; overflow-y: auto; z-index: 90;
  }
  .sidebar h2 { font-size: 14px; color: #7f8c8d; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
  .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 24px; }
  .stat-card {
    background: #f8f9fa; border-radius: 8px; padding: 12px; text-align: center;
  }
  .stat-card .value { font-size: 22px; font-weight: 700; color: #2c3e50; }
  .stat-card .label { font-size: 11px; color: #7f8c8d; margin-top: 4px; }
  .legend-item { display: flex; align-items: center; margin-bottom: 8px; font-size: 13px; }
  .legend-dot { width: 12px; height: 12px; border-radius: 50%; margin-right: 8px; }
  .legend-line { width: 24px; height: 2px; margin-right: 8px; }
  .node-detail {
    margin-top: 20px; padding: 12px; background: #f8f9fa; border-radius: 8px;
    font-size: 13px; line-height: 1.6; min-height: 80px;
  }
  .node-detail.empty { color: #95a5a6; font-style: italic; }
  #graph-container {
    position: fixed; top: 56px; left: 280px; right: 0; bottom: 0;
    background: #fff;
  }
  .tooltip {
    position: absolute; padding: 8px 12px; background: rgba(0,0,0,0.85);
    color: #fff; border-radius: 6px; font-size: 12px; pointer-events: none;
    opacity: 0; transition: opacity 0.15s; max-width: 280px; line-height: 1.5;
  }
  .controls {
    position: fixed; bottom: 20px; right: 20px; z-index: 100;
    display: flex; flex-direction: column; gap: 8px;
  }
  .controls button {
    width: 40px; height: 40px; border-radius: 50%; border: none;
    background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    cursor: pointer; font-size: 18px; display: flex; align-items: center;
    justify-content: center; transition: all 0.2s;
  }
  .controls button:hover { background: #f0f0f0; transform: scale(1.1); }
  .filter-group { margin-bottom: 16px; }
  .filter-group label { display: flex; align-items: center; font-size: 13px; margin-bottom: 6px; cursor: pointer; }
  .filter-group input { margin-right: 6px; }
  .warning-banner {
    background: #fff3cd; border: 1px solid #ffc107; color: #856404;
    padding: 8px 12px; border-radius: 6px; font-size: 12px; margin-bottom: 16px;
  }
</style>
</head>
<body>

<div class="header">
  <h1>{{network_name}} <span style="font-weight:400;color:#7f8c8d;">学术关系网络图谱</span></h1>
  <span class="badge">{{node_count}} 节点 / {{link_count}} 关系</span>
</div>

<div class="sidebar">
  <h2>网络统计</h2>
  <div class="stat-grid">
    <div class="stat-card">
      <div class="value">{{node_count}}</div>
      <div class="label">总节点</div>
    </div>
    <div class="stat-card">
      <div class="value">{{link_count}}</div>
      <div class="label">总关系</div>
    </div>
    <div class="stat-card">
      <div class="value">{{network_density}}</div>
      <div class="label">网络密度</div>
    </div>
    <div class="stat-card">
      <div class="value">{{anomaly_count}}</div>
      <div class="label">异常信号</div>
    </div>
  </div>

  <h2>节点图例</h2>
  {{node_legend}}

  <h2>关系图例</h2>
  {{link_legend}}

  <h2>图层过滤</h2>
  <div class="filter-group">
    {{filter_checkboxes}}
  </div>

  <h2>选中节点详情</h2>
  <div class="node-detail empty" id="node-detail">点击节点查看详细信息</div>

  {{warning_banner}}
</div>

<div id="graph-container"></div>
<div class="tooltip" id="tooltip"></div>

<div class="controls">
  <button onclick="resetZoom()" title="重置视图">⟲</button>
  <button onclick="toggleAnimation()" title="暂停/继续">⏸</button>
</div>

<script>
const networkData = {{network_json}};

const width = document.getElementById('graph-container').clientWidth;
const height = document.getElementById('graph-container').clientHeight;

const svg = d3.select('#graph-container').append('svg')
  .attr('width', width)
  .attr('height', height)
  .attr('viewBox', [0, 0, width, height]);

// Zoom
const g = svg.append('g');
const zoom = d3.zoom()
  .scaleExtent([0.3, 4])
  .on('zoom', (e) => g.attr('transform', e.transform));
svg.call(zoom);

function resetZoom() {
  svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity);
}

let animationEnabled = true;
function toggleAnimation() {
  animationEnabled = !animationEnabled;
  if (animationEnabled) simulation.alpha(0.3).restart();
  else simulation.stop();
}

// Color & radius maps
const nodeTypes = {{node_types_js}};
const linkTypes = {{link_types_js}};

// Filters
const activeTypes = new Set(Object.keys(nodeTypes));

function updateFilters() {
  document.querySelectorAll('.filter-group input').forEach(cb => {
    if (cb.checked) activeTypes.add(cb.value);
    else activeTypes.delete(cb.value);
  });

  const activeNodeIds = new Set(networkData.nodes
    .filter(n => activeTypes.has(n.type))
    .map(n => n.id));

  nodeElements.style('opacity', d => activeNodeIds.has(d.id) ? 1 : 0.05)
    .style('pointer-events', d => activeNodeIds.has(d.id) ? 'all' : 'none');
  linkElements.style('opacity', d =>
    activeNodeIds.has(d.source.id) && activeNodeIds.has(d.target.id) ? 0.6 : 0.02);
  labelElements.style('opacity', d => activeNodeIds.has(d.id) ? 1 : 0.05);
}

// Simulation
const simulation = d3.forceSimulation(networkData.nodes)
  .force('link', d3.forceLink(networkData.links).id(d => d.id).distance(d => {
    return d.type === 'advisor_of' ? 120 : d.type === 'collaborates_with' ? 100 : 140;
  }))
  .force('charge', d3.forceManyBody().strength(d => d.type === 'scholar' ? -800 : -400))
  .force('center', d3.forceCenter(width / 2, height / 2))
  .force('collide', d3.forceCollide().radius(d => (nodeTypes[d.type]?.radius || 10) + 8));

// Links
const linkElements = g.append('g')
  .selectAll('line')
  .data(networkData.links)
  .join('line')
  .attr('stroke', d => linkTypes[d.type]?.color || '#999')
  .attr('stroke-width', d => linkTypes[d.type]?.width || 1)
  .attr('stroke-opacity', 0.6)
  .attr('stroke-dasharray', d => linkTypes[d.type]?.dash ? '5,5' : 'none');

// Nodes
const nodeElements = g.append('g')
  .selectAll('circle')
  .data(networkData.nodes)
  .join('circle')
  .attr('r', d => nodeTypes[d.type]?.radius || 10)
  .attr('fill', d => nodeTypes[d.type]?.color || '#95a5a6')
  .attr('stroke', '#fff')
  .attr('stroke-width', 2)
  .style('cursor', 'pointer')
  .call(d3.drag()
    .on('start', (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
    .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
    .on('end', (e, d) => { if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }));

// Labels
const labelElements = g.append('g')
  .selectAll('text')
  .data(networkData.nodes)
  .join('text')
  .text(d => d.name)
  .attr('font-size', d => d.type === 'scholar' ? 14 : 11)
  .attr('font-weight', d => d.type === 'scholar' ? 700 : 400)
  .attr('fill', '#2c3e50')
  .attr('dx', d => (nodeTypes[d.type]?.radius || 10) + 4)
  .attr('dy', 4)
  .style('pointer-events', 'none')
  .style('text-shadow', '0 0 3px rgba(255,255,255,0.8)');

// Tooltip & detail
const tooltip = d3.select('#tooltip');
const detailBox = document.getElementById('node-detail');

nodeElements
  .on('mouseover', (e, d) => {
    tooltip.style('opacity', 1)
      .html(`<strong>${d.name}</strong><br/>类型: ${nodeTypes[d.type]?.label || d.type}<br/>${d.institution ? '机构: ' + d.institution + '<br/>' : ''}${d.detail || ''}`)
      .style('left', (e.pageX + 12) + 'px')
      .style('top', (e.pageY - 10) + 'px');
  })
  .on('mouseout', () => tooltip.style('opacity', 0))
  .on('click', (e, d) => {
    detailBox.classList.remove('empty');
    detailBox.innerHTML = `<strong style="font-size:15px;color:${nodeTypes[d.type]?.color || '#333'}">${d.name}</strong><br/><span style="color:#7f8c8d;font-size:12px">${nodeTypes[d.type]?.label || d.type}</span><br/><br/>${d.detail || '暂无详细信息'}`;
    e.stopPropagation();
  });

svg.on('click', () => {
  detailBox.classList.add('empty');
  detailBox.textContent = '点击节点查看详细信息';
});

simulation.on('tick', () => {
  linkElements
    .attr('x1', d => d.source.x)
    .attr('y1', d => d.source.y)
    .attr('x2', d => d.target.x)
    .attr('y2', d => d.target.y);
  nodeElements
    .attr('cx', d => d.x)
    .attr('cy', d => d.y);
  labelElements
    .attr('x', d => d.x)
    .attr('y', d => d.y);
});

// Initial filter setup
document.querySelectorAll('.filter-group input').forEach(cb => {
  cb.addEventListener('change', updateFilters);
});
</script>

</body>
</html>
"""


def _build_legend_items(node_types: dict, link_types: dict) -> tuple:
    """Build HTML legend strings."""
    node_legend = ""
    for key, info in node_types.items():
        node_legend += f'<div class="legend-item"><span class="legend-dot" style="background:{info["color"]};"></span>{info["label"]}</div>\n'

    link_legend = ""
    for key, info in link_types.items():
        dash = "border-top: 2px dashed " if info.get("dash") else "background: "
        link_legend += f'<div class="legend-item"><span class="legend-line" style="{dash}{info["color"]};"></span>{info["label"]}</div>\n'

    return node_legend, link_legend


def _build_filter_checkboxes(node_types: dict) -> str:
    """Build filter checkbox HTML."""
    # Only show types that actually exist in data (handled by JS, just emit all)
    boxes = ""
    for key, info in node_types.items():
        if key == "unknown":
            continue
        boxes += f'<label><input type="checkbox" value="{key}" checked> {info["label"]}</label>\n'
    return boxes


def generate_html(network: dict, stats: dict) -> str:
    """Generate the interactive HTML visualization."""
    network_name = network.get("network_name", network.get("scholar_name", "未知网络"))
    nodes = network["nodes"]
    links = network["links"]

    # Serialize network data for JS embedding
    # Convert link source/target from objects back to ids for D3
    d3_nodes = []
    d3_links = []
    id_to_node = {}
    for n in nodes:
        d3_nodes.append({
            "id": n["id"],
            "name": n["name"],
            "type": n["type"],
            "institution": n.get("institution", ""),
            "detail": n.get("detail", ""),
        })
        id_to_node[n["id"]] = n

    for l in links:
        d3_links.append({
            "source": l["source"],
            "target": l["target"],
            "type": l["type"],
            "detail": l.get("detail", ""),
            "weight": l.get("weight", 1),
            "is_anomaly": l.get("is_anomaly", False),
        })

    d3_data = {"nodes": d3_nodes, "links": d3_links}
    network_json = json.dumps(d3_data, ensure_ascii=False)
    node_types_js = json.dumps(NODE_TYPES, ensure_ascii=False)
    link_types_js = json.dumps(LINK_TYPES, ensure_ascii=False)

    node_legend, link_legend = _build_legend_items(NODE_TYPES, LINK_TYPES)
    filter_checkboxes = _build_filter_checkboxes(NODE_TYPES)

    # Warning banner if anomalies detected
    warning_html = ""
    if stats["anomaly_link_count"] > 0:
        warning_html = (
            f'<div class="warning-banner">⚠️ 检测到 {stats["anomaly_link_count"]} 条引用异常信号，'
            f'包括高频互引或集中引用。建议结合 citation_profiler.py 输出进行交叉验证。</div>'
        )

    html = HTML_TEMPLATE
    html = html.replace("{{network_name}}", network_name)
    html = html.replace("{{node_count}}", str(len(nodes)))
    html = html.replace("{{link_count}}", str(len(links)))
    html = html.replace("{{network_density}}", f"{stats['density']:.3f}")
    html = html.replace("{{anomaly_count}}", str(stats["anomaly_link_count"]))
    html = html.replace("{{network_json}}", network_json)
    html = html.replace("{{node_types_js}}", node_types_js)
    html = html.replace("{{link_types_js}}", link_types_js)
    html = html.replace("{{node_legend}}", node_legend)
    html = html.replace("{{link_legend}}", link_legend)
    html = html.replace("{{filter_checkboxes}}", filter_checkboxes)
    html = html.replace("{{warning_banner}}", warning_html)

    return html


# ── CLI ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Visualize scholar or corruption relationship network")
    parser.add_argument("--input", "-i", required=True, help="Path to scholar_data.json or corruption_network.json")
    parser.add_argument("--output-dir", "-o", default=".", help="Output directory for HTML and JSON")
    parser.add_argument("--prefix", "-p", default="", help="Filename prefix")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if _is_corruption_network(data):
        network_name = data.get("network_name", "corruption_network")
    else:
        network_name = data.get("name", "scholar")
    prefix = args.prefix or network_name

    # Build network
    print(f"[INFO] Building network for: {network_name}")
    network = build_network(data)
    stats = compute_stats(network)

    print(f"[INFO] Nodes: {network['node_count']}, Links: {network['link_count']}")
    print(f"[INFO] Type distribution: {stats['type_distribution']}")
    print(f"[INFO] Anomaly links: {stats['anomaly_link_count']}")

    # Output directory
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save JSON network data
    json_path = out_dir / f"{prefix}_network.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(network, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Network JSON saved: {json_path}")

    # Save HTML visualization
    html_path = out_dir / f"{prefix}_network.html"
    html = generate_html(network, stats)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[INFO] Network HTML saved: {html_path}")

    # Summary
    print(f"\n[SUCCESS] Relationship network visualization complete.")
    print(f"  - Open {html_path.name} in a browser to view the interactive graph.")
    print(f"  - Raw network data: {json_path.name}")


if __name__ == "__main__":
    main()
