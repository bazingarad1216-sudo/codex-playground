from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .nutrients import KEY_NUTRIENTS
from .toxicity import is_toxic_food_name


@dataclass(frozen=True)
class FoodRecord:
    id: int
    name: str
    kcal_per_100g: float
    source: str
    fdc_id: int | None


@dataclass(frozen=True)
class NutrientValue:
    nutrient_key: str
    display_name: str
    amount_per_100g: float
    unit: str
    group: str


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
        CREATE TABLE IF NOT EXISTS nutrient_meta (
            nutrient_key TEXT PRIMARY KEY,
            nutrient_name TEXT NOT NULL,
            unit TEXT NOT NULL,
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
            FOREIGN KEY(nutrient_key) REFERENCES nutrient_meta(nutrient_key)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_food_nutrients_key ON food_nutrients(nutrient_key)")
    conn.commit()


def upsert_food(
    conn: sqlite3.Connection,
    *,
    name: str,
    kcal_per_100g: float,
    source: str,
    fdc_id: int | None,
) -> int:
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("Food name cannot be empty")
    if kcal_per_100g < 0:
        raise ValueError("kcal_per_100g must be >= 0")

    if fdc_id is None:
        cur = conn.execute(
            "INSERT INTO foods(name, kcal_per_100g, source, fdc_id) VALUES (?, ?, ?, NULL)",
            (normalized_name, kcal_per_100g, source),
        )
        return int(cur.lastrowid)

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
    row = conn.execute(
        "SELECT id FROM foods WHERE source = ? AND fdc_id = ?",
        (source, fdc_id),
    ).fetchone()
    if row is None:
        raise RuntimeError("Failed to upsert food")
    return int(row["id"])


def upsert_nutrient_meta(
    conn: sqlite3.Connection,
    *,
    nutrient_key: str,
    nutrient_name: str,
    unit: str,
    fdc_nutrient_number: str | None = None,
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


def get_food_nutrients(conn: sqlite3.Connection, food_id: int) -> list[NutrientValue]:
    rows = conn.execute(
        """
        SELECT fn.nutrient_key, nm.nutrient_name, fn.amount_per_100g, nm.unit
        FROM food_nutrients fn
        JOIN nutrient_meta nm ON nm.nutrient_key = fn.nutrient_key
        WHERE fn.food_id = ?
        ORDER BY fn.nutrient_key
        """,
        (food_id,),
    ).fetchall()
    return [
        NutrientValue(
            nutrient_key=row["nutrient_key"],
            display_name=row["nutrient_name"],
            amount_per_100g=row["amount_per_100g"],
            unit=row["unit"],
            group=KEY_NUTRIENTS.get(row["nutrient_key"], ("", "", "其他"))[2],
        )
        for row in rows
    ]


def _normalize_query(query: str) -> str:
    q = query.lower().strip()
    q = re.sub(r"[,.\-_/()\[\]{}]+", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    return q


def _query_to_tokens(query: str) -> tuple[str, list[str]]:
    normalized = _normalize_query(query)
    if not normalized:
        return normalized, []
    return normalized, [token for token in normalized.split(" ") if token]


def search_foods(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 20,
    include_toxic: bool = False,
) -> list[FoodRecord]:
    if limit <= 0:
        raise ValueError("limit must be > 0")

    q, tokens = _query_to_tokens(query)
    if not q:
        return []
    if tokens:
        where_clause = " AND ".join(["lower(name) LIKE ?" for _ in tokens])
        params = [f"%{token}%" for token in tokens]
    else:
        where_clause = "lower(name) LIKE ?"
        params = [f"%{q}%"]

    rows = conn.execute(
        f"""
        SELECT id, name, kcal_per_100g, source, fdc_id
        FROM foods
        WHERE {where_clause}
        ORDER BY name ASC, id ASC
        LIMIT ?
        """,
        [*params, limit * 3],
    ).fetchall()

    records = [
        FoodRecord(
            id=row["id"],
            name=row["name"],
            kcal_per_100g=row["kcal_per_100g"],
            source=row["source"],
            fdc_id=row["fdc_id"],
        )
        for row in rows
    ]
    if include_toxic:
        return records[:limit]
    safe = [item for item in records if not is_toxic_food_name(item.name)]
    return safe[:limit]


def calculate_kcal_for_grams(*, kcal_per_100g: float, grams: float) -> float:
    if kcal_per_100g < 0:
        raise ValueError("kcal_per_100g must be >= 0")
    if grams < 0:
        raise ValueError("grams must be >= 0")
    return (kcal_per_100g * grams) / 100.0
