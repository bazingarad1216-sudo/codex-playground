from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .foods_db import connect_db, init_db, upsert_food, upsert_food_nutrient, upsert_nutrient_meta
from .nutrients import FDC_NUTRIENT_TO_KEY, KEY_NUTRIENTS

ENERGY_KCAL_NUMBER = "1008"
ENERGY_KJ_NUMBER = "1062"
from .foods_db import connect_db, init_db, upsert_food, upsert_food_nutrient


ENERGY_KCAL_CODES = {"1008"}
ENERGY_KJ_CODES = {"1062"}
PROTEIN_CODES = {"1003"}
FAT_CODES = {"1004"}
CARB_CODES = {"1005"}
_JSON_FOOD_LIST_KEYS = ("foods", "FoundationFoods", "SRLegacyFoods", "SurveyFoods", "BrandedFoods")


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None




def _extract_fdc_nutrient_number(nutrient: dict[str, Any]) -> str:
    nd = nutrient.get("nutrient")
    num = nutrient.get("nutrientId") or nutrient.get("nutrient_id")
    if not num and isinstance(nd, dict):
        num = nd.get("id") or nd.get("number") or nd.get("nutrientNumber")
    if not num:
        num = nutrient.get("nutrientNumber") or nutrient.get("number")
    return str(num).strip() if num is not None else ""

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
        number = _extract_fdc_nutrient_number(nutrient)
        amount = _to_float(nutrient.get("value") or nutrient.get("amount"))
        if amount is None:
            continue

        if number == ENERGY_KCAL_NUMBER:
            out["kcal"] = amount
        elif number == ENERGY_KJ_NUMBER:
            out["kcal"] = amount / 4.184

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
def _extract_foods_from_json(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if not isinstance(data, dict):
        return []
    for key in _JSON_FOOD_LIST_KEYS:
        value = data.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    return []


def _extract_nutrients(item: dict[str, Any]) -> list[dict[str, Any]]:
    nutrients = item.get("foodNutrients")
    if isinstance(nutrients, list):
        return [x for x in nutrients if isinstance(x, dict)]
    return []


def _extract_energy_and_macros(nutrients: list[dict[str, Any]]) -> tuple[float | None, bool]:
    energy_kcal: float | None = None
    energy_kj: float | None = None
    protein: float | None = None
    fat: float | None = None
    carb: float | None = None

    for n in nutrients:
        code = str(n.get("nutrientNumber") or n.get("number") or "").strip()
        name = str(n.get("nutrientName") or n.get("name") or "").strip().lower()
        raw_amount = n.get("value") if n.get("value") is not None else n.get("amount")
        amount = _to_float(raw_amount)
        if amount is None:
            continue

        if code in ENERGY_KCAL_CODES or "energy" in name and "kj" not in name:
            energy_kcal = amount
        elif code in ENERGY_KJ_CODES or "kj" in name:
            energy_kj = amount

        if code in PROTEIN_CODES or "protein" in name:
            protein = amount
        elif code in FAT_CODES or "fat" in name:
            fat = amount
        elif code in CARB_CODES or "carbohydrate" in name:
            carb = amount

    if energy_kcal is not None:
        return energy_kcal, False
    if energy_kj is not None:
        return energy_kj / 4.184, False
    if protein is not None and fat is not None and carb is not None:
        return protein * 4.0 + fat * 9.0 + carb * 4.0, True
    return None, False


def _extract_record_from_json_item(item: dict[str, Any]) -> tuple[str, float | None, int | None, bool, list[dict[str, Any]]]:
    name = str(item.get("description") or item.get("name") or "").strip()
    fdc_id_value = item.get("fdcId") or item.get("fdc_id")
    fdc_id = int(fdc_id_value) if isinstance(fdc_id_value, int) or str(fdc_id_value).isdigit() else None

    direct_kcal = _to_float(item.get("kcal_per_100g") or item.get("energy_kcal") or item.get("energy"))
    nutrients = _extract_nutrients(item)

    if direct_kcal is not None:
        return name, direct_kcal, fdc_id, False, nutrients

    kcal, estimated = _extract_energy_and_macros(nutrients)
    return name, kcal, fdc_id, estimated, nutrients

def import_from_json(conn: sqlite3.Connection, json_path: Path, source: str) -> tuple[int, int]:
    _seed_nutrient_meta(conn)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    foods = data.get("foods") if isinstance(data, dict) else data
    if not isinstance(foods, list):
        raise ValueError("Unsupported JSON structure")

    imported = 0
    skipped = 0

def _save_nutrients(conn: sqlite3.Connection, food_id: int, nutrients: list[dict[str, Any]]) -> None:
    for n in nutrients:
        raw_amount = n.get("value") if n.get("value") is not None else n.get("amount")
        amount = _to_float(raw_amount)
        if amount is None:
            continue
        upsert_food_nutrient(
            conn,
            food_id=food_id,
            nutrient_code=str(n.get("nutrientNumber") or n.get("number") or "").strip() or None,
            nutrient_name=str(n.get("nutrientName") or n.get("name") or "").strip(),
            unit=str(n.get("unitName") or n.get("unit") or "").strip() or None,
            amount=amount,
        )


def import_from_json(conn: sqlite3.Connection, json_path: Path, source: str, dataset: str) -> tuple[int, int, Counter[str]]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    foods = _extract_foods_from_json(data)

    imported = 0
    skipped_missing_energy = 0
    skip_reasons: Counter[str] = Counter()
    for item in foods:
        name, kcal, fdc_id, estimated, nutrients = _extract_record_from_json_item(item)
        if not name:
            skip_reasons["missing_name"] += 1
            continue
        parsed = _extract_record_from_json_item(item)
        if parsed is None:
            skipped += 1
            continue
        name, kcal, fdc_id, nutrients = parsed
        food_id = upsert_food(conn, name=name, kcal_per_100g=kcal, source=source, fdc_id=fdc_id)
        for k, v in nutrients.items():
            upsert_food_nutrient(conn, food_id=food_id, nutrient_key=k, amount_per_100g=v)

        if kcal is None:
            skipped_missing_energy += 1
            skip_reasons["missing_energy_imported_nutrients"] += 1

        food_id = upsert_food(
            conn,
            name=name,
            kcal_per_100g=kcal,
            source=f"{source}:{dataset}",
            fdc_id=fdc_id,
            energy_estimated=estimated,
        )
        _save_nutrients(conn, food_id, nutrients)
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
    return imported, skipped_missing_energy, skip_reasons


def import_from_csv(conn: sqlite3.Connection, csv_path: Path, source: str, dataset: str) -> tuple[int, int, Counter[str]]:
    imported = 0
    skipped_missing_energy = 0
    skip_reasons: Counter[str] = Counter()
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = (row.get("description") or row.get("name") or "").strip()
            if not name:
                skip_reasons["missing_name"] += 1
                continue
            fdc_id_raw = (row.get("fdc_id") or row.get("fdcId") or "").strip()
            fdc_id = int(fdc_id_raw) if fdc_id_raw.isdigit() else None
            kcal = _to_float(row.get("kcal_per_100g") or row.get("energy_kcal") or row.get("energy") or row.get("Energy"))
            if kcal is None:
                skipped_missing_energy += 1
                skip_reasons["missing_energy_imported"] += 1
            upsert_food(conn, name=name, kcal_per_100g=kcal, source=f"{source}:{dataset}", fdc_id=fdc_id)
            imported += 1
    conn.commit()
    return imported, skipped_missing_energy, skip_reasons


def _collect_input_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if not input_path.is_dir():
        return []
    json_files = sorted(input_path.glob("*_food_json_*.json"))
    if json_files:
        return json_files
    return sorted([p for p in input_path.iterdir() if p.is_file() and p.suffix.lower() in {".json", ".csv"}])


def run_import(*, db_path: Path, input_paths: list[Path], source: str = "fdc") -> tuple[int, int, dict[str, int], list[tuple[str, int]]]:
    conn = connect_db(db_path)
    try:
        init_db(conn)
        if input_path.suffix.lower() == ".json":
            return import_from_json(conn, input_path, source)
        if input_path.suffix.lower() == ".csv":
            return import_from_csv(conn, input_path, source)
        raise ValueError("Unsupported file type. Use .json or .csv")
        imported_total = 0
        skipped_total = 0
        by_dataset: dict[str, int] = defaultdict(int)
        reasons: Counter[str] = Counter()

        for root in input_paths:
            files = _collect_input_files(root)
            for file_path in files:
                dataset = file_path.stem.lower()
                if file_path.suffix.lower() == ".json":
                    imported, skipped, skip_reasons = import_from_json(conn, file_path, source, dataset)
                elif file_path.suffix.lower() == ".csv":
                    imported, skipped, skip_reasons = import_from_csv(conn, file_path, source, dataset)
                else:
                    continue
                imported_total += imported
                skipped_total += skipped
                by_dataset[dataset] += imported
                reasons.update(skip_reasons)

        return imported_total, skipped_total, dict(by_dataset), reasons.most_common(8)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import local FDC data into SQLite")
    parser.add_argument("--db", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--source", default="fdc")
    parser.add_argument("--db", required=True, help="SQLite DB path")
    parser.add_argument("--input", action="append", required=True, help="Input JSON/CSV file or directory. Can be used multiple times")
    parser.add_argument("--source", default="fdc", help="Data source label")
    args = parser.parse_args()

    input_paths = [Path(p) for p in args.input]
    for path in input_paths:
        if not path.exists():
            raise SystemExit(f"Input path not found: {path}")

    imported, skipped = run_import(db_path=db_path, input_path=input_path, source=args.source)
    print(f"Import done. imported={imported} skipped_missing_energy={skipped} db={db_path}")
    imported, skipped_missing_energy, by_dataset, skip_reasons = run_import(
        db_path=Path(args.db),
        input_paths=input_paths,
        source=args.source,
    )
    print(f"Import done. imported={imported} skipped_missing_energy={skipped_missing_energy} db={args.db}")
    print(f"By dataset: {by_dataset}")
    print(f"Skip reasons top: {skip_reasons}")


if __name__ == "__main__":
    main()
