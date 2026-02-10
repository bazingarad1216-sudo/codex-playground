import pytest

from dog_nutrition.energy import calculate_mer, calculate_rer
from dog_nutrition.models import DogProfile


@pytest.mark.parametrize(
    ("weight_kg", "expected_rer"),
    [
        (5.0, 234.03),
        (10.0, 393.64),
        (20.0, 662.05),
    ],
)
def test_calculate_rer(weight_kg: float, expected_rer: float) -> None:
    assert calculate_rer(weight_kg) == pytest.approx(expected_rer, rel=1e-3)


@pytest.mark.parametrize(
    ("activity", "expected_mer"),
    [
        ("low", 551.09),
        ("normal", 629.82),
        ("high", 787.28),
    ],
)
def test_calculate_mer_by_activity(activity: str, expected_mer: float) -> None:
    profile = DogProfile(weight_kg=10.0, neutered=True, activity=activity)
    assert calculate_mer(profile) == pytest.approx(expected_mer, rel=1e-3)
