from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dog_nutrition.foods_db import connect_db, init_db, search_foods, search_foods_cn, upsert_food


def _seed(conn) -> None:
    upsert_food(
        conn,
        name="Chicken, broilers or fryers, breast, meat only, cooked, roasted",
        kcal_per_100g=165.0,
        source="fdc",
        fdc_id=1001,
    )
    upsert_food(conn, name="Chicken drumstick, meat only", kcal_per_100g=161.0, source="fdc", fdc_id=1002)
    upsert_food(conn, name="Egg, whole, cooked", kcal_per_100g=155.0, source="fdc", fdc_id=1003)
    upsert_food(conn, name="Onion, raw", kcal_per_100g=40.0, source="fdc", fdc_id=1004)
    upsert_food(conn, name="Chocolate, dark", kcal_per_100g=546.0, source="fdc", fdc_id=1005)
    conn.commit()


def _names(rows) -> list[str]:
    return [item.name for item in rows]


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "verify_foods.sqlite"
        conn = connect_db(db_path)
        init_db(conn)
        _seed(conn)

        en = search_foods(conn, "chicken breast")
        en_names = _names(en)
        assert len(en_names) > 0, "EN search 'chicken breast' must return > 0"
        assert any("chicken" in name.lower() and "breast" in name.lower() for name in en_names), (
            "EN search must include a chicken breast result"
        )

        cn_breast = search_foods_cn(conn, "鸡胸肉")
        cn_breast_names = _names(cn_breast)
        assert len(cn_breast_names) > 0, "CN search '鸡胸肉' must return > 0"
        assert any("chicken" in name.lower() for name in cn_breast_names), (
            "CN search '鸡胸肉' must include chicken food names"
        )

        cn_chicken = search_foods_cn(conn, "鸡肉")
        cn_chicken_names = _names(cn_chicken)
        assert len(cn_chicken_names) > 0, "CN search '鸡肉' must return > 0"
        assert any("chicken" in name.lower() for name in cn_chicken_names), (
            "CN search '鸡肉' must include chicken food names"
        )

        print("EN chicken breast > 0:", len(en_names), en_names)
        print("CN 鸡胸肉 > 0 and contains chicken:", len(cn_breast_names), cn_breast_names)
        print("CN 鸡肉 > 0 and contains chicken:", len(cn_chicken_names), cn_chicken_names)

        conn.close()


if __name__ == "__main__":
    main()
