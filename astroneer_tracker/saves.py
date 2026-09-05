from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class SaveInfo:
    path: Path
    filename: str
    display_name: str
    modified_time: float
    size_bytes: int


def display_name_from_filename(filename: str) -> str:
    """
    Convert an Astroneer physical save filename into the logical save name.

    Examples:
        SAVE_1$2026.04.17-09.savegame -> SAVE_1
        CUSTOM GAME.savegame          -> CUSTOM GAME

    Astroneer can append a '$...' timestamp/version suffix. The tracker groups
    those files under the portion before the first '$'.
    """
    name = filename

    if name.lower().endswith(".savegame"):
        name = name[:-9]

    if "$" in name:
        name = name.split("$", 1)[0]

    return name.strip()


def find_savegames(save_directory: Path) -> list[SaveInfo]:
    if not save_directory.exists() or not save_directory.is_dir():
        return []

    saves: list[SaveInfo] = []

    for path in save_directory.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() != ".savegame":
            continue

        try:
            stat = path.stat()
        except OSError:
            continue

        saves.append(
            SaveInfo(
                path=path,
                filename=path.name,
                display_name=display_name_from_filename(path.name),
                modified_time=stat.st_mtime,
                size_bytes=stat.st_size,
            )
        )

    saves.sort(key=lambda item: item.modified_time, reverse=True)
    return saves


def newest_save(save_directory: Path) -> SaveInfo | None:
    saves = find_savegames(save_directory)
    return saves[0] if saves else None


def grouped_saves(saves: Iterable[SaveInfo]) -> dict[str, list[SaveInfo]]:
    groups: dict[str, list[SaveInfo]] = {}

    for save in saves:
        groups.setdefault(save.display_name, []).append(save)

    for group in groups.values():
        group.sort(key=lambda item: item.modified_time, reverse=True)

    return groups
