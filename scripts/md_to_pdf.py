#!/usr/bin/env python3
"""
md_to_pdf.py — Markdown 调查报告 → 精美 PDF

功能：
  1. 解析 Markdown 报告（含 YAML frontmatter）
  2. 自动识别 <!--chart:...--> 注释，调用 chart_generator 生成图表
  3. 应用 A4 样式模板（封面、目录、页眉页脚、表格美化）
  4. Playwright 渲染为 PDF

用法：
    python3 scripts/md_to_pdf.py --input reports/报告.md --output reports/报告.pdf
    python3 scripts/md_to_pdf.py --input reports/报告.md --output reports/报告.pdf --case-dir ./cases/xxx

依赖（全部已安装）：
    markdown, playwright, matplotlib, numpy, networkx
"""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from datetime import datetime

import markdown
from markdown.extensions.tables import TableExtension
from playwright.sync_api import sync_playwright

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from chart_generator import generate_chart


# ──────────────────────────────────────────────
# HTML/CSS 模板（复刻CASE_020 PDF 风格）
# ──────────────────────────────────────────────
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
/* ========== 页面设置 ========== */
@page {{
  size: A4;
  margin: 25mm 20mm 25mm 20mm;
  @top-center {{
    content: string(chapter);
    font-size: 9pt;
    color: #666;
    border-bottom: 0.5pt solid #ccc;
    padding-bottom: 5mm;
  }}
  @bottom-center {{
    content: counter(page);
    font-size: 9pt;
    color: #666;
  }}
}}

@page :first {{
  @top-center {{ content: none; }}
  @bottom-center {{ content: none; }}
}}

@page cover {{
  margin: 0;
  @top-center {{ content: none; }}
  @bottom-center {{ content: none; }}
}}

@page toc {{
  @top-center {{ content: "目 录"; }}
}}

/* ========== 基础样式 ========== */
* {{
  box-sizing: border-box;
}}

body {{
  font-family: "Noto Serif CJK SC", "Source Han Serif SC", "SimSun", "STSong", serif;
  font-size: 11pt;
  line-height: 1.8;
  color: #333;
  text-align: justify;
}}

/* ========== 封面 ========== */
.cover {{
  page: cover;
  width: 210mm;
  height: 297mm;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
  padding: 40mm 25mm;
  background: linear-gradient(180deg, #f8f9fa 0%, #fff 40%, #fff 100%);
}}

.cover-badge {{
  font-size: 10pt;
  color: #888;
  letter-spacing: 4pt;
  text-transform: uppercase;
  margin-bottom: 15mm;
  border: 1pt solid #ccc;
  padding: 3mm 8mm;
}}

.cover-title {{
  font-size: 28pt;
  font-weight: bold;
  color: #1a1a1a;
  margin-bottom: 8mm;
  letter-spacing: 2pt;
  line-height: 1.3;
}}

.cover-subtitle {{
  font-size: 12pt;
  color: #555;
  margin-bottom: 20mm;
  max-width: 140mm;
}}

.cover-meta {{
  margin-top: 15mm;
  text-align: left;
  width: 140mm;
  font-size: 10.5pt;
  color: #444;
  line-height: 2.2;
}}

.cover-meta-item {{
  border-bottom: 0.3pt solid #ddd;
  padding: 2mm 0;
}}

.cover-meta-label {{
  color: #888;
  display: inline-block;
  width: 6em;
}}

/* ========== 目录 ========== */
.toc-page {{
  page: toc;
  page-break-before: always;
}}

.toc-title {{
  font-size: 18pt;
  font-weight: bold;
  text-align: center;
  margin-bottom: 15mm;
  letter-spacing: 8pt;
}}

.toc-item {{
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 2.5mm 0;
  font-size: 10.5pt;
  border-bottom: 0.3pt dotted #ddd;
}}

.toc-item-l1 {{
  font-weight: bold;
  font-size: 11pt;
}}

.toc-item-l2 {{
  padding-left: 8mm;
}}

.toc-item-l3 {{
  padding-left: 16mm;
  font-size: 10pt;
  color: #555;
}}

.toc-page-num {{
  color: #666;
}}

/* ========== 正文标题 ========== */
h1 {{
  string-set: chapter content();
  font-size: 18pt;
  font-weight: bold;
  color: #1a1a1a;
  margin-top: 0;
  margin-bottom: 8mm;
  padding-bottom: 3mm;
  border-bottom: 1.5pt solid #1a1a1a;
  page-break-before: always;
  page-break-after: avoid;
}}

h1:first-of-type {{
  page-break-before: auto;
}}

h2 {{
  font-size: 14pt;
  font-weight: bold;
  color: #222;
  margin-top: 10mm;
  margin-bottom: 5mm;
  page-break-after: avoid;
}}

h3 {{
  font-size: 12pt;
  font-weight: bold;
  color: #333;
  margin-top: 8mm;
  margin-bottom: 4mm;
  page-break-after: avoid;
}}

h4 {{
  font-size: 11pt;
  font-weight: bold;
  color: #444;
  margin-top: 6mm;
  margin-bottom: 3mm;
}}

/* ========== 段落与列表 ========== */
p {{
  margin: 0 0 4mm 0;
  text-indent: 2em;
}}

p.no-indent {{
  text-indent: 0;
}}

ul, ol {{
  margin: 3mm 0 4mm 0;
  padding-left: 6mm;
}}

li {{
  margin-bottom: 1.5mm;
}}

/* ========== 表格 ========== */
table {{
  width: 100%;
  border-collapse: collapse;
  margin: 5mm 0;
  font-size: 9.5pt;
  page-break-inside: avoid;
}}

thead {{
  display: table-header-group;
}}

th {{
  background-color: #f0f0f0;
  font-weight: bold;
  text-align: left;
  padding: 2.5mm 3mm;
  border-top: 1pt solid #333;
  border-bottom: 0.8pt solid #333;
}}

td {{
  padding: 2mm 3mm;
  border-bottom: 0.3pt solid #ccc;
  vertical-align: top;
}}

tr:nth-child(even) td {{
  background-color: #fafafa;
}}

/* ========== 图片与图表 ========== */
.figure {{
  margin: 6mm 0;
  text-align: center;
  page-break-inside: avoid;
}}

.figure img {{
  max-width: 100%;
  max-height: 180mm;
}}

.figure-caption {{
  font-size: 9.5pt;
  color: #555;
  margin-top: 2mm;
  text-align: center;
}}

/* ========== 引用块 ========== */
blockquote {{
  margin: 4mm 0;
  padding: 3mm 5mm;
  border-left: 2pt solid #4A90D9;
  background-color: #f8f9fa;
  font-size: 10pt;
  color: #444;
}}

blockquote p {{
  text-indent: 0;
  margin: 0;
}}

/* ========== 代码 ========== */
code {{
  font-family: "Consolas", "Monaco", monospace;
  font-size: 9pt;
  background-color: #f4f4f4;
  padding: 0.5mm 1.5mm;
  border-radius: 1mm;
}}

pre {{
  background-color: #f4f4f4;
  padding: 3mm;
  overflow-x: auto;
  font-size: 8.5pt;
  line-height: 1.5;
  border: 0.3pt solid #ddd;
}}

pre code {{
  background: none;
  padding: 0;
}}

/* ========== 水平线 ========== */
hr {{
  border: none;
  border-top: 0.5pt solid #ccc;
  margin: 8mm 0;
}}

/* ========== 强调 ========== */
strong {{
  font-weight: bold;
  color: #1a1a1a;
}}

em {{
  font-style: italic;
}}

/* ========== 链接 ========== */
a {{
  color: #4A90D9;
  text-decoration: none;
}}

/* ========== 分页控制 ========== */
.page-break {{
  page-break-after: always;
}}

.avoid-break {{
  page-break-inside: avoid;
}}
</style>
</head>
<body>
{cover_html}
{toc_html}
{content_html}
</body>
</html>
"""

COVER_TEMPLATE = """
<div class="cover">
  <div class="cover-badge">最终综合调查报告</div>
  <div class="cover-title">{title}</div>
  <div class="cover-subtitle">{subtitle}</div>
  <div class="cover-meta">
    <div class="cover-meta-item"><span class="cover-meta-label">调查对象：</span>{subject}</div>
    <div class="cover-meta-item"><span class="cover-meta-label">所属机构：</span>{institution}</div>
    <div class="cover-meta-item"><span class="cover-meta-label">调查日期：</span>{date}</div>
    <div class="cover-meta-item"><span class="cover-meta-label">报告性质：</span>{nature}</div>
  </div>
</div>
"""

TOC_TEMPLATE = """
<div class="toc-page">
  <div class="toc-title">目 录</div>
  {toc_items}
</div>
"""


# ──────────────────────────────────────────────
# 核心函数
# ──────────────────────────────────────────────
def parse_frontmatter(md_text: str) -> tuple[dict, str]:
    """解析 YAML frontmatter，返回 (meta, 正文)"""
    pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
    match = re.match(pattern, md_text, re.DOTALL)
    if match:
        yaml_text = match.group(1)
        body = match.group(2)
        # 简单解析 YAML（只处理 key: value 和 key: [value1, value2]）
        meta = {}
        for line in yaml_text.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if ':' in line:
                key, val = line.split(':', 1)
                key = key.strip()
                val = val.strip()
                # 去除引号
                if val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                elif val.startswith("'") and val.endswith("'"):
                    val = val[1:-1]
                meta[key] = val
        return meta, body
    return {}, md_text


def extract_chapters(html: str) -> list[dict]:
    """从 HTML 中提取章节标题，用于生成目录"""
    chapters = []
    h1_pattern = re.compile(r'<h1[^>]*>(.*?)</h1>')
    h2_pattern = re.compile(r'<h2[^>]*>(.*?)</h2>')

    # 先找 h1
    pos = 0
    for m in h1_pattern.finditer(html):
        title = re.sub(r'<[^>]+>', '', m.group(1))
        chapters.append({"level": 1, "title": title, "pos": m.start()})

    # 再找 h2（只在 h1 之间）
    for m in h2_pattern.finditer(html):
        title = re.sub(r'<[^>]+>', '', m.group(1))
        chapters.append({"level": 2, "title": title, "pos": m.start()})

    chapters.sort(key=lambda x: x["pos"])
    return chapters


def generate_toc_html(chapters: list[dict]) -> str:
    """生成目录 HTML"""
    items = []
    for i, ch in enumerate(chapters, 1):
        level_class = f"toc-item-l{ch['level']}"
        items.append(f'<div class="toc-item {level_class}">{ch["title"]}<span class="toc-page-num"></span></div>')
    return TOC_TEMPLATE.format(toc_items="\n".join(items))


def process_charts(md_body: str, output_dir: str) -> str:
    """解析图表注释，生成图片，替换为 img 标签"""
    chart_pattern = re.compile(r'<!--chart:(.*?)-->')
    chart_index = 0

    def replace_chart(match):
        nonlocal chart_index
        annotation = match.group(0)
        chart_path = generate_chart(annotation, output_dir, chart_index)
        chart_index += 1

        if chart_path:
            # 提取标题用于 caption
            title_match = re.search(r'title="([^"]+)"', annotation)
            caption = title_match.group(1) if title_match else f"图 {chart_index}"
            rel_path = os.path.relpath(chart_path, output_dir)
            return f'\n<div class="figure avoid-break"><img src="file://{chart_path}" alt="{caption}"><div class="figure-caption">图 {chart_index} {caption}</div></div>\n'
        else:
            return f'\n<p style="color:red">[图表生成失败]</p>\n'

    return chart_pattern.sub(replace_chart, md_body)


def md_to_pdf(input_path: str, output_path: str, case_dir: str = None):
    """主函数：Markdown → PDF"""
    input_path = Path(input_path).resolve()
    output_path = Path(output_path).resolve()

    if not input_path.exists():
        print(f"[错误] 输入文件不存在: {input_path}")
        sys.exit(1)

    # 读取 Markdown
    with open(input_path, 'r', encoding='utf-8') as f:
        md_text = f.read()

    # 解析 frontmatter
    meta, md_body = parse_frontmatter(md_text)

    # 确定输出目录（用于存放图表）
    figures_dir = Path(case_dir).resolve() / "reports" / "figures" if case_dir else input_path.parent / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    # 处理图表注释
    md_body = process_charts(md_body, str(figures_dir))

    # Markdown → HTML
    md = markdown.Markdown(extensions=['tables', 'fenced_code', 'toc'])
    content_html = md.convert(md_body)

    # 清理 markdown 生成的 ID（避免冲突）
    content_html = re.sub(r' id="[^"]*"', '', content_html)

    # 提取章节生成目录
    chapters = extract_chapters(content_html)
    toc_html = generate_toc_html(chapters)

    # 生成封面
    title = meta.get('title', meta.get('报告标题', input_path.stem))
    subtitle = meta.get('subtitle', meta.get('副标题', ''))
    subject = meta.get('subject', meta.get('调查对象', ''))
    institution = meta.get('institution', meta.get('所属机构', ''))
    date = meta.get('date', meta.get('调查日期', datetime.now().strftime('%Y年%m月%d日')))
    nature = meta.get('nature', meta.get('报告性质', '公开信息综合调查报告'))

    cover_html = COVER_TEMPLATE.format(
        title=title,
        subtitle=subtitle,
        subject=subject,
        institution=institution,
        date=date,
        nature=nature,
    )

    # 组装完整 HTML
    full_html = HTML_TEMPLATE.format(
        title=title,
        cover_html=cover_html,
        toc_html=toc_html,
        content_html=f'<div class="content">{content_html}</div>',
    )

    # 临时 HTML 文件
    tmp_html = output_path.with_suffix('.tmp.html')
    with open(tmp_html, 'w', encoding='utf-8') as f:
        f.write(full_html)

    # Playwright 渲染 PDF
    print(f"[md_to_pdf] 正在渲染 PDF: {output_path}")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f'file://{tmp_html}')
        page.wait_for_load_state('networkidle')

        # 等待字体和图片加载
        page.wait_for_timeout(1000)

        page.pdf(
            path=str(output_path),
            format='A4',
            margin={
                'top': '25mm',
                'right': '20mm',
                'bottom': '25mm',
                'left': '20mm',
            },
            print_background=True,
            display_header_footer=True,
            header_template='<div style="font-size:9px; width:100%; text-align:center; color:#666; border-bottom:0.5px solid #ccc; padding-bottom:5px;"><span class="title"></span></div>',
            footer_template='<div style="font-size:9px; width:100%; text-align:center; color:#666;"><span class="pageNumber"></span> / <span class="totalPages"></span></div>',
        )
        browser.close()

    # 清理临时文件
    tmp_html.unlink(missing_ok=True)

    print(f"[md_to_pdf] ✅ PDF 生成完成: {output_path}")
    return str(output_path)


def main():
    parser = argparse.ArgumentParser(description="Markdown 调查报告 → 精美 PDF")
    parser.add_argument("--input", "-i", required=True, help="输入的 Markdown 报告路径")
    parser.add_argument("--output", "-o", required=True, help="输出的 PDF 路径")
    parser.add_argument("--case-dir", "-d", help="案件目录（用于存放图表）")
    args = parser.parse_args()

    md_to_pdf(args.input, args.output, args.case_dir)


if __name__ == "__main__":
    main()
