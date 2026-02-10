import json

import typer

from .energy import ACTIVITY_FACTORS, calculate_mer, calculate_rer
from .models import ActivityLevel, DogProfile

app = typer.Typer(help="Dog nutrition utilities")


@app.command()
def energy(
    weight_kg: float = typer.Option(..., min=0.0001, help="Dog weight in kg"),
    neutered: bool = typer.Option(True, help="Whether the dog is neutered"),
    activity: ActivityLevel = typer.Option(
        "normal",
        help="Activity level: low, normal, high",
        case_sensitive=False,
    ),
) -> None:
    """Compute RER and MER for a dog profile."""
    profile = DogProfile(weight_kg=weight_kg, neutered=neutered, activity=activity)
    rer = calculate_rer(profile.weight_kg)
    mer = calculate_mer(profile)

    typer.echo(
        json.dumps(
            {
                "weight_kg": profile.weight_kg,
                "neutered": profile.neutered,
                "activity": profile.activity,
                "activity_factor": ACTIVITY_FACTORS[profile.activity],
                "rer": round(rer, 2),
                "mer": round(mer, 2),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    app()
