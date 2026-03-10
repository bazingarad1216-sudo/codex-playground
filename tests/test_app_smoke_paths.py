import importlib.util
import os
import types
from pathlib import Path

from dog_nutrition.energy import ACTIVITY_FACTORS, calculate_mer, calculate_rer
from dog_nutrition.foods_db import connect_db, init_db, search_foods, upsert_food
from dog_nutrition.models import DogProfile
from dog_nutrition.search import SearchResult, search_foods_cn

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _load_app_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("app", APP_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_app_import_smoke(tmp_path) -> None:
    os.environ["FOODS_DB_PATH"] = str(tmp_path / "foods.sqlite")
    mod = _load_app_module()
    assert hasattr(mod, "normalize_search_matches")


def test_main_visible_paths_smoke(tmp_path) -> None:
    profile = DogProfile(weight_kg=12.0, neutered=True, activity="normal")
    rer = calculate_rer(profile.weight_kg)
    mer = calculate_mer(profile)
    assert rer > 0
    assert mer == rer * ACTIVITY_FACTORS["normal"]

    conn = connect_db(tmp_path / "foods.sqlite")
    init_db(conn)
    upsert_food(conn, name="Chicken breast, cooked", kcal_per_100g=165.0, source="fdc", fdc_id=1001)
    upsert_food(conn, name="Egg, whole, cooked", kcal_per_100g=155.0, source="fdc", fdc_id=1002)
    conn.commit()

    en_results = search_foods(conn, "chicken breast", limit=20)
    assert en_results
    assert "chicken" in en_results[0].name.lower()

    zh_results = search_foods_cn(conn, "鸡蛋", limit=20)
    assert zh_results
    assert isinstance(zh_results[0], SearchResult)
    assert "egg" in zh_results[0].food.name.lower()

    os.environ["FOODS_DB_PATH"] = str(tmp_path / "foods.sqlite")
    app_mod = _load_app_module()
    normalized_en = app_mod.normalize_search_matches(en_results)
    normalized_zh = app_mod.normalize_search_matches(zh_results)

    assert normalized_en[0].name == en_results[0].name
    assert normalized_zh[0].name == zh_results[0].food.name
    conn.close()
