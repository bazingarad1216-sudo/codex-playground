from __future__ import annotations

import os
import random
from pathlib import Path

from dog_nutrition.foods_db import connect_db, get_food_nutrients, init_db


def main() -> None:
    db_path = Path(os.environ.get("FOODS_DB_PATH", "foods.db")).resolve()
    with connect_db(db_path) as conn:
        init_db(conn)
        foods = conn.execute("SELECT COUNT(*) AS c FROM foods").fetchone()["c"]
        meta = conn.execute("SELECT COUNT(*) AS c FROM nutrient_meta").fetchone()["c"]
        fn = conn.execute("SELECT COUNT(*) AS c FROM food_nutrients").fetchone()["c"]
        print(f"db={db_path}")
        print(f"foods={foods}")
        print(f"nutrient_meta={meta}")
        print(f"food_nutrients={fn}")

        rows = conn.execute("SELECT id, name FROM foods ORDER BY id LIMIT 100").fetchall()
        if not rows:
            print("sample_food=None")
            return
        sample = random.choice(rows)
        nutrients = get_food_nutrients(conn, int(sample["id"]))
        print(f"sample_food={sample['name']}")
        print(f"sample_nutrient_rows={len(nutrients)}")


if __name__ == "__main__":
    main()
