from __future__ import annotations

import os


def place_on_primary_monitor_fullscreen(root) -> None:
    """
    Maximize the Tk window on Display 1 / the primary monitor.
    """
    root.update_idletasks()

    if os.name == "nt":
        try:
            root.state("zoomed")
            return
        except Exception:
            pass

    try:
        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()
        root.geometry(f"{width}x{height}+0+0")
    except Exception:
        pass
