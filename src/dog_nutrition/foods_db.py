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
    kcal_per_100g: float | None
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

_DEFAULT_ZH_ALIASES: dict[str, tuple[str, int]] = {
    "chicken breast": ("鸡胸肉", 100),
    "beef shank": ("牛腱", 95),
    "beef brisket": ("牛腩", 90),
    "lamb, leg": ("羊腿", 95),
    "lamb leg": ("羊腿", 95),
    "salmon": ("三文鱼", 80),
    "broccoli": ("西兰花", 70),
    "carrot": ("胡萝卜", 70),
    "egg": ("鸡蛋", 100),
}


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
        CREATE TABLE IF NOT EXISTS food_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            food_id INTEGER NOT NULL,
            lang TEXT NOT NULL,
            alias TEXT NOT NULL,
            weight INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(food_id) REFERENCES foods(id) ON DELETE CASCADE,
            UNIQUE(lang, alias, food_id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_food_aliases_lang_alias ON food_aliases(lang, alias)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS nutrient_meta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nutrient_code TEXT,
            nutrient_name TEXT,
            unit TEXT,
            UNIQUE(nutrient_code, nutrient_name)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS food_nutrients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            food_id INTEGER NOT NULL,
            nutrient_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            FOREIGN KEY(food_id) REFERENCES foods(id) ON DELETE CASCADE,
            FOREIGN KEY(nutrient_id) REFERENCES nutrient_meta(id) ON DELETE CASCADE,
            UNIQUE(food_id, nutrient_id)
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
    energy_estimated: bool = False,
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


def upsert_food_nutrient(
    conn: sqlite3.Connection,
    *,
    food_id: int,
    nutrient_code: str | None,
    nutrient_name: str,
    unit: str | None,
    amount: float,
) -> None:
    if amount < 0:
        return
    code = (nutrient_code or "").strip() or None
    name = nutrient_name.strip()
    if not name:
        return
    row = conn.execute(
        "SELECT id FROM nutrient_meta WHERE nutrient_code IS ? AND nutrient_name = ?",
        (code, name),
    ).fetchone()
    if row is None:
        cur = conn.execute(
            "INSERT INTO nutrient_meta(nutrient_code, nutrient_name, unit) VALUES (?, ?, ?)",
            (code, name, unit),
        )
        nutrient_id = int(cur.lastrowid)
    else:
        nutrient_id = int(row["id"])

    conn.execute(
        """
        INSERT INTO food_nutrients(food_id, nutrient_id, amount)
        VALUES (?, ?, ?)
        ON CONFLICT(food_id, nutrient_id)
        DO UPDATE SET amount = excluded.amount
        """,
        (food_id, nutrient_id, amount),
    )


def add_food_alias(conn: sqlite3.Connection, food_id: int, lang: str, alias: str, weight: int = 0) -> None:
    normalized_alias = alias.strip()
    normalized_lang = lang.strip().lower()
    if not normalized_alias:
        raise ValueError("alias cannot be empty")
    if not normalized_lang:
        raise ValueError("lang cannot be empty")
    conn.execute(
        """
        INSERT INTO food_aliases(food_id, lang, alias, weight)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(lang, alias, food_id)
        DO UPDATE SET weight = excluded.weight
        """,
        (food_id, normalized_lang, normalized_alias, weight),
    )
    conn.commit()


def seed_default_zh_aliases(conn: sqlite3.Connection) -> None:
    for keyword, (alias, weight) in _DEFAULT_ZH_ALIASES.items():
        rows = conn.execute(
            "SELECT id FROM foods WHERE lower(name) LIKE ?",
            (f"%{keyword.lower()}%",),
        ).fetchall()
        for row in rows:
            conn.execute(
                """
                INSERT OR IGNORE INTO food_aliases(food_id, lang, alias, weight)
                VALUES (?, 'zh', ?, ?)
                """,
                (int(row["id"]), alias, weight),
            )
    conn.commit()


def delete_food_alias(conn: sqlite3.Connection, alias_id: int) -> None:
    conn.execute("DELETE FROM food_aliases WHERE id = ?", (alias_id,))
    conn.commit()


def get_food_aliases(conn: sqlite3.Connection, food_id: int, lang: str = "zh") -> list[str]:
    rows = conn.execute(
        "SELECT alias FROM food_aliases WHERE food_id = ? AND lang = ? ORDER BY weight DESC, alias ASC",
        (food_id, lang.strip().lower()),
    ).fetchall()
    return [str(row["alias"]) for row in rows]


def list_aliases(conn: sqlite3.Connection, lang: str = "zh") -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT a.id, a.food_id, a.lang, a.alias, a.weight, a.created_at, f.name AS food_name
        FROM food_aliases AS a
        JOIN foods AS f ON f.id = a.food_id
        WHERE a.lang = ?
        ORDER BY a.weight DESC, a.food_id ASC, a.alias ASC
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


def _rows_to_records(rows: list[sqlite3.Row], *, require_kcal: bool = False) -> list[FoodRecord]:
    records: list[FoodRecord] = []
    for row in rows:
        if is_toxic_food_name(row["name"]):
            continue
        kcal = row["kcal_per_100g"]
        if require_kcal and kcal is None:
            continue
        records.append(
            FoodRecord(
                id=row["id"],
                name=row["name"],
                kcal_per_100g=float(kcal) if kcal is not None else None,
                source=row["source"],
                fdc_id=row["fdc_id"],
            )
        )
    return records


def search_foods(conn: sqlite3.Connection, query: str, *, limit: int = 20, require_kcal: bool = True) -> list[FoodRecord]:
    if limit <= 0:
        raise ValueError("limit must be > 0")

    normalized_query = query.strip().lower()
    if not normalized_query:
        return []

    tokens = _tokenize_query(normalized_query)
    if not tokens:
        return []

    where_clause = "lower(name) LIKE ?" if len(tokens) == 1 else " AND ".join("lower(name) LIKE ?" for _ in tokens)
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
    records = _rows_to_records(rows, require_kcal=require_kcal)
    if records:
        return records

    where_clause = " OR ".join("lower(name) LIKE ?" for _ in tokens)
    rows = conn.execute(
        f"""
        SELECT id, name, kcal_per_100g, source, fdc_id
        FROM foods
        WHERE {where_clause}
        ORDER BY name ASC
        LIMIT ?
        """,
        [*params[:-1], limit],
    ).fetchall()
    return _rows_to_records(rows, require_kcal=require_kcal)


def search_foods_by_alias(
    conn: sqlite3.Connection,
    query: str,
    *,
    lang: str = "zh",
    limit: int = 20,
    require_kcal: bool = True,
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
        ORDER BY a.weight DESC, a.alias ASC, f.name ASC
        LIMIT ?
        """,
        (lang.strip().lower(), f"%{normalized_query}%", limit),
    ).fetchall()
    return _rows_to_records(rows, require_kcal=require_kcal)


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
            if candidates:
                mapping[alias] = candidates
    return mapping


def expand_query(query: str) -> list[str]:
    normalized_query = query.strip().lower()
    expanded = [normalized_query]

    if "鸡胸肉" in query:
        expanded.extend(["chicken breast", "chicken", "breast"])
    elif "鸡肉" in query:
        expanded.extend(["chicken", "chicken drumstick", "chicken breast"])
    elif query.strip() == "鸡":
        expanded.extend(["chicken", "chicken breast", "chicken drumstick"])
    elif any(token in query for token in ("鸡蛋", "蛋白", "蛋黄", "全蛋")):
        expanded.extend(["egg", "whole egg", "egg yolk", "egg white"])

    seed_map = _load_seed_alias_map()
    expanded.extend(seed_map.get(normalized_query, []))

    seen: set[str] = set()
    deduped: list[str] = []
    for item in expanded:
        if item and item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def _cn_intent_weights(query: str, name: str) -> tuple[int, int, int]:
    q = query.strip()
    n = name.lower()
    egg_query = any(token in q for token in ("鸡蛋", "蛋白", "蛋黄", "全蛋"))
    breast_query = "鸡胸肉" in q
    chicken_query = q == "鸡" or "鸡肉" in q or breast_query

    egg_score = 0
    chicken_score = 0
    breast_score = 0
    if "egg" in n:
        egg_score = 2 if egg_query else 0
    if "chicken" in n:
        chicken_score = 2 if chicken_query else 0
    if "breast" in n:
        breast_score = 2 if breast_query else 0

    if egg_query and "chicken" in n and "egg" not in n:
        chicken_score -= 2
    return egg_score, chicken_score, breast_score


def search_foods_cn(conn: sqlite3.Connection, query: str, *, limit: int = 20, require_kcal: bool = True) -> list[FoodRecord]:
    merged: dict[int, tuple[int, int, FoodRecord]] = {}

    for record in search_foods_by_alias(conn, query, lang="zh", limit=limit, require_kcal=require_kcal):
        merged[record.id] = (0, 10_000, record)

    for candidate in expand_query(query):
        priority = max(1, len(candidate))
        for record in search_foods(conn, candidate, limit=limit, require_kcal=require_kcal):
            existing = merged.get(record.id)
            # alias-first, then longer matched expansion first
            rank = (1, -priority, record)
            if existing is None or rank < existing:
                merged[record.id] = rank

    ranked = list(merged.values())
    ranked.sort(
        key=lambda pair: (
            pair[0],
            -_cn_intent_weights(query, pair[2].name)[0],
            -_cn_intent_weights(query, pair[2].name)[2],
            -_cn_intent_weights(query, pair[2].name)[1],
            pair[1],
            pair[2].name.lower(),
        )
    )
    return [pair[2] for pair in ranked[:limit]]


def calculate_kcal_for_grams(*, kcal_per_100g: float, grams: float) -> float:
    if kcal_per_100g < 0:
        raise ValueError("kcal_per_100g must be >= 0")
    if grams < 0:
        raise ValueError("grams must be >= 0")
    return (kcal_per_100g * grams) / 100.0
