from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

from .foods_db import connect_db, init_db, upsert_food


ENERGY_NUTRIENT_NUMBERS = {"1008"}
ENERGY_NUTRIENT_NAMES = {
    "Energy",
    "Energy (Atwater General Factors)",
    "Energy (Atwater Specific Factors)",
    "Energy (kcal)",
}


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_energy_from_nutrients(nutrients: list[dict[str, Any]]) -> float | None:
    for nutrient in nutrients:
        number = str(nutrient.get("nutrientNumber", "")).strip()
        name = str(nutrient.get("nutrientName", "")).strip()
        if number in ENERGY_NUTRIENT_NUMBERS or name in ENERGY_NUTRIENT_NAMES:
            amount = _to_float(nutrient.get("value") or nutrient.get("amount"))
            if amount is not None:
                return amount
    return None


def _extract_record_from_json_item(item: dict[str, Any]) -> tuple[str, float, int | None] | None:
    name = str(item.get("description") or item.get("name") or "").strip()
    if not name:
        return None

    fdc_id_value = item.get("fdcId") or item.get("fdc_id")
    fdc_id = int(fdc_id_value) if isinstance(fdc_id_value, int) or str(fdc_id_value).isdigit() else None

    kcal = _to_float(item.get("kcal_per_100g") or item.get("energy_kcal") or item.get("energy"))
    if kcal is None:
        nutrients = item.get("foodNutrients")
        if isinstance(nutrients, list):
            kcal = _extract_energy_from_nutrients(nutrients)
    if kcal is None:
        return None

    return name, kcal, fdc_id


def import_from_json(conn: sqlite3.Connection, json_path: Path, source: str) -> tuple[int, int]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        foods = data.get("foods")
        if not isinstance(foods, list):
            raise ValueError("JSON file must contain a top-level list or a 'foods' list field")
    elif isinstance(data, list):
        foods = data
    else:
        raise ValueError("Unsupported JSON structure")

    imported = 0
    skipped_missing_energy = 0
    for item in foods:
        if not isinstance(item, dict):
            continue
        parsed = _extract_record_from_json_item(item)
        if parsed is None:
            skipped_missing_energy += 1
            continue
        name, kcal, fdc_id = parsed
        upsert_food(conn, name=name, kcal_per_100g=kcal, source=source, fdc_id=fdc_id)
        imported += 1

    conn.commit()
    return imported, skipped_missing_energy


def _extract_record_from_csv_row(row: dict[str, str]) -> tuple[str, float, int | None] | None:
    name = (row.get("description") or row.get("name") or "").strip()
    if not name:
        return None

    fdc_id_raw = (row.get("fdc_id") or row.get("fdcId") or "").strip()
    fdc_id = int(fdc_id_raw) if fdc_id_raw.isdigit() else None

    kcal = _to_float(
        row.get("kcal_per_100g")
        or row.get("energy_kcal")
        or row.get("energy")
        or row.get("Energy")
    )
    if kcal is None:
        return None

    return name, kcal, fdc_id


def import_from_csv(conn: sqlite3.Connection, csv_path: Path, source: str) -> tuple[int, int]:
    imported = 0
    skipped_missing_energy = 0
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            parsed = _extract_record_from_csv_row(row)
            if parsed is None:
                skipped_missing_energy += 1
                continue
            name, kcal, fdc_id = parsed
            upsert_food(conn, name=name, kcal_per_100g=kcal, source=source, fdc_id=fdc_id)
            imported += 1
    conn.commit()
    return imported, skipped_missing_energy


def run_import(*, db_path: Path, input_path: Path, source: str = "fdc") -> tuple[int, int]:
    conn = connect_db(db_path)
    try:
        init_db(conn)
        suffix = input_path.suffix.lower()
        if suffix == ".json":
            return import_from_json(conn, input_path, source)
        if suffix == ".csv":
            return import_from_csv(conn, input_path, source)
        raise ValueError("Unsupported file type. Use .json or .csv")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import local FDC data into SQLite")
    parser.add_argument("--db", required=True, help="SQLite DB path")
    parser.add_argument("--input", required=True, help="Local FDC JSON/CSV file path")
    parser.add_argument("--source", default="fdc", help="Data source label")
    args = parser.parse_args()

    db_path = Path(args.db)
    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    imported, skipped_missing_energy = run_import(
        db_path=db_path,
        input_path=input_path,
        source=args.source,
    )
    print(
        f"Import done. imported={imported} skipped_missing_energy={skipped_missing_energy} db={db_path}"
    )


if __name__ == "__main__":
    main()
