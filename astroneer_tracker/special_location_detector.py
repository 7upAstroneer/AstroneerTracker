from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import zlib


LANDING_MARKER_TOKEN = b"Game/Exploration/Planet_Marker_LandingPad.Planet_Marker_LandingPad_C"
SUN_ROOM_TOKEN = b"ControlRoomMesh"
ORBITAL_TOKEN = b"Orbital"


@dataclass
class SpecialLocationEvidence:
    sun_room_mesh: int
    orbital_refs: int
    landing_markers: int
    baseline: int | None
    detected: str | None


def _decompressed_bytes(path: Path) -> bytes:
    raw = path.read_bytes()
    if len(raw) < 24:
        return b""
    return zlib.decompress(raw[16:])


def inspect_special_location(
    path: Path,
    save_entry: dict[str, Any],
    ordinary_location: str | None,
) -> SpecialLocationEvidence:
    """
    Port of the proven PowerShell special-location rules.

    Detection order:
      1. Sun Room: ControlRoomMesh present.
      2. Normal seven planets: caller's coordinate result wins and refreshes
         the LandingPad baseline.
      3. Unidentified Satellite: LandingPad count == baseline + 1.
      4. Orbital Platform: >=20 'Orbital' references.
      5. Otherwise use caller's ordinary coordinate classification.

    The LandingPad baseline persists per logical save.
    """
    try:
        raw = _decompressed_bytes(path)
    except Exception:
        raw = b""

    sun_room_mesh = raw.count(SUN_ROOM_TOKEN)
    orbital_refs = raw.count(ORBITAL_TOKEN)
    landing_markers = raw.count(LANDING_MARKER_TOKEN)

    baseline_value = save_entry.get("satellite_marker_baseline")
    baseline = int(baseline_value) if baseline_value is not None else None

    # v0.41: coordinate classification is authoritative for ALL 10 locations.
    #
    # The older PowerShell token/marker logic remains useful diagnostic evidence,
    # but it must never override a positively decoded player coordinate. Developed
    # saves can retain high "Orbital" counts even after returning to a planet.
    #
    # Refresh the legacy LandingPad baseline on normal planets and OP only so the
    # diagnostic remains meaningful, but do not use it to choose location.
    if ordinary_location in {
        "Sylva", "Desolo", "Calidor", "Vesania",
        "Novus", "Glacio", "Atrox", "Orbital Platform",
    }:
        save_entry["satellite_marker_baseline"] = landing_markers
        baseline = landing_markers

    return SpecialLocationEvidence(
        sun_room_mesh,
        orbital_refs,
        landing_markers,
        baseline,
        ordinary_location,
    )
