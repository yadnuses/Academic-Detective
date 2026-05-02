#!/usr/bin/env python3
"""
agents/dududu.py — Analyst/Strategist Agent (v3.2)

Persona: 冷静、犀利、不相信巧合、擅长把碎片拼成图。
对黄毛的假设进行可行性评估，不过滤脑洞但评估价值。
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from base import BaseAgent
from core.recommendation_engine import RuleEngine


class Dududu(BaseAgent):
    """Analyst agent — reads results, reasons across modules, recommends next tools."""

    def __init__(self, case_dir: Path):
        super().__init__(case_dir, "dududu")

    def run(self, context: dict | None = None) -> dict:
        """Execute full analysis pipeline and persist outputs."""
        self.log_activity("run", "starting analysis pipeline")
        zhu_summary = self.read_other_agent("zhu_xiansheng", "summary.json")
        huangmao_findings = self.read_other_agent("huangmao", "findings.json")
        output_paths = self.list_outputs()
        all_signals: list[dict] = []
        for opath in output_paths:
            data = self.read_json(str(opath.relative_to(self.case_dir)))
            if isinstance(data, dict):
                all_signals.extend([s for s in data.get("signals", []) if isinstance(s, dict)])
        signal_analysis = self.analyze_signals(all_signals)
        chains = self.cross_module_correlation(output_paths)
        hypothesis_evaluations: list[dict] = []
        if isinstance(huangmao_findings, dict):
            for hypo in huangmao_findings.get("findings", []):
                if isinstance(hypo, dict):
                    hypothesis_evaluations.append(self.evaluate_hypothesis(hypo))
        confidence = self.assess_confidence(all_signals)
        recommendations = self.generate_recommendations(
            {"signal_analysis": signal_analysis, "chains": chains,
             "hypothesis_evaluations": hypothesis_evaluations, "zhu_summary": zhu_summary}
        )
        critical = any(c.get("confidence", 0.0) >= 0.8 for c in chains)
        analysis_payload = {
            "agent": self.name, "signal_analysis": signal_analysis,
            "cross_module_chains": chains, "hypothesis_evaluations": hypothesis_evaluations,
            "confidence_overall": round(confidence, 4), "critical": critical,
        }
        recommendations_payload = {
            "agent": self.name, "recommendations": recommendations,
            "critical": critical, "confidence_overall": round(confidence, 4),
        }
        self.write_json(recommendations_payload, "recommendations.json")
        self.write_json(analysis_payload, "analysis.json")
        if critical:
            self.mark_critical({
                "chains": [c["chain_type"] for c in chains if c.get("confidence", 0.0) >= 0.8],
                "confidence": confidence,
            })
        else:
            self.clear_critical()
        self.log_activity("run", f"completed: {len(all_signals)} signals, {len(chains)} chains, critical={critical}")
        return {
            "agent": self.name, "analysis": signal_analysis, "recommendations": recommendations,
            "cross_module_chains": chains, "hypothesis_evaluations": hypothesis_evaluations,
            "critical": critical, "confidence_overall": round(confidence, 4),
        }

    def analyze_signals(self, signals: list[dict]) -> dict:
        """Group, rank, and pattern-flag signals."""
        if not signals:
            return {"overall_assessment": "无可用信号。", "key_patterns": [],
                    "grouped": {}, "highest_confidence_signal": None}
        valid = [s for s in signals if isinstance(s, dict)]
        by_type: dict[str, list[dict]] = {}
        by_source: dict[str, list[dict]] = {}
        for s in valid:
            by_type.setdefault(s.get("type", "unknown"), []).append(s)
            by_source.setdefault(s.get("source", "unknown"), []).append(s)
        sorted_by_conf = sorted(valid, key=lambda s: s.get("confidence", 0.0), reverse=True)
        highest = sorted_by_conf[0] if sorted_by_conf else None
        patterns: list[str] = []
        dates = []
        for s in valid:
            ev = s.get("evidence", {})
            if isinstance(ev, dict):
                for k in ("preprint_date", "journal_date", "date", "submission_date"):
                    if ev.get(k):
                        dates.append(str(ev[k]))
                        break
        if len(dates) >= 3:
            patterns.append(f"temporal_clustering: {len(dates)} 个时间标记信号，可能存在时间窗口压缩")
        if len(by_source) >= 2:
            patterns.append(f"platform_spanning: 信号横跨 {len(by_source)} 个来源 ({', '.join(by_source.keys())})")
        if len(sorted_by_conf) >= 2:
            hi, lo = sorted_by_conf[0].get("confidence", 0.0), sorted_by_conf[-1].get("confidence", 0.0)
            if hi - lo > 0.3:
                patterns.append(f"confidence_gradient: 最高置信度 {hi:.2f} 与最低 {lo:.2f} 差距显著，暗示证据质量不均")
        hc = highest.get("confidence", 0.0) if highest else 0.0
        if hc >= 0.8:
            assessment = f"最高置信度信号达 {hc:.2f}，存在值得深入调查的强异常。"
        elif hc >= 0.5:
            assessment = f"存在中等置信度信号 ({hc:.2f})，建议结合其他模块交叉验证。"
        else:
            assessment = "所有信号置信度均偏低，尚不足以构成独立判断依据。"
        return {
            "overall_assessment": assessment, "key_patterns": patterns,
            "grouped": {"by_type": {k: len(v) for k, v in by_type.items()},
                        "by_source": {k: len(v) for k, v in by_source.items()}},
            "highest_confidence_signal": {
                "type": highest.get("type") if highest else None,
                "confidence": highest.get("confidence") if highest else None,
                "description": highest.get("description") if highest else None,
            },
        }

    def _read_all_signals(self) -> list[dict]:
        """Helper: ingest every signal from outputs/*.json."""
        all_signals: list[dict] = []
        for opath in self.list_outputs():
            data = self.read_json(str(opath.relative_to(self.case_dir)))
            if isinstance(data, dict):
                all_signals.extend([s for s in data.get("signals", []) if isinstance(s, dict)])
        return all_signals

    def _build_chain(self, chain_type: str, signal_types: tuple[str, ...], description: str,
                     all_signals: list[dict]) -> dict | None:
        """Helper: assemble a chain dict if any of the signal types are present."""
        contrib = [s for s in all_signals if s.get("type") in signal_types]
        if not contrib:
            return None
        confs = [s.get("confidence", 0.0) for s in contrib]
        avg_conf = sum(confs) / len(confs) if confs else 0.0
        return {
            "chain_type": chain_type, "confidence": round(avg_conf, 4),
            "contributing_signals": [
                {"type": s.get("type"), "source": s.get("source"), "confidence": s.get("confidence")}
                for s in contrib
            ],
            "description": description,
        }

    def cross_module_correlation(self, outputs: list[Path]) -> list[dict]:
        """Detect multi-module evidence chains."""
        all_signals: list[dict] = []
        for opath in outputs:
            data = self.read_json(str(opath.relative_to(self.case_dir)))
            if isinstance(data, dict):
                all_signals.extend([s for s in data.get("signals", []) if isinstance(s, dict)])
        signal_types = {s.get("type", "") for s in all_signals}
        chains: list[dict] = []
        if "stats_anomaly" in signal_types and "image_duplicate" in signal_types:
            chain = self._build_chain(
                "data_fabrication_chain",
                ("stats_anomaly", "image_duplicate"),
                "统计异常与图像重复同时出现，构成数据捏造链。统计数据的不合理分布配合图像层面的复制痕迹，强烈暗示实验数据被人为构造或篡改。",
                all_signals,
            )
            if chain:
                chains.append(chain)
        has_preprint_overlap = "preprint_overlap" in signal_types or "duplicate_submission" in signal_types
        has_fast_review = "fast_review" in signal_types or "suspicious_gap" in signal_types
        has_editorial_self = "editorial_self_publish" in signal_types
        if has_preprint_overlap and has_fast_review and has_editorial_self:
            chain = self._build_chain(
                "review_bypass_chain",
                ("preprint_overlap", "duplicate_submission", "fast_review", "suspicious_gap", "editorial_self_publish"),
                "预印本重叠、快速审稿与编辑自发表同时出现，构成审稿绕过链。作者可能通过预印本抢占优先权，再利用编辑关系快速通过审稿，形成对传统同行评审机制的系统性规避。",
                all_signals,
            )
            if chain:
                chains.append(chain)
        if "missing_registry" in signal_types and "missing_ethics_statement" in signal_types:
            chain = self._build_chain(
                "ethics_violation_chain",
                ("missing_registry", "missing_ethics_statement"),
                "临床试验注册缺失与伦理声明缺失同时出现，构成伦理违规链。涉及人体或动物实验的研究若缺乏注册记录和伦理审查文件，可能存在未经审批开展实验的严重合规风险。",
                all_signals,
            )
            if chain:
                chains.append(chain)
        if not chains and len(all_signals) >= 3:
            confs = [s.get("confidence", 0.0) for s in all_signals]
            avg_conf = sum(confs) / len(confs) if confs else 0.0
            chains.append({
                "chain_type": "general_suspicion_cluster", "confidence": round(avg_conf, 4),
                "contributing_signals": [
                    {"type": s.get("type"), "source": s.get("source"), "confidence": s.get("confidence")}
                    for s in all_signals
                ],
                "description": f"检测到 {len(all_signals)} 个独立信号，虽未形成明确命名链条，但信号密度已超出随机噪声预期，建议继续深挖。",
            })
        return sorted(chains, key=lambda c: c.get("confidence", 0.0), reverse=True)

    def evaluate_hypothesis(self, hypothesis: dict) -> dict:
        """Assess a Huangmao hypothesis against the evidence landscape."""
        hypo_cred = hypothesis.get("credibility", "")
        hypo_tools = hypothesis.get("suggested_tools", [])
        all_signals = self._read_all_signals()
        combined_text = f"{hypothesis.get('description', '')} {hypothesis.get('reasoning', '')}".lower()
        supporting_signals = []
        for s in all_signals:
            desc = s.get("description", "").lower()
            stype = s.get("type", "").lower()
            if any(kw in combined_text for kw in desc.split()) or any(kw in combined_text for kw in stype.split("_")):
                supporting_signals.append(s)
        support_confs = [s.get("confidence", 0.0) for s in supporting_signals]
        max_support = max(support_confs) if support_confs else 0.0
        avg_support = sum(support_confs) / len(support_confs) if support_confs else 0.0
        base_verdict = {"strongly_suggested": "supported", "plausible": "plausible",
                        "wild_guess": "weak", "refuted": "refuted"}.get(hypo_cred, "weak")
        if base_verdict == "supported" and max_support < 0.5:
            verdict, reasoning = "plausible", f"假设逻辑自洽，但现有信号最高置信度仅 {max_support:.2f}，建议按黄毛建议的工具继续取证。"
        elif base_verdict == "weak" and max_support >= 0.7:
            verdict, reasoning = "plausible", f"黄毛标记为大胆猜测，但现有证据中存在 {max_support:.2f} 置信度的支持信号，使该假设升级为值得验证的方向。"
        elif base_verdict == "plausible" and max_support >= 0.8:
            verdict, reasoning = "supported", f"假设与 {len(supporting_signals)} 个信号形成呼应，最高置信度 {max_support:.2f}，证据支撑充分。"
        elif base_verdict == "refuted":
            verdict, reasoning = "refuted", "现有证据直接反驳该假设，或无支持信号。"
        else:
            verdict, reasoning = base_verdict, f"假设可信度为 {hypo_cred}，现有 {len(supporting_signals)} 个相关信号，平均置信度 {avg_support:.2f}。"
        merged_tools = list(hypo_tools)
        for s in supporting_signals:
            src = s.get("source", "")
            if src and src not in merged_tools:
                merged_tools.append(src)
        return {
            "hypothesis_id": hypothesis.get("id"), "verdict": verdict,
            "reasoning": reasoning, "supporting_signals_count": len(supporting_signals),
            "suggested_tools": merged_tools,
        }

    def generate_recommendations(self, analysis: dict) -> list[dict]:
        """Build prioritized tool recommendations from RuleEngine + dynamic chains."""
        baseline = RuleEngine().evaluate(self.case_dir)
        recs: list[dict] = []
        seen_tools: set[str] = set()
        for rec in baseline:
            for tool in rec.tools:
                if tool in seen_tools:
                    continue
                seen_tools.add(tool)
                recs.append({
                    "priority": rec.priority, "tool": tool, "reason": rec.reason,
                    "expected_value": f"基于规则 {rec.rule_id} 的自动化触发，来源: {rec.trigger_source}",
                    "rule_id": rec.rule_id,
                })
        chain_recs: dict[str, tuple[int, str, str, str]] = {
            "data_fabrication_chain": (1, "data_forensics/stats_reverse_engineer",
                "数据捏造链已激活：统计异常与图像重复并存，需深度数据取证。",
                "定位统计不一致与图像篡改的精确位置，量化造假程度"),
            "review_bypass_chain": (1, "peer_review_intel/review_cycle_analyzer",
                "审稿绕过链已激活：预印本重叠、快速审稿与编辑自发表形成闭环。",
                "追踪异常审稿周期，识别编辑利益冲突网络"),
            "ethics_violation_chain": (1, "ethics_audit/clinical_trial_registry_checker",
                "伦理违规链已激活：临床注册与伦理声明同时缺失。",
                "交叉验证WHO临床试验注册平台与机构伦理审查记录"),
        }
        for chain in analysis.get("chains", []):
            c_type, c_conf = chain.get("chain_type", ""), chain.get("confidence", 0.0)
            if c_type in chain_recs:
                pri, tool, reason, ev = chain_recs[c_type]
                if tool not in seen_tools:
                    seen_tools.add(tool)
                    recs.append({"priority": pri, "tool": tool, "reason": reason,
                                 "expected_value": ev, "rule_id": f"DYNAMIC-{c_type.upper().replace('_', '-')}"})
            elif c_type == "general_suspicion_cluster" and c_conf >= 0.6:
                tool = "evidence_compiler/signal_aggregator"
                if tool not in seen_tools:
                    seen_tools.add(tool)
                    recs.append({"priority": 2, "tool": tool,
                                 "reason": "高密度未分类信号集群 detected，建议用信号聚合器重新归类。",
                                 "expected_value": "从无序信号中提取隐藏模式，生成新的假设方向",
                                 "rule_id": "DYNAMIC-CLUSTER"})
        for heval in analysis.get("hypothesis_evaluations", []):
            if heval.get("verdict") in ("supported", "plausible"):
                for tool in heval.get("suggested_tools", []):
                    if "/" not in tool or tool in seen_tools:
                        continue
                    seen_tools.add(tool)
                    recs.append({
                        "priority": 2, "tool": tool,
                        "reason": f"假设 #{heval.get('hypothesis_id')} 评估为 {heval['verdict']}，推荐跟进。",
                        "expected_value": f"验证假设可信度，当前支持信号数: {heval.get('supporting_signals_count', 0)}",
                        "rule_id": f"DYNAMIC-HYP-{heval.get('hypothesis_id', 'UNK')}",
                    })
        recs.sort(key=lambda r: r["priority"])
        return recs

    def assess_confidence(self, signals: list[dict]) -> float:
        """Calculate overall confidence: geometric mean of top 3, boosted 0.1 per extra source, max 0.95."""
        valid = [s.get("confidence", 0.0) for s in signals
                 if isinstance(s, dict) and isinstance(s.get("confidence"), (int, float))]
        if not valid:
            return 0.0
        top3 = sorted(valid, reverse=True)[:3]
        geo_mean = math.prod(top3) ** (1.0 / len(top3))
        sources = {s["source"] for s in signals if isinstance(s, dict) and s.get("source")}
        boost = max(0, len(sources) - 1) * 0.1
        return round(min(geo_mean + boost, 0.95), 4)
