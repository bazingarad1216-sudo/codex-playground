from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

from .foods_db import connect_db, init_db, upsert_food, upsert_food_nutrient, upsert_nutrient_meta
from .nutrients import FDC_NUTRIENT_TO_KEY, KEY_NUTRIENTS

ENERGY_NUTRIENT_NUMBERS = {"1008"}


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _seed_nutrient_meta(conn: sqlite3.Connection) -> None:
    upsert_nutrient_meta(conn, nutrient_key="kcal", nutrient_name="Energy", unit="kcal", fdc_nutrient_number="1008")
    reverse_map = {v: k for k, v in FDC_NUTRIENT_TO_KEY.items()}
    for key, (name, unit, _) in KEY_NUTRIENTS.items():
        upsert_nutrient_meta(conn, nutrient_key=key, nutrient_name=name, unit=unit, fdc_nutrient_number=reverse_map.get(key))


def _extract_nutrients_from_json_item(item: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    nutrients = item.get("foodNutrients")
    if not isinstance(nutrients, list):
        return out
    for nutrient in nutrients:
        if not isinstance(nutrient, dict):
            continue
        number = str(nutrient.get("nutrientNumber", "")).strip()
        amount = _to_float(nutrient.get("value") or nutrient.get("amount"))
        if amount is None:
            continue
        if number in ENERGY_NUTRIENT_NUMBERS:
            out["kcal"] = amount
        mapped = FDC_NUTRIENT_TO_KEY.get(number)
        if mapped is not None:
            out[mapped] = amount
    return out


def _extract_record_from_json_item(item: dict[str, Any]) -> tuple[str, float, int | None, dict[str, float]] | None:
    name = str(item.get("description") or item.get("name") or "").strip()
    if not name:
        return None
    fdc_id_raw = item.get("fdcId") or item.get("fdc_id")
    fdc_id = int(fdc_id_raw) if isinstance(fdc_id_raw, int) or str(fdc_id_raw).isdigit() else None
    nutrients = _extract_nutrients_from_json_item(item)
    kcal = _to_float(item.get("kcal_per_100g") or item.get("energy_kcal") or item.get("energy"))
    if kcal is None:
        kcal = nutrients.get("kcal")
    if kcal is None:
        return None
    nutrients["kcal"] = kcal
    return name, kcal, fdc_id, nutrients


def import_from_json(conn: sqlite3.Connection, json_path: Path, source: str) -> tuple[int, int]:
    _seed_nutrient_meta(conn)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    foods = data.get("foods") if isinstance(data, dict) else data
    if not isinstance(foods, list):
        raise ValueError("Unsupported JSON structure")

    imported = 0
    skipped = 0
    for item in foods:
        if not isinstance(item, dict):
            continue
        parsed = _extract_record_from_json_item(item)
        if parsed is None:
            skipped += 1
            continue
        name, kcal, fdc_id, nutrients = parsed
        food_id = upsert_food(conn, name=name, kcal_per_100g=kcal, source=source, fdc_id=fdc_id)
        for k, v in nutrients.items():
            upsert_food_nutrient(conn, food_id=food_id, nutrient_key=k, amount_per_100g=v)
        imported += 1
    conn.commit()
    return imported, skipped


def _extract_record_from_csv_row(row: dict[str, str]) -> tuple[str, float, int | None, dict[str, float]] | None:
    name = (row.get("description") or row.get("name") or "").strip()
    if not name:
        return None
    fdc_id_raw = (row.get("fdc_id") or row.get("fdcId") or "").strip()
    fdc_id = int(fdc_id_raw) if fdc_id_raw.isdigit() else None
    kcal = _to_float(row.get("kcal_per_100g") or row.get("energy_kcal") or row.get("energy") or row.get("Energy"))
    if kcal is None:
        return None
    nutrients: dict[str, float] = {"kcal": kcal}
    for key in KEY_NUTRIENTS:
        value = _to_float(row.get(key))
        if value is not None:
            nutrients[key] = value
    return name, kcal, fdc_id, nutrients


def import_from_csv(conn: sqlite3.Connection, csv_path: Path, source: str) -> tuple[int, int]:
    _seed_nutrient_meta(conn)
    imported = 0
    skipped = 0
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            parsed = _extract_record_from_csv_row(row)
            if parsed is None:
                skipped += 1
                continue
            name, kcal, fdc_id, nutrients = parsed
            food_id = upsert_food(conn, name=name, kcal_per_100g=kcal, source=source, fdc_id=fdc_id)
            for k, v in nutrients.items():
                upsert_food_nutrient(conn, food_id=food_id, nutrient_key=k, amount_per_100g=v)
            imported += 1
    conn.commit()
    return imported, skipped


def run_import(*, db_path: Path, input_path: Path, source: str = "fdc") -> tuple[int, int]:
    conn = connect_db(db_path)
    try:
        init_db(conn)
        if input_path.suffix.lower() == ".json":
            return import_from_json(conn, input_path, source)
        if input_path.suffix.lower() == ".csv":
            return import_from_csv(conn, input_path, source)
        raise ValueError("Unsupported file type. Use .json or .csv")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import local FDC data into SQLite")
    parser.add_argument("--db", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--source", default="fdc")
    args = parser.parse_args()

    db_path = Path(args.db)
    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    imported, skipped = run_import(db_path=db_path, input_path=input_path, source=args.source)
    print(f"Import done. imported={imported} skipped_missing_energy={skipped} db={db_path}")


if __name__ == "__main__":
    main()
