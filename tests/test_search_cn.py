from pathlib import Path

from dog_nutrition.foods_db import connect_db, init_db, search_foods, upsert_food
from dog_nutrition.toxicity import is_toxic_food_name
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


def test_search_foods_cn_filters_toxic_keywords(tmp_path: Path) -> None:
    db_path = tmp_path / "foods.db"
    with connect_db(db_path) as conn:
        init_db(conn)
        upsert_food(conn, name="Onion, raw", kcal_per_100g=40.0, source="fdc", fdc_id=101)
        upsert_food(conn, name="Chocolate, dark, 70%", kcal_per_100g=598.0, source="fdc", fdc_id=102)
        upsert_food(conn, name="Grape, raw", kcal_per_100g=69.0, source="fdc", fdc_id=103)
        upsert_food(conn, name="Xylitol chewing gum", kcal_per_100g=0.0, source="fdc", fdc_id=104)
        conn.commit()

        onion_hits = search_foods_cn(conn, "onion", limit=10)
        chocolate_hits = search_foods_cn(conn, "chocolate", limit=10)
        grape_hits = search_foods_cn(conn, "grape", limit=10)
        xylitol_hits = search_foods_cn(conn, "xylitol", limit=10)

    assert is_toxic_food_name("onion")
    assert is_toxic_food_name("chocolate")
    assert is_toxic_food_name("grape")
    assert is_toxic_food_name("xylitol")

    assert onion_hits == []
    assert chocolate_hits == []
    assert grape_hits == []
    assert xylitol_hits == []


def test_search_foods_cn_chicken_meat_match(tmp_path: Path) -> None:
    db_path = tmp_path / "foods.db"
    with connect_db(db_path) as conn:
        init_db(conn)
        upsert_food(conn, name="Chicken, stewing, meat only, cooked", kcal_per_100g=180.0, source="fdc", fdc_id=201)
        conn.commit()
        hits_cn = search_foods_cn(conn, "鸡肉", limit=10)

    assert len(hits_cn) >= 1
    assert any("chicken" in h.food.name.lower() for h in hits_cn)


def test_search_foods_cn_egg_match(tmp_path: Path) -> None:
    db_path = tmp_path / "foods.db"
    with connect_db(db_path) as conn:
        init_db(conn)
        upsert_food(conn, name="Egg, white, raw, fresh", kcal_per_100g=52.0, source="fdc", fdc_id=202)
        conn.commit()
        hits_cn = search_foods_cn(conn, "鸡蛋", limit=10)

    assert len(hits_cn) >= 1
    assert any("egg" in h.food.name.lower() for h in hits_cn)


def test_expand_query_chicken_keyword_present_for_ji() -> None:
    expanded = [e.lower() for e in expand_query("鸡")]
    assert "chicken" in expanded
