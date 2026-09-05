from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import struct
import zlib

from .planet_classifier import classify_planet


@dataclass
class MegaTechActorProbeResult:
    dls_locations: list[str]
    biodome_actor_ids: list[str]
    biodome_locations: list[str]
    museum_actor_ids: list[str]
    museum_locations: list[str]
    museum_stage_by_actor: dict[str, int]
    error: str | None = None


class R:
    def __init__(self, data: bytes):
        self.d=data
        self.p=0

    def take(self,n:int)->bytes:
        if n<0 or self.p+n>len(self.d):
            raise ValueError("read past end")
        b=self.d[self.p:self.p+n]
        self.p+=n
        return b

    def u8(self): return struct.unpack("<B",self.take(1))[0]
    def u16(self): return struct.unpack("<H",self.take(2))[0]
    def u32(self): return struct.unpack("<I",self.take(4))[0]
    def i32(self): return struct.unpack("<i",self.take(4))[0]
    def i64(self): return struct.unpack("<q",self.take(8))[0]
    def f32(self): return struct.unpack("<f",self.take(4))[0]
    def u128(self): return int.from_bytes(self.take(16),"little")

    def string(self)->str:
        n=self.i32()
        if n==0:return ""
        if n<0:
            return self.take(-n*2).decode(
                "utf-16-le",errors="replace"
            ).rstrip("\0")
        return self.take(n).decode("utf-8",errors="replace").rstrip("\0")


def _safe_name(names:list[str],index:int)->str:
    if 1<=index<=len(names):
        return names[index-1]
    if 0<=index<len(names):
        return names[index]
    return ""


def probe_megatech_actors(path:Path)->MegaTechActorProbeResult:
    try:
        raw=path.read_bytes()
        d=zlib.decompress(raw[16:])
        r=R(d)

        r.u32();r.i32();r.i32()
        r.u16();r.u16();r.u16()
        r.u32();r.string()
        r.i32()
        custom_count=r.u32()
        for _ in range(custom_count):
            r.u128();r.i32()
        r.string();r.string()
        r.i32();r.u32()
        if r.p<len(d) and d[r.p]==0:
            r.p+=1
        r.string();r.u32();r.u32()

        string_count=r.i64()
        names=[r.string() for _ in range(max(0,string_count-1))]

        object_count=r.u32()
        objects=[]
        for _ in range(object_count):
            object_type=r.string()
            name_index=r.i32()
            r.u32()
            save_flags=r.u8()
            outer=r.i32()
            data_offset=r.u32()
            total_size=r.u32() if save_flags&4 else 0
            data_bytes=r.take(data_offset)
            if total_size:
                r.take(total_size-data_offset)
            objects.append(
                (
                    object_type,
                    _safe_name(names,name_index),
                    outer,
                    data_bytes,
                )
            )

        actor_count=r.u32()
        actor_rows=[]
        for _ in range(actor_count):
            object_index=r.i32()

            child_count=r.i32()
            for _ in range(child_count):
                r.i32();r.i32()

            component_count=r.i32()
            for _ in range(component_count):
                r.i32();r.i32()

            for _ in range(4):
                r.f32()
            x=r.f32();y=r.f32();z=r.f32()
            for _ in range(3):
                r.f32()

            actor_rows.append((object_index,x,y,z))

        dls_locations=[]
        biodome_actor_ids=[]
        biodome_locations=[]
        museum_actor_ids=[]
        museum_locations=[]

        for object_index,x,y,z in actor_rows:
            if not (0<=object_index<len(objects)):
                continue
            object_type,object_name,outer,data_bytes=objects[object_index]

            location=classify_planet(x,y,z).planet

            if re.fullmatch(r"BP_MS_Wreck_C_\d+",object_name):
                if location not in dls_locations:
                    dls_locations.append(location)

            bm=re.fullmatch(r"BP_MS_Biodome_C_(\d+)",object_name)
            if bm:
                biodome_actor_ids.append(bm.group(1))
                if location not in biodome_locations:
                    biodome_locations.append(location)

            mm=re.fullmatch(r"BP_MS_Museum_C_(\d+)",object_name)
            if mm:
                actor_id=mm.group(1)
                museum_actor_ids.append(actor_id)
                if location not in museum_locations:
                    museum_locations.append(location)

        # Museum stages confirmed from controlled progression saves.
        #
        # A live BP_MS_Museum_C actor establishes Stage 1.
        # The Stage-2 post-save gains the Museum002_1 progression set while
        # MissionData_ObjectiveMuseum002 disappears.
        museum_stage_by_actor={}
        stage2=(
            b"Megatech_Museum002_1" in d
            or b"MissionData_Objective_Museum002-1_1" in d
        )
        for actor_id in museum_actor_ids:
            museum_stage_by_actor[actor_id]=2 if stage2 else 1

        return MegaTechActorProbeResult(
            dls_locations=dls_locations,
            biodome_actor_ids=sorted(set(biodome_actor_ids)),
            biodome_locations=biodome_locations,
            museum_actor_ids=sorted(set(museum_actor_ids)),
            museum_locations=museum_locations,
            museum_stage_by_actor=museum_stage_by_actor,
        )

    except Exception as exc:
        return MegaTechActorProbeResult(
            dls_locations=[],
            biodome_actor_ids=[],
            biodome_locations=[],
            museum_actor_ids=[],
            museum_locations=[],
            museum_stage_by_actor={},
            error=f"{type(exc).__name__}: {exc}",
        )
