from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
import zlib


@dataclass
class SaveParseProbeResult:
    compressed_size: int
    decompressed_size: int
    outer_header_hex: str
    format_tag: int | None = None
    save_game_version: int | None = None
    package_version: int | None = None
    engine_major: int | None = None
    engine_minor: int | None = None
    engine_patch: int | None = None
    engine_build: int | None = None
    engine_build_id: str | None = None
    save_class: str | None = None
    end_of_header1: str | None = None
    end_of_header2: int | None = None
    astro_save_version: int | None = None
    level_name: str | None = None
    chunk_save_version: int | None = None
    string_table_count: int | None = None
    first_strings: list[str] | None = None
    error: str | None = None


class Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def remaining(self) -> int:
        return len(self.data) - self.pos

    def take(self, n: int) -> bytes:
        if n < 0 or self.pos + n > len(self.data):
            raise ValueError(
                f"Read past end at offset {self.pos:,}: requested {n:,}, "
                f"remaining {self.remaining():,}"
            )
        out = self.data[self.pos:self.pos+n]
        self.pos += n
        return out

    def u16(self) -> int:
        return struct.unpack("<H", self.take(2))[0]

    def u32(self) -> int:
        return struct.unpack("<I", self.take(4))[0]

    def i32(self) -> int:
        return struct.unpack("<i", self.take(4))[0]

    def i64(self) -> int:
        return struct.unpack("<q", self.take(8))[0]

    def u128(self) -> int:
        return int.from_bytes(self.take(16), "little", signed=False)

    def string(self) -> str:
        size = self.i32()

        if size == 0:
            return ""

        # The historical Astroneer parser expects positive UTF-8 byte lengths.
        if size < 0:
            # Unreal FString convention: negative lengths are UTF-16 code units.
            units = -size
            raw = self.take(units * 2)
            text = raw.decode("utf-16-le", errors="replace")
            return text.rstrip("\x00")

        raw = self.take(size)
        return raw.decode("utf-8", errors="replace").rstrip("\x00")


def parse_save_probe(path: Path) -> SaveParseProbeResult:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return SaveParseProbeResult(0, 0, "", error=str(exc))

    if len(raw) <= 16:
        return SaveParseProbeResult(
            len(raw), 0, raw.hex(" "),
            error="File is too small to contain the 16-byte outer header plus payload."
        )

    outer = raw[:16]
    compressed = raw[16:]

    try:
        decompressed = zlib.decompress(compressed)
    except Exception as exc:
        return SaveParseProbeResult(
            compressed_size=len(compressed),
            decompressed_size=0,
            outer_header_hex=outer.hex(" "),
            error=f"zlib decompression after byte 16 failed: {type(exc).__name__}: {exc}",
        )

    result = SaveParseProbeResult(
        compressed_size=len(compressed),
        decompressed_size=len(decompressed),
        outer_header_hex=outer.hex(" "),
        first_strings=[],
    )

    try:
        r = Reader(decompressed)

        # Header::deserialize from astro_save_parser
        result.format_tag = r.u32()
        result.save_game_version = r.i32()
        result.package_version = r.i32()

        result.engine_major = r.u16()
        result.engine_minor = r.u16()
        result.engine_patch = r.u16()
        result.engine_build = r.u32()
        result.engine_build_id = r.string()

        # CustomFormatData
        _custom_version = r.i32()
        custom_count = r.u32()
        if custom_count > 10000:
            raise ValueError(f"Implausible custom format count: {custom_count}")

        for _ in range(custom_count):
            r.u128()
            r.i32()

        result.save_class = r.string()
        result.end_of_header1 = r.string()
        result.end_of_header2 = r.i32()

        # AstroLevelSaveChunk begins here.
        result.astro_save_version = r.u32()
        result.level_name = r.string()

        # AstroSaveChunk begins here.
        result.chunk_save_version = r.u32()

        # StringTable::deserialize
        count = r.i64()
        result.string_table_count = count

        if count < 0 or count > 2_000_000:
            raise ValueError(f"Implausible string table count: {count}")

        # Historical parser reads count-1 strings.
        to_read = max(0, count - 1)
        preview_limit = min(to_read, 100)

        strings = []
        for i in range(to_read):
            s = r.string()
            if i < preview_limit:
                strings.append(s)

        result.first_strings = strings

    except Exception as exc:
        result.error = (
            f"Decompression succeeded, but structured parse stopped at "
            f"decompressed offset {getattr(locals().get('r', None), 'pos', 0):,}: "
            f"{type(exc).__name__}: {exc}"
        )

    return result
