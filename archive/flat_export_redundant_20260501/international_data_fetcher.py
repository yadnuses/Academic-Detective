#!/usr/bin/env python3
"""
international/data_fetcher.py

Free-API data collection for international academic investigations.
Supports: OpenAlex, ORCID, Semantic Scholar, Google Scholar (via scholarly),
PubPeer, Retraction Watch, arXiv.

Usage:
    from international.data_fetcher import UnifiedFetcher

    fetcher = UnifiedFetcher()
    result = fetcher.fetch_all("Prof. Smith", institution="MIT")
    # result is a dict compatible with domestic data_importer output format
"""

import json
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional

from core_utils import get_logger, save_json

logger = get_logger("international_fetcher")

# ---------------------------------------------------------------------------
# Rate limiting helpers
# ---------------------------------------------------------------------------

_LAST_CALL_TIME = {}


def _rate_limit(domain: str, min_interval: float = 1.0):
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


# ---------------------------------------------------------------------------
# OpenAlex
# ---------------------------------------------------------------------------

OPENALEX_BASE = "https://api.openalex.org"


def fetch_openalex(author_name: str, institution: str = "", orcid: str = "", max_works: int = 100) -> dict:
    """
    Fetch author profile and works from OpenAlex.

    Returns:
        {
            "author": {id, orcid, display_name, works_count, cited_by_count, ...},
            "works": [{id, title, publication_year, authorships, ...}],
            "concepts": [{display_name, score}],
        }
    """
    _rate_limit("openalex", 0.2)  # OpenAlex is generous

    # Search author
    query = urllib.parse.quote(author_name)
    if institution:
        query += f"+{urllib.parse.quote(institution)}"

    search_url = f"{OPENALEX_BASE}/authors?search={query}&per_page=5"
    logger.info("OpenAlex author search: %s", search_url)

    try:
        search_data = _http_get_json(search_url)
        results = search_data.get("results", [])
        if not results:
            logger.warning("OpenAlex: no author found for '%s'", author_name)
            return {"author": None, "works": [], "concepts": []}

        # Pick best match
        author = results[0]
        author_id = author.get("id", "").split("/")[-1]

        # If ORCID provided, verify match
        if orcid:
            author_orcid = author.get("orcid", "")
            if orcid not in author_orcid:
                # Try to find exact ORCID match
                for r in results:
                    if orcid in (r.get("orcid") or ""):
                        author = r
                        author_id = author.get("id", "").split("/")[-1]
                        break

        # Fetch works
        works = []
        works_url = f"{OPENALEX_BASE}/works?filter=author.id:{author_id}&per_page={min(max_works, 200)}&sort=cited_by_count:desc"
        works_data = _http_get_json(works_url)
        for w in works_data.get("results", []):
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
                            i.get("display_name", "") for i in a.get("institutions", [])
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

        # Author concepts
        concepts = [
            {"name": c.get("display_name", ""), "score": c.get("score", 0)}
            for c in author.get("x_concepts", [])
        ]

        return {
            "author": {
                "id": author.get("id", ""),
                "orcid": author.get("orcid", ""),
                "display_name": author.get("display_name", ""),
                "works_count": author.get("works_count", 0),
                "cited_by_count": author.get("cited_by_count", 0),
                "h_index": author.get("summary_stats", {}).get("h_index", 0),
                "i10_index": author.get("summary_stats", {}).get("i10_index", 0),
                "affiliations": [
                    {"name": inst.get("display_name", ""), "years": inst.get("years", [])}
                    for inst in author.get("last_known_institutions", [])
                ],
            },
            "works": works,
            "concepts": concepts,
        }

    except Exception as e:
        logger.error("OpenAlex fetch failed: %s", e)
        return {"author": None, "works": [], "concepts": []}


# ---------------------------------------------------------------------------
# ORCID
# ---------------------------------------------------------------------------

ORCID_BASE = "https://pub.orcid.org/v3.0"


def fetch_orcid(orcid_id: str) -> dict:
    """
    Fetch public ORCID record.

    Returns:
        {
            "orcid_id": str,
            "name": str,
            "biography": str,
            "education": [...],
            "employment": [...],
            "works": [...],
        }
    """
    _rate_limit("orcid", 0.5)

    # Clean ORCID ID
    orcid_id = orcid_id.replace("https://orcid.org/", "").replace("http://orcid.org/", "").strip()

    url = f"{ORCID_BASE}/{orcid_id}"
    logger.info("ORCID fetch: %s", url)

    try:
        data = _http_get_json(url, headers={"Accept": "application/json"})

        person = data.get("person", {})
        name = person.get("name", {})
        given = name.get("given-names", {}).get("value", "")
        family = name.get("family-name", {}).get("value", "")
        full_name = f"{given} {family}".strip()

        # Education
        education = []
        for item in data.get("activities-summary", {}).get("educations", {}).get("affiliation-group", []):
            for s in item.get("summaries", []):
                e = s.get("education-summary", {})
                education.append({
                    "institution": e.get("organization", {}).get("name", ""),
                    "department": e.get("department-name", ""),
                    "role": e.get("role-title", ""),
                    "start_date": _orcid_date(e.get("start-date")),
                    "end_date": _orcid_date(e.get("end-date")),
                })

        # Employment
        employment = []
        for item in data.get("activities-summary", {}).get("employments", {}).get("affiliation-group", []):
            for s in item.get("summaries", []):
                e = s.get("employment-summary", {})
                employment.append({
                    "institution": e.get("organization", {}).get("name", ""),
                    "department": e.get("department-name", ""),
                    "role": e.get("role-title", ""),
                    "start_date": _orcid_date(e.get("start-date")),
                    "end_date": _orcid_date(e.get("end-date")),
                })

        # Works
        works = []
        for group in data.get("activities-summary", {}).get("works", {}).get("group", []):
            for w in group.get("work-summary", []):
                works.append({
                    "title": w.get("title", {}).get("title", {}).get("value", ""),
                    "type": w.get("type", ""),
                    "publication_date": _orcid_date(w.get("publication-date")),
                    "journal": w.get("journal-title", {}).get("value", ""),
                    "url": w.get("url", {}).get("value", ""),
                    "external_ids": [
                        {"type": eid.get("external-id-type", ""), "value": eid.get("external-id-value", "")}
                        for eid in w.get("external-ids", {}).get("external-id", [])
                    ],
                })

        return {
            "orcid_id": orcid_id,
            "name": full_name,
            "biography": (person.get("biography") or {}).get("content", ""),
            "education": education,
            "employment": employment,
            "works": works,
        }

    except Exception as e:
        logger.error("ORCID fetch failed: %s", e)
        return {"orcid_id": orcid_id, "name": "", "biography": "", "education": [], "employment": [], "works": []}


def _orcid_date(d: dict) -> str:
    if not d:
        return ""
    year = d.get("year", {}).get("value", "")
    month = d.get("month", {}).get("value", "")
    day = d.get("day", {}).get("value", "")
    parts = [p for p in [year, month, day] if p]
    return "-".join(parts)


# ---------------------------------------------------------------------------
# Semantic Scholar
# ---------------------------------------------------------------------------

S2_BASE = "https://api.semanticscholar.org/graph/v1"


def fetch_semantic_scholar(author_name: str, max_papers: int = 100) -> dict:
    """
    Fetch author profile and papers from Semantic Scholar.

    Returns:
        {
            "author": {name, affiliations, paperCount, citationCount, hIndex},
            "papers": [{paperId, title, year, citationCount, tldr, ...}],
        }
    """
    _rate_limit("semantic_scholar", 0.2)  # 5000 per 5 min

    search_url = f"{S2_BASE}/author/search?query={urllib.parse.quote(author_name)}&fields=name,affiliations,paperCount,citationCount,hIndex&limit=5"
    logger.info("Semantic Scholar search: %s", search_url)

    try:
        search_data = _http_get_json(search_url)
        authors = search_data.get("data", [])
        if not authors:
            logger.warning("Semantic Scholar: no author found for '%s'", author_name)
            return {"author": None, "papers": []}

        author = authors[0]
        author_id = author.get("authorId")

        # Fetch papers
        papers = []
        papers_url = f"{S2_BASE}/author/{author_id}/papers?fields=paperId,title,year,abstract,citationCount,influentialCitationCount,tldr,openAccessPdf,publicationDate,journal,authors&limit={min(max_papers, 500)}"
        papers_data = _http_get_json(papers_url)
        for p in papers_data.get("data", []):
            tldr = p.get("tldr", {})
            papers.append({
                "paper_id": p.get("paperId", ""),
                "title": p.get("title", ""),
                "year": p.get("year"),
                "abstract": p.get("abstract", ""),
                "citation_count": p.get("citationCount", 0),
                "influential_citation_count": p.get("influentialCitationCount", 0),
                "tldr": tldr.get("text", "") if tldr else "",
                "open_access_pdf": (p.get("openAccessPdf") or {}).get("url", ""),
                "publication_date": p.get("publicationDate", ""),
                "journal": (p.get("journal") or {}).get("name", ""),
                "authors": [a.get("name", "") for a in p.get("authors", [])],
            })

        return {
            "author": {
                "author_id": author_id,
                "name": author.get("name", ""),
                "affiliations": author.get("affiliations", []),
                "paper_count": author.get("paperCount", 0),
                "citation_count": author.get("citationCount", 0),
                "h_index": author.get("hIndex", 0),
            },
            "papers": papers,
        }

    except Exception as e:
        logger.error("Semantic Scholar fetch failed: %s", e)
        return {"author": None, "papers": []}


# ---------------------------------------------------------------------------
# PubPeer
# ---------------------------------------------------------------------------

PUBPEER_BASE = "https://pubpeer.com"


def fetch_pubpeer(author_name: str) -> dict:
    """
    Search PubPeer for comments on author's papers.

    Returns:
        {
            "total_comments": int,
            "papers_with_comments": [
                {title, doi, url, comment_count, comments: [...]}
            ],
        }
    """
    _rate_limit("pubpeer", 1.0)

    search_url = f"{PUBPEER_BASE}/api/v3/search?q={urllib.parse.quote(author_name)}"
    logger.info("PubPeer search: %s", search_url)

    try:
        data = _http_get_json(search_url)
        feeds = data.get("feeds", [])

        papers = []
        for feed in feeds:
            pub = feed.get("publication", {})
            comments = feed.get("comments", [])
            papers.append({
                "title": pub.get("title", ""),
                "doi": pub.get("doi", ""),
                "url": f"{PUBPEER_BASE}/publications/{pub.get('id', '')}",
                "comment_count": len(comments),
                "comments": [
                    {
                        "text": c.get("content", ""),
                        "user": c.get("user", ""),
                        "date": c.get("created_at", ""),
                    }
                    for c in comments
                ],
            })

        return {
            "total_comments": sum(p["comment_count"] for p in papers),
            "papers_with_comments": papers,
        }

    except Exception as e:
        logger.error("PubPeer fetch failed: %s", e)
        return {"total_comments": 0, "papers_with_comments": []}


# ---------------------------------------------------------------------------
# arXiv
# ---------------------------------------------------------------------------

ARXIV_BASE = "http://export.arxiv.org/api/query"


def fetch_arxiv(author_name: str, max_results: int = 50) -> dict:
    """
    Search arXiv for preprints by author.

    Returns:
        {
            "total_results": int,
            "papers": [
                {id, title, summary, authors, published, updated, primary_category, categories, pdf_url}
            ],
        }
    """
    _rate_limit("arxiv", 3.0)  # arXiv is strict: max 1 request per 3 seconds

    query = urllib.parse.quote(f"au:{author_name}")
    url = f"{ARXIV_BASE}?search_query={query}&start=0&max_results={min(max_results, 100)}&sortBy=submittedDate&sortOrder=descending"
    logger.info("arXiv search: %s", url)

    try:
        import xml.etree.ElementTree as ET

        with urllib.request.urlopen(url, timeout=30) as resp:
            xml_data = resp.read().decode("utf-8")

        root = ET.fromstring(xml_data)
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

        entries = root.findall("atom:entry", ns)
        papers = []
        for entry in entries:
            # Skip the "totalResults" pseudo-entry
            if entry.find("atom:title", ns) is None:
                continue

            arxiv_id = ""
            id_elem = entry.find("atom:id", ns)
            if id_elem is not None:
                arxiv_id = id_elem.text.split("/")[-1] if id_elem.text else ""

            pdf_url = f"http://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id else ""

            papers.append({
                "id": arxiv_id,
                "title": (entry.find("atom:title", ns).text or "").strip().replace("\n", " "),
                "summary": (entry.find("atom:summary", ns).text or "").strip().replace("\n", " "),
                "authors": [a.text for a in entry.findall("atom:author/atom:name", ns) if a.text],
                "published": (entry.find("atom:published", ns).text or "")[:10],
                "updated": (entry.find("atom:updated", ns).text or "")[:10],
                "primary_category": (entry.find("arxiv:primary_category", ns).attrib.get("term", "")) if entry.find("arxiv:primary_category", ns) is not None else "",
                "categories": [c.attrib.get("term", "") for c in entry.findall("atom:category", ns)],
                "pdf_url": pdf_url,
            })

        total_elem = root.find("atom:totalResults", ns)
        total = int(total_elem.text) if total_elem is not None else len(papers)

        return {
            "total_results": total,
            "papers": papers,
        }

    except Exception as e:
        logger.error("arXiv fetch failed: %s", e)
        return {"total_results": 0, "papers": []}


# ---------------------------------------------------------------------------
# Retraction Watch (CSV-based)
# ---------------------------------------------------------------------------

RW_CSV_URL = "https://api.retractionwatch.com/v2/works"


def fetch_retraction_watch(author_name: str) -> dict:
    """
    Check Retraction Watch for retracted papers by author.

    Note: Retraction Watch requires institutional access for full API.
    This uses the public search endpoint if available, or returns empty.

    Returns:
        {
            "retracted_papers": [
                {title, doi, retraction_date, reason, original_paper_url}
            ],
        }
    """
    _rate_limit("retractionwatch", 1.0)

    # Try the public API endpoint
    search_url = f"https://retractionwatch.com/?s={urllib.parse.quote(author_name)}&post_type=retraction"
    logger.info("Retraction Watch search (web): %s", search_url)

    # For now, return empty as direct API access may require auth
    # TODO: Implement full Retraction Watch API integration when credentials available
    logger.info("Retraction Watch: direct API search not implemented (requires institutional access).")
    return {"retracted_papers": []}


# ---------------------------------------------------------------------------
# Google Scholar (via scholarly library, optional)
# ---------------------------------------------------------------------------


def fetch_google_scholar(author_name: str) -> dict:
    """
    Fetch author profile from Google Scholar using the `scholarly` library.

    Returns:
        {
            "name": str,
            "affiliation": str,
            "interests": [str],
            "cited_by": int,
            "h_index": int,
            "i10_index": int,
            "publications": [{title, year, cited_by, pub_url}],
        }
    """
    _rate_limit("google_scholar", 5.0)

    try:
        from scholarly import scholarly
    except ImportError:
        logger.warning("scholarly library not installed. Run: pip install scholarly")
        return {"name": "", "affiliation": "", "cited_by": 0, "h_index": 0, "i10_index": 0, "publications": []}

    try:
        logger.info("Google Scholar search: %s", author_name)
        search_query = scholarly.search_author(author_name)
        author = next(search_query, None)
        if not author:
            logger.warning("Google Scholar: no author found for '%s'", author_name)
            return {"name": "", "affiliation": "", "cited_by": 0, "h_index": 0, "i10_index": 0, "publications": []}

        # Fill author profile
        author = scholarly.fill(author)

        publications = []
        for pub in author.get("publications", []):
            publications.append({
                "title": pub.get("bib", {}).get("title", ""),
                "year": pub.get("bib", {}).get("pub_year", ""),
                "cited_by": pub.get("num_citations", 0),
                "pub_url": pub.get("pub_url", ""),
            })

        return {
            "name": author.get("name", ""),
            "affiliation": author.get("affiliation", ""),
            "interests": author.get("interests", []),
            "cited_by": author.get("citedby", 0),
            "h_index": author.get("hindex", 0),
            "i10_index": author.get("i10index", 0),
            "publications": publications,
        }

    except Exception as e:
        logger.error("Google Scholar fetch failed: %s", e)
        return {"name": "", "affiliation": "", "cited_by": 0, "h_index": 0, "i10_index": 0, "publications": []}


# ---------------------------------------------------------------------------
# Unified fetcher
# ---------------------------------------------------------------------------

class UnifiedFetcher:
    """
    High-level unified fetcher that orchestrates all free APIs.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.sources = self.config.get("international_sources", {})

    def fetch_all(self, author_name: str, institution: str = "", orcid: str = "") -> dict:
        """
        Fetch from all enabled APIs and merge into unified format.

        Returns dict compatible with domestic data_importer output:
        {
            "papers": [...],  # unified paper list
            "author_profile": {...},
            "metrics": {...},
            "reviews": {...},  # PubPeer
            "source_metadata": {...},
        }
        """
        result = {
            "papers": [],
            "author_profile": {},
            "metrics": {},
            "reviews": {"pubpeer": {}},
            "source_metadata": {},
        }

        # OpenAlex
        if self._enabled("openalex"):
            oa = fetch_openalex(author_name, institution, orcid)
            result["source_metadata"]["openalex"] = oa
            if oa.get("author"):
                result["author_profile"]["openalex"] = oa["author"]
            for w in oa.get("works", []):
                result["papers"].append(self._normalize_paper(w, "openalex"))

        # Semantic Scholar
        if self._enabled("semantic_scholar"):
            s2 = fetch_semantic_scholar(author_name)
            result["source_metadata"]["semantic_scholar"] = s2
            if s2.get("author"):
                result["author_profile"]["semantic_scholar"] = s2["author"]
            for p in s2.get("papers", []):
                result["papers"].append(self._normalize_paper(p, "semantic_scholar"))

        # arXiv
        if self._enabled("arxiv"):
            arx = fetch_arxiv(author_name)
            result["source_metadata"]["arxiv"] = arx
            for p in arx.get("papers", []):
                result["papers"].append(self._normalize_paper(p, "arxiv"))

        # PubPeer
        if self._enabled("pubpeer"):
            pp = fetch_pubpeer(author_name)
            result["reviews"]["pubpeer"] = pp

        # Google Scholar (optional)
        if self._enabled("google_scholar"):
            gs = fetch_google_scholar(author_name)
            result["source_metadata"]["google_scholar"] = gs
            if gs.get("name"):
                result["author_profile"]["google_scholar"] = gs

        # ORCID (if ORCID ID provided)
        if orcid and self._enabled("orcid"):
            oc = fetch_orcid(orcid)
            result["source_metadata"]["orcid"] = oc
            if oc.get("name"):
                result["author_profile"]["orcid"] = oc

        # Deduplicate papers
        result["papers"] = self._deduplicate(result["papers"])

        # Aggregate metrics
        result["metrics"] = self._aggregate_metrics(result["author_profile"])

        logger.info("Unified fetch complete: %d unique papers from %d sources",
                    len(result["papers"]), len(result["source_metadata"]))
        return result

    def _enabled(self, name: str) -> bool:
        src = self.sources.get(name, {})
        return src.get("enabled", True)

    def _normalize_paper(self, paper: dict, source: str) -> dict:
        """Normalize paper from different APIs to unified format."""
        normalized = {
            "source": source,
            "title": "",
            "authors": [],
            "year": None,
            "doi": "",
            "journal": "",
            "citation_count": 0,
            "url": "",
            "pdf_url": "",
            "abstract": "",
            "is_oa": False,
        }

        if source == "openalex":
            normalized["title"] = paper.get("title", "")
            normalized["authors"] = [a["author_name"] for a in paper.get("authorships", [])]
            normalized["year"] = paper.get("publication_year")
            normalized["doi"] = paper.get("doi", "")
            normalized["journal"] = paper.get("host_venue", {}).get("name", "")
            normalized["citation_count"] = paper.get("cited_by_count", 0)
            normalized["url"] = paper.get("id", "")
            normalized["pdf_url"] = paper.get("open_access", {}).get("oa_url", "")
            normalized["is_oa"] = paper.get("open_access", {}).get("is_oa", False)

        elif source == "semantic_scholar":
            normalized["title"] = paper.get("title", "")
            normalized["authors"] = paper.get("authors", [])
            normalized["year"] = paper.get("year")
            normalized["doi"] = ""  # S2 doesn't always expose DOI in search
            normalized["journal"] = paper.get("journal", "")
            normalized["citation_count"] = paper.get("citation_count", 0)
            normalized["abstract"] = paper.get("abstract", "")
            normalized["pdf_url"] = paper.get("open_access_pdf", "")
            normalized["is_oa"] = bool(paper.get("open_access_pdf"))

        elif source == "arxiv":
            normalized["title"] = paper.get("title", "")
            normalized["authors"] = paper.get("authors", [])
            normalized["year"] = int(paper.get("published", "")[:4]) if paper.get("published") else None
            normalized["doi"] = ""
            normalized["journal"] = f"arXiv:{paper.get('primary_category', '')}"
            normalized["url"] = f"http://arxiv.org/abs/{paper.get('id', '')}"
            normalized["pdf_url"] = paper.get("pdf_url", "")
            normalized["abstract"] = paper.get("summary", "")
            normalized["is_oa"] = True

        return normalized

    def _deduplicate(self, papers: list) -> list:
        """Simple DOI-based deduplication."""
        seen = {}
        for p in papers:
            key = p.get("doi", "").lower() or p.get("title", "").lower()
            if not key:
                continue
            if key in seen:
                # Merge: keep higher citation count
                existing = seen[key]
                if p.get("citation_count", 0) > existing.get("citation_count", 0):
                    # Update source to reflect merged data
                    existing["citation_count"] = p["citation_count"]
                    if not existing.get("doi"):
                        existing["doi"] = p.get("doi", "")
                    if not existing.get("pdf_url"):
                        existing["pdf_url"] = p.get("pdf_url", "")
                existing["source"] = f"{existing.get('source', '')}+{p.get('source', '')}"
            else:
                seen[key] = p
        return list(seen.values())

    def _aggregate_metrics(self, profiles: dict) -> dict:
        """Aggregate metrics from all sources."""
        metrics = {
            "total_papers": 0,
            "total_citations": 0,
            "h_index": 0,
            "i10_index": 0,
            "sources": list(profiles.keys()),
        }

        for source, profile in profiles.items():
            if source == "openalex":
                metrics["total_papers"] = max(metrics["total_papers"], profile.get("works_count", 0))
                metrics["total_citations"] = max(metrics["total_citations"], profile.get("cited_by_count", 0))
                metrics["h_index"] = max(metrics["h_index"], profile.get("h_index", 0))
                metrics["i10_index"] = max(metrics["i10_index"], profile.get("i10_index", 0))
            elif source == "semantic_scholar":
                metrics["total_papers"] = max(metrics["total_papers"], profile.get("paper_count", 0))
                metrics["total_citations"] = max(metrics["total_citations"], profile.get("citation_count", 0))
                metrics["h_index"] = max(metrics["h_index"], profile.get("h_index", 0))
            elif source == "google_scholar":
                metrics["total_citations"] = max(metrics["total_citations"], profile.get("cited_by", 0))
                metrics["h_index"] = max(metrics["h_index"], profile.get("h_index", 0))
                metrics["i10_index"] = max(metrics["i10_index"], profile.get("i10_index", 0))

        return metrics


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="International academic data fetcher (free APIs)")
    parser.add_argument("--name", "-n", required=True, help="Author name")
    parser.add_argument("--institution", "-i", default="", help="Institution name")
    parser.add_argument("--orcid", "-o", default="", help="ORCID ID")
    parser.add_argument("--output", "-O", required=True, help="Output JSON file path")
    parser.add_argument("--source", "-s", default="all", choices=["all", "openalex", "orcid", "semantic_scholar", "google_scholar", "pubpeer", "arxiv"])
    args = parser.parse_args()

    if args.source == "all":
        fetcher = UnifiedFetcher()
        result = fetcher.fetch_all(args.name, args.institution, args.orcid)
    else:
        func = globals()[f"fetch_{args.source}"]
        result = func(args.name)

    save_json(result, Path(args.output))
    logger.info("Results saved to: %s", args.output)


if __name__ == "__main__":
    main()
