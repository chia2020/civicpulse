from __future__ import annotations

from datetime import date, datetime
from typing import Final


WEIGHTS: Final[dict[str, float]] = {
    "S": 0.30,
    "F": 0.25,
    "R": 0.20,
    "D": 0.15,
    "P": 0.10,
}


def clamp_score(value: float) -> float:
    """Keep each scoring parameter inside the normalized 0-10 range."""
    return max(0.0, min(10.0, float(value)))


def calculate_impact_score(S: float, F: float, R: float, D: float, P: float) -> float:
    return round(
        (clamp_score(S) * WEIGHTS["S"])
        + (clamp_score(F) * WEIGHTS["F"])
        + (clamp_score(R) * WEIGHTS["R"])
        + (clamp_score(D) * WEIGHTS["D"])
        + (clamp_score(P) * WEIGHTS["P"]),
        2,
    )


def calculate_duration_score(post_date: str, today: date | None = None) -> float:
    reference_date = today or date.today()
    posted_on = datetime.strptime(post_date, "%Y-%m-%d").date()
    age_days = max(0, (reference_date - posted_on).days)
    return round(min(age_days / 30 * 10, 10), 2)


def urgency_label(score: float) -> str:
    if score >= 8.0:
        return "Critical"
    if score >= 7.0:
        return "High"
    if score >= 6.0:
        return "Medium"
    return "Low"


def urgency_colors(score: float) -> tuple[str, str]:
    if score >= 8.0:
        return "#A32D2D", "#FCEBEB"
    if score >= 7.0:
        return "#BA7517", "#FAEEDA"
    if score >= 6.0:
        return "#1D9E75", "#E1F5EE"
    return "#52616B", "#EEF2F5"
