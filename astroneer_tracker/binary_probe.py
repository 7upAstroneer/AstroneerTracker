from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import binascii
import gzip
import io
import lzma
import struct
import zlib


@dataclass
class BinaryProbeResult:
    file_size: int
    first_64_hex: str
    first_16_ascii: str
    entropy_sample: float
    signatures: list[str]
    decompression_results: list[str]
    error: str | None = None


def _entropy(data: bytes) -> float:
    if not data:
        return 0.0

    counts = [0] * 256
    for b in data:
        counts[b] += 1

    import math
    n = len(data)
    h = 0.0
    for c in counts:
        if c:
            p = c / n
            h -= p * math.log2(p)
    return h


def _ascii_preview(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b <= 126 else "." for b in data)


def _try_zlib(data: bytes) -> list[str]:
    out = []

    for label, wbits in (
        ("zlib", zlib.MAX_WBITS),
        ("raw-deflate", -zlib.MAX_WBITS),
        ("gzip-via-zlib", zlib.MAX_WBITS | 16),
    ):
        try:
            dec = zlib.decompress(data, wbits)
            out.append(f"{label}: SUCCESS ({len(dec):,} bytes)")
        except Exception as exc:
            out.append(f"{label}: no ({type(exc).__name__})")

    return out


def _try_gzip(data: bytes) -> str:
    try:
        dec = gzip.decompress(data)
        return f"gzip: SUCCESS ({len(dec):,} bytes)"
    except Exception as exc:
        return f"gzip: no ({type(exc).__name__})"


def _try_lzma(data: bytes) -> str:
    try:
        dec = lzma.decompress(data)
        return f"lzma/xz: SUCCESS ({len(dec):,} bytes)"
    except Exception as exc:
        return f"lzma/xz: no ({type(exc).__name__})"


def probe_binary_container(path: Path) -> BinaryProbeResult:
    try:
        data = path.read_bytes()
    except OSError as exc:
        return BinaryProbeResult(
            0, "", "", 0.0, [], [], str(exc)
        )

    head = data[:64]
    sample = data[: min(len(data), 1024 * 1024)]

    signatures = []

    known = [
        (b"\x1f\x8b", "GZIP magic"),
        (b"PK\x03\x04", "ZIP magic"),
        (b"\x78\x01", "Possible zlib header 78 01"),
        (b"\x78\x9c", "Possible zlib header 78 9C"),
        (b"\x78\xda", "Possible zlib header 78 DA"),
        (b"\xfd7zXZ\x00", "XZ/LZMA magic"),
        (b"LZ4", "LZ4 text signature"),
        (b"\x04\x22\x4d\x18", "LZ4 frame magic"),
        (b"\x28\xb5\x2f\xfd", "Zstandard frame magic"),
    ]

    for sig, label in known:
        if data.startswith(sig):
            signatures.append(f"STARTS WITH: {label}")
        elif sig in data[:1024 * 1024]:
            signatures.append(f"FOUND WITHIN FIRST 1 MiB: {label}")

    if not signatures:
        signatures.append("No common compression/container signature detected.")

    dec_results = []
    dec_results.extend(_try_zlib(data))
    dec_results.append(_try_gzip(data))
    dec_results.append(_try_lzma(data))

    return BinaryProbeResult(
        file_size=len(data),
        first_64_hex=binascii.hexlify(head, sep=b" ").decode("ascii"),
        first_16_ascii=_ascii_preview(data[:16]),
        entropy_sample=_entropy(sample),
        signatures=signatures,
        decompression_results=dec_results,
    )
