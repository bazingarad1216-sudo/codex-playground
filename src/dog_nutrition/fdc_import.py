from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import Counter, defaultdict
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
_JSON_FOOD_LIST_KEYS = (
    "foods",
    "FoundationFoods",
    "SRLegacyFoods",
    "SurveyFoods",
    "BrandedFoods",
)


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


def _extract_foods_from_json(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    if not isinstance(data, dict):
        raise ValueError("Unsupported JSON structure")

    for key in _JSON_FOOD_LIST_KEYS:
        foods = data.get(key)
        if isinstance(foods, list):
            return [item for item in foods if isinstance(item, dict)]

    raise ValueError("JSON file must contain a top-level foods list")


def import_from_json(
    conn: sqlite3.Connection,
    json_path: Path,
    source: str,
    *,
    dataset: str,
) -> tuple[int, int, Counter[str]]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    foods = _extract_foods_from_json(data)

    imported = 0
    skipped_missing_energy = 0
    skip_reasons: Counter[str] = Counter()
    for item in foods:
        parsed = _extract_record_from_json_item(item)
        if parsed is None:
            skipped_missing_energy += 1
            skip_reasons["missing_energy_or_name"] += 1
            continue
        name, kcal, fdc_id = parsed
        upsert_food(conn, name=name, kcal_per_100g=kcal, source=f"{source}:{dataset}", fdc_id=fdc_id)
        imported += 1

    conn.commit()
    return imported, skipped_missing_energy, skip_reasons


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


def import_from_csv(
    conn: sqlite3.Connection,
    csv_path: Path,
    source: str,
    *,
    dataset: str,
) -> tuple[int, int, Counter[str]]:
    imported = 0
    skipped_missing_energy = 0
    skip_reasons: Counter[str] = Counter()
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            parsed = _extract_record_from_csv_row(row)
            if parsed is None:
                skipped_missing_energy += 1
                skip_reasons["missing_energy_or_name"] += 1
                continue
            name, kcal, fdc_id = parsed
            upsert_food(conn, name=name, kcal_per_100g=kcal, source=f"{source}:{dataset}", fdc_id=fdc_id)
            imported += 1
    conn.commit()
    return imported, skipped_missing_energy, skip_reasons


def _import_from_csv_package(
    conn: sqlite3.Connection,
    input_dir: Path,
    source: str,
) -> tuple[int, int, dict[str, int], Counter[str]]:
    food_csv = input_dir / "food.csv"
    nutrient_csv = input_dir / "nutrient.csv"
    food_nutrient_csv = input_dir / "food_nutrient.csv"

    if not (food_csv.exists() and nutrient_csv.exists() and food_nutrient_csv.exists()):
        raise ValueError("CSV package mode requires food.csv + nutrient.csv + food_nutrient.csv")

    nutrient_map: dict[str, str] = {}
    with nutrient_csv.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            nutrient_id = (row.get("id") or "").strip()
            nutrient_number = (row.get("nutrient_nbr") or row.get("number") or "").strip()
            nutrient_name = (row.get("name") or "").strip()
            if nutrient_id:
                nutrient_map[nutrient_id] = nutrient_number or nutrient_name

    energy_by_food_id: dict[str, float] = {}
    with food_nutrient_csv.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            food_id = (row.get("fdc_id") or "").strip()
            nutrient_id = (row.get("nutrient_id") or "").strip()
            amount = _to_float(row.get("amount"))
            if not (food_id and nutrient_id and amount is not None):
                continue
            marker = nutrient_map.get(nutrient_id, "")
            if marker in ENERGY_NUTRIENT_NUMBERS or marker in ENERGY_NUTRIENT_NAMES:
                energy_by_food_id[food_id] = amount

    imported = 0
    skipped_missing_energy = 0
    by_dataset: dict[str, int] = defaultdict(int)
    skip_reasons: Counter[str] = Counter()
    with food_csv.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            fdc_id_raw = (row.get("fdc_id") or "").strip()
            name = (row.get("description") or "").strip()
            data_type = (row.get("data_type") or "unknown").strip().lower()
            if not (fdc_id_raw and name):
                skipped_missing_energy += 1
                skip_reasons["missing_id_or_name"] += 1
                continue
            kcal = energy_by_food_id.get(fdc_id_raw)
            if kcal is None:
                skipped_missing_energy += 1
                skip_reasons["missing_energy_in_food_nutrient"] += 1
                continue

            upsert_food(
                conn,
                name=name,
                kcal_per_100g=kcal,
                source=f"{source}:{data_type}",
                fdc_id=int(fdc_id_raw) if fdc_id_raw.isdigit() else None,
            )
            imported += 1
            by_dataset[data_type] += 1

    conn.commit()
    return imported, skipped_missing_energy, dict(by_dataset), skip_reasons


def run_import(*, db_path: Path, input_path: Path, source: str = "fdc") -> tuple[int, int, dict[str, int], list[tuple[str, int]]]:
    conn = connect_db(db_path)
    try:
        init_db(conn)
        by_dataset: dict[str, int] = defaultdict(int)
        skip_reasons: Counter[str] = Counter()

        if input_path.is_dir():
            csv_package = {"food.csv", "food_nutrient.csv", "nutrient.csv"}
            dir_files = {p.name for p in input_path.iterdir() if p.is_file()}
            if csv_package.issubset(dir_files):
                imported, skipped_missing_energy, csv_by_dataset, csv_skip = _import_from_csv_package(conn, input_path, source)
                for key, value in csv_by_dataset.items():
                    by_dataset[key] += value
                skip_reasons.update(csv_skip)
                return imported, skipped_missing_energy, dict(by_dataset), skip_reasons.most_common(5)

            imported_total = 0
            skipped_total = 0
            for file_path in sorted(input_path.iterdir()):
                if not file_path.is_file():
                    continue
                suffix = file_path.suffix.lower()
                dataset = file_path.stem.lower()
                if suffix == ".json":
                    imported, skipped, reasons = import_from_json(conn, file_path, source, dataset=dataset)
                elif suffix == ".csv":
                    imported, skipped, reasons = import_from_csv(conn, file_path, source, dataset=dataset)
                else:
                    continue
                imported_total += imported
                skipped_total += skipped
                by_dataset[dataset] += imported
                skip_reasons.update(reasons)
            return imported_total, skipped_total, dict(by_dataset), skip_reasons.most_common(5)

        suffix = input_path.suffix.lower()
        dataset = input_path.stem.lower()
        if suffix == ".json":
            imported, skipped, reasons = import_from_json(conn, input_path, source, dataset=dataset)
        elif suffix == ".csv":
            imported, skipped, reasons = import_from_csv(conn, input_path, source, dataset=dataset)
        else:
            raise ValueError("Unsupported file type. Use .json/.csv file or directory")
        by_dataset[dataset] += imported
        skip_reasons.update(reasons)
        return imported, skipped, dict(by_dataset), skip_reasons.most_common(5)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import local FDC data into SQLite")
    parser.add_argument("--db", required=True, help="SQLite DB path")
    parser.add_argument("--input", required=True, help="Local FDC JSON/CSV path or directory")
    parser.add_argument("--source", default="fdc", help="Data source label")
    args = parser.parse_args()

    db_path = Path(args.db)
    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input path not found: {input_path}")

    imported, skipped_missing_energy, by_dataset, skip_reasons = run_import(
        db_path=db_path,
        input_path=input_path,
        source=args.source,
    )
    print(f"Import done. imported={imported} skipped_missing_energy={skipped_missing_energy} db={db_path}")
    print(f"By dataset: {by_dataset}")
    print(f"Skip reasons top: {skip_reasons}")


if __name__ == "__main__":
    main()
