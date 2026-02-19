from __future__ import annotations

import csv
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
_ZH_ALIAS_SEED_PATH = Path("data/aliases/zh_seed.csv")


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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_foods_name ON foods(name)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS food_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            food_id INTEGER NOT NULL,
            lang TEXT NOT NULL,
            alias TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(food_id) REFERENCES foods(id) ON DELETE CASCADE,
            UNIQUE(lang, alias, food_id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_food_aliases_lang_alias ON food_aliases(lang, alias)")
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


def add_food_alias(conn: sqlite3.Connection, food_id: int, lang: str, alias: str) -> None:
    normalized_alias = alias.strip()
    normalized_lang = lang.strip().lower()
    if not normalized_alias:
        raise ValueError("alias cannot be empty")
    if not normalized_lang:
        raise ValueError("lang cannot be empty")
    conn.execute(
        """
        INSERT OR IGNORE INTO food_aliases(food_id, lang, alias)
        VALUES (?, ?, ?)
        """,
        (food_id, normalized_lang, normalized_alias),
    )
    conn.commit()


def delete_food_alias(conn: sqlite3.Connection, alias_id: int) -> None:
    conn.execute("DELETE FROM food_aliases WHERE id = ?", (alias_id,))
    conn.commit()


def get_food_aliases(conn: sqlite3.Connection, food_id: int, lang: str = "zh") -> list[str]:
    rows = conn.execute(
        "SELECT alias FROM food_aliases WHERE food_id = ? AND lang = ? ORDER BY alias ASC",
        (food_id, lang.strip().lower()),
    ).fetchall()
    return [str(row["alias"]) for row in rows]


def list_aliases(conn: sqlite3.Connection, lang: str = "zh") -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT a.id, a.food_id, a.lang, a.alias, a.created_at, f.name AS food_name
        FROM food_aliases AS a
        JOIN foods AS f ON f.id = a.food_id
        WHERE a.lang = ?
        ORDER BY a.food_id ASC, a.alias ASC
        """,
        (lang.strip().lower(),),
    ).fetchall()


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


def search_foods_by_alias(
    conn: sqlite3.Connection,
    query: str,
    *,
    lang: str = "zh",
    limit: int = 20,
) -> list[FoodRecord]:
    normalized_query = query.strip().lower()
    if not normalized_query:
        return []

    rows = conn.execute(
        """
        SELECT f.id, f.name, f.kcal_per_100g, f.source, f.fdc_id
        FROM food_aliases AS a
        JOIN foods AS f ON f.id = a.food_id
        WHERE a.lang = ? AND lower(a.alias) LIKE ?
        ORDER BY a.alias ASC, f.name ASC
        LIMIT ?
        """,
        (lang.strip().lower(), f"%{normalized_query}%", limit),
    ).fetchall()
    return _rows_to_records(rows)


def _load_seed_alias_map() -> dict[str, list[str]]:
    if not _ZH_ALIAS_SEED_PATH.exists():
        return {}

    mapping: dict[str, list[str]] = {}
    with _ZH_ALIAS_SEED_PATH.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            alias = (row.get("alias") or "").strip().lower()
            expands_to = (row.get("expands_to") or "").strip()
            if not alias or not expands_to:
                continue
            candidates = [item.strip().lower() for item in expands_to.split("|") if item.strip()]
            if not candidates:
                continue
            mapping[alias] = candidates
    return mapping


def expand_query(query: str) -> list[str]:
    normalized_query = query.strip().lower()
    expanded = [normalized_query]

    if "鸡胸肉" in query:
        expanded.extend(["chicken breast", "chicken", "breast"])
    elif "鸡肉" in query:
        expanded.extend(["chicken", "chicken drumstick", "chicken breast"])
    elif "鸡蛋" in query:
        expanded.extend(["egg", "eggs"])

    seed_map = _load_seed_alias_map()
    expanded.extend(seed_map.get(normalized_query, []))

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
    merged: dict[int, tuple[int, FoodRecord]] = {}

    for record in search_foods_by_alias(conn, query, lang="zh", limit=limit):
        merged.setdefault(record.id, (0, record))

    for candidate in expand_query(query):
        for record in search_foods(conn, candidate, limit=limit):
            merged.setdefault(record.id, (1, record))

    ranked = list(merged.values())
    raw_query = query.strip()
    if "鸡胸" in raw_query or "鸡肉" in raw_query:
        ranked.sort(
            key=lambda pair: (
                pair[0],
                "chicken" not in pair[1].name.lower(),
                pair[1].name.lower(),
            )
        )
    else:
        ranked.sort(key=lambda pair: (pair[0], pair[1].name.lower()))
    return [pair[1] for pair in ranked[:limit]]


def calculate_kcal_for_grams(*, kcal_per_100g: float, grams: float) -> float:
    if kcal_per_100g < 0:
        raise ValueError("kcal_per_100g must be >= 0")
    if grams < 0:
        raise ValueError("grams must be >= 0")
    return (kcal_per_100g * grams) / 100.0
