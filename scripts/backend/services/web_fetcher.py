import asyncio
import httpx
import re
from typing import List, Dict

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


async def fetch_url(url: str, max_chars: int = 4000) -> str:
    """获取URL内容，尝试多种绕过策略。"""
    strategies = [
        ("markdown.new", f"https://markdown.new/{url}"),
        ("r.jina.ai", f"https://r.jina.ai/{url}"),
        ("defuddle.md", f"https://defuddle.md/{url}"),
    ]

    # Try direct access first with short timeout
    try:
        async with httpx.AsyncClient(timeout=8, headers={"User-Agent": USER_AGENT}) as client:
            r = await client.get(url)
            if r.status_code == 200:
                text = r.text.strip()
                if len(text) > 200:
                    return text[:max_chars]
    except Exception:
        pass

    # Try prefix strategies
    async with httpx.AsyncClient(
        timeout=15, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    ) as client:
        for name, strategy_url in strategies:
            try:
                r = await client.get(strategy_url)
                if r.status_code == 200:
                    text = r.text.strip()
                    if len(text) > 200:
                        return text[:max_chars]
            except Exception:
                continue

    # Scrapling fallback
    try:
        from scrapling import Fetcher
        page = Fetcher().get(url)
        text = page.get_all_text().strip()
        return text[:max_chars]
    except Exception as e:
        return f"获取失败: {str(e)}"


async def bing_search(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    """用Bing搜索获取结果列表。"""
    try:
        from scrapling import Fetcher
        import urllib.parse
        search_url = "https://www.bing.com/search?q=" + urllib.parse.quote(query)
        page = Fetcher().get(search_url)
        html = page.html_content

        results = []
        algo_blocks = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', html, re.DOTALL)
        for block in algo_blocks[:max_results]:
            # Extract title and URL from <a> tag
            title_match = re.search(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', block, re.DOTALL)
            if title_match:
                url = title_match.group(1)
                title_raw = title_match.group(2)
                # Remove nested tags and domain prefix from title
                title = re.sub(r'<[^>]+>', '', title_raw)
                title = re.sub(r'^\s*\w+\.\w+\s*', '', title)  # Remove leading domain like "zhihu.com"
                # Extract snippet
                snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
                snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)) if snippet_match else ""
                if url.startswith('http') and 'microsoft.com' not in url and 'bing.com' not in url:
                    results.append({"title": title.strip(), "url": url, "snippet": snippet.strip()})
        return results
    except Exception as e:
        return [{"title": "搜索失败", "url": "", "snippet": str(e)}]


async def search_and_fetch(query: str, max_results: int = 2) -> str:
    """搜索关键词并获取前N个结果的内容，返回汇总文本。"""
    results = await bing_search(query, max_results)
    if not results or not results[0].get("url"):
        return f"搜索未返回有效结果。查询: {query}"

    # Fetch content concurrently
    urls = [r["url"] for r in results if r.get("url")]
    tasks = [fetch_url(url, max_chars=3000) for url in urls]
    contents = await asyncio.gather(*tasks, return_exceptions=True)

    output = []
    for i, (url, content) in enumerate(zip(urls, contents)):
        title = results[i]["title"] if i < len(results) else ""
        snippet = results[i]["snippet"] if i < len(results) else ""
        text = content if isinstance(content, str) else str(content)
        output.append(f"---\n来源: {title}\nURL: {url}\n摘要: {snippet[:200]}\n内容:\n{text[:3000]}\n")

    return "\n".join(output)
