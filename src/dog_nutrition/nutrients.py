from __future__ import annotations

FDC_NUTRIENT_TO_KEY = {
    "1008": "energy_kcal",
    "1062": "energy_kj",
    "1003": "protein",
    "1004": "fat",
    "1005": "carbohydrate",
}

KEY_NUTRIENTS = {
    "energy_kcal": ("Energy", "kcal", "1008"),
    "energy_kj": ("Energy", "kJ", "1062"),
    "protein": ("Protein", "g", "1003"),
    "fat": ("Total lipid (fat)", "g", "1004"),
    "carbohydrate": ("Carbohydrate", "g", "1005"),
}
