from src.core.scoring import calculate_impact_score, urgency_label


def test_impact_score_uses_documented_weights() -> None:
    score = calculate_impact_score(S=8, F=7, R=6, D=5, P=9)

    assert score == 7.0


def test_impact_score_clamps_parameters_to_normalized_scale() -> None:
    score = calculate_impact_score(S=20, F=-1, R=10, D=10, P=10)

    assert score == 7.5


def test_urgency_thresholds_match_dashboard_language() -> None:
    assert urgency_label(8.0) == "Critical"
    assert urgency_label(7.0) == "High"
    assert urgency_label(6.0) == "Medium"
    assert urgency_label(5.9) == "Low"
