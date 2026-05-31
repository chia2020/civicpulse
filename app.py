from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import streamlit as st

from src.core.scoring import urgency_colors, urgency_label
from src.ingestion.pipeline import load_issues


GHMC_GRIEVANCE_URL = "https://greenhyderabad.ghmc.gov.in/GrievanceRegistration.aspx"
SQLITE_DB_PATH = Path("storage/civicpulse_vector.db")


st.set_page_config(page_title="CivicPulse", page_icon="🏙️", layout="wide")


def load_dashboard_data() -> pd.DataFrame:
    frame = load_issues(st.session_state.get("semantic_query") or None)
    if frame.empty:
        return frame
    frame["post_date"] = pd.to_datetime(frame["post_date"])
    frame["traction_date"] = pd.to_datetime(frame["traction_date"])
    return frame


def load_unresolved_grievances(db_path: Path = SQLITE_DB_PATH) -> pd.DataFrame:
    if not db_path.exists():
        return pd.DataFrame()

    try:
        with sqlite3.connect(db_path) as connection:
            rows = connection.execute(
                """
                SELECT id, category, landmark, description, severity_score, impact_score
                FROM grievances
                ORDER BY impact_score DESC, severity_score DESC
                """
            ).fetchall()
    except sqlite3.OperationalError:
        return pd.DataFrame()

    return pd.DataFrame(
        rows,
        columns=[
            "id",
            "category",
            "landmark",
            "description",
            "severity_score",
            "impact_score",
        ],
    )


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


def render_manual_copy_fallback(issue: pd.Series) -> None:
    prefilled_text = (
        f"Category: {issue.get('category') or 'Unspecified'}\n"
        f"Landmark: {issue.get('landmark') or issue.get('area') or 'Unspecified'}\n"
        f"Description: {issue.get('description') or issue.get('title') or 'No description provided'}"
    )
    st.caption("If the GHMC portal does not pre-fill these fields, copy this text:")
    st.code(prefilled_text, language="text")


def render_grievance_escalation_queue(grievances: pd.DataFrame) -> None:
    if grievances.empty:
        return

    st.subheader("Unresolved GHMC Escalations")
    for _, issue in grievances.iterrows():
        color, background = urgency_colors(float(issue["impact_score"]))
        with st.container(border=True):
            detail_col, action_col = st.columns([3, 1])
            with detail_col:
                st.markdown(
                    f"**{issue['category']}** near **{issue['landmark']}**  \n"
                    f"{issue['description']}"
                )
                st.markdown(
                    f"<span style='background:{background};color:{color};"
                    "padding:4px 8px;border-radius:6px;font-weight:700;'>"
                    f"Impact {float(issue['impact_score']):.2f}</span>",
                    unsafe_allow_html=True,
                )
            with action_col:
                escalation_url = build_ghmc_escalation_url(issue)
                st.link_button(
                    "🔴 Escalate to GHMC (One-Click)",
                    escalation_url,
                    use_container_width=True,
                )
                st.markdown(
                    (
                        f"<a href='{escalation_url}' target='_blank' "
                        "rel='noopener noreferrer'>Open in new tab</a>"
                    ),
                    unsafe_allow_html=True,
                )
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
                    f"{float(issue['impact_score']):.2f} · {urgency_label(float(issue['impact_score']))}</span>",
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
                st.link_button(
                    "🔴 Escalate to GHMC (One-Click)",
                    escalation_url,
                    use_container_width=True,
                )
                st.markdown(
                    (
                        f"<a href='{escalation_url}' target='_blank' "
                        "rel='noopener noreferrer'>Open in new tab</a>"
                    ),
                    unsafe_allow_html=True,
                )

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
        f"{score:.2f} · {urgency_label(score)}</span>"
    )


st.title("CivicPulse")
st.caption("AI-driven civic issue prioritization for Hyderabad GHMC zones")

st.text_input(
    "Vector Search",
    key="semantic_query",
    placeholder="Search by issue, area, category, or urgency signal",
)

df = load_dashboard_data()

if df.empty:
    st.warning("No civic issues found in the vector database.")
    st.stop()

active = len(df)
critical = int((df["impact_score"] >= 8.0).sum())
zones_affected = int(df["zone"].nunique())
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
filtered = filtered.sort_values(sort_column, ascending=direction == "Ascending")

map_col, trend_col = st.columns([1.35, 1])
with map_col:
    st.subheader("Hyderabad Hotspots")
    render_issue_map(filtered)

with trend_col:
    st.subheader("Zone Trend View")
    trend = (
        filtered.groupby(["zone", "category"], as_index=False)
        .size()
        .rename(columns={"size": "reports"})
    )
    st.bar_chart(trend, x="zone", y="reports", color="category")

st.subheader("Prioritized Issue Queue")
render_prioritized_issue_cards(filtered)

render_grievance_escalation_queue(load_unresolved_grievances())
