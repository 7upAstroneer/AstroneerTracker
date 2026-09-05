from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import struct, zlib

@dataclass
class Result:
    decompressed_size: int
    astro_save_version: int | None
    level_name: str | None
    extra_post_level_u32: int | None
    chunk_save_version: int | None
    string_table_count: int | None
    first_strings: list[str]
    post_level_bytes: str
    error: str | None = None

class R:
    def __init__(self, d): self.d=d; self.p=0
    def take(self,n):
        if self.p+n>len(self.d):
            raise ValueError(f"read past end at {self.p}, need {n}")
        x=self.d[self.p:self.p+n]; self.p+=n; return x
    def u16(self): return struct.unpack("<H",self.take(2))[0]
    def u32(self): return struct.unpack("<I",self.take(4))[0]
    def i32(self): return struct.unpack("<i",self.take(4))[0]
    def i64(self): return struct.unpack("<q",self.take(8))[0]
    def u128(self): return int.from_bytes(self.take(16),"little")
    def string(self):
        n=self.i32()
        if n==0:return ""
        if n<0:
            return self.take((-n)*2).decode("utf-16-le",errors="replace").rstrip("\0")
        return self.take(n).decode("utf-8",errors="replace").rstrip("\0")

def probe(path: Path) -> Result:
    d=b""
    try:
        raw=path.read_bytes()
        d=zlib.decompress(raw[16:])
        r=R(d)

        # UE header
        r.u32(); r.i32(); r.i32()
        r.u16(); r.u16(); r.u16(); r.u32(); r.string()
        r.i32(); cc=r.u32()
        for _ in range(cc):
            r.u128(); r.i32()
        r.string(); r.string(); r.i32()

        astro_ver=r.u32()

        # Current saves have an extra leading 0 byte before the level FString.
        if r.d[r.p] == 0:
            r.p += 1
        level=r.string()

        post_bytes = d[r.p:r.p+40].hex(" ")

        # v0.14 showed:
        # 00 00 00 00 33 00 00 00 fa 14 00 00 00 00 00 00 ...
        # Treat the first u32 as an extra/reserved field,
        # then 0x33 (51) as AstroSaveChunk save version.
        extra = r.u32()
        chunk = r.u32()
        count = r.i64()

        strings=[]
        if count < 0 or count > 2_000_000:
            raise ValueError(f"implausible string-table count: {count}")

        for i in range(max(0, count-1)):
            s=r.string()
            if i < 80:
                strings.append(s)

        return Result(
            len(d), astro_ver, level, extra, chunk, count,
            strings, post_bytes, None
        )

    except Exception as e:
        return Result(
            len(d),
            locals().get("astro_ver"),
            locals().get("level"),
            locals().get("extra"),
            locals().get("chunk"),
            locals().get("count"),
            locals().get("strings", []),
            locals().get("post_bytes", ""),
            f"{type(e).__name__}: {e}",
        )
