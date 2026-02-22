from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dog_nutrition.foods_db import connect_db, init_db, search_foods, search_foods_cn, seed_default_zh_aliases, upsert_food


def _seed(conn) -> None:
    upsert_food(conn, name="Chicken, broilers or fryers, breast, meat only, cooked, roasted", kcal_per_100g=165.0, source="fdc", fdc_id=1001)
    upsert_food(conn, name="Chicken drumstick, meat only", kcal_per_100g=161.0, source="fdc", fdc_id=1002)
    upsert_food(conn, name="Egg, whole, cooked", kcal_per_100g=155.0, source="fdc", fdc_id=1003)
    upsert_food(conn, name="Lamb, leg, separable lean only", kcal_per_100g=206.0, source="fdc", fdc_id=1004)
    upsert_food(conn, name="Beef shank, separable lean", kcal_per_100g=201.0, source="fdc", fdc_id=1005)
    upsert_food(conn, name="Onion, raw", kcal_per_100g=40.0, source="fdc", fdc_id=1006)
    upsert_food(conn, name="Chocolate, dark", kcal_per_100g=546.0, source="fdc", fdc_id=1007)
    conn.commit()


def _names(rows) -> list[str]:
    return [item.name for item in rows]


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "verify_foods.sqlite"
        conn = connect_db(db_path)
        init_db(conn)
        _seed(conn)
        seed_default_zh_aliases(conn)

        en = search_foods(conn, "chicken breast")
        assert len(en) > 0

        egg = search_foods_cn(conn, "鸡蛋")
        assert egg, "鸡蛋检索必须有结果"
        egg_top3 = egg[:3]
        egg_positions = [idx for idx, row in enumerate(egg_top3) if "egg" in row.name.lower()]
        chicken_positions = [idx for idx, row in enumerate(egg_top3) if "chicken" in row.name.lower()]
        assert egg_positions, "鸡蛋 top3 必须包含 Egg"
        if chicken_positions:
            assert min(egg_positions) < min(chicken_positions), "鸡蛋结果中 Chicken 不得排在 Egg 前面"

        breast = search_foods_cn(conn, "鸡胸肉")
        assert breast and "chicken" in breast[0].name.lower() and "breast" in breast[0].name.lower(), "鸡胸肉 top1 必须是 chicken breast"

        lamb = search_foods_cn(conn, "羊腿")
        assert any("lamb" in name.lower() for name in _names(lamb))
        beef = search_foods_cn(conn, "牛霖")
        assert any("beef" in name.lower() or "shank" in name.lower() for name in _names(beef))

        print("PASS", _names(en), _names(egg_top3), _names(breast[:1]), _names(lamb[:3]), _names(beef[:3]))
        conn.close()


if __name__ == "__main__":
    main()
