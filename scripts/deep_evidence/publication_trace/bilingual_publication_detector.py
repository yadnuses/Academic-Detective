#!/usr/bin/env python3
"""
bilingual_publication_detector.py

Detect bilingual publication where the same research is published in Chinese
and English without cross-reference. Handles Chinese name variations and
title translation similarity.

Supported sources: local unified paper list (mixed CNKI / WoS / Scopus sources).

Usage:
    python bilingual_publication_detector.py --papers ./data/papers.json \
        --output ./data/bilingual_detect.json [--year-window 24] [--verbose]
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import Optional
import sys
import difflib
import re

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.utils import get_logger, save_json

logger = get_logger("bilingual_publication_detector")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class BilingualPair:
    chinese_title: str
    chinese_authors: list[str]
    chinese_year: Optional[int]
    chinese_source: str
    chinese_id: str
    english_title: str
    english_authors: list[str]
    english_year: Optional[int]
    english_source: str
    english_id: str
    title_similarity: float
    author_match_ratio: float
    abstract_similarity: Optional[float]
    year_gap_months: Optional[int]
    pair_type: str            # bilingual_pair | undisclosed_bilingual | salami_bilingual
    confidence: str           # low | medium | high
    explanation: str


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

def _cjk_ratio(text: str) -> float:
    if not text:
        return 0.0
    cjk_count = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return cjk_count / len(text)


def is_chinese_title(title: str) -> bool:
    return _cjk_ratio(title) > 0.30


# ---------------------------------------------------------------------------
# Name normalization helpers
# ---------------------------------------------------------------------------

def _normalize_name(name: str) -> str:
    """Normalize whitespace and case."""
    return name.lower().strip().replace(" ", "").replace("·", "").replace(".", "")


def _pinyin_like(name: str) -> str:
    """Very light heuristic: strip non-ascii to get pinyin-ish core."""
    return re.sub(r"[^a-z]", "", name.lower())


def _name_match_chinese_en(cn_name: str, en_name: str) -> bool:
    """
    Heuristic match between Chinese name and English name.
    e.g. 张三 <-> Zhang San, San Zhang
    """
    cn = _normalize_name(cn_name)
    en = _normalize_name(en_name)

    # Direct substring
    if cn in en or en in cn:
        return True

    # Split English name
    parts = en_name.lower().strip().split()
    if len(parts) >= 2:
        family = parts[-1]
        given = "".join(parts[:-1])
        # Zhang San -> family=San, given=Zhang; we try both orders
        if family in cn or given in cn:
            return True
        if cn and len(cn) == 2:
            # Two-character Chinese name: 张三
            if family == cn[1] and given.startswith(cn[0]):
                return True
            if family == cn[0] and given.startswith(cn[1]):
                return True
    return False


def _author_overlap_ratio(chinese_authors: list[str], english_authors: list[str]) -> float:
    if not chinese_authors or not english_authors:
        return 0.0

    matches = 0
    for ca in chinese_authors:
        ca_norm = _normalize_name(ca)
        for ea in english_authors:
            ea_norm = _normalize_name(ea)
            if ca_norm == ea_norm:
                matches += 1
                break
            if _name_match_chinese_en(ca, ea):
                matches += 1
                break

    return matches / max(len(chinese_authors), len(english_authors))


# ---------------------------------------------------------------------------
# Title similarity
# ---------------------------------------------------------------------------

STOP_WORDS = set([
    "a", "an", "the", "and", "or", "of", "in", "on", "at", "to", "for",
    "with", "by", "from", "study", "analysis", "effect", "effects",
    "基于", "研究", "分析", "影响", "的", "了", "与", "和", "对",
])


def _clean_title(title: str) -> str:
    """Remove common words and punctuation for cleaner comparison."""
    t = title.lower()
    for p in "，。、；：！？\"“”‘’《》【】()[]{},.!?;:-":
        t = t.replace(p, " ")
    words = [w for w in t.split() if w and w not in STOP_WORDS and len(w) > 1]
    return " ".join(words)


def _title_similarity(a: str, b: str) -> float:
    ca = _clean_title(a)
    cb = _clean_title(b)
    if not ca or not cb:
        return 0.0
    return difflib.SequenceMatcher(None, ca, cb).ratio()


# ---------------------------------------------------------------------------
# Abstract similarity
# ---------------------------------------------------------------------------

def _abstract_similarity(abs_a: Optional[str], abs_b: Optional[str]) -> Optional[float]:
    if not abs_a or not abs_b:
        return None
    a = _clean_title(abs_a)
    b = _clean_title(abs_b)
    if not a or not b:
        return None
    return difflib.SequenceMatcher(None, a, b).ratio()


# ---------------------------------------------------------------------------
# Year helpers
# ---------------------------------------------------------------------------

def _extract_year(paper: dict) -> Optional[int]:
    for key in ("year", "date", "publication_date", "published"):
        val = paper.get(key)
        if val:
            try:
                return int(str(val)[:4])
            except ValueError:
                continue
    return None


# ---------------------------------------------------------------------------
# Core detection
# ---------------------------------------------------------------------------

def detect_bilingual_pairs(
    papers: list[dict],
    year_window: int = 24,
) -> list[BilingualPair]:
    chinese_papers = [p for p in papers if is_chinese_title(str(p.get("title", "")))]
    english_papers = [p for p in papers if not is_chinese_title(str(p.get("title", "")))]

    logger.info("Language split: %d Chinese, %d English papers", len(chinese_papers), len(english_papers))

    pairs: list[BilingualPair] = []

    for cp in chinese_papers:
        c_title = str(cp.get("title", ""))
        c_authors = cp.get("authors", [])
        if isinstance(c_authors, str):
            c_authors = [a.strip() for a in c_authors.split(",") if a.strip()]
        c_year = _extract_year(cp)
        c_source = str(cp.get("source", cp.get("database", cp.get("journal", ""))))
        c_id = str(cp.get("id", cp.get("doi", c_title[:40])))
        c_abstract = str(cp.get("abstract", ""))

        best_match: Optional[BilingualPair] = None
        best_score = 0.0

        for ep in english_papers:
            e_title = str(ep.get("title", ""))
            e_authors = ep.get("authors", [])
            if isinstance(e_authors, str):
                e_authors = [a.strip() for a in e_authors.split(",") if a.strip()]
            e_year = _extract_year(ep)
            e_source = str(ep.get("source", ep.get("database", ep.get("journal", ""))))
            e_id = str(ep.get("id", ep.get("doi", e_title[:40])))
            e_abstract = str(ep.get("abstract", ""))

            # Year proximity
            if c_year and e_year:
                gap = abs((c_year - e_year) * 12)
                if gap > year_window:
                    continue
            else:
                gap = None

            title_sim = _title_similarity(c_title, e_title)
            if title_sim < 0.50:
                continue

            author_ratio = _author_overlap_ratio(c_authors, e_authors)
            if author_ratio < 0.30:
                continue

            abs_sim = _abstract_similarity(c_abstract, e_abstract)

            # Determine pair type and confidence
            if title_sim >= 0.80 and author_ratio >= 0.50:
                if gap is not None and gap <= 12:
                    pair_type = "bilingual_pair"
                    confidence = "high"
                    explanation = f"标题相似度{title_sim:.2f}，作者匹配率{author_ratio:.2f}，发表时间接近({gap}个月)"
                else:
                    pair_type = "bilingual_pair"
                    confidence = "medium"
                    explanation = f"标题与作者高度匹配，时间间隔{gap if gap is not None else '未知'}个月"
            elif title_sim >= 0.60 and author_ratio >= 0.30:
                pair_type = "undisclosed_bilingual"
                confidence = "medium"
                explanation = f"标题相似度{title_sim:.2f}，作者匹配率{author_ratio:.2f}，疑似未披露双语发表"
            else:
                pair_type = "undisclosed_bilingual"
                confidence = "low"
                explanation = f"标题相似度{title_sim:.2f}，作者匹配率{author_ratio:.2f}，匹配较弱"

            # Salami override: abstracts very similar
            if abs_sim is not None and abs_sim > 0.80:
                pair_type = "salami_bilingual"
                explanation += f"，摘要高度相似({abs_sim:.2f})，疑似内容重复发表"
                if confidence == "low":
                    confidence = "medium"

            score = title_sim * 0.5 + author_ratio * 0.5
            if score > best_score:
                best_score = score
                best_match = BilingualPair(
                    chinese_title=c_title,
                    chinese_authors=c_authors,
                    chinese_year=c_year,
                    chinese_source=c_source,
                    chinese_id=c_id,
                    english_title=e_title,
                    english_authors=e_authors,
                    english_year=e_year,
                    english_source=e_source,
                    english_id=e_id,
                    title_similarity=round(title_sim, 3),
                    author_match_ratio=round(author_ratio, 3),
                    abstract_similarity=round(abs_sim, 3) if abs_sim is not None else None,
                    year_gap_months=gap,
                    pair_type=pair_type,
                    confidence=confidence,
                    explanation=explanation,
                )

        if best_match:
            pairs.append(best_match)

    # Deduplicate by Chinese paper id (keep best score per Chinese paper)
    seen: dict[str, BilingualPair] = {}
    for p in pairs:
        if p.chinese_id not in seen:
            seen[p.chinese_id] = p
        else:
            old = seen[p.chinese_id]
            old_score = old.title_similarity + old.author_match_ratio
            new_score = p.title_similarity + p.author_match_ratio
            if new_score > old_score:
                seen[p.chinese_id] = p

    final_pairs = list(seen.values())
    conf_order = {"high": 0, "medium": 1, "low": 2}
    final_pairs.sort(key=lambda x: (conf_order.get(x.confidence, 3), -(x.title_similarity + x.author_match_ratio)))
    return final_pairs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Detect bilingual publication pairs")
    p.add_argument("--papers", type=Path, required=True, help="Path to unified papers JSON")
    p.add_argument("--output", type=Path, default=Path("./data/bilingual_detect.json"), help="Output JSON path")
    p.add_argument("--year-window", type=int, default=24, help="Max months between Chinese and English publication")
    p.add_argument("--verbose", action="store_true", help="Verbose logging")
    return p


def main():
    args = build_parser().parse_args()
    if args.verbose:
        logger.setLevel("DEBUG")

    if not args.papers.exists():
        logger.error("Papers file not found: %s", args.papers)
        sys.exit(1)

    with open(args.papers, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    paper_list = raw if isinstance(raw, list) else raw.get("papers", [])
    logger.info("Loaded %d papers", len(paper_list))

    pairs = detect_bilingual_pairs(paper_list, args.year_window)

    undisclosed = [p for p in pairs if p.pair_type == "undisclosed_bilingual"]
    salami = [p for p in pairs if p.pair_type == "salami_bilingual"]

    def _pair_confidence(conf: str) -> float:
        return {"low": 0.3, "medium": 0.5, "high": 0.8}.get(conf, 0.5)

    signals = []
    for p in pairs:
        if p.pair_type == "bilingual_pair":
            continue
        signals.append({
            "type": p.pair_type,
            "description": p.explanation[:200],
            "confidence": _pair_confidence(p.confidence),
            "paper_id": p.english_title,
            "source": "bilingual_publication_detector",
            "evidence": {
                "chinese_title": p.chinese_title,
                "similarity_score": p.title_similarity,
            },
        })

    result = {
        "meta": {
            "script": "bilingual_publication_detector",
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "input_file": str(args.papers),
        },
        "signals": signals,
        "details": {
            "pairs": [asdict(p) for p in pairs],
            "summary": {
                "bilingual_pair": sum(1 for p in pairs if p.pair_type == "bilingual_pair"),
                "undisclosed_bilingual": len(undisclosed),
                "salami_bilingual": len(salami),
            },
        },
    }

    save_json(result, args.output)
    logger.info("Saved bilingual detection to %s", args.output)

    print(f"\n{'='*60}")
    print("Bilingual Publication Detector Summary")
    print(f"{'='*60}")
    print(f"Papers scanned:          {len(paper_list)}")
    print(f"Bilingual pairs found:   {len(pairs)}")
    print(f"  Confirmed pair:        {result['summary']['bilingual_pair']}")
    print(f"  Undisclosed:           {result['summary']['undisclosed_bilingual']}")
    print(f"  Salami bilingual:      {result['summary']['salami_bilingual']}")
    if pairs:
        print(f"\nTop pairs:")
        for p in pairs[:5]:
            print(f"  [{p.confidence.upper()}] {p.chinese_title[:30]}... <=> {p.english_title[:30]}...")
            print(f"    {p.explanation}")
    print(f"\nOutput:                  {args.output}")


if __name__ == "__main__":
    main()
