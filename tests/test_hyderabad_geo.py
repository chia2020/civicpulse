from src.geo.hyderabad import resolve_locality


def test_mehdipatnam_flyover_resolves_to_central_zone() -> None:
    locality = resolve_locality("open manhole near Mehdipatnam flyover")

    assert locality.zone == "Central"


def test_kukatpally_metro_resolves_to_west_zone() -> None:
    locality = resolve_locality("potholes beside Kukatpally metro")

    assert locality.zone == "West"


def test_unknown_landmark_falls_back_for_manual_triage() -> None:
    locality = resolve_locality("unclear landmark from a noisy scraped post")

    assert locality.zone == "Unknown"
