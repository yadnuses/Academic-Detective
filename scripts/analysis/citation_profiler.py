#!/usr/bin/env python3
"""
citation_profiler.py

Academic citation profile analyzer for detecting metric gaming:
- h-index growth anomalies
- Self-citation / team-citation rates
- Mutual citation cartel signals
- Citing journal quality breakdown

Semi-automatic principle: human exports/records citation data from CNKI,
Google Scholar, or Web of Science; script performs quantitative analysis.

Usage:
    python citation_profiler.py --input ./citations.json --output ./citation_report.json

Input JSON schema:
{
  "scholar_name": "张三",
  "scholar_aliases": ["张三", "Zhang San"],
  "team_members": ["李四", "王五"],
  "yearly_h_index": [
    {"year": 2018, "h_index": 5, "total_citations": 120},
    ...
  ],
  "citations": [
    {
      "title": "...",
      "first_author": "张三",
      "authors": ["张三", "李四"],
      "institution": "某国家级研究机构",
      "journal": "顶级经济期刊",
      "year": 2020,
      "journal_tier": "A"
    },
    ...
  ],
  "scholar_citations_out": ["李四", "王五"]  // optional: authors the scholar cited back
}
"""

import json
import sys
import argparse
import math
from pathlib import Path
from collections import Counter, defaultdict


def load_data(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def analyze_h_index(yearly_data: list) -> dict:
    if not yearly_data or len(yearly_data) < 3:
        return {
            "note": "Insufficient yearly data for anomaly detection (minimum 3 years required).",
            "growth_rates": [],
            "anomalies": []
        }

    sorted_data = sorted(yearly_data, key=lambda x: x["year"])
    growth_rates = []
    for i in range(1, len(sorted_data)):
        prev = sorted_data[i - 1]["h_index"]
        curr = sorted_data[i]["h_index"]
        growth = curr - prev
        growth_rates.append({
            "year": sorted_data[i]["year"],
            "h_index": curr,
            "absolute_growth": growth,
            "previous_h_index": prev
        })

    if len(growth_rates) < 3:
        return {
            "growth_rates": growth_rates,
            "anomalies": [],
            "note": "Need at least 3 years of growth data for baseline comparison."
        }

    # Use rolling 3-year mean as baseline
    anomalies = []
    for i in range(3, len(growth_rates)):
        recent_3 = [g["absolute_growth"] for g in growth_rates[i-3:i]]
        baseline = sum(recent_3) / len(recent_3)
        current = growth_rates[i]["absolute_growth"]
        if baseline > 0 and current / baseline >= 3.0:
            anomalies.append({
                "year": growth_rates[i]["year"],
                "absolute_growth": current,
                "baseline_avg": round(baseline, 2),
                "ratio": round(current / baseline, 2),
                "severity": "high" if current / baseline >= 4.0 else "medium-high"
            })
        elif baseline == 0 and current >= 3:
            anomalies.append({
                "year": growth_rates[i]["year"],
                "absolute_growth": current,
                "baseline_avg": 0,
                "ratio": None,
                "severity": "high",
                "note": "Jump from zero baseline growth."
            })

    return {
        "growth_rates": growth_rates,
        "anomalies": anomalies,
        "note": None if anomalies else "No significant h-index growth anomalies detected."
    }


def classify_citations(citations: list, scholar_name: str, aliases: list, team: list, scholar_out: list) -> dict:
    aliases_lower = set((aliases or []) + [scholar_name])
    team_lower = set(team or [])
    scholar_out_lower = set(scholar_out or [])

    total = len(citations)
    self_count = 0
    team_count = 0
    mutual_count = 0
    third_party_count = 0

    author_counter = Counter()
    institution_counter = Counter()
    journal_counter = Counter()
    tier_counter = Counter()
    yearly_author_counter = defaultdict(Counter)

    for c in citations:
        authors = c.get("authors") or [c.get("first_author", "")]
        first_author = c.get("first_author", "")
        year = c.get("year")
        journal = c.get("journal", "Unknown")
        tier = c.get("journal_tier", "unclassified")
        institution = c.get("institution", "Unknown")

        author_counter[first_author] += 1
        institution_counter[institution] += 1
        journal_counter[journal] += 1
        tier_counter[tier] += 1
        if year:
            yearly_author_counter[year][first_author] += 1

        is_self = any(a in aliases_lower for a in authors)
        is_team = any(a in team_lower for a in authors) and not is_self
        is_mutual = any(a in scholar_out_lower for a in authors)

        if is_self:
            self_count += 1
        elif is_team:
            team_count += 1
        elif is_mutual:
            mutual_count += 1
            # Also count as third party for overall structure unless you want separate
            third_party_count += 1
        else:
            third_party_count += 1

    ratios = {
        "self_citation": round(self_count / total, 4) if total else 0,
        "team_citation": round(team_count / total, 4) if total else 0,
        "mutual_citation": round(mutual_count / total, 4) if total else 0,
        "third_party": round(third_party_count / total, 4) if total else 0
    }

    # Journal quality breakdown
    tier_breakdown = {}
    for tier, count in tier_counter.most_common():
        tier_breakdown[tier] = {
            "count": count,
            "ratio": round(count / total, 4)
        }

    # Author concentration
    top_authors = [
        {"author": name, "count": cnt, "ratio": round(cnt / total, 4)}
        for name, cnt in author_counter.most_common(10)
    ]

    # Institutional concentration
    top_institutions = [
        {"institution": name, "count": cnt, "ratio": round(cnt / total, 4)}
        for name, cnt in institution_counter.most_common(10)
    ]

    # Detect dense mutual-citation pairs within time windows
    cartel_signals = []
    for year, ac in yearly_author_counter.items():
        for author, cnt in ac.most_common():
            if cnt >= 3:
                cartel_signals.append({
                    "type": "yearly_dense_citation",
                    "author": author,
                    "year": year,
                    "count": cnt,
                    "note": "Same author cited the scholar 3+ times in a single year."
                })

    # Cross-year pair detection (simple: any author with total >=5)
    for author, cnt in author_counter.most_common():
        if cnt >= 5:
            cartel_signals.append({
                "type": "persistent_citer",
                "author": author,
                "total_count": cnt,
                "note": "Same author cited the scholar 5+ times across all years."
            })

    return {
        "total_citations": total,
        "category_counts": {
            "self_citation": self_count,
            "team_citation": team_count,
            "mutual_citation": mutual_count,
            "third_party": third_party_count
        },
        "ratios": ratios,
        "tier_breakdown": tier_breakdown,
        "top_citing_authors": top_authors,
        "top_citing_institutions": top_institutions,
        "cartel_signals": cartel_signals
    }


def generate_red_flags(report: dict) -> list:
    flags = []
    ratios = report["citation_structure"]["ratios"]
    tiers = report["citation_structure"]["tier_breakdown"]
    cartels = report["citation_structure"]["cartel_signals"]
    h_anomalies = report["h_index_analysis"]["anomalies"]

    if h_anomalies:
        for a in h_anomalies:
            flags.append({
                "signal": "h-index jumping growth",
                "detail": f"Year {a['year']}: growth {a['absolute_growth']}, baseline avg {a['baseline_avg']}",
                "severity": a.get("severity", "high")
            })

    if ratios.get("self_citation", 0) > 0.20:
        flags.append({
            "signal": "High self-citation rate",
            "detail": f"Self-citation ratio: {ratios['self_citation']:.1%}",
            "severity": "high" if ratios["self_citation"] > 0.25 else "medium-high"
        })

    if ratios.get("team_citation", 0) > 0.30:
        flags.append({
            "signal": "High team citation rate",
            "detail": f"Team citation ratio: {ratios['team_citation']:.1%}",
            "severity": "high"
        })

    c_d_ratio = tiers.get("C", {}).get("ratio", 0) + tiers.get("D", {}).get("ratio", 0)
    if c_d_ratio >= 0.40:
        flags.append({
            "signal": "High proportion of low-quality citing sources",
            "detail": f"C+D tier ratio: {c_d_ratio:.1%}",
            "severity": "high" if c_d_ratio >= 0.50 else "medium-high"
        })

    d_ratio = tiers.get("D", {}).get("ratio", 0)
    if d_ratio >= 0.15:
        flags.append({
            "signal": "Predatory/low-quality journal citations",
            "detail": f"D tier ratio: {d_ratio:.1%}",
            "severity": "high"
        })

    mutual_pairs = [c for c in cartels if c["type"] == "persistent_citer"]
    for p in mutual_pairs:
        flags.append({
            "signal": "Persistent citer (potential cartel)",
            "detail": f"Author '{p['author']}' cited {p['total_count']} times",
            "severity": "high" if p["total_count"] >= 10 else "medium-high"
        })

    yearly_dense = [c for c in cartels if c["type"] == "yearly_dense_citation"]
    for d in yearly_dense:
        flags.append({
            "signal": "Dense yearly citation",
            "detail": f"Author '{d['author']}' cited {d['count']} times in {d['year']}",
            "severity": "high" if d["count"] >= 5 else "medium-high"
        })

    if not flags:
        flags.append({
            "signal": "None detected",
            "detail": "No red flags triggered based on current thresholds.",
            "severity": "low"
        })

    return flags


def main():
    parser = argparse.ArgumentParser(description="Academic citation profile analyzer")
    parser.add_argument("--input", "-i", required=True, help="Path to input citations JSON")
    parser.add_argument("--output", "-o", required=True, help="Path to output JSON report")
    args = parser.parse_args()

    print(f"[INFO] Loading citation data from: {args.input}")
    data = load_data(args.input)

    scholar_name = data.get("scholar_name", "Unknown")
    aliases = data.get("scholar_aliases", [])
    team = data.get("team_members", [])
    yearly = data.get("yearly_h_index", [])
    citations = data.get("citations", [])
    scholar_out = data.get("scholar_citations_out", [])

    if not citations:
        print("[ERROR] No citation records found in input.", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Scholar: {scholar_name}")
    print(f"[INFO] Total citation records: {len(citations)}")

    h_report = analyze_h_index(yearly)
    cite_report = classify_citations(citations, scholar_name, aliases, team, scholar_out)

    report = {
        "scholar_name": scholar_name,
        "analysis_timestamp": __import__("datetime").datetime.now().isoformat(),
        "record_count": len(citations),
        "h_index_analysis": h_report,
        "citation_structure": cite_report
    }

    report["red_flags"] = generate_red_flags(report)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"[INFO] Report saved to: {args.output}")
    print(f"[SUMMARY] Self-citation: {cite_report['ratios']['self_citation']:.1%}, "
          f"Team citation: {cite_report['ratios']['team_citation']:.1%}, "
          f"H-index anomalies: {len(h_report['anomalies'])}, "
          f"Red flags: {len(report['red_flags'])}")


if __name__ == "__main__":
    main()
