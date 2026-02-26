from dog_nutrition.foods_db import connect_db, init_db, upsert_food
from dog_nutrition.search import expand_query, search_foods_cn


def test_expand_query_mapping_for_lamb_and_beef(tmp_path) -> None:
    conn = connect_db(tmp_path / "foods.sqlite")
    init_db(conn)
    upsert_food(conn, name="Lamb, leg, separable lean only", kcal_per_100g=206.0, source="fdc", fdc_id=3)
    upsert_food(conn, name="Beef, round, separable lean", kcal_per_100g=201.0, source="fdc", fdc_id=4)
    conn.commit()

    assert "lamb leg" in expand_query("羊腿")
    assert "beef round" in expand_query("牛霖")

    lamb_results = search_foods_cn(conn, "羊腿")
    assert any("lamb" in row.food.name.lower() for row in lamb_results)

    beef_results = search_foods_cn(conn, "牛霖")
    assert any("beef" in row.food.name.lower() for row in beef_results)
    conn.close()
