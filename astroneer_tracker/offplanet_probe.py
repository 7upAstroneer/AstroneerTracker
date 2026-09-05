from __future__ import annotations

from dataclasses import dataclass
import math

from .planet_classifier import PLANET_CENTERS


@dataclass
class OffPlanetProbe:
    nearest_planet: str
    nearest_distance: float
    x: float
    y: float
    z: float


def probe_position(x: float, y: float, z: float) -> OffPlanetProbe:
    distances = []
    for name, (cx, cy, cz) in PLANET_CENTERS.items():
        distance = math.sqrt(
            (x - cx) ** 2 +
            (y - cy) ** 2 +
            (z - cz) ** 2
        )
        distances.append((distance, name))

    distances.sort()
    return OffPlanetProbe(
        nearest_planet=distances[0][1],
        nearest_distance=distances[0][0],
        x=x,
        y=y,
        z=z,
    )
