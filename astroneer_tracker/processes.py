from __future__ import annotations

import os
import subprocess

from .config import ASTRONEER_PROCESS_NAMES


def _tasklist_contains(image_name: str) -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False

    output = (result.stdout or "").strip().lower()

    if not output:
        return False

    # tasklist returns an INFO line when no task matches.
    if output.startswith("info:"):
        return False

    return image_name.lower() in output


def is_astroneer_running() -> bool:
    """
    Return True when a known Astroneer Windows process is running.
    """
    if os.name != "nt":
        return False

    return any(_tasklist_contains(name) for name in ASTRONEER_PROCESS_NAMES)
