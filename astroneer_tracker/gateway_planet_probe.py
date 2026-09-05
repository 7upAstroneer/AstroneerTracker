from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import math, struct, zlib
from .planet_classifier import PLANET_CENTERS

TELEPORTER_TYPE="/Game/Scenarios/Gates/ControlPanel/TeleporterControlPanel.TeleporterControlPanel_C"
PLANET_GATEWAY_MAX={"Sylva":6,"Desolo":2,"Calidor":6,"Vesania":6,"Novus":2,"Glacio":6,"Atrox":6}

@dataclass
class GatewayActor:
    actor_record_index:int
    object_index:int
    object_name:str
    x:float;y:float;z:float
    planet:str
    center_distance:float

@dataclass
class GatewayPlanetProbeResult:
    counts:dict[str,int]
    actors:list[GatewayActor]
    object_records_count:int|None
    actor_records_count:int|None
    error:str|None=None

class R:
    def __init__(self,d): self.d=d; self.p=0
    def take(self,n):
        if n<0 or self.p+n>len(self.d): raise ValueError("read past end")
        b=self.d[self.p:self.p+n]; self.p+=n; return b
    def u8(self): return struct.unpack("<B",self.take(1))[0]
    def u16(self): return struct.unpack("<H",self.take(2))[0]
    def u32(self): return struct.unpack("<I",self.take(4))[0]
    def i32(self): return struct.unpack("<i",self.take(4))[0]
    def i64(self): return struct.unpack("<q",self.take(8))[0]
    def f32(self): return struct.unpack("<f",self.take(4))[0]
    def u128(self): return int.from_bytes(self.take(16),"little")
    def string(self):
        n=self.i32()
        if n==0:return ""
        if n<0:return self.take(-n*2).decode("utf-16-le",errors="replace").rstrip("\0")
        return self.take(n).decode("utf-8",errors="replace").rstrip("\0")

def safe_name(names,i):
    if 0<=i<len(names) and names[i]: return names[i]
    if 1<=i<=len(names) and names[i-1]: return names[i-1]
    return ""

def dec(path):
    b=path.read_bytes()
    try:return zlib.decompress(b[16:])
    except Exception:
        for sig in (b"\x78\x01",b"\x78\x9c",b"\x78\xda"):
            p=b.find(sig)
            while p>=0:
                try:return zlib.decompress(b[p:])
                except Exception:p=b.find(sig,p+1)
    raise ValueError("Could not decompress Astroneer save")

def nearest(x,y,z):
    vals=[]
    for p,c in PLANET_CENTERS.items():
        vals.append((math.sqrt((x-c[0])**2+(y-c[1])**2+(z-c[2])**2),p))
    vals.sort()
    return vals[0][1],vals[0][0]

def probe_gateways_by_planet(path:Path)->GatewayPlanetProbeResult:
    counts={p:0 for p in PLANET_GATEWAY_MAX};actors=[];oc=None;ac=None
    try:
        d=dec(path);r=R(d)
        r.u32();r.i32();r.i32();r.u16();r.u16();r.u16();r.u32();r.string()
        r.i32();cc=r.u32()
        for _ in range(cc):r.u128();r.i32()
        r.string();r.string();r.i32();r.u32()
        if r.p<len(d) and d[r.p]==0:r.p+=1
        r.string();r.u32();r.u32()
        sc=r.i64()
        if sc<1 or sc>2_000_000:raise ValueError("implausible string table")
        names=[r.string() for _ in range(sc-1)]
        oc=r.u32();objs=[]
        for _ in range(oc):
            typ=r.string();ni=r.i32();r.u32();sf=r.u8();r.i32();off=r.u32()
            size=r.u32() if sf&4 else 0
            r.take(off)
            if size:r.take(size-off)
            objs.append((typ,safe_name(names,ni)))
        ac=r.u32();seen=set()
        for ai in range(ac):
            oi=r.i32();cc=r.i32()
            for _ in range(cc):r.i32();r.i32()
            nc=r.i32()
            for _ in range(nc):r.i32();r.i32()
            for _ in range(4):r.f32()
            x,y,z=r.f32(),r.f32(),r.f32()
            for _ in range(3):r.f32()
            if not (0<=oi<len(objs)):
                continue
            typ,name=objs[oi]

            # v0.80 correction:
            # The supplied restored save proves that the serialized object NAME
            # is not stable enough to identify an activated surface Gateway.
            # Desolo's real Gateway actor has the exact TeleporterControlPanel
            # CLASS but its object name is "gate_engine_arm_structure".
            #
            # The class path + world-space surface position is the stable signal.
            if typ != TELEPORTER_TYPE:
                continue

            planet,distance=nearest(x,y,z)

            # Surface chambers lie well away from planet center. This rejects
            # engine/helper records while preserving actual surface Gateways.
            if not (25_000<=distance<=180_000):
                continue

            # Actor record is unique; use actor index rather than unstable name.
            key=(ai,oi)
            if key in seen:
                continue
            seen.add(key)
            counts[planet]+=1
            actors.append(GatewayActor(ai,oi,name,x,y,z,planet,distance))
        for p,m in PLANET_GATEWAY_MAX.items():counts[p]=min(max(counts[p],0),m)
        return GatewayPlanetProbeResult(counts,actors,oc,ac,None)
    except Exception as e:
        return GatewayPlanetProbeResult(counts,actors,oc,ac,f"{type(e).__name__}: {e}")
