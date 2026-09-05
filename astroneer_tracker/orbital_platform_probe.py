from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import struct
import zlib


PLANET_ENUM_TO_NAME = {
    "EPlanetIdentifier::Terran": "Sylva",
    "EPlanetIdentifier::TerranMoon": "Desolo",
    "EPlanetIdentifier::Arid": "Calidor",
    "EPlanetIdentifier::Exotic": "Vesania",
    "EPlanetIdentifier::ExoticMoon": "Novus",
    "EPlanetIdentifier::Tundra": "Glacio",
    "EPlanetIdentifier::Radiated": "Atrox",
}


@dataclass
class OrbitalPlatformProbeResult:
    count: int
    actor_ids: list[str]
    orbiting_planets: list[str]
    stages_by_actor: dict[str, int]
    error: str | None = None


class R:
    def __init__(self, data: bytes):
        self.d = data
        self.p = 0

    def take(self, n: int) -> bytes:
        if n < 0 or self.p + n > len(self.d):
            raise ValueError("read past end")
        b = self.d[self.p:self.p+n]
        self.p += n
        return b

    def u8(self): return struct.unpack("<B", self.take(1))[0]
    def u16(self): return struct.unpack("<H", self.take(2))[0]
    def u32(self): return struct.unpack("<I", self.take(4))[0]
    def i32(self): return struct.unpack("<i", self.take(4))[0]
    def i64(self): return struct.unpack("<q", self.take(8))[0]
    def u128(self): return int.from_bytes(self.take(16), "little")

    def string(self) -> str:
        n = self.i32()
        if n == 0:
            return ""
        if n < 0:
            return self.take(-n * 2).decode(
                "utf-16-le", errors="replace"
            ).rstrip("\0")
        return self.take(n).decode("utf-8", errors="replace").rstrip("\0")


def _fname(names: list[str], encoded_index: int) -> str:
    # This save family uses one-based FName references in tagged properties.
    if 1 <= encoded_index <= len(names):
        return names[encoded_index - 1]
    if 0 <= encoded_index < len(names):
        return names[encoded_index]
    return ""


def probe_orbital_platforms(path: Path) -> OrbitalPlatformProbeResult:
    try:
        raw = path.read_bytes()
        d = zlib.decompress(raw[16:])

        actor_ids = sorted({
            x.decode("ascii", errors="ignore")
            for x in re.findall(rb"BP_MS_OrbitalPlatform_C_(\d+)", d)
        })
        if not actor_ids:
            return OrbitalPlatformProbeResult(0, [], [], {})

        r = R(d)

        r.u32(); r.i32(); r.i32()
        r.u16(); r.u16(); r.u16()
        r.u32(); r.string()
        r.i32()
        custom_count = r.u32()
        for _ in range(custom_count):
            r.u128(); r.i32()
        r.string(); r.string()
        r.i32(); r.u32()
        if r.p < len(d) and d[r.p] == 0:
            r.p += 1
        r.string(); r.u32(); r.u32()

        string_count = r.i64()
        names = [r.string() for _ in range(max(0, string_count - 1))]

        try:
            orbit_prop_encoded = (
                names.index("REP_OrbitingPlanetIdentifier") + 1
            )
        except ValueError:
            orbit_prop_encoded = None

        object_count = r.u32()
        orbiting_planets: list[str] = []
        stages_by_actor: dict[str, int] = {}

        for _ in range(object_count):
            object_type = r.string()
            r.i32()  # object-name string-table index
            r.u32()  # flags
            save_flags = r.u8()
            r.i32()  # outer
            data_offset = r.u32()
            total_size = r.u32() if save_flags & 4 else 0
            data_bytes = r.take(data_offset)
            if total_size:
                r.take(total_size - data_offset)

            if (
                orbit_prop_encoded is None
                or "BP_MS_OrbitalPlatform.BP_MS_OrbitalPlatform_C"
                not in object_type
            ):
                continue

            # Decode REP_Stage from the same live platform object.
            try:
                stage_prop_encoded = names.index("REP_Stage") + 1
            except ValueError:
                stage_prop_encoded = None

            if stage_prop_encoded is not None:
                stage_target = struct.pack("<I", stage_prop_encoded)
                stage_pos = data_bytes.find(stage_target)
                if stage_pos >= 0 and stage_pos + 21 <= len(data_bytes):
                    # Observed byte property layout:
                    # +00 property FName
                    # +04 property type FName
                    # +08 payload size
                    # +12 array index
                    # +16 one-byte property-guid flag
                    # +17 payload value
                    raw_stage = int(data_bytes[stage_pos + 17])
                    display_stage = raw_stage + 1

                    actor_match = re.search(
                        rb"BP_MS_OrbitalPlatform_C_(\d+)",
                        d,
                    )
                    if actor_match:
                        actor_id = actor_match.group(1).decode(
                            "ascii", errors="ignore"
                        )
                        stages_by_actor[actor_id] = display_stage

            target = struct.pack("<I", orbit_prop_encoded)
            pos = data_bytes.find(target)
            if pos < 0:
                continue

            # Observed tagged EnumProperty layout in the controlled save:
            #  +00 property FName
            #  +04 EnumProperty FName
            #  +08 payload size
            #  +12 array index
            #  +16 enum type FName
            #  +20 one-byte property-guid flag
            #  +21 enum value FName
            if pos + 25 > len(data_bytes):
                continue

            enum_value_index = struct.unpack(
                "<I",
                data_bytes[pos + 21:pos + 25],
            )[0]
            enum_value = _fname(names, enum_value_index)
            planet = PLANET_ENUM_TO_NAME.get(enum_value)
            if planet and planet not in orbiting_planets:
                orbiting_planets.append(planet)

        return OrbitalPlatformProbeResult(
            count=len(actor_ids),
            actor_ids=actor_ids,
            orbiting_planets=orbiting_planets,
            stages_by_actor=stages_by_actor,
        )

    except Exception as exc:
        return OrbitalPlatformProbeResult(
            count=0,
            actor_ids=[],
            orbiting_planets=[],
            stages_by_actor={},
            error=f"{type(exc).__name__}: {exc}",
        )
