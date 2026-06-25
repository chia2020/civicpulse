from __future__ import annotations

import logging
import threading
import time
from html import escape
from typing import Any
from urllib.parse import urlencode

import streamlit as st

from src.core.state import BackgroundJob

# Configure logging to a file to capture errors even if UI goes black
logging.basicConfig(
    filename="civicpulse_debug.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

_CACHED_LOAD_ISSUES = None
GHMC_GRIEVANCE_URL = "https://greenhyderabad.ghmc.gov.in/GrievanceRegistration.aspx"


def _run_ingestion_background() -> None:
    """Background task to run the pipeline."""
    import asyncio

    try:
        logging.info("Background thread: Starting ingestion...")
        from src.ingestion.pipeline import run_live_pipeline

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        start_time = time.time()
        # Non-blocking async run
        frame = loop.run_until_complete(run_live_pipeline(replace_existing=False))
        duration = time.time() - start_time
        logging.info(f"Background thread: Success, added {len(frame)} issues.")
        BackgroundJob.complete(len(frame), duration)
    except Exception as e:
        logging.error(f"Background thread: Failed with error: {str(e)}", exc_info=True)
        BackgroundJob.fail(str(e))


def trigger_background_refresh() -> None:
    if BackgroundJob.get_data()["status"] == "running":
        logging.info("Refresh already running, skipping trigger.")
        return

    logging.info("Triggering background refresh...")
    BackgroundJob.start()
    thread = threading.Thread(target=_run_ingestion_background, daemon=True)
    thread.start()


def render_cloud_database_error(error: Exception) -> None:
    st.error(f"Supabase Connection Error: {str(error)}")
    st.info(
        "Please check your `.env` file for valid SUPABASE_URL and Keys. "
        "The application needs these to fetch and store live civic issues."
    )


def _load_issues_uncached(query: str | None, refresh_version: int = 0):
    from src.ingestion.pipeline import load_issues

    return load_issues(query)


def cached_load_issues(query: str | None, refresh_version: int = 0):
    global _CACHED_LOAD_ISSUES

    if _CACHED_LOAD_ISSUES is None:
        _CACHED_LOAD_ISSUES = st.cache_data(ttl=600)(_load_issues_uncached)
    return _CACHED_LOAD_ISSUES(query, refresh_version)


def load_dashboard_data():
    import pandas as pd

    query = str(st.session_state.get("search_query") or "").strip()
    refresh_version = int(st.session_state.get("applied_refresh_version") or 0)
    frame = cached_load_issues(query or None, refresh_version)
    if frame.empty:
        return frame
    frame["post_date"] = pd.to_datetime(frame["post_date"])
    frame["traction_date"] = pd.to_datetime(frame["traction_date"])
    return frame


def build_ghmc_grievance_url(
    category: str = "",
    landmark: str = "",
    description: str = "",
) -> str:
    query = urlencode(
        {
            "category": category,
            "landmark": landmark,
            "description": description,
        }
    )
    return f"{GHMC_GRIEVANCE_URL}?{query}" if query else GHMC_GRIEVANCE_URL


def render_ghmc_link(label: str, url: str) -> None:
    safe_label = escape(label)
    safe_url = escape(url, quote=True)
    st.markdown(
        (
            f"<a href='{safe_url}' target='_blank' rel='noopener noreferrer' "
            "style='display:inline-block;padding:0.45rem 0.7rem;border-radius:6px;"
            "background:#2D7FF9;color:white;text-decoration:none;font-weight:700;'>"
            f"{safe_label}</a>"
        ),
        unsafe_allow_html=True,
    )


def apply_completed_refresh(job: dict[str, Any]) -> bool:
    version = int(job.get("version") or 0)
    applied_version = int(st.session_state.get("applied_refresh_version") or 0)
    if job.get("status") != "complete" or version <= applied_version:
        return False

    count, duration = job["results"]
    st.session_state["applied_refresh_version"] = version
    st.session_state["last_refresh_notice"] = (count, duration)
    st.cache_data.clear()
    st.session_state["dashboard_df"] = None
    BackgroundJob.reset()
    return True


# Render Helper Functions
def render_issue_map(frame) -> None:
    from src.core.scoring import urgency_colors

    try:
        map_data = frame[["latitude", "longitude", "impact_score"]].copy()
        map_data["color"] = map_data["impact_score"].apply(
            lambda score: urgency_colors(float(score))[0]
        )
        map_data["size"] = map_data["impact_score"].apply(lambda s: max(float(s) * 14, 60))
        st.map(
            map_data,
            latitude="latitude",
            longitude="longitude",
            color="color",
            size="size",
            zoom=10,
            height=400,
        )
    except Exception as e:
        st.warning(f"Map rendering skipped: {e}")


def filter_and_sort_issues(frame):
    left, middle, right, order = st.columns([1, 1, 1.2, 1])

    categories = ["All", *sorted(str(value) for value in frame["category"].dropna().unique())]
    zones = ["All", *sorted(str(value) for value in frame["zone"].dropna().unique())]

    selected_zone = left.selectbox("Location / GHMC Zone", zones)
    selected_category = middle.selectbox("Category", categories)
    sort_label = right.selectbox(
        "Sort Issues By",
        [
            "Impact Score",
            "Location",
            "GHMC Zone",
            "Critical Priority",
            "Post Date",
            "Peak Traction Date",
        ],
    )
    direction = order.selectbox("Direction", ["Descending", "Ascending"])

    filtered = frame.copy()
    if selected_zone != "All":
        filtered = filtered[filtered["zone"] == selected_zone]
    if selected_category != "All":
        filtered = filtered[filtered["category"] == selected_category]

    sort_column = {
        "Impact Score": "impact_score",
        "Location": "area",
        "GHMC Zone": "zone",
        "Critical Priority": "impact_score",
        "Post Date": "post_date",
        "Peak Traction Date": "traction_date",
    }[sort_label]
    return filtered.sort_values(
        by=sort_column,
        ascending=(direction == "Ascending"),
        kind="mergesort",
    )


def render_report_new_issue() -> None:
    with st.expander("Report New Issue", expanded=False):
        category = st.selectbox(
            "Issue Category",
            [
                "Drainage",
                "Roads",
                "Water",
                "Sanitation",
                "Street Lighting",
                "Power",
                "Traffic & Public Safety",
                "Urban Infrastructure",
                "Uncategorized",
            ],
            key="new_issue_category",
        )
        landmark = st.text_input(
            "Location / Landmark",
            placeholder="Example: Kukatpally metro",
            key="new_issue_landmark",
        )
        description = st.text_area(
            "Issue Description",
            placeholder="Describe the civic issue clearly.",
            key="new_issue_description",
        )
        url = build_ghmc_grievance_url(category, landmark, description)
        render_ghmc_link("Open Official GHMC Grievance Portal", url)


def render_prioritized_issue_cards(frame) -> None:
    from src.core.scoring import urgency_colors, urgency_label

    for _, issue in frame.head(50).iterrows():
        color, background = urgency_colors(float(issue["impact_score"]))
        grievance_url = build_ghmc_grievance_url(
            str(issue.get("category") or ""),
            str(issue.get("area") or ""),
            str(issue.get("description") or issue.get("title") or ""),
        )
        with st.container(border=True):
            st.markdown(f"**{issue['title']}**")
            st.markdown(
                f"{issue['category']} near **{issue['area']}** | "
                f"Zone: **{issue.get('zone', 'Unknown')}**"
            )
            description = issue["description"]
            st.write(description[:300] + ("..." if len(description) > 300 else ""))
            st.markdown(
                f"<span style='background:{background};color:{color};"
                "padding:4px 8px;border-radius:6px;font-weight:700;'>"
                f"{float(issue['impact_score']):.2f} - "
                f"{urgency_label(float(issue['impact_score']))}</span>",
                unsafe_allow_html=True,
            )
            st.caption(
                "Post date: "
                f"{issue['post_date'].strftime('%Y-%m-%d')} | "
                "Peak traction: "
                f"{issue['traction_date'].strftime('%Y-%m-%d')} | "
                f"Source: {issue.get('source', 'unknown')}"
            )
            render_ghmc_link("Report to Official GHMC Portal", grievance_url)


def render_sidebar() -> None:
    from src.config import get_int_env

    with st.sidebar:
        st.subheader("Data Management")
        if st.button("Refresh Feed", use_container_width=True):
            trigger_background_refresh()
            st.toast("Refreshing live feed...")

        if "last_refresh_notice" in st.session_state:
            count, duration = st.session_state["last_refresh_notice"]
            st.success(f"Applied {count} scraped issues ({duration:.1f}s)")

        @st.fragment(run_every=2)
        def render_refresh_status() -> None:
            job = BackgroundJob.get_data()
            if job["status"] == "running":
                timeout_seconds = (
                    get_int_env(
                        "CIVICPULSE_SCRAPE_TOTAL_TIMEOUT_SECONDS",
                        45,
                    )
                    + 10
                )
                if job["elapsed"] > timeout_seconds:
                    BackgroundJob.fail(
                        f"Live scrape exceeded {timeout_seconds}s. "
                        "Try again or reduce the scrape target limit."
                    )
                    st.rerun()
                st.info(f"Scraping live sources... ({job['elapsed']:.0f}s)")
            elif job["status"] == "complete":
                if apply_completed_refresh(job):
                    st.rerun()
            elif job["status"] == "error":
                st.error(f"Refresh failed: {job['error']}")
                if st.button("Dismiss"):
                    BackgroundJob.reset()
                    st.rerun()

        render_refresh_status()


def main() -> None:
    st.set_page_config(
        page_title="CivicPulse",
        page_icon=":material/radar:",
        layout="wide",
    )
    logging.info("app.py: Starting execution...")

    if apply_completed_refresh(BackgroundJob.get_data()):
        st.rerun()

    st.title("CivicPulse")
    st.caption("AI-driven civic issue prioritization for Hyderabad GHMC zones")
    render_sidebar()
    st.text_input(
        "Search",
        key="search_query",
        placeholder="Search by area, category, or issue",
    )

    if "dashboard_df" not in st.session_state:
        st.session_state["dashboard_df"] = None

    query_changed = str(st.session_state.get("search_query")) != str(
        st.session_state.get("last_query")
    )
    if st.session_state["dashboard_df"] is None or query_changed:
        st.session_state["last_query"] = st.session_state.get("search_query")
        with st.spinner("Updating dashboard..."):
            try:
                from src.storage.vector_store import MissingSupabaseConfig

                st.session_state["dashboard_df"] = load_dashboard_data()
            except MissingSupabaseConfig as error:
                render_cloud_database_error(error)
                st.stop()
            except Exception as error:
                logging.error(f"Dashboard data load failed: {error}", exc_info=True)
                st.error(f"Error loading data: {error}")
                st.stop()

    df = st.session_state["dashboard_df"]

    if df is not None and not df.empty:
        active = len(df)
        critical = (df["impact_score"] >= 8.0).sum()

        m1, m2 = st.columns(2)
        m1.metric("Active Issues", active)
        m2.metric("Critical Priority", critical)

        st.subheader("Hotspots")
        render_issue_map(df)

        st.subheader("Issue Queue")
        render_prioritized_issue_cards(df)
    else:
        st.info("No issues found. Use the Refresh button in the sidebar to fetch data.")


if __name__ == "__main__":
    main()
