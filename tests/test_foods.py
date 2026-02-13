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


def test_calculate_kcal_for_grams_rejects_negative() -> None:
    with pytest.raises(ValueError):
        calculate_kcal_for_grams(kcal_per_100g=100.0, grams=-1.0)


def test_search_foods_by_name(tmp_path) -> None:
    db_path = tmp_path / "foods.sqlite"
    conn = connect_db(db_path)
    init_db(conn)
    upsert_food(conn, name="Chicken Breast", kcal_per_100g=165.0, source="fdc", fdc_id=1)
    upsert_food(conn, name="Chicken Liver", kcal_per_100g=119.0, source="fdc", fdc_id=2)
    upsert_food(conn, name="Pumpkin", kcal_per_100g=26.0, source="fdc", fdc_id=3)
    conn.commit()

    results = search_foods(conn, "chicken")
    assert [item.name for item in results] == ["Chicken Breast", "Chicken Liver"]
    assert [item.kcal_per_100g for item in results] == [165.0, 119.0]

    conn.close()
