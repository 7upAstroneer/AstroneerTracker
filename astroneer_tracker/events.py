from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass
class SessionEventRecorder:
    data: dict[str, Any]
    current_session_id: str | None = None
    current_save: str | None = None

    def game_started(self) -> None:
        # We do not call a save "played" until it is actually identified.
        self.current_session_id = now_iso()
        self.current_save = None

    def save_identified(self, logical_name: str) -> bool:
        """
        Record a first-save identification or a switch to another save.
        Returns True if persistent data changed.
        """
        if self.current_session_id is None:
            self.game_started()

        if self.current_save == logical_name:
            return False

        sessions = self.data.setdefault("sessions", [])
        event_type = "save_identified" if self.current_save is None else "save_switched"

        sessions.append({
            "timestamp": now_iso(),
            "session_id": self.current_session_id,
            "event": event_type,
            "from_save": self.current_save,
            "to_save": logical_name,
        })

        self.current_save = logical_name
        self._trim(sessions)
        return True

    def game_exited(self) -> bool:
        if self.current_session_id is None:
            return False

        sessions = self.data.setdefault("sessions", [])
        sessions.append({
            "timestamp": now_iso(),
            "session_id": self.current_session_id,
            "event": "game_exited",
            "from_save": self.current_save,
            "to_save": None,
        })

        self.current_session_id = None
        self.current_save = None
        self._trim(sessions)
        return True

    @staticmethod
    def _trim(events: list[dict[str, Any]]) -> None:
        if len(events) > 200:
            del events[:-200]
