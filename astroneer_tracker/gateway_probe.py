from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import zlib


TELEPORTER_RE = re.compile(rb"TeleporterControlPanel_C_(\d+)")


@dataclass
class GatewayProbeResult:
    total: int | None
    error: str | None = None


def get_gateway_activation_total(path: Path) -> GatewayProbeResult:
    """
    Python port of PowerShell Get-GatewayActivationTotal.

    Count unique TeleporterControlPanel_C_<id> values in decompressed save data.
    """
    try:
        raw_file = path.read_bytes()
        if len(raw_file) < 24:
            return GatewayProbeResult(None, "save too small")

        raw = zlib.decompress(raw_file[16:])
        ids = {m.decode("ascii") for m in TELEPORTER_RE.findall(raw)}
        return GatewayProbeResult(len(ids))
    except Exception as exc:
        return GatewayProbeResult(None, str(exc))
