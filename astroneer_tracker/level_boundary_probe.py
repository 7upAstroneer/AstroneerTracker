from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import binascii
import struct
import zlib


@dataclass
class BoundaryProbeResult:
    decompressed_size: int
    astro_save_version: int | None
    boundary_offset: int | None
    next_i32: int | None
    next_u32: int | None
    next_i64: int | None
    bytes_hex: str
    bytes_ascii: str
    candidate_level_name: str | None
    after_candidate_offset: int | None
    candidate_chunk_version: int | None
    candidate_string_count: int | None
    error: str | None = None


class Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def take(self, n: int) -> bytes:
        if n < 0 or self.pos + n > len(self.data):
            raise ValueError(
                f"Read past end at offset {self.pos:,}; requested {n:,}, "
                f"remaining {len(self.data)-self.pos:,}"
            )
        out = self.data[self.pos:self.pos+n]
        self.pos += n
        return out

    def u16(self):
        return struct.unpack("<H", self.take(2))[0]

    def u32(self):
        return struct.unpack("<I", self.take(4))[0]

    def i32(self):
        return struct.unpack("<i", self.take(4))[0]

    def u128(self):
        return int.from_bytes(self.take(16), "little")

    def string(self):
        n = self.i32()
        if n == 0:
            return ""
        if n < 0:
            units = -n
            return self.take(units * 2).decode("utf-16-le", errors="replace").rstrip("\x00")
        return self.take(n).decode("utf-8", errors="replace").rstrip("\x00")


def _ascii_preview(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b <= 126 else "." for b in data)


def probe_level_boundary(path: Path) -> BoundaryProbeResult:
    try:
        raw = path.read_bytes()
        dec = zlib.decompress(raw[16:])
    except Exception as exc:
        return BoundaryProbeResult(
            0, None, None, None, None, None, "", "", None, None, None, None,
            f"Container/decompression failed: {type(exc).__name__}: {exc}"
        )

    try:
        r = Reader(dec)

        # UE save header, matching the historical parser.
        r.u32()  # format tag
        r.i32()  # save_game_version
        r.i32()  # package_version

        r.u16()
        r.u16()
        r.u16()
        r.u32()
        r.string()  # engine build id

        r.i32()  # custom format version
        custom_count = r.u32()
        if custom_count > 10000:
            raise ValueError(f"Implausible custom format count {custom_count}")
        for _ in range(custom_count):
            r.u128()
            r.i32()

        r.string()  # save class
        r.string()  # end header string
        r.i32()     # end header int

        astro_version = r.u32()
        boundary = r.pos

        preview = dec[boundary:boundary+128]
        next_i32 = struct.unpack("<i", dec[boundary:boundary+4])[0] if len(preview) >= 4 else None
        next_u32 = struct.unpack("<I", dec[boundary:boundary+4])[0] if len(preview) >= 4 else None
        next_i64 = struct.unpack("<q", dec[boundary:boundary+8])[0] if len(preview) >= 8 else None

        candidate_name = None
        after = None
        chunk_version = None
        string_count = None

        # Interpret the bytes exactly as the old parser expects:
        # FString length + bytes, then u32 chunk version, then i64 string table count.
        try:
            q = Reader(dec)
            q.pos = boundary
            candidate_name = q.string()
            after = q.pos
            chunk_version = q.u32()
            string_count = struct.unpack("<q", q.take(8))[0]
        except Exception:
            pass

        return BoundaryProbeResult(
            decompressed_size=len(dec),
            astro_save_version=astro_version,
            boundary_offset=boundary,
            next_i32=next_i32,
            next_u32=next_u32,
            next_i64=next_i64,
            bytes_hex=binascii.hexlify(preview, sep=b" ").decode("ascii"),
            bytes_ascii=_ascii_preview(preview),
            candidate_level_name=candidate_name,
            after_candidate_offset=after,
            candidate_chunk_version=chunk_version,
            candidate_string_count=string_count,
        )

    except Exception as exc:
        return BoundaryProbeResult(
            len(dec), None, None, None, None, None, "", "", None, None, None, None,
            f"Header parse failed: {type(exc).__name__}: {exc}"
        )
