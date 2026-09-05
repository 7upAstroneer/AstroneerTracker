from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import os, re, time

BROAD_RE = re.compile(
    r"\b(death|dead|died|killed|respawn|respawning|respawned|corpse|"
    r"astrocharacter|playerstate|playercontroller|pawn)\b", re.I
)
EXPLICIT_DEATH_PATTERNS = (
    re.compile(r"\bplayer\b.{0,100}\b(?:died|was killed|death)\b", re.I),
    re.compile(r"\b(?:died|was killed)\b", re.I),
    re.compile(r"\b(?:playerdeath|onplayerdeath|handledeath|death event)\b", re.I),
    re.compile(r"\bastrocharacter\b.{0,100}\b(?:died|death|killed)\b", re.I),
)
RESPAWN_EVENT_PATTERNS = (
    re.compile(r"\brespawned\b", re.I),
    re.compile(r"\brespawning\b", re.I),
    re.compile(r"\brespawnplayer\b", re.I),
    re.compile(r"\brespawncharacter\b", re.I),
    re.compile(r"\bonrespawn\b", re.I),
)
EXCLUDE_RE = re.compile(
    r"(RespawnToken|RespawnSettings|RespawnTokenCount|RespawnTokenState|"
    r"InitialRespawnTokenCount|SecondsUntilRespawn|AstroRespawnToken)", re.I
)

@dataclass
class LiveLogEvent:
    timestamp: float
    kind: str
    line: str
    counted: bool = False

def default_logs_directory() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "Astro" / "Saved" / "Logs"
    return Path.home() / "AppData" / "Local" / "Astro" / "Saved" / "Logs"

class LiveDeathMonitor:
    def __init__(self, trace_path: Path | None = None) -> None:
        self.trace_path = trace_path
        self.logs_directory = default_logs_directory()
        self.log_path: Path | None = None
        self._fh = None
        self._buffer = ""
        self.active_save: str | None = None
        self.active_location: str | None = None
        self.last_candidate = "not attached"
        self.last_counted_line: str | None = None
        self.counted_events = 0
        self._last_counted_at = 0.0
        self._dedupe_seconds = 4.0

    def _append_trace(self, title: str, lines: list[str]) -> None:
        if self.trace_path is None:
            return
        try:
            self.trace_path.parent.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().astimezone().isoformat(timespec="milliseconds")
            with self.trace_path.open("a", encoding="utf-8") as f:
                f.write("\n" + "=" * 96 + "\n")
                f.write(f"{title}  {stamp}\n")
                for line in lines:
                    f.write(line.rstrip("\n") + "\n")
                f.write("=" * 96 + "\n")
        except Exception:
            pass

    def set_context(self, save_name: str | None, location: str | None) -> None:
        self.active_save = save_name
        self.active_location = location

    def _newest_log(self) -> Path | None:
        try:
            files = [p for p in self.logs_directory.glob("*.log") if p.is_file()]
            return max(files, key=lambda p: p.stat().st_mtime_ns) if files else None
        except Exception:
            return None

    def _close(self) -> None:
        try:
            if self._fh is not None:
                self._fh.close()
        except Exception:
            pass
        self._fh = None
        self.log_path = None
        self._buffer = ""

    def reset_session(self) -> None:
        self._close()
        self.active_save = None
        self.active_location = None
        self.last_candidate = "not attached"
        self.last_counted_line = None
        self._last_counted_at = 0.0

    def _attach(self, path: Path) -> None:
        self._close()
        try:
            self._fh = path.open("r", encoding="utf-8", errors="replace")
            self._fh.seek(0, 2)  # only new lines
            self.log_path = path
            self.last_candidate = f"watching {path.name}"
            self._append_trace("LIVE LOG ATTACHED", [
                f"Path: {path}",
                "Mode: seek-to-end; only new log lines will be examined",
            ])
        except Exception as exc:
            self.last_candidate = f"log attach error: {type(exc).__name__}"

    def _ensure_attached(self) -> None:
        newest = self._newest_log()
        if newest is None:
            if self._fh is None:
                self.last_candidate = "no Astroneer .log file found"
            return
        if self.log_path is None or self.log_path != newest:
            self._attach(newest)
            return
        try:
            if newest.stat().st_size < (self._fh.tell() if self._fh else 0):
                self._attach(newest)
        except Exception:
            self._attach(newest)

    @staticmethod
    def _classify(line: str) -> str | None:
        if EXCLUDE_RE.search(line):
            return "RESPAWN_CONFIG"
        if not BROAD_RE.search(line):
            return None
        if any(p.search(line) for p in EXPLICIT_DEATH_PATTERNS):
            return "EXPLICIT_DEATH"
        if any(p.search(line) for p in RESPAWN_EVENT_PATTERNS):
            return "RESPAWN_CANDIDATE"
        if re.search(r"\b(death|died|killed|dead|respawn)\b", line, re.I):
            return "DEATH_RESPAWN_CANDIDATE"
        return "PLAYER_LIFECYCLE_CANDIDATE"

    def poll(self) -> list[LiveLogEvent]:
        self._ensure_attached()
        if self._fh is None:
            return []
        try:
            chunk = self._fh.read()
        except Exception:
            self._close()
            return []
        if not chunk:
            return []

        text = self._buffer + chunk
        parts = text.splitlines(keepends=True)
        complete, self._buffer = [], ""
        for part in parts:
            if part.endswith("\n") or part.endswith("\r"):
                complete.append(part.rstrip("\r\n"))
            else:
                self._buffer = part

        events = []
        now = time.time()
        for line in complete:
            kind = self._classify(line)
            if kind is None:
                continue
            compact = line.strip()
            if len(compact) > 1200:
                compact = compact[:1200] + " ...[truncated]"
            counted = (
                kind == "EXPLICIT_DEATH"
                and self.active_save is not None
                and now - self._last_counted_at >= self._dedupe_seconds
            )
            if counted:
                self._last_counted_at = now
                self.counted_events += 1
                self.last_counted_line = compact
            self.last_candidate = f"{kind}: {compact[:180]}"
            event = LiveLogEvent(now, kind, compact, counted)
            events.append(event)
            self._append_trace(
                "LIVE DEATH EVENT" if counted else "LIVE LOG CANDIDATE",
                [
                    f"Kind: {kind}",
                    f"Counted: {'YES' if counted else 'No'}",
                    f"Active Save: {self.active_save or '—'}",
                    f"Location: {self.active_location or '—'}",
                    f"Log: {self.log_path or '—'}",
                    f"Line: {compact}",
                ],
            )
        return events
