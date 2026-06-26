"""
src/core/enrichment.py
──────────────────────
Retroactive data-enrichment pipeline for pre-existing CivicPulse records.

Responsibility:
  • Scan the Supabase store for records whose GHMC zone is still "Unknown"
    (i.e. the initial geocoding pipeline couldn't resolve the locality).
  • For each such record, use the LLM inference layer (Ollama or Gemini, via
    ai_location.infer_hyderabad_locality) to derive a Hyderabad locality from
    the issue title + description.
  • Resolve the inferred locality to a GHMC zone and update the record in-place
    using CivicVectorStore.patch_issue().
  • Recompute impact_score with the updated population density if the zone
    changed from Unknown.

Usage (manual run):
    python -m src.core.enrichment

Or trigger from app.py / pipeline after a refresh.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.config import load_environment
from src.core.scoring import calculate_impact_score
from src.geo.ai_location import infer_hyderabad_locality
from src.geo.hyderabad import UNKNOWN_LOCALITY, extract_known_locality, resolve_locality
from src.storage.vector_store import CivicVectorStore

LOGGER = logging.getLogger(__name__)


def _to_float(value: object, default: float) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def enrich_missing_locations(
    store: CivicVectorStore | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Scan for Unknown-zone records and attempt to resolve them via LLM.

    Parameters
    ----------
    store:
        A ``CivicVectorStore`` instance to use. Created from environment if None.
    dry_run:
        If True, perform inference but do NOT write back to the store.

    Returns
    -------
    A summary dict with keys ``checked``, ``updated``, ``failed``.
    """
    load_environment()
    store = store or CivicVectorStore()
    summary: dict[str, int] = {"checked": 0, "updated": 0, "failed": 0}

    try:
        unknown_df = store.fetch_unknown_zone_records()
    except Exception as exc:
        LOGGER.error("Could not fetch unknown-zone records: %s", exc)
        return summary

    if unknown_df.empty:
        LOGGER.info("No Unknown-zone records found – nothing to enrich.")
        return summary

    summary["checked"] = len(unknown_df)
    LOGGER.info("Enrichment: %d records with Unknown zone found.", len(unknown_df))

    for _, row in unknown_df.iterrows():
        issue_id = str(row.get("id", ""))
        if not issue_id:
            summary["failed"] += 1
            continue

        title = str(row.get("title") or "")
        description = str(row.get("description") or "")
        area = str(row.get("area") or "")
        combined_text = " ".join(filter(None, [area, title, description]))

        # Step 1: try regex-based extraction first (free, instant)
        new_area: str | None = extract_known_locality(combined_text)

        # Step 2: fall back to LLM
        if not new_area:
            new_area = infer_hyderabad_locality(combined_text, timeout_seconds=8)

        if not new_area:
            LOGGER.debug("Enrichment: could not resolve locality for id=%s", issue_id)
            summary["failed"] += 1
            continue

        locality = resolve_locality(new_area)
        if locality.zone == "Unknown":
            LOGGER.debug(
                "Enrichment: resolved '%s' for id=%s but zone is still Unknown.",
                new_area,
                issue_id,
            )
            summary["failed"] += 1
            continue

        # Recompute impact score with the correct population density
        S = _to_float(row.get("S"), 5.0)
        F = _to_float(row.get("F"), 5.0)
        R = _to_float(row.get("R"), 5.0)
        D = _to_float(row.get("D"), 1.0)
        P = locality.population_density_score
        new_score = calculate_impact_score(S, F, R, D, P)

        updates: dict[str, Any] = {
            "area": new_area,
            "zone": locality.zone,
            "latitude": locality.latitude,
            "longitude": locality.longitude,
            "P": P,
            "impact_score": new_score,
        }

        LOGGER.info(
            "Enrichment: id=%s → zone=%s score=%.2f (was Unknown)",
            issue_id,
            locality.zone,
            new_score,
        )

        if not dry_run:
            try:
                store.patch_issue(issue_id, updates)
                summary["updated"] += 1
            except Exception as exc:
                LOGGER.error("patch_issue failed for id=%s: %s", issue_id, exc)
                summary["failed"] += 1
        else:
            summary["updated"] += 1

    LOGGER.info(
        "Enrichment complete: checked=%d updated=%d failed=%d",
        summary["checked"],
        summary["updated"],
        summary["failed"],
    )
    return summary


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s – %(message)s")
    parser = argparse.ArgumentParser(description="Enrich CivicPulse Unknown-zone records.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Infer locations but do not write back to the database.",
    )
    args = parser.parse_args()
    result = enrich_missing_locations(dry_run=args.dry_run)
    print(result)
