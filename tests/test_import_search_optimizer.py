from pathlib import Path

from dog_nutrition.fdc_import import run_import
from dog_nutrition.foods_db import connect_db, get_food_nutrients
from dog_nutrition.models import DogProfile
from dog_nutrition.nrc import nrc_status, requirements_for_profile
from dog_nutrition.optimizer import optimize_recipe
from dog_nutrition.search import search_foods_cn


def test_json_import_priority_and_cn_search(tmp_path: Path) -> None:
    json_path = tmp_path / "fdc_wrapped.json"
    json_path.write_text(
        '{"foods":[{'
        '"fdcId":1,"description":"Chicken breast",'
        '"foodNutrients":['
        '{"nutrient":{"id":1008},"amount":165},'
        '{"nutrient":{"id":1003},"amount":31},'
        '{"nutrient":{"id":1004},"amount":3.6},'
        '{"nutrient":{"id":1005},"amount":0.0}'
        ']},'
        '{"fdcId":2,"description":"Onion",'
        '"foodNutrients":[{"nutrient":{"id":1062},"amount":167.36}]}'
        ']}' ,
        encoding="utf-8",
    )
    db_path = tmp_path / "foods.db"
    imported, skipped = run_import(db_path=db_path, input_path=json_path, source="fdc")
    assert imported > 0
    assert skipped >= 0

    with connect_db(db_path) as conn:
        foods_count = conn.execute("SELECT COUNT(*) AS c FROM foods").fetchone()["c"]
        meta_count = conn.execute("SELECT COUNT(*) AS c FROM nutrient_meta").fetchone()["c"]
        nutrient_count = conn.execute("SELECT COUNT(*) AS c FROM food_nutrients").fetchone()["c"]
        assert foods_count > 0
        assert meta_count > 0
        assert nutrient_count > 0

        hits = search_foods_cn(conn, "鸡胸肉", limit=10)
        assert hits
        assert "Chicken" in hits[0].food.name

        all_names = [h.food.name for h in search_foods_cn(conn, "onion", limit=10)]
        assert "Onion" not in all_names

        row = conn.execute("SELECT id, kcal_per_100g FROM foods WHERE fdc_id = 1").fetchone()
        assert row is not None
        assert float(row["kcal_per_100g"]) > 0
        nutrients = get_food_nutrients(conn, int(row["id"]))
        nutrient_map = {n.nutrient_key: n.amount_per_100g for n in nutrients}
        assert nutrient_map.get("kcal", 0.0) > 0
        assert nutrient_map.get("protein_g", 0.0) > 0
        assert nutrient_map.get("fat_g", 0.0) > 0
        assert "carb_g" in nutrient_map


def test_nrc_and_optimizer_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "fdc.csv"
    csv_path.write_text(
        "fdc_id,description,kcal_per_100g,protein_g,fat_g,ca_mg,p_mg,k_mg,na_mg,mg_mg,fe_mg,zn_mg,cu_mg,mn_mg,se_ug,iodine_ug,vit_a_ug,vit_d_ug,vit_e_mg\n"
        "1,Supplement Mix,100,45,15,300,200,1800,250,180,2.5,20,2,2,80,180,500,8,10\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "foods.db"
    run_import(db_path=db_path, input_path=csv_path, source="fdc")

    profile = DogProfile(weight_kg=5.0, neutered=True, activity="low")
    mer, reqs = requirements_for_profile(profile)
    assert mer > 0
    assert reqs[0].suggest_per_day >= reqs[0].min_per_day

    with connect_db(db_path) as conn:
        row = conn.execute("SELECT id FROM foods WHERE fdc_id = 1").fetchone()
        result = optimize_recipe(conn, profile, [int(row["id"])])
        assert result.feasible
        assert result.items
        assert result.nrc_rows
        assert all(r.status in {"OK", "LOW", "HIGH"} for r in result.nrc_rows)


def test_nrc_status() -> None:
    assert nrc_status(9, 10, 20) == "LOW"
    assert nrc_status(21, 10, 20) == "HIGH"
    assert nrc_status(11, 10, 20) == "OK"
