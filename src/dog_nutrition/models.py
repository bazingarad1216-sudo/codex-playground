from dataclasses import dataclass
from typing import Literal

ActivityLevel = Literal["low", "normal", "high"]


@dataclass(frozen=True)
class DogProfile:
    """Minimal profile for daily energy calculation."""

    weight_kg: float
    neutered: bool = True
    activity: ActivityLevel = "normal"

    def __post_init__(self) -> None:
        if self.weight_kg <= 0:
            raise ValueError("weight_kg must be greater than 0")
        if self.activity not in ("low", "normal", "high"):
            raise ValueError("activity must be one of: low, normal, high")
