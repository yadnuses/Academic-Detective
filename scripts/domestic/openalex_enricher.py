#!/usr/bin/env python3
"""
openalex_enricher.py

Enrich domestic scholar_data.json with English publications from OpenAlex.
Many domestic scholars (e.g. CASE_017) may also have records in OpenAlex,
especially when they have English collaborative papers.

Usage:
    python openalex_enricher.py --name "Jingxuan Ji" --institution "Peking University" --input ./scholar_data.json --output ./enriched_scholar_data.json
    python openalex_enricher.py --name "Jingxuan Ji" --institution "北京大学" --input ./scholar_data.json
"""

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from core.utils import get_logger, load_json, save_json

logger = get_logger("openalex_enricher")

OPENALEX_BASE = "https://api.openalex.org"

_LAST_CALL_TIME = {}


def _rate_limit(domain: str, min_interval: float = 0.2):
    """Ensure minimum interval between calls to the same domain."""
    now = time.time()
    last = _LAST_CALL_TIME.get(domain, 0)
    wait = min_interval - (now - last)
    if wait > 0:
        time.sleep(wait)
    _LAST_CALL_TIME[domain] = time.time()


def _http_get_json(url: str, timeout: int = 30) -> dict:
    """Simple HTTP GET returning parsed JSON."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _build_search_query(author_name: str, institution: str = "") -> str:
    """Build OpenAlex search query from name and institution."""
    query = urllib.parse.quote(author_name)
    if institution:
        query += f"+{urllib.parse.quote(institution)}"
    return query


def search_openalex_author(author_name: str, institution: str = "") -> Optional[dict]:
    """
    Search for an author on OpenAlex by name + institution.

    Returns:
        Best matching author dict, or None if not found.
    """
    _rate_limit("openalex", 0.2)

    query = _build_search_query(author_name, institution)
    search_url = f"{OPENALEX_BASE}/authors?search={query}&per_page=5"
    logger.info("OpenAlex author search: %s", search_url)

    try:
        data = _http_get_json(search_url)
        results = data.get("results", [])
        if not results:
            return None
        return results[0]
    except Exception as e:
        logger.error("OpenAlex author search failed: %s", e)
        return None


def fetch_openalex_works(author_id: str, max_works: int = 100) -> list[dict]:
    """
    Fetch works for a given OpenAlex author ID.

    Returns:
        List of normalized work dicts.
    """
    _rate_limit("openalex", 0.2)

    works_url = (
        f"{OPENALEX_BASE}/works?filter=author.id:{author_id}"
        f"&per_page={min(max_works, 200)}"
        f"&sort=cited_by_count:desc"
    )
    logger.info("OpenAlex works fetch: %s", works_url)

    try:
        data = _http_get_json(works_url)
        works = []
        for w in data.get("results", []):
            works.append({
                "id": w.get("id", ""),
                "title": w.get("display_name", ""),
                "doi": w.get("doi", ""),
                "publication_year": w.get("publication_year"),
                "publication_date": w.get("publication_date"),
                "authorships": [
                    {
                        "author_name": a.get("author", {}).get("display_name", ""),
                        "author_id": a.get("author", {}).get("id", ""),
                        "institutions": [
                            i.get("display_name", "")
                            for i in a.get("institutions", [])
                        ],
                        "is_corresponding": a.get("is_corresponding", False),
                    }
                    for a in w.get("authorships", [])
                ],
                "cited_by_count": w.get("cited_by_count", 0),
                "concepts": [
                    {"name": c.get("display_name", ""), "score": c.get("score", 0)}
                    for c in w.get("concepts", [])
                ],
                "open_access": {
                    "is_oa": w.get("open_access", {}).get("is_oa", False),
                    "oa_url": w.get("open_access", {}).get("oa_url", ""),
                },
                "host_venue": {
                    "name": w.get("host_venue", {}).get("display_name", ""),
                    "publisher": w.get("host_venue", {}).get("publisher", ""),
                    "type": w.get("host_venue", {}).get("type", ""),
                },
            })
        return works
    except Exception as e:
        logger.error("OpenAlex works fetch failed: %s", e)
        return []


def _normalize_title(title: str) -> str:
    """Normalize title for deduplication comparison."""
    if not title:
        return ""
    return re.sub(r"[^\w]", "", title).lower()


def _paper_key(paper: dict) -> str:
    """Generate deduplication key for a paper."""
    doi = paper.get("doi", "").lower().strip()
    if doi:
        return f"doi:{doi}"
    title = _normalize_title(paper.get("title", ""))
    return f"title:{title}"


def merge_papers(existing_papers: list, openalex_papers: list) -> tuple[list[dict], int]:
    """
    Merge existing papers with OpenAlex papers, deduplicating by DOI or title.

    Returns:
        (merged_list, newly_added_count)
    """
    seen = {}
    merged = []

    for p in existing_papers:
        if not isinstance(p, dict):
            continue
        key = _paper_key(p)
        if key and key not in seen:
            seen[key] = True
            merged.append(p)

    added = 0
    for p in openalex_papers:
        key = _paper_key(p)
        if not key:
            continue
        if key in seen:
            logger.debug("Skipping duplicate: %s", p.get("title", ""))
            continue
        seen[key] = True
        merged.append(p)
        added += 1

    return merged, added


def _ensure_paper_list(scholar_data: dict) -> list[dict]:
    """Extract existing paper list from scholar_data, handling placeholder strings."""
    ao = scholar_data.get("academic_outputs", {})
    paper_list = ao.get("paper_list", [])

    if isinstance(paper_list, str):
        # Handle placeholder like "[TO BE FILLED]"
        stripped = paper_list.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            return []
        return []

    if isinstance(paper_list, list):
        return [p for p in paper_list if isinstance(p, dict)]

    return []


def _update_paper_list(scholar_data: dict, merged_papers: list) -> dict:
    """Update scholar_data with the merged paper list."""
    if "academic_outputs" not in scholar_data:
        scholar_data["academic_outputs"] = {}

    scholar_data["academic_outputs"]["paper_list"] = merged_papers

    # Update verified_papers count if it was a placeholder or numeric
    verified = scholar_data["academic_outputs"].get("verified_papers")
    if isinstance(verified, str) and verified.strip().startswith("["):
        scholar_data["academic_outputs"]["verified_papers"] = len(merged_papers)
    elif isinstance(verified, int):
        scholar_data["academic_outputs"]["verified_papers"] = len(merged_papers)

    return scholar_data


def enrich_scholar_data(
    scholar_data: dict,
    author_name: str,
    institution: str = "",
    max_works: int = 100,
) -> dict:
    """
    Enrich scholar_data with OpenAlex English publications.

    Args:
        scholar_data: Existing domestic scholar data dict.
        author_name: Author name to search on OpenAlex (pinyin recommended).
        institution: Institution name (Chinese or English).
        max_works: Max number of works to fetch from OpenAlex.

    Returns:
        Enriched scholar_data dict.
    """
    scholar_name = scholar_data.get("name", author_name)
    logger.info("Starting OpenAlex enrichment for: %s", scholar_name)

    # Search author
    author = search_openalex_author(author_name, institution)
    if author is None:
        logger.warning(
            "OpenAlex: no author found for '%s' (institution: '%s'). "
            "Skipping enrichment. Consider using pinyin name or English institution name.",
            author_name,
            institution,
        )
        scholar_data["_openalex_enrichment"] = {
            "status": "author_not_found",
            "searched_name": author_name,
            "searched_institution": institution,
            "note": "No matching author found on OpenAlex. "
                    "Try using pinyin name (e.g. 'Jingxuan Ji') and English institution name.",
        }
        return scholar_data

    author_id = author.get("id", "").split("/")[-1]
    display_name = author.get("display_name", "")
    works_count = author.get("works_count", 0)
    cited_by_count = author.get("cited_by_count", 0)

    logger.info(
        "OpenAlex author matched: %s (ID: %s, works: %d, citations: %d)",
        display_name, author_id, works_count, cited_by_count,
    )

    # Fetch works
    openalex_works = fetch_openalex_works(author_id, max_works=max_works)
    logger.info("Fetched %d works from OpenAlex", len(openalex_works))

    if not openalex_works:
        scholar_data["_openalex_enrichment"] = {
            "status": "no_works",
            "author_matched": {
                "id": author.get("id", ""),
                "display_name": display_name,
                "orcid": author.get("orcid", ""),
                "works_count": works_count,
                "cited_by_count": cited_by_count,
            },
        }
        return scholar_data

    # Merge with existing papers
    existing_papers = _ensure_paper_list(scholar_data)
    merged_papers, added = merge_papers(existing_papers, openalex_works)

    logger.info(
        "Merged papers: %d existing + %d OpenAlex = %d total (%d new)",
        len(existing_papers), len(openalex_works), len(merged_papers), added,
    )

    # Update scholar_data
    scholar_data = _update_paper_list(scholar_data, merged_papers)

    # Record enrichment metadata
    scholar_data["_openalex_enrichment"] = {
        "status": "success",
        "author_matched": {
            "id": author.get("id", ""),
            "display_name": display_name,
            "orcid": author.get("orcid", ""),
            "works_count": works_count,
            "cited_by_count": cited_by_count,
            "h_index": author.get("summary_stats", {}).get("h_index", 0),
            "i10_index": author.get("summary_stats", {}).get("i10_index", 0),
        },
        "works_fetched": len(openalex_works),
        "works_added": added,
        "total_papers_after_merge": len(merged_papers),
    }

    # Also enrich basic_profile if overseas_experience is empty
    bp = scholar_data.get("basic_profile", {})
    affiliations = [
        inst.get("display_name", "")
        for inst in author.get("last_known_institutions", [])
    ]
    if affiliations and not bp.get("overseas_experience"):
        bp["overseas_experience"] = (
            f"OpenAlex records affiliations: {', '.join(affiliations)}"
        )
        scholar_data["basic_profile"] = bp

    return scholar_data


def main():
    parser = argparse.ArgumentParser(
        description="Enrich domestic scholar_data.json with English publications from OpenAlex"
    )
    parser.add_argument(
        "--name", "-n", required=True,
        help="Author name for OpenAlex search (pinyin recommended, e.g. 'Jingxuan Ji')"
    )
    parser.add_argument(
        "--institution", "-i", default="",
        help="Institution name (Chinese or English, e.g. 'Peking University' or '北京大学')"
    )
    parser.add_argument(
        "--input", "-I", required=True,
        help="Path to existing scholar_data.json"
    )
    parser.add_argument(
        "--output", "-o", default="",
        help="Output path (default: <input_dir>/enriched_scholar_data.json)"
    )
    parser.add_argument(
        "--max-works", type=int, default=100,
        help="Maximum number of works to fetch from OpenAlex (default: 100)"
    )
    args = parser.parse_args()

    # Load existing data
    scholar_data = load_json(args.input)
    if not scholar_data:
        logger.error("Failed to load scholar_data from: %s", args.input)
        raise SystemExit(1)

    # Enrich
    enriched = enrich_scholar_data(
        scholar_data,
        author_name=args.name,
        institution=args.institution,
        max_works=args.max_works,
    )

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        input_path = Path(args.input)
        output_path = input_path.parent / "enriched_scholar_data.json"

    # Save
    if save_json(enriched, output_path):
        logger.info("Enriched scholar data saved to: %s", output_path)
    else:
        logger.error("Failed to save enriched data to: %s", output_path)
        raise SystemExit(1)

    # Print summary
    enrichment = enriched.get("_openalex_enrichment", {})
    status = enrichment.get("status", "unknown")
    print(f"\n[OpenAlex Enrichment Summary]")
    print(f"  Status: {status}")
    if status == "success":
        matched = enrichment.get("author_matched", {})
        print(f"  Author matched: {matched.get('display_name', 'N/A')}")
        print(f"  Works fetched: {enrichment.get('works_fetched', 0)}")
        print(f"  Works added (after dedup): {enrichment.get('works_added', 0)}")
        print(f"  Total papers now: {enrichment.get('total_papers_after_merge', 0)}")
    elif status == "author_not_found":
        print(f"  Searched name: {enrichment.get('searched_name', 'N/A')}")
        print(f"  Searched institution: {enrichment.get('searched_institution', 'N/A')}")
        print(f"  Note: {enrichment.get('note', '')}")
    print(f"  Output: {output_path}")


if __name__ == "__main__":
    main()
