from __future__ import annotations

from dataclasses import dataclass
import math


# Packed-planets coordinate-space centers inferred from the parsed save data.
# Sylva occupies the origin coordinate space. The six other planetary bodies
# are offset by roughly 800,000 Unreal units along one cardinal axis.
PLANET_CENTERS = {
    "Sylva":   (0.0, 0.0, 0.0),
    "Desolo":  (0.0, 800000.0, 0.0),
    "Calidor": (-800000.0, 0.0, 0.0),
    "Vesania": (800000.0, 0.0, 0.0),
    "Novus":   (0.0, 0.0, 800000.0),
    "Glacio":  (0.0, -800000.0, 0.0),
    "Atrox":   (0.0, 0.0, -800000.0),
}

SPECIAL_LOCATION_CENTERS = {
    # Controlled v0.34b calibration:
    # OP = (816111.375, -789623.5625, 1120.7783)
    "Orbital Platform": (800000.0, -800000.0, 0.0),

    # Controlled v0.38 calibration:
    # Unidentified Satellite = (824886.3125, 821708.8125, 784.7471)
    "Unidentified Satellite": (800000.0, 800000.0, 0.0),

    # Controlled v0.39 calibration:
    # Sun Room = (-806479.625, -816042.375, 218.8142)
    "Sun Room": (-800000.0, -800000.0, 0.0),
}

# Conservative radius; both special regions are far from each other and planets.
SPECIAL_LOCATION_RADIUS = 150000.0


@dataclass
class PlanetClassification:
    planet: str
    center_x: float
    center_y: float
    center_z: float
    distance_from_center: float
    second_closest_planet: str
    second_closest_distance: float


def classify_planet(x: float, y: float, z: float) -> PlanetClassification:
    # Special locations are checked first. They occupy distinct combined-axis
    # coordinate regions that would otherwise look closest to a planet center.
    for name, (cx, cy, cz) in SPECIAL_LOCATION_CENTERS.items():
        distance = math.sqrt(
            (x - cx) ** 2 +
            (y - cy) ** 2 +
            (z - cz) ** 2
        )
        if distance <= SPECIAL_LOCATION_RADIUS:
            # Find nearest ordinary planet only as a diagnostic second choice.
            ordinary = []
            for p_name, (px, py, pz) in PLANET_CENTERS.items():
                pd = math.sqrt(
                    (x - px) ** 2 +
                    (y - py) ** 2 +
                    (z - pz) ** 2
                )
                ordinary.append((pd, p_name))
            ordinary.sort()

            return PlanetClassification(
                planet=name,
                center_x=cx,
                center_y=cy,
                center_z=cz,
                distance_from_center=distance,
                second_closest_planet=ordinary[0][1],
                second_closest_distance=ordinary[0][0],
            )

    distances = []

    for name, (cx, cy, cz) in PLANET_CENTERS.items():
        d = math.sqrt(
            (x - cx) ** 2 +
            (y - cy) ** 2 +
            (z - cz) ** 2
        )
        distances.append((d, name, cx, cy, cz))

    distances.sort(key=lambda item: item[0])

    best = distances[0]
    second = distances[1]

    return PlanetClassification(
        planet=best[1],
        center_x=best[2],
        center_y=best[3],
        center_z=best[4],
        distance_from_center=best[0],
        second_closest_planet=second[1],
        second_closest_distance=second[0],
    )
