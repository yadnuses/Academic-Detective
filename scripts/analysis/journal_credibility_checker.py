#!/usr/bin/env python3
"""
journal_credibility_checker.py

Free journal credibility assessment tool using open-access databases:
- DOAJ (Directory of Open Access Journals)
- SCImago Journal Rank (SJR & quartile via page scraping)
- Retraction Watch (public search)
- COPE (Committee on Publication Ethics membership)
- OASPA (Open Access Scholarly Publishers Association)

Usage:
    python journal_credibility_checker.py --issn 2096-787X
    python journal_credibility_checker.py --journal-name "新闻文化建设"
    python journal_credibility_checker.py --input ./journals.json --output ./journal_cred_report.json
"""

import argparse
import json
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.utils import get_logger, save_json

logger = get_logger("journal_credibility")

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
_LAST_CALL_TIME = {}


def _rate_limit(domain: str, min_interval: float = 0.5):
    now = time.time()
    last = _LAST_CALL_TIME.get(domain, 0)
    wait = min_interval - (now - last)
    if wait > 0:
        time.sleep(wait)
    _LAST_CALL_TIME[domain] = time.time()


def _http_get(url: str, headers: dict = None, timeout: int = 30) -> Tuple[int, str]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning("HTTP GET failed for %s: %s", url, e)
        return 0, ""


# ---------------------------------------------------------------------------
# DOAJ
# ---------------------------------------------------------------------------

def check_doaj(issn: str = "", journal_name: str = "") -> Dict:
    """Query DOAJ API for journal presence."""
    _rate_limit("doaj", 0.5)
    result = {"in_doaj": False, "doaj_url": "", "apc": None, "peer_review": None, "license": None}

    query = ""
    if issn:
        query = f"bibjson.eissn:{issn} OR bibjson.pissn:{issn}"
    elif journal_name:
        query = f"bibjson.title:{journal_name}"
    else:
        return result

    url = f"https://doaj.org/api/v3/search/journals/{urllib.parse.quote(query)}?pageSize=5"
    status, text = _http_get(url, headers={"Accept": "application/json"})
    if status != 200:
        logger.warning("DOAJ query failed: status=%d", status)
        return result

    try:
        data = json.loads(text)
        hits = data.get("results", [])
        if hits:
            j = hits[0].get("bibjson", {})
            result["in_doaj"] = True
            result["doaj_url"] = f"https://doaj.org/toc/{hits[0].get('id', '')}"
            result["apc"] = j.get("apc", {}).get("has_apc", None)
            result["peer_review"] = j.get("editorial", {}).get("review_process", [])
            result["license"] = j.get("license", [{}])[0].get("type", None) if j.get("license") else None
    except Exception as e:
        logger.warning("DOAJ parse error: %s", e)

    return result


# ---------------------------------------------------------------------------
# SCImago (page scraping)
# ---------------------------------------------------------------------------

def check_scimago(issn: str = "") -> Dict:
    """Scrape SCImago journal page for SJR and quartile."""
    _rate_limit("scimago", 1.0)
    result = {"sjr": None, "quartile": None, "h_index": None, "found": False}
    if not issn:
        return result

    search_url = f"https://www.scimagojr.com/journalsearch.php?q={issn}"
    status, text = _http_get(search_url)
    if status != 200:
        return result

    # SCImago search redirects or shows result page
    # Try to extract journal page link
    m = re.search(r'href="(https://www\.scimagojr\.com/journalsearch\.php\?q=[^"]+&tip=sid[^"]*)"', text)
    if not m:
        m = re.search(r'href="(/journalsearch\.php\?q=[^"]+&tip=sid[^"]*)"', text)

    journal_url = None
    if m:
        link = m.group(1)
        if link.startswith("/"):
            journal_url = f"https://www.scimagojr.com{link}"
        else:
            journal_url = link

    if not journal_url:
        # Try direct pattern: some pages contain SJR directly
        sjr_m = re.search(r'SJR\s*[=:]\s*([0-9]+(?:\.[0-9]+)?)', text, re.I)
        if sjr_m:
            result["sjr"] = float(sjr_m.group(1))
        q_m = re.search(r'Q([1-4])', text)
        if q_m:
            result["quartile"] = int(q_m.group(1))
        return result

    _rate_limit("scimago", 1.0)
    status2, text2 = _http_get(journal_url)
    if status2 != 200:
        return result

    result["found"] = True
    sjr_m = re.search(r'SJR\s*2023[^0-9]*([0-9]+(?:\.[0-9]+)?)', text2, re.I)
    if not sjr_m:
        sjr_m = re.search(r'SJR\s*SCImago Journal Rank[^0-9]*([0-9]+(?:\.[0-9]+)?)', text2, re.I)
    if sjr_m:
        result["sjr"] = float(sjr_m.group(1))

    q_m = re.search(r'Q([1-4])\s*\(', text2)
    if not q_m:
        q_m = re.search(r'class=["\']quartile[^>]*>\s*Q([1-4])', text2, re.I)
    if q_m:
        result["quartile"] = int(q_m.group(1))

    h_m = re.search(r'H-index\s*([0-9]+)', text2, re.I)
    if h_m:
        result["h_index"] = int(h_m.group(1))

    return result


# ---------------------------------------------------------------------------
# Retraction Watch
# ---------------------------------------------------------------------------

def check_retraction_watch(issn: str = "", journal_name: str = "") -> Dict:
    """Search Retraction Watch database for journal retractions."""
    _rate_limit("retractionwatch", 1.0)
    result = {"retraction_count": 0, "retraction_url": "", "has_retractions": False}

    query = issn or journal_name
    if not query:
        return result

    # Use Retraction Watch public search endpoint
    url = f"https://retractionwatch.com/?s={urllib.parse.quote(query)}&search=Search"
    status, text = _http_get(url)
    if status != 200:
        return result

    # Check if results exist
    if "No results" in text or "no posts matched" in text.lower():
        return result

    # Count result entries (approximate)
    entries = re.findall(r'class="entry-title"', text)
    result["retraction_count"] = len(entries)
    result["has_retractions"] = len(entries) > 0
    result["retraction_url"] = url
    return result


# ---------------------------------------------------------------------------
# COPE membership (cached list)
# ---------------------------------------------------------------------------

COPE_MEMBERS_URL = "https://publicationethics.org/membership/members"
COPE_CACHE_FILE = Path(__file__).parent / ".cache" / "cope_members.json"
OASPA_MEMBERS_URL = "https://oaspa.org/membership/members/"
OASPA_CACHE_FILE = Path(__file__).parent / ".cache" / "oaspa_members.json"


def _load_cached_members(cache_file: Path, url: str, org_name: str) -> set:
    """Load member list from cache or fetch and cache."""
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    # Use cache if less than 7 days old
    if cache_file.exists():
        age = (datetime.now().timestamp() - cache_file.stat().st_mtime) / 86400
        if age < 7:
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return set(json.load(f))
            except Exception:
                pass

    _rate_limit("members", 2.0)
    status, text = _http_get(url)
    members = set()
    if status != 200:
        logger.warning("%s member fetch failed: status=%d", org_name, status)
        return members

    # Extract member names or journal names from HTML
    # COPE page: member entries in various formats
    for m in re.finditer(r'<a[^>]*href="[^"]*"[^>]*>([^<]{3,80})</a>', text):
        name = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if name and len(name) > 3:
            members.add(name.lower())

    # Also try pattern for publisher names
    for m in re.finditer(r'class="[^"]*member[^"]*"[^>]*>.*?<h[23][^>]*>([^<]+)', text, re.S):
        name = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if name and len(name) > 3:
            members.add(name.lower())

    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(list(members), f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return members


def check_cope(publisher_name: str = "", journal_name: str = "") -> Dict:
    """Check if publisher/journal is in COPE membership."""
    result = {"is_cope_member": False, "match": None}
    if not publisher_name and not journal_name:
        return result

    members = _load_cached_members(COPE_CACHE_FILE, COPE_MEMBERS_URL, "COPE")
    queries = [q.lower() for q in [publisher_name, journal_name] if q]

    for member in members:
        for q in queries:
            if q in member or member in q:
                result["is_cope_member"] = True
                result["match"] = member
                return result
    return result


def check_oaspa(publisher_name: str = "", journal_name: str = "") -> Dict:
    """Check if publisher/journal is in OASPA membership."""
    result = {"is_oaspa_member": False, "match": None}
    if not publisher_name and not journal_name:
        return result

    members = _load_cached_members(OASPA_CACHE_FILE, OASPA_MEMBERS_URL, "OASPA")
    queries = [q.lower() for q in [publisher_name, journal_name] if q]

    for member in members:
        for q in queries:
            if q in member or member in q:
                result["is_oaspa_member"] = True
                result["match"] = member
                return result
    return result


# ---------------------------------------------------------------------------
# Composite checker
# ---------------------------------------------------------------------------

def check_journal(issn: str = "", journal_name: str = "", publisher: str = "") -> Dict:
    """Run all free checks against a journal and return composite report."""
    logger.info("Checking journal: issn=%s name=%s", issn, journal_name)

    doaj = check_doaj(issn, journal_name)
    scimago = check_scimago(issn)
    retraction = check_retraction_watch(issn, journal_name)
    cope = check_cope(publisher, journal_name)
    oaspa = check_oaspa(publisher, journal_name)

    # Composite scoring (0-100)
    score = 0
    reasons = []

    if doaj["in_doaj"]:
        score += 25
        reasons.append("DOAJ收录")
    else:
        reasons.append("DOAJ未收录")

    if scimago["quartile"]:
        score += scimago["quartile"] * 5  # Q1=5, Q2=10, Q3=15, Q4=20
        reasons.append(f"SCImago Q{scimago['quartile']}")
    else:
        reasons.append("SCImago无记录")

    if cope["is_cope_member"]:
        score += 15
        reasons.append("COPE成员")
    else:
        reasons.append("COPE非成员")

    if oaspa["is_oaspa_member"]:
        score += 15
        reasons.append("OASPA成员")
    else:
        reasons.append("OASPA非成员")

    if retraction["has_retractions"]:
        score -= min(retraction["retraction_count"] * 5, 20)
        reasons.append(f"Retraction Watch有{retraction['retraction_count']}条记录")
    else:
        score += 10
        reasons.append("Retraction Watch无记录")

    score = max(0, min(100, score))

    # Risk level
    if score >= 70:
        risk = "低"
    elif score >= 40:
        risk = "中"
    else:
        risk = "高"

    return {
        "journal_name": journal_name,
        "issn": issn,
        "publisher": publisher,
        "checked_at": datetime.now().isoformat(),
        "composite_score": score,
        "risk_level": risk,
        "reasons": reasons,
        "doaj": doaj,
        "scimago": scimago,
        "retraction_watch": retraction,
        "cope": cope,
        "oaspa": oaspa,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Journal credibility checker (free APIs)")
    parser.add_argument("--issn", default="", help="Journal ISSN")
    parser.add_argument("--journal-name", default="", help="Journal name")
    parser.add_argument("--publisher", default="", help="Publisher name")
    parser.add_argument("--input", type=Path, help="JSON array of journals [{issn, name, publisher}]")
    parser.add_argument("--output", type=Path, default=Path("journal_credibility_report.json"), help="Output JSON path")
    args = parser.parse_args()

    journals = []
    if args.input and args.input.exists():
        with open(args.input, "r", encoding="utf-8") as f:
            journals = json.load(f)
    elif args.issn or args.journal_name:
        journals = [{"issn": args.issn, "name": args.journal_name, "publisher": args.publisher}]
    else:
        print("[ERROR] Provide --issn/--journal-name or --input")
        return

    results = []
    for j in journals:
        r = check_journal(
            issn=j.get("issn", ""),
            journal_name=j.get("name", j.get("journal_name", "")),
            publisher=j.get("publisher", ""),
        )
        results.append(r)
        print(f"\n[{r['risk_level']}风险] {r['journal_name'] or r['issn']} | 综合评分: {r['composite_score']}/100")
        print("  " + " | ".join(r["reasons"]))

    save_json({"journals": results, "generated_at": datetime.now().isoformat()}, args.output)
    print(f"\n[OK] Report saved: {args.output}")


if __name__ == "__main__":
    main()
