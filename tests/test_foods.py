from pathlib import Path

from dog_nutrition.foods_db import (
    connect_db,
    get_food_nutrients,
    init_db,
    search_foods,
    search_foods_cn,
    upsert_food,
    upsert_food_nutrient,
    upsert_nutrient_meta,
)
from dog_nutrition.toxicity import is_toxic_food_name


def test_upsert_and_search_foods(tmp_path: Path) -> None:
    db_path = tmp_path / "foods.db"
    conn = connect_db(db_path)
    init_db(conn)
    upsert_food(conn, name="Chicken Breast", kcal_per_100g=165.0, source="fdc", fdc_id=1)
    upsert_food(conn, name="Onion", kcal_per_100g=40.0, source="fdc", fdc_id=2)
    conn.commit()

    results = search_foods(conn, "", limit=20)
    assert results == []

    results_by_token = search_foods(conn, "chicken", limit=20)
    assert [item.name for item in results_by_token] == ["Chicken Breast"]
    conn.close()


def test_nutrients_storage(tmp_path: Path) -> None:
    db_path = tmp_path / "foods.db"
    conn = connect_db(db_path)
    init_db(conn)
    food_id = upsert_food(conn, name="Chicken Breast", kcal_per_100g=165.0, source="fdc", fdc_id=1)
    upsert_nutrient_meta(conn, nutrient_key="protein_g", nutrient_name="Protein", unit="g")
    upsert_food_nutrient(conn, food_id=food_id, nutrient_key="protein_g", amount_per_100g=31.0)
    conn.commit()

    items = get_food_nutrients(conn, food_id)
    assert len(items) == 1
    assert items[0].nutrient_key == "protein_g"
    assert items[0].display_name == "Protein"
    assert items[0].amount_per_100g == 31.0


def test_toxic_keywords() -> None:
    assert is_toxic_food_name("洋葱")
    assert is_toxic_food_name("dark chocolate")
    assert not is_toxic_food_name("鸡胸肉")


def test_search_foods_multi_token_non_contiguous(tmp_path: Path) -> None:
    db_path = tmp_path / "foods.db"
    conn = connect_db(db_path)
    init_db(conn)
    upsert_food(
        conn,
        name="Chicken, broiler or fryers, breast, skinless, boneless, meat only, raw",
        kcal_per_100g=120.0,
        source="fdc",
        fdc_id=10,
    )
    upsert_food(
        conn,
        name="Egg, white, raw, fresh",
        kcal_per_100g=52.0,
        source="fdc",
        fdc_id=11,
    )
    conn.commit()

    chicken_hits = search_foods(conn, "chicken breast", limit=20)
    chicken_comma_hits = search_foods(conn, "chicken, breast", limit=20)
    egg_hits = search_foods(conn, "egg white", limit=20)

    assert len(chicken_hits) >= 1
    assert any("chicken" in item.name.lower() and "breast" in item.name.lower() for item in chicken_hits)
    assert len(chicken_comma_hits) >= 1
    assert any("chicken" in item.name.lower() and "breast" in item.name.lower() for item in chicken_comma_hits)
    assert len(egg_hits) >= 1
    assert any("egg" in item.name.lower() and "white" in item.name.lower() for item in egg_hits)
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
