import pytest

from dog_nutrition.foods_db import (
    calculate_kcal_for_grams,
    connect_db,
    init_db,
    search_foods,
    search_foods_cn,
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


def test_search_foods_multi_token_and(tmp_path) -> None:
    db_path = tmp_path / "foods.sqlite"
    conn = connect_db(db_path)
    init_db(conn)
    upsert_food(
        conn,
        name="Chicken, broilers or fryers, breast, meat only, cooked, roasted",
        kcal_per_100g=165.0,
        source="fdc",
        fdc_id=11,
    )
    upsert_food(conn, name="Chicken Drumstick", kcal_per_100g=161.0, source="fdc", fdc_id=12)
    upsert_food(conn, name="Beef Breast", kcal_per_100g=250.0, source="fdc", fdc_id=13)
    conn.commit()

    assert any("chicken" in row.name.lower() and "breast" in row.name.lower() for row in search_foods(conn, "chicken breast"))
    assert any("chicken" in row.name.lower() and "breast" in row.name.lower() for row in search_foods(conn, "chicken, breast"))
    assert any("chicken" in row.name.lower() and "breast" in row.name.lower() for row in search_foods(conn, "chicken AND breast"))

    conn.close()


def test_search_foods_cn_chicken_breast(tmp_path) -> None:
    db_path = tmp_path / "foods.sqlite"
    conn = connect_db(db_path)
    init_db(conn)
    upsert_food(
        conn,
        name="Chicken, broilers or fryers, breast, meat only, cooked, roasted",
        kcal_per_100g=165.0,
        source="fdc",
        fdc_id=21,
    )
    upsert_food(conn, name="Egg, whole, cooked", kcal_per_100g=155.0, source="fdc", fdc_id=22)
    conn.commit()

    chicken_breast_results = search_foods_cn(conn, "鸡胸肉")
    assert any("chicken" in row.name.lower() and "breast" in row.name.lower() for row in chicken_breast_results)

    chicken_results = search_foods_cn(conn, "鸡肉")
    assert any("chicken" in row.name.lower() for row in chicken_results)

    egg_results = search_foods_cn(conn, "鸡蛋")
    assert any("egg" in row.name.lower() for row in egg_results)

    conn.close()


def test_search_foods_filters_toxic_foods(tmp_path) -> None:
    db_path = tmp_path / "foods.sqlite"
    conn = connect_db(db_path)
    init_db(conn)
    upsert_food(conn, name="Onion, raw", kcal_per_100g=40.0, source="fdc", fdc_id=31)
    upsert_food(conn, name="Chocolate, dark", kcal_per_100g=546.0, source="fdc", fdc_id=32)
    upsert_food(conn, name="Chicken Breast", kcal_per_100g=165.0, source="fdc", fdc_id=33)
    conn.commit()

    results = search_foods(conn, "onion") + search_foods(conn, "chocolate") + search_foods(conn, "chicken")
    names = [item.name.lower() for item in results]
    assert all("onion" not in name for name in names)
    assert all("chocolate" not in name for name in names)
    assert any("chicken" in name for name in names)

    conn.close()
