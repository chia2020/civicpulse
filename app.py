from __future__ import annotations

import pandas as pd
import streamlit as st

from src.core.scoring import urgency_colors, urgency_label
from src.ingestion.pipeline import load_issues


st.set_page_config(page_title="CivicPulse", page_icon="🏙️", layout="wide")


def load_dashboard_data() -> pd.DataFrame:
    frame = load_issues(st.session_state.get("semantic_query") or None)
    if frame.empty:
        return frame
    frame["post_date"] = pd.to_datetime(frame["post_date"])
    frame["traction_date"] = pd.to_datetime(frame["traction_date"])
    return frame


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

display = filtered[
    [
        "id",
        "title",
        "area",
        "zone",
        "category",
        "impact_score",
        "post_date",
        "traction_date",
        "engagement_count",
    ]
].copy()
display["post_date"] = display["post_date"].dt.strftime("%Y-%m-%d")
display["traction_date"] = display["traction_date"].dt.strftime("%Y-%m-%d")
display["impact"] = display["impact_score"].apply(lambda value: score_badge(float(value)))

st.write(
    display[
        [
            "id",
            "title",
            "area",
            "zone",
            "category",
            "impact",
            "post_date",
            "traction_date",
            "engagement_count",
        ]
    ].to_html(escape=False, index=False),
    unsafe_allow_html=True,
)
