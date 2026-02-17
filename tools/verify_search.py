from __future__ import annotations

import os
from pathlib import Path

from dog_nutrition.foods_db import connect_db, init_db, search_foods
from dog_nutrition.search import search_foods_cn


def main() -> None:
    db_path = Path(os.environ.get("FOODS_DB_PATH", "foods.db")).resolve()
    with connect_db(db_path) as conn:
        init_db(conn)
        hits_token_and = search_foods(conn, "chicken breast", limit=20)
        hits_search_foods = search_foods(conn, "chicken breast", limit=20)
        hits_search_cn = search_foods_cn(conn, "鸡胸肉", limit=20)

    print(f"token_and_hits={len(hits_token_and)}")
    print(f"search_foods('chicken breast')_hits={len(hits_search_foods)}")
    print(f"search_foods_cn('鸡胸肉')_hits={len(hits_search_cn)}")


if __name__ == "__main__":
    main()
