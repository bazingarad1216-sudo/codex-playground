from pathlib import Path

from dog_nutrition.foods_db import (
    add_food_alias,
    connect_db,
    expand_query,
    get_food_aliases,
    init_db,
    search_foods,
    search_foods_cn,
    seed_default_zh_aliases,
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
    upsert_food(conn, name="Chicken, drumstick, meat only", kcal_per_100g=161.0, source="fdc", fdc_id=5)
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
    add_food_alias(conn, chicken.id, "zh", "鸡胸肉", weight=120)

    results = search_foods_cn(conn, "鸡胸肉")
    assert results
    assert "chicken" in results[0].name.lower() and "breast" in results[0].name.lower()

    aliases = get_food_aliases(conn, chicken.id)
    assert "鸡胸肉" in aliases
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


def test_expand_query_egg_rules() -> None:
    egg = expand_query("鸡蛋")
    assert "egg" in egg
    assert "whole egg" in egg
    assert "chicken" not in egg
    assert "whole" not in egg

    yolk = expand_query("鸡蛋黄")
    assert any("egg" in term for term in yolk)

    white = expand_query("鸡蛋白")
    assert any("egg" in term for term in white)

    breast = expand_query("鸡胸肉")
    assert "chicken" in breast
    assert "breast" in breast


def test_search_foods_cn_sorting_rules(tmp_path: Path) -> None:
    conn = connect_db(tmp_path / "foods.sqlite")
    init_db(conn)
    _seed_foods(conn)
    seed_default_zh_aliases(conn)

    egg_results = search_foods_cn(conn, "鸡蛋")
    assert egg_results
    top3_egg = egg_results[:3]
    egg_positions = [idx for idx, row in enumerate(top3_egg) if "egg" in row.name.lower()]
    chicken_positions = [idx for idx, row in enumerate(top3_egg) if "chicken" in row.name.lower()]
    assert egg_positions, "鸡蛋 top3 必须包含 egg"
    if chicken_positions:
        assert min(egg_positions) < min(chicken_positions), "鸡蛋结果中 chicken 不能排在 egg 前"

    breast_results = search_foods_cn(conn, "鸡胸肉")
    assert breast_results
    assert "chicken" in breast_results[0].name.lower()
    assert "breast" in breast_results[0].name.lower()

    chicken_results = search_foods_cn(conn, "鸡")
    top3 = chicken_results[:3]
    assert any("chicken" in row.name.lower() for row in top3)
    conn.close()
