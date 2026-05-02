#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import json
import pdfplumber

PDF_DIR = "/Users/xiaoy/Downloads/调查名单/谷文萍/谷文萍论文"
OUTPUT_MD = "/Users/xiaoy/Downloads/调查名单/谷文萍/谷文萍论文作者分析_v5.md"
OUTPUT_JSON = "/Users/xiaoy/Downloads/调查名单/谷文萍/谷文萍论文作者分析_v5.json"

EXCLUDE_WORDS = set([
    '摘要', '关键词', '目的', '方法', '结果', '结论', '引言', '正文', '参考文献',
    '杂志', '学报', '医院', '大学', '研究所', '学院', '中心', '长沙', '北京', '广州',
    '研究', '分析', '探讨', '观察', '报告', '例', '患者', '对照', '治疗',
    '检查', '检测', '水平', '表达', '影响', '作用', '机制', '关系', '相关性',
    '进展', '综述', '通讯', '作者', '基金', '项目', '单位', '实验', '临床',
    '神经', '内科', '外科', '医学', '中国', '中华', '国际', '实用',
    '脑缺血', '脑血管', '脑梗死', '脑出血', '卒中', '癫痫', '疾病'
])

def extract_text_from_pdf(pdf_path):
    texts = {}
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            texts['total_pages'] = total_pages
            all_pages_text = []
            for i in range(total_pages):
                page_text = pdf.pages[i].extract_text()
                if page_text:
                    all_pages_text.append(page_text)
                    texts[f'page_{i+1}'] = page_text
            texts['all_text'] = "\n".join(all_pages_text)
    except Exception as e:
        texts['error'] = str(e)
    return texts

def preprocess_line(line):
    """Preprocess line to normalize spaces and remove special chars inside names"""
    # Remove various star/special symbols
    line = re.sub(r'[∗★☆✱✲✳✴✵✶✷✸✹✺✻✼✽✾✿❃❉❊❋*#]', '', line)
    # Remove internal spaces in 2-4 char Chinese sequences (e.g., "李 伟" -> "李伟")
    # Pattern: Chinese char, space, Chinese char
    line = re.sub(r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])', r'\1\2', line)
    return line

def clean_name(p):
    if not p:
        return ""
    p = re.sub(r'^[①②③④⑤⑥⑦⑧⑨⑩¹²³⁴⁵⁶⁷⁸⁹⁰\d\.\s,，、；;]+', '', p)
    p = re.sub(r'[①②③④⑤⑥⑦⑧⑨⑩¹²³⁴⁵⁶⁷⁸⁹⁰\d\.\s,，、；;]+$', '', p)
    p = re.sub(r'[（(].*?[）)]', '', p)
    p = re.sub(r'\s*[\d,，、；;\s]+$', '', p)
    p = p.strip()
    return p

def parse_names_from_line(line):
    if not line:
        return []
    line = preprocess_line(line)
    parts = re.split(r'[，,、；;\s]+', line)
    names = []
    for p in parts:
        p = clean_name(p)
        if p and 2 <= len(p) <= 4 and re.search(r'[\u4e00-\u9fff]', p):
            if p not in EXCLUDE_WORDS and not any(w in p for w in ['杂志', '医院', '大学', '研究所', '长沙', '北京', '广州', '神经', '内科']):
                names.append(p)
    return names

def is_likely_author_line(line):
    line = preprocess_line(line)
    line_stripped = line.strip()
    if len(line_stripped) > 150:
        return False
    if '，' not in line_stripped and ',' not in line_stripped and ' ' not in line_stripped:
        return False
    names = parse_names_from_line(line_stripped)
    if len(names) >= 2:
        name_chars = sum(len(n) for n in names)
        if name_chars / max(len(line_stripped), 1) > 0.3:
            return True
    return False

def contains_institution_prefix(line):
    return bool(re.match(r'^(中南大学|首都医科|中山大学|复旦大学|哈尔滨|南京大学|北京协和|北京|广州|长沙|研究所|医院|学院|中心|1\s+|\d+\s*)', line.strip()))

def find_authors(first_page, all_text, filename):
    strategies = []
    
    if first_page:
        lines = first_page.split('\n')
        
        # Strategy A: Find lines containing 谷文萍 in first 25 lines
        for i, line in enumerate(lines[:25]):
            if '谷文萍' in line:
                line_pp = preprocess_line(line)
                names = parse_names_from_line(line_pp)
                if names and '谷文萍' in names:
                    score = len(names)
                    if contains_institution_prefix(line):
                        score -= 10
                    strategies.append((score, 'guwenping_line_top', names, line.strip()))
                    
                    # Try merging with adjacent lines
                    merged_down = line.strip()
                    for j in range(i+1, min(len(lines), i+4)):
                        next_line = lines[j].strip()
                        next_pp = preprocess_line(next_line)
                        if is_likely_author_line(next_line) or (',' in next_pp or '，' in next_pp or len(parse_names_from_line(next_pp)) >= 2):
                            # Check it's not an institution line
                            if not contains_institution_prefix(next_line):
                                merged_down += " " + next_line
                                merged_names = parse_names_from_line(merged_down)
                                if merged_names and '谷文萍' in merged_names:
                                    strategies.append((len(merged_names), 'guwenping_merged_down', merged_names, merged_down))
                            else:
                                break
                        else:
                            break
                    
                    merged_up = line.strip()
                    for j in range(i-1, max(-1, i-4), -1):
                        prev_line = lines[j].strip()
                        prev_pp = preprocess_line(prev_line)
                        if is_likely_author_line(prev_line) or (',' in prev_pp or '，' in prev_pp or len(parse_names_from_line(prev_pp)) >= 2):
                            if not contains_institution_prefix(prev_line):
                                merged_up = prev_line + " " + merged_up
                                merged_names_up = parse_names_from_line(merged_up)
                                if merged_names_up and '谷文萍' in merged_names_up:
                                    strategies.append((len(merged_names_up), 'guwenping_merged_up', merged_names_up, merged_up))
                            else:
                                break
                        else:
                            break
        
        # Strategy B: Before clear markers
        for i, line in enumerate(lines):
            if any(k in line for k in ['作者单位', '中南大学湘雅医院', '首都医科大学', '中山大学', '复旦大学', '哈尔滨', '南京大学', '北京协和', '摘要', '目的', 'ABSTRACT', 'Objective', '【摘要']):
                for j in range(i-1, max(-1, i-6), -1):
                    candidate = lines[j].strip()
                    if candidate and len(candidate) < 120 and not candidate.startswith('【'):
                        names = parse_names_from_line(candidate)
                        if len(names) >= 2:
                            strategies.append((len(names), 'before_marker', names, candidate))
    
    # Strategy C: Anywhere in text
    if all_text and not strategies:
        lines = all_text.split('\n')
        for i, line in enumerate(lines):
            if '谷文萍' in line and len(line.strip()) < 120:
                line_pp = preprocess_line(line)
                names = parse_names_from_line(line_pp)
                if names and '谷文萍' in names and len(names) >= 2:
                    score = len(names)
                    if contains_institution_prefix(line):
                        score -= 10
                    strategies.append((score, 'guwenping_anywhere', names, line.strip()))
    
    strategies.sort(reverse=True, key=lambda x: x[0])
    
    best_names = []
    best_source = None
    best_line = ""
    
    for score, source, names, line in strategies:
        if not best_names:
            best_names = names
            best_source = source
            best_line = line
    
    if not best_names and '_谷文萍.pdf' in filename and first_page:
        lines = first_page.split('\n')
        for line in lines:
            if '谷文萍' in line:
                names = parse_names_from_line(line)
                if names and '谷文萍' in names:
                    best_names = names
                    best_source = 'filename_fallback'
                    best_line = line
                    break
    
    return best_names, best_source, best_line

def extract_title(first_page):
    if not first_page:
        return ""
    lines = first_page.split('\n')
    candidates = []
    for line in lines[:25]:
        line = line.strip()
        if not line or line.isdigit():
            continue
        if re.search(r'^(中华|中国|国际|临床|实用|医学|杂志|JOURNAL|第\d+卷|Vol\.|No\.|DOI|收稿日期|中图分类号|文章编号|【)', line, re.IGNORECASE):
            continue
        if len(line) < 5:
            continue
        if re.search(r'[\u4e00-\u9fff]', line) and len(line) > 10:
            candidates.append(line)
        elif re.search(r'[a-zA-Z]', line) and len(line) > 20 and not line.startswith('http'):
            candidates.append(line)
    if candidates:
        return max(candidates, key=len)
    return ""

def extract_year(text):
    if not text:
        return ""
    matches = re.findall(r'(20\d{2})\s*年?', text[:2000])
    if matches:
        return matches[0]
    matches = re.findall(r'(19\d{2}|20\d{2})[;,]', text[:1000])
    if matches:
        return matches[0]
    return ""

def extract_journal(text):
    if not text:
        return ""
    lines = text.split('\n')[:20]
    for line in lines:
        line = line.strip()
        if re.search(r'(杂志|Journal|学报|Letters|Medicine|Neurology|Stroke|Diseases|Biomedicine|医师|中华|中国)', line, re.IGNORECASE):
            if 3 < len(line) < 100:
                return line
    return ""

def find_sections(all_text):
    if not all_text:
        return {}
    keywords = ['作者简介', '通信作者', '通讯作者', '基金项目', '利益冲突', '贡献声明', 
                '作者贡献', 'Author contributions', 'Funding', 'Conflict of interest',
                'Corresponding author']
    results = {}
    lines = all_text.split('\n')
    for keyword in keywords:
        for i, line in enumerate(lines):
            if keyword in line:
                context = '\n'.join(lines[max(0,i-1):min(i+5, len(lines))])
                if keyword not in results:
                    results[keyword] = []
                results[keyword].append(context.strip())
    return results

def determine_corresponding_author(all_text):
    is_corresponding = '否'
    cor_keywords = ['通信作者', '通讯作者', 'Corresponding author']
    for ck in cor_keywords:
        if all_text and ck in all_text:
            lines = all_text.split('\n')
            for i, line in enumerate(lines):
                if ck in line:
                    context = '\n'.join(lines[max(0,i-2):min(i+4, len(lines))])
                    if '谷文萍' in context or 'guwenping' in context.lower() or 'gu wenping' in context.lower() or 'GWping' in context:
                        is_corresponding = '是'
                        break
        if is_corresponding == '是':
            break
    return is_corresponding

def process_all_pdfs():
    pdf_files = sorted([f for f in os.listdir(PDF_DIR) if f.endswith('.pdf')])
    results = []
    
    for idx, pdf_file in enumerate(pdf_files, 1):
        print(f"\n[{idx}/{len(pdf_files)}] Processing: {pdf_file}")
        pdf_path = os.path.join(PDF_DIR, pdf_file)
        
        texts = extract_text_from_pdf(pdf_path)
        
        if 'error' in texts:
            results.append({
                'filename': pdf_file, 'error': texts['error'],
                'title': '', 'journal': '', 'year': '',
                'author_total': 0, 'gu_position': '-',
                'is_corresponding': '否', 'is_first_author': '否',
                'notes': 'PDF提取失败', 'extracted_sections': {}, 'author_line': ''
            })
            continue
        
        first_page = texts.get('page_1', '')
        all_text = texts.get('all_text', '')
        
        title = extract_title(first_page)
        year = extract_year(first_page) or extract_year(all_text)
        journal = extract_journal(first_page)
        
        authors, source, author_line = find_authors(first_page, all_text, pdf_file)
        
        position = '-'
        if authors:
            for i, name in enumerate(authors, 1):
                if name == '谷文萍':
                    position = i
                    break
        
        is_first_author = '否'
        if position == 1:
            is_first_author = '是'
        elif '_谷文萍.pdf' in pdf_file and position == '-':
            is_first_author = '是（文件名推断）'
        
        sections = find_sections(all_text)
        is_corresponding = determine_corresponding_author(all_text)
        
        extracted_sections = {}
        for k, v in sections.items():
            if v:
                text_snippet = v[0].replace('\n', ' | ')
                if len(text_snippet) > 400:
                    text_snippet = text_snippet[:400] + "..."
                extracted_sections[k] = text_snippet
        
        # Detect abnormal PDF
        abnormal_pdf = False
        if first_page and not any(k in first_page[:500] for k in ['摘要', '目的', '关键词', '文章编号', '中图分类号', 'Abstract', 'Objective']):
            if title and len(title) < 15:
                abnormal_pdf = True
        
        notes = ""
        author_count = len(authors) if authors else 0
        if abnormal_pdf and author_count < 3:
            notes = "PDF页序异常（第一页非封面）"
        elif author_count > 20:
            notes = "专家共识类（超长作者列表）"
        elif author_count > 10:
            notes = "多作者论文"
        elif position != '-' and position == author_count and author_count > 1 and is_corresponding == '否':
            notes = "末尾作者但非通讯作者"
        elif position != '-' and 5 <= position <= 15:
            notes = "中间作者"
        elif position != '-' and position > 1 and is_corresponding == '否':
            notes = "非通讯挂名作者"
        elif '_谷文萍.pdf' in pdf_file and position == '-' and is_corresponding == '否':
            notes = "第一作者（作者列表未提取）"
        elif position == '-':
            notes = "作者提取失败"
        
        results.append({
            'filename': pdf_file, 'title': title, 'journal': journal, 'year': year,
            'author_total': author_count, 'gu_position': position,
            'is_corresponding': is_corresponding, 'is_first_author': is_first_author,
            'notes': notes, 'extracted_sections': extracted_sections,
            'author_line': author_line, 'source': source, 'abnormal_pdf': abnormal_pdf
        })
        
        print(f"  Authors: {author_count}, 谷文萍位置: {position}, 通讯: {is_corresponding}, 第一: {is_first_author}, source: {source}")
    
    return results

def generate_markdown(results):
    lines = []
    lines.append("# 谷文萍论文作者贡献度分析报告")
    lines.append("")
    lines.append(f"分析论文总数: {len(results)} 篇")
    lines.append("")
    
    first_author_count = sum(1 for r in results if '是' in r['is_first_author'])
    corresponding_count = sum(1 for r in results if r['is_corresponding'] == '是' and '是' not in r['is_first_author'])
    failed_count = sum(1 for r in results if '失败' in r.get('notes', ''))
    abnormal_count = sum(1 for r in results if '异常' in r.get('notes', ''))
    
    lines.append("## 统计摘要")
    lines.append("")
    lines.append(f"- 第一作者论文: {first_author_count} 篇")
    lines.append(f"- 通讯作者论文（非第一作者）: {corresponding_count} 篇")
    lines.append(f"- PDF页序异常: {abnormal_count} 篇")
    lines.append(f"- 作者提取失败: {failed_count} 篇")
    lines.append(f"- 待分析挂名论文: {len(results) - first_author_count - corresponding_count - failed_count - abnormal_count} 篇")
    lines.append("")
    
    lines.append("## 详细分析表格")
    lines.append("")
    lines.append("| 文件名 | 论文标题 | 期刊 | 年份 | 作者总数 | 谷文萍排序 | 是否通讯 | 备注/分类 | 贡献声明/基金信息摘录 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    
    for r in results:
        title = r['title'][:55] + "..." if len(r['title']) > 55 else r['title']
        journal = r['journal'][:30] + "..." if len(r['journal']) > 30 else r['journal']
        year = r['year']
        author_total = r['author_total'] if r['author_total'] > 0 else '-'
        gu_pos = r['gu_position']
        is_cor = r['is_corresponding']
        notes = r['notes']
        
        sections_text = ""
        if r.get('extracted_sections'):
            parts = []
            for k, v in list(r['extracted_sections'].items())[:3]:
                parts.append(f"【{k}】{v}")
            sections_text = " | ".join(parts)
        
        lines.append(f"| {r['filename']} | {title} | {journal} | {year} | {author_total} | {gu_pos} | {is_cor} | {notes} | {sections_text} |")
    
    lines.append("")
    lines.append("## 分类详述")
    lines.append("")
    
    lines.append("### 第一作者论文")
    first_author_papers = [r for r in results if '是' in r['is_first_author']]
    for r in first_author_papers:
        lines.append(f"- {r['filename']} | 排序:{r['gu_position']}/{r['author_total']} | {r['title'][:50]}")
    lines.append("")
    
    lines.append("### 通讯作者论文（非第一作者）")
    corr_papers = [r for r in results if r['is_corresponding'] == '是' and '是' not in r['is_first_author']]
    for r in corr_papers:
        lines.append(f"- {r['filename']} | 排序:{r['gu_position']}/{r['author_total']} | {r['title'][:50]}")
    lines.append("")
    
    lines.append("### 专家共识类文章（作者数>20）")
    consensus = [r for r in results if r.get('author_total', 0) > 20]
    for r in consensus:
        lines.append(f"- {r['filename']} | 作者数:{r['author_total']} | 谷文萍排序:{r['gu_position']} | {r['title'][:50]}")
    lines.append("")
    
    lines.append("### 末尾作者但非通讯作者")
    end_authors = [r for r in results if r.get('gu_position') != '-' and r.get('gu_position') == r.get('author_total') and isinstance(r.get('author_total', 0), int) and r.get('author_total', 0) > 1 and r['is_corresponding'] == '否']
    for r in end_authors:
        lines.append(f"- {r['filename']} | 排序:{r['gu_position']}/{r['author_total']} | {r['title'][:50]}")
    lines.append("")
    
    lines.append("### 中间作者（排序5-15位）")
    middle = [r for r in results if r.get('gu_position') != '-' and isinstance(r.get('gu_position'), int) and 5 <= r['gu_position'] <= 15]
    for r in middle:
        lines.append(f"- {r['filename']} | 排序:{r['gu_position']}/{r['author_total']} | {r['title'][:50]}")
    lines.append("")
    
    lines.append("### 其他非第一/非通讯挂名作者论文")
    others = [r for r in results if '是' not in r['is_first_author'] and r['is_corresponding'] == '否' and r not in end_authors and r not in middle and r not in consensus]
    for r in others:
        if '失败' not in r.get('notes', '') and '异常' not in r.get('notes', ''):
            lines.append(f"- {r['filename']} | 排序:{r['gu_position']}/{r['author_total']} | {r['title'][:50]}")
    lines.append("")
    
    lines.append("### PDF页序异常的论文")
    abnormal = [r for r in results if '异常' in r.get('notes', '')]
    for r in abnormal:
        lines.append(f"- {r['filename']} | {r['notes']}")
    lines.append("")
    
    lines.append("### 提取失败的论文")
    failed = [r for r in results if '失败' in r.get('notes', '')]
    for r in failed:
        lines.append(f"- {r['filename']} | {r.get('error', r['notes'])}")
    lines.append("")
    
    return "\n".join(lines)

if __name__ == "__main__":
    results = process_all_pdfs()
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    md_content = generate_markdown(results)
    with open(OUTPUT_MD, 'w', encoding='utf-8') as f:
        f.write(md_content)
    print(f"\n\n分析完成！")
    print(f"JSON结果: {OUTPUT_JSON}")
    print(f"Markdown结果: {OUTPUT_MD}")
