import pandas as pd

from src.data.sample_issues import build_sample_issues
from src.ingestion.pipeline import normalize_issue


def test_traction_date_sorting_differs_from_post_date_sorting() -> None:
    frame = pd.DataFrame(normalize_issue(issue) for issue in build_sample_issues())
    by_post = frame.sort_values("post_date", ascending=False)["id"].tolist()
    by_traction = frame.sort_values("traction_date", ascending=False)["id"].tolist()

    assert by_post != by_traction
    assert by_post[0] == "HYD-005"
    assert by_traction[0] == "HYD-003"
