from __future__ import annotations

from datetime import datetime
from typing import Any


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class SaveSummaryTracker:
    """
    Maintains lightweight persistent metadata for each logical save.
    This does not yet parse gameplay location/deaths/visits from save contents.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    def ensure_save(self, logical_name: str) -> dict[str, Any]:
        saves = self.data.setdefault("saves", {})
        entry = saves.setdefault(logical_name, {})
        entry.setdefault("total_play_seconds", 0.0)
        entry.setdefault("first_seen", now_iso())
        entry.setdefault("last_played", None)
        entry.setdefault("times_identified", 0)
        return entry

    def identified(self, logical_name: str) -> None:
        entry = self.ensure_save(logical_name)
        entry["last_played"] = now_iso()
        entry["times_identified"] = int(entry.get("times_identified", 0)) + 1

    def ordered_names(self) -> list[str]:
        saves = self.data.get("saves", {})

        def key(item: tuple[str, Any]):
            name, info = item
            if not isinstance(info, dict):
                return ("", name.lower())
            last = info.get("last_played") or ""
            return (last, name.lower())

        # Most recently played first; alphabetic naturally breaks ties.
        items = list(saves.items())
        items.sort(key=key, reverse=True)
        return [name for name, _ in items]
