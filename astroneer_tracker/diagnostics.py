from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shutil

from .saves import SaveInfo


@dataclass
class DiagnosticCopy:
    source: Path
    destination: Path
    logical_name: str


class DiagnosticsArchive:
    def __init__(self, base_directory: Path, max_per_logical_save: int = 10) -> None:
        self.base_directory = base_directory
        self.max_per_logical_save = max_per_logical_save
        self._last_archived_meta: dict[str, tuple[float, int]] = {}
        self.last_error: str | None = None

    def archive_if_changed(self, save: SaveInfo) -> DiagnosticCopy | None:
        self.last_error = None

        key = str(save.path)
        meta = (save.modified_time, save.size_bytes)

        if self._last_archived_meta.get(key) == meta:
            return None

        if not save.path.exists():
            self.last_error = f"Source save no longer exists: {save.path}"
            return None

        safe_name = self._safe_name(save.display_name)
        target_dir = self.base_directory / "Diagnostics" / "Autosaves" / safe_name

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.last_error = f"Could not create diagnostics folder: {exc}"
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        destination = target_dir / f"{timestamp}_{save.path.name}"

        try:
            # copyfile avoids metadata-copy issues and is all we need for parsing.
            shutil.copyfile(save.path, destination)
        except OSError as exc:
            self.last_error = f"Copy failed: {exc}"
            return None

        self._last_archived_meta[key] = meta
        self._trim(target_dir)

        return DiagnosticCopy(
            source=save.path,
            destination=destination,
            logical_name=save.display_name,
        )

    def _trim(self, target_dir: Path) -> None:
        try:
            files = [p for p in target_dir.iterdir() if p.is_file()]
            files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            return

        for old in files[self.max_per_logical_save:]:
            try:
                old.unlink()
            except OSError:
                pass

    @staticmethod
    def _safe_name(name: str) -> str:
        invalid = '<>:"/\\\\|?*'
        cleaned = "".join("_" if c in invalid else c for c in name).strip()
        return cleaned or "UnknownSave"
