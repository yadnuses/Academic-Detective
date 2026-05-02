#!/usr/bin/env python3
"""
citation_constellation.py

基于 OpenAlex 免费 API 的引用网络分析工具。
获取学者论文列表及其引用数据，构建引用网络，计算外部独立引用比例，
识别内部圈依赖（自引、团队引用、机构引用）。

核心概念（简化版 BARON / HEROCON）：
- 自引：学者自己引用自己的论文
- 团队引用：合作者引用该学者的论文
- 机构引用：同一机构的同事引用该学者的论文
- 外部独立引用：无合作关系、不同机构的学者引用

Usage:
    python citation_constellation.py --name "张三" --institution "北京大学" --output ./reports
    python citation_constellation.py --name "John Smith" --orcid "0000-0001-2345-6789" --output ./reports
"""

import argparse
import json
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.utils import get_logger, save_json

logger = get_logger("citation_constellation")

OPENALEX_BASE = "https://api.openalex.org"

# ---------------------------------------------------------------------------
# Rate limiting & HTTP helpers
# ---------------------------------------------------------------------------

_LAST_CALL_TIME = {}


def _rate_limit(domain: str, min_interval: float = 0.2):
    """Ensure minimum interval between calls to the same domain."""
    now = time.time()
    last = _LAST_CALL_TIME.get(domain, 0)
    wait = min_interval - (now - last)
    if wait > 0:
        time.sleep(wait)
    _LAST_CALL_TIME[domain] = time.time()


def _http_get_json(url: str, headers: dict = None, timeout: int = 30) -> dict:
    """Simple HTTP GET returning parsed JSON."""
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_paginated(url_base: str, params: dict, max_results: int, per_page: int = 200) -> list:
    """Fetch all pages from an OpenAlex paginated endpoint."""
    items = []
    cursor = "*"
    while len(items) < max_results:
        page_params = dict(params)
        page_params["per_page"] = min(per_page, max_results - len(items))
        page_params["cursor"] = cursor
        query = urllib.parse.urlencode(page_params, safe=":")
        url = f"{url_base}?{query}"
        _rate_limit("openalex", 0.2)
        try:
            data = _http_get_json(url)
        except Exception as e:
            logger.error("HTTP error for %s: %s", url, e)
            break
        results = data.get("results", [])
        if not results:
            break
        items.extend(results)
        meta = data.get("meta", {})
        next_cursor = meta.get("next_cursor", "")
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
    return items[:max_results]


# ---------------------------------------------------------------------------
# OpenAlex fetchers
# ---------------------------------------------------------------------------

def search_author(author_name: str, institution: str = "", orcid: str = "") -> Optional[dict]:
    """
    Search OpenAlex for an author.

    Returns:
        Author dict or None if not found.
    """
    query = urllib.parse.quote(author_name)
    if institution:
        query += f"+{urllib.parse.quote(institution)}"

    url = f"{OPENALEX_BASE}/authors?search={query}&per_page=5"
    logger.info("OpenAlex author search: %s", url)
    _rate_limit("openalex", 0.2)

    try:
        data = _http_get_json(url)
        results = data.get("results", [])
        if not results:
            logger.warning("No author found for '%s'", author_name)
            return None

        author = results[0]

        # If ORCID provided, verify or find exact match
        if orcid:
            orcid_clean = orcid.replace("https://orcid.org/", "").replace("http://orcid.org/", "").strip()
            for r in results:
                author_orcid = (r.get("orcid") or "").replace("https://orcid.org/", "").replace("http://orcid.org/", "").strip()
                if orcid_clean == author_orcid:
                    author = r
                    break

        return author
    except Exception as e:
        logger.error("Author search failed: %s", e)
        return None


def fetch_author_works(author_id: str, max_works: int = 100) -> list:
    """
    Fetch works by author ID.

    Returns:
        List of work dicts.
    """
    # author_id may be full URL or just the ID part
    clean_id = author_id.split("/")[-1] if "/" in author_id else author_id
    url_base = f"{OPENALEX_BASE}/works"
    params = {
        "filter": f"author.id:{clean_id}",
        "sort": "cited_by_count:desc",
    }
    logger.info("Fetching works for author %s (max %d)", clean_id, max_works)
    works = _fetch_paginated(url_base, params, max_works)
    logger.info("Retrieved %d works", len(works))
    return works


def fetch_citing_papers(work_id: str, max_citations: int = 200) -> list:
    """
    Fetch papers that cite a given work.

    OpenAlex filter: cites:Wxxxxxxxx

    Returns:
        List of citing work dicts.
    """
    clean_id = work_id.split("/")[-1] if "/" in work_id else work_id
    url_base = f"{OPENALEX_BASE}/works"
    params = {
        "filter": f"cites:{clean_id}",
        "sort": "cited_by_count:desc",
    }
    logger.info("Fetching citations for work %s (max %d)", clean_id, max_citations)
    citations = _fetch_paginated(url_base, params, max_citations)
    logger.info("Retrieved %d citations for work %s", len(citations), clean_id)
    return citations


# ---------------------------------------------------------------------------
# Citation classification
# ---------------------------------------------------------------------------

def _extract_author_ids(work: dict) -> set:
    """Extract OpenAlex author IDs from a work's authorships."""
    ids = set()
    for auth in work.get("authorships", []):
        author = auth.get("author", {})
        aid = author.get("id", "")
        if aid:
            ids.add(aid.split("/")[-1] if "/" in aid else aid)
    return ids


def _extract_author_names(work: dict) -> set:
    """Extract author display names from a work's authorships."""
    names = set()
    for auth in work.get("authorships", []):
        author = auth.get("author", {})
        name = author.get("display_name", "").strip()
        if name:
            names.add(name.lower())
    return names


def _extract_institutions(work: dict) -> set:
    """Extract institution names from a work's authorships."""
    insts = set()
    for auth in work.get("authorships", []):
        for inst in auth.get("institutions", []):
            name = inst.get("display_name", "").strip()
            if name:
                insts.add(name.lower())
    return insts


def _is_self_citation(target_author_id: str, target_author_name: str, citing_work: dict) -> bool:
    """Check if citing work includes the target author."""
    author_ids = _extract_author_ids(citing_work)
    if target_author_id and target_author_id.split("/")[-1] in author_ids:
        return True
    author_names = _extract_author_names(citing_work)
    if target_author_name and target_author_name.lower() in author_names:
        return True
    return False


def _is_team_citation(collaborator_ids: set, collaborator_names: set, citing_work: dict) -> bool:
    """Check if citing work includes any known collaborator."""
    author_ids = _extract_author_ids(citing_work)
    if author_ids & collaborator_ids:
        return True
    author_names = _extract_author_names(citing_work)
    if author_names & collaborator_names:
        return True
    return False


def _is_institution_citation(target_institutions: set, citing_work: dict) -> bool:
    """Check if citing work includes any author from target institutions."""
    work_insts = _extract_institutions(citing_work)
    if work_insts & target_institutions:
        return True
    return False


# ---------------------------------------------------------------------------
# Constellation builder
# ---------------------------------------------------------------------------

def build_constellation(
    author_name: str,
    institution: str = "",
    orcid: str = "",
    max_works: int = 50,
    max_citations_per_work: int = 100,
) -> dict:
    """
    Build a citation constellation for a given scholar.

    Args:
        author_name: Scholar name.
        institution: Institution name (optional, for disambiguation and classification).
        orcid: ORCID ID (optional).
        max_works: Max number of works to analyze.
        max_citations_per_work: Max citations to fetch per work.

    Returns:
        Structured dict with network statistics and citation proportions.
    """
    start_time = datetime.now().isoformat(timespec="seconds")

    # 1. Search author
    author = search_author(author_name, institution, orcid)
    if not author:
        return {
            "query": {"author_name": author_name, "institution": institution, "orcid": orcid},
            "error": "Author not found in OpenAlex",
            "generated_at": start_time,
        }

    author_id = author.get("id", "")
    author_id_short = author_id.split("/")[-1] if "/" in author_id else author_id
    author_display_name = author.get("display_name", author_name)
    author_orcid = author.get("orcid", "")

    # Author's known institutions from profile
    author_institutions = set()
    for inst in author.get("last_known_institutions", []):
        name = inst.get("display_name", "").strip()
        if name:
            author_institutions.add(name.lower())
    if institution:
        author_institutions.add(institution.lower())

    # 2. Fetch works
    works = fetch_author_works(author_id, max_works)

    # Build collaborator sets from all works
    collaborator_ids = set()
    collaborator_names = set()
    for w in works:
        for auth in w.get("authorships", []):
            a = auth.get("author", {})
            aid = a.get("id", "")
            aname = a.get("display_name", "").strip()
            aid_short = aid.split("/")[-1] if "/" in aid else aid
            if aid_short and aid_short != author_id_short:
                collaborator_ids.add(aid_short)
            if aname and aname.lower() != author_display_name.lower():
                collaborator_names.add(aname.lower())

    # 3. Fetch citations for each work and classify
    work_nodes = []
    all_citing_papers = []

    total_citations_fetched = 0
    self_citation_count = 0
    team_citation_count = 0
    institution_citation_count = 0
    external_independent_count = 0

    # Track per-work stats
    for w in works:
        work_id = w.get("id", "")
        work_id_short = work_id.split("/")[-1] if "/" in work_id else work_id
        title = w.get("display_name", "")
        cited_by_count = w.get("cited_by_count", 0)
        pub_year = w.get("publication_year")

        citing_papers = fetch_citing_papers(work_id, max_citations_per_work)
        total_citations_fetched += len(citing_papers)

        work_self = 0
        work_team = 0
        work_inst = 0
        work_ext = 0

        citing_ids = []
        for cp in citing_papers:
            cp_id = cp.get("id", "")
            cp_id_short = cp_id.split("/")[-1] if "/" in cp_id else cp_id
            citing_ids.append(cp_id_short)

            if _is_self_citation(author_id, author_display_name, cp):
                work_self += 1
                self_citation_count += 1
            elif _is_team_citation(collaborator_ids, collaborator_names, cp):
                work_team += 1
                team_citation_count += 1
            elif _is_institution_citation(author_institutions, cp):
                work_inst += 1
                institution_citation_count += 1
            else:
                work_ext += 1
                external_independent_count += 1

            all_citing_papers.append({
                "id": cp_id,
                "title": cp.get("display_name", ""),
                "year": cp.get("publication_year"),
                "cited_work_id": work_id,
                "authorships": [
                    {
                        "author_name": a.get("author", {}).get("display_name", ""),
                        "author_id": a.get("author", {}).get("id", ""),
                        "institutions": [i.get("display_name", "") for i in a.get("institutions", [])],
                    }
                    for a in cp.get("authorships", [])
                ],
            })

        work_nodes.append({
            "id": work_id,
            "title": title,
            "publication_year": pub_year,
            "cited_by_count": cited_by_count,
            "citations_fetched": len(citing_papers),
            "classification": {
                "self": work_self,
                "team": work_team,
                "institution": work_inst,
                "external_independent": work_ext,
            },
            "citing_work_ids": citing_ids,
        })

    # 4. Compute proportions
    total_classified = self_citation_count + team_citation_count + institution_citation_count + external_independent_count

    proportions = {}
    if total_classified > 0:
        proportions = {
            "self_citation_ratio": round(self_citation_count / total_classified, 4),
            "team_citation_ratio": round(team_citation_count / total_classified, 4),
            "institution_citation_ratio": round(institution_citation_count / total_classified, 4),
            "external_independent_ratio": round(external_independent_count / total_classified, 4),
        }
    else:
        proportions = {
            "self_citation_ratio": 0.0,
            "team_citation_ratio": 0.0,
            "institution_citation_ratio": 0.0,
            "external_independent_ratio": 0.0,
        }

    # 5. Detect internal-circle dependency patterns
    internal_circle_flags = []
    if total_classified > 0:
        internal_total = self_citation_count + team_citation_count + institution_citation_count
        internal_ratio = internal_total / total_classified
        if internal_ratio > 0.5:
            internal_circle_flags.append("内部引用占比超过50%，存在明显的内部圈依赖迹象")
        if self_citation_count / max(total_classified, 1) > 0.2:
            internal_circle_flags.append("自引率超过20%")
        if team_citation_count / max(total_classified, 1) > 0.3:
            internal_circle_flags.append("团队引用率超过30%")
        if institution_citation_count / max(total_classified, 1) > 0.3:
            internal_circle_flags.append("机构引用率超过30%")

    # 6. Build network stats
    network_stats = {
        "works_analyzed": len(works),
        "total_citations_fetched": total_citations_fetched,
        "total_classified": total_classified,
        "unique_citing_papers": len({cp["id"] for cp in all_citing_papers}),
        "self_citations": self_citation_count,
        "team_citations": team_citation_count,
        "institution_citations": institution_citation_count,
        "external_independent_citations": external_independent_count,
        "proportions": proportions,
        "internal_circle_flags": internal_circle_flags,
        "internal_circle_dependency_score": round(1 - proportions.get("external_independent_ratio", 0), 4),
    }

    result = {
        "query": {
            "author_name": author_name,
            "institution": institution,
            "orcid": orcid,
        },
        "author": {
            "id": author_id,
            "display_name": author_display_name,
            "orcid": author_orcid,
            "works_count": author.get("works_count", 0),
            "cited_by_count": author.get("cited_by_count", 0),
            "h_index": author.get("summary_stats", {}).get("h_index", 0),
            "institutions": list(author_institutions),
            "collaborator_count": len(collaborator_ids),
        },
        "network_stats": network_stats,
        "works": work_nodes,
        "citing_papers": all_citing_papers,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "api_source": "OpenAlex",
    }

    return result


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------

def generate_report(data: dict) -> str:
    """Generate a human-readable Markdown report from constellation data."""
    lines = []
    lines.append("# 引用网络分析报告（Citation Constellation）")
    lines.append("")

    query = data.get("query", {})
    lines.append(f"**查询学者**：{query.get('author_name', 'N/A')}")
    if query.get("institution"):
        lines.append(f"**所在机构**：{query['institution']}")
    if query.get("orcid"):
        lines.append(f"**ORCID**：{query['orcid']}")
    lines.append("")

    author = data.get("author", {})
    if not author:
        lines.append("未在 OpenAlex 中找到该学者。")
        return "\n".join(lines)

    lines.append(f"## 学者基本信息")
    lines.append(f"- **OpenAlex ID**：{author.get('id', 'N/A')}")
    lines.append(f"- **显示名称**：{author.get('display_name', 'N/A')}")
    lines.append(f"- **论文总数**：{author.get('works_count', 0)}")
    lines.append(f"- **被引总数**：{author.get('cited_by_count', 0)}")
    lines.append(f"- **h-index**：{author.get('h_index', 0)}")
    lines.append(f"- **已知合作者数**：{author.get('collaborator_count', 0)}")
    lines.append("")

    stats = data.get("network_stats", {})
    lines.append(f"## 引用网络统计")
    lines.append(f"- **分析论文数**：{stats.get('works_analyzed', 0)}")
    lines.append(f"- **获取引用数**：{stats.get('total_citations_fetched', 0)}")
    lines.append(f"- **去重后引用论文数**：{stats.get('unique_citing_papers', 0)}")
    lines.append("")

    lines.append(f"## 引用分类与比例")
    prop = stats.get("proportions", {})
    lines.append(f"| 类型 | 数量 | 比例 |")
    lines.append(f"|:---|---:|---:|")
    lines.append(f"| 自引 | {stats.get('self_citations', 0)} | {prop.get('self_citation_ratio', 0):.2%} |")
    lines.append(f"| 团队引用 | {stats.get('team_citations', 0)} | {prop.get('team_citation_ratio', 0):.2%} |")
    lines.append(f"| 机构引用 | {stats.get('institution_citations', 0)} | {prop.get('institution_citation_ratio', 0):.2%} |")
    lines.append(f"| 外部独立引用 | {stats.get('external_independent_citations', 0)} | {prop.get('external_independent_ratio', 0):.2%} |")
    lines.append("")

    lines.append(f"## 内部圈依赖评估")
    dep_score = stats.get("internal_circle_dependency_score", 0)
    lines.append(f"- **内部圈依赖指数**：{dep_score:.2%}（越接近100%说明内部依赖越强）")
    flags = stats.get("internal_circle_flags", [])
    if flags:
        lines.append("- **警示信号**：")
        for flag in flags:
            lines.append(f"  - ⚠ {flag}")
    else:
        lines.append("- **警示信号**：未发现明显的内部圈依赖迹象。")
    lines.append("")

    lines.append(f"## 论文级引用明细")
    for w in data.get("works", []):
        cls = w.get("classification", {})
        lines.append(f"### {w.get('title', 'Untitled')}")
        lines.append(f"- 发表年份：{w.get('publication_year', 'N/A')}")
        lines.append(f"- 总被引：{w.get('cited_by_count', 0)}（获取 {w.get('citations_fetched', 0)} 条）")
        lines.append(f"- 自引：{cls.get('self', 0)} | 团队引用：{cls.get('team', 0)} | 机构引用：{cls.get('institution', 0)} | 外部独立：{cls.get('external_independent', 0)}")
        lines.append("")

    lines.append(f"---")
    lines.append(f"*报告生成时间：{data.get('generated_at', '')} | 数据来源：{data.get('api_source', 'OpenAlex')}*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Citation constellation analyzer (OpenAlex)")
    parser.add_argument("--name", "-n", required=True, help="Scholar name")
    parser.add_argument("--institution", "-i", default="", help="Institution name")
    parser.add_argument("--orcid", "-o", default="", help="ORCID ID")
    parser.add_argument("--max-works", type=int, default=50, help="Max works to analyze (default: 50)")
    parser.add_argument("--max-citations", type=int, default=100, help="Max citations per work (default: 100)")
    parser.add_argument("--output", "-O", default="./reports", help="Output directory")
    parser.add_argument("--json-only", action="store_true", help="Only output JSON, skip Markdown report")
    args = parser.parse_args()

    logger.info("Starting citation constellation analysis for: %s", args.name)

    result = build_constellation(
        author_name=args.name,
        institution=args.institution,
        orcid=args.orcid,
        max_works=args.max_works,
        max_citations_per_work=args.max_citations,
    )

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save JSON
    safe_name = args.name.replace(" ", "_").replace("/", "_")
    json_path = out_dir / f"citation_constellation_{safe_name}.json"
    save_json(result, json_path)
    logger.info("JSON saved to: %s", json_path)

    # Save Markdown report
    if not args.json_only:
        md_path = out_dir / f"citation_constellation_{safe_name}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(generate_report(result))
        logger.info("Report saved to: %s", md_path)

    # Print summary to console
    stats = result.get("network_stats", {})
    prop = stats.get("proportions", {})
    print(f"\n{'='*60}")
    print(f"引用网络分析完成：{args.name}")
    print(f"{'='*60}")
    print(f"分析论文数：{stats.get('works_analyzed', 0)}")
    print(f"获取引用数：{stats.get('total_citations_fetched', 0)}（去重后 {stats.get('unique_citing_papers', 0)}）")
    print(f"自引：{stats.get('self_citations', 0)} ({prop.get('self_citation_ratio', 0):.2%})")
    print(f"团队引用：{stats.get('team_citations', 0)} ({prop.get('team_citation_ratio', 0):.2%})")
    print(f"机构引用：{stats.get('institution_citations', 0)} ({prop.get('institution_citation_ratio', 0):.2%})")
    print(f"外部独立引用：{stats.get('external_independent_citations', 0)} ({prop.get('external_independent_ratio', 0):.2%})")
    print(f"内部圈依赖指数：{stats.get('internal_circle_dependency_score', 0):.2%}")
    flags = stats.get("internal_circle_flags", [])
    if flags:
        print("警示信号：")
        for flag in flags:
            print(f"  ⚠ {flag}")
    else:
        print("未发现明显的内部圈依赖迹象。")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
