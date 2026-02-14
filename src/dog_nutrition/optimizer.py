from __future__ import annotations

from dataclasses import dataclass

from .foods_db import get_food_nutrients
from .nrc import requirements_for_profile
from .toxicity import is_toxic_food_name


@dataclass(frozen=True)
class FormulaItem:
    food_id: int
    food_name: str
    grams: float


@dataclass(frozen=True)
class FormulaResult:
    feasible: bool
    reason: str
    items: list[FormulaItem]


def _compute_totals(grams, nutrient_by_food):
    totals: dict[str, float] = {}
    for idx, g in enumerate(grams):
        for nutrient_key, amount_per_100g in nutrient_by_food[idx].items():
            totals[nutrient_key] = totals.get(nutrient_key, 0.0) + amount_per_100g * g / 100.0
    return totals


def optimize_recipe(conn, profile, food_ids: list[int]) -> FormulaResult:
    foods = []
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
        return FormulaResult(False, "no safe foods available", [])

    mer, reqs = requirements_for_profile(profile)
    n = len(foods)
    grams = [mer / n / (nutrient_by_food[i]["kcal"] / 100.0) for i in range(n)]

    for _ in range(80):
        totals = _compute_totals(grams, nutrient_by_food)
        unmet = [r for r in reqs if totals.get(r.nutrient_key, 0.0) < r.min_per_day]
        exceeded = [r for r in reqs if r.max_per_day is not None and totals.get(r.nutrient_key, 0.0) > r.max_per_day]
        if not unmet and not exceeded:
            items = [
                FormulaItem(food_id=foods[i][0], food_name=foods[i][1], grams=round(float(g), 1))
                for i, g in enumerate(grams)
                if g > 0.1
            ]
            return FormulaResult(True, "ok", items)

        for req in unmet:
            best_idx = max(range(n), key=lambda i: nutrient_by_food[i].get(req.nutrient_key, 0.0))
            density = nutrient_by_food[best_idx].get(req.nutrient_key, 0.0)
            if density <= 0:
                continue
            gap = req.min_per_day - totals.get(req.nutrient_key, 0.0)
            grams[best_idx] += (gap / density) * 100.0

        for req in exceeded:
            worst_idx = max(range(n), key=lambda i: nutrient_by_food[i].get(req.nutrient_key, 0.0))
            density = nutrient_by_food[worst_idx].get(req.nutrient_key, 0.0)
            if density <= 0:
                continue
            over = totals.get(req.nutrient_key, 0.0) - (req.max_per_day or 0)
            grams[worst_idx] = max(0.0, grams[worst_idx] - (over / density) * 100.0)

    return FormulaResult(False, "no feasible solution", [])
