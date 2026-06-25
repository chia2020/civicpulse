from __future__ import annotations

import asyncio
import html
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from defusedxml import ElementTree

from src.config import get_bool_env, get_int_env
from src.geo.hyderabad import extract_known_locality

PUBLISHER_SUFFIX_PATTERN = re.compile(r"\s+-\s+[^-]+$")
REQUEST_TIMEOUT_SECONDS = 8
CRAWLER_TIMEOUT_SECONDS = 12
DEFAULT_TARGET_LIMIT = 8
DEFAULT_ENTRY_LIMIT_PER_TARGET = 8
SCRAPE_TOTAL_TIMEOUT_SECONDS = 45
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "CivicPulse/1.0 Hyderabad civic issue monitor"
    ),
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, text/html",
}

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CrawlTarget:
    url: str
    platform: str


HYDERABAD_QUERIES = (
    "Hyderabad civic issue",
    "Hyderabad GHMC complaint",
    "Hyderabad pothole road damage",
    "Hyderabad bad roads traffic civic",
    "Hyderabad sewage overflow complaint GHMC",
    "Hyderabad drainage problem",
    "Hyderabad nala overflow",
    "Hyderabad water supply disruption",
    "Hyderabad drinking water problem",
    "Hyderabad water leakage",
    "Hyderabad street light outage",
    "Hyderabad power cut civic issue",
    "Hyderabad garbage collection issue GHMC",
    "Hyderabad waste dumping",
    "Hyderabad waterlogging monsoon drain",
    "Hyderabad flood prone areas",
    "Hyderabad road repair complaint",
    "Hyderabad public safety traffic issue",
    "Hyderabad encroachment civic issue",
    "Hyderabad lake pollution",
    "Hyderabad footpath encroachment",
    "Hyderabad construction debris",
)

CIVIC_KEYWORDS = (
    "pothole",
    "road",
    "sewage",
    "sewer",
    "drain",
    "drainage",
    "garbage",
    "waste",
    "waterlogging",
    "water supply",
    "drinking water",
    "street light",
    "streetlight",
    "traffic",
    "manhole",
    "ghmc",
    "hmwssb",
    "power cut",
    "electricity",
    "outage",
    "pollution",
    "lake",
    "footpath",
    "encroachment",
    "debris",
    "flood",
    "flooding",
    "nala",
    "civic",
    "complaint",
    "public safety",
)

GRIEVANCE_KEYWORDS = (
    "accident fears",
    "choke",
    "crisis",
    "damage",
    "dark",
    "disrupt",
    "dump",
    "failure",
    "flood",
    "garbage",
    "hotspot",
    "issue",
    "leakage",
    "overflow",
    "pothole",
    "sewage",
    "struggles",
    "waste pile",
    "waterlogging",
    "woes",
    "problem",
    "problems",
    "complaint",
    "complaints",
    "concern",
    "concerns",
    "shortage",
    "contamination",
    "pollution",
    "delay",
    "delayed",
    "repair",
    "repairs",
    "restoration",
    "maintenance",
    "encroachment",
    "debris",
    "overflowing",
    "stagnant",
    "disrupted",
    "disruption",
    "outage",
)

EXCLUDED_TOPICS = (
    "arrest",
    "blazing through",
    "go-kart",
    "praises hyderabad roads",
    "promises",
    "roadmap",
    "traffic-free",
    "election",
    "campaign",
    "manifesto",
    "stock market",
    "movie",
    "cricket",
    "celebrity",
)

SCOPE_NOISE_TERMS = (
    "hyderabad mail",
    "hyderabad news",
)

CATEGORY_KEYWORDS = {
    "Drainage": ("sewage", "sewer", "drain", "drainage", "manhole", "nala"),
    "Roads": ("pothole", "road", "repair", "flyover", "debris"),
    "Water": (
        "water supply",
        "drinking water",
        "low pressure",
        "water leakage",
        "hmwssb",
    ),
    "Sanitation": ("garbage", "waste", "sanitation", "trash"),
    "Street Lighting": ("street light", "streetlight", "lighting outage"),
    "Power": ("power cut", "electricity", "power outage"),
    "Traffic & Public Safety": ("traffic", "accident", "unsafe", "public safety"),
    "Urban Infrastructure": (
        "footpath",
        "encroachment",
        "flood",
        "waterlogging",
        "lake",
        "pollution",
    ),
}


def build_default_targets(limit: int | None = None) -> list[CrawlTarget]:
    target_limit = (
        limit
        if limit is not None
        else get_int_env(
            "CIVICPULSE_SCRAPE_TARGET_LIMIT",
            DEFAULT_TARGET_LIMIT,
        )
    )
    queries = HYDERABAD_QUERIES[: max(target_limit, 1)]
    return [
        CrawlTarget(
            url=(
                "https://news.google.com/rss/search?q="
                f"{quote(query + ' when:90d')}"
                "&hl=en-IN&gl=IN&ceid=IN:en"
            ),
            platform="google_news",
        )
        for query in queries
    ]


def _platform_from_url(url: str) -> str:
    hostname = urlparse(url).hostname or ""
    if "reddit.com" in hostname:
        return "reddit"
    if "news.google.com" in hostname:
        return "google_news"
    if "thehindu.com" in hostname or "telanganatoday.com" in hostname:
        return "news"
    return "web"


def _is_feed_url(url: str) -> bool:
    parsed = urlparse(url)
    return any(
        marker in parsed.path.lower() or marker in parsed.query.lower()
        for marker in ("rss", "atom", "feed", "xml")
    )


def _fetch_text_direct(url: str, timeout_seconds: int = REQUEST_TIMEOUT_SECONDS) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return ""

    request = Request(url, headers=HTTP_HEADERS)  # noqa: S310
    try:
        # URL scheme is limited to http/https above.
        # nosemgrep
        with urlopen(  # noqa: S310  # nosec B310
            request,
            timeout=timeout_seconds,
        ) as response:
            raw_body = response.read()
            content_type = response.headers.get_content_charset() or "utf-8"
    except (OSError, URLError):
        return ""

    return str(raw_body.decode(content_type, errors="replace"))


def _strip_markup(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _strip_publisher_suffix(title: str) -> str:
    return PUBLISHER_SUFFIX_PATTERN.sub("", title).strip()


def _parse_date(value: str | None) -> str:
    if not value:
        return date.today().isoformat()
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.date().isoformat()
    except (TypeError, ValueError):
        pass

    for date_format in ("%Y-%m-%d", "%d %b %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(value, date_format).date().isoformat()
        except ValueError:
            continue
    return date.today().isoformat()


async def _fetch_text_async(url: str, retries: int = 1, delay_seconds: float = 1.0) -> str:
    if _is_feed_url(url):
        try:
            direct_content = await asyncio.wait_for(
                asyncio.to_thread(_fetch_text_direct, url),
                timeout=REQUEST_TIMEOUT_SECONDS + 2,
            )
        except asyncio.TimeoutError:
            logger.warning("Timed out fetching feed: %s", url)
            direct_content = ""
        if direct_content:
            return direct_content

    try:
        from crawl4ai import AsyncWebCrawler
    except ImportError:
        return ""

    for attempt in range(1, retries + 1):
        try:
            async with AsyncWebCrawler(verbose=False) as crawler:
                result = await asyncio.wait_for(
                    crawler.arun(url=url, bypass_cache=True),
                    timeout=CRAWLER_TIMEOUT_SECONDS,
                )
                if result and result.html:
                    return str(result.html)
                if result and result.markdown:
                    return str(result.markdown)
                return ""
        except (asyncio.TimeoutError, Exception):
            if attempt == retries:
                logger.warning("Crawler failed for %s after %s attempt(s)", url, attempt)
                return ""
            await asyncio.sleep(delay_seconds * (2 ** (attempt - 1)))
    return ""


def _find_text(element: ElementTree.Element, *names: str) -> str:
    for name in names:
        found = element.find(name)
        if found is not None and found.text:
            return _strip_markup(found.text)
    return ""


def _parse_rss(xml_text: str) -> list[dict[str, str]]:
    if not xml_text:
        return []
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return []

    entries: list[dict[str, str]] = []
    for item in root.findall(".//item"):
        entries.append(
            {
                "title": _find_text(item, "title"),
                "description": _find_text(item, "description"),
                "link": _find_text(item, "link"),
                "published": _find_text(item, "pubDate"),
            }
        )

    if entries:
        return entries

    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in root.findall(".//atom:entry", namespace):
        link = ""
        link_element = entry.find("atom:link", namespace)
        if link_element is not None:
            link = link_element.attrib.get("href") or ""
        entries.append(
            {
                "title": _find_text(entry, "{http://www.w3.org/2005/Atom}title"),
                "description": _find_text(entry, "{http://www.w3.org/2005/Atom}summary"),
                "link": link,
                "published": _find_text(
                    entry,
                    "{http://www.w3.org/2005/Atom}published",
                    "{http://www.w3.org/2005/Atom}updated",
                ),
            }
        )
    return entries


def _is_hyderabad_civic_item(title: str, description: str) -> bool:
    text = f"{title} {description}".lower()
    scope_text = text
    for noise_term in SCOPE_NOISE_TERMS:
        scope_text = scope_text.replace(noise_term, "")
    if "hyderabad" not in scope_text:
        return False
    if any(topic in text for topic in EXCLUDED_TOPICS):
        return False
    return any(keyword in text for keyword in CIVIC_KEYWORDS)


GEMINI_SEMAPHORE = asyncio.Semaphore(2)
_GEMINI_DISABLED = False


async def _extract_area(title: str, description: str) -> str:
    global _GEMINI_DISABLED

    text = f"{title} {description}"
    if not _GEMINI_DISABLED and get_bool_env("CIVICPULSE_USE_GEMINI_LOCALITY", False):
        from src.geo.ai_location import ainfer_hyderabad_locality

        async with GEMINI_SEMAPHORE:
            try:
                inferred = await ainfer_hyderabad_locality(text, timeout_seconds=5)
            except Exception as error:
                _GEMINI_DISABLED = True
                logger.warning(
                    "Disabling Gemini locality inference for this scrape: %s",
                    error,
                )
                inferred = None
        if inferred:
            return inferred

    landmark = extract_known_locality(text)
    if landmark:
        return landmark.title()

    return "Hyderabad"


def _classify_category(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return category
    return "Uncategorized"


def _score_issue(
    category: str,
    title: str,
    description: str,
    post_date: str,
) -> dict[str, float]:
    text = f"{title} {description}".lower()
    severity = 5.0
    safety_terms = ("danger", "accident", "death", "injured", "unsafe", "open manhole")
    if any(word in text for word in safety_terms):
        severity = 8.5
    elif category in {"Drainage", "Roads", "Water"}:
        severity = 7.0
    elif category in {"Sanitation", "Street Lighting"}:
        severity = 6.0

    repeated_terms = ("residents", "several", "multiple", "again")
    frequency = 6.5 if any(word in text for word in repeated_terms) else 4.5

    monsoon_terms = ("monsoon", "rain", "waterlogging")
    risk = 7.8 if category == "Drainage" and any(word in text for word in monsoon_terms) else 5.5
    try:
        age_days = max(0, (date.today() - datetime.strptime(post_date, "%Y-%m-%d").date()).days)
    except ValueError:
        age_days = 0
    duration = min(age_days / 30 * 10, 10)
    return {"S": severity, "F": frequency, "R": risk, "D": round(duration, 2)}


async def _entry_to_issue(entry: dict[str, str], platform: str) -> dict[str, Any] | None:
    title = _strip_publisher_suffix(entry["title"])
    description = entry["description"] or title
    if not _is_hyderabad_civic_item(title, description):
        return None

    post_date = _parse_date(entry.get("published"))
    category = _classify_category(title, description)
    scores = _score_issue(category, title, description, post_date)
    area = await _extract_area(title, description)
    return {
        "title": title,
        "area": area,
        "category": category,
        "description": description,
        "post_date": post_date,
        "traction_date": post_date,
        "engagement_count": 0,
        "source": platform,
        "source_url": entry.get("link") or "",
        **scores,
    }


async def _scrape_target(target: CrawlTarget) -> list[dict[str, Any]]:
    content = await _fetch_text_async(target.url)
    issues = []
    # Attempt RSS extraction first
    rss_entries = _parse_rss(content)
    if rss_entries:
        entry_limit = get_int_env(
            "CIVICPULSE_SCRAPE_ENTRY_LIMIT_PER_TARGET",
            DEFAULT_ENTRY_LIMIT_PER_TARGET,
        )
        tasks = [
            _entry_to_issue(entry, target.platform) for entry in rss_entries[: max(entry_limit, 1)]
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        issues = [issue for issue in results if isinstance(issue, dict)]
    else:
        # Fallback for dynamic/markdown websites (like fb/ig mapped via crawl4ai)
        # In a complete implementation, an LLM would parse markdown to issues here.
        # For this refactor, we just extract a single generic issue if it matches keywords.
        if content and _is_hyderabad_civic_item(target.url, content):
            entry = {
                "title": f"Civic Issue from {target.platform}",
                "description": content[:500] + "...",
                "link": target.url,
                "published": date.today().isoformat(),
            }
            issue = await _entry_to_issue(entry, target.platform)
            if issue:
                issues.append(issue)

    return issues


async def scrape_civic_sources_deep(urls: list[str] | None = None) -> list[dict[str, Any]]:
    targets = (
        [CrawlTarget(url=url, platform=_platform_from_url(url)) for url in urls]
        if urls
        else build_default_targets()
    )

    semaphore = asyncio.Semaphore(4)

    async def bounded_scrape(target: CrawlTarget) -> list[dict[str, Any]]:
        async with semaphore:
            try:
                return await _scrape_target(target)
            except Exception as error:
                logger.warning("Skipping failed scrape target %s: %s", target.url, error)
                return []

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*(bounded_scrape(target) for target in targets)),
            timeout=get_int_env(
                "CIVICPULSE_SCRAPE_TOTAL_TIMEOUT_SECONDS",
                SCRAPE_TOTAL_TIMEOUT_SECONDS,
            ),
        )
    except asyncio.TimeoutError:
        logger.warning("Live scrape timed out before all targets completed")
        results = []

    deduped: dict[str, dict[str, Any]] = {}
    for records in results:
        for record in records:
            key = str(record.get("source_url") or "").lower()
            if not key:
                key = "|".join(
                    [
                        str(record.get("title", "")).lower(),
                        str(record.get("post_date", "")),
                        str(record.get("source", "")).lower(),
                    ]
                )
            deduped[key] = record
    return list(deduped.values())
