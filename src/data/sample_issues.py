from __future__ import annotations

from src.core.scoring import calculate_impact_score
from src.geo.hyderabad import resolve_locality


RAW_SAMPLE_ISSUES: list[dict[str, object]] = [
    {
        "id": "HYD-001",
        "title": "Open manhole near Mehdipatnam flyover",
        "area": "Mehdipatnam flyover",
        "category": "Drainage",
        "description": "Residents report an uncovered manhole near the bus stop after repeated complaints.",
        "source": "r/hyderabad",
        "post_date": "2026-05-11",
        "traction_date": "2026-05-24",
        "engagement_count": 188,
        "S": 9.4,
        "F": 7.8,
        "R": 8.7,
        "D": 6.3,
    },
    {
        "id": "HYD-002",
        "title": "Kukatpally metro road potholes",
        "area": "Kukatpally metro",
        "category": "Roads",
        "description": "Multiple commuters flagged deep potholes along the metro corridor service road.",
        "source": "Telangana Today",
        "post_date": "2026-05-18",
        "traction_date": "2026-05-19",
        "engagement_count": 141,
        "S": 8.0,
        "F": 8.6,
        "R": 7.4,
        "D": 4.0,
    },
    {
        "id": "HYD-003",
        "title": "LB Nagar drinking water disruption",
        "area": "LB Nagar",
        "category": "Water",
        "description": "Apartment clusters report low pressure and intermittent supply for several days.",
        "source": "Local RSS",
        "post_date": "2026-05-21",
        "traction_date": "2026-05-28",
        "engagement_count": 96,
        "S": 6.8,
        "F": 7.2,
        "R": 7.8,
        "D": 3.0,
    },
    {
        "id": "HYD-004",
        "title": "Charminar garbage collection backlog",
        "area": "Charminar",
        "category": "Sanitation",
        "description": "Shopkeepers say garbage bins have overflowed near high-footfall lanes.",
        "source": "Public post",
        "post_date": "2026-05-14",
        "traction_date": "2026-05-15",
        "engagement_count": 74,
        "S": 6.1,
        "F": 6.9,
        "R": 6.4,
        "D": 5.3,
    },
    {
        "id": "HYD-005",
        "title": "Secunderabad street lighting outage",
        "area": "Secunderabad",
        "category": "Street Lighting",
        "description": "Several street lights are out near the station approach road, raising safety concerns.",
        "source": "r/hyderabad",
        "post_date": "2026-05-23",
        "traction_date": "2026-05-25",
        "engagement_count": 82,
        "S": 7.2,
        "F": 6.0,
        "R": 5.8,
        "D": 2.3,
    },
    {
        "id": "HYD-006",
        "title": "Malakpet monsoon drain choking",
        "area": "Malakpet",
        "category": "Drainage",
        "description": "Residents warn that desilting has not happened before expected monsoon showers.",
        "source": "The Hindu Hyderabad",
        "post_date": "2026-05-08",
        "traction_date": "2026-05-27",
        "engagement_count": 122,
        "S": 7.6,
        "F": 7.4,
        "R": 9.1,
        "D": 7.3,
    },
]


def build_sample_issues() -> list[dict[str, object]]:
    issues = []
    for item in RAW_SAMPLE_ISSUES:
        locality = resolve_locality(str(item["area"]))
        issue = dict(item)
        issue["zone"] = locality.zone
        issue["latitude"] = locality.latitude
        issue["longitude"] = locality.longitude
        issue["P"] = locality.population_density_score
        issue["impact_score"] = calculate_impact_score(
            float(issue["S"]),
            float(issue["F"]),
            float(issue["R"]),
            float(issue["D"]),
            float(issue["P"]),
        )
        issues.append(issue)
    return issues
