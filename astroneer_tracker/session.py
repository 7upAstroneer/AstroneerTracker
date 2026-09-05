from __future__ import annotations

from dataclasses import dataclass, field
from time import time

from .saves import SaveInfo


@dataclass
class SaveChangeEvent:
    logical_name: str
    filename: str
    detected_at: float


@dataclass
class ActiveSessionState:
    active_save: SaveInfo | None = None
    last_changed_physical_save: SaveInfo | None = None
    last_change_detected_at: float | None = None
    previous_logical_save: str | None = None
    change_history: list[SaveChangeEvent] = field(default_factory=list)


class ActiveSaveDetector:
    """
    Detects active Astroneer save activity from file metadata changes.

    v0.3 adds reliable switching between logical saves during the same
    Astroneer process session.
    """

    def __init__(self) -> None:
        self._known: dict[str, tuple[float, int]] = {}
        self.state = ActiveSessionState()

    def prime(self, saves: list[SaveInfo]) -> None:
        self._known = {
            str(save.path): (save.modified_time, save.size_bytes)
            for save in saves
        }

    def reset_active_session(self) -> None:
        self.state.active_save = None
        self.state.last_changed_physical_save = None
        self.state.last_change_detected_at = None
        self.state.previous_logical_save = None

    def update(self, saves: list[SaveInfo]) -> SaveInfo | None:
        changed: list[SaveInfo] = []
        current_keys: set[str] = set()

        for save in saves:
            key = str(save.path)
            current_keys.add(key)

            old = self._known.get(key)
            now_meta = (save.modified_time, save.size_bytes)

            if old is None or old != now_meta:
                changed.append(save)

            self._known[key] = now_meta

        # Remove stale physical-file entries after rename/delete.
        for key in list(self._known):
            if key not in current_keys:
                del self._known[key]

        # If the currently active physical save was deleted, it must immediately
        # stop being considered active. Otherwise downstream timing code can
        # recreate a tracker record that was just retired as "(gone)".
        if (
            self.state.active_save is not None
            and str(self.state.active_save.path) not in current_keys
        ):
            self.state.previous_logical_save = self.state.active_save.display_name
            self.state.active_save = None
            self.state.last_changed_physical_save = None

        if not changed:
            return self.state.active_save

        # Prefer the changed file with the newest filesystem modified time.
        changed.sort(key=lambda item: item.modified_time, reverse=True)
        winner = changed[0]

        prior = self.state.active_save.display_name if self.state.active_save else None

        self.state.previous_logical_save = prior
        self.state.active_save = winner
        self.state.last_changed_physical_save = winner
        self.state.last_change_detected_at = time()
        self.state.change_history.append(
            SaveChangeEvent(
                logical_name=winner.display_name,
                filename=winner.filename,
                detected_at=self.state.last_change_detected_at,
            )
        )

        # Keep a small diagnostics history in memory.
        if len(self.state.change_history) > 25:
            self.state.change_history = self.state.change_history[-25:]

        return self.state.active_save
