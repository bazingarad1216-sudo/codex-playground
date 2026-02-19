from pathlib import Path

from dog_nutrition.foods_db import (
    add_food_alias,
    connect_db,
    expand_query,
    init_db,
    search_foods,
    search_foods_cn,
    upsert_food,
)


def _seed_foods(conn) -> None:
    upsert_food(
        conn,
        name="Chicken, broiler or fryers, breast, meat only, cooked, roasted",
        kcal_per_100g=165.0,
        source="fdc",
        fdc_id=1,
    )
    upsert_food(conn, name="Egg, whole, cooked", kcal_per_100g=155.0, source="fdc", fdc_id=2)
    upsert_food(conn, name="Lamb, leg, separable lean only", kcal_per_100g=206.0, source="fdc", fdc_id=3)
    upsert_food(conn, name="Beef, round, separable lean", kcal_per_100g=201.0, source="fdc", fdc_id=4)
    conn.commit()


def test_search_foods_chicken_breast_token_and(tmp_path: Path) -> None:
    conn = connect_db(tmp_path / "foods.sqlite")
    init_db(conn)
    _seed_foods(conn)

    results = search_foods(conn, "chicken breast")
    assert any("chicken" in item.name.lower() and "breast" in item.name.lower() for item in results)

    comma_results = search_foods(conn, "chicken, breast")
    assert any("chicken" in item.name.lower() and "breast" in item.name.lower() for item in comma_results)

    conn.close()


def test_add_food_alias_and_search_foods_cn(tmp_path: Path) -> None:
    conn = connect_db(tmp_path / "foods.sqlite")
    init_db(conn)
    _seed_foods(conn)

    chicken = search_foods(conn, "chicken breast")[0]
    add_food_alias(conn, chicken.id, "zh", "鸡胸肉")

    results = search_foods_cn(conn, "鸡胸肉")
    assert any(item.id == chicken.id for item in results)

    conn.close()


def test_expand_query_mapping_for_lamb_and_beef(tmp_path: Path) -> None:
    conn = connect_db(tmp_path / "foods.sqlite")
    init_db(conn)
    _seed_foods(conn)

    lamb_query_expanded = expand_query("羊腿")
    assert "lamb leg" in lamb_query_expanded

    beef_query_expanded = expand_query("牛霖")
    assert "beef round" in beef_query_expanded

    lamb_results = search_foods_cn(conn, "羊腿")
    assert any("lamb" in item.name.lower() for item in lamb_results)

    beef_results = search_foods_cn(conn, "牛霖")
    assert any("beef" in item.name.lower() for item in beef_results)

    conn.close()
