from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
import zlib


CORE_ENGINE_RECORD_BY_PLANET = {
    # Confirmed from controlled pre/post Core saves:
    # actor payload = 124 bytes
    # payload byte 16 = persistent bEngineActivated state
    # 0 = Locked, 1 = Active

    "Sylva": {
        "class_path": (
            b"/Game/Scenarios/Gates/Engines/"
            b"GatewayEngine_Terran.GatewayEngine_Terran_C"
        ),
        "payload_size": 124,
        "activation_offset": 16,
    },

    "Desolo": {
        "class_path": (
            b"/Game/Scenarios/Gates/Engines/"
            b"GatewayEngine_TerranMoon.GatewayEngine_TerranMoon_C"
        ),
        "payload_size": 124,
        "activation_offset": 16,
    },

    "Glacio": {
        "class_path": (
            b"/Game/Scenarios/Gates/Engines/"
            b"GatewayEngine_Tundra.GatewayEngine_Tundra_C"
        ),
        "payload_size": 124,
        "activation_offset": 16,
    },

    "Vesania": {
        "class_path": (
            b"/Game/Scenarios/Gates/Engines/"
            b"GatewayEngine_Exotic.GatewayEngine_Exotic_C"
        ),
        "payload_size": 124,
        "activation_offset": 16,
    },

    "Atrox": {
        "class_path": (
            b"/Game/Scenarios/Gates/Engines/"
            b"GatewayEngine_Radiated.GatewayEngine_Radiated_C"
        ),
        "payload_size": 124,
        "activation_offset": 16,
    },

    "Calidor": {
        "class_path": (
            b"/Game/Scenarios/Gates/Engines/"
            b"GatewayEngine_Arid.GatewayEngine_Arid_C"
        ),
        "payload_size": 124,
        "activation_offset": 16,
    },

    "Novus": {
        "class_path": (
            b"/Game/Scenarios/Gates/Engines/"
            b"GatewayEngine_ExoticMoon.GatewayEngine_ExoticMoon_C"
        ),
        "payload_size": 124,
        "activation_offset": 16,
    },
}


@dataclass
class CoreProbeResult:
    planet: str
    found: bool
    active: bool | None
    engine_token: str | None
    activation_byte: int | None
    note: str


def _decompressed_bytes(path: Path) -> bytes:
    raw = path.read_bytes()

    # Current Astroneer save format used by the tracker has a 16-byte outer
    # header followed by zlib data. Try that known path first.
    try:
        return zlib.decompress(raw[16:])
    except Exception:
        pass

    # Defensive fallback if the outer header changes.
    for sig in (b"\x78\x01", b"\x78\x9c", b"\x78\xda"):
        pos = raw.find(sig)
        while pos >= 0:
            try:
                return zlib.decompress(raw[pos:])
            except Exception:
                pos = raw.find(sig, pos + 1)

    raise ValueError("Could not decompress Astroneer save")


def _engine_payload_candidates(
    raw: bytes,
    class_path: bytes,
    expected_payload_size: int,
) -> list[tuple[int, bytes]]:
    """
    Locate serialized actor records for a specific GatewayEngine class.

    The class path occurs in multiple save sections. A live actor record is
    identified by a little-endian payload-size field shortly after the
    null-terminated class path, followed by exactly that payload.

    Controlled Sylva saves place the 124-byte payload-size field 13 bytes
    after the terminating NUL. We scan a compact range so the parser remains
    tolerant of small metadata-layout shifts while still requiring the exact
    expected payload length.
    """
    candidates: list[tuple[int, bytes]] = []
    needle = class_path + b"\x00"
    start = 0

    while True:
        idx = raw.find(needle, start)
        if idx < 0:
            break

        after = idx + len(needle)

        # Scan only the compact actor-record metadata immediately after class.
        for rel in range(0, 33):
            p = after + rel
            if p + 4 > len(raw):
                break

            size = struct.unpack_from("<I", raw, p)[0]
            if size != expected_payload_size:
                continue

            payload_start = p + 4
            payload_end = payload_start + size
            if payload_end <= len(raw):
                candidates.append(
                    (payload_start, raw[payload_start:payload_end])
                )

        start = idx + 1

    return candidates


def probe_core_activation(path: Path, planet: str) -> CoreProbeResult:
    spec = CORE_ENGINE_RECORD_BY_PLANET.get(planet)

    if spec is None:
        return CoreProbeResult(
            planet=planet,
            found=False,
            active=None,
            engine_token=None,
            activation_byte=None,
            note="planet-specific GatewayEngine record mapping not implemented yet",
        )

    raw = _decompressed_bytes(path)
    class_path = spec["class_path"]
    payload_size = int(spec["payload_size"])
    activation_offset = int(spec["activation_offset"])

    candidates = _engine_payload_candidates(
        raw,
        class_path,
        payload_size,
    )

    if not candidates:
        return CoreProbeResult(
            planet=planet,
            found=False,
            active=None,
            engine_token=class_path.decode("ascii", errors="ignore"),
            activation_byte=None,
            note=(
                f"GatewayEngine actor record not found "
                f"(expected payload {payload_size} bytes)"
            ),
        )

    # There should be one live actor-record candidate. If duplicates appear,
    # accept only candidates whose activation byte is an actual boolean.
    valid: list[tuple[int, int]] = []
    for payload_start, payload in candidates:
        if activation_offset >= len(payload):
            continue
        value = payload[activation_offset]
        if value in (0, 1):
            valid.append((payload_start, value))

    if not valid:
        return CoreProbeResult(
            planet=planet,
            found=True,
            active=None,
            engine_token=class_path.decode("ascii", errors="ignore"),
            activation_byte=None,
            note=(
                f"GatewayEngine record found, but payload byte "
                f"{activation_offset} was not boolean"
            ),
        )

    # The live actor record is the last qualifying occurrence in the
    # decompressed save in the controlled dataset.
    payload_start, value = max(valid, key=lambda item: item[0])

    return CoreProbeResult(
        planet=planet,
        found=True,
        active=bool(value),
        engine_token=class_path.decode("ascii", errors="ignore"),
        activation_byte=value,
        note=(
            f"exact actor payload: {payload_size} bytes; "
            f"bEngineActivated candidate at payload byte "
            f"{activation_offset}={value}; "
            f"payload_start={payload_start}"
        ),
    )
