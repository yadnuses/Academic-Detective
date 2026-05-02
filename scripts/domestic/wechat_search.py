#!/usr/bin/env python3
"""
WeChat article search for academic investigation.
Searches Sogou WeChat, resolves real mp.weixin.qq.com URLs via Playwright+camoufox,
and fetches article text via direct HTTP (no images downloaded).

Intended as a supplementary search channel. WeChat articles may contain rumors,
gossip, and unverified claims. Treat findings as leads requiring corroboration.

Usage:
    # If camoufox/playwright are available in the current Python environment:
    python scripts/wechat_search.py --keyword "学者姓名" --limit 10

    # If camoufox is only installed via wechat-article-to-markdown uv tool:
    uv tool run --from wechat-article-to-markdown python scripts/wechat_search.py \
        --keyword "学者姓名" --limit 10 --output ./data/wechat_articles
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


def sogou_search(keyword: str, max_results: int = 5) -> list[dict]:
    """Fetch Sogou WeChat search results via HTTP."""
    import html as html_lib
    import requests

    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
    }
    url = f'https://weixin.sogou.com/weixin?type=2&query={quote(keyword)}'
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    text = resp.text

    results = []
    blocks = re.findall(r'<div class="txt-box">(.*?)</div>\s*</div>', text, re.DOTALL)
    for block in blocks[:max_results]:
        title_match = re.search(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', block, re.DOTALL)
        if not title_match:
            continue
        article_url = title_match.group(1).replace('&amp;', '&')
        raw_title = title_match.group(2)
        title = re.sub(r'<[^>]+>', '', raw_title).strip()
        title = html_lib.unescape(title)
        author_match = re.search(r'<a[^>]*class="account"[^>]*>(.*?)</a>', block, re.DOTALL)
        author = re.sub(r'<[^>]+>', '', author_match.group(1)).strip() if author_match else ''
        snippet_match = re.search(r'<p class="txt-info">(.*?)</p>', block, re.DOTALL)
        snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip() if snippet_match else ''
        snippet = html_lib.unescape(snippet)
        date_match = re.search(r"document\.write\(timeConvert\('(\d+)'\)\)", block)
        date = datetime.fromtimestamp(int(date_match.group(1))).strftime('%Y-%m-%d') if date_match else ''
        if article_url.startswith('/link'):
            article_url = 'https://weixin.sogou.com' + article_url
        results.append({'title': title, 'url': article_url, 'author': author, 'snippet': snippet, 'date': date})
    return results


def resolve_real_urls(results: list[dict], keyword: str) -> list[dict]:
    """Click through Sogou search results page to capture real mp.weixin.qq.com URLs."""
    try:
        from playwright.sync_api import sync_playwright
        from camoufox.utils import launch_options
    except ImportError as e:
        print(f"[ERROR] Playwright or camoufox not available: {e}", file=sys.stderr)
        print("[HINT] If you installed wechat-article-to-markdown via uv, run:", file=sys.stderr)
        print("  uv tool run --from wechat-article-to-markdown python scripts/wechat_search.py ...", file=sys.stderr)
        return results

    opts = launch_options()
    search_url = f'https://weixin.sogou.com/weixin?type=2&query={quote(keyword)}'
    with sync_playwright() as p:
        browser = p.firefox.launch(**opts)
        page = browser.new_page()
        page.goto(search_url, timeout=30000, wait_until='networkidle')
        page.wait_for_timeout(2000)

        for r in results:
            try:
                safe_title = r['title'].replace('"', '\\"')
                link = page.locator(f'.txt-box h3 a:has-text("{safe_title}")')
                if link.count() == 0:
                    continue
                with page.expect_popup(timeout=30000) as popup_info:
                    link.first.click()
                popup = popup_info.value
                popup.wait_for_load_state('networkidle', timeout=30000)
                popup.wait_for_timeout(2000)
                real_url = popup.url
                if 'mp.weixin.qq.com' in real_url:
                    r['resolved_url'] = real_url
                popup.close()
                page.wait_for_timeout(1000)
            except Exception as e:
                r['resolve_error'] = str(e)
                continue
        browser.close()
    return results


def fetch_wechat_text(url: str) -> dict:
    """Fetch WeChat article text via direct HTTP (no images, no browser)."""
    req = Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    })
    with urlopen(req, timeout=15) as resp:
        html = resp.read().decode('utf-8', errors='replace')

    title = ""
    author = ""
    account = ""
    published_at = ""
    content = ""

    m = re.search(r'<meta\s+property="og:title"\s+content="([^"]*)"', html)
    if m:
        title = _unescape_html(m.group(1))
    if not title:
        m = re.search(r'<h1[^>]*class="rich_media_title"[^>]*>(.*?)</h1>', html, re.DOTALL)
        if m:
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()

    m = re.search(r'<meta\s+name="author"\s+content="([^"]*)"', html)
    if m:
        author = _unescape_html(m.group(1))

    m = re.search(r'var\s+nickname\s*=\s*["\']([^"\']+)["\']', html)
    if m:
        account = m.group(1)
    if not account:
        m = re.search(r'<a[^>]*id="js_name"[^>]*>(.*?)</a>', html, re.DOTALL)
        if m:
            account = re.sub(r'<[^>]+>', '', m.group(1)).strip()

    m = re.search(r'var\s+ct\s*=\s*["\'](\d+)["\']', html)
    if m:
        ts = int(m.group(1))
        dt = datetime.fromtimestamp(ts)
        published_at = dt.strftime('%Y-%m-%d %H:%M:%S')

    m = re.search(r'<div[^>]*class="rich_media_content[^"]*"[^>]*>(.*?)</div>\s*(?:<div|<script)', html, re.DOTALL)
    if m:
        raw = m.group(1)
        raw = re.sub(r'<br\s*/?>', '\n', raw)
        raw = re.sub(r'</p>', '\n', raw)
        raw = re.sub(r'<[^>]+>', '', raw)
        raw = re.sub(r'&nbsp;', ' ', raw)
        raw = _unescape_html(raw)
        lines = [line.strip() for line in raw.split('\n') if line.strip()]
        content = '\n'.join(lines)

    return {
        'url': url,
        'title': title,
        'author': author or account or '未知公众号',
        'account': account,
        'published_at': published_at,
        'content': content,
    }


def _unescape_html(text: str) -> str:
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    text = text.replace('&nbsp;', ' ')
    return text


def save_article_markdown(article: dict, output_dir: Path) -> Path:
    """Save fetched article as a single Markdown file (no images)."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_title = re.sub(r'[/\\?%*:|"<>]', '_', article.get('title', 'article'))[:80]
    md_path = output_dir / f"{safe_title}.md"
    if md_path.exists():
        base = md_path.stem
        suffix = md_path.suffix
        for idx in range(1, 100):
            candidate = output_dir / f"{base}_{idx}{suffix}"
            if not candidate.exists():
                md_path = candidate
                break

    lines = [
        '---',
        f"platform: weixin",
        f"url: {article.get('url', '')}",
        f'title: "{article.get("title", "").replace(chr(34), chr(92)+chr(34))}"',
        f'author: "{article.get("author", "").replace(chr(34), chr(92)+chr(34))}"',
        f'account: "{article.get("account", "").replace(chr(34), chr(92)+chr(34))}"',
        f"published_at: \"{article.get('published_at', '')}\"",
        f"fetched_at: \"{datetime.now().isoformat()}\"",
        'availability: full',
        '---',
        '',
    ]
    if article.get('title'):
        lines.append(f"# {article['title']}\n")
    if article.get('content'):
        lines.append(article['content'])

    md_path.write_text('\n'.join(lines), encoding='utf-8')
    return md_path


def main():
    parser = argparse.ArgumentParser(description="Search and fetch WeChat articles for investigation")
    parser.add_argument('--keyword', '-k', required=True, help='Search keyword (e.g., scholar name)')
    parser.add_argument('--limit', '-l', type=int, default=10, help='Max results to resolve')
    parser.add_argument('--download', '-d', action='store_true', help='Fetch article text and save as Markdown')
    parser.add_argument('--output', '-o', default='./data/wechat_articles', help='Output directory')
    parser.add_argument('--json', '-j', action='store_true', help='Output JSON summary to stdout')
    parser.add_argument('--skip-resolve', action='store_true', help='Skip URL resolution (faster, but returns Sogou intermediate links)')
    args = parser.parse_args()

    print(f"[INFO] Searching Sogou for: {args.keyword}")
    results = sogou_search(args.keyword, args.limit)
    if not results:
        print("[WARN] No results found.")
        sys.exit(1)

    if not args.skip_resolve:
        print(f"[INFO] Resolving {len(results)} links via Playwright + camoufox...")
        results = resolve_real_urls(results, args.keyword)

    downloaded = []
    if args.download:
        for r in results:
            url = r.get('resolved_url') if not args.skip_resolve else r.get('url')
            if url and 'mp.weixin.qq.com' in url:
                try:
                    article = fetch_wechat_text(url)
                    md_path = save_article_markdown(article, Path(args.output))
                    r['downloaded_to'] = str(md_path)
                    downloaded.append(md_path)
                except Exception as e:
                    r['fetch_error'] = str(e)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for i, r in enumerate(results, 1):
            print(f"\n{i}. {r['title']}")
            print(f"   Date: {r.get('date', '')}")
            if 'resolved_url' in r:
                print(f"   URL:  {r['resolved_url']}")
            elif 'resolve_error' in r:
                print(f"   Error: {r['resolve_error']}")
            else:
                print(f"   URL:  {r['url']}")
            if 'downloaded_to' in r:
                print(f"   Saved: {r['downloaded_to']}")
        print(f"\n[INFO] Resolved: {sum(1 for r in results if 'resolved_url' in r)}/{len(results)}")
        if args.download:
            print(f"[INFO] Downloaded: {len(downloaded)}/{len(results)}")
            print(f"[INFO] Output: {args.output}")

    sys.exit(0)


if __name__ == '__main__':
    main()
