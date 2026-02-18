from pathlib import Path

from dog_nutrition.foods_db import connect_db, init_db, upsert_food
from dog_nutrition.search import search_foods_cn


def test_cn_chicken_breast_hits_fdc_style_name(tmp_path: Path) -> None:
    db_path = tmp_path / "foods.db"
    with connect_db(db_path) as conn:
        init_db(conn)
        upsert_food(
            conn,
            name="Chicken, broiler or fryers, breast, skinless, boneless, meat only, cooked, braised",
            kcal_per_100g=180.0,
            source="fdc",
            fdc_id=32,
        )
        upsert_food(
            conn,
            name="Chicken, broiler or fryers, drumstick, meat only, raw",
            kcal_per_100g=170.0,
            source="fdc",
            fdc_id=33,
        )
        conn.commit()

        hits_breast = search_foods_cn(conn, "鸡胸肉", limit=10)
        hits_meat = search_foods_cn(conn, "鸡肉", limit=10)

    assert len(hits_breast) >= 1
    assert any("chicken" in h.food.name.lower() and "breast" in h.food.name.lower() for h in hits_breast[:3])

    assert len(hits_meat) >= 1
    assert any("chicken" in h.food.name.lower() for h in hits_meat)
