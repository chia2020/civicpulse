from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd


DEFAULT_DB_PATH = Path("storage/civicpulse_vector.db")
EMBEDDING_DIMENSIONS = 128


def _tokenize(text: str) -> list[str]:
    return [
        token.strip(".,:;!?()[]{}\"'").lower()
        for token in text.split()
        if token.strip(".,:;!?()[]{}\"'")
    ]


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
    return sum(a * b for a, b in zip(left, right))


class CivicVectorStore:
    def __init__(self, path: Path = DEFAULT_DB_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS issues (
                    id TEXT PRIMARY KEY,
                    document TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    impact_score REAL NOT NULL,
                    post_date TEXT NOT NULL,
                    traction_date TEXT NOT NULL,
                    zone TEXT NOT NULL,
                    category TEXT NOT NULL,
                    source TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_issues_dashboard
                ON issues (impact_score DESC, traction_date DESC, post_date DESC)
                """
            )

    def upsert_issues(self, issues: Iterable[dict[str, object]]) -> int:
        count = 0
        with self._connect() as connection:
            for issue in issues:
                document = json.dumps(issue, sort_keys=True)
                searchable_text = " ".join(
                    str(issue.get(field, ""))
                    for field in ("title", "area", "zone", "category", "description", "source")
                )
                connection.execute(
                    """
                    INSERT INTO issues (
                        id, document, embedding, impact_score, post_date,
                        traction_date, zone, category, source
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        document = excluded.document,
                        embedding = excluded.embedding,
                        impact_score = excluded.impact_score,
                        post_date = excluded.post_date,
                        traction_date = excluded.traction_date,
                        zone = excluded.zone,
                        category = excluded.category,
                        source = excluded.source
                    """,
                    (
                        str(issue["id"]),
                        document,
                        json.dumps(embed_text(searchable_text)),
                        float(issue["impact_score"]),
                        str(issue["post_date"]),
                        str(issue["traction_date"]),
                        str(issue["zone"]),
                        str(issue["category"]),
                        str(issue.get("source", "unknown")),
                    ),
                )
                count += 1
        return count

    def fetch_all(self) -> pd.DataFrame:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT document
                FROM issues
                ORDER BY impact_score DESC, traction_date DESC
                """
            ).fetchall()
        return pd.DataFrame([json.loads(row["document"]) for row in rows])

    def search(self, query: str, limit: int = 20) -> pd.DataFrame:
        query_embedding = embed_text(query)
        with self._connect() as connection:
            rows = connection.execute("SELECT document, embedding FROM issues").fetchall()

        scored = []
        for row in rows:
            score = cosine_similarity(query_embedding, json.loads(row["embedding"]))
            issue = json.loads(row["document"])
            issue["search_score"] = round(score, 4)
            scored.append(issue)

        scored.sort(key=lambda item: item["search_score"], reverse=True)
        return pd.DataFrame(scored[:limit])

    def count(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM issues").fetchone()[0])
