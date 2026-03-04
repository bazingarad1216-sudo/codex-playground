import pytest

from dog_nutrition.foods_db import (
    calculate_kcal_for_grams,
    connect_db,
    init_db,
    search_foods,
    upsert_food,
)


def test_calculate_kcal_for_grams() -> None:
    assert calculate_kcal_for_grams(kcal_per_100g=200.0, grams=50.0) == pytest.approx(100.0)


def test_search_foods_multi_token_and(tmp_path) -> None:
    conn = connect_db(tmp_path / "foods.sqlite")
    init_db(conn)
    upsert_food(conn, name="Chicken, broilers or fryers, breast, meat only", kcal_per_100g=165.0, source="fdc", fdc_id=1)
    upsert_food(conn, name="Chicken drumstick", kcal_per_100g=161.0, source="fdc", fdc_id=2)
    conn.commit()

    result = search_foods(conn, "chicken breast")
    assert any("chicken" in r.name.lower() and "breast" in r.name.lower() for r in result)

    result2 = search_foods(conn, "chicken, breast")
    assert any("chicken" in r.name.lower() and "breast" in r.name.lower() for r in result2)
    conn.close()


def test_search_foods_filters_toxic_by_default(tmp_path) -> None:
    conn = connect_db(tmp_path / "foods.sqlite")
    init_db(conn)
    upsert_food(conn, name="Onion, raw", kcal_per_100g=40.0, source="fdc", fdc_id=3)
    upsert_food(conn, name="Chocolate, dark", kcal_per_100g=540.0, source="fdc", fdc_id=4)
    upsert_food(conn, name="Chicken Breast", kcal_per_100g=165.0, source="fdc", fdc_id=5)
    conn.commit()

    names = [r.name.lower() for r in search_foods(conn, "onion") + search_foods(conn, "chicken")]
    assert all("onion" not in n and "chocolate" not in n for n in names)
    assert any("chicken" in n for n in names)
    conn.close()
