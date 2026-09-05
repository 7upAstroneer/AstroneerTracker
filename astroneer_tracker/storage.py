from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class TrackerStorage:
    """
    Small JSON persistence layer for tracker-owned statistics.

    Never writes to Astroneer's save directory.
    """

    FORMAT_VERSION = 1

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self.empty_data()

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self.empty_data()

        if not isinstance(raw, dict):
            return self.empty_data()

        raw.setdefault("format_version", self.FORMAT_VERSION)
        raw.setdefault("saves", {})
        return raw

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(data, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temp.replace(self.path)

    @classmethod
    def empty_data(cls) -> dict[str, Any]:
        return {
            "format_version": cls.FORMAT_VERSION,
            "saves": {},
        }
