import pytest
from src.storage.vector_store import CivicVectorStore

class DedupFakeSupabaseClient:
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
            # Order matches fetch_all select parameters
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
            return [{"document": row["document"], "embedding": row["embedding"]} for row in rows]

        if method == "DELETE":
            if params and "id" in params:
                val = params["id"]
                if val.startswith("in.("):
                    ids_str = val[4:-1]
                    ids = [id_str.strip() for id_str in ids_str.split(",") if id_str.strip()]
                    for issue_id in ids:
                        self.rows.pop(issue_id, None)
                elif val.startswith("eq."):
                    issue_id = val[3:]
                    self.rows.pop(issue_id, None)
                elif val == "not.is.null":
                    self.rows.clear()
            else:
                self.rows.clear()
            return None

        raise AssertionError(f"Unexpected method: {method}")


def test_deduplicate_existing_issues() -> None:
    client = DedupFakeSupabaseClient()
    store = CivicVectorStore(client=client)

    # Let's seed duplicates
    # Issue A: original, lower impact score
    issue_a_v1 = {
        "id": "HYD-A1",
        "title": "Severe Pothole on Road",
        "area": "Kukatpally",
        "zone": "Unknown",
        "category": "Roads",
        "description": "Large pothole in the middle of Kukatpally road",
        "source": "twitter",
        "source_url": "",
        "post_date": "2026-06-25",
        "traction_date": "2026-06-25",
        "impact_score": 5.2,
    }

    # Issue A v2: Duplicate, higher impact score, resolved zone
    issue_a_v2 = {
        "id": "HYD-A2",
        "title": "Severe Pothole on Road",
        "area": "Kukatpally",
        "zone": "West",
        "category": "Roads",
        "description": "Large pothole in the middle of Kukatpally road",
        "source": "twitter",
        "source_url": "https://twitter.com/status/123",
        "post_date": "2026-06-25",
        "traction_date": "2026-06-25",
        "impact_score": 8.5,
    }

    # Issue B: Unique issue
    issue_b = {
        "id": "HYD-B",
        "title": "Waterlogging near Metro station",
        "area": "Miyapur",
        "zone": "West",
        "category": "Water",
        "description": "Flooding near Miyapur metro",
        "source": "twitter",
        "source_url": "",
        "post_date": "2026-06-25",
        "traction_date": "2026-06-25",
        "impact_score": 6.8,
    }

    # Upsert all into fake db
    store.upsert_issues([issue_a_v1, issue_a_v2, issue_b])
    assert store.count() == 3

    # Run deduplication
    deleted = store.deduplicate_existing()
    assert deleted == 1

    # Verify count is 2
    assert store.count() == 2

    # Verify that the kept record for A is A2 (the one with the higher impact score, resolved zone, and URL)
    records = store.fetch_all()
    assert len(records) == 2
    
    ids_in_store = records["id"].tolist()
    assert "HYD-A2" in ids_in_store
    assert "HYD-B" in ids_in_store
    assert "HYD-A1" not in ids_in_store
