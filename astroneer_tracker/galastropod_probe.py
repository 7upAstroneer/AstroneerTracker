from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import zlib


# Planet -> live terrarium Galastropod actor class.
GALASTROPOD_CLASS_BY_PLANET = {
    "Sylva": b"TerrariumSnail_Sylva_C",
    "Desolo": b"TerrariumSnail_Desolo_C",
    "Calidor": b"TerrariumSnail_Calidor_C",
    "Vesania": b"TerrariumSnail_Vesania_C",
    "Novus": b"TerrariumSnail_Novus_C",
    "Glacio": b"TerrariumSnail_Glacio_C",
    "Atrox": b"TerrariumSnail_Atrox_C",
}

# Friendly names for display. Detection itself uses planet/class, not the name.
GALASTROPOD_NAME_BY_PLANET = {
    "Sylva": "Sylvie",
    "Desolo": "Usagi",
    "Calidor": "Stilgar",
    "Vesania": "Princess",
    "Novus": "Rogal",
    "Glacio": "Bestefar",
    "Atrox": "Enoki",
}


@dataclass
class GalastropodProbeResult:
    present_by_planet: dict[str, bool]
    ids_by_planet: dict[str, list[int]]


def _decompressed_bytes(path: Path) -> bytes:
    raw = path.read_bytes()
    try:
        return zlib.decompress(raw[16:])
    except Exception:
        pass

    for sig in (b"\x78\x01", b"\x78\x9c", b"\x78\xda"):
        pos = raw.find(sig)
        while pos >= 0:
            try:
                return zlib.decompress(raw[pos:])
            except Exception:
                pos = raw.find(sig, pos + 1)

    return raw


def probe_galastropods(path: Path) -> GalastropodProbeResult:
    raw = _decompressed_bytes(path)

    present: dict[str, bool] = {}
    ids: dict[str, list[int]] = {}

    for planet, actor_class in GALASTROPOD_CLASS_BY_PLANET.items():
        # Require an actual numbered live actor, not merely the class-name
        # string in a schema/string table.
        pattern = re.compile(re.escape(actor_class) + rb"_(\d+)")
        values = sorted({int(m) for m in pattern.findall(raw)})
        ids[planet] = values
        present[planet] = bool(values)

    return GalastropodProbeResult(
        present_by_planet=present,
        ids_by_planet=ids,
    )
