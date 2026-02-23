from __future__ import annotations

import os
from pathlib import Path

from dog_nutrition.foods_db import connect_db, init_db, search_foods
from dog_nutrition.search import expand_query, search_foods_cn


QUERIES = ["鸡胸肉", "鸡肉", "红薯", "鸡蛋"]


def main() -> None:
    db_path = Path(os.environ.get("FOODS_DB_PATH", "foods.db")).resolve()
    with connect_db(db_path) as conn:
        init_db(conn)
        print(f"db={db_path}")
        for q in QUERIES:
            print(f"\nquery={q}")
            terms = expand_query(q)
            print(f"expanded={terms}")
            for term in terms:
                hit_count = len(search_foods(conn, term, limit=20))
                print(f"  term={term!r} hits={hit_count}")
            final_hits = search_foods_cn(conn, q, limit=5)
            print("  final_candidates=")
            for h in final_hits:
                print(f"    - {h.food.name} ({h.food.kcal_per_100g:.1f} kcal/100g)")


if __name__ == "__main__":
    main()
