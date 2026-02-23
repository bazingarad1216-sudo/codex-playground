from pathlib import Path

from dog_nutrition.foods_db import connect_db, init_db, search_foods, upsert_food


def test_search_foods_multi_token_fdc_style_name(tmp_path: Path) -> None:
    db_path = tmp_path / "foods.db"
    with connect_db(db_path) as conn:
        init_db(conn)
        upsert_food(
            conn,
            name="Chicken, broiler or fryers, breast, skinless, boneless, meat only, cooked, braised",
            kcal_per_100g=180.0,
            source="fdc",
            fdc_id=32,
        )
        conn.commit()

        hits_space = search_foods(conn, "chicken breast", limit=20)
        hits_comma = search_foods(conn, "chicken, breast", limit=20)

    assert len(hits_space) >= 1
    assert any("chicken" in h.name.lower() and "breast" in h.name.lower() for h in hits_space)
    assert len(hits_comma) >= 1
    assert any("chicken" in h.name.lower() and "breast" in h.name.lower() for h in hits_comma)
