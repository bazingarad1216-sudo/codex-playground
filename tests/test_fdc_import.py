import json
from pathlib import Path

from dog_nutrition.fdc_import import run_import
from dog_nutrition.foods_db import connect_db


def test_run_import_supports_multi_inputs_and_estimated_energy(tmp_path: Path) -> None:
    db = tmp_path / "foods.sqlite"
    input_dir = tmp_path / "fdc"
    input_dir.mkdir()

    foundation = {
        "FoundationFoods": [
            {
                "fdcId": 1,
                "description": "Lamb, leg, roasted",
                "foodNutrients": [
                    {"nutrientNumber": "1003", "nutrientName": "Protein", "value": 20},
                    {"nutrientNumber": "1004", "nutrientName": "Total lipid (fat)", "value": 10},
                    {"nutrientNumber": "1005", "nutrientName": "Carbohydrate", "value": 0},
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
                    {"nutrientNumber": "1008", "nutrientName": "Energy", "value": 210},
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
    lamb = conn.execute("select kcal_per_100g, energy_estimated from foods where fdc_id = 1").fetchone()
    assert lamb is not None
    assert lamb[0] is not None
    assert lamb[1] == 1
    conn.close()
