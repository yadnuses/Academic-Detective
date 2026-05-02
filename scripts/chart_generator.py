#!/usr/bin/env python3
"""
chart_generator.py — 自动图表生成模块

支持从 Markdown 注释自动生成 matplotlib 图表：
  radar    雷达图（六维质量评分等）
  pie      饼图（论文署名结构等）
  bar      柱状图
  heatmap  热力图（风险评估矩阵等）
  timeline 时间线（事件序列）
  network  网络关系图（导师-学生-合作者）

用法（被 md_to_pdf.py 调用）：
    from chart_generator import generate_chart
    path = generate_chart('<!--chart:radar dimensions=[...] scores=[...]-->', './figures/', 0)
"""

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Optional

import matplotlib
matplotlib.use('Agg')  # 无GUI后端

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# 中文字体设置（尝试多种字体，兼容不同系统）
font_candidates = ['SimHei', 'Heiti TC', 'STHeiti', 'WenQuanYi Micro Hei',
                   'DejaVu Sans', 'Arial Unicode MS', 'sans-serif']
available_fonts = [f for f in font_candidates if f in [f.name for f in matplotlib.font_manager.fontManager.ttflist]]
plt.rcParams['font.sans-serif'] = available_fonts if available_fonts else ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


def generate_radar(config: dict, output_path: str) -> str:
    """生成雷达图"""
    dimensions = config.get("dimensions", [])
    scores = config.get("scores", [])
    title = config.get("title", "雷达图")
    
    if len(dimensions) != len(scores):
        raise ValueError("dimensions 和 scores 长度不一致")
    if not dimensions:
        raise ValueError("dimensions 不能为空")
    
    angles = np.linspace(0, 2 * np.pi, len(dimensions), endpoint=False).tolist()
    scores_plot = scores + [scores[0]]
    angles += angles[:1]
    
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.fill(angles, scores_plot, color='#4A90D9', alpha=0.25)
    ax.plot(angles, scores_plot, color='#2E5C8A', linewidth=2, marker='o', markersize=6)
    
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(dimensions, fontsize=10)
    ax.set_ylim(0, max(scores + [10]))
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    ax.grid(True, linestyle='--', alpha=0.5)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    return output_path


def generate_pie(config: dict, output_path: str) -> str:
    """生成饼图"""
    labels = config.get("labels", [])
    values = config.get("values", [])
    title = config.get("title", "饼图")
    colors = config.get("colors", ['#4A90D9', '#50C878', '#F5A623', '#E85D75', '#9B59B6', '#1ABC9C'])
    
    fig, ax = plt.subplots(figsize=(6, 6))
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, autopct='%1.1f%%',
        colors=colors[:len(values)], startangle=90,
        textprops={'fontsize': 10}
    )
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
    ax.set_title(title, fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    return output_path


def generate_bar(config: dict, output_path: str) -> str:
    """生成柱状图"""
    labels = config.get("labels", [])
    values = config.get("values", [])
    title = config.get("title", "柱状图")
    xlabel = config.get("xlabel", "")
    ylabel = config.get("ylabel", "")
    color = config.get("color", "#4A90D9")
    
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, values, color=color, edgecolor='white', linewidth=0.5)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}', ha='center', va='bottom', fontsize=9)
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    return output_path


def generate_heatmap(config: dict, output_path: str) -> str:
    """生成热力图"""
    matrix = config.get("matrix", [[]])
    row_labels = config.get("row_labels", [])
    col_labels = config.get("col_labels", [])
    title = config.get("title", "热力图")
    
    fig, ax = plt.subplots(figsize=(max(8, len(col_labels)*1.2), max(6, len(row_labels)*0.8)))
    im = ax.imshow(matrix, cmap='RdYlGn_r', aspect='auto', vmin=0, vmax=10)
    
    ax.set_xticks(np.arange(len(col_labels)))
    ax.set_yticks(np.arange(len(row_labels)))
    ax.set_xticklabels(col_labels, fontsize=10)
    ax.set_yticklabels(row_labels, fontsize=10)
    
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
    
    for i in range(len(row_labels)):
        for j in range(len(col_labels)):
            val = matrix[i][j]
            text_color = "white" if val < 3 or val > 7 else "black"
            ax.text(j, i, f'{val:.1f}', ha="center", va="center", 
                   color=text_color, fontsize=9, fontweight='bold')
    
    ax.set_title(title, fontsize=14, fontweight='bold')
    fig.colorbar(im, ax=ax, shrink=0.8)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    return output_path


def generate_timeline(config: dict, output_path: str) -> str:
    """生成时间线"""
    events = config.get("events", [])
    title = config.get("title", "时间线")
    
    fig, ax = plt.subplots(figsize=(max(10, len(events)*2), 4))
    colors = ['#4A90D9', '#50C878', '#F5A623', '#E85D75', '#9B59B6', '#1ABC9C']
    
    for i, event in enumerate(events):
        y = 1 if i % 2 == 0 else -1
        color = colors[i % len(colors)]
        date = event.get("date", i)
        label = event.get("label", "")
        
        ax.scatter(date, 0, s=120, c=color, zorder=3, edgecolors='white', linewidths=2)
        ax.plot([date, date], [0, y*0.7], color=color, linestyle='-', alpha=0.6, linewidth=2)
        ax.text(date, y*0.85, label, ha='center', va='bottom' if y > 0 else 'top',
                fontsize=9, bbox=dict(boxstyle='round,pad=0.4', facecolor=color, alpha=0.15, edgecolor=color))
    
    ax.axhline(y=0, color='#666666', linestyle='-', linewidth=2)
    ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    return output_path


def generate_network(config: dict, output_path: str) -> str:
    """生成网络关系图"""
    import networkx as nx
    
    nodes = config.get("nodes", [])
    edges = config.get("edges", [])
    title = config.get("title", "网络关系图")
    
    G = nx.Graph()
    for node in nodes:
        G.add_node(node["id"], label=node.get("label", node["id"]),
                  node_type=node.get("type", "default"))
    for edge in edges:
        G.add_edge(edge["from"], edge["to"], relation=edge.get("relation", ""))
    
    fig, ax = plt.subplots(figsize=(10, 8))
    pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
    
    node_colors = []
    color_map = {
        "scholar": "#E85D75",
        "mentor": "#4A90D9",
        "student": "#50C878",
        "collaborator": "#F5A623",
        "institution": "#9B59B6",
        "default": "#95A5A6"
    }
    for node in G.nodes():
        node_type = G.nodes[node].get("node_type", "default")
        node_colors.append(color_map.get(node_type, "#95A5A6"))
    
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=1200, alpha=0.9, ax=ax)
    nx.draw_networkx_edges(G, pos, width=1.5, alpha=0.4, edge_color='gray', ax=ax)
    
    labels = {n: G.nodes[n].get("label", n) for n in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels, font_size=9, ax=ax)
    
    # 图例
    legend_elements = [mpatches.Patch(facecolor=color_map[k], label=k) 
                      for k in set(nx.get_node_attributes(G, 'node_type').values())]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=9)
    
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.axis('off')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    return output_path


CHART_GENERATORS = {
    "radar": generate_radar,
    "pie": generate_pie,
    "bar": generate_bar,
    "heatmap": generate_heatmap,
    "timeline": generate_timeline,
    "network": generate_network,
}


def generate_chart(annotation_text: str, output_dir: str, index: int) -> Optional[str]:
    """
    解析 Markdown 图表注释并生成图表。

    支持的注释格式：
      <!--chart:radar dimensions=["a","b"] scores=[1,2] title="..."-->
      <!--chart:pie labels=["x","y"] values=[10,20] title="..."-->
      <!--chart:heatmap matrix=[[1,2],[3,4]] row_labels=["a","b"] col_labels=["x","y"]-->
      <!--chart:timeline events=[{"date":1,"label":"事件"}] title="..."-->
      <!--chart:network nodes=[{"id":"A","type":"scholar"}] edges=[{"from":"A","to":"B"}]-->

    返回：生成的图片绝对路径，或 None（解析/生成失败）
    """
    try:
        match = re.search(r'<!--chart:(\w+)\s+(.+?)-->', annotation_text, re.DOTALL)
        if not match:
            return None

        chart_type = match.group(1)
        config_text = match.group(2).strip()

        # 安全解析：支持嵌套列表的 key=value 对
        config = {}
        keys = re.findall(r'(\w+)\s*=', config_text)
        for i, key in enumerate(keys):
            key_pos = config_text.find(f'{key}=', 0 if i == 0 else config_text.find(f'{keys[i-1]}=') + len(keys[i-1]) + 1)
            eq_pos = config_text.find('=', key_pos)
            val_start = eq_pos + 1
            if i + 1 < len(keys):
                next_key_pos = config_text.find(f'{keys[i+1]}=', val_start)
                val_end = next_key_pos
            else:
                val_end = len(config_text)
            val = config_text[val_start:val_end].strip()

            if val.startswith('"') and val.endswith('"'):
                config[key] = val[1:-1]
            elif val.startswith('[') and val.endswith(']'):
                config[key] = json.loads(val)
            elif val.startswith('{') and val.endswith('}'):
                config[key] = json.loads(val)
            else:
                try:
                    config[key] = json.loads(val)
                except json.JSONDecodeError:
                    config[key] = val

        if chart_type not in CHART_GENERATORS:
            print(f"[chart_generator] 未知图表类型: {chart_type}")
            return None

        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"chart_{index:03d}_{chart_type}.png")

        return CHART_GENERATORS[chart_type](config, output_path)

    except Exception as e:
        print(f"[chart_generator] 图表生成失败: {e}")
        return None


if __name__ == "__main__":
    import tempfile
    test_dir = tempfile.mkdtemp()

    # 测试雷达图
    radar_ann = '<!--chart:radar dimensions=["原创性","严谨性","证据质量","逻辑结构","文献规范","表达清晰"] scores=[9.2,9.0,8.8,9.1,8.5,8.7] title="六维质量评分"-->'
    p = generate_chart(radar_ann, test_dir, 0)
    print(f"雷达图: {p}")

    # 测试饼图
    pie_ann = '<!--chart:pie labels=["第一作者","通信作者","其他作者"] values=[8,5,35] title="论文署名结构"-->'
    p = generate_chart(pie_ann, test_dir, 1)
    print(f"饼图: {p}")

    # 测试热力图
    heat_ann = '<!--chart:heatmap matrix=[[9.5,3.2],[2.1,8.7]] row_labels=["师德","学术"] col_labels=["严重性","可信度"] title="风险评估矩阵"-->'
    p = generate_chart(heat_ann, test_dir, 2)
    print(f"热力图: {p}")

    print(f"\n测试图表已保存到: {test_dir}")
