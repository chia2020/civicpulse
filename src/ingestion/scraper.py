from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig
from crawl4ai.async_configs import BrowserConfig
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy, DomainFilter, FilterChain
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from pydantic import BaseModel, Field


class ScrapedCivicIssue(BaseModel):
    title: str = Field(description="Short issue title.")
    area: str = Field(description="Hyderabad locality, landmark, road, colony, or metro station.")
    category: str = Field(description="Roads, Water, Power, Sanitation, Drainage, Street Lighting, or Traffic & Public Safety.")
    description: str = Field(description="Factual civic grievance summary.")
    post_date: str = Field(description="First reported date in YYYY-MM-DD format. Infer conservatively if needed.")
    traction_date: str = Field(description="Date of highest public traction in YYYY-MM-DD format.")
    engagement_count: int = Field(default=0, description="Observed likes, comments, shares, upvotes, or article discussion count.")
    S: float = Field(ge=0, le=10, description="Severity score.")
    F: float = Field(ge=0, le=10, description="Frequency score.")
    R: float = Field(ge=0, le=10, description="Compounding risk score.")
    D: float = Field(ge=0, le=10, description="Duration score.")


@dataclass(frozen=True)
class CrawlTarget:
    url: str
    platform: str


HYDERABAD_QUERIES = (
    "hyderabad pothole civic issue",
    "hyderabad sewage overflow complaint",
    "hyderabad water supply disruption",
    "hyderabad street light outage",
    "hyderabad garbage collection issue",
    "hyderabad waterlogging monsoon drain",
)


def build_default_targets() -> list[CrawlTarget]:
    reddit_targets = [
        CrawlTarget(
            url=f"https://www.reddit.com/r/hyderabad/search/?q={query.replace(' ', '%20')}&restrict_sr=1&sort=new",
            platform="reddit",
        )
        for query in HYDERABAD_QUERIES
    ]
    news_targets = [
        CrawlTarget("https://telanganatoday.com/tag/hyderabad", "news"),
        CrawlTarget("https://www.thehindu.com/news/cities/Hyderabad/", "news"),
    ]
    return [*reddit_targets, *news_targets]


def _platform_from_url(url: str) -> str:
    if "reddit.com" in url:
        return "reddit"
    if "twitter.com" in url or "x.com" in url:
        return "x"
    if "instagram.com" in url:
        return "instagram"
    if "facebook.com" in url:
        return "facebook"
    return "web"


def _parse_extracted_content(content: str) -> list[dict[str, Any]]:
    parsed = json.loads(content)
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        if "items" in parsed and isinstance(parsed["items"], list):
            return parsed["items"]
        for value in parsed.values():
            if isinstance(value, list):
                return value
        return [parsed]
    return []


def _domain_filter(url: str) -> FilterChain:
    hostname = urlparse(url).hostname
    if not hostname:
        return FilterChain()
    return FilterChain([DomainFilter(allowed_domains=[hostname])])


async def _crawl_target(
    crawler: AsyncWebCrawler,
    target: CrawlTarget,
    strategy: LLMExtractionStrategy,
    retries: int,
    delay_seconds: float,
) -> list[dict[str, Any]]:
    scroll_script = """
    (async () => {
        await new Promise(resolve => setTimeout(resolve, 2500));
        const buttons = [...document.querySelectorAll('button, a')]
            .filter(el => /more|load|comments|continue/i.test(el.innerText || ''));
        for (const button of buttons.slice(0, 4)) {
            try { button.click(); } catch (error) {}
            await new Promise(resolve => setTimeout(resolve, 800));
        }
        for (let i = 0; i < 7; i++) {
            window.scrollTo(0, document.body.scrollHeight);
            await new Promise(resolve => setTimeout(resolve, 1200));
        }
    })();
    """
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        js_code=scroll_script,
        extraction_strategy=strategy,
        wait_until="networkidle",
        page_timeout=90000,
        scan_full_page=True,
        max_scroll_steps=10,
        scroll_delay=0.4,
        process_iframes=True,
        remove_overlay_elements=True,
        remove_consent_popups=True,
        simulate_user=True,
        override_navigator=True,
        deep_crawl_strategy=BFSDeepCrawlStrategy(
            max_depth=1,
            max_pages=8,
            filter_chain=_domain_filter(target.url),
            include_external=False,
        ),
    )

    for attempt in range(1, retries + 1):
        try:
            result = await crawler.arun(url=target.url, config=run_config)
            crawl_results = result if isinstance(result, list) else [result]
            records = []
            for crawl_result in crawl_results:
                if crawl_result.success and crawl_result.extracted_content:
                    page_records = _parse_extracted_content(crawl_result.extracted_content)
                    for record in page_records:
                        record["source"] = target.platform
                        record["source_url"] = getattr(crawl_result, "url", target.url)
                        record["scraped_on"] = date.today().isoformat()
                    records.extend(page_records)
            if records:
                return records
            await asyncio.sleep(delay_seconds * attempt)
        except Exception:
            if attempt == retries:
                return []
            await asyncio.sleep(delay_seconds * (2 ** (attempt - 1)))
    return []


async def scrape_civic_sources_deep(urls: list[str] | None = None) -> list[dict[str, Any]]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return []

    targets = (
        [CrawlTarget(url=url, platform=_platform_from_url(url)) for url in urls]
        if urls
        else build_default_targets()
    )
    browser_config = BrowserConfig(
        browser_type="chromium",
        headless=True,
        text_mode=False,
        viewport_width=1440,
        viewport_height=1400,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
        },
    )
    strategy = LLMExtractionStrategy(
        provider="google/gemini-2.5-flash",
        api_key=api_key,
        schema=ScrapedCivicIssue.model_json_schema(),
        instruction=(
            "Extract only concrete civic infrastructure grievances within Hyderabad, Telangana. "
            "Look deeply through visible posts, article cards, comments, replies, timestamps, "
            "and engagement counters. Ignore politics without a civic issue, ads, unrelated cities, "
            "generic navigation, and duplicate summaries. Return an array of unique issues. "
            "Use ISO dates. If a landmark cannot be confidently resolved, keep the area text as written."
        ),
    )

    all_records: list[dict[str, Any]] = []
    semaphore = asyncio.Semaphore(3)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        async def bounded_crawl(target: CrawlTarget) -> list[dict[str, Any]]:
            async with semaphore:
                return await _crawl_target(crawler, target, strategy, retries=3, delay_seconds=2.0)

        results = await asyncio.gather(*(bounded_crawl(target) for target in targets))

    for records in results:
        all_records.extend(records)
    return all_records
