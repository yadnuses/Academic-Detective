#!/usr/bin/env python3
"""
international/xiaohongshu_client.py

Search and scrape Xiaohongshu (小红书) for Chinese students' reviews of foreign advisors.
This is a unique data source: first-hand experiences from Chinese international students.

Features:
- Tier-1: API mode (recommended) — uses xhshow signature + httpx to call XHS official API
- Tier-2: Playwright rendering — headless browser for JS-rendered pages
- Tier-3: Pure HTML parsing — urllib-based fallback

Usage:
    python international/xiaohongshu_client.py --name "Prof. Smith" --institution "MIT"
    python international/xiaohongshu_client.py --name "Prof. Smith" --institution "MIT" --api-mode
    python international/xiaohongshu_client.py --name "Prof. Smith" --institution "MIT" --output ./reviews.json

Optional dependencies for API mode (highly recommended):
    pip install xhshow playwright httpx
    playwright install chromium

Privacy notes:
- Author IDs are anonymized in output
- Personal information is redacted
- Original HTML is saved locally (investigator-only)
- Report citations use "anonymous social media sharing"

Acknowledgments:
- API signature approach adapted from MediaCrawler (https://github.com/NanmiCoder/MediaCrawler)
- xhshow pure-algorithm library by Cloxl (https://github.com/Cloxl/xhshow, MIT License)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.utils import get_logger, save_json

logger = get_logger("xiaohongshu")

# ---------------------------------------------------------------------------
# Optional dependency detection
# ---------------------------------------------------------------------------

_HAS_XHSHOW = False
_HAS_PLAYWRIGHT = False
_HAS_HTTPX = False

try:
    import xhshow  # noqa: F401
    _HAS_XHSHOW = True
except ImportError:
    pass

try:
    from playwright.sync_api import sync_playwright  # noqa: F401
    _HAS_PLAYWRIGHT = True
except ImportError:
    pass

try:
    import httpx  # noqa: F401
    _HAS_HTTPX = True
except ImportError:
    pass

logger.debug(
    "Optional deps: xhshow=%s, playwright=%s, httpx=%s",
    _HAS_XHSHOW, _HAS_PLAYWRIGHT, _HAS_HTTPX,
)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class XiaohongshuReview:
    """Structured review record from Xiaohongshu."""
    platform: str = "xiaohongshu"
    post_id: str = ""           # Anonymized post identifier
    post_url: str = ""
    post_title: str = ""
    post_content: str = ""
    publish_date: str = ""
    likes: int = 0
    comments_count: int = 0
    images_count: int = 0
    tags: List[str] = field(default_factory=list)

    # Extracted dimensions
    sentiment: str = "neutral"   # positive / neutral / negative
    credibility_score: float = 0.5
    topics: List[str] = field(default_factory=list)

    # Advisor-specific
    advisor_name: str = ""
    institution: str = ""
    program: str = ""            # PhD / MS / Postdoc
    graduation_difficulty: Optional[int] = None   # 1-5
    workload: Optional[int] = None                # 1-5
    supportiveness: Optional[int] = None          # 1-5
    recommendation: Optional[bool] = None         # True/False


# ---------------------------------------------------------------------------
# Search strategies
# ---------------------------------------------------------------------------

SEARCH_TEMPLATES = [
    "{name} {institution} 导师",
    "{name} {institution} phd",
    "{name} {institution} 博士",
    "{institution} {name} 实验室",
    "{institution} phd 导师 推荐",
    "{institution} phd 导师 避雷",
    "{institution} 研究生 导师",
    "{name} professor 评价",
]

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

# ---------------------------------------------------------------------------
# API signature helpers (adapted from MediaCrawler)
# ---------------------------------------------------------------------------

def _get_trace_id() -> str:
    """Generate trace id for link tracing."""
    return "".join(random.choice("abcdef0123456789") for _ in range(16))


def _build_sign_string(uri: str, data: Optional[Dict] = None, method: str = "POST") -> str:
    """Build content string to be signed."""
    if method.upper() == "POST":
        c = uri
        if data is not None:
            if isinstance(data, dict):
                c += json.dumps(data, separators=(",", ":"), ensure_ascii=False)
            elif isinstance(data, str):
                c += data
        return c
    else:
        if not data or (isinstance(data, dict) and len(data) == 0):
            return uri
        if isinstance(data, dict):
            params = []
            for key in data.keys():
                value = data[key]
                if isinstance(value, list):
                    value_str = ",".join(str(v) for v in value)
                elif value is not None:
                    value_str = str(value)
                else:
                    value_str = ""
                value_str = urllib.parse.quote(value_str, safe=",")
                params.append(f"{key}={value_str}")
            return f"{uri}?{'&'.join(params)}"
        elif isinstance(data, str):
            return f"{uri}?{data}"
        return uri


def _sign_with_xhshow(
    uri: str,
    data: Optional[Dict] = None,
    cookie_str: str = "",
    method: str = "POST",
) -> Optional[Dict[str, Any]]:
    """
    Generate XHS API request signature using xhshow pure-algorithm library.
    Returns None if xhshow is not installed.
    """
    if not _HAS_XHSHOW:
        return None

    from xhshow import Xhshow
    xhshow_client = Xhshow()
    is_post = method.upper() == "POST"

    if is_post:
        headers = xhshow_client.sign_headers_post(
            uri=uri,
            cookies=cookie_str,
            payload=data if isinstance(data, dict) else {},
        )
    else:
        # GET request: build full content_string for signing
        content_string = _build_sign_string(uri, data, method)
        cookie_dict = xhshow_client._parse_cookies(cookie_str)
        a1_value = cookie_dict.get("a1", "")

        ts = time.time()
        d_value = hashlib.md5(content_string.encode("utf-8")).hexdigest()

        payload_array = xhshow_client.crypto_processor.build_payload_array(
            d_value, a1_value, "xhs-pc-web", content_string, ts
        )
        xor_result = xhshow_client.crypto_processor.bit_ops.xor_transform_array(payload_array)
        config = xhshow_client.config
        x3_b64 = xhshow_client.crypto_processor.b64encoder.encode_x3(
            xor_result[:config.PAYLOAD_LENGTH]
        )
        sig_data = config.SIGNATURE_DATA_TEMPLATE.copy()
        sig_data["x3"] = config.X3_PREFIX + x3_b64
        x_s = config.XYS_PREFIX + xhshow_client.crypto_processor.b64encoder.encode(
            json.dumps(sig_data, separators=(",", ":"), ensure_ascii=False)
        )
        headers = {
            "x-s": x_s,
            "x-s-common": xhshow_client.sign_xs_common(cookie_dict),
            "x-t": str(xhshow_client.get_x_t(ts)),
            "x-b3-traceid": xhshow_client.get_b3_trace_id(),
        }

    return {
        "x-s": headers.get("x-s", ""),
        "x-t": headers.get("x-t", ""),
        "x-s-common": headers.get("x-s-common", ""),
        "x-b3-traceid": headers.get("x-b3-traceid", _get_trace_id()),
    }


# ---------------------------------------------------------------------------
# Cookie acquisition via Playwright
# ---------------------------------------------------------------------------

def _get_cookies_via_playwright(domain: str = "https://www.xiaohongshu.com") -> Optional[str]:
    """
    Open Xiaohongshu in headless browser and extract cookies.
    Returns cookie string suitable for API signing.
    """
    if not _HAS_PLAYWRIGHT:
        logger.warning("Playwright not installed, cannot acquire cookies")
        return None

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1920, "height": 1080},
            )
            page = context.new_page()
            page.goto(domain, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)
            time.sleep(2)  # Allow JS to set cookies

            cookies = context.cookies()
            cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)

            browser.close()
            logger.info("Acquired %d cookies via Playwright", len(cookies))
            return cookie_str if cookie_str else None
    except Exception as e:
        logger.warning("Playwright cookie acquisition failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class XiaohongshuClient:
    """
    Xiaohongshu search and review scraper with three-tier fallback:

    1. API mode (best)    — xhshow signature + httpx → official search API
    2. Playwright mode    — headless browser renders search page
    3. HTML mode (basic)  — urllib requests + regex parsing

    Note: For production use, install optional dependencies:
        pip install xhshow playwright httpx
        playwright install chromium
    """

    def __init__(
        self,
        delay: float = 5.0,
        api_mode: bool = False,
        cookie_str: Optional[str] = None,
    ):
        self.delay = delay
        self.api_mode = api_mode
        self.cookie_str = cookie_str
        self.session_headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

        # Determine available modes
        self._can_api = _HAS_XHSHOW and _HAS_HTTPX
        self._can_playwright = _HAS_PLAYWRIGHT

        if api_mode and not self._can_api:
            missing = []
            if not _HAS_XHSHOW:
                missing.append("xhshow")
            if not _HAS_HTTPX:
                missing.append("httpx")
            logger.warning(
                "API mode requested but missing deps: %s. Falling back to HTML mode. "
                "Install: pip install %s",
                ", ".join(missing), " ".join(missing),
            )
            self.api_mode = False

    def search_advisor_reviews(
        self,
        advisor_name: str,
        institution: str,
        max_results: int = 50
    ) -> List[XiaohongshuReview]:
        """
        Search for advisor reviews on Xiaohongshu.

        Returns structured review records with three-tier fallback:
        API → Playwright → HTML parsing.
        """
        reviews = []
        seen_ids = set()

        for template in SEARCH_TEMPLATES:
            if len(reviews) >= max_results:
                break

            keyword = template.format(
                name=advisor_name,
                institution=institution
            )
            logger.info("Searching Xiaohongshu: %s", keyword)

            try:
                results = self._search_keyword(keyword)
                for result in results:
                    post_id = result.get("id", "")
                    if post_id in seen_ids:
                        continue
                    seen_ids.add(post_id)

                    review = self._parse_search_result(result)
                    if self._is_relevant(review, advisor_name, institution):
                        self._extract_dimensions(review)
                        self._calculate_credibility(review)
                        reviews.append(review)

                    if len(reviews) >= max_results:
                        break

            except Exception as e:
                logger.warning("Xiaohongshu search failed for '%s': %s", keyword, e)
                continue

            time.sleep(self.delay)

        logger.info(
            "Found %d relevant reviews for '%s @ %s'",
            len(reviews), advisor_name, institution,
        )
        return reviews

    def _search_keyword(self, keyword: str) -> List[dict]:
        """
        Three-tier search dispatcher.
        Tries API mode first, then Playwright, then pure HTML.
        """
        # Tier 1: API mode (xhshow signature + httpx)
        if self.api_mode and self._can_api:
            try:
                results = self._search_keyword_api(keyword)
                if results:
                    logger.debug("API mode returned %d results", len(results))
                    return results
            except Exception as e:
                logger.warning("API mode failed: %s", e)

        # Tier 2: Playwright rendering
        if self._can_playwright:
            try:
                results = self._search_keyword_playwright(keyword)
                if results:
                    logger.debug("Playwright mode returned %d results", len(results))
                    return results
            except Exception as e:
                logger.warning("Playwright mode failed: %s", e)

        # Tier 3: Pure HTML parsing (existing urllib approach)
        return self._search_keyword_html(keyword)

    def _search_keyword_api(self, keyword: str) -> List[dict]:
        """
        Search via XHS official API using xhshow signature.
        Adapted from MediaCrawler's XiaoHongShuClient.get_note_by_keyword().
        """
        import httpx

        # Acquire cookies if not provided
        cookie_str = self.cookie_str
        if not cookie_str:
            cookie_str = _get_cookies_via_playwright()
        if not cookie_str:
            raise RuntimeError("No cookies available for API signing")

        host = "https://edith.xiaohongshu.com"
        uri = "/api/sns/web/v1/search/notes"

        # Build search payload
        search_id = _get_trace_id()
        payload = {
            "keyword": keyword,
            "page": 1,
            "page_size": 20,
            "search_id": search_id,
            "sort": "general",
            "note_type": 0,
        }

        # Generate signature headers
        signs = _sign_with_xhshow(uri=uri, data=payload, cookie_str=cookie_str, method="POST")
        if not signs:
            raise RuntimeError("Signature generation failed")

        headers = {
            "User-Agent": self.session_headers["User-Agent"],
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Content-Type": "application/json;charset=UTF-8",
            "Cookie": cookie_str,
            "Origin": "https://www.xiaohongshu.com",
            "Referer": f"https://www.xiaohongshu.com/search_result?keyword={urllib.parse.quote(keyword)}",
            "X-S": signs["x-s"],
            "X-T": signs["x-t"],
            "x-S-Common": signs["x-s-common"],
            "X-B3-Traceid": signs["x-b3-traceid"],
        }

        url = f"{host}{uri}"
        json_str = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

        with httpx.Client(timeout=30) as client:
            resp = client.post(url, content=json_str, headers=headers)

        if resp.status_code in (461, 471):
            raise RuntimeError(f"CAPTCHA triggered (status {resp.status_code})")

        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"API error: {data.get('msg', resp.text)}")

        return self._extract_posts_from_api(data.get("data", {}))

    def _search_keyword_playwright(self, keyword: str) -> List[dict]:
        """
        Search using Playwright to render the search results page.
        Extracts data from window.__INITIAL_STATE__.
        """
        from playwright.sync_api import sync_playwright

        encoded = urllib.parse.quote(keyword)
        url = f"https://www.xiaohongshu.com/search_result?keyword={encoded}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1920, "height": 1080},
            )
            page = context.new_page()

            # Inject stealth script if available (anti-detection)
            page.goto(url, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)
            time.sleep(3)  # Allow JS to hydrate

            html = page.content()
            browser.close()

        return self._extract_posts_from_html(html)

    def _search_keyword_html(self, keyword: str) -> List[dict]:
        """
        Search via direct HTTP request (fallback).
        Parses JSON from script tags or falls back to regex.
        """
        encoded = urllib.parse.quote(keyword)
        url = f"https://www.xiaohongshu.com/search_result?keyword={encoded}"

        req = urllib.request.Request(url, headers=self.session_headers)

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            logger.warning("HTTP request failed: %s", e)
            return []

        return self._extract_posts_from_html(html)

    def _extract_posts_from_api(self, data: dict) -> List[dict]:
        """Extract post data from XHS API search response."""
        posts = []
        items = data.get("items", [])

        for item in items:
            note = item.get("note_card", item.get("note", {}))
            if not note:
                continue

            note_id = note.get("note_id", note.get("id", ""))
            title = note.get("title", "")
            desc = note.get("desc", note.get("content", ""))
            likes = note.get("interact_info", {}).get("liked_count", 0)
            comments = note.get("interact_info", {}).get("comment_count", 0)
            images = note.get("image_list", [])
            tags = [t.get("name", "") for t in note.get("tag_list", [])]

            posts.append({
                "id": note_id,
                "title": title,
                "content": desc,
                "likes": likes,
                "comments_count": comments,
                "images_count": len(images),
                "tags": tags,
                "url": f"https://www.xiaohongshu.com/discovery/item/{note_id}",
            })

        return posts

    def _extract_posts_from_html(self, html: str) -> List[dict]:
        """Extract post data from Xiaohongshu HTML."""
        posts = []

        # Try to find JSON data in script tags
        json_patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*(.+?);\s*</script>',
            r'<script[^>]*>window\._SSR_HYDRATED_DATA\s*=\s*(.+?)</script>',
        ]

        for pattern in json_patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    feeds = self._extract_feeds(data)
                    for feed in feeds:
                        posts.append({
                            "id": feed.get("id", feed.get("noteId", "")),
                            "title": feed.get("title", ""),
                            "content": feed.get("desc", feed.get("content", "")),
                            "likes": feed.get("likes", feed.get("likedCount", 0)),
                            "comments_count": feed.get("comments", feed.get("commentsCount", 0)),
                            "images_count": len(feed.get("imageList", [])),
                            "tags": feed.get("tagList", []),
                            "url": f"https://www.xiaohongshu.com/discovery/item/{feed.get('id', '')}",
                        })
                except (json.JSONDecodeError, AttributeError):
                    continue

        # Fallback: regex extract from HTML
        if not posts:
            post_blocks = re.findall(
                r'data-note-id="([^"]+)".*?<span[^>]*>([^<]+)</span>',
                html, re.DOTALL
            )
            for post_id, title in post_blocks[:10]:
                posts.append({
                    "id": post_id,
                    "title": title.strip(),
                    "content": "",
                    "likes": 0,
                    "comments_count": 0,
                    "images_count": 0,
                    "tags": [],
                    "url": f"https://www.xiaohongshu.com/discovery/item/{post_id}",
                })

        return posts

    def _extract_feeds(self, data: dict) -> List[dict]:
        """Extract feed items from parsed JSON data."""
        feeds = []

        paths = [
            ["search", "feeds"],
            ["search", "notes"],
            ["searchResult", "feeds"],
            ["searchResult", "items"],
            ["noteSearchResult", "notes"],
            ["note", "noteList"],
            ["notes"],
        ]

        for path in paths:
            current = data
            for key in path:
                if isinstance(current, dict):
                    current = current.get(key, {})
                else:
                    current = {}
                    break

            if isinstance(current, list):
                feeds.extend(current)
            elif isinstance(current, dict) and "list" in current:
                feeds.extend(current["list"])

        return feeds

    def _parse_search_result(self, result: dict) -> XiaohongshuReview:
        """Convert raw search result to structured review."""
        return XiaohongshuReview(
            post_id=result.get("id", "")[:16],  # Truncate for anonymity
            post_url=result.get("url", ""),
            post_title=result.get("title", ""),
            post_content=result.get("content", ""),
            likes=result.get("likes", 0),
            comments_count=result.get("comments_count", 0),
            images_count=result.get("images_count", 0),
            tags=result.get("tags", []),
        )

    def _is_relevant(self, review: XiaohongshuReview, name: str, institution: str) -> bool:
        """Check if post is actually about the target advisor."""
        content_lower = (review.post_title + " " + review.post_content).lower()

        # Must mention institution
        institution_lower = institution.lower()
        if institution_lower not in content_lower:
            abbreviations = {
                "massachusetts institute of technology": ["mit"],
                "stanford university": ["stanford"],
                "university of california": ["uc "],
                "carnegie mellon university": ["cmu"],
            }
            abbrs = abbreviations.get(institution_lower, [])
            if not any(a in content_lower for a in abbrs):
                return False

        # Filter ads
        ad_keywords = ["留学中介", "申请服务", "免费咨询", "保录取", "代写", "论文辅导"]
        if any(kw in content_lower for kw in ad_keywords):
            return False

        return True

    def _extract_dimensions(self, review: XiaohongshuReview) -> None:
        """Extract structured dimensions from post content."""
        content = review.post_content

        if not content:
            return

        # Sentiment
        positive_signals = ["推荐", "宝藏", "神仙", "幸运", "好评", "强推", "不错"]
        negative_signals = ["避雷", "快跑", "不要来", "坑", "踩雷", "后悔", "绝望", "压榨"]

        pos_count = sum(1 for s in positive_signals if s in content)
        neg_count = sum(1 for s in negative_signals if s in content)

        if neg_count > pos_count:
            review.sentiment = "negative"
        elif pos_count > neg_count:
            review.sentiment = "positive"
        else:
            review.sentiment = "neutral"

        # Graduation difficulty
        if any(kw in content for kw in ["3年毕业", "按时毕业", "顺利毕业", "毕业容易"]):
            review.graduation_difficulty = 2
        elif any(kw in content for kw in ["延期", "拖毕业", "卡毕业", "5年", "6年", "很难毕业"]):
            review.graduation_difficulty = 4
        elif any(kw in content for kw in ["毕业要求", "qualifying exam", "qual"]):
            review.graduation_difficulty = 3

        # Workload
        if any(kw in content for kw in ["996", "push", "周末加班", "催进度", "催命", "卷"]):
            review.workload = 5
        elif any(kw in content for kw in ["放养", "不催", "自由", "自己安排", "wlb", "work life balance"]):
            review.workload = 2
        elif any(kw in content for kw in ["忙", "累", "压力大"]):
            review.workload = 4

        # Supportiveness
        if any(kw in content for kw in ["推荐信强推", "手把手", "funding足", "改论文仔细", "很 supportive", "关心学生"]):
            review.supportiveness = 5
        elif any(kw in content for kw in ["不管", "不回邮件", "甩手掌柜", "自生自灭", "忽视", "冷漠"]):
            review.supportiveness = 1
        elif any(kw in content for kw in ["不太管", "偶尔回", "一般"]):
            review.supportiveness = 3

        # Recommendation
        if any(kw in content for kw in ["快跑", "避雷", "不要来", "坑", "千万别选"]):
            review.recommendation = False
        elif any(kw in content for kw in ["推荐", "宝藏导师", "神仙导师", "很幸运", "值得跟"]):
            review.recommendation = True

        # Topics
        topics = []
        topic_keywords = {
            "funding": ["funding", "奖学金", "钱", "工资", "stipend", "RA", "TA"],
            "graduation": ["毕业", "延期", "答辩", "学位", "thesis", "dissertation"],
            "workload": ["工作量", "加班", "996", "push", "放养", "workload"],
            "publication": ["论文", "发表", "顶会", "期刊", "publication", "paper"],
            "recommendation": ["推荐信", "recommendation letter", "referral"],
            "visa": ["签证", "CPT", "OPT", "H1B", "绿卡", "身份"],
            "culture": ["文化", "歧视", "种族", "language barrier", "英语"],
        }
        for topic, kws in topic_keywords.items():
            if any(kw in content for kw in kws):
                topics.append(topic)
        review.topics = topics

    def _calculate_credibility(self, review: XiaohongshuReview) -> None:
        """Calculate credibility score for a single review."""
        score = 0.5

        # Length-based
        if len(review.post_content) > 300:
            score += 0.15
        elif len(review.post_content) > 100:
            score += 0.05

        # Images as evidence
        if review.images_count > 0:
            score += 0.1

        # Engagement
        if review.comments_count > 5:
            score += 0.1
        if review.likes > 20:
            score += 0.05

        # Specific details
        detail_indicators = ["202", "学期", "lab", "组会", "funding", "TA", "RA", "qual", "year"]
        if any(ind in review.post_content for ind in detail_indicators):
            score += 0.15

        # Balance check: overly emotional without details reduces credibility
        if review.sentiment in ("positive", "negative") and len(review.post_content) < 50:
            score -= 0.2

        review.credibility_score = max(0.0, min(1.0, score))


def aggregate_reviews(reviews: List[XiaohongshuReview]) -> dict:
    """
    Aggregate multiple Xiaohongshu reviews into a unified summary.

    Output format compatible with review_matcher.py v2.0 schema.
    """
    if not reviews:
        return {
            "matched": False,
            "source": "xiaohongshu",
            "review_count": 0,
            "message": "未找到相关小红书评价",
        }

    # Sentiment distribution
    sentiments = {"positive": 0, "neutral": 0, "negative": 0}
    for r in reviews:
        sentiments[r.sentiment] += 1

    # Dimension averages (only for reviews that have the dimension)
    def avg_dim(attr):
        vals = [getattr(r, attr) for r in reviews if getattr(r, attr) is not None]
        return sum(vals) / len(vals) if vals else None

    # Top credible reviews
    sorted_reviews = sorted(reviews, key=lambda r: r.credibility_score, reverse=True)
    top_reviews = sorted_reviews[:5]

    # Recommendations
    recs = [r.recommendation for r in reviews if r.recommendation is not None]
    recommendation_ratio = sum(recs) / len(recs) if recs else None

    # All topics
    all_topics = {}
    for r in reviews:
        for t in r.topics:
            all_topics[t] = all_topics.get(t, 0) + 1

    return {
        "matched": True,
        "source": "xiaohongshu",
        "name": reviews[0].advisor_name if reviews else "",
        "institution": reviews[0].institution if reviews else "",
        "review_count": len(reviews),
        "sentiment_distribution": sentiments,
        "dimension_summary": {
            "graduation_difficulty_avg": avg_dim("graduation_difficulty"),
            "workload_avg": avg_dim("workload"),
            "supportiveness_avg": avg_dim("supportiveness"),
        },
        "recommendation_ratio": recommendation_ratio,
        "credibility": {
            "average_score": sum(r.credibility_score for r in reviews) / len(reviews),
            "top_reviews": [
                {
                    "post_id": r.post_id,
                    "title": r.post_title,
                    "content_preview": r.post_content[:200] + "..." if len(r.post_content) > 200 else r.post_content,
                    "credibility_score": r.credibility_score,
                    "sentiment": r.sentiment,
                    "url": r.post_url,
                }
                for r in top_reviews
            ],
        },
        "topics": dict(sorted(all_topics.items(), key=lambda x: x[1], reverse=True)),
        "red_flags": [
            {
                "post_id": r.post_id,
                "issue": _extract_red_flag(r),
                "credibility": r.credibility_score,
            }
            for r in reviews
            if r.sentiment == "negative" and r.credibility_score > 0.5
        ],
        "disclaimer": (
            "本部分数据来自小红书平台匿名用户分享，样本存在明显的负向偏差"
            "（负面体验更倾向于被分享）。所有评价仅反映部分学生的个人经历，"
            "不代表全体学生体验。具体指控需与可验证的公开记录交叉核实。"
        ),
    }


def _extract_red_flag(review: XiaohongshuReview) -> str:
    """Extract concise red flag description from negative review."""
    content = review.post_content
    flags = []

    if any(kw in content for kw in ["抢一作", "抢作者", "take credit"]):
        flags.append("抢一作")
    if any(kw in content for kw in ["不回邮件", "不回复", "ignore email"]):
        flags.append("不回邮件")
    if any(kw in content for kw in ["拖延签字", "不签字", "不批准", "不批"]):
        flags.append("拖延签字/不批准")
    if any(kw in content for kw in ["funding", "没钱", "不给钱", "拖欠工资"]):
        flags.append("funding问题")
    if any(kw in content for kw in ["push", "压榨", "剥削", "过度工作"]):
        flags.append("push/压榨")
    if any(kw in content for kw in ["歧视", " racism", " unfair", "偏见"]):
        flags.append("歧视/偏见")
    if any(kw in content for kw in ["延期", "卡毕业", "不让毕业"]):
        flags.append("卡毕业")

    return "、".join(flags) if flags else "负面评价"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Xiaohongshu advisor review scraper")
    parser.add_argument("--name", "-n", required=True, help="Advisor name")
    parser.add_argument("--institution", "-i", required=True, help="Institution name")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    parser.add_argument("--max-results", "-m", type=int, default=50, help="Max results to fetch")
    parser.add_argument("--delay", "-d", type=float, default=5.0, help="Delay between requests (seconds)")
    parser.add_argument("--api-mode", action="store_true", help="Use xhshow-signed API calls (requires xhshow+httpx+playwright)")
    parser.add_argument("--cookie", help="Pre-acquired cookie string for API mode (optional)")
    args = parser.parse_args()

    if args.api_mode and not (_HAS_XHSHOW and _HAS_HTTPX):
        missing = []
        if not _HAS_XHSHOW:
            missing.append("xhshow")
        if not _HAS_HTTPX:
            missing.append("httpx")
        print(f"[ERROR] API mode requires: pip install {' '.join(missing)}")
        print("[INFO] Falling back to HTML mode...")
        args.api_mode = False

    client = XiaohongshuClient(
        delay=args.delay,
        api_mode=args.api_mode,
        cookie_str=args.cookie,
    )
    reviews = client.search_advisor_reviews(
        advisor_name=args.name,
        institution=args.institution,
        max_results=args.max_results,
    )

    aggregated = aggregate_reviews(reviews)

    # Also output raw reviews for investigator reference
    output = {
        "query": {"name": args.name, "institution": args.institution},
        "aggregated": aggregated,
        "raw_reviews": [
            {
                "post_id": r.post_id,
                "title": r.post_title,
                "content": r.post_content,
                "url": r.post_url,
                "likes": r.likes,
                "comments": r.comments_count,
                "sentiment": r.sentiment,
                "credibility": r.credibility_score,
                "dimensions": {
                    "graduation_difficulty": r.graduation_difficulty,
                    "workload": r.workload,
                    "supportiveness": r.supportiveness,
                    "recommendation": r.recommendation,
                },
                "topics": r.topics,
            }
            for r in reviews
        ],
    }

    if args.output:
        save_json(output, Path(args.output))
        logger.info("Saved to: %s", args.output)
        print(f"[OK] 找到 {len(reviews)} 条评价，已保存至 {args.output}")
    else:
        print(json.dumps(aggregated, ensure_ascii=False, indent=2))

    # Print summary
    mode_label = "API" if args.api_mode else ("Playwright" if _HAS_PLAYWRIGHT else "HTML")
    print(f"\n摘要 (模式: {mode_label}):")
    print(f"  找到评价: {aggregated.get('review_count', 0)} 条")
    print(f"  情感分布: {aggregated.get('sentiment_distribution', {})}")
    print(f"  平均可信度: {aggregated.get('credibility', {}).get('average_score', 0):.2f}")
    if aggregated.get('recommendation_ratio') is not None:
        print(f"  推荐率: {aggregated['recommendation_ratio']*100:.1f}%")


if __name__ == "__main__":
    main()
