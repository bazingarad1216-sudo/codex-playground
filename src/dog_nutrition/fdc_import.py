from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .foods_db import (
    connect_db,
    init_db,
    upsert_food,
    upsert_food_nutrient,
    upsert_nutrient_meta,
)
from .nutrients import FDC_NUTRIENT_TO_KEY, KEY_NUTRIENTS

_JSON_FOOD_LIST_KEYS = ("foods", "FoundationFoods", "SRLegacyFoods", "SurveyFoods", "BrandedFoods")


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_foods(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in _JSON_FOOD_LIST_KEYS:
            val = data.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
    return []


def _extract_nutrients(item: dict[str, Any]) -> list[dict[str, Any]]:
    val = item.get("foodNutrients")
    return [x for x in val if isinstance(x, dict)] if isinstance(val, list) else []


def _derive_energy(nutr_map: dict[str, float]) -> tuple[float | None, int]:
    if "energy_kcal" in nutr_map:
        return nutr_map["energy_kcal"], 0
    if "energy_kj" in nutr_map:
        return nutr_map["energy_kj"] / 4.184, 0
    if {"protein", "fat", "carbohydrate"}.issubset(nutr_map.keys()):
        kcal = nutr_map["protein"] * 4 + nutr_map["fat"] * 9 + nutr_map["carbohydrate"] * 4
        return kcal, 1
    return None, 0


def _seed_nutrient_meta(conn: sqlite3.Connection) -> None:
    for key, (name, unit, fdc_number) in KEY_NUTRIENTS.items():
        upsert_nutrient_meta(
            conn,
            nutrient_key=key,
            nutrient_name=name,
            unit=unit,
            fdc_nutrient_number=fdc_number,
        )


def _import_json_file(conn: sqlite3.Connection, path: Path, source: str, dataset: str) -> tuple[int, int, Counter[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    foods = _extract_foods(data)
    imported = 0
    skipped = 0
    reasons: Counter[str] = Counter()

    for item in foods:
        name = str(item.get("description") or item.get("name") or "").strip()
        if not name:
            reasons["missing_name"] += 1
            continue

        fdc_id_val = item.get("fdcId") or item.get("fdc_id")
        fdc_id = int(fdc_id_val) if isinstance(fdc_id_val, int) or str(fdc_id_val).isdigit() else None

        nutrients = _extract_nutrients(item)
        nutr_map: dict[str, float] = {}
        for nutrient in nutrients:
            code = str(nutrient.get("nutrientNumber") or nutrient.get("number") or "").strip()
            key = FDC_NUTRIENT_TO_KEY.get(code)
            if not key:
                continue
            amount = _to_float(nutrient.get("value") if nutrient.get("value") is not None else nutrient.get("amount"))
            if amount is None:
                continue
            nutr_map[key] = amount

        kcal, energy_estimated = _derive_energy(nutr_map)
        if kcal is None:
            skipped += 1
            reasons["missing_energy"] += 1

        food_id = upsert_food(
            conn,
            name=name,
            kcal_per_100g=kcal,
            source=f"{source}:{dataset}",
            fdc_id=fdc_id,
            energy_estimated=energy_estimated,
        )

        for key, amount in nutr_map.items():
            upsert_food_nutrient(conn, food_id=food_id, nutrient_key=key, amount_per_100g=amount)

        imported += 1

    conn.commit()
    return imported, skipped, reasons


def _collect_input_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        json_files = sorted(path.glob("*_food_json_*.json"))
        return json_files if json_files else sorted(path.glob("*.json"))
    return []


def run_import(
    *,
    db_path: Path,
    source: str = "fdc",
    input_path: Path | None = None,
    input_paths: list[Path] | None = None,
):
    conn = connect_db(db_path)
    try:
        init_db(conn)
        _seed_nutrient_meta(conn)

        if input_paths is None:
            if input_path is None:
                raise ValueError("input_path or input_paths is required")
            paths = [input_path]
        else:
            paths = input_paths

        imported_total = 0
        skipped_total = 0
        by_dataset: dict[str, int] = defaultdict(int)
        reasons: Counter[str] = Counter()

        for root in paths:
            for file_path in _collect_input_files(root):
                dataset = file_path.stem.lower()
                imported, skipped, rs = _import_json_file(conn, file_path, source, dataset)
                imported_total += imported
                skipped_total += skipped
                by_dataset[dataset] += imported
                reasons.update(rs)

        if input_paths is None:
            return imported_total, skipped_total
        return imported_total, skipped_total, dict(by_dataset), reasons.most_common(8)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import local FDC data into SQLite")
    parser.add_argument("--db", required=True)
    parser.add_argument("--input", action="append", required=True)
    parser.add_argument("--source", default="fdc")
    args = parser.parse_args()

    imported, skipped, by_dataset, reasons = run_import(
        db_path=Path(args.db),
        input_paths=[Path(x) for x in args.input],
        source=args.source,
    )
    print(f"Import done. imported={imported} skipped_missing_energy={skipped} db={args.db}")
    print(f"By dataset: {by_dataset}")
    print(f"Skip reasons top: {reasons}")


if __name__ == "__main__":
    main()
