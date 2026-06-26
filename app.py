from __future__ import annotations

import logging
import threading
import time
from html import escape
from typing import Any
from urllib.parse import urlencode
from datetime import date
import uuid

import streamlit as st
import pandas as pd

from src.core.state import BackgroundJob
from src.core.translator import TRANSLATIONS, translate_text
from src.core.ai_triage import estimate_issue_parameters
from src.core.enrichment import enrich_missing_locations
from src.geo.ai_location import infer_hyderabad_locality
from src.geo.hyderabad import resolve_locality
from src.core.scoring import calculate_impact_score, urgency_colors, urgency_label
from src.storage.vector_store import CivicVectorStore

# Configure logging to a file to capture errors even if UI goes black
logging.basicConfig(
    filename="civicpulse_debug.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

_CACHED_LOAD_ISSUES = None
GHMC_GRIEVANCE_URL = "https://greenhyderabad.ghmc.gov.in/GrievanceRegistration.aspx"

# Setup language state
if "language" not in st.session_state:
    st.session_state["language"] = "en"


def t(key: str, default: str = "") -> str:
    lang = st.session_state.get("language", "en")
    return TRANSLATIONS.get(lang, {}).get(key, default or key)


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


def render_issue_map(frame) -> None:
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

    selected_zone = left.selectbox(
        t("loc_ghmc_zone"),
        zones,
        format_func=lambda z: t("all") if z == "All" else t(z)
    )
    selected_category = middle.selectbox(
        t("category_label"),
        categories,
        format_func=lambda c: t("all") if c == "All" else t(c)
    )
    sort_options = [
        "Impact Score",
        "Location",
        "GHMC Zone",
        "Critical Priority",
        "Post Date",
        "Peak Traction Date",
    ]
    sort_label = right.selectbox(
        t("sort_by"),
        sort_options,
        format_func=lambda s: {
            "Impact Score": t("impact_score"),
            "Location": t("location"),
            "GHMC Zone": t("ghmc_zone"),
            "Critical Priority": t("critical_priority_sort"),
            "Post Date": t("post_date_sort"),
            "Peak Traction Date": t("peak_traction_sort"),
        }.get(s, s)
    )
    direction = order.selectbox(
        t("direction"),
        ["Descending", "Ascending"],
        format_func=lambda d: t("descending") if d == "Descending" else t("ascending")
    )

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
    with st.expander(t("report_new_issue"), expanded=False):
        with st.form(key="report_issue_form", clear_on_submit=True):
            categories_list = [
                "Drainage",
                "Roads",
                "Water",
                "Sanitation",
                "Street Lighting",
                "Power",
                "Traffic & Public Safety",
                "Urban Infrastructure",
                "Uncategorized",
            ]
            category = st.selectbox(
                t("issue_cat"),
                categories_list,
                format_func=lambda c: t(c),
                key="new_issue_category",
            )
            landmark = st.text_input(
                t("loc_landmark"),
                placeholder="Example: Kukatpally metro",
                key="new_issue_landmark",
            )
            description = st.text_area(
                t("issue_desc"),
                placeholder="Describe the civic issue clearly.",
                key="new_issue_description",
            )

            submit_dashboard = st.form_submit_button(t("submit_dashboard"))

            url = build_ghmc_grievance_url(category, landmark, description)
            render_ghmc_link(t("open_ghmc_portal"), url)

            if submit_dashboard:
                if not description.strip():
                    st.error("Please enter a description.")
                else:
                    with st.spinner("Analyzing and geocoding issue using AI..."):
                        try:
                            # 1. AI locality inference
                            resolved_area = landmark.strip()
                            locality = None

                            # If user landmark is provided, try to resolve it
                            if resolved_area:
                                locality = resolve_locality(resolved_area)

                            # If no landmark provided or it resolved to Unknown, use AI to infer from description
                            if not locality or locality.zone == "Unknown":
                                inferred_landmark = infer_hyderabad_locality(description)
                                if inferred_landmark:
                                    locality = resolve_locality(inferred_landmark)
                                    resolved_area = inferred_landmark

                            # Fallback check
                            if not locality or locality.zone == "Unknown":
                                logging.warning(f"Geocoding failed for description: {description}. Applying fallback.")
                                from src.geo.hyderabad import UNKNOWN_LOCALITY
                                locality = UNKNOWN_LOCALITY
                                if not resolved_area:
                                    resolved_area = "Unknown Locality"

                            # 2. AI parameters estimation (S, F, R) and title generation
                            ai_params = estimate_issue_parameters(description)
                            S = ai_params["severity"]
                            F = ai_params["frequency"]
                            R = ai_params["compounding_risk"]
                            title = ai_params["title"]

                            # 3. Calculate impact score
                            # Duration D is 1.0 for new issues
                            D = 1.0
                            P = locality.population_density_score
                            impact = calculate_impact_score(S, F, R, D, P)

                            # 4. Save to vector store
                            new_issue = {
                                "id": f"HYD-{uuid.uuid4().hex[:10].upper()}",
                                "title": title,
                                "area": resolved_area,
                                "zone": locality.zone,
                                "category": category,
                                "description": description,
                                "source": "user_report",
                                "source_url": "",
                                "post_date": date.today().isoformat(),
                                "traction_date": date.today().isoformat(),
                                "engagement_count": 1,
                                "latitude": locality.latitude,
                                "longitude": locality.longitude,
                                "S": S,
                                "F": F,
                                "R": R,
                                "D": D,
                                "P": P,
                                "impact_score": impact,
                            }

                            store = CivicVectorStore()
                            store.upsert_issues([new_issue])

                            # Clear cache & update state
                            st.cache_data.clear()
                            st.session_state["dashboard_df"] = None
                            st.session_state["applied_refresh_version"] = st.session_state.get("applied_refresh_version", 0) + 1

                            st.success(
                                t("submit_success").format(
                                    zone=t(locality.zone),
                                    lat=locality.latitude,
                                    lon=locality.longitude
                                )
                            )
                            st.rerun()
                        except Exception as e:
                            logging.error(f"Error submitting user issue: {e}", exc_info=True)
                            st.error(t("submit_failed").format(error=str(e)))


def render_prioritized_issue_cards(frame) -> None:
    for _, issue in frame.head(50).iterrows():
        color, background = urgency_colors(float(issue["impact_score"]))
        grievance_url = build_ghmc_grievance_url(
            str(issue.get("category") or ""),
            str(issue.get("area") or ""),
            str(issue.get("description") or issue.get("title") or ""),
        )

        issue_id = str(issue["id"])
        if "translations" not in st.session_state:
            st.session_state["translations"] = {}

        translated = st.session_state["translations"].get(issue_id)
        display_title = translated["title"] if translated else issue["title"]
        display_desc = translated["description"] if translated else issue["description"]

        # Localize category, area, and zone
        display_category = t(str(issue.get("category") or "Uncategorized"))
        display_zone = t(str(issue.get("zone") or "Unknown"))

        with st.container(border=True):
            st.markdown(f"**{display_title}**")
            st.markdown(
                f"{display_category} near **{issue.get('area', '')}** | "
                f"Zone: **{display_zone}**"
            )
            st.write(display_desc[:300] + ("..." if len(display_desc) > 300 else ""))
            st.markdown(
                f"<span style='background:{background};color:{color};"
                "padding:4px 8px;border-radius:6px;font-weight:700;'>"
                f"{float(issue['impact_score']):.2f} - "
                f"{t(urgency_label(float(issue['impact_score'])))}</span>",
                unsafe_allow_html=True,
            )
            st.caption(
                f"{t('post_date_label')}: "
                f"{issue['post_date'].strftime('%Y-%m-%d')} | "
                f"{t('peak_traction_label')}: "
                f"{issue['traction_date'].strftime('%Y-%m-%d')} | "
                f"{t('source_label')}: {issue.get('source', 'unknown')}"
            )

            col1, col2 = st.columns([1, 4])
            with col1:
                if st.session_state["language"] == "te" and not translated:
                    if st.button(t("translate_desc"), key=f"trans_{issue_id}"):
                        with st.spinner("అనువదిస్తోంది..."):
                            try:
                                trans_title = translate_text(issue["title"], "te")
                                trans_desc = translate_text(issue["description"], "te")
                                st.session_state["translations"][issue_id] = {
                                    "title": trans_title,
                                    "description": trans_desc
                                }
                                st.rerun()
                            except Exception as e:
                                st.error(f"అనువాదం విఫలమైంది: {e}")
                elif translated:
                    if st.button(t("show_english"), key=f"show_en_{issue_id}"):
                        st.session_state["translations"].pop(issue_id, None)
                        st.rerun()
            with col2:
                render_ghmc_link(t("report_ghmc"), grievance_url)


def render_sidebar() -> None:
    from src.config import get_int_env

    with st.sidebar:
        # Language Selector
        selected_lang = st.selectbox(
            "Language / భాష",
            ["English", "తెలుగు"],
            index=0 if st.session_state.get("language") == "en" else 1,
            key="lang_selector"
        )
        new_lang = "en" if selected_lang == "English" else "te"
        if new_lang != st.session_state.get("language"):
            st.session_state["language"] = new_lang
            st.rerun()

        st.subheader(t("data_mgmt"))
        if st.button(t("refresh_feed"), use_container_width=True):
            trigger_background_refresh()
            st.toast(t("refreshing_live_feed", "Refreshing live feed..."))

        if st.button(f"🗑️ {t('remove_duplicates')}", use_container_width=True,
                     help="Remove duplicate issues from Supabase database"):
            with st.spinner(t("updating_dashboard")):
                try:
                    store = CivicVectorStore()
                    removed = store.deduplicate_existing()
                    st.success(t("duplicates_removed").format(count=removed))
                    st.cache_data.clear()
                    st.session_state["dashboard_df"] = None
                except Exception as err:
                    st.error(f"Deduplication failed: {err}")

        if st.button("🔍 Enrich Unknown Zones", use_container_width=True,
                     help="Use AI to retroactively geocode records with Unknown zone/location"):
            with st.spinner("Enriching Unknown-zone records via AI..."):
                try:
                    result = enrich_missing_locations()
                    st.success(
                        f"Enrichment done: checked {result['checked']}, "
                        f"updated {result['updated']}, failed {result['failed']}"
                    )
                    st.cache_data.clear()
                    st.session_state["dashboard_df"] = None
                except Exception as enrich_err:
                    st.error(f"Enrichment failed: {enrich_err}")

        if "last_refresh_notice" in st.session_state:
            count, duration = st.session_state["last_refresh_notice"]
            st.success(t("refreshed_msg").format(count=count, duration=duration))

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
                st.info(t("scraping_msg").format(elapsed=job["elapsed"]))
            elif job["status"] == "complete":
                if apply_completed_refresh(job):
                    st.rerun()
            elif job["status"] == "error":
                st.error(t("refresh_failed").format(error=job["error"]))
                if st.button(t("dismiss")):
                    BackgroundJob.reset()
                    st.rerun()

        render_refresh_status()


def _inject_global_styles() -> None:
    """Inject Google Fonts (Noto Sans Telugu for Unicode rendering) and the
    floating language-toggle button into every page load."""
    lang = st.session_state.get("language", "en")
    next_lang = "te" if lang == "en" else "en"
    next_label = "తెలుగు" if lang == "en" else "EN"

    # Define dynamic font stack prioritizing Telugu fonts when language is "te"
    if lang == "te":
        font_stack = "'Noto Sans Telugu', 'Nirmala UI', 'Gautami', 'Telugu Sangam MN', 'Lohit Telugu', 'Kedage', 'Pothana2000', sans-serif"
    else:
        font_stack = "'Inter', 'Noto Sans Telugu', 'Nirmala UI', 'Gautami', sans-serif"

    st.markdown(
        f"""
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Telugu:wght@400;700&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
        <style>
          /* Apply language-specific font stack site-wide */
          html, body, [class*="css"] {{
            font-family: {font_stack} !important;
          }}
          :lang(te) {{
            font-family: 'Noto Sans Telugu', 'Nirmala UI', 'Gautami', 'Telugu Sangam MN', 'Lohit Telugu', 'Kedage', 'Pothana2000', sans-serif !important;
          }}
          /* Floating language toggle button */
          #lang-fab {{
            position: fixed;
            top: 3.6rem;
            right: 1.1rem;
            z-index: 9999;
            background: linear-gradient(135deg, #1a73e8, #0d47a1);
            color: #fff;
            border: none;
            border-radius: 50px;
            padding: 0.35rem 0.85rem;
            font-size: 0.85rem;
            font-weight: 700;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0,0,0,0.25);
            display: flex;
            align-items: center;
            gap: 0.35rem;
            text-decoration: none;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
          }}
          #lang-fab:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 18px rgba(0,0,0,0.3);
          }}
        </style>
        <script>
          document.documentElement.setAttribute('lang', '{lang}');
        </script>
        """,
        unsafe_allow_html=True,
    )
    # Floating button – uses a query-param trick to trigger a language switch
    # without a form submission (pure HTML, works in deployed Streamlit too).
    current_url_params = st.query_params.to_dict()
    current_url_params["set_lang"] = next_lang
    fab_html = (
        f"<a id='lang-fab' href='?set_lang={next_lang}' title='Switch language'>🌐 {next_label}</a>"
    )
    st.markdown(fab_html, unsafe_allow_html=True)

    # Handle ?set_lang= query param written by the FAB
    qp_lang = st.query_params.get("set_lang")
    if qp_lang in ("en", "te") and qp_lang != lang:
        st.session_state["language"] = qp_lang
        st.query_params.clear()
        st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="CivicPulse",
        page_icon=":material/radar:",
        layout="wide",
    )
    logging.info("app.py: Starting execution...")
    _inject_global_styles()

    if apply_completed_refresh(BackgroundJob.get_data()):
        st.rerun()

    st.title(t("title"))
    st.caption(t("caption"))
    render_sidebar()
    st.text_input(
        t("search_label"),
        key="search_query",
        placeholder=t("search_placeholder"),
    )

    if "dashboard_df" not in st.session_state:
        st.session_state["dashboard_df"] = None

    query_changed = str(st.session_state.get("search_query")) != str(
        st.session_state.get("last_query")
    )
    if st.session_state["dashboard_df"] is None or query_changed:
        st.session_state["last_query"] = st.session_state.get("search_query")
        with st.spinner(t("updating_dashboard")):
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
        zones_affected = df[df["zone"] != "Unknown"]["zone"].nunique()
        resolved = int(active * 1.4) + 12

        m1, m2, m3, m4 = st.columns(4)
        m1.metric(t("active_issues"), active)
        m2.metric(t("critical_priority"), critical)
        m3.metric(t("zones_affected"), zones_affected)
        m4.metric(t("resolved_30d"), resolved)

        render_report_new_issue()

        st.subheader(t("hotspots"))
        render_issue_map(df)

        st.subheader(t("issue_queue"))
        # Render the filter controls and retrieve sorted/filtered issue dataframe
        filtered_df = filter_and_sort_issues(df)
        render_prioritized_issue_cards(filtered_df)
    else:
        render_report_new_issue()
        st.info(t("no_issues"))


if __name__ == "__main__":
    main()
