#!/usr/bin/env python3
"""
学者档案基准比对脚本
从学者档案库中找出与目标学者最相似的已有案例

用法:
    python scholar_profile_matcher.py --name "CASE_005" --top 3
    python scholar_profile_matcher.py --db /path/to/scholar_profile_database.csv --name "CASE_011"
"""

import os
import sys
import csv
import math
import argparse
from difflib import SequenceMatcher


class ScholarProfileMatcher:
    def __init__(self, profile_db_path, misconduct_db_path=None):
        self.profiles = []
        self.misconduct_cases = []
        self.load_profiles(profile_db_path)
        if misconduct_db_path and os.path.exists(misconduct_db_path):
            self.load_misconduct(misconduct_db_path)

    def load_profiles(self, path):
        with open(path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            self.profiles = list(reader)

    def load_misconduct(self, path):
        with open(path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            self.misconduct_cases = list(reader)

    def _str_similarity(self, a, b):
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def _parse_num(self, val):
        if not val:
            return None
        try:
            s = str(val).strip()
            for suffix in ['篇', '部', '个', '人', '项', '本']:
                s = s.replace(suffix, '')
            import re
            m = re.search(r'\d+\.?\d*', s)
            return float(m.group()) if m else None
        except:
            return None

    def _title_level(self, title):
        if not title:
            return 0
        keywords = {
            '教授': 3, '研究员': 3, '博士生导师': 3,
            '副教授': 2, '副研究员': 2, ' Senior Lecturer': 2,
            '讲师': 1, '助理': 1,
        }
        for kw, lv in keywords.items():
            if kw in title:
                return lv
        # English titles
        if 'Professor' in title and 'Associate' not in title:
            return 3
        if 'Associate Professor' in title:
            return 2
        if 'Lecturer' in title or 'Senior Lecturer' in title:
            return 2
        return 0

    def compare(self, target_name, top_k=3):
        target = None
        for p in self.profiles:
            if p['name'] == target_name:
                target = p
                break

        if not target:
            # Try partial match
            for p in self.profiles:
                if target_name in p['name'] or p['name'] in target_name:
                    target = p
                    break

        if not target:
            return f"学者 '{target_name}' 不在档案库中"

        scores = []
        for p in self.profiles:
            if p['name'] == target['name']:
                continue

            s = 0.0
            weights = 0.0

            # 机构相似度
            inst_sim = self._str_similarity(
                target.get('institution', ''), p.get('institution', ''))
            s += inst_sim * 0.15
            weights += 0.15

            # 职称级别
            tl_t = self._title_level(target.get('current_title', ''))
            tl_p = self._title_level(p.get('current_title', ''))
            if tl_t > 0 and tl_p > 0:
                title_sim = 1.0 - abs(tl_t - tl_p) / 3.0
                s += title_sim * 0.20
                weights += 0.20

            # 学科领域
            dept_sim = self._str_similarity(
                target.get('department', ''), p.get('department', ''))
            s += dept_sim * 0.15
            weights += 0.15

            # hybrid_score
            t_score = self._parse_num(target.get('avg_hybrid_score', ''))
            p_score = self._parse_num(p.get('avg_hybrid_score', ''))
            if t_score is not None and p_score is not None:
                diff = abs(t_score - p_score)
                score_sim = max(0, 1.0 - diff / 50.0)
                s += score_sim * 0.35
                weights += 0.35

            # 发文量
            t_papers = self._parse_num(target.get('num_papers_claimed', ''))
            p_papers = self._parse_num(p.get('num_papers_claimed', ''))
            if t_papers is not None and p_papers is not None:
                t_log = math.log10(max(1, t_papers))
                p_log = math.log10(max(1, p_papers))
                diff = abs(t_log - p_log)
                paper_sim = max(0, 1.0 - diff / 2.0)
                s += paper_sim * 0.15
                weights += 0.15

            if weights > 0:
                scores.append((p, s / weights))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def list_profiles(self):
        for p in self.profiles:
            status = p.get('investigation_status', 'unknown')
            icon = "⚠️" if status == 'confirmed_misconduct' else "✓"
            print(f"{icon} {p['name']} | {p['institution']} | {status}")


def main():
    parser = argparse.ArgumentParser(description='学者档案基准比对工具')
    parser.add_argument('--db', default='./data/scholar_profile_database.csv',
                        help='学者档案库CSV路径')
    parser.add_argument('--misconduct-db',
                        help='学术不端特征数据库CSV路径（可选）')
    parser.add_argument('--name', required=True, help='目标学者姓名')
    parser.add_argument('--top', type=int, default=3, help='返回最相似的N个结果')
    parser.add_argument('--list', action='store_true', help='列出档案库中所有学者')

    args = parser.parse_args()

    matcher = ScholarProfileMatcher(args.db, args.misconduct_db)

    if args.list:
        matcher.list_profiles()
        return

    results = matcher.compare(args.name, top_k=args.top)

    if isinstance(results, str):
        print(results)
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"学者档案基准比对结果")
    print(f"{'='*60}")
    print(f"\n目标学者: {args.name}")
    print(f"档案库中共有 {len(matcher.profiles)} 位学者")
    print(f"\n最相似的 {len(results)} 个案例：\n")

    for i, (p, score) in enumerate(results, 1):
        status = p.get('investigation_status', 'unknown')
        icon = "⚠️" if status == 'confirmed_misconduct' else "✓"
        print(f"  #{i} {icon} {p['name']} ({p['institution']})")
        print(f"     综合相似度: {score:.2%}")
        print(f"     职称: {p['current_title'] or 'N/A'}")
        print(f"     部门: {p['department'] or 'N/A'}")
        print(f"     hybrid_score: {p['avg_hybrid_score'] or 'N/A'}")
        print(f"     论文数(声称): {p['num_papers_claimed'] or 'N/A'}")
        print(f"     调查结论: {status}")
        print()


if __name__ == '__main__':
    main()
