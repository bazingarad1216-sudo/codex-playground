from __future__ import annotations

import os
from pathlib import Path

from dog_nutrition.foods_db import connect_db, describe_search_query, search_foods
from dog_nutrition.search import expand_query, search_foods_cn


def _top3_names_en(rows) -> list[str]:
    return [row.name for row in rows[:3]]


def _top3_names_cn(rows) -> list[str]:
    return [row.food.name for row in rows[:3]]


def _assert_real_db_ready(db_path: Path) -> None:
    if not db_path.exists():
        raise SystemExit(
            "foods.db not found. Please import data first, e.g.: "
            "PYTHONPATH=src python -m dog_nutrition.fdc_import --db foods.db --input <path-to-fdc-json-or-csv>"
        )



def main() -> None:
    db_path = Path(os.environ.get("FOODS_DB_PATH", "foods.db")).resolve()
    _assert_real_db_ready(db_path)

    en_queries = ["chicken", "breast", "chicken breast", "chicken, breast"]
    cn_queries = ["鸡蛋", "鸡胸肉", "鸡肉", "鸡"]

    with connect_db(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM foods").fetchone()
        food_count = int(row["c"]) if row is not None else 0
        if food_count <= 0:
            raise SystemExit(
                "foods table is empty. Please import FDC data first, e.g.: "
                "PYTHONPATH=src python -m dog_nutrition.fdc_import --db foods.db --input <path-to-fdc-json-or-csv>"
            )

        print(f"db={db_path}")

        for query in en_queries:
            tokens, summary = describe_search_query(query)
            hits = search_foods(conn, query, limit=20)
            print(f"EN query={query!r} tokens={tokens} condition={summary} hits={len(hits)} top3={_top3_names_en(hits)}")

        for query in cn_queries:
            hits = search_foods_cn(conn, query, limit=20)
            print(f"CN query={query!r} hits={len(hits)} top3={_top3_names_cn(hits)}")

        # Hard assertions to verify tokenized AND, CN expansion, and egg intent behavior.
        assert describe_search_query("chicken, breast")[0] == ["chicken", "breast"]

        egg_terms = [term.lower() for term in expand_query("鸡蛋")]
        assert "egg" in egg_terms
        assert "whole" not in egg_terms
        assert "chicken" not in egg_terms

        chicken_breast_hits = search_foods(conn, "chicken breast", limit=10)
        assert chicken_breast_hits and any(
            "chicken" in row.name.lower() and "breast" in row.name.lower()
            for row in chicken_breast_hits
        )

        egg_hits = search_foods_cn(conn, "鸡蛋", limit=10)
        assert egg_hits and any("egg" in row.food.name.lower() for row in egg_hits)

        chicken_hits = search_foods_cn(conn, "鸡胸肉", limit=10)
        assert chicken_hits and any(
            "chicken" in row.food.name.lower() and "breast" in row.food.name.lower()
            for row in chicken_hits
        )


if __name__ == "__main__":
    main()
