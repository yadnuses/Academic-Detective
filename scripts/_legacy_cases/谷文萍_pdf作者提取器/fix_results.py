#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

INPUT_JSON = "/Users/xiaoy/Downloads/调查名单/谷文萍/谷文萍论文作者分析_v3.json"
OUTPUT_MD = "/Users/xiaoy/Downloads/调查名单/谷文萍/谷文萍论文作者分析_最终.md"
OUTPUT_JSON = "/Users/xiaoy/Downloads/调查名单/谷文萍/谷文萍论文作者分析_最终.json"

# Manual corrections based on direct PDF first-page inspection
CORRECTIONS = {
    'Ephrin-B2促进大鼠局灶脑缺血再灌注后VEGF表达及血管新生_肖慧.pdf': {
        'authors': ['肖慧', '谷文萍', '胡珏', '王振'],
        'notes': '通讯作者（已核验）'
    },
    'PPARr2基因Pro12Ala多态性与脑梗死的关系_黄蕾.pdf': {
        'authors': ['黄蕾', '谷文萍', '李伟', '王妮妮', '宋晓明', '王玉周', '彭颖琼'],
        'notes': '通讯作者（已核验）'
    },
    '实验性脑缺血再灌后迟发性神经元死亡表现为细胞凋亡_谷文萍.pdf': {
        'authors': ['谷文萍', '杨期东', '谢光洁'],
        'notes': '第一作者（已核验）'
    },
    '实验性局灶性脑缺血再灌注后HSP_(70)_mRNA的表达_谷文萍.pdf': {
        'authors': ['谷文萍', '杨期东', '史伟雄', '谢光洁', '周艳宏'],
        'notes': '第一作者（已核验）'
    },
    '沙鼠短暂脑缺血再灌p53基因表达_谷文萍.pdf': {
        'authors': ['谷文萍', '杨期东', '谢光洁', '杨洁', '谢逸群'],
        'notes': '第一作者（已核验）'
    },
    'IL-6基因多态性与脑出血的相关性研究_李拥军.pdf': {
        'authors': ['李拥军', '刘竞', '龚姣娥', '唐永忠', '谷文萍', '谢明', '梁静', '宋小明', '杨期东'],
        'notes': '通讯作者（已核验）'
    },
    '脑卒中SELP基因C-2123G多态性研究_谷文萍.pdf': {
        'authors': ['谷文萍', '王妮妮', '唐春柳', '宋小明', '李伟', '梁静', '杨期东'],
        'notes': '第一作者（已核验）'
    },
    '阿托伐他汀钙对大鼠脑缺血再灌后ICAM-1表达的影响_谷文萍.pdf': {
        'authors': ['谷文萍', '肖慧', '黄蕾', '宋小明', '刘福中', '李小军', '李伟'],
        'notes': '第一作者（已核验）'
    },
    '阿托伐他汀钙对实验性脑缺血MMP-9表达变化的影响_刘福中.pdf': {
        'authors': ['刘福中', '谷文萍', '李伟', '肖慧', '李晓军', '宋小明', '王妮妮', '杨期东'],
        'notes': '非通讯挂名作者（已核验）'
    },
    '脑淀粉样血管病相关炎症的临床、影像及预后分析_李维.pdf': {
        'authors': ['李维', '周颖', '陈婵娟', '谷文萍', '侯德仁', '薛群', '谭红'],
        'notes': '非通讯挂名作者（已核验）'
    },
    '长沙市脑血管病社区人群预防研究——死亡率的变化_杨期东.pdf': {
        'authors': ['杨期东', '周艳宏', '刘运海', '许宏伟', '田发发', '萧剑锋', '荆照政', '谷文萍', '杜小平', '杨杰', '谢逸群', '夏健', '张乐', '杨欢', '洗东方'],
        'notes': '中间作者（已核验）'
    },
    '脑小血管病患者眼球运动与白质高信号特征的相关性_杜昊.pdf': {
        'authors': ['杜昊', '杨舒婷', '夏健', '宋明谕', '王宏', '卢芷妍', '何剑', '易芳', '谷文萍'],
        'notes': '末尾作者但非通讯作者（已核验）'
    },
    '巨细胞病毒脑炎临床分析_谷文萍.pdf': {
        'authors': [],
        'notes': 'PDF页序异常（第一页非论文开头，无法核验）'
    },
}

# Additional notes for some papers where position is known but full list not inspected
POSITION_NOTES = {
    '穿支动脉粥样硬化病中国专家共识_门雪娇.pdf': '专家共识类（超长作者列表，已核验谷文萍排序第17位/34位）',
    '心率变异性与脑小血管病相关研究进展_郑兰.pdf': '中间作者（已核验）',
}

def apply_corrections(results):
    for r in results:
        fname = r['filename']
        if fname in CORRECTIONS:
            corr = CORRECTIONS[fname]
            authors = corr.get('authors', [])
            r['author_total'] = len(authors)
            if authors:
                for i, name in enumerate(authors, 1):
                    if name == '谷文萍':
                        r['gu_position'] = i
                        break
                else:
                    r['gu_position'] = '-'
            else:
                r['gu_position'] = '-'
            r['is_first_author'] = '是' if r['gu_position'] == 1 else '否'
            r['notes'] = corr.get('notes', r['notes'])
            r['author_line'] = '（人工核验修正）'
        
        if fname in POSITION_NOTES:
            r['notes'] = POSITION_NOTES[fname]
    
    # Special fix for expert consensus
    for r in results:
        if r['filename'] == '穿支动脉粥样硬化病中国专家共识_门雪娇.pdf':
            r['gu_position'] = 17
            r['author_total'] = 34
            r['is_first_author'] = '否'
    
    return results

def generate_markdown(results):
    lines = []
    lines.append("# 谷文萍论文作者贡献度分析报告（最终版）")
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
    with open(INPUT_JSON, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    results = apply_corrections(results)
    
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    md_content = generate_markdown(results)
    with open(OUTPUT_MD, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print("修正完成！")
    print(f"最终JSON: {OUTPUT_JSON}")
    print(f"最终Markdown: {OUTPUT_MD}")
