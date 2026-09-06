# Astroneer Gameplay Tracker

Windows desktop gameplay tracker for **ASTRONEER**, currently at **v1.15**.

The tracker reads local Astroneer save data and maintains persistent gameplay
statistics and progression information. It includes planet/location tracking,
play time, visits, deaths, Gateway/Core progress, Galastropods, EXO Aid
information, MegaTech structures/stages, save browsing, manual corrections,
and special-location progression.

## Current version

**v1.15**

Notable current features include:

- Seven-planet visit/time/death tracking
- Orbital Platform, Unidentified Satellite, and Sun Room tracking
- Gateway and Core progress
- Galastropod progress
- EXO Aid resource reference
- MegaTech tracking:
  - DLS with planet/location
  - Intermodal Platform
  - Biodome count, highest current stage, and location
  - Museum count, stage, and location
  - Orbital Platform count, stage, and orbiting planet
- Manual Data Input for persistent corrections
- Automatic save recognition and save browsing
- Offline bundled UI images/assets
- Unidentified Satellite Success detection when the seven required Gateway
  Keys disappear, even if extra triptychs are retained

## Run from Python source

Requirements:

- Windows
- Python 3
- ASTRO installed with normal local save-game folders

Install dependencies:

```text
python -m pip install -r requirements.txt
```

Run:

```text
python main.py
```

You can also double-click `RUN_TRACKER.bat`.

## Build a Windows standalone executable

Double-click:

`BUILD_WINDOWS_STANDALONE.bat`

The script installs the required build dependencies and uses PyInstaller to
create a Windows standalone distribution under `dist`.

See `WINDOWS_STANDALONE_BUILD.md` for details.

## Controls

See `EXPLANATION_OF_BUTTONS.md` for the tracker controls and what each one does.

## Repository contents

- `main.py` — source entry point
- `astroneer_tracker/` — tracker source and bundled assets
- `requirements.txt` — Python runtime dependencies
- `RUN_TRACKER.bat` — convenient source launcher
- `BUILD_WINDOWS_STANDALONE.bat` — Windows standalone build script
- `Astroneer_Gameplay_Tracker.spec` — PyInstaller build definition
- `EXPLANATION_OF_BUTTONS.md` — control reference
- `WINDOWS_STANDALONE_BUILD.md` — build instructions
- `CHANGELOG.md` — current release notes

## Data safety

The tracker reads Astroneer save files and keeps its own tracking/diagnostic
data separately. The **Clear ALL Data** control applies to tracker-maintained
data and should be used deliberately.
