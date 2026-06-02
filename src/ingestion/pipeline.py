from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL

import pandas as pd

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core.scoring import calculate_impact_score
from src.data.sample_issues import build_sample_issues
from src.geo.ai_location import infer_hyderabad_locality
from src.geo.hyderabad import resolve_locality
from src.storage.vector_store import CivicVectorStore


def normalize_issue(raw_issue: dict[str, object]) -> dict[str, object]:
    area = str(raw_issue.get("area") or raw_issue.get("location") or "Hyderabad")
    title = str(
        raw_issue.get("title")
        or raw_issue.get("raw_complaint_summary")
        or "Hyderabad civic issue"
    )
    description = str(
        raw_issue.get("description")
        or raw_issue.get("raw_complaint_summary")
        or title
    )
    locality = resolve_locality(area)
    if locality.zone == "Unknown":
        text_for_location = " ".join([area, title, description])
        inferred_area = infer_hyderabad_locality(text_for_location)
        if inferred_area:
            inferred_locality = resolve_locality(inferred_area)
            if inferred_locality.zone != "Unknown":
                area = inferred_area
                locality = inferred_locality
    post_date = str(raw_issue.get("post_date") or date.today().isoformat())
    traction_date = str(raw_issue.get("traction_date") or post_date)
    source_url = str(raw_issue.get("source_url") or "")
    stable_key = "|".join([title.lower(), area.lower(), post_date, source_url])
    issue_id = str(
        raw_issue.get("id")
        or f"HYD-{uuid5(NAMESPACE_URL, stable_key).hex[:10].upper()}"
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
    from src.ingestion.scraper import scrape_civic_sources_deep

    raw_issues = await scrape_civic_sources_deep(urls)
    store = CivicVectorStore()
    if not raw_issues:
        return pd.DataFrame()

    issues = [normalize_issue(issue) for issue in raw_issues]
    if replace_existing:
        store.clear()
    store.upsert_issues(issues)
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
