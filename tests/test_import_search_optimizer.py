from dog_nutrition.foods_db import connect_db, init_db, search_foods, upsert_food
from dog_nutrition.search import search_foods_cn


def test_import_search_optimizer_paths(tmp_path) -> None:
    conn = connect_db(tmp_path / "foods.sqlite")
    init_db(conn)
    upsert_food(conn, name="Chicken, broiler or fryers, breast, meat only", kcal_per_100g=165.0, source="fdc", fdc_id=1)
    upsert_food(conn, name="Egg, whole, cooked", kcal_per_100g=155.0, source="fdc", fdc_id=2)
    conn.commit()

    en = search_foods(conn, "chicken breast")
    assert any("breast" in r.name.lower() for r in en)

    cn = search_foods_cn(conn, "鸡蛋")
    assert cn
    assert "egg" in cn[0].food.name.lower()
    conn.close()
