from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

LOCATION_TERMS = (
    "Sylva",
    "Desolo",
    "Calidor",
    "Vesania",
    "Novus",
    "Glacio",
    "Atrox",
    "Orbital",
    "Satellite",
    "Sun Room",
)


@dataclass
class LocationProbeResult:
    matched_terms: list[str]
    file_size: int
    error: str | None = None


def probe_location_terms(path: Path) -> LocationProbeResult:
    """
    Development probe only.

    Looks for plain-text/UTF-16 representations of known location names in a
    diagnostic copy of the save. This does not claim the current location yet;
    it helps determine whether location decoding can use direct signatures or
    requires deeper Unreal save parsing.
    """
    try:
        data = path.read_bytes()
    except OSError as exc:
        return LocationProbeResult([], 0, str(exc))

    matches: list[str] = []

    for term in LOCATION_TERMS:
        ascii_sig = term.encode("utf-8").lower()
        utf16_sig = term.encode("utf-16-le").lower()

        lower_data = data.lower()
        if ascii_sig in lower_data or utf16_sig in lower_data:
            matches.append(term)

    return LocationProbeResult(matches, len(data))
