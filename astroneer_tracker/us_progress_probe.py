from __future__ import annotations

from pathlib import Path
import re
import zlib


KEY_RE = re.compile(
    rb"GatewayKey_(?:Terran|TerranMoon|Arid|Exotic|ExoticMoon|Tundra|Radiated)_C_[0-9]+"
)


def _decompress(path: Path) -> bytes:
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
    raise ValueError("could not decompress save")


def probe_us_state(path: Path, all_cores_active: bool) -> tuple[str, int, bool]:
    raw = _decompress(path)
    station_active = b"GateStationActivated" in raw
    live_keys = set(KEY_RE.findall(raw))

    if not station_active:
        return "Locked", len(live_keys), station_active

    if all_cores_active and not live_keys:
        return "Completed", 0, station_active

    return "Active", len(live_keys), station_active
