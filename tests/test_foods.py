from pathlib import Path

from dog_nutrition.foods_db import (
    connect_db,
    get_food_nutrients,
    init_db,
    search_foods,
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
