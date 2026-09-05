from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic


@dataclass
class TimingState:
    session_started_at: float | None = None
    active_segment_started_at: float | None = None
    active_logical_save: str | None = None
    accumulated_by_save: dict[str, float] = field(default_factory=dict)


class SessionTimer:
    def __init__(self, initial_totals: dict[str, float] | None = None) -> None:
        self.state = TimingState()
        if initial_totals:
            self.state.accumulated_by_save = {
                str(name): max(0.0, float(seconds))
                for name, seconds in initial_totals.items()
            }

    def identify_save(self, logical_name: str) -> bool:
        """
        Returns True if switching/starting a timing segment changed totals.
        """
        now = monotonic()

        if self.state.active_logical_save == logical_name:
            return False

        changed = self._commit_current(now)

        self.state.active_logical_save = logical_name
        self.state.active_segment_started_at = now

        if self.state.session_started_at is None:
            self.state.session_started_at = now

        self.state.accumulated_by_save.setdefault(logical_name, 0.0)
        return changed

    def game_exited(self) -> bool:
        now = monotonic()
        changed = self._commit_current(now)
        self.state.active_logical_save = None
        self.state.active_segment_started_at = None
        self.state.session_started_at = None
        return changed

    def checkpoint(self) -> bool:
        """
        Commit the current segment to accumulated totals and immediately start
        a new segment. Used before writing tracker-owned persistence data.
        """
        now = monotonic()
        changed = self._commit_current(now)

        if self.state.active_logical_save is not None:
            self.state.active_segment_started_at = now

        return changed

    def _commit_current(self, now: float) -> bool:
        name = self.state.active_logical_save
        started = self.state.active_segment_started_at

        if name is None or started is None:
            return False

        elapsed = max(0.0, now - started)
        if elapsed <= 0:
            return False

        self.state.accumulated_by_save[name] = (
            self.state.accumulated_by_save.get(name, 0.0) + elapsed
        )
        return True

    def elapsed_for(self, logical_name: str) -> float:
        total = self.state.accumulated_by_save.get(logical_name, 0.0)

        if (
            self.state.active_logical_save == logical_name
            and self.state.active_segment_started_at is not None
        ):
            total += max(0.0, monotonic() - self.state.active_segment_started_at)

        return total

    def current_segment_elapsed(self) -> float:
        if self.state.active_segment_started_at is None:
            return 0.0
        return max(0.0, monotonic() - self.state.active_segment_started_at)

    def totals_snapshot(self) -> dict[str, float]:
        return dict(self.state.accumulated_by_save)


def format_elapsed(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
