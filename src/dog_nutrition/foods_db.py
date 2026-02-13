from __future__ import annotations

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


def search_foods(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 20,
) -> list[FoodRecord]:
    if limit <= 0:
        raise ValueError("limit must be > 0")

    rows = conn.execute(
        """
        SELECT id, name, kcal_per_100g, source, fdc_id
        FROM foods
        WHERE name LIKE ?
        ORDER BY name ASC
        LIMIT ?
        """,
        (f"%{query.strip()}%", limit),
    ).fetchall()
    return [
        FoodRecord(
            id=row["id"],
            name=row["name"],
            kcal_per_100g=row["kcal_per_100g"],
            source=row["source"],
            fdc_id=row["fdc_id"],
        )
        for row in rows
    ]


def calculate_kcal_for_grams(*, kcal_per_100g: float, grams: float) -> float:
    if kcal_per_100g < 0:
        raise ValueError("kcal_per_100g must be >= 0")
    if grams < 0:
        raise ValueError("grams must be >= 0")
    return (kcal_per_100g * grams) / 100.0
