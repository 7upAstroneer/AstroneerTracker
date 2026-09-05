from __future__ import annotations
from typing import Any

class LocationStateTracker:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    def update_location(self, save_name: str, location: str) -> tuple[bool, int]:
        saves = self.data.setdefault("saves", {})
        entry = saves.setdefault(save_name, {})
        previous = entry.get("current_location")
        visits = entry.setdefault("visits", {})
        current_count = int(visits.get(location, 0))
        changed = previous != location

        if changed:
            current_count += 1
            visits[location] = current_count
            entry["current_location"] = location
        else:
            visits.setdefault(location, current_count)

        return changed, current_count

    def current_location(self, save_name: str) -> str | None:
        entry = self.data.get("saves", {}).get(save_name, {})
        return entry.get("current_location") if isinstance(entry, dict) else None

    def visits_for(self, save_name: str) -> dict[str, int]:
        entry = self.data.get("saves", {}).get(save_name, {})
        if not isinstance(entry, dict):
            return {}
        visits = entry.get("visits", {})
        if not isinstance(visits, dict):
            return {}
        return {str(k): int(v) for k, v in visits.items()}
