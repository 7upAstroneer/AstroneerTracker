from pathlib import Path
import os

APP_NAME = "Astroneer Gameplay Tracker"
VERSION = "1.15.0"

POLL_INTERVAL_MS = 2000

def default_save_directory() -> Path:
    r"""
    Steam/Windows Astroneer save location:
    %LOCALAPPDATA%\Astro\Saved\SaveGames
    """
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Astro" / "Saved" / "SaveGames"

    # Fallback mainly for development/testing.
    return Path.home() / "AppData" / "Local" / "Astro" / "Saved" / "SaveGames"

ACTIVE_CHANGE_WINDOW_SECONDS = 15

ASTRONEER_PROCESS_NAMES = ("Astro-Win64-Shipping.exe", "Astro.exe")

ACTIVE_SAVE_STALE_SECONDS = 120

def tracker_data_directory() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home()
    return base / "AstroneerGameplayTracker"

def tracker_data_file() -> Path:
    return tracker_data_directory() / "tracker_data.json"

DIAGNOSTIC_RETRY_DELAY_SECONDS = 1.0
