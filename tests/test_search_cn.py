from pathlib import Path

from dog_nutrition.foods_db import connect_db, init_db, search_foods, upsert_food
from dog_nutrition.search import expand_query, search_foods_cn


def test_search_foods_cn_chicken_breast_match(tmp_path: Path) -> None:
    db_path = tmp_path / "foods.db"
    with connect_db(db_path) as conn:
        init_db(conn)
        upsert_food(
            conn,
            name="Chicken, broiler or fryers, breast, skinless, boneless, meat only, raw",
            kcal_per_100g=120.0,
            source="fdc",
            fdc_id=1,
        )
        upsert_food(conn, name="Hummus, commercial", kcal_per_100g=166.0, source="fdc", fdc_id=2)
        conn.commit()

        hits_en = search_foods(conn, "chicken breast", limit=10)
        hits_cn = search_foods_cn(conn, "鸡胸肉", limit=10)

    assert len(hits_en) >= 1
    assert any("breast" in h.name.lower() for h in hits_en)

    assert len(hits_cn) >= 1
    names = [h.food.name.lower() for h in hits_cn]
    assert any("chicken" in name and "breast" in name for name in names)


def test_expand_query_contains_chicken_tokens() -> None:
    expanded = expand_query("鸡胸肉")
    lowered = {item.lower() for item in expanded}
    assert "chicken breast" in lowered
    assert "chicken" in lowered
    assert "breast" in lowered
