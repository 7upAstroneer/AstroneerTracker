from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class LiveTimingState:
    active_save: str | None = None
    pending: float = 0.0
    pending_location_time: float = 0.0
    session: float = 0.0
    was_running: bool = False


class PowerShellTimingModel:
    """
    Current Python four-timer model, instrumented for v0.43h.

    IMPORTANT:
    This diagnostic build does NOT intentionally change timing arithmetic.
    Every mutation is logged before and after so the current behavior can be
    compared with the intended PowerShell rules.
    """

    def __init__(
        self,
        data: dict[str, Any],
        trace_path: Path | None = None,
    ) -> None:
        self.data = data
        self.state = LiveTimingState()
        self.trace_path = trace_path
        self._trace_sequence = 0

        self._trace(
            "TIMING MODEL INITIALIZED",
            operation=(
                "Four live values start at zero. Persistent totals and "
                "location totals remain in tracker data."
            ),
        )

    @staticmethod
    def _fmt(seconds: float) -> str:
        total = max(0, int(float(seconds)))
        h, r = divmod(total, 3600)
        m, s = divmod(r, 60)
        return f"{h:02d}:{m:02d}:{s:02d} ({float(seconds):.3f}s)"

    def _save_entry(self, save_name: str) -> dict[str, Any]:
        saves = self.data.setdefault("saves", {})
        entry = saves.setdefault(save_name, {})
        entry.setdefault("total_seconds", 0.0)
        entry.setdefault("location_seconds", {})
        return entry

    def _snapshot(self, focus_save: str | None = None) -> dict[str, Any]:
        active = self.state.active_save
        focus = focus_save or active

        persistent = 0.0
        location_seconds: dict[str, float] = {}
        if focus:
            entry = self.data.get("saves", {}).get(focus, {})
            if isinstance(entry, dict):
                persistent = float(entry.get("total_seconds", 0.0))
                raw_locations = entry.get("location_seconds", {})
                if isinstance(raw_locations, dict):
                    location_seconds = {
                        str(k): float(v)
                        for k, v in raw_locations.items()
                    }

        return {
            "focus_save": focus,
            "active_save": active,
            "persistent_total": persistent,
            "session": float(self.state.session),
            "pending_startup": float(self.state.pending),
            "pending_location": float(self.state.pending_location_time),
            "locations": location_seconds,
        }

    def _snapshot_text(self, snap: dict[str, Any]) -> str:
        lines = [
            f"  Focus Save:             {snap['focus_save'] or '—'}",
            f"  Active Save:            {snap['active_save'] or '—'}",
            f"  Persistent Total:       {self._fmt(snap['persistent_total'])}",
            f"  Current Session:        {self._fmt(snap['session'])}",
            f"  Pending Startup:        {self._fmt(snap['pending_startup'])}",
            f"  Pending Location:       {self._fmt(snap['pending_location'])}",
        ]

        locations = snap["locations"]
        if locations:
            lines.append("  Persisted Location Times:")
            for name in sorted(locations):
                lines.append(
                    f"    {name:<24} {self._fmt(locations[name])}"
                )
        else:
            lines.append("  Persisted Location Times: (none)")

        return "\n".join(lines)

    def _trace(
        self,
        event: str,
        *,
        operation: str,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        details: list[str] | None = None,
    ) -> None:
        if self.trace_path is None:
            return

        self._trace_sequence += 1
        timestamp = datetime.now().astimezone().isoformat(timespec="milliseconds")

        lines = [
            "",
            "=" * 88,
            f"TRACE #{self._trace_sequence:05d}  {timestamp}",
            f"EVENT: {event}",
            "-" * 88,
            "OPERATION:",
            f"  {operation}",
        ]

        if details:
            lines.append("DETAILS:")
            for detail in details:
                lines.append(f"  {detail}")

        if before is not None:
            lines.extend([
                "BEFORE:",
                self._snapshot_text(before),
            ])

        if after is not None:
            lines.extend([
                "AFTER:",
                self._snapshot_text(after),
            ])

        lines.append("=" * 88)

        try:
            self.trace_path.parent.mkdir(parents=True, exist_ok=True)
            with self.trace_path.open("a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception:
            pass

    def trace_external(
        self,
        event: str,
        operation: str,
        *,
        focus_save: str | None = None,
        details: list[str] | None = None,
    ) -> None:
        snap = self._snapshot(focus_save)
        self._trace(
            event,
            operation=operation,
            before=snap,
            after=snap,
            details=details,
        )

    def game_started(self) -> None:
        before = self._snapshot()
        self.state.active_save = None
        self.state.pending = 0.0
        self.state.pending_location_time = 0.0
        self.state.session = 0.0
        self.state.was_running = True
        after = self._snapshot()

        self._trace(
            "GAME STARTED",
            operation=(
                "Reset live Active Save, Current Session, Pending Startup, "
                "and Pending Location to zero. Persistent save totals are not changed."
            ),
            before=before,
            after=after,
        )

    def game_stopped(self) -> None:
        before = self._snapshot()
        self.state.active_save = None
        self.state.pending = 0.0
        self.state.pending_location_time = 0.0
        self.state.session = 0.0
        self.state.was_running = False
        after = self._snapshot()

        self._trace(
            "GAME STOPPED",
            operation=(
                "Reset all live timers to zero. Persistent totals/location totals "
                "remain stored in tracker data."
            ),
            before=before,
            after=after,
        )

    def tick(self, running: bool, delta: float) -> None:
        delta = max(0.0, min(float(delta), 5.0))

        if not running:
            return

        focus = self.state.active_save
        before = self._snapshot(focus)

        if self.state.active_save:
            entry = self._save_entry(self.state.active_save)
            entry["total_seconds"] = (
                float(entry.get("total_seconds", 0.0)) + delta
            )
            self.state.session += delta
            self.state.pending_location_time += delta

            operation = (
                f"Active save known: add {delta:.3f}s to Persistent Total, "
                f"Current Session, and Pending Location. "
                f"Pending Startup is unchanged."
            )
        else:
            self.state.pending += delta
            operation = (
                f"No active save known: add {delta:.3f}s ONLY to Pending Startup. "
                f"Persistent Total, Session, and Pending Location are unchanged."
            )

        after = self._snapshot(focus)
        self._trace(
            "TICK",
            operation=operation,
            before=before,
            after=after,
            details=[f"running={running}", f"delta={delta:.3f}s"],
        )

    def on_save_identified(
        self,
        save_name: str,
        location: str | None,
        *,
        tracked_before_processing: bool | None = None,
    ) -> None:
        previous_save = self.state.active_save
        switching_saves = (
            previous_save is not None
            and previous_save != save_name
        )

        initial = self._snapshot(save_name)

        self._trace(
            "SAVE IDENTIFICATION BEGIN",
            operation=(
                "Begin current Python save-identification timing flow. "
                "No arithmetic has been applied by this event yet."
            ),
            before=initial,
            after=initial,
            details=[
                f"Identified Save={save_name}",
                f"Detected Location={location or '—'}",
                f"Previous Active Save={previous_save or '—'}",
                f"Switching Saves={switching_saves}",
                f"Tracker record existed before save processing="
                f"{tracked_before_processing}",
                "Startup rule active: NEW save first identification credits 0; "
                "EXISTING save credits max(0, Pending Startup - 30s).",
            ],
        )

        # SAVE SWITCH TRANSFER.
        transferred_interval = 0.0
        if switching_saves and self.state.pending_location_time > 0:
            before = self._snapshot(save_name)
            old_entry = self._save_entry(previous_save)
            new_entry = self._save_entry(save_name)

            transferred_interval = min(
                self.state.pending_location_time,
                float(old_entry.get("total_seconds", 0.0)),
            )

            old_before = float(old_entry.get("total_seconds", 0.0))
            new_before = float(new_entry.get("total_seconds", 0.0))

            old_entry["total_seconds"] = max(
                0.0,
                old_before - transferred_interval,
            )
            new_entry["total_seconds"] = (
                new_before + transferred_interval
            )

            after = self._snapshot(save_name)
            self._trace(
                "SAVE SWITCH — TRANSFER UNFLUSHED INTERVAL",
                operation=(
                    f"Move {transferred_interval:.3f}s of unflushed Pending Location "
                    f"backing from old save '{previous_save}' Persistent Total to "
                    f"new save '{save_name}' Persistent Total. Pending Location itself "
                    f"is NOT reset here."
                ),
                before=before,
                after=after,
                details=[
                    f"Old save persistent before={old_before:.3f}s",
                    f"Old save persistent after="
                    f"{float(old_entry.get('total_seconds', 0.0)):.3f}s",
                    f"New save persistent before={new_before:.3f}s",
                    f"New save persistent after="
                    f"{float(new_entry.get('total_seconds', 0.0)):.3f}s",
                ],
            )

        # ACTIVATE IDENTIFIED SAVE.
        if self.state.active_save != save_name:
            before = self._snapshot(save_name)
            self.state.active_save = save_name
            self.state.session = transferred_interval
            after = self._snapshot(save_name)

            self._trace(
                "ACTIVATE IDENTIFIED SAVE",
                operation=(
                    f"Set Active Save to '{save_name}'. Set Current Session to "
                    f"transferred interval ({transferred_interval:.3f}s)."
                ),
                before=before,
                after=after,
            )

        entry = self._save_entry(save_name)

        # STARTUP BUFFER FOLD — restored PowerShell-era rule.
        if self.state.pending > 0:
            before = self._snapshot(save_name)
            startup_before = float(self.state.pending)
            persistent_before = float(entry.get("total_seconds", 0.0))

            # A save that already had a tracker record before this save event is
            # an EXISTING save. Credit startup time minus 30 seconds to exclude
            # main-menu/loading overhead. A brand-new tracker save establishes
            # its first-save baseline and receives zero startup credit.
            is_existing_save = bool(tracked_before_processing)

            if is_existing_save:
                startup_credit = max(0.0, startup_before - 30.0)
                startup_discarded = startup_before - startup_credit
                rule_text = (
                    "EXISTING SAVE: credit max(0, Pending Startup - 30s)"
                )
            else:
                startup_credit = 0.0
                startup_discarded = startup_before
                rule_text = (
                    "NEW SAVE: first identification establishes baseline; "
                    "startup credit = 0"
                )

            if startup_credit > 0:
                entry["total_seconds"] = (
                    persistent_before + startup_credit
                )
                self.state.session += startup_credit
                self.state.pending_location_time += startup_credit

            # The entire startup buffer is consumed by this first identification.
            # Only startup_credit survives into tracked play time.
            self.state.pending = 0.0

            after = self._snapshot(save_name)
            self._trace(
                "APPLY PENDING STARTUP",
                operation=(
                    f"{rule_text}. Pending Startup was {startup_before:.3f}s; "
                    f"credited {startup_credit:.3f}s to Persistent Total + "
                    f"Current Session + Pending Location; discarded "
                    f"{startup_discarded:.3f}s; reset Pending Startup to 0."
                ),
                before=before,
                after=after,
                details=[
                    f"Tracker record existed before processing={tracked_before_processing}",
                    f"Persistent before={persistent_before:.3f}s",
                    f"Persistent after={float(entry.get('total_seconds', 0.0)):.3f}s",
                    f"Startup buffer={startup_before:.3f}s",
                    f"Startup credit={startup_credit:.3f}s",
                    f"Startup discarded={startup_discarded:.3f}s",
                ],
            )
        else:
            snap = self._snapshot(save_name)
            self._trace(
                "APPLY PENDING STARTUP — NOTHING TO APPLY",
                operation="Pending Startup is 0; no startup timing values changed.",
                before=snap,
                after=snap,
                details=[
                    f"Tracker record existed before processing={tracked_before_processing}",
                ],
            )

        # DESTINATION LOCATION FLUSH.
        if (
            self.state.pending_location_time > 0
            and location
            and location != "Unknown"
        ):
            before = self._snapshot(save_name)
            times = entry.setdefault("location_seconds", {})
            location_before = float(times.get(location, 0.0))
            amount = float(self.state.pending_location_time)

            times[location] = location_before + amount
            self.state.pending_location_time = 0.0

            after = self._snapshot(save_name)
            self._trace(
                "FLUSH PENDING LOCATION TO DESTINATION",
                operation=(
                    f"ADD {amount:.3f}s to EXISTING '{location}' location time "
                    f"({location_before:.3f}s + {amount:.3f}s = "
                    f"{float(times[location]):.3f}s), then reset Pending Location to 0."
                ),
                before=before,
                after=after,
                details=[
                    "This operation is additive. It should never replace or reduce "
                    "the previous persisted location total."
                ],
            )
        else:
            snap = self._snapshot(save_name)
            self._trace(
                "FLUSH PENDING LOCATION — NOT APPLIED",
                operation=(
                    "No location flush performed because Pending Location is 0 "
                    "or the detected location is missing/Unknown."
                ),
                before=snap,
                after=snap,
                details=[
                    f"Detected Location={location or '—'}",
                    f"Pending Location="
                    f"{self.state.pending_location_time:.3f}s",
                ],
            )

        final = self._snapshot(save_name)
        self._trace(
            "SAVE IDENTIFICATION COMPLETE",
            operation="End of current Python timing handling for this save event.",
            before=final,
            after=final,
        )

    def total_seconds(self, save_name: str) -> float:
        entry = self.data.get("saves", {}).get(save_name, {})
        if not isinstance(entry, dict):
            return 0.0
        return float(entry.get("total_seconds", 0.0))

    def location_seconds(self, save_name: str, location: str) -> float:
        entry = self.data.get("saves", {}).get(save_name, {})
        if not isinstance(entry, dict):
            return 0.0
        times = entry.get("location_seconds", {})
        if not isinstance(times, dict):
            return 0.0
        return float(times.get(location, 0.0))
