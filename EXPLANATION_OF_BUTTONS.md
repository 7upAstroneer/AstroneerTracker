# Explanation of Buttons — v1.15

## Save Browser controls

### Refresh Saves
Re-scans Astroneer's SaveGames folder and refreshes the save list and tracker
view. Use it when a save has been created, renamed, deleted, or otherwise does
not yet appear correctly in the list.

### Open Last 10 Saves
Opens the tracker's diagnostic autosave-copy folder containing the retained
recent save snapshots used for comparison and recovery/testing.

### Copy Stored Data
Copies the tracker's stored information so it can be captured or shared for
diagnostics without manually selecting the status text.

### Astroneer's Saves
Opens Astroneer's actual local SaveGames folder.

### Manual Data Input
Opens the manual correction utility for persistent tracker values. This is
useful when something happened in gameplay that could not be detected from a
save transition, such as correcting a missed visit or death.

### Clear ALL Data
Deletes/reset the tracker's stored tracking data. This is intentionally the
destructive tracker-data control; use it only when you want to start the
tracker's records over.

## Research List
Opens the offline Research List/Research Item tracker. Its bundled images are
stored with the application so the feature does not require internet access.

## Planet selection
Selecting a planet changes the Planet Information panel to that planet. Status
colors remain visible while a row is selected.

## Save selection
Selecting a save in the right-side save table changes the save being viewed.
While Astroneer is running, the tracker can automatically follow the detected
active save. When the game is not running, manual browsing is left alone so
you can scroll/select other saves.

## MegaTech information buttons
The small `i` controls beside supported MegaTech entries show the resource or
construction information associated with that item.

MegaTech currently reports DLS, Intermodal Platform, Biodome, Museum, and
Orbital Platform. Green indicates that at least one applicable structure has
been detected. Staged structures can show `(S1)`, `(S2)`, or `(S3)` where
stage detection has been established.

## Status/color behavior
Red generally indicates a locked/not-yet-detected requirement. Green indicates
a detected/completed/currently present condition. Special destinations are
hidden from Gameplay Totals until they become available according to their
progression rules.
