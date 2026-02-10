from .models import ActivityLevel, DogProfile

# Baseline coefficients by activity level.
# - low: low daily activity
# - normal: typical household activity
# - high: high daily activity / working dog
ACTIVITY_FACTORS: dict[ActivityLevel, float] = {
    "low": 1.4,
    "normal": 1.6,
    "high": 2.0,
}


def calculate_rer(weight_kg: float) -> float:
    """Calculate Resting Energy Requirement (RER)."""
    return 70 * (weight_kg**0.75)


def calculate_mer(profile: DogProfile) -> float:
    """Calculate Maintenance Energy Requirement (MER)."""
    rer = calculate_rer(profile.weight_kg)
    factor = ACTIVITY_FACTORS[profile.activity]
    return rer * factor
