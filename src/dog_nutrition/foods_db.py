from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .toxicity import is_toxic_food_name

_TOKEN_SPLIT_RE = re.compile(r"[\s,;，；、]+")
_STOPWORDS = {"and", "or", "&", "the"}
_MAX_QUERY_TOKENS = 6


@dataclass(frozen=True)
class FoodRecord:
    id: int
    name: str
    kcal_per_100g: float | None
    source: str
    fdc_id: int | None
    energy_estimated: int


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
            kcal_per_100g REAL,
            source TEXT NOT NULL,
            fdc_id INTEGER,
            energy_estimated INTEGER NOT NULL DEFAULT 0,
            UNIQUE(source, fdc_id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_foods_name ON foods(name)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS nutrient_meta (
            nutrient_key TEXT PRIMARY KEY,
            nutrient_name TEXT NOT NULL,
            unit TEXT,
            fdc_nutrient_number TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS food_nutrients (
            food_id INTEGER NOT NULL,
            nutrient_key TEXT NOT NULL,
            amount_per_100g REAL NOT NULL,
            PRIMARY KEY(food_id, nutrient_key),
            FOREIGN KEY(food_id) REFERENCES foods(id) ON DELETE CASCADE,
            FOREIGN KEY(nutrient_key) REFERENCES nutrient_meta(nutrient_key) ON DELETE CASCADE
        )
        """
    )
    conn.commit()


def upsert_food(
    conn: sqlite3.Connection,
    *,
    name: str,
    kcal_per_100g: float | None,
    source: str,
    fdc_id: int | None,
    energy_estimated: int = 0,
) -> int:
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("Food name cannot be empty")
    if kcal_per_100g is not None and kcal_per_100g < 0:
        raise ValueError("kcal_per_100g must be >= 0")

    if fdc_id is None:
        cur = conn.execute(
            "INSERT INTO foods(name, kcal_per_100g, source, fdc_id, energy_estimated) VALUES (?, ?, ?, NULL, ?)",
            (normalized_name, kcal_per_100g, source, int(energy_estimated)),
        )
        return int(cur.lastrowid)

    conn.execute(
        """
        INSERT INTO foods(name, kcal_per_100g, source, fdc_id, energy_estimated)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(source, fdc_id)
        DO UPDATE SET
            name = excluded.name,
            kcal_per_100g = excluded.kcal_per_100g,
            energy_estimated = excluded.energy_estimated
        """,
        (normalized_name, kcal_per_100g, source, fdc_id, int(energy_estimated)),
    )
    row = conn.execute("SELECT id FROM foods WHERE source = ? AND fdc_id = ?", (source, fdc_id)).fetchone()
    if row is None:
        raise RuntimeError("failed to locate upserted food")
    return int(row["id"])


def upsert_nutrient_meta(
    conn: sqlite3.Connection,
    *,
    nutrient_key: str,
    nutrient_name: str,
    unit: str | None,
    fdc_nutrient_number: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO nutrient_meta(nutrient_key, nutrient_name, unit, fdc_nutrient_number)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(nutrient_key)
        DO UPDATE SET
            nutrient_name = excluded.nutrient_name,
            unit = excluded.unit,
            fdc_nutrient_number = excluded.fdc_nutrient_number
        """,
        (nutrient_key, nutrient_name, unit, fdc_nutrient_number),
    )


def upsert_food_nutrient(
    conn: sqlite3.Connection,
    *,
    food_id: int,
    nutrient_key: str,
    amount_per_100g: float,
) -> None:
    conn.execute(
        """
        INSERT INTO food_nutrients(food_id, nutrient_key, amount_per_100g)
        VALUES (?, ?, ?)
        ON CONFLICT(food_id, nutrient_key)
        DO UPDATE SET amount_per_100g = excluded.amount_per_100g
        """,
        (food_id, nutrient_key, amount_per_100g),
    )


def get_food_nutrients(conn: sqlite3.Connection, food_id: int) -> dict[str, float]:
    rows = conn.execute(
        "SELECT nutrient_key, amount_per_100g FROM food_nutrients WHERE food_id = ?",
        (food_id,),
    ).fetchall()
    return {str(row["nutrient_key"]): float(row["amount_per_100g"]) for row in rows}


def _tokenize_query(query: str) -> list[str]:
    tokens: list[str] = []
    for raw in _TOKEN_SPLIT_RE.split(query.lower()):
        token = raw.strip()
        if not token or token in _STOPWORDS:
            continue
        tokens.append(token)
        if len(tokens) >= _MAX_QUERY_TOKENS:
            break
    return tokens


def _rows_to_records(rows: list[sqlite3.Row], *, include_toxic: bool) -> list[FoodRecord]:
    records: list[FoodRecord] = []
    for row in rows:
        if (not include_toxic) and is_toxic_food_name(str(row["name"])):
            continue
        kcal = row["kcal_per_100g"]
        records.append(
            FoodRecord(
                id=int(row["id"]),
                name=str(row["name"]),
                kcal_per_100g=float(kcal) if kcal is not None else None,
                source=str(row["source"]),
                fdc_id=int(row["fdc_id"]) if row["fdc_id"] is not None else None,
                energy_estimated=int(row["energy_estimated"]),
            )
        )
    return records


def search_foods(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 20,
    include_toxic: bool = False,
) -> list[FoodRecord]:
    if limit <= 0:
        raise ValueError("limit must be > 0")

    tokens = _tokenize_query(query.strip().lower())
    if not tokens:
        return []

    where_clause = "lower(name) LIKE ?" if len(tokens) == 1 else " AND ".join("lower(name) LIKE ?" for _ in tokens)
    params: list[object] = [f"%{token}%" for token in tokens]
    params.append(limit)
    rows = conn.execute(
        f"""
        SELECT id, name, kcal_per_100g, source, fdc_id, energy_estimated
        FROM foods
        WHERE {where_clause}
        ORDER BY name ASC
        LIMIT ?
        """,
        params,
    ).fetchall()

    records = _rows_to_records(rows, include_toxic=include_toxic)
    if records:
        return records

    where_clause_or = " OR ".join("lower(name) LIKE ?" for _ in tokens)
    rows = conn.execute(
        f"""
        SELECT id, name, kcal_per_100g, source, fdc_id, energy_estimated
        FROM foods
        WHERE {where_clause_or}
        ORDER BY name ASC
        LIMIT ?
        """,
        [*params[:-1], limit],
    ).fetchall()
    return _rows_to_records(rows, include_toxic=include_toxic)


def calculate_kcal_for_grams(*, kcal_per_100g: float, grams: float) -> float:
    if kcal_per_100g < 0:
        raise ValueError("kcal_per_100g must be >= 0")
    if grams < 0:
        raise ValueError("grams must be >= 0")
    return (kcal_per_100g * grams) / 100.0
