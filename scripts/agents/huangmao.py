#!/usr/bin/env python3
"""
huangmao.py — Explorer / Creative Thinker Agent.

Roam freely across case data, make cross-domain associations,
generate hypotheses without worrying about correctness.

Credibility levels:
  strongly_suggested — direct evidence, quantifiable anomaly
  plausible — indirect evidence, reasonable inference
  wild_guess — speculative, no direct evidence, high impact if true
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from base import BaseAgent


class Huangmao(BaseAgent):
    """Explorer agent — freely roams data, makes cross-domain associations, brainstorms."""

    def __init__(self, case_dir: Path):
        super().__init__(case_dir, "huangmao")
        self._findings: list[dict] = []
        self._counter = 0

    # ------------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------------

    def run(self, context: dict | None = None) -> dict:
        """Execute roaming pipeline and write findings."""
        self.log_activity("roam_start", f"case_dir={self.case_dir}")
        scholar_data = self.read_json("scholar_data.json")
        outputs = self._load_all_outputs()
        papers = self._extract_papers(scholar_data, outputs)

        findings: list[dict] = []
        findings.extend(self.roam_temporal(papers))
        findings.extend(self.roam_titles(papers))
        findings.extend(self.roam_authors(papers))
        findings.extend(self.roam_funding(papers))
        findings.extend(self.roam_journals(papers))
        findings.extend(self.cross_domain_associate(findings))

        seeds = [f for f in findings if f["credibility"] in ("strongly_suggested", "plausible")]
        for seed in seeds:
            findings.extend(self.brainstorm(seed))

        result = {
            "agent": self.name,
            "findings": findings,
            "roam_stats": {
                "papers_examined": len(papers),
                "findings_total": len(findings),
                "wild_guess": sum(1 for f in findings if f["credibility"] == "wild_guess"),
                "plausible": sum(1 for f in findings if f["credibility"] == "plausible"),
                "strongly_suggested": sum(1 for f in findings if f["credibility"] == "strongly_suggested"),
            },
        }
        self.write_json(result, "findings.json")
        self.log_activity("roam_end", f"findings={len(findings)}")
        return result

    # ------------------------------------------------------------------
    # Roam strategies
    # ------------------------------------------------------------------

    def roam_temporal(self, papers: list[dict]) -> list[dict]:
        """Check temporal clustering, gaps, inversions, career-milestone correlations."""
        findings: list[dict] = []
        if len(papers) < 3:
            return findings
        years = sorted([p.get("year") for p in papers if isinstance(p.get("year"), int)])
        if not years:
            return findings

        year_counts = Counter(years)
        max_year, max_count = year_counts.most_common(1)[0]
        if max_count >= 5:
            findings.append(self._finding("temporal", f"{max_year}年集中发表了{max_count}篇，像是学术井喷。",
                "strongly_suggested",
                f"{max_count}篇堆在同一年，要么前期积累集中释放，要么有外部压力（考核、评职称）。时间密度高到可疑，值得看投稿日期是否也扎堆。",
                {"year": max_year, "count": max_count, "total": len(years)},
                ["review_cycle_analyzer", "crossref_event_tracker"]))
        elif max_count >= 3:
            findings.append(self._finding("temporal", f"{max_year}年发了{max_count}篇，小有集中。",
                "plausible", f"{max_count}篇同一年不算极端，但若涉及不同子领域就有意思了。",
                {"year": max_year, "count": max_count}, ["review_cycle_analyzer"]))

        gaps = [(years[i], years[i + 1] - years[i]) for i in range(len(years) - 1)]
        big_gaps = [(y, g) for y, g in gaps if g >= 3]
        if big_gaps:
            y, g = big_gaps[0]
            findings.append(self._finding("temporal", f"{y}年到{y+g}年出现{g}年空白。",
                "plausible", f"{g}年不发论文在活跃研究者身上不常见。可能行政挂职，也可能产出转移给了别人。",
                {"gap_start": y, "gap_end": y + g}, ["citation_profiler", "network_visualizer"]))

        if len(years) >= 4:
            early = sum(year_counts[y] for y in years[:2]) / 2
            late = sum(year_counts[y] for y in years[-2:]) / 2
            if early > late * 2:
                findings.append(self._finding("temporal", "早期产出密度显著高于近期，呈现倒序曲线。",
                    "plausible", "一般是越写越顺。如果早期又多又好，后期反而沉寂，可能早年有合作者代笔，或早期数据‘借来的’。",
                    {"early_avg": early, "late_avg": late}, ["text_profiler", "stylometry_profiler"]))
        return findings

    def roam_titles(self, papers: list[dict]) -> list[dict]:
        """Check title similarity, keyword clustering, semantic equivalence."""
        findings: list[dict] = []
        titles = [p.get("title", "") for p in papers if p.get("title")]
        if len(titles) < 2:
            return findings

        words = []
        for t in titles:
            words.extend(re.findall(r"[A-Za-z\u4e00-\u9fff]+", t.lower()))
        stop = {"a", "the", "of", "in", "on", "and", "for", "with", "to", "an", "研究", "分析", "基于", "的", "与", "及"}
        keywords = [w for w in words if w not in stop and len(w) > 1]
        top_kw, top_n = Counter(keywords).most_common(1)[0] if keywords else (None, 0)
        if top_kw and top_n >= 4:
            findings.append(self._finding("title", f"关键词‘{top_kw}’在标题中出现{top_n}次，形成主题垄断。",
                "plausible", f"{top_n}篇带同一个关键词，要么真深耕，要么同一套素材反复包装。实验数据、引用网络可能高度重叠。",
                {"keyword": top_kw, "freq": top_n}, ["stats_reverse_engineer", "text_profiler"]))

        similar = []
        for i in range(len(titles)):
            for j in range(i + 1, len(titles)):
                a = set(re.findall(r"[A-Za-z\u4e00-\u9fff]+", titles[i].lower())) - stop
                b = set(re.findall(r"[A-Za-z\u4e00-\u9fff]+", titles[j].lower())) - stop
                if a and b:
                    overlap = len(a & b) / min(len(a), len(b))
                    if overlap >= 0.7:
                        similar.append((titles[i], titles[j], overlap))
        if len(similar) >= 2:
            findings.append(self._finding("title", f"发现{len(similar)}组标题语义高度重叠，疑似一鱼多吃。",
                "strongly_suggested", "标题70%以上相同词汇，大概率同一批数据换了说法。多组组合说明可能是系统性的标题改写策略。",
                {"pairs": len(similar), "examples": similar[:2]}, ["publication_trace", "text_profiler"]))
        elif similar:
            findings.append(self._finding("title", "一组标题语义重叠较高，可能是同一研究的变体投稿。",
                "plausible", "一个pair可能是系列研究的延续。若发表时间接近、期刊层次差异大，就可能是先投好的再改投差的。",
                {"examples": similar[:1]}, ["publication_trace"]))
        return findings

    def roam_authors(self, papers: list[dict]) -> list[dict]:
        """Check co-author networks, self-citation, ghost authorship signals."""
        findings: list[dict] = []
        if len(papers) < 3:
            return findings

        coauthor_counts: Counter[str] = Counter()
        last_author_counts: Counter[str] = Counter()
        for p in papers:
            authors = p.get("authors", [])
            if isinstance(authors, list):
                for a in authors:
                    name = a if isinstance(a, str) else a.get("name", "")
                    if name:
                        coauthor_counts[name] += 1
                if authors:
                    last = authors[-1]
                    name = last if isinstance(last, str) else last.get("name", "")
                    if name:
                        last_author_counts[name] += 1

        frequent = [(n, c) for n, c in coauthor_counts.most_common(5) if c >= 3]
        if len(frequent) >= 2:
            names = "、".join([n for n, _ in frequent[:3]])
            findings.append(self._finding("author", f"存在一个紧密合作圈（{names}等人反复出现）。",
                "plausible", "小圈子反复合作正常，但如果互相引用比例异常高，可能形成引用卡特尔。",
                {"frequent": frequent}, ["citation_profiler", "network_visualizer"]))

        if last_author_counts:
            ghost, gc = last_author_counts.most_common(1)[0]
            if gc >= 4:
                findings.append(self._finding("author", f"{ghost}作为末位作者出现{gc}次，比例偏高。",
                    "plausible", "末位作者通常是导师，挂名多正常。但若横跨多个不相关子领域，可能是幽灵署名——挂名换资源。",
                    {"last_author": ghost, "count": gc}, ["network_visualizer", "citation_profiler"]))
        return findings

    def roam_funding(self, papers: list[dict]) -> list[dict]:
        """Check grant reuse and funding scope mismatches."""
        findings: list[dict] = []
        grants: list[tuple[str, str]] = []
        for p in papers:
            gids = p.get("grant_ids", p.get("funding", []))
            if isinstance(gids, str):
                gids = [gids]
            if isinstance(gids, list):
                for g in gids:
                    gid = g if isinstance(g, str) else g.get("id", g.get("grant_id", ""))
                    if gid:
                        grants.append((gid, p.get("title", "")))
        if not grants:
            return findings

        gp: dict[str, list[str]] = {}
        for gid, title in grants:
            gp.setdefault(gid, []).append(title)
        reused = {k: v for k, v in gp.items() if len(v) >= 2}
        if reused:
            findings.append(self._finding("funding", f"发现{len(reused)}个基金号出现在多篇论文中。",
                "plausible", "基金复用本身不违规，但关键看资助范围是否匹配。同一基金号既出现在临床又出现在算法论文里，显然是错配。",
                {"reused": {k: len(v) for k, v in reused.items()}}, ["grant_linker", "publication_trace"]))
        return findings

    def roam_journals(self, papers: list[dict]) -> list[dict]:
        """Check journal concentration and quality vs seniority mismatch."""
        findings: list[dict] = []
        journals = [p.get("journal", "") for p in papers if p.get("journal")]
        if len(journals) < 3:
            return findings

        jc = Counter(journals)
        top_j, top_c = jc.most_common(1)[0]
        ratio = top_c / len(journals)
        if ratio >= 0.5 and top_c >= 3:
            findings.append(self._finding("journal", f"{top_c}篇（{ratio:.0%}）集中在《{top_j}》，集中度异常。",
                "strongly_suggested", "一半以上砸在一个期刊，不符合正常投稿策略。除非是该期刊编委或有特殊关系，也可能是掠夺性期刊。",
                {"journal": top_j, "count": top_c, "ratio": ratio},
                ["peer_review_intel", "editorial_self_publishing_detector"]))
        elif ratio >= 0.3 and top_c >= 2:
            findings.append(self._finding("journal", f"《{top_j}》占比{ratio:.0%}，偏好明显。",
                "plausible", "偏好一个期刊不一定是坏事，但若该期刊审稿周期异常短、或作者资历明显高于平均作者水平，值得怀疑。",
                {"journal": top_j, "count": top_c, "ratio": ratio}, ["peer_review_intel"]))
        return findings

    # ------------------------------------------------------------------
    # Association & brainstorming
    # ------------------------------------------------------------------

    def cross_domain_associate(self, findings: list[dict]) -> list[dict]:
        """Connect findings from different roam strategies into combined hypotheses."""
        combined: list[dict] = []
        cats = {f["category"] for f in findings}

        if "temporal" in cats and "title" in cats:
            combined.append(self._finding("cross_domain", "时间聚类 + 标题相似 = 可能的批量生产流水线。",
                "plausible", "一堆论文同窗口发表且标题差不多，很可能是同一批次生产。正常研究分散不可预测，批量生产才集中相似。",
                {"linked": ["temporal", "title"]}, ["stats_reverse_engineer", "image_metadata_extractor"]))

        if "journal" in cats and "author" in cats:
            combined.append(self._finding("cross_domain", "期刊集中度 + 固定合作圈 = 可能的学术小团体互推。",
                "wild_guess", "脑洞开大：固定小圈子持续在同一期刊发文、互相引用、互相挂名。如果编辑也在网络里，审稿流程就被架空了。只是猜测，但值得查。",
                {"linked": ["journal", "author"]}, ["network_visualizer", "peer_review_intel"]))

        if "funding" in cats and "temporal" in cats:
            combined.append(self._finding("cross_domain", "基金复用 + 时间聚类 = 可能为结题突击发文。",
                "plausible", "项目快结题，经费没花完，指标没达标，突击写几篇挂同一个基金号投出去。这剧本太常见了。",
                {"linked": ["funding", "temporal"]}, ["grant_linker", "review_cycle_analyzer"]))
        return combined

    def brainstorm(self, seed: dict) -> list[dict]:
        """Generate 'what if' scenarios from a seed finding."""
        ideas: list[dict] = []
        desc = seed.get("description", "")
        sid = seed.get("id")

        if "批量" in desc or "batch" in desc.lower():
            ideas.append(self._finding("brainstorm", "假设：这些论文由AI批量生产，人工微调后投稿。",
                "wild_guess", "GPT写摘要能力已很强。若用同一批数据让AI生成不同角度叙述再投不同平台，标题相似、时间集中都可解释。验证方向：文本风格一致性、图片元数据时间戳。",
                {"seed_id": sid}, ["text_profiler", "image_metadata_extractor", "stylometry_profiler"]))

        if "预印本" in desc or "preprint" in desc.lower() or "arXiv" in desc:
            ideas.append(self._finding("brainstorm", "假设：预印本被用作时间戳武器，确立优先权。",
                "wild_guess", "先传预印本哪怕期刊拖一年也可声称早做了。更黑暗的假设：密集上传预印本制造‘这个方向被我们占了’的假象，阻止竞争对手。",
                {"seed_id": sid}, ["crossref_event_tracker", "publication_trace"]))

        if not ideas:
            ideas.append(self._finding("brainstorm", f"基于发现#{sid}的自由联想：背后是否有更系统性的操纵？",
                "wild_guess", "一个异常是孤立，两个是巧合，三个就值得怀疑背后有系统性安排。建议扩大搜索范围。",
                {"seed_id": sid}, ["investigation_retrospector", "negative_space_analyzer"]))
        return ideas

    def mark_credibility(self, finding: dict) -> str:
        """Assess credibility based on evidence strength."""
        evidence = finding.get("evidence", {})
        category = finding.get("category", "")
        if category in ("temporal", "journal") and evidence:
            if any(isinstance(v, (int, float)) and v > 2 for v in evidence.values() if isinstance(v, (int, float))):
                return "strongly_suggested"
        if evidence:
            return "plausible"
        return "wild_guess"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _finding(self, category: str, description: str, credibility: str, reasoning: str,
                 evidence: dict | None = None, suggested_tools: list[str] | None = None) -> dict:
        """Assemble a single finding with auto-increment id."""
        self._counter += 1
        return {
            "id": self._counter,
            "category": category,
            "description": description,
            "credibility": credibility,
            "reasoning": reasoning,
            "evidence": evidence or {},
            "suggested_tools": suggested_tools or [],
        }

    def _load_all_outputs(self) -> list[dict]:
        """Load every JSON file in outputs/ directory."""
        outputs = []
        for path in self.list_outputs():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    outputs.append(json.load(f))
            except Exception:
                self.logger.warning("Failed to load output %s", path)
        return outputs

    def _extract_papers(self, scholar_data: dict, outputs: list[dict]) -> list[dict]:
        """Normalize paper list from scholar_data and deep_evidence outputs."""
        papers: list[dict] = []
        ao = scholar_data.get("academic_outputs", {})
        if isinstance(ao, dict):
            for k in ("verified_papers", "paper_list", "recent_3yr_papers"):
                v = ao.get(k, [])
                if isinstance(v, list):
                    papers.extend(v)
        for out in outputs:
            if not isinstance(out, dict):
                continue
            for k in ("papers", "signals", "details", "preprints"):
                v = out.get(k, [])
                if isinstance(v, list):
                    papers.extend(v)
            for v in out.values():
                if isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict) and ("title" in item or "year" in item) and item not in papers:
                            papers.append(item)
        seen: set[str] = set()
        unique: list[dict] = []
        for p in papers:
            if isinstance(p, dict):
                key = f"{p.get('title', '')}::{p.get('year', '')}"
                if key not in seen:
                    seen.add(key)
                    unique.append(p)
        return unique
