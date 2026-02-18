from __future__ import annotations

from dataclasses import dataclass

from .foods_db import get_food_nutrients
from .nrc import nrc_status, requirements_for_profile
from .toxicity import is_toxic_food_name


@dataclass(frozen=True)
class FormulaItem:
    food_id: int
    food_name: str
    grams: float


@dataclass(frozen=True)
class NrcRow:
    nutrient_key: str
    minimum: float
    suggest: float
    maximum: float | None
    actual: float
    status: str


@dataclass(frozen=True)
class FormulaResult:
    feasible: bool
    reason: str
    items: list[FormulaItem]
    nrc_rows: list[NrcRow]


def _compute_totals(grams: list[float], nutrient_by_food: list[dict[str, float]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for idx, g in enumerate(grams):
        for nutrient_key, amount_per_100g in nutrient_by_food[idx].items():
            totals[nutrient_key] = totals.get(nutrient_key, 0.0) + amount_per_100g * g / 100.0
    return totals


def _make_nrc_rows(reqs, totals: dict[str, float]) -> list[NrcRow]:
    rows: list[NrcRow] = []
    for req in reqs:
        actual = totals.get(req.nutrient_key, 0.0)
        rows.append(
            NrcRow(
                nutrient_key=req.nutrient_key,
                minimum=req.min_per_day,
                suggest=req.suggest_per_day,
                maximum=req.max_per_day,
                actual=actual,
                status=nrc_status(actual, req.min_per_day, req.max_per_day),
            )
        )
    return rows


def optimize_recipe(conn, profile, food_ids: list[int]) -> FormulaResult:
    foods: list[tuple[int, str]] = []
    nutrient_by_food: list[dict[str, float]] = []
    for food_id in food_ids:
        row = conn.execute("SELECT id, name FROM foods WHERE id = ?", (food_id,)).fetchone()
        if row is None or is_toxic_food_name(row["name"]):
            continue
        nutrients = {n.nutrient_key: n.amount_per_100g for n in get_food_nutrients(conn, row["id"])}
        if nutrients.get("kcal", 0.0) <= 0:
            continue
        foods.append((row["id"], row["name"]))
        nutrient_by_food.append(nutrients)

    if not foods:
        return FormulaResult(False, "no safe foods available", [], [])

    mer, reqs = requirements_for_profile(profile)
    n = len(foods)
    grams = [mer / n / (nutrient_by_food[i]["kcal"] / 100.0) for i in range(n)]

    for _ in range(120):
        totals = _compute_totals(grams, nutrient_by_food)
        rows = _make_nrc_rows(reqs, totals)
        hard_fail = [row for row in rows if row.status != "OK"]
        if not hard_fail:
            items = [
                FormulaItem(food_id=foods[i][0], food_name=foods[i][1], grams=round(float(g), 1))
                for i, g in enumerate(grams)
                if g > 0.1
            ]
            return FormulaResult(True, "ok", items, rows)

        for row in hard_fail:
            if row.status == "LOW":
                idx = max(range(n), key=lambda i: nutrient_by_food[i].get(row.nutrient_key, 0.0))
                density = nutrient_by_food[idx].get(row.nutrient_key, 0.0)
                if density > 0:
                    grams[idx] += (row.minimum - row.actual) / density * 100.0
            if row.status == "HIGH" and row.maximum is not None:
                idx = max(range(n), key=lambda i: nutrient_by_food[i].get(row.nutrient_key, 0.0))
                density = nutrient_by_food[idx].get(row.nutrient_key, 0.0)
                if density > 0:
                    grams[idx] = max(0.0, grams[idx] - (row.actual - row.maximum) / density * 100.0)

    final_totals = _compute_totals(grams, nutrient_by_food)
    return FormulaResult(False, "no feasible solution", [], _make_nrc_rows(reqs, final_totals))
