from __future__ import annotations

import argparse
import asyncio
from datetime import date
from uuid import uuid5, NAMESPACE_URL

import pandas as pd

from src.core.scoring import calculate_impact_score
from src.data.sample_issues import build_sample_issues
from src.geo.hyderabad import resolve_locality
from src.storage.vector_store import CivicVectorStore


def normalize_issue(raw_issue: dict[str, object]) -> dict[str, object]:
    area = str(raw_issue.get("area") or raw_issue.get("location") or "Hyderabad")
    locality = resolve_locality(area)
    title = str(raw_issue.get("title") or raw_issue.get("raw_complaint_summary") or "Hyderabad civic issue")
    description = str(raw_issue.get("description") or raw_issue.get("raw_complaint_summary") or title)
    post_date = str(raw_issue.get("post_date") or date.today().isoformat())
    traction_date = str(raw_issue.get("traction_date") or post_date)
    source_url = str(raw_issue.get("source_url") or "")
    stable_key = "|".join([title.lower(), area.lower(), post_date, source_url])
    issue_id = str(raw_issue.get("id") or f"HYD-{uuid5(NAMESPACE_URL, stable_key).hex[:10].upper()}")

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
        "engagement_count": int(raw_issue.get("engagement_count") or 0),
        "latitude": locality.latitude,
        "longitude": locality.longitude,
        "S": float(raw_issue.get("S") or raw_issue.get("severity") or 5.0),
        "F": float(raw_issue.get("F") or 5.0),
        "R": float(raw_issue.get("R") or 5.0),
        "D": float(raw_issue.get("D") or 1.0),
        "P": locality.population_density_score,
    }
    issue["impact_score"] = calculate_impact_score(
        float(issue["S"]),
        float(issue["F"]),
        float(issue["R"]),
        float(issue["D"]),
        float(issue["P"]),
    )
    return issue


def seed_sample_data(store: CivicVectorStore | None = None) -> pd.DataFrame:
    vector_store = store or CivicVectorStore()
    issues = [normalize_issue(issue) for issue in build_sample_issues()]
    vector_store.upsert_issues(issues)
    return pd.DataFrame(issues)


def load_issues(query: str | None = None, store: CivicVectorStore | None = None) -> pd.DataFrame:
    vector_store = store or CivicVectorStore()
    if vector_store.count() == 0:
        seed_sample_data(vector_store)
    if query:
        return vector_store.search(query)
    return vector_store.fetch_all()


async def run_live_pipeline(urls: list[str] | None = None) -> pd.DataFrame:
    from src.ingestion.scraper import scrape_civic_sources_deep

    raw_issues = await scrape_civic_sources_deep(urls)
    store = CivicVectorStore()
    if not raw_issues:
        return load_issues(store=store)

    issues = [normalize_issue(issue) for issue in raw_issues]
    store.upsert_issues(issues)
    return pd.DataFrame(issues)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CivicPulse ingestion pipeline.")
    parser.add_argument("--live", action="store_true", help="Use live Crawl4AI + Gemini scraping.")
    parser.add_argument("--url", action="append", default=None, help="Optional URL to scrape. Repeat for more URLs.")
    args = parser.parse_args()

    if args.live:
        frame = asyncio.run(run_live_pipeline(args.url))
        print(f"Stored {len(frame)} live or previously cached issues in the vector database.")
    else:
        frame = seed_sample_data()
        print(f"Seeded {len(frame)} sample issues in storage/civicpulse_vector.db.")


if __name__ == "__main__":
    main()
