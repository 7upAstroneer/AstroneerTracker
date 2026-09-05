from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import struct


@dataclass
class DeepProbeResult:
    ascii_strings: list[str]
    utf16_strings: list[str]
    likely_tokens: list[str]
    file_size: int
    error: str | None = None


PRINTABLE_RE = re.compile(rb"[ -~]{5,}")
TOKEN_HINTS = (
    "planet",
    "biome",
    "world",
    "solar",
    "surface",
    "orbit",
    "spawn",
    "player",
    "transform",
    "location",
    "persistent",
    "save",
    "level",
    "astro",
)


def _extract_ascii(data: bytes, limit: int = 5000) -> list[str]:
    out = []
    for m in PRINTABLE_RE.finditer(data):
        s = m.group().decode("ascii", errors="ignore").strip()
        if s:
            out.append(s)
        if len(out) >= limit:
            break
    return out


def _extract_utf16le(data: bytes, min_chars: int = 5, limit: int = 5000) -> list[str]:
    out = []
    i = 0
    n = len(data)

    while i + 2 <= n and len(out) < limit:
        start = i
        chars = []

        while i + 2 <= n:
            pair = data[i:i+2]
            code = pair[0] | (pair[1] << 8)

            if 32 <= code <= 126:
                chars.append(chr(code))
                i += 2
            else:
                break

        if len(chars) >= min_chars:
            out.append("".join(chars))

        i = max(i + 2, start + 2)

    return out


def _interesting(strings: list[str], limit: int = 80) -> list[str]:
    chosen = []
    seen = set()

    for s in strings:
        low = s.lower()

        if any(hint in low for hint in TOKEN_HINTS):
            if s not in seen:
                seen.add(s)
                chosen.append(s)

        if len(chosen) >= limit:
            break

    return chosen


def probe_deep_structure(path: Path) -> DeepProbeResult:
    try:
        data = path.read_bytes()
    except OSError as exc:
        return DeepProbeResult([], [], [], 0, str(exc))

    ascii_strings = _extract_ascii(data)
    utf16_strings = _extract_utf16le(data)

    combined = ascii_strings + utf16_strings
    likely = _interesting(combined)

    return DeepProbeResult(
        ascii_strings=ascii_strings[:80],
        utf16_strings=utf16_strings[:80],
        likely_tokens=likely,
        file_size=len(data),
    )
