from src.core.ai_triage import estimate_issue_parameters


def test_estimate_issue_parameters_empty_falls_back() -> None:
    res = estimate_issue_parameters("")
    assert res["severity"] == 5.0
    assert res["frequency"] == 3.0
    assert res["compounding_risk"] == 5.0
    assert "issue" in res["title"].lower() or "hyderabad" in res["title"].lower()


def test_estimate_issue_parameters_normal_falls_back_when_no_api_key(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GENERATIVE_AI_API_KEY", raising=False)

    res = estimate_issue_parameters("Monsoon rainwater flooding near Ameerpet metro station")
    assert res["severity"] == 5.0
    assert res["frequency"] == 3.0
    assert res["compounding_risk"] == 5.0
    assert "ameerpet" in res["title"].lower()
