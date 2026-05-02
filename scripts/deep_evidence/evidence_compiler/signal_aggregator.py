#!/usr/bin/env python3
"""
signal_aggregator.py

Aggregate signals from all deep_evidence sub-modules into a unified report.
Scans JSON outputs from various scripts, normalizes signals, deduplicates,
and ranks them by confidence.

Supported input schemas:
    - signals / alerts / anomalies lists from any deep_evidence module

Confidence rules:
    - Single-source signal: capped at 0.60
    - Two independent sources corroborating: boosted to 0.75
    - Three or more sources, or strong statistical evidence: up to 0.90

Usage:
    python signal_aggregator.py --signals-dir ./data/deep_evidence/ --output ./data/aggregated_signals.json
    python signal_aggregator.py --signals-dir ./data/deep_evidence/ --output ./data/aggregated_signals.json --min-confidence 0.5
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

logger = get_logger("signal_aggregator")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Signal:
    source: str
    type: str
    description: str
    confidence: float
    evidence: dict
    timestamp: Optional[str]
    paper_id: Optional[str]


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def _normalize_signal(raw: dict, source_file: str) -> Optional[Signal]:
    """Validate and convert a raw signal dict into the Signal dataclass."""
    if not isinstance(raw, dict):
        return None

    sig_type = raw.get("type")
    description = raw.get("description")
    if not sig_type or not description:
        return None

    confidence = raw.get("confidence", 0.5)
    if isinstance(confidence, str):
        confidence = {"high": 0.8, "medium": 0.5, "low": 0.3}.get(confidence.lower(), 0.5)
    try:
        confidence = float(confidence)
    except (ValueError, TypeError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    evidence = raw.get("evidence", {})
    if not isinstance(evidence, dict):
        evidence = {}

    timestamp = raw.get("timestamp") or raw.get("queried_at")
    paper_id = raw.get("paper_id") or raw.get("doi") or raw.get("id")
    source_name = raw.get("source") or Path(source_file).stem

    return Signal(
        source=source_name,
        type=sig_type,
        description=description,
        confidence=confidence,
        evidence=evidence,
        timestamp=timestamp,
        paper_id=paper_id,
    )


def _extract_signals_from_file(path: Path) -> list[Signal]:
    signals: list[Signal] = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Skipping unreadable file %s: %s", path, exc)
        return signals

    candidates = []
    if isinstance(data, dict):
        candidates = data.get("signals", [])
    elif isinstance(data, list):
        candidates = data

    for raw in candidates:
        if isinstance(raw, dict):
            sig = _normalize_signal(raw, path.name)
            if sig:
                signals.append(sig)

    return signals


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def _description_overlap(a: str, b: str) -> float:
    """Simple Jaccard-like overlap on words."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    inter = words_a & words_b
    union = words_a | words_b
    return len(inter) / len(union)


def deduplicate(signals: list[Signal], overlap_threshold: float = 0.75) -> list[Signal]:
    """Deduplicate signals by type + description overlap across different sources."""
    deduped: list[Signal] = []
    for sig in signals:
        merged = False
        for existing in deduped:
            if sig.type != existing.type:
                continue
            if _description_overlap(sig.description, existing.description) >= overlap_threshold:
                # Merge: keep higher confidence, combine evidence
                existing.confidence = max(existing.confidence, sig.confidence)
                existing.evidence.update(sig.evidence)
                if not existing.paper_id and sig.paper_id:
                    existing.paper_id = sig.paper_id
                # Track multiple sources in evidence
                sources = set(existing.evidence.get("__sources", [existing.source]))
                sources.add(sig.source)
                existing.evidence["__sources"] = sorted(sources)
                existing.source = "multi_source"
                merged = True
                break
        if not merged:
            deduped.append(sig)
    return deduped


# ---------------------------------------------------------------------------
# Confidence boosting
# ---------------------------------------------------------------------------


def apply_confidence_rules(signals: list[Signal]) -> list[Signal]:
    for sig in signals:
        sources = set()
        if sig.source == "multi_source":
            src_list = sig.evidence.get("__sources", [])
            sources = set(src_list) if src_list else {"multi_source"}
        else:
            sources = {sig.source}

        source_count = len(sources)

        if source_count == 1:
            sig.confidence = min(sig.confidence, 0.60)
        elif source_count == 2:
            sig.confidence = max(sig.confidence, 0.75)
            sig.confidence = min(sig.confidence, 0.85)
        elif source_count >= 3:
            sig.confidence = max(sig.confidence, 0.80)
            sig.confidence = min(sig.confidence, 0.90)

        # Boost for strong statistical evidence fields
        if any(k in sig.evidence for k in ("expected", "reported", "deviation_factor", "benchmark_median")):
            sig.confidence = min(sig.confidence + 0.05, 0.90)

        sig.confidence = round(sig.confidence, 2)
    return signals


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Aggregate and deduplicate deep_evidence signals")
    p.add_argument("--signals-dir", type=Path, required=True, help="Directory containing JSON signal files")
    p.add_argument("--output", type=Path, default=Path("./data/aggregated_signals.json"), help="Output JSON path")
    p.add_argument("--min-confidence", type=float, default=0.5, help="Minimum confidence to include")
    p.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    return p


def main():
    args = build_parser().parse_args()
    if args.verbose:
        logger.setLevel(10)

    if not args.signals_dir.exists():
        logger.error("Signals directory not found: %s", args.signals_dir)
        sys.exit(1)

    json_files = sorted(args.signals_dir.glob("*.json"))
    logger.info("Found %d JSON files in %s", len(json_files), args.signals_dir)

    all_signals: list[Signal] = []
    for jf in json_files:
        sigs = _extract_signals_from_file(jf)
        logger.info("%s: extracted %d signals", jf.name, len(sigs))
        all_signals.extend(sigs)

    logger.info("Total raw signals: %d", len(all_signals))

    deduped = deduplicate(all_signals)
    ranked = apply_confidence_rules(deduped)
    ranked = [s for s in ranked if s.confidence >= args.min_confidence]
    ranked.sort(key=lambda s: -s.confidence)

    # Category summary
    by_category: dict[str, int] = {}
    high_confidence = 0
    for s in ranked:
        by_category[s.type] = by_category.get(s.type, 0) + 1
        if s.confidence >= 0.7:
            high_confidence += 1

    by_source: dict[str, int] = {}
    for s in all_signals:
        by_source[s.source] = by_source.get(s.source, 0) + 1
    dropped = len(all_signals) - len(ranked)

    result = {
        "meta": {
            "script": "signal_aggregator",
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "input_file": str(args.signals_dir),
            "files_scanned": len(json_files),
            "raw_signals": len(all_signals),
            "deduplicated_signals": len(deduped),
            "final_signals": len(ranked),
            "high_confidence_count": high_confidence,
            "min_confidence": args.min_confidence,
        },
        "signals": [asdict(s) for s in ranked],
        "details": {
            "by_source": by_source,
            "dropped": dropped,
        },
    }

    save_json(result, args.output)
    logger.info("Saved aggregated signals to %s", args.output)

    print(f"\n{'='*60}")
    print(f"Signal Aggregator Summary")
    print(f"{'='*60}")
    print(f"Files scanned:     {len(json_files)}")
    print(f"Raw signals:       {len(all_signals)}")
    print(f"After dedup:       {len(deduped)}")
    print(f"Final signals:     {len(ranked)} (>= {args.min_confidence})")
    print(f"High confidence:   {high_confidence} (>= 0.70)")
    if by_category:
        print(f"\nBy category:")
        for cat, cnt in sorted(by_category.items(), key=lambda x: -x[1])[:8]:
            print(f"  {cat}: {cnt}")
    print(f"\nOutput:           {args.output}")


if __name__ == "__main__":
    main()
