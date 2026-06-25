from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pandas as pd

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config import get_bool_env
from src.core.scoring import calculate_impact_score
from src.data.sample_issues import build_sample_issues
from src.geo.ai_location import infer_hyderabad_locality
from src.geo.hyderabad import extract_known_locality, resolve_locality
from src.storage.vector_store import CivicVectorStore


def _to_float(value: object, default: float) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def normalize_issue(raw_issue: dict[str, object]) -> dict[str, object]:
    area = str(raw_issue.get("area") or raw_issue.get("location") or "Hyderabad")
    title = str(
        raw_issue.get("title") or raw_issue.get("raw_complaint_summary") or "Hyderabad civic issue"
    )
    description = str(
        raw_issue.get("description") or raw_issue.get("raw_complaint_summary") or title
    )
    locality = resolve_locality(area)
    text_for_location = " ".join([area, title, description])
    if locality.zone == "Unknown":
        known_area = extract_known_locality(text_for_location)
        if known_area:
            area = known_area
            locality = resolve_locality(known_area)

    if locality.zone == "Unknown" and get_bool_env("CIVICPULSE_USE_GEMINI_LOCALITY", False):
        inferred_area = infer_hyderabad_locality(text_for_location, timeout_seconds=5)
        if inferred_area:
            inferred_locality = resolve_locality(inferred_area)
            if inferred_locality.zone != "Unknown":
                area = inferred_area
                locality = inferred_locality
    post_date = str(raw_issue.get("post_date") or date.today().isoformat())
    traction_date = str(raw_issue.get("traction_date") or post_date)
    source_url = str(raw_issue.get("source_url") or "")
    stable_key = source_url or "|".join(
        [
            title.lower().strip(),
            post_date,
            str(raw_issue.get("source") or raw_issue.get("source_platform") or "unknown"),
        ]
    )
    issue_id = str(
        raw_issue.get("id") or f"HYD-{uuid5(NAMESPACE_URL, stable_key).hex[:10].upper()}"
    )

    issue = {
        "id": issue_id,
        "title": title,
        "area": area,
        "zone": locality.zone,
        "category": str(raw_issue.get("category") or "Uncategorized"),
        "description": description,
        "source": str(raw_issue.get("source") or raw_issue.get("source_platform") or "unknown"),
        "source_url": source_url,
        "post_date": post_date,
        "traction_date": traction_date,
        "engagement_count": _to_int(raw_issue.get("engagement_count"), 0),
        "latitude": locality.latitude,
        "longitude": locality.longitude,
        "S": _to_float(raw_issue.get("S") or raw_issue.get("severity"), 5.0),
        "F": _to_float(raw_issue.get("F"), 5.0),
        "R": _to_float(raw_issue.get("R"), 5.0),
        "D": _to_float(raw_issue.get("D"), 1.0),
        "P": locality.population_density_score,
    }
    issue["impact_score"] = calculate_impact_score(
        _to_float(issue["S"], 5.0),
        _to_float(issue["F"], 5.0),
        _to_float(issue["R"], 5.0),
        _to_float(issue["D"], 1.0),
        _to_float(issue["P"], 5.0),
    )
    return issue


def seed_sample_data(store: CivicVectorStore | None = None) -> pd.DataFrame:
    vector_store = store or CivicVectorStore()
    issues = [normalize_issue(issue) for issue in build_sample_issues()]
    vector_store.upsert_issues(issues)
    return pd.DataFrame(issues)


def load_issues(
    query: str | None = None,
    store: CivicVectorStore | None = None,
    seed_if_empty: bool = False,
) -> pd.DataFrame:
    vector_store = store or CivicVectorStore()
    if seed_if_empty and vector_store.count() == 0:
        seed_sample_data(vector_store)
    normalized_query = query.strip() if query else None
    if normalized_query:
        return vector_store.search(normalized_query)
    return vector_store.fetch_all()


async def run_live_pipeline(
    urls: list[str] | None = None,
    replace_existing: bool = True,
) -> pd.DataFrame:
    import time

    from src.ingestion.scraper import scrape_civic_sources_deep

    start_time = time.time()
    raw_issues = await scrape_civic_sources_deep(urls)
    scrape_time = time.time() - start_time

    store = CivicVectorStore()
    if not raw_issues:
        return pd.DataFrame()

    process_start = time.time()
    issues = [normalize_issue(issue) for issue in raw_issues]
    process_time = time.time() - process_start

    if replace_existing:
        store.clear()
    store.upsert_issues(issues)

    total_time = time.time() - start_time
    print(
        f"Pipeline: Scraped in {scrape_time:.2f}s, processed {len(issues)} issues "
        f"in {process_time:.2f}s. Total: {total_time:.2f}s"
    )

    return pd.DataFrame(issues)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CivicPulse ingestion pipeline.")
    parser.add_argument("--live", action="store_true", help="Use live RSS/news scraping.")
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append live records instead of replacing the dashboard dataset.",
    )
    parser.add_argument(
        "--url",
        action="append",
        default=None,
        help="Optional URL to scrape. Repeat for more URLs.",
    )
    args = parser.parse_args()

    if args.live:
        frame = asyncio.run(run_live_pipeline(args.url, replace_existing=not args.append))
        print(f"Stored {len(frame)} live issues in Supabase.")
    else:
        frame = seed_sample_data()
        print(f"Seeded {len(frame)} sample issues in Supabase.")


if __name__ == "__main__":
    main()
