from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import struct, zlib

@dataclass
class Result:
    decompressed_size: int
    astro_save_version: int | None
    boundary: int | None
    prefix_byte: int | None
    level_name_length: int | None
    level_name: str | None
    post_level_hex: str
    candidate_chunk_version: int | None
    candidate_string_count: int | None
    first_strings: list[str]
    error: str | None = None

class R:
    def __init__(self, d): self.d=d; self.p=0
    def take(self,n):
        if self.p+n>len(self.d): raise ValueError("read past end")
        x=self.d[self.p:self.p+n]; self.p+=n; return x
    def u16(self): return struct.unpack("<H",self.take(2))[0]
    def u32(self): return struct.unpack("<I",self.take(4))[0]
    def i32(self): return struct.unpack("<i",self.take(4))[0]
    def i64(self): return struct.unpack("<q",self.take(8))[0]
    def u128(self): return int.from_bytes(self.take(16),"little")
    def string(self):
        n=self.i32()
        if n==0:return ""
        if n<0:return self.take((-n)*2).decode("utf-16-le",errors="replace").rstrip("\0")
        return self.take(n).decode("utf-8",errors="replace").rstrip("\0")

def probe(path: Path) -> Result:
    try:
        raw=path.read_bytes(); d=zlib.decompress(raw[16:])
        r=R(d)
        r.u32(); r.i32(); r.i32()
        r.u16(); r.u16(); r.u16(); r.u32(); r.string()
        r.i32(); cc=r.u32()
        for _ in range(cc): r.u128(); r.i32()
        r.string(); r.string(); r.i32()
        av=r.u32(); boundary=r.p

        # v0.13 revealed a single 0x00 byte before a normal FString.
        prefix=d[r.p]
        if prefix == 0:
            r.p += 1

        level_len=struct.unpack("<i",d[r.p:r.p+4])[0]
        level=r.string()
        post=d[r.p:r.p+32].hex(" ")

        chunk=r.u32()
        count=r.i64()

        strings=[]
        if 0 <= count <= 2_000_000:
            for i in range(max(0,count-1)):
                s=r.string()
                if i<60: strings.append(s)
        else:
            raise ValueError(f"implausible string-table count after corrected level name: {count}")

        return Result(len(d),av,boundary,prefix,level_len,level,post,chunk,count,strings)
    except Exception as e:
        return Result(len(d) if 'd' in locals() else 0, locals().get('av'), locals().get('boundary'),
                      locals().get('prefix'), locals().get('level_len'), locals().get('level'),
                      locals().get('post',''), locals().get('chunk'), locals().get('count'),
                      locals().get('strings',[]), f"{type(e).__name__}: {e}")
