from __future__ import annotations

import os
from pathlib import Path

from dog_nutrition.foods_db import connect_db, describe_search_query, init_db, search_foods, upsert_food
from dog_nutrition.search import expand_query, search_foods_cn


def _top3_names_en(rows) -> list[str]:
    return [row.name for row in rows[:3]]


def _top3_names_cn(rows) -> list[str]:
    return [row.food.name for row in rows[:3]]


def _seed_verify_records(conn) -> None:
    fixtures = [
        ("Egg, whole, raw, fresh", 143.0, 91001),
        ("Egg, white, raw, fresh", 52.0, 91002),
        ("Chicken, broilers or fryers, breast, meat only, cooked", 165.0, 91003),
        ("Chicken, stewing, meat only, cooked", 190.0, 91004),
        ("Sweet potato, cooked, baked in skin, flesh", 90.0, 91005),
    ]
    for name, kcal, fdc_id in fixtures:
        upsert_food(conn, name=name, kcal_per_100g=kcal, source="verify", fdc_id=fdc_id)
    conn.commit()


def main() -> None:
    db_path = Path(os.environ.get("FOODS_DB_PATH", "foods.db")).resolve()
    en_queries = ["chicken", "breast", "chicken breast", "chicken, breast"]
    cn_queries = ["鸡蛋", "鸡胸肉", "鸡肉", "鸡"]

    with connect_db(db_path) as conn:
        init_db(conn)
        _seed_verify_records(conn)
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
        chicken_breast_hits = search_foods(conn, "chicken breast", limit=10)
        assert chicken_breast_hits and all(
            "chicken" in row.name.lower() and "breast" in row.name.lower()
            for row in chicken_breast_hits
        )

        egg_terms = [term.lower() for term in expand_query("鸡蛋")]
        assert "egg" in egg_terms
        assert "whole" not in egg_terms
        assert "chicken" not in egg_terms

        egg_hits = search_foods_cn(conn, "鸡蛋", limit=10)
        assert egg_hits and "egg" in egg_hits[0].food.name.lower()

        chicken_hits = search_foods_cn(conn, "鸡胸肉", limit=10)
        assert chicken_hits and any(
            "chicken" in row.food.name.lower() and "breast" in row.food.name.lower()
            for row in chicken_hits
        )


if __name__ == "__main__":
    main()
