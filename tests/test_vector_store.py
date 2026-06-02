from src.data.sample_issues import build_sample_issues
from src.ingestion.pipeline import normalize_issue
from src.storage.vector_store import CivicVectorStore


class FakeSupabaseClient:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, object]] = {}

    def request(
        self,
        method: str,
        table: str,
        params: dict[str, str] | None = None,
        payload: object | None = None,
        headers: dict[str, str] | None = None,
    ) -> object:
        if method == "POST":
            assert isinstance(payload, list)
            for row in payload:
                assert isinstance(row, dict)
                self.rows[str(row["id"])] = row
            return None

        if method == "GET":
            rows = list(self.rows.values())
            rows.sort(
                key=lambda row: (
                    float(row["impact_score"]),
                    str(row["traction_date"]),
                    str(row["post_date"]),
                ),
                reverse=True,
            )
            select = (params or {}).get("select")
            if select == "id":
                return [{"id": row["id"]} for row in rows]
            if select == "document":
                return [{"document": row["document"]} for row in rows]
            return [
                {"document": row["document"], "embedding": row["embedding"]}
                for row in rows
            ]

        if method == "DELETE":
            self.rows.clear()
            return None

        raise AssertionError(f"Unexpected method: {method}")


def test_vector_store_upserts_and_searches_issues() -> None:
    store = CivicVectorStore(client=FakeSupabaseClient())
    issues = [normalize_issue(issue) for issue in build_sample_issues()]

    assert store.upsert_issues(issues) == len(issues)
    assert store.count() == len(issues)

    results = store.search("metro potholes in west hyderabad", limit=3)

    assert not results.empty
    assert "Kukatpally" in results.iloc[0]["area"]


def test_vector_store_search_ignores_unrelated_queries() -> None:
    store = CivicVectorStore(client=FakeSupabaseClient())
    issues = [normalize_issue(issue) for issue in build_sample_issues()]
    store.upsert_issues(issues)

    results = store.search("zzzz-not-a-civic-topic", limit=3)

    assert results.empty
