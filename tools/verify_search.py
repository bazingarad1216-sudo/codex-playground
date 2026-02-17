from __future__ import annotations

import os
from pathlib import Path

from dog_nutrition.foods_db import connect_db, init_db, search_foods
from dog_nutrition.search import search_foods_cn


def _top3_names_en(rows) -> list[str]:
    return [row.name for row in rows[:3]]


def _top3_names_cn(rows) -> list[str]:
    return [row.food.name for row in rows[:3]]


def main() -> None:
    db_path = Path(os.environ.get("FOODS_DB_PATH", "foods.db")).resolve()
    en_queries = ["chicken", "breast", "chicken breast"]
    cn_queries = ["鸡蛋", "鸡胸肉", "鸡肉", "鸡"]

    with connect_db(db_path) as conn:
        init_db(conn)
        print(f"db={db_path}")

        for query in en_queries:
            hits = search_foods(conn, query, limit=20)
            print(f"EN query={query!r} hits={len(hits)} top3={_top3_names_en(hits)}")

        for query in cn_queries:
            hits = search_foods_cn(conn, query, limit=20)
            print(f"CN query={query!r} hits={len(hits)} top3={_top3_names_cn(hits)}")


if __name__ == "__main__":
    main()
