from __future__ import annotations

from dataclasses import dataclass

from .models import DogProfile
from .energy import calculate_mer


@dataclass(frozen=True)
class NutrientRequirement:
    nutrient_key: str
    min_per_day: float
    max_per_day: float | None


NRC_PER_1000KCAL = {
    "protein_g": (45.0, None),
    "fat_g": (13.8, None),
    "ca_mg": (1250.0, 6250.0),
    "p_mg": (1000.0, 4000.0),
    "k_mg": (1500.0, None),
    "na_mg": (200.0, 3200.0),
    "mg_mg": (150.0, None),
    "fe_mg": (7.5, 75.0),
    "zn_mg": (15.0, 300.0),
    "cu_mg": (1.5, 30.0),
    "mn_mg": (1.2, 24.0),
    "se_ug": (90.0, 900.0),
    "iodine_ug": (220.0, 2200.0),
    "vit_a_ug": (379.0, 18750.0),
    "vit_d_ug": (3.4, 80.0),
    "vit_e_mg": (7.5, None),
}


def requirements_for_profile(profile: DogProfile) -> tuple[float, list[NutrientRequirement]]:
    mer = calculate_mer(profile)
    scale = mer / 1000.0
    reqs = [
        NutrientRequirement(
            nutrient_key=k,
            min_per_day=v[0] * scale,
            max_per_day=(v[1] * scale if v[1] is not None else None),
        )
        for k, v in NRC_PER_1000KCAL.items()
    ]
    return mer, reqs
