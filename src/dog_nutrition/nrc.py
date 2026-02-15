from __future__ import annotations

from dataclasses import dataclass

from .energy import calculate_mer
from .models import DogProfile


@dataclass(frozen=True)
class NutrientRequirement:
    nutrient_key: str
    min_per_day: float
    suggest_per_day: float
    max_per_day: float | None


NRC_PER_1000KCAL = {
    "protein_g": (45.0, 52.0, None),
    "fat_g": (13.8, 16.0, None),
    "ca_mg": (1250.0, 1500.0, 6250.0),
    "p_mg": (1000.0, 1200.0, 4000.0),
    "k_mg": (1500.0, 1700.0, None),
    "na_mg": (200.0, 300.0, 3200.0),
    "mg_mg": (150.0, 170.0, None),
    "fe_mg": (7.5, 10.0, 75.0),
    "zn_mg": (15.0, 20.0, 300.0),
    "cu_mg": (1.5, 1.8, 30.0),
    "mn_mg": (1.2, 1.6, 24.0),
    "se_ug": (90.0, 100.0, 900.0),
    "iodine_ug": (220.0, 300.0, 2200.0),
    "vit_a_ug": (379.0, 500.0, 18750.0),
    "vit_d_ug": (3.4, 5.0, 80.0),
    "vit_e_mg": (7.5, 10.0, None),
}


def requirements_for_profile(profile: DogProfile) -> tuple[float, list[NutrientRequirement]]:
    mer = calculate_mer(profile)
    scale = mer / 1000.0
    reqs = [
        NutrientRequirement(
            nutrient_key=k,
            min_per_day=min_v * scale,
            suggest_per_day=suggest_v * scale,
            max_per_day=(max_v * scale if max_v is not None else None),
        )
        for k, (min_v, suggest_v, max_v) in NRC_PER_1000KCAL.items()
    ]
    return mer, reqs


def nrc_status(actual: float, minimum: float, maximum: float | None) -> str:
    if actual < minimum:
        return "LOW"
    if maximum is not None and actual > maximum:
        return "HIGH"
    return "OK"
