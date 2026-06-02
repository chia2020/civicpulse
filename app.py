from __future__ import annotations

import asyncio
from html import escape
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import streamlit as st

from src.config import get_bool_env, get_int_env
from src.core.scoring import urgency_colors, urgency_label
from src.ingestion.pipeline import load_issues, run_live_pipeline
from src.storage.vector_store import MissingSupabaseConfig


GHMC_GRIEVANCE_URL = "https://greenhyderabad.ghmc.gov.in/GrievanceRegistration.aspx"
LOCAL_DOCS_PATH = Path("PIPELINE.md").resolve()


CATEGORY_COLORS = {
    "Drainage": "#2D7FF9",
    "Potholes": "#BA7517",
    "Waterlogging": "#1D9E75",
    "Garbage": "#6A5ACD",
    "Streetlights": "#C2518A",
    "Water Supply": "#007A7A",
    "Encroachment": "#A32D2D",
    "Uncategorized": "#6B7280",
}


st.set_page_config(page_title="CivicPulse", page_icon="CP", layout="wide")


@st.cache_data(
    ttl=get_int_env("CIVICPULSE_REFRESH_TTL_SECONDS", 900),
    show_spinner=False,
)
def refresh_live_issues_on_open() -> int:
    frame = asyncio.run(run_live_pipeline(replace_existing=False))
    return len(frame)


def render_cloud_database_error(error: Exception) -> None:
    st.error(str(error))
    st.info(
        "Configure Supabase in `.env` with `SUPABASE_URL` and "
        "`SUPABASE_SERVICE_ROLE_KEY` for server-side refreshes, or "
        "`SUPABASE_ANON_KEY`/`SUPABASE_API_KEY` if Row Level Security allows "
        "the dashboard operations. Then create the `issues` table from `PIPELINE.md`."
    )
    if LOCAL_DOCS_PATH.exists():
        st.caption(f"Pipeline guide: {LOCAL_DOCS_PATH}")


def load_dashboard_data() -> pd.DataFrame:
    query = str(st.session_state.get("search_query") or "").strip()
    frame = load_issues(query or None)
    if frame.empty:
        return frame
    frame["post_date"] = pd.to_datetime(frame["post_date"])
    frame["traction_date"] = pd.to_datetime(frame["traction_date"])
    return frame


def load_unresolved_grievances(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "zone" not in frame:
        return pd.DataFrame()
    return frame.loc[frame["zone"] == "Unknown"].sort_values(
        by=["impact_score", "post_date"],
        ascending=[False, False],
    )  # type: ignore


def build_ghmc_escalation_url(issue: pd.Series) -> str:
    category = quote(str(issue.get("category") or ""), safe="")
    landmark = quote(str(issue.get("landmark") or issue.get("area") or ""), safe="")
    description = quote(
        str(issue.get("description") or issue.get("title") or ""),
        safe="",
    )
    return (
        f"{GHMC_GRIEVANCE_URL}"
        f"?category={category}&landmark={landmark}&description={description}"
    )


def render_escalation_link(url: str) -> None:
    safe_url = escape(url, quote=True)
    st.markdown(
        (
            "<a class='cp-action-link' "
            f"href='{safe_url}' target='_blank' rel='noopener noreferrer'>"
            "Escalate to GHMC</a>"
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        (
            f"<a href='{safe_url}' target='_blank' "
            "rel='noopener noreferrer'>Open in new tab</a>"
        ),
        unsafe_allow_html=True,
    )


def render_manual_copy_fallback(issue: pd.Series) -> None:
    prefilled_text = (
        f"Category: {issue.get('category') or 'Unspecified'}\n"
        f"Landmark: {issue.get('landmark') or issue.get('area') or 'Unspecified'}\n"
        "Description: "
        f"{issue.get('description') or issue.get('title') or 'No description provided'}"
    )
    st.caption("If the GHMC portal does not pre-fill these fields, copy this text:")
    st.code(prefilled_text, language="text")


def render_grievance_escalation_queue(grievances: pd.DataFrame) -> None:
    if grievances.empty:
        return

    st.subheader("Manual Location Triage")
    for _, issue in grievances.iterrows():
        color, background = urgency_colors(float(issue["impact_score"]))
        with st.container(border=True):
            detail_col, action_col = st.columns([3, 1])
            with detail_col:
                st.markdown(
                    f"**{issue['category']}** near **{issue.get('area', 'Unknown')}**  \n"
                    f"{issue.get('description', '')}"
                )
                st.markdown(
                    f"<span style='background:{background};color:{color};"
                    "padding:4px 8px;border-radius:6px;font-weight:700;'>"
                    f"Impact {float(issue['impact_score']):.2f}</span>",
                    unsafe_allow_html=True,
                )
            with action_col:
                escalation_url = build_ghmc_escalation_url(issue)
                render_escalation_link(escalation_url)
            render_manual_copy_fallback(issue)


def render_prioritized_issue_cards(frame: pd.DataFrame) -> None:
    for _, issue in frame.iterrows():
        color, background = urgency_colors(float(issue["impact_score"]))
        escalation_url = build_ghmc_escalation_url(issue)

        with st.container(border=True):
            detail_col, action_col = st.columns([3, 1])
            with detail_col:
                st.markdown(
                    f"**{issue['title']}**  \n"
                    f"{issue['category']} near **{issue['area']}** | {issue['zone']}"
                )
                st.write(issue["description"])
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
                    f"Engagement: {int(issue['engagement_count'])}"
                )

            with action_col:
                render_escalation_link(escalation_url)

            with st.expander("Manual copy fallback"):
                render_manual_copy_fallback(issue)


def render_issue_map(frame: pd.DataFrame) -> None:
    map_data = frame[["latitude", "longitude", "impact_score"]].copy()
    map_data["color"] = map_data["impact_score"].apply(
        lambda score: urgency_colors(float(score))[0]
    )
    map_data["size"] = map_data["impact_score"].apply(lambda score: max(float(score) * 14, 60))
    st.map(
        map_data,
        latitude="latitude",
        longitude="longitude",
        color="color",
        size="size",
        zoom=10,
        height=430,
    )


def score_badge(score: float) -> str:
    color, background = urgency_colors(score)
    return (
        f"<span style='background:{background};color:{color};"
        "padding:4px 8px;border-radius:6px;font-weight:700;'>"
        f"{score:.2f} - {urgency_label(score)}</span>"
    )


import json
import streamlit.components.v1 as components

def render_zone_trend_chart(frame: pd.DataFrame) -> None:
    trend = (
        frame.groupby(["zone", "category"], as_index=False)
        .size()
        .rename(columns={"size": "reports"})
    )
    if trend.empty:
        st.caption("No reports available for the selected filters.")
        return

    labels = []
    data_values = []
    bg_colors = []

    for _, row in trend.sort_values(["zone", "category"]).iterrows():
        labels.append(f"{row['zone']} - {row['category']}")
        data_values.append(int(row["reports"]))
        bg_colors.append(CATEGORY_COLORS.get(str(row["category"]), "#6B7280"))

    chart_data = {
        "labels": labels,
        "datasets": [{
            "label": "Reports",
            "data": data_values,
            "backgroundColor": bg_colors,
        }]
    }

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    </head>
    <body style="margin: 0; padding: 0;">
        <canvas id="myChart" width="400" height="300"></canvas>
        <script>
            var ctx = document.getElementById('myChart').getContext('2d');
            var chart = new Chart(ctx, {{
                type: 'bar',
                data: {json.dumps(chart_data)},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        y: {{
                            beginAtZero: true
                        }}
                    }},
                    plugins: {{
                        legend: {{
                            display: false
                        }}
                    }}
                }}
            }});
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=320)


st.markdown(
    """
    <style>
    .cp-action-link {
        display: block;
        width: 100%;
        box-sizing: border-box;
        padding: 0.55rem 0.75rem;
        border: 1px solid #2d7ff9;
        border-radius: 6px;
        color: #ffffff !important;
        background: #2d7ff9;
        text-align: center;
        font-weight: 700;
        text-decoration: none !important;
        margin-bottom: 0.65rem;
    }
    .cp-action-link:hover {
        background: #1f6fe5;
        border-color: #1f6fe5;
    }
    .cp-trend-chart {
        display: grid;
        gap: 0.8rem;
        padding-top: 0.15rem;
    }
    .cp-trend-row {
        display: grid;
        gap: 0.35rem;
    }
    .cp-trend-meta {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 0.75rem;
        font-weight: 700;
    }
    .cp-trend-meta small {
        color: #8b949e;
        font-weight: 600;
        white-space: nowrap;
    }
    .cp-trend-track {
        height: 0.7rem;
        border-radius: 999px;
        background: rgba(148, 163, 184, 0.2);
        overflow: hidden;
    }
    .cp-trend-bar {
        height: 100%;
        border-radius: inherit;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


st.title("CivicPulse")
st.caption("AI-driven civic issue prioritization for Hyderabad GHMC zones")

if get_bool_env("CIVICPULSE_AUTO_REFRESH_ON_OPEN", True):
    with st.spinner("Refreshing live Hyderabad civic issue feed..."):
        try:
            refreshed_count = refresh_live_issues_on_open()
            if refreshed_count:
                st.caption(f"Cloud database refreshed with {refreshed_count} live records.")
        except MissingSupabaseConfig as error:
            render_cloud_database_error(error)
            st.stop()
        except RuntimeError as error:
            st.warning(f"Live refresh skipped: {error}")

st.text_input(
    "Search",
    key="search_query",
    placeholder="Search by issue, area, category, or urgency signal",
)

try:
    df = load_dashboard_data()
except MissingSupabaseConfig as error:
    render_cloud_database_error(error)
    st.stop()
except RuntimeError as error:
    st.error(f"Could not read CivicPulse issues from Supabase: {error}")
    st.stop()

if df.empty:
    if str(st.session_state.get("search_query") or "").strip():
        st.warning("No civic issues match this search.")
    else:
        st.warning(
            "No live civic issues found in Supabase yet. The dashboard refresh runs on open; "
            "check the Supabase table, RSS connectivity, and `.env` settings if this stays empty."
        )
    st.stop()

active = len(df)
critical = (df["impact_score"] >= 8.0).sum()
zones_affected = int(df[df["zone"] != "Unknown"]["zone"].nunique())
resolved = 0

metric_cols = st.columns(4)
metric_cols[0].metric("Active", active)
metric_cols[1].metric("Critical", critical)
metric_cols[2].metric("Zones Affected", zones_affected)
metric_cols[3].metric("Resolved", resolved)

filter_cols = st.columns([1.1, 1.1, 1.2, 1])
category = filter_cols[0].selectbox("Category", ["All", *sorted(df["category"].unique())])
zone = filter_cols[1].selectbox("GHMC Zone", ["All", *sorted(df["zone"].unique())])
sort_by = filter_cols[2].selectbox(
    "Sort By",
    ["Impact Score", "Post Date", "Peak Traction Date"],
)
direction = filter_cols[3].selectbox("Direction", ["Descending", "Ascending"])

filtered = df.copy()
if category != "All":
    filtered = filtered[filtered["category"] == category]
if zone != "All":
    filtered = filtered[filtered["zone"] == zone]

sort_column = {
    "Impact Score": "impact_score",
    "Post Date": "post_date",
    "Peak Traction Date": "traction_date",
}[sort_by]
filtered = filtered.sort_values(by=sort_column, ascending=(direction == "Ascending"))  # type: ignore

map_col, trend_col = st.columns([1.35, 1])
with map_col:
    st.subheader("Hyderabad Hotspots")
    render_issue_map(filtered)

with trend_col:
    st.subheader("Zone Trend View")
    render_zone_trend_chart(filtered)

st.subheader("Prioritized Issue Queue")
render_prioritized_issue_cards(filtered)

render_grievance_escalation_queue(load_unresolved_grievances(df))
