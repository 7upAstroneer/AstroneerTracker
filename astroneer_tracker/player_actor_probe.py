from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import struct
import zlib


@dataclass
class ActorCandidate:
    actor_record_index: int
    object_index: int
    object_type: str
    object_name: str
    child_count: int
    component_count: int
    x: float
    y: float
    z: float
    scale_x: float
    scale_y: float
    scale_z: float


@dataclass
class ParseResult:
    level_name: str | None
    string_table_count: int | None
    object_records_count: int | None
    actor_records_count: int | None
    candidates: list[ActorCandidate]
    error: str | None = None


class R:
    def __init__(self, d: bytes):
        self.d = d
        self.p = 0

    def take(self, n: int) -> bytes:
        if n < 0 or self.p + n > len(self.d):
            raise ValueError(
                f"read past end at offset {self.p:,}; need {n:,}, "
                f"remaining {len(self.d)-self.p:,}"
            )
        b = self.d[self.p:self.p+n]
        self.p += n
        return b

    def u8(self): return struct.unpack("<B", self.take(1))[0]
    def u16(self): return struct.unpack("<H", self.take(2))[0]
    def u32(self): return struct.unpack("<I", self.take(4))[0]
    def i32(self): return struct.unpack("<i", self.take(4))[0]
    def i64(self): return struct.unpack("<q", self.take(8))[0]
    def f32(self): return struct.unpack("<f", self.take(4))[0]
    def u128(self): return int.from_bytes(self.take(16), "little")

    def string(self) -> str:
        n = self.i32()
        if n == 0:
            return ""
        if n < 0:
            units = -n
            if units > 10_000_000:
                raise ValueError(f"implausible UTF-16 string length {units}")
            return self.take(units * 2).decode("utf-16-le", errors="replace").rstrip("\0")
        if n > 10_000_000:
            raise ValueError(f"implausible string length {n}")
        return self.take(n).decode("utf-8", errors="replace").rstrip("\0")


def _safe_name(names: list[str], index: int) -> str:
    # String-table index conventions may reserve one entry. Try both common mappings.
    possibilities = []
    if 0 <= index < len(names):
        possibilities.append(names[index])
    if 1 <= index <= len(names):
        possibilities.append(names[index - 1])

    for value in possibilities:
        if value:
            return value
    return f"<name_index {index}>"


def _interesting(text: str) -> bool:
    low = text.lower()
    hints = (
        "/game/character/designastro.designastro_c",
        "playcontrollerinstance.playcontrollerinstance_c",
        "/script/astro.astroplayerstate",
        "astrocharacter",
    )
    return any(h in low for h in hints)


def parse_player_actor_candidates(path: Path) -> ParseResult:
    d = b""
    names: list[str] = []
    candidates: list[ActorCandidate] = []
    level = None
    count = None
    or_count = None
    ar_count = None

    try:
        raw = path.read_bytes()
        d = zlib.decompress(raw[16:])
        r = R(d)

        # UE SaveGame header.
        r.u32(); r.i32(); r.i32()
        r.u16(); r.u16(); r.u16(); r.u32(); r.string()
        r.i32()
        custom_count = r.u32()
        if custom_count > 10000:
            raise ValueError(f"implausible custom-format count {custom_count}")
        for _ in range(custom_count):
            r.u128(); r.i32()

        r.string()
        r.string()
        r.i32()

        # AstroLevelSaveChunk.
        r.u32()  # astro save version

        # Current save-format compatibility discovered in v0.13-v0.15.
        if r.p < len(r.d) and r.d[r.p] == 0:
            r.p += 1

        level = r.string()

        # Current format has a reserved u32 before AstroSaveChunk.
        r.u32()

        # AstroSaveChunk.
        r.u32()  # chunk save version
        count = r.i64()
        if count < 1 or count > 2_000_000:
            raise ValueError(f"implausible string-table count {count}")

        for _ in range(count - 1):
            names.append(r.string())

        or_count = r.u32()
        if or_count > 2_000_000:
            raise ValueError(f"implausible object-record count {or_count}")

        object_records = []

        for i in range(or_count):
            object_type = r.string()
            name_index = r.i32()
            flags = r.u32()
            save_flags = r.u8()
            outer_object_index = r.i32()
            custom_data_offset = r.u32()

            size = 0
            if save_flags & 4:
                size = r.u32()

            if custom_data_offset > r.p + len(r.d):
                raise ValueError(
                    f"implausible custom_data_offset {custom_data_offset} "
                    f"for object record {i}"
                )

            data = r.take(custom_data_offset)

            custom_data = b""
            if size != 0:
                if size < custom_data_offset:
                    raise ValueError(
                        f"object record {i} size {size} < custom_data_offset {custom_data_offset}"
                    )
                custom_data = r.take(size - custom_data_offset)

            object_records.append(
                (object_type, name_index, flags, save_flags, outer_object_index)
            )

        ar_count = r.u32()
        if ar_count > 2_000_000:
            raise ValueError(f"implausible actor-record count {ar_count}")

        for actor_i in range(ar_count):
            object_index = r.i32()

            child_count = r.i32()
            if child_count < 0 or child_count > 100_000:
                raise ValueError(
                    f"implausible child count {child_count} in actor {actor_i}"
                )
            for _ in range(child_count):
                r.i32()
                r.i32()

            component_count = r.i32()
            if component_count < 0 or component_count > 100_000:
                raise ValueError(
                    f"implausible component count {component_count} in actor {actor_i}"
                )
            for _ in range(component_count):
                r.i32()
                r.i32()

            # Quaternion.
            r.f32(); r.f32(); r.f32(); r.f32()

            # Translation.
            x = r.f32()
            y = r.f32()
            z = r.f32()

            # Scale.
            sx = r.f32()
            sy = r.f32()
            sz = r.f32()

            object_type = ""
            object_name = ""

            # Actor object_index is expected to refer to ObjectSaveRecord.
            if 0 <= object_index < len(object_records):
                obj = object_records[object_index]
                object_type = obj[0]
                object_name = _safe_name(names, obj[1])
            elif 1 <= object_index <= len(object_records):
                obj = object_records[object_index - 1]
                object_type = obj[0]
                object_name = _safe_name(names, obj[1])

            descriptor = f"{object_type} {object_name}"

            if _interesting(descriptor):
                candidates.append(
                    ActorCandidate(
                        actor_record_index=actor_i,
                        object_index=object_index,
                        object_type=object_type,
                        object_name=object_name,
                        child_count=child_count,
                        component_count=component_count,
                        x=x, y=y, z=z,
                        scale_x=sx, scale_y=sy, scale_z=sz,
                    )
                )

        return ParseResult(
            level_name=level,
            string_table_count=count,
            object_records_count=or_count,
            actor_records_count=ar_count,
            candidates=candidates[:100],
            error=None,
        )

    except Exception as exc:
        return ParseResult(
            level_name=level,
            string_table_count=count,
            object_records_count=or_count,
            actor_records_count=ar_count,
            candidates=candidates[:100],
            error=f"{type(exc).__name__}: {exc}",
        )
