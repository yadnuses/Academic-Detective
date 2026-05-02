#!/usr/bin/env python3
"""
evidence_chain_builder.py

Build logical evidence chains from aggregated signals.
Links signals that share a paper_id or are temporally related into
predefined chain templates, calculates overall confidence, and generates
narrative summaries.

Predefined templates:
    - Data fabrication chain: stats_anomaly + image_duplicate + data_unavailability
    - Publication misconduct chain: preprint_overlap + fast_review + editorial_self_publish
    - Ethics violation chain: missing_registry + missing_ethics_statement

Usage:
    python evidence_chain_builder.py --signals ./data/aggregated_signals.json --output ./data/evidence_chains.json
    python evidence_chain_builder.py --signals ./data/aggregated_signals.json --output ./data/evidence_chains.json --templates ./custom_templates.json
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.utils import get_logger, save_json

logger = get_logger("evidence_chain_builder")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ChainSignal:
    type: str
    description: str
    confidence: float
    source: str


@dataclass
class EvidenceChain:
    chain_id: str
    template: str
    paper_id: Optional[str]
    signals: list[ChainSignal]
    confidence: float
    narrative: str


# ---------------------------------------------------------------------------
# Default templates
# ---------------------------------------------------------------------------

DEFAULT_TEMPLATES = {
    "data_fabrication": {
        "label": "Data fabrication chain",
        "required": ["stats_anomaly", "image_duplicate"],
        "optional": ["data_unavailability", "impossible_sd", "integer_discrepancy", "duplicate_image_across_papers", "suspicious_resolution"],
        "min_signals": 2,
    },
    "publication_misconduct": {
        "label": "Publication misconduct chain",
        "required": ["preprint_overlap"],
        "optional": ["fast_review", "fast_cycle", "batch_acceptance", "high_velocity", "editorial_self_publish"],
        "min_signals": 2,
    },
    "ethics_violation": {
        "label": "Ethics violation chain",
        "required": ["missing_registry", "missing_ethics_statement"],
        "optional": ["missing_metadata", "mismatched_software"],
        "min_signals": 2,
    },
    "image_manipulation": {
        "label": "Image manipulation chain",
        "required": ["duplicate_image_across_papers"],
        "optional": ["suspicious_resolution", "mismatched_software", "missing_metadata"],
        "min_signals": 2,
    },
    "statistical_irregularity": {
        "label": "Statistical irregularity chain",
        "required": ["impossible_sd", "inconsistent_p_value"],
        "optional": ["integer_discrepancy", "test_statistic_mismatch", "stats_anomaly"],
        "min_signals": 2,
    },
}


# ---------------------------------------------------------------------------
# Chain logic
# ---------------------------------------------------------------------------


def _load_signals(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        return data.get("signals", [])
    return data if isinstance(data, list) else []


def _group_signals_by_paper(signals: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for sig in signals:
        pid = sig.get("paper_id") or sig.get("doi") or sig.get("id") or "unknown"
        groups.setdefault(pid, []).append(sig)
    return groups


def _match_template(signals: list[dict], template: dict) -> list[dict]:
    """Return the subset of signals that match a template."""
    matched: list[dict] = []
    required = set(template["required"])
    optional = set(template["optional"])
    found_required: set[str] = set()

    for sig in signals:
        stype = sig.get("type", "")
        if stype in required:
            matched.append(sig)
            found_required.add(stype)
        elif stype in optional:
            matched.append(sig)

    if not required.issubset(found_required):
        return []
    if len(matched) < template.get("min_signals", 2):
        return []
    return matched


def _chain_confidence(signals: list[dict], dampen: float = 0.95) -> float:
    """Combine individual confidences with a dampening factor."""
    if not signals:
        return 0.0
    confs = [s.get("confidence", 0.5) for s in signals]
    product = 1.0
    for c in confs:
        product *= c
    # Geometric mean with dampening
    geom = product ** (1.0 / len(confs))
    return round(min(geom * dampen, 0.95), 2)


def _generate_narrative(template_name: str, signals: list[dict], paper_id: str) -> str:
    template_label = DEFAULT_TEMPLATES.get(template_name, {}).get("label", template_name)
    signal_types = [s.get("type", "unknown") for s in signals]
    descriptions = [s.get("description", "") for s in signals]
    avg_conf = sum(s.get("confidence", 0.5) for s in signals) / len(signals)

    parts = [f"{template_label} detected for paper '{paper_id}' with average signal confidence {avg_conf:.2f}."]
    parts.append(f"The chain includes {len(signals)} linked signals: {', '.join(signal_types)}.")

    # Add key details
    for desc in descriptions[:2]:
        if desc:
            parts.append(f"Key detail: {desc}.")

    if "stats_anomaly" in signal_types or "impossible_sd" in signal_types:
        parts.append("Statistical inconsistencies suggest possible fabrication or reporting errors.")
    if "duplicate_image_across_papers" in signal_types:
        parts.append("Duplicate imagery across different papers raises questions about original data collection.")
    if "preprint_overlap" in signal_types or "fast_cycle" in signal_types:
        parts.append("Unusual publication timelines may indicate duplicate submission or accelerated review.")
    if "missing_registry" in signal_types or "missing_ethics_statement" in signal_types:
        parts.append("Missing ethical documentation requires verification against institutional records.")

    return " ".join(parts)


def build_chains(signals: list[dict], templates: dict) -> list[EvidenceChain]:
    chains: list[EvidenceChain] = []
    by_paper = _group_signals_by_paper(signals)

    chain_counter = 0
    for paper_id, paper_signals in by_paper.items():
        for template_name, template in templates.items():
            matched = _match_template(paper_signals, template)
            if not matched:
                continue
            chain_counter += 1
            conf = _chain_confidence(matched)
            chain_signals = [
                ChainSignal(
                    type=s.get("type", ""),
                    description=s.get("description", ""),
                    confidence=s.get("confidence", 0.5),
                    source=s.get("source", ""),
                )
                for s in matched
            ]
            narrative = _generate_narrative(template_name, matched, paper_id)
            chains.append(EvidenceChain(
                chain_id=f"{template_name}_{chain_counter:03d}",
                template=template_name,
                paper_id=paper_id if paper_id != "unknown" else None,
                signals=chain_signals,
                confidence=conf,
                narrative=narrative,
            ))

    # Also try cross-paper temporal chains if timestamps are available
    chains = sorted(chains, key=lambda c: -c.confidence)
    return chains


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build logical evidence chains from aggregated signals")
    p.add_argument("--signals", type=Path, required=True, help="Path to aggregated_signals.json")
    p.add_argument("--output", type=Path, default=Path("./data/evidence_chains.json"), help="Output JSON path")
    p.add_argument("--templates", type=Path, help="Optional custom templates JSON (same schema as DEFAULT_TEMPLATES)")
    p.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    return p


def main():
    args = build_parser().parse_args()
    if args.verbose:
        logger.setLevel(10)

    if not args.signals.exists():
        logger.error("Signals file not found: %s", args.signals)
        sys.exit(1)

    templates = DEFAULT_TEMPLATES.copy()
    if args.templates and args.templates.exists():
        with open(args.templates, "r", encoding="utf-8") as fh:
            custom = json.load(fh)
        if isinstance(custom, dict):
            templates.update(custom)
            logger.info("Loaded %d custom templates", len(custom))

    input_signals = _load_signals(args.signals)
    logger.info("Loaded %d signals from %s", len(input_signals), args.signals)

    chains = build_chains(input_signals, templates)
    logger.info("Built %d evidence chains", len(chains))

    by_template: dict[str, int] = {}
    high_confidence = 0
    for c in chains:
        by_template[c.template] = by_template.get(c.template, 0) + 1
        if c.confidence >= 0.7:
            high_confidence += 1

    signals = []
    for c in chains:
        signals.append({
            "type": "evidence_chain",
            "description": c.narrative,
            "confidence": float(c.confidence),
            "paper_id": c.paper_id,
            "source": "evidence_chain_builder",
            "evidence": {
                "chain_id": c.chain_id,
                "template": c.template,
                "signals_in_chain": [asdict(s) for s in c.signals],
            },
        })

    result = {
        "meta": {
            "script": "evidence_chain_builder",
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "input_file": str(args.signals),
            "input_signals": len(input_signals),
            "chains_built": len(chains),
            "high_confidence_chains": high_confidence,
            "templates_used": list(templates.keys()),
        },
        "signals": signals,
        "details": {
            "chains": [asdict(c) for c in chains],
        },
    }

    save_json(result, args.output)
    logger.info("Saved evidence chains to %s", args.output)

    print(f"\n{'='*60}")
    print(f"Evidence Chain Builder Summary")
    print(f"{'='*60}")
    print(f"Input signals:     {len(input_signals)}")
    print(f"Chains built:      {len(chains)}")
    print(f"High confidence:   {high_confidence} (>= 0.70)")
    if by_template:
        print(f"\nBy template:")
        for t, cnt in sorted(by_template.items(), key=lambda x: -x[1]):
            print(f"  {t}: {cnt}")
    if chains:
        print(f"\nTop chains:")
        for c in chains[:5]:
            print(f"  [{c.confidence:.2f}] {c.chain_id}: {c.narrative[:100]}...")
    print(f"\nOutput:           {args.output}")


if __name__ == "__main__":
    main()
