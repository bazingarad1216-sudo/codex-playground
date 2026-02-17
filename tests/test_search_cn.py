from pathlib import Path

from dog_nutrition.foods_db import connect_db, init_db, search_foods, upsert_food
from dog_nutrition.search import search_foods_cn


def test_search_foods_cn_chicken_breast_match(tmp_path: Path) -> None:
    db_path = tmp_path / "foods.db"
    with connect_db(db_path) as conn:
        init_db(conn)
        upsert_food(conn, name="Chicken, broilers or fryers, breast, meat only, raw", kcal_per_100g=120.0, source="fdc", fdc_id=1)
        upsert_food(conn, name="Chicken, broilers or fryers, drumstick, meat only, raw", kcal_per_100g=140.0, source="fdc", fdc_id=2)
        conn.commit()

        hits = search_foods_cn(conn, "鸡胸肉", limit=10)

    names = [h.food.name.lower() for h in hits]
    assert hits
    assert any("chicken" in name for name in names)
    assert any("breast" in name for name in names)


def test_search_foods_token_and_match(tmp_path: Path) -> None:
    db_path = tmp_path / "foods.db"
    with connect_db(db_path) as conn:
        init_db(conn)
        upsert_food(conn, name="Chicken, broilers or fryers, breast, meat only, raw", kcal_per_100g=120.0, source="fdc", fdc_id=1)
        upsert_food(conn, name="Chicken, broilers or fryers, drumstick, meat only, raw", kcal_per_100g=140.0, source="fdc", fdc_id=2)
        conn.commit()

        hits = search_foods(conn, "chicken breast", limit=10)

    assert hits
    assert any("breast" in h.name.lower() for h in hits)
