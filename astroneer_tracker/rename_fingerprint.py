from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import re
import zlib


# Stable-ish world identity tokens seen in Astroneer saves.
ENTITY_WORLD_RE = re.compile(rb"AstroEntityWorld_(\d+)")
GAMESTATE_RE = re.compile(rb"Astro_Gates_GameState_Instance_C_(\d+)")
CUSTOM_MANAGER_RE = re.compile(rb"__CustomGameManager")
MISSIONS_RE = re.compile(rb"__MissionsManagerSingleton")


@dataclass
class RenameFingerprint:
    signature: str | None
    entity_world: str | None = None
    gate_state: str | None = None
    size: int | None = None
    error: str | None = None


def _decompressed(path: Path) -> bytes:
    raw = path.read_bytes()
    if len(raw) < 24:
        raise ValueError("save too small")
    return zlib.decompress(raw[16:])


def get_rename_fingerprint(path: Path) -> RenameFingerprint:
    """
    Build a rename fingerprint from stable internal world identifiers rather
    than the entire file bytes. Astroneer can rewrite metadata during rename.
    """
    try:
        raw = _decompressed(path)

        entity = None
        gate = None

        m = ENTITY_WORLD_RE.search(raw)
        if m:
            entity = m.group(1).decode("ascii", errors="ignore")

        m = GAMESTATE_RE.search(raw)
        if m:
            gate = m.group(1).decode("ascii", errors="ignore")

        # Fallback structural digest from selected stable markers/counts.
        stable_parts = [
            entity or "",
            gate or "",
            str(raw.count(b"AstroEntityWorld_")),
            str(raw.count(b"Astro_Gates_GameState_Instance_C_")),
            str(raw.count(b"__CustomGameManager")),
            str(raw.count(b"__MissionsManagerSingleton")),
            str(raw.count(b"TeleporterControlPanel_C_")),
            str(raw.count(b"BackpackRail_C_")),
        ]

        sig = "|".join(stable_parts)
        digest = hashlib.sha256(sig.encode("utf-8")).hexdigest()

        return RenameFingerprint(
            signature=digest,
            entity_world=entity,
            gate_state=gate,
            size=len(raw),
            error=None,
        )
    except Exception as exc:
        return RenameFingerprint(None, error=f"{type(exc).__name__}: {exc}")
