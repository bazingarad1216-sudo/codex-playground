from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FoodRecord:
    id: int
    name: str
    kcal_per_100g: float
    source: str
    fdc_id: int | None


_TOXIC_KEYWORDS = (
    "onion",
    "chocolate",
    "grape",
    "xylitol",
    "葡萄",
    "木糖醇",
    "洋葱",
    "巧克力",
)
_TOKEN_SPLIT_RE = re.compile(r"[\s,;，；、]+")
_STOPWORDS = {"and", "or", "&", "the"}
_MAX_QUERY_TOKENS = 6


def connect_db(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS foods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            kcal_per_100g REAL NOT NULL,
            source TEXT NOT NULL,
            fdc_id INTEGER,
            UNIQUE(source, fdc_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_foods_name ON foods(name)"
    )
    conn.commit()


def upsert_food(
    conn: sqlite3.Connection,
    *,
    name: str,
    kcal_per_100g: float,
    source: str,
    fdc_id: int | None,
) -> None:
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("Food name cannot be empty")
    if kcal_per_100g < 0:
        raise ValueError("kcal_per_100g must be >= 0")

    if fdc_id is None:
        conn.execute(
            "INSERT INTO foods(name, kcal_per_100g, source, fdc_id) VALUES (?, ?, ?, NULL)",
            (normalized_name, kcal_per_100g, source),
        )
    else:
        conn.execute(
            """
            INSERT INTO foods(name, kcal_per_100g, source, fdc_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(source, fdc_id)
            DO UPDATE SET
                name = excluded.name,
                kcal_per_100g = excluded.kcal_per_100g
            """,
            (normalized_name, kcal_per_100g, source, fdc_id),
        )


def is_toxic_food_name(name: str) -> bool:
    lowered = name.lower()
    return any(keyword in lowered for keyword in _TOXIC_KEYWORDS)


def _tokenize_query(query: str) -> list[str]:
    tokens = []
    for raw in _TOKEN_SPLIT_RE.split(query.lower()):
        token = raw.strip()
        if not token or token in _STOPWORDS:
            continue
        tokens.append(token)
        if len(tokens) >= _MAX_QUERY_TOKENS:
            break
    return tokens


def _rows_to_records(rows: list[sqlite3.Row]) -> list[FoodRecord]:
    return [
        FoodRecord(
            id=row["id"],
            name=row["name"],
            kcal_per_100g=row["kcal_per_100g"],
            source=row["source"],
            fdc_id=row["fdc_id"],
        )
        for row in rows
        if not is_toxic_food_name(row["name"])
    ]


def search_foods(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 20,
) -> list[FoodRecord]:
    if limit <= 0:
        raise ValueError("limit must be > 0")

    normalized_query = query.strip().lower()
    if not normalized_query:
        return []

    tokens = _tokenize_query(normalized_query)
    if not tokens:
        return []

    if len(tokens) == 1:
        where_clause = "lower(name) LIKE ?"
    else:
        where_clause = " AND ".join("lower(name) LIKE ?" for _ in tokens)

    params: list[object] = [f"%{token}%" for token in tokens]
    params.append(limit)
    rows = conn.execute(
        f"""
        SELECT id, name, kcal_per_100g, source, fdc_id
        FROM foods
        WHERE {where_clause}
        ORDER BY name ASC
        LIMIT ?
        """,
        params,
    ).fetchall()
    records = _rows_to_records(rows)
    if records:
        return records

    # Optional fallback: broaden to OR search when strict AND returns nothing.
    where_clause = " OR ".join("lower(name) LIKE ?" for _ in tokens)
    params = [f"%{token}%" for token in tokens]
    params.append(limit)
    rows = conn.execute(
        f"""
        SELECT id, name, kcal_per_100g, source, fdc_id
        FROM foods
        WHERE {where_clause}
        ORDER BY name ASC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return _rows_to_records(rows)


def expand_query(query: str) -> list[str]:
    normalized_query = query.strip().lower()
    expanded = [normalized_query]

    if "鸡胸肉" in query:
        expanded.extend(["chicken breast", "chicken", "breast"])
    elif "鸡肉" in query:
        expanded.extend(["chicken", "chicken drumstick", "chicken breast"])
    elif "鸡蛋" in query:
        expanded.extend(["egg", "eggs"])

    seen: set[str] = set()
    deduped: list[str] = []
    for item in expanded:
        if item and item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def search_foods_cn(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 20,
) -> list[FoodRecord]:
    merged: dict[int, FoodRecord] = {}
    for candidate in expand_query(query):
        for record in search_foods(conn, candidate, limit=limit):
            merged.setdefault(record.id, record)

    records = list(merged.values())
    raw_query = query.strip()
    if "鸡胸" in raw_query or "鸡肉" in raw_query:
        records.sort(key=lambda r: ("chicken" not in r.name.lower(), r.name.lower()))
    else:
        records.sort(key=lambda r: r.name.lower())
    return records[:limit]


def calculate_kcal_for_grams(*, kcal_per_100g: float, grams: float) -> float:
    if kcal_per_100g < 0:
        raise ValueError("kcal_per_100g must be >= 0")
    if grams < 0:
        raise ValueError("grams must be >= 0")
    return (kcal_per_100g * grams) / 100.0
