from dog_nutrition.foods_db import connect_db, init_db, search_foods_cn, seed_default_zh_aliases, upsert_food


def test_search_foods_cn_egg_ranked_before_chicken(tmp_path) -> None:
    conn = connect_db(tmp_path / "foods.sqlite")
    init_db(conn)
    upsert_food(conn, name="Chicken drumstick, meat only", kcal_per_100g=161.0, source="fdc", fdc_id=1)
    upsert_food(conn, name="Egg, whole, cooked", kcal_per_100g=155.0, source="fdc", fdc_id=2)
    conn.commit()
    seed_default_zh_aliases(conn)

    results = search_foods_cn(conn, "鸡蛋")
    top3 = results[:3]
    egg_positions = [i for i, row in enumerate(top3) if "egg" in row.name.lower()]
    chicken_positions = [i for i, row in enumerate(top3) if "chicken" in row.name.lower()]

    assert egg_positions
    if chicken_positions:
        assert min(egg_positions) < min(chicken_positions)

    conn.close()
