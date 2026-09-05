from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from pathlib import Path
from datetime import datetime
import re
import struct
import time
import zlib


DESIGN_ASTRO_RE = re.compile(rb"DesignAstro_C_(\d+)")
BACKPACK_RAIL_RE = re.compile(rb"BackpackRail_C_(\d+)")
PRINTHEAD_BP_RE = re.compile(rb"Printhead_Backpack_C_(\d+)")
CATALOG_BP_RE = re.compile(rb"Catalog_GEN_VARIABLE_BackpackCatalog_C_CAT_(\d+)")
CATALOG_CREATIVE_BP_RE = re.compile(rb"CatalogCreative_GEN_VARIABLE_BackpackCatalog_Creative_C_CAT_(\d+)")
MISSIONLOG_BP_RE = re.compile(rb"MissionLog_GEN_VARIABLE_MissionsControlPanel_Backpack_C_CAT_(\d+)")
PLAYER_CORPSE_RE = re.compile(rb"AstroCorpse_C_(\d+)")
ASCII_TOKEN_RE = re.compile(rb"[ -~]{4,120}")
KEYWORDS = (
    "backpack",
    "death",
    "dead",
    "corpse",
    "respawn",
    "grave",
    "marker",
)


RESPAWN_FIELDS = (
    "AstroPlayerIdRespawnTokenCountPair",
    "AstroRespawnTokenSettings",
    "AstroRespawnTokenState",
    "InitialRespawnTokenCount",
    "RespawnTokenCount",
    "RespawnTokenCounts",
    "RespawnTokenSettings",
    "RespawnTokenState",
    "RespawnTokensActive",
    "RespawnTokensAreShared",
    "SecondsUntilRespawn",
)


@dataclass
class DeathProbeResult:
    death_detected: bool
    backpack_signature: str | None
    backpack_rail_ids: list[int]
    new_backpack_rail_ids: list[int]
    removed_backpack_rail_ids: list[int]
    evidence_tokens: list[str]
    new_evidence_tokens: list[str]
    removed_evidence_tokens: list[str]
    corpse_discovery_count: int
    respawn_snapshots: dict[str, list[str]]
    changed_respawn_fields: list[str]
    player_instance_signature: str | None
    player_instance_components: dict[str, int | None]
    player_instance_changed: bool
    respawn_state_values: dict[str, str]
    changed_respawn_state_values: list[str]
    respawn_snapshot_change_count: int
    respawn_snapshot_all_changed: bool
    respawn_snapshot_changed_fields: list[str]
    probe_status: str


def _decompressed(save_copy: Path) -> bytes:
    raw_file = save_copy.read_bytes()
    if len(raw_file) < 24:
        raise ValueError("save too small")
    return zlib.decompress(raw_file[16:])


def _ascii_evidence_tokens(raw: bytes) -> list[str]:
    found: set[str] = set()
    for m in ASCII_TOKEN_RE.findall(raw):
        try:
            text = m.decode("ascii", errors="ignore").strip()
        except Exception:
            continue
        lower = text.lower()
        if any(k in lower for k in KEYWORDS):
            # Keep concise object/class-like strings and avoid huge prose blobs.
            if len(text) <= 120:
                found.add(text)
    return sorted(found)


def _corpse_discovery_count(raw: bytes) -> int:
    return len(set(re.findall(rb"AstroCorpse_Discovery_C_(\d+)", raw)))

def _hex_ascii_window(raw: bytes, start: int, end: int) -> str:
    chunk = raw[max(0, start):min(len(raw), end)]
    hex_part = " ".join(f"{b:02x}" for b in chunk[:96])
    ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk[:96])
    return f"HEX[{hex_part}] ASCII[{ascii_part}]"


def _respawn_snapshots(raw: bytes) -> dict[str, list[str]]:
    """
    Capture compact raw neighborhoods around each respawn-related token.

    This deliberately does not assume Unreal property type/size yet. It gives
    us stable before/after evidence for counters, booleans, arrays, or structs.
    """
    result: dict[str, list[str]] = {}

    for field in RESPAWN_FIELDS:
        needle = field.encode("ascii")
        matches: list[str] = []
        offset = 0

        while True:
            idx = raw.find(needle, offset)
            if idx < 0:
                break

            # Include bytes before and after the token so we can see serialized
            # type/value changes adjacent to the property name.
            start = max(0, idx - 48)
            end = min(len(raw), idx + len(needle) + 96)
            matches.append(
                f"offset={idx} " + _hex_ascii_window(raw, start, end)
            )

            offset = idx + len(needle)

            if len(matches) >= 12:
                break

        result[field] = matches

    return result


def _changed_respawn_fields(
    previous: dict[str, list[str]] | None,
    current: dict[str, list[str]],
) -> list[str]:
    if previous is None:
        return []
    changed = []
    for field in RESPAWN_FIELDS:
        if previous.get(field, []) != current.get(field, []):
            changed.append(field)
    return changed




def _max_id(pattern: re.Pattern[bytes], raw: bytes) -> int | None:
    matches = pattern.findall(raw)
    if not matches:
        return None
    try:
        return max(int(x) for x in matches)
    except Exception:
        return None


def _player_instance_components(raw: bytes) -> dict[str, int | None]:
    return {
        "DesignAstro": _max_id(DESIGN_ASTRO_RE, raw),
        "BackpackRail": _max_id(BACKPACK_RAIL_RE, raw),
        "Printhead_Backpack": _max_id(PRINTHEAD_BP_RE, raw),
        "BackpackCatalog": _max_id(CATALOG_BP_RE, raw),
        "BackpackCatalogCreative": _max_id(CATALOG_CREATIVE_BP_RE, raw),
        "MissionLog_Backpack": _max_id(MISSIONLOG_BP_RE, raw),
    }


def _player_instance_signature(components: dict[str, int | None]) -> str | None:
    vals = [components[k] for k in (
        "DesignAstro",
        "BackpackRail",
        "Printhead_Backpack",
        "BackpackCatalog",
        "BackpackCatalogCreative",
        "MissionLog_Backpack",
    )]
    if not any(v is not None for v in vals):
        return None
    return "|".join(str(v) if v is not None else "-" for v in vals)


def _read_fstring_at(raw: bytes, offset: int) -> tuple[str | None, int]:
    """
    Best-effort UE4 FString parser at offset:
      int32 length, then ANSI/UTF-16 payload.
    Returns (text, next_offset).
    """
    if offset + 4 > len(raw):
        return None, offset
    n = struct.unpack_from("<i", raw, offset)[0]
    offset += 4
    if n == 0:
        return "", offset
    if n > 0:
        end = offset + n
        if end > len(raw):
            return None, offset
        data = raw[offset:end]
        if data.endswith(b"\x00"):
            data = data[:-1]
        return data.decode("utf-8", errors="ignore"), end
    # negative length means UTF-16 count
    count = -n
    end = offset + count * 2
    if end > len(raw):
        return None, offset
    data = raw[offset:end]
    if data.endswith(b"\x00\x00"):
        data = data[:-2]
    return data.decode("utf-16-le", errors="ignore"), end


def _parse_respawn_state_values(raw: bytes) -> dict[str, str]:
    """
    Best-effort structural parser around RespawnTokenState-related serialized
    properties. We are looking for explicit property-name/type/value triples,
    not raw byte-window shifts.

    This intentionally returns strings for safety until the exact UE property
    layout is proven.
    """
    values: dict[str, str] = {}

    # Search exact property-name strings and inspect forward for common Unreal
    # property type names plus compact numeric/boolean payloads.
    targets = (
        "RespawnTokenCount",
        "InitialRespawnTokenCount",
        "RespawnTokensActive",
        "RespawnTokensAreShared",
        "SecondsUntilRespawn",
    )

    for field in targets:
        needle = field.encode("ascii") + b"\x00"
        pos = 0
        captures = []

        while True:
            idx = raw.find(needle, pos)
            if idx < 0:
                break

            # Examine a limited region following the property name.
            region = raw[idx + len(needle): idx + len(needle) + 96]

            # Try to find Unreal property type markers.
            type_name = None
            for t in (
                b"IntProperty\x00",
                b"Int64Property\x00",
                b"UInt32Property\x00",
                b"UInt64Property\x00",
                b"BoolProperty\x00",
                b"FloatProperty\x00",
                b"DoubleProperty\x00",
                b"StrProperty\x00",
                b"StructProperty\x00",
                b"ArrayProperty\x00",
                b"MapProperty\x00",
            ):
                ti = region.find(t)
                if ti >= 0:
                    type_name = t[:-1].decode("ascii")
                    break

            # Add a compact normalized hex tail independent of absolute offset.
            # This is much less noisy than including the address itself.
            tail = region[:48]
            captures.append(
                f"type={type_name or '?'} tail=" +
                " ".join(f"{b:02x}" for b in tail)
            )

            pos = idx + len(needle)
            if len(captures) >= 8:
                break

        if captures:
            values[field] = " || ".join(captures)
        else:
            values[field] = "not found"

    # Also record whether the struct/type tokens are present.
    for field in (
        "AstroPlayerIdRespawnTokenCountPair",
        "AstroRespawnTokenSettings",
        "AstroRespawnTokenState",
        "RespawnTokenCounts",
        "RespawnTokenSettings",
        "RespawnTokenState",
    ):
        values[field] = "present" if field.encode("ascii") in raw else "not found"

    return values


def _changed_value_keys(
    previous: dict[str, str] | None,
    current: dict[str, str],
) -> list[str]:
    if previous is None:
        return []
    return sorted(
        key for key in current
        if previous.get(key) != current.get(key)
    )


class DeathTracker:
    """
    Hybrid death tracker.

    Deaths can be recorded from high-confidence live log events and from
    new AstroCorpse_C_<ID> save evidence as a fallback.

    Backpack/player-instance signature changes are diagnostic only.

    It compares:
    - every BackpackRail_C_<ID> across saves
    - all ASCII save tokens containing backpack/death/dead/corpse/
      respawn/grave/marker
    - added/removed evidence after each save
    """

    def __init__(
        self,
        data: dict[str, Any],
        trace_path: Path | None = None,
    ) -> None:
        self.data = data
        self.trace_path = trace_path
        self.active_save: str | None = None
        self.last_backpack_ids: set[int] | None = None
        self.last_evidence_tokens: set[str] | None = None
        self.last_player_corpse_ids: set[int] | None = None
        self.last_respawn_snapshots: dict[str, list[str]] | None = None
        self.last_player_instance_signature: str | None = None
        self.last_player_instance_components: dict[str, int | None] | None = None
        self.last_respawn_state_values: dict[str, str] | None = None
        self.last_save_observed_at: float | None = None
        self.live_death_times: list[float] = []
        self._trace_sequence = 0

    def _save_entry(self, save_name: str) -> dict[str, Any]:
        return self.data.setdefault("saves", {}).setdefault(save_name, {})

    def _restore_persisted_baseline(self, save_name: str) -> bool:
        """
        Restore the last save-based death comparison state for this logical save.

        This is deliberately per-save so:
        - tracker/game restarts do not throw away the previous death baseline;
        - switching from Save A to Save B and back does not force a new baseline.
        """
        entry = self._save_entry(save_name)
        state = entry.get("_death_baseline")
        if not isinstance(state, dict):
            return False

        try:
            self.last_player_instance_signature = (
                str(state["player_instance_signature"])
                if state.get("player_instance_signature") is not None
                else None
            )

            raw_components = state.get("player_instance_components", {})
            if isinstance(raw_components, dict):
                self.last_player_instance_components = {
                    str(k): (int(v) if v is not None else None)
                    for k, v in raw_components.items()
                }
            else:
                self.last_player_instance_components = None

            raw_corpses = state.get("player_corpse_ids", [])
            self.last_player_corpse_ids = {
                int(x) for x in raw_corpses
            } if isinstance(raw_corpses, list) else set()

            raw_backpacks = state.get("backpack_ids", [])
            self.last_backpack_ids = {
                int(x) for x in raw_backpacks
            } if isinstance(raw_backpacks, list) else set()

            raw_tokens = state.get("evidence_tokens", [])
            self.last_evidence_tokens = {
                str(x) for x in raw_tokens
            } if isinstance(raw_tokens, list) else set()

            raw_snapshots = state.get("respawn_snapshots")
            self.last_respawn_snapshots = (
                {
                    str(k): [str(x) for x in v]
                    for k, v in raw_snapshots.items()
                    if isinstance(v, list)
                }
                if isinstance(raw_snapshots, dict)
                else None
            )

            raw_state_values = state.get("respawn_state_values")
            self.last_respawn_state_values = (
                {str(k): str(v) for k, v in raw_state_values.items()}
                if isinstance(raw_state_values, dict)
                else None
            )

            observed_at = state.get("observed_at")
            self.last_save_observed_at = (
                float(observed_at) if observed_at is not None else None
            )
        except Exception:
            return False

        return bool(
            self.last_player_instance_components
            or self.last_player_corpse_ids is not None
        )

    def _persist_baseline(
        self,
        save_name: str,
        *,
        backpack_ids: set[int],
        evidence_tokens: set[str],
        player_corpse_ids: set[int],
        respawn_snapshots: dict[str, list[str]],
        player_instance_signature: str | None,
        player_instance_components: dict[str, int | None],
        respawn_state_values: dict[str, str],
        observed_at: float,
    ) -> None:
        entry = self._save_entry(save_name)
        entry["_death_baseline"] = {
            "backpack_ids": sorted(backpack_ids),
            "evidence_tokens": sorted(evidence_tokens),
            "player_corpse_ids": sorted(player_corpse_ids),
            "respawn_snapshots": respawn_snapshots,
            "player_instance_signature": player_instance_signature,
            "player_instance_components": dict(player_instance_components),
            "respawn_state_values": dict(respawn_state_values),
            "observed_at": float(observed_at),
        }

    def reset_session(self) -> None:
        self.active_save = None
        self.last_backpack_ids = None
        self.last_evidence_tokens = None
        self.last_player_corpse_ids = None
        self.last_respawn_snapshots = None
        self.last_player_instance_signature = None
        self.last_player_instance_components = None
        self.last_respawn_state_values = None
        self.last_save_observed_at = None
        self.live_death_times = []

    @staticmethod
    def _fmt_ids(values: list[int] | set[int]) -> str:
        vals = sorted(values)
        return ", ".join(str(v) for v in vals) if vals else "none"

    @staticmethod
    def _classify_event(
        new_corpses: list[int],
        removed_corpses: list[int],
        new_bp: list[int],
        removed_bp: list[int],
        new_tokens: list[str],
        removed_tokens: list[str],
        baseline: bool,
    ) -> str:
        if baseline:
            return "BASELINE"
        if new_corpses:
            return "CORPSE CREATED"
        if removed_corpses:
            return "CORPSE REMOVED"
        if new_bp or removed_bp or new_tokens or removed_tokens:
            return "STRUCTURE CHANGED"
        return "NO RELEVANT CHANGE"

    def _append_trace(
        self,
        *,
        save_name: str,
        location: str | None,
        event: str,
        backpack_ids: list[int],
        new_bp: list[int],
        removed_bp: list[int],
        player_corpse_ids: list[int],
        new_corpses: list[int],
        removed_corpses: list[int],
        evidence_tokens: list[str],
        new_tokens: list[str],
        removed_tokens: list[str],
        corpse_discovery_count: int,
        respawn_snapshots: dict[str, list[str]],
        changed_respawn_fields: list[str],
        player_instance_signature: str | None,
        player_instance_components: dict[str, int | None],
        player_instance_changed: bool,
        respawn_state_values: dict[str, str],
        changed_respawn_state_values: list[str],
        respawn_snapshot_change_count: int,
        respawn_snapshot_all_changed: bool,
        respawn_snapshot_changed_fields: list[str],
    ) -> None:
        if self.trace_path is None:
            return

        self._trace_sequence += 1
        timestamp = datetime.now().astimezone().isoformat(timespec="milliseconds")

        lines = [
            "",
            "=" * 96,
            f"DEATH TRACE #{self._trace_sequence:04d}  {timestamp}",
            f"EVENT: {event}",
            f"Save: {save_name}",
            f"Location: {location or '—'}",
            "-" * 96,
            f"Player Corpse IDs:        {self._fmt_ids(player_corpse_ids)}",
            f"New Player Corpse IDs:    {self._fmt_ids(new_corpses)}",
            f"Removed Player Corpse IDs:{' ' if removed_corpses else ' '}{self._fmt_ids(removed_corpses)}",
            "",
            f"BackpackRail IDs:         {self._fmt_ids(backpack_ids)}",
            f"New BackpackRail IDs:     {self._fmt_ids(new_bp)}",
            f"Removed BackpackRail IDs: {self._fmt_ids(removed_bp)}",
            "",
            f"Corpse Discovery Count:   {corpse_discovery_count}",
            "",
            "New Death-Evidence Tokens:",
        ]

        if new_tokens:
            lines.extend([f"  + {x}" for x in new_tokens[:40]])
        else:
            lines.append("  none")

        lines.append("Removed Death-Evidence Tokens:")
        if removed_tokens:
            lines.extend([f"  - {x}" for x in removed_tokens[:40]])
        else:
            lines.append("  none")

        lines.append("Current Relevant Tokens:")
        if evidence_tokens:
            lines.extend([f"  {x}" for x in evidence_tokens[:80]])
        else:
            lines.append("  none")

        lines.append("")
        lines.append("Live Player Instance Signature:")
        lines.append(f"  Signature: {player_instance_signature or 'none'}")
        lines.append(f"  Changed Since Previous Save: {'YES' if player_instance_changed else 'No'}")
        for key, value in player_instance_components.items():
            lines.append(f"  {key}: {value if value is not None else 'none'}")

        lines.append("")
        lines.append("Death OR Rule:")
        lines.append(
            "  Six-ID Signal: all of DesignAstro, BackpackRail, "
            "Printhead_Backpack, BackpackCatalog, BackpackCatalogCreative, "
            "MissionLog_Backpack change together"
        )
        lines.append(
            f"  Six-ID Signal Present: "
            f"{'YES' if player_instance_changed and all(v is not None for v in player_instance_components.values()) else 'No'}"
        )
        lines.append(
            f"  New Player Corpse Signal Present: "
            f"{'YES' if new_corpses else 'No'}"
        )
        lines.append(
            f"  Save Death OR Result: "
            f"{'YES' if ((player_instance_changed and all(v is not None for v in player_instance_components.values())) or bool(new_corpses)) else 'No'}"
        )
        lines.append(
            "  Counting Rule: six-ID OR corpse = +1; both together still = +1"
        )

        lines.append("")
        lines.append("Parsed Respawn State Value Changes:")
        if changed_respawn_state_values:
            for field in changed_respawn_state_values:
                lines.append(f"  CHANGED: {field}")
        else:
            lines.append("  none")

        lines.append("Parsed Respawn State Values:")
        for field in sorted(respawn_state_values):
            lines.append(f"  {field}: {respawn_state_values[field]}")

        lines.append("")
        lines.append("Coordinated Respawn Snapshot Signal:")
        lines.append(
            f"  Changed Fields: {respawn_snapshot_change_count}/{len(RESPAWN_FIELDS)}"
        )
        lines.append(
            f"  All {len(RESPAWN_FIELDS)} Changed Together: "
            f"{'YES' if respawn_snapshot_all_changed else 'No'}"
        )
        lines.append(
            "  Candidate Death Signal: "
            + ("YES (diagnostic only)" if respawn_snapshot_all_changed else "No")
        )
        if respawn_snapshot_changed_fields:
            for field in respawn_snapshot_changed_fields:
                lines.append(f"  * {field}")
        else:
            lines.append("  * none")

        lines.append("")
        lines.append("Respawn Field Changes:")
        if changed_respawn_fields:
            for field in changed_respawn_fields:
                lines.append(f"  CHANGED: {field}")
        else:
            lines.append("  none")

        lines.append("Respawn Field Snapshots:")
        for field in RESPAWN_FIELDS:
            snapshots = respawn_snapshots.get(field, [])
            lines.append(f"  {field}:")
            if not snapshots:
                lines.append("    not found")
            else:
                for snap in snapshots[:6]:
                    lines.append(f"    {snap}")

        lines.append("=" * 96)

        try:
            self.trace_path.parent.mkdir(parents=True, exist_ok=True)
            with self.trace_path.open("a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception:
            pass

    def _increment_deaths(self, save_name: str, location: str | None, amount: int, source: str) -> None:
        if amount <= 0:
            return
        entry = self.data.setdefault("saves", {}).setdefault(save_name, {})
        entry["deaths"] = int(entry.get("deaths", 0)) + int(amount)
        if location and location != "Unknown":
            by_location = entry.setdefault("deaths_by_location", {})
            by_location[location] = int(by_location.get(location, 0)) + int(amount)
        if self.trace_path is not None:
            try:
                self.trace_path.parent.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now().astimezone().isoformat(timespec="milliseconds")
                with self.trace_path.open("a", encoding="utf-8") as f:
                    f.write("\n" + "=" * 96 + "\n")
                    f.write(f"DEATH COUNT MUTATION  {stamp}\n")
                    f.write(f"Save: {save_name}\nLocation: {location or '—'}\n")
                    f.write(f"Amount: +{amount}\nSource: {source}\n")
                    f.write(f"New Total: {entry['deaths']}\n")
                    f.write("=" * 96 + "\n")
            except Exception:
                pass

    def record_live_death(self, save_name: str, location: str | None, source_line: str, event_time: float | None = None) -> None:
        when = float(event_time if event_time is not None else time.time())
        self._increment_deaths(save_name, location, 1, f"LIVE LOG: {source_line[:500]}")
        entry = self._save_entry(save_name)
        entry["_death_pending_live_count"] = (
            int(entry.get("_death_pending_live_count", 0)) + 1
        )
        self.live_death_times.append(when)
        cutoff = when - 3600.0
        self.live_death_times = [t for t in self.live_death_times if t >= cutoff]

    def observe_save(
        self,
        save_name: str,
        save_copy: Path,
        location: str | None,
    ) -> DeathProbeResult:
        try:
            raw = _decompressed(save_copy)
        except Exception as exc:
            return DeathProbeResult(
                death_detected=False,
                backpack_signature=None,
                backpack_rail_ids=[],
                new_backpack_rail_ids=[],
                removed_backpack_rail_ids=[],
                evidence_tokens=[],
                new_evidence_tokens=[],
                removed_evidence_tokens=[],
                corpse_discovery_count=0,
                respawn_snapshots={},
                changed_respawn_fields=[],
                player_instance_signature=None,
                player_instance_components={},
                player_instance_changed=False,
                respawn_state_values={},
                changed_respawn_state_values=[],
                respawn_snapshot_change_count=0,
                respawn_snapshot_all_changed=False,
                respawn_snapshot_changed_fields=[],
                probe_status=f"probe error: {type(exc).__name__}",
            )

        backpack_ids = sorted({int(x) for x in BACKPACK_RAIL_RE.findall(raw)})
        backpack_set = set(backpack_ids)
        signature = str(max(backpack_ids)) if backpack_ids else None

        player_corpse_ids = sorted({int(x) for x in PLAYER_CORPSE_RE.findall(raw)})
        player_corpse_set = set(player_corpse_ids)

        evidence_tokens = _ascii_evidence_tokens(raw)
        evidence_set = set(evidence_tokens)
        corpse_count = _corpse_discovery_count(raw)

        switching_save = self.active_save != save_name
        restored_persisted_baseline = False
        if switching_save:
            restored_persisted_baseline = self._restore_persisted_baseline(
                save_name
            )
            self.active_save = save_name

        respawn_snapshots = _respawn_snapshots(raw)
        changed_respawn_fields = _changed_respawn_fields(
            self.last_respawn_snapshots,
            respawn_snapshots,
        )
        respawn_snapshot_change_count = len(changed_respawn_fields)
        respawn_snapshot_all_changed = (
            self.last_respawn_snapshots is not None
            and respawn_snapshot_change_count == len(RESPAWN_FIELDS)
        )

        player_instance_components = _player_instance_components(raw)
        player_instance_signature = _player_instance_signature(
            player_instance_components
        )
        player_instance_changed = bool(
            self.last_player_instance_signature is not None
            and player_instance_signature is not None
            and self.last_player_instance_signature != player_instance_signature
        )

        required_player_keys = (
            "DesignAstro",
            "BackpackRail",
            "Printhead_Backpack",
            "BackpackCatalog",
            "BackpackCatalogCreative",
            "MissionLog_Backpack",
        )

        all_six_present = all(
            player_instance_components.get(k) is not None
            for k in required_player_keys
        )
        previous_all_six_present = bool(
            self.last_player_instance_components
            and all(
                self.last_player_instance_components.get(k) is not None
                for k in required_player_keys
            )
        )
        changed_player_component_keys = []
        if self.last_player_instance_components is not None:
            changed_player_component_keys = [
                k for k in required_player_keys
                if self.last_player_instance_components.get(k)
                != player_instance_components.get(k)
            ]

        all_six_changed_together = bool(
            previous_all_six_present
            and all_six_present
            and len(changed_player_component_keys) == len(required_player_keys)
        )

        respawn_state_values = _parse_respawn_state_values(raw)
        changed_respawn_state_values = _changed_value_keys(
            self.last_respawn_state_values,
            respawn_state_values,
        )

        baseline = bool(
            switching_save and not restored_persisted_baseline
        )
        now_epoch = time.time()
        fallback_amount = 0

        entry = self._save_entry(save_name)
        persisted_live_pending = int(
            entry.get("_death_pending_live_count", 0)
        )

        if baseline:
            new_bp = []
            removed_bp = []
            new_ev = []
            removed_ev = []
            new_corpses = []
            removed_corpses = []
            status = "baseline established; existing corpse state not counted"
        else:
            prev_bp = self.last_backpack_ids or set()
            prev_ev = self.last_evidence_tokens or set()
            prev_corpses = self.last_player_corpse_ids or set()

            new_bp = sorted(backpack_set - prev_bp)
            removed_bp = sorted(prev_bp - backpack_set)
            new_ev = sorted(evidence_set - prev_ev)
            removed_ev = sorted(prev_ev - evidence_set)
            new_corpses = sorted(player_corpse_set - prev_corpses)
            removed_corpses = sorted(prev_corpses - player_corpse_set)

            live_since_last_save = persisted_live_pending
            if self.last_save_observed_at is not None:
                live_since_last_save += sum(
                    1 for t in self.live_death_times
                    if self.last_save_observed_at < t <= now_epoch
                )

            six_signal = bool(all_six_changed_together)
            corpse_signal = bool(new_corpses)

            # Explicit save-based OR rule:
            #   six-ID bundle changed OR new player corpse exists => one death.
            #
            # If both are true on the same save transition, count only one.
            # If a live-log death already counted since the previous save,
            # the save evidence only corroborates it.
            save_death_signal = six_signal or corpse_signal

            if save_death_signal and live_since_last_save == 0:
                if six_signal and corpse_signal:
                    source_label = "SIX-ID OR CORPSE: BOTH signals"
                    status = (
                        "DEATH COUNTED: six-ID bundle AND new player corpse "
                        "both detected; +1 total"
                    )
                elif six_signal:
                    source_label = "SIX-ID OR CORPSE: six-ID bundle only"
                    status = (
                        "DEATH COUNTED: all six player IDs changed together; "
                        "+1 total"
                    )
                else:
                    source_label = "SIX-ID OR CORPSE: new player corpse only"
                    status = (
                        "DEATH COUNTED: new AstroCorpse_C_<ID> detected; "
                        "+1 total"
                    )

                detail_parts = []
                if six_signal:
                    detail_parts.append(
                        "six="
                        + ", ".join(
                            f"{k} "
                            f"{self.last_player_instance_components.get(k)}"
                            f"->{player_instance_components.get(k)}"
                            for k in required_player_keys
                        )
                    )
                if corpse_signal:
                    detail_parts.append(
                        "corpse_ids=" + ",".join(str(x) for x in new_corpses)
                    )

                self._increment_deaths(
                    save_name,
                    location,
                    1,
                    source=source_label + ("; " + "; ".join(detail_parts) if detail_parts else ""),
                )

            elif save_death_signal and live_since_last_save > 0:
                if six_signal and corpse_signal:
                    status = (
                        "six-ID bundle + corpse corroborate live death; "
                        "no duplicate death added"
                    )
                elif six_signal:
                    status = (
                        "six-ID bundle corroborates live death; "
                        "no duplicate death added"
                    )
                else:
                    status = (
                        "new player corpse corroborates live death; "
                        "no duplicate death added"
                    )

            elif removed_corpses:
                status = "player corpse removed; no death counted"
            elif respawn_snapshot_all_changed:
                status = (
                    "RESPAWN SNAPSHOT CANDIDATE: all "
                    f"{len(RESPAWN_FIELDS)} respawn-field snapshots changed together; "
                    "diagnostic only"
                )
            elif player_instance_changed:
                status = "partial player-instance change; no death counted"
            elif changed_respawn_fields:
                status = (
                    f"partial respawn snapshot change: "
                    f"{respawn_snapshot_change_count}/{len(RESPAWN_FIELDS)} fields; "
                    "no death counted"
                )
            elif new_bp or removed_bp or new_ev or removed_ev:
                status = "death-evidence structure changed; no death counted"
            else:
                status = "no relevant structural change"

        event = self._classify_event(
            new_corpses,
            removed_corpses,
            new_bp,
            removed_bp,
            new_ev,
            removed_ev,
            baseline,
        )

        self._append_trace(
            save_name=save_name,
            location=location,
            event=event,
            backpack_ids=backpack_ids,
            new_bp=new_bp,
            removed_bp=removed_bp,
            player_corpse_ids=player_corpse_ids,
            new_corpses=new_corpses,
            removed_corpses=removed_corpses,
            evidence_tokens=evidence_tokens,
            new_tokens=new_ev,
            removed_tokens=removed_ev,
            corpse_discovery_count=corpse_count,
            respawn_snapshots=respawn_snapshots,
            changed_respawn_fields=changed_respawn_fields,
            player_instance_signature=player_instance_signature,
            player_instance_components=player_instance_components,
            player_instance_changed=player_instance_changed,
            respawn_state_values=respawn_state_values,
            changed_respawn_state_values=changed_respawn_state_values,
            respawn_snapshot_change_count=respawn_snapshot_change_count,
            respawn_snapshot_all_changed=respawn_snapshot_all_changed,
            respawn_snapshot_changed_fields=changed_respawn_fields,
        )

        self.last_backpack_ids = backpack_set
        self.last_evidence_tokens = evidence_set
        self.last_player_corpse_ids = player_corpse_set
        self.last_respawn_snapshots = respawn_snapshots
        self.last_player_instance_signature = player_instance_signature
        self.last_player_instance_components = dict(player_instance_components)
        self.last_respawn_state_values = respawn_state_values
        self.last_save_observed_at = now_epoch

        self._persist_baseline(
            save_name,
            backpack_ids=backpack_set,
            evidence_tokens=evidence_set,
            player_corpse_ids=player_corpse_set,
            respawn_snapshots=respawn_snapshots,
            player_instance_signature=player_instance_signature,
            player_instance_components=player_instance_components,
            respawn_state_values=respawn_state_values,
            observed_at=now_epoch,
        )
        entry["_death_pending_live_count"] = 0

        return DeathProbeResult(
            death_detected=bool((not baseline) and new_corpses),
            backpack_signature=signature,
            backpack_rail_ids=backpack_ids,
            new_backpack_rail_ids=new_bp,
            removed_backpack_rail_ids=removed_bp,
            evidence_tokens=evidence_tokens,
            new_evidence_tokens=new_ev,
            removed_evidence_tokens=removed_ev,
            corpse_discovery_count=corpse_count,
            respawn_snapshots=respawn_snapshots,
            changed_respawn_fields=changed_respawn_fields,
            player_instance_signature=player_instance_signature,
            player_instance_components=player_instance_components,
            player_instance_changed=player_instance_changed,
            respawn_state_values=respawn_state_values,
            changed_respawn_state_values=changed_respawn_state_values,
            respawn_snapshot_change_count=respawn_snapshot_change_count,
            respawn_snapshot_all_changed=respawn_snapshot_all_changed,
            respawn_snapshot_changed_fields=changed_respawn_fields,
            probe_status=status,
        )

    def deaths_for(self, save_name: str) -> int:
        entry = self.data.get("saves", {}).get(save_name, {})
        if not isinstance(entry, dict):
            return 0
        return int(entry.get("deaths", 0))

    def deaths_at(self, save_name: str, location: str) -> int:
        entry = self.data.get("saves", {}).get(save_name, {})
        if not isinstance(entry, dict):
            return 0
        by_location = entry.get("deaths_by_location", {})
        if not isinstance(by_location, dict):
            return 0
        return int(by_location.get(location, 0))
