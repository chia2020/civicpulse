import pathlib

p = pathlib.Path('c:/Users/chait/OneDrive/Desktop/acaddocs/practice_school/ps1_project/ps1-bits-pilani/civicpulse/src/ingestion/scraper.py')
text = p.read_text('utf-8')

# Replace _fetch_text
target_fetch = """def _fetch_text(url: str, retries: int = 3, delay_seconds: float = 1.5) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
            "Accept-Language": "en-IN,en;q=0.9",
        },
    )
    for attempt in range(1, retries + 1):
        try:
            with urlopen(request, timeout=20) as response:
                return response.read().decode("utf-8", errors="replace")
        except (OSError, URLError):
            if attempt == retries:
                return ""
            time.sleep(delay_seconds * attempt)
    return ""
"""

replacement_fetch = """async def _fetch_text_async(url: str, retries: int = 3, delay_seconds: float = 1.5) -> str:
    from crawl4ai import AsyncWebCrawler
    for attempt in range(1, retries + 1):
        try:
            async with AsyncWebCrawler(verbose=False) as crawler:
                result = await crawler.arun(url=url, bypass_cache=True)
                if result and result.html:
                    return result.html
                if result and result.markdown:
                    return result.markdown
                return ""
        except Exception:
            if attempt == retries:
                return ""
            import asyncio
            await asyncio.sleep(delay_seconds * (2 ** (attempt - 1)))
    return ""
"""

if target_fetch in text:
    text = text.replace(target_fetch, replacement_fetch)
else:
    # Try normalizing newlines
    target_fetch = target_fetch.replace("\n", "\r\n")
    replacement_fetch = replacement_fetch.replace("\n", "\r\n")
    if target_fetch in text:
        text = text.replace(target_fetch, replacement_fetch)
    else:
        print("Target fetch not found")


target_scrape = """async def _scrape_target(target: CrawlTarget) -> list[dict[str, Any]]:
    xml_text = await asyncio.to_thread(_fetch_text, target.url)
    issues = []
    for entry in _parse_rss(xml_text):
        issue = _entry_to_issue(entry, target.platform)
        if issue:
            issues.append(issue)
    return issues"""

replacement_scrape = """async def _scrape_target(target: CrawlTarget) -> list[dict[str, Any]]:
    xml_text = await _fetch_text_async(target.url)
    issues = []
    for entry in _parse_rss(xml_text):
        issue = _entry_to_issue(entry, target.platform)
        if issue:
            issues.append(issue)
    return issues"""

if target_scrape in text:
    text = text.replace(target_scrape, replacement_scrape)
else:
    target_scrape = target_scrape.replace("\n", "\r\n")
    replacement_scrape = replacement_scrape.replace("\n", "\r\n")
    if target_scrape in text:
        text = text.replace(target_scrape, replacement_scrape)
    else:
        print("Target scrape not found")

p.write_text(text, 'utf-8')
print("Done")
