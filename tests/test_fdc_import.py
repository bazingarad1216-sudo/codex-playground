import json
from pathlib import Path

from dog_nutrition.fdc_import import run_import
from dog_nutrition.foods_db import connect_db, get_food_nutrients


def test_run_import_supports_input_paths_and_estimated_energy(tmp_path: Path) -> None:
    db = tmp_path / "foods.sqlite"
    input_dir = tmp_path / "fdc"
    input_dir.mkdir()

    foundation = {
        "FoundationFoods": [
            {
                "fdcId": 1,
                "description": "Lamb, leg, roasted",
                "foodNutrients": [
                    {"nutrientNumber": "1003", "value": 20},
                    {"nutrientNumber": "1004", "value": 10},
                    {"nutrientNumber": "1005", "value": 0},
                ],
            }
        ]
    }
    sr_legacy = {
        "foods": [
            {
                "fdcId": 2,
                "description": "Beef shank, braised",
                "foodNutrients": [
                    {"nutrientNumber": "1008", "value": 210},
                ],
            }
        ]
    }
    (input_dir / "foundation_food_json_1.json").write_text(json.dumps(foundation), encoding="utf-8")
    (input_dir / "sr_legacy_food_json_1.json").write_text(json.dumps(sr_legacy), encoding="utf-8")

    imported, skipped, by_dataset, _ = run_import(db_path=db, input_paths=[input_dir], source="fdc")
    assert imported == 2
    assert skipped == 0
    assert by_dataset

    conn = connect_db(db)
    lamb = conn.execute("select id, kcal_per_100g, energy_estimated from foods where fdc_id = 1").fetchone()
    assert lamb is not None
    assert lamb[1] is not None
    assert lamb[2] == 1
    nutrients = get_food_nutrients(conn, int(lamb[0]))
    assert "protein" in nutrients
    conn.close()


def test_run_import_single_input_path_returns_two_values(tmp_path: Path) -> None:
    db = tmp_path / "foods.sqlite"
    file_path = tmp_path / "foods.json"
    data = {"foods": [{"fdcId": 10, "description": "Egg, whole", "foodNutrients": [{"nutrientNumber": "1008", "value": 150}]}]}
    file_path.write_text(json.dumps(data), encoding="utf-8")

    imported, skipped = run_import(db_path=db, input_path=file_path, source="fdc")
    assert imported == 1
    assert skipped == 0
