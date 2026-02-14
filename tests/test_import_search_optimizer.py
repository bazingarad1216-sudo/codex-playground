from pathlib import Path

from dog_nutrition.fdc_import import run_import
from dog_nutrition.foods_db import connect_db, get_food_nutrients
from dog_nutrition.models import DogProfile
from dog_nutrition.nrc import requirements_for_profile
from dog_nutrition.optimizer import optimize_recipe
from dog_nutrition.search import search_foods_cn


def test_csv_import_and_cn_search(tmp_path: Path) -> None:
    csv_path = tmp_path / "fdc.csv"
    csv_path.write_text(
        "fdc_id,description,kcal_per_100g,protein_g,fat_g,ca_mg,p_mg\n"
        "1,Chicken breast,165,31,3.6,15,210\n"
        "2,Onion,40,1.1,0.1,23,29\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "foods.db"
    imported, skipped = run_import(db_path=db_path, input_path=csv_path, source="fdc")
    assert imported == 2
    assert skipped == 0

    with connect_db(db_path) as conn:
        hits = search_foods_cn(conn, "鸡胸肉", limit=10)
        assert hits
        assert "Chicken" in hits[0].food.name
        all_names = [h.food.name for h in search_foods_cn(conn, "onion", limit=10)]
        assert "Onion" not in all_names


def test_nrc_and_optimizer_feasible(tmp_path: Path) -> None:
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
    assert any(r.nutrient_key == "ca_mg" for r in reqs)

    with connect_db(db_path) as conn:
        row = conn.execute("SELECT id FROM foods WHERE fdc_id = 1").fetchone()
        assert row is not None
        result = optimize_recipe(conn, profile, [int(row["id"])])
        assert result.feasible
        assert result.items
        nutrients = get_food_nutrients(conn, int(row["id"]))
        assert any(n.nutrient_key == "protein_g" for n in nutrients)
