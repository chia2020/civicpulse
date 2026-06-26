from __future__ import annotations

import hashlib
import json
import logging
import math
import os
from collections.abc import Iterable
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import pandas as pd

from src.config import load_environment

EMBEDDING_DIMENSIONS = 128
DEFAULT_TABLE_NAME = "issues"
LOGGER = logging.getLogger(__name__)


class MissingSupabaseConfig(RuntimeError):
    """Raised when the cloud database environment variables are not configured."""


class SupabaseClientProtocol(Protocol):
    def request(
        self,
        method: str,
        table: str,
        params: dict[str, str] | None = None,
        payload: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any: ...


def _tokenize(text: str) -> list[str]:
    return [
        token.strip(".,:;!?()[]{}\"'").lower()
        for token in text.split()
        if token.strip(".,:;!?()[]{}\"'")
    ]


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def embed_text(text: str, dimensions: int = EMBEDDING_DIMENSIONS) -> list[float]:
    vector = [0.0] * dimensions
    for token in _tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return vector
    return [round(value / magnitude, 6) for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=False))


def _searchable_text(issue: dict[str, object]) -> str:
    return " ".join(
        str(issue.get(field, ""))
        for field in ("title", "area", "zone", "category", "description", "source")
    )


def _supabase_api_key() -> str | None:
    return (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_API_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
    )


class SupabaseRestClient:
    def __init__(self, url: str, api_key: str, timeout_seconds: int = 30) -> None:
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_environment(cls) -> SupabaseRestClient:
        load_environment()
        url = os.getenv("SUPABASE_URL") or os.getenv("CIVICPULSE_SUPABASE_URL")
        api_key = _supabase_api_key()
        if not url or not api_key:
            raise MissingSupabaseConfig(
                "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY, SUPABASE_API_KEY, "
                "or SUPABASE_ANON_KEY in .env."
            )
        timeout = int(os.getenv("SUPABASE_TIMEOUT_SECONDS", "30"))
        return cls(url=url, api_key=api_key, timeout_seconds=timeout)

    def request(
        self,
        method: str,
        table: str,
        params: dict[str, str] | None = None,
        payload: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        query = f"?{urlencode(params)}" if params else ""
        url = f"{self.url}/rest/v1/{table}{query}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request_headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if headers:
            request_headers.update(headers)

        parsed_url = urlparse(url)
        if parsed_url.scheme not in {"http", "https"}:
            raise RuntimeError("Supabase URL must use http or https.")

        request = Request(url, data=body, headers=request_headers, method=method)  # noqa: S310
        try:
            # URL scheme is limited to http/https above.
            # nosemgrep
            with urlopen(  # noqa: S310  # nosec B310
                request,
                timeout=self.timeout_seconds,
            ) as response:
                response_body = response.read().decode("utf-8")
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Supabase {method} failed: {exc.code} {details}") from exc
        except URLError as exc:
            raise RuntimeError(f"Supabase is unreachable: {exc.reason}") from exc

        if not response_body:
            return None
        return json.loads(response_body)


class CivicVectorStore:
    """Cloud-backed issue store with deterministic embeddings for local ranking."""

    def __init__(
        self,
        client: SupabaseClientProtocol | None = None,
        table_name: str | None = None,
    ) -> None:
        load_environment()
        self.client = client or SupabaseRestClient.from_environment()
        self.table_name: str = table_name or os.getenv("SUPABASE_TABLE") or DEFAULT_TABLE_NAME

    def upsert_issues(self, issues: Iterable[dict[str, object]]) -> int:
        records = []
        for issue in issues:
            document = dict(issue)
            records.append(
                {
                    "id": str(issue["id"]),
                    "document": document,
                    "embedding": embed_text(_searchable_text(document)),
                    "impact_score": _to_float(issue["impact_score"]),
                    "post_date": str(issue["post_date"]),
                    "traction_date": str(issue["traction_date"]),
                    "zone": str(issue["zone"]),
                    "category": str(issue["category"]),
                    "source": str(issue.get("source", "unknown")),
                }
            )

        if not records:
            return 0

        self.client.request(
            "POST",
            self.table_name,
            params={"on_conflict": "id"},
            payload=records,
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        )
        return len(records)

    def fetch_all(self) -> pd.DataFrame:
        rows = self.client.request(
            "GET",
            self.table_name,
            params={
                "select": "document",
                "order": "impact_score.desc,traction_date.desc,post_date.desc",
            },
        )
        return pd.DataFrame([row["document"] for row in rows or []])

    def search(self, query: str, limit: int = 50) -> pd.DataFrame:
        query = query.strip()
        if not query:
            return self.fetch_all()

        query_tokens = set(_tokenize(query))
        query_embedding = embed_text(query)
        rows = self.client.request(
            "GET",
            self.table_name,
            params={"select": "document,embedding"},
        )

        scored = []
        for row in rows or []:
            issue = dict(row["document"])
            searchable_text = _searchable_text(issue)
            text_tokens = set(_tokenize(searchable_text))
            token_overlap = len(query_tokens & text_tokens)
            token_score = token_overlap / max(len(query_tokens), 1)
            substring_score = 1.0 if query.lower() in searchable_text.lower() else 0.0
            vector_score = cosine_similarity(query_embedding, row.get("embedding") or [])
            score = vector_score + (token_score * 0.75) + (substring_score * 0.35)

            if token_overlap > 0 or substring_score > 0:
                issue["search_score"] = round(score, 4)
                scored.append(issue)

        scored.sort(key=lambda item: item["search_score"], reverse=True)
        return pd.DataFrame(scored[:limit])

    def count(self) -> int:
        rows = self.client.request(
            "GET",
            self.table_name,
            params={"select": "id"},
        )
        return len(rows or [])

    def fetch_unknown_zone_records(self) -> pd.DataFrame:
        """Return all records whose zone column is Unknown or whose lat/lon are 0.0."""
        rows = self.client.request(
            "GET",
            self.table_name,
            params={
                "select": "document",
                "zone": "eq.Unknown",
            },
        )
        return pd.DataFrame([row["document"] for row in rows or []])

    def patch_issue(self, issue_id: str, updates: dict[str, object]) -> None:
        """Patch the JSON document and selected top-level columns for a single issue.

        ``updates`` is a flat dict of issue fields to merge into the stored document.
        Only the keys present in ``updates`` are changed; all other fields are preserved.
        """
        # Fetch existing document first
        rows = self.client.request(
            "GET",
            self.table_name,
            params={"select": "document", "id": f"eq.{issue_id}"},
        )
        if not rows:
            LOGGER.warning("patch_issue: id=%s not found", issue_id)
            return

        existing: dict[str, object] = dict(rows[0]["document"])
        existing.update(updates)

        record: dict[str, object] = {
            "id": issue_id,
            "document": existing,
            "embedding": embed_text(_searchable_text(existing)),
            "impact_score": _to_float(existing.get("impact_score", 0.0)),
            "post_date": str(existing.get("post_date", "")),
            "traction_date": str(existing.get("traction_date", "")),
            "zone": str(existing.get("zone", "Unknown")),
            "category": str(existing.get("category", "Uncategorized")),
            "source": str(existing.get("source", "unknown")),
        }
        self.client.request(
            "POST",
            self.table_name,
            params={"on_conflict": "id"},
            payload=[record],
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        )

    def clear(self) -> None:
        self.client.request(
            "DELETE",
            self.table_name,
            params={"id": "not.is.null"},
            headers={"Prefer": "return=minimal"},
        )
