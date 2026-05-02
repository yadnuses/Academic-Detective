#!/usr/bin/env python3
"""
学者档案基准比对脚本 v2.0
"""

import os, sys, csv, math, argparse
from difflib import SequenceMatcher

FEATURE_COLS = [
    "feat_data_fabrication", "feat_data_falsification", "feat_image_manipulation",
    "feat_plagiarism", "feat_self_plagiarism", "feat_translation_plagiarism",
    "feat_ghostwriting", "feat_fake_peer_review", "feat_paper_mill",
    "feat_data_trading", "feat_authorship_misconduct", "feat_fund_misconduct",
    "feat_duplicate_publication", "feat_citation_manipulation",
    "feat_ethical_violation", "feat_systemic_fraud", "feat_supervisor_abuse"
]

FEATURE_NAMES = {
    "feat_data_fabrication": "数据伪造", "feat_data_falsification": "数据篡改",
    "feat_image_manipulation": "图像操纵", "feat_plagiarism": "抄袭剽窃",
    "feat_self_plagiarism": "自我抄袭", "feat_translation_plagiarism": "翻译抄袭",
    "feat_ghostwriting": "代写", "feat_fake_peer_review": "虚假同行评审",
    "feat_paper_mill": "论文工厂", "feat_data_trading": "数据买卖",
    "feat_authorship_misconduct": "作者身份不端", "feat_fund_misconduct": "基金不端",
    "feat_duplicate_publication": "重复发表", "feat_citation_manipulation": "引用操纵",
    "feat_ethical_violation": "伦理违规", "feat_systemic_fraud": "系统性造假",
    "feat_supervisor_abuse": "导师权力滥用",
}


class ScholarProfileMatcherV2:
    def __init__(self, profile_db_path):
        self.profiles = []
        self.load_profiles(profile_db_path)

    def load_profiles(self, path):
        with open(path, 'r', encoding='utf-8-sig') as f:
            self.profiles = list(csv.DictReader(f))

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
        for kw, lv in {'教授': 3, '研究员': 3, '博士生导师': 3,
                       '副教授': 2, '副研究员': 2, ' Senior Lecturer': 2,
                       '讲师': 1, '助理': 1}.items():
            if kw in title:
                return lv
        if 'Professor' in title and 'Associate' not in title:
            return 3
        if 'Associate Professor' in title:
            return 2
        if 'Lecturer' in title or 'Senior Lecturer' in title:
            return 2
        return 0

    def _tier_level(self, tier):
        return {'A': 5, 'B': 4, 'C': 3, 'D': 2, 'F': 1}.get(tier, 0)

    def _feature_vector(self, profile):
        return [1 if profile.get(c) == '1' else 0 for c in FEATURE_COLS]

    def _jaccard_similarity(self, vec_a, vec_b):
        intersection = sum(1 for a, b in zip(vec_a, vec_b) if a == 1 and b == 1)
        union = sum(1 for a, b in zip(vec_a, vec_b) if a == 1 or b == 1)
        return intersection / union if union > 0 else 0.0

    def _cosine_similarity(self, vec_a, vec_b):
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _prefilter_similarity(self, target, candidate):
        s, weights = 0.0, 0.0
        # 1. 机构 (0.10)
        s += self._str_similarity(target.get('institution', ''), candidate.get('institution', '')) * 0.10
        weights += 0.10
        # 2. 职称 (0.10)
        tl_t, tl_p = self._title_level(target.get('current_title', '')), self._title_level(candidate.get('current_title', ''))
        if tl_t > 0 and tl_p > 0:
            s += (1.0 - abs(tl_t - tl_p) / 3.0) * 0.10
            weights += 0.10
        # 3. 学科 (0.10)
        s += self._str_similarity(target.get('department', ''), candidate.get('department', '')) * 0.10
        weights += 0.10
        # 4. hybrid_score (0.15)
        t_s, p_s = self._parse_num(target.get('avg_hybrid_score', '')), self._parse_num(candidate.get('avg_hybrid_score', ''))
        if t_s is not None and p_s is not None:
            s += max(0, 1.0 - abs(t_s - p_s) / 50.0) * 0.15
            weights += 0.15
        # 5. 发文量 (0.10)
        t_p, p_p = self._parse_num(target.get('num_papers_claimed', '')), self._parse_num(candidate.get('num_papers_claimed', ''))
        if t_p is not None and p_p is not None:
            s += max(0, 1.0 - abs(math.log10(max(1, t_p)) - math.log10(max(1, p_p))) / 2.0) * 0.10
            weights += 0.10
        # 6. h_index (0.15)
        t_h, p_h = self._parse_num(target.get('h_index', '')), self._parse_num(candidate.get('h_index', ''))
        if t_h is not None and p_h is not None:
            s += max(0, 1.0 - abs(math.log10(max(1, t_h + 1)) - math.log10(max(1, p_h + 1))) / 1.5) * 0.15
            weights += 0.15
        # 7. 引用数 (0.10)
        t_c, p_c = self._parse_num(target.get('total_citations', '')), self._parse_num(candidate.get('total_citations', ''))
        if t_c is not None and p_c is not None:
            s += max(0, 1.0 - abs(math.log10(max(1, t_c)) - math.log10(max(1, p_c))) / 3.0) * 0.10
            weights += 0.10
        # 8. 期刊层级 (0.10)
        t_t, p_t = self._tier_level(target.get('max_journal_tier', '')), self._tier_level(candidate.get('max_journal_tier', ''))
        if t_t > 0 and p_t > 0:
            s += (1.0 - abs(t_t - p_t) / 5.0) * 0.10
            weights += 0.10
        # 9. 一作数 (0.10)
        t_f, p_f = self._parse_num(target.get('first_author_count', '')), self._parse_num(candidate.get('first_author_count', ''))
        if t_f is not None and p_f is not None:
            s += max(0, 1.0 - abs(math.log10(max(1, t_f)) - math.log10(max(1, p_f))) / 2.0) * 0.10
            weights += 0.10
        return s / weights if weights > 0 else 0.0

    def _mode_similarity(self, target, candidate):
        t_vec, p_vec = self._feature_vector(target), self._feature_vector(candidate)
        return self._jaccard_similarity(t_vec, p_vec) * 0.7 + self._cosine_similarity(t_vec, p_vec) * 0.3

    def _composite_similarity(self, target, candidate):
        prefilter = self._prefilter_similarity(target, candidate)
        mode = self._mode_similarity(target, candidate)
        t_active = sum(self._feature_vector(target))
        p_active = sum(self._feature_vector(candidate))
        if t_active == 0 and p_active == 0:
            return prefilter, prefilter, 0.0
        elif t_active == 0 or p_active == 0:
            return prefilter * 0.8 + mode * 0.2, prefilter, mode
        else:
            return prefilter * 0.5 + mode * 0.5, prefilter, mode

    def compare(self, target_name, top_k=5, mode='composite'):
        target = next((p for p in self.profiles if p['name'] == target_name or target_name in p['name'] or p['name'] in target_name), None)
        if not target:
            return f"学者 '{target_name}' 不在档案库中"
        results = []
        for p in self.profiles:
            if p['name'] == target['name']:
                continue
            if mode == 'composite':
                score, prefilter, mode_sim = self._composite_similarity(target, p)
            elif mode == 'prefilter':
                score, prefilter, mode_sim = self._prefilter_similarity(target, p), self._prefilter_similarity(target, p), self._mode_similarity(target, p)
            elif mode == 'mode':
                score, prefilter, mode_sim = self._mode_similarity(target, p), self._prefilter_similarity(target, p), self._mode_similarity(target, p)
            else:
                score, prefilter, mode_sim = 0.0, 0.0, 0.0
            results.append((p, score, prefilter, mode_sim))
        results.sort(key=lambda x: x[1], reverse=True)
        return target, results[:top_k]

    def risk_profile(self, target_name):
        target = next((p for p in self.profiles if p['name'] == target_name), None)
        if not target:
            return f"学者 '{target_name}' 不在档案库中"
        t_vec = self._feature_vector(target)
        risk_report = []
        for i, col in enumerate(FEATURE_COLS):
            if t_vec[i] == 0:
                continue
            feature_name = FEATURE_NAMES[col]
            best_match, best_score = None, -1
            for p in self.profiles:
                if p['investigation_status'] != 'confirmed_misconduct' or p['name'] == target['name']:
                    continue
                p_vec = self._feature_vector(p)
                if p_vec[i] == 0:
                    continue
                overlap = sum(1 for a, b in zip(t_vec, p_vec) if a == 1 and b == 1)
                if overlap > best_score:
                    best_score = overlap
                    best_match = p
            if best_match:
                risk_report.append({'feature': feature_name, 'closest_case': best_match['name'], 'institution': best_match['institution'], 'overlap_count': best_score})
        return target, risk_report

    def misconduct_ranking(self, target_name, top_k=5):
        target = next((p for p in self.profiles if p['name'] == target_name), None)
        if not target:
            return f"学者 '{target_name}' 不在档案库中"
        results = []
        for p in self.profiles:
            if p['investigation_status'] != 'confirmed_misconduct' or p['name'] == target['name']:
                continue
            score, prefilter, mode_sim = self._composite_similarity(target, p)
            results.append((p, score, prefilter, mode_sim))
        results.sort(key=lambda x: x[1], reverse=True)
        return target, results[:top_k]

    def list_profiles(self):
        for p in self.profiles:
            status = p.get('investigation_status', 'unknown')
            icon = {"confirmed_misconduct": "⚠️", "suspicious": "?", "normal": "✓"}.get(status, "")
            active = sum(1 for c in FEATURE_COLS if p.get(c) == '1')
            print(f"{icon} {p['name']} | {p['institution']} | {status} | {active}个特征")


def main():
    parser = argparse.ArgumentParser(description='学者档案基准比对工具 v2.0')
    parser.add_argument('--db', default='/Users/xiaoy/Desktop/端上台来/data/scholar_profile_database.csv')
    parser.add_argument('--name', required=True)
    parser.add_argument('--top', type=int, default=5)
    parser.add_argument('--mode', default='composite', choices=['composite', 'prefilter', 'mode', 'risk_profile', 'misconduct_ranking'])
    parser.add_argument('--list', action='store_true')
    args = parser.parse_args()

    matcher = ScholarProfileMatcherV2(args.db)
    if args.list:
        matcher.list_profiles()
        return

    if args.mode == 'risk_profile':
        target, report = matcher.risk_profile(args.name)
        if isinstance(report, str):
            print(report); sys.exit(1)
        print(f"\n{'='*60}\n不端风险画像: {target['name']}\n{'='*60}")
        print(f"\n目标学者激活的特征维度: {sum(matcher._feature_vector(target))}个\n")
        if not report:
            print("  该学者未激活任何不端特征维度。"); return
        for i, item in enumerate(report, 1):
            print(f"  #{i} 【{item['feature']}】")
            print(f"     最接近的确认不端案例: {item['closest_case']} ({item['institution']})")
            print(f"     特征重叠数: {item['overlap_count']}个")
            print()
        return

    if args.mode == 'misconduct_ranking':
        target, results = matcher.misconduct_ranking(args.name, top_k=args.top)
        if isinstance(results, str):
            print(results); sys.exit(1)
        print(f"\n{'='*60}\n与确认不端案例的专门比对: {target['name']}\n{'='*60}")
        print(f"\n档案库中共有 {sum(1 for p in matcher.profiles if p['investigation_status'] == 'confirmed_misconduct')} 个confirmed_misconduct案例")
        print(f"\n最接近的 {len(results)} 个不端案例：\n")
        for i, (p, score, prefilter, mode_sim) in enumerate(results, 1):
            active = [c.replace("feat_", "") for c in FEATURE_COLS if p.get(c) == '1']
            print(f"  #{i} ⚠️ {p['name']} ({p['institution']})")
            print(f"     综合相似度: {score:.2%} (前置筛查: {prefilter:.2%}, 模式相似度: {mode_sim:.2%})")
            print(f"     激活特征: {', '.join(active)}")
            print()
        return

    target, results = matcher.compare(args.name, top_k=args.top, mode=args.mode)
    if isinstance(results, str):
        print(results); sys.exit(1)
    print(f"\n{'='*60}\n学者档案基准比对结果 v2.0\n{'='*60}")
    print(f"\n目标学者: {target['name']}\n状态: {target['investigation_status']}\n激活特征数: {sum(matcher._feature_vector(target))}")
    print(f"档案库总计: {len(matcher.profiles)} 位学者\n比对模式: {args.mode}\n\n最相似的 {len(results)} 个案例：\n")
    for i, (p, score, prefilter, mode_sim) in enumerate(results, 1):
        status = p.get('investigation_status', 'unknown')
        icon = {"confirmed_misconduct": "⚠️", "suspicious": "?", "normal": "✓"}.get(status, "")
        active = sum(1 for c in FEATURE_COLS if p.get(c) == '1')
        print(f"  #{i} {icon} {p['name']} ({p['institution']})")
        print(f"     综合相似度: {score:.2%}")
        print(f"       └─ 前置筛查: {prefilter:.2%}")
        print(f"       └─ 模式相似度: {mode_sim:.2%}")
        print(f"     职称: {p['current_title'] or 'N/A'}")
        print(f"     hybrid_score: {p['avg_hybrid_score'] or 'N/A'} | h_index: {p['h_index'] or 'N/A'}")
        print(f"     调查结论: {status} | 激活特征: {active}")
        print()


if __name__ == '__main__':
    main()
