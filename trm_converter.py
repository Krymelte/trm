"""Converter between TRM binary format and JSON.

The primary format supported here is the Little-Endian binary TRM layout
observed in training files:

- u32 entry_count at offset 0x00
- entry_count fixed-size entries (6692 bytes each)
- footer of 8 float32 values (32 bytes)

Each entry exposes the following decoded fields for human-friendly editing:
- name (char[32], null-terminated)
- ten u32 header fields starting at offset 0x20
  difficulty, time_flag, stage_index, group, flags, value, count,
  pass_value, rate_u32 (bitwise float), zero_unused
- position: 3×float32 at offset 0x54
- raw_entry_base64: base64 of the entire 6692-byte entry for lossless
  roundtripping when only a few fields are modified.

Text-based key/value TRM files remain supported as a fallback if the binary
layout cannot be parsed.
"""
from __future__ import annotations

import argparse
import base64
import json
import struct
import sys
from pathlib import Path
from typing import Dict, Iterable, List

ENTRY_SIZE = 6692
FOOTER_FLOAT_COUNT = 8
FOOTER_SIZE = FOOTER_FLOAT_COUNT * 4
HEADER_OFFSET = 4
NAME_SIZE = 32
HEADER_FIELD_COUNT = 10
HEADER_FIELD_OFFSET = 0x20
POSITION_OFFSET = 0x54
POSITION_FLOAT_COUNT = 3

HEADER_FIELD_NAMES = [
    "difficulty",
    "time_flag",
    "stage_index",
    "group",
    "flags",
    "value",
    "count",
    "pass_value",
    "rate_u32",
    "zero_unused",
]


def _decode_bytes_with_fallback(data: bytes, encodings: tuple[str, ...]) -> str:
    """Decode bytes using several encodings in order."""

    last_error: UnicodeDecodeError | None = None
    for encoding in encodings:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError as exc:  # pragma: no cover - exercised via fallback success
            last_error = exc
    if last_error:
        raise last_error
    raise UnicodeDecodeError("unknown", b"", 0, 1, "no encodings provided")


def read_text_with_fallback(
    path: Path, encodings: tuple[str, ...] = ("utf-8", "cp1252", "latin-1")
) -> str:
    """Read text trying several encodings."""

    return _decode_bytes_with_fallback(path.read_bytes(), encodings)


def _raise_if_binary(text: str) -> None:
    """Raise a helpful error if the text looks binary."""

    if "\x00" in text:
        raise ValueError(
            "TRM file appears to be binary (contains NUL bytes). "
            "This tool only supports text-based 'key = value' TRM files."
        )


def parse_trm_text(text: str) -> Dict[str, str]:
    """Parse legacy text TRM content into a dictionary."""

    _raise_if_binary(text)

    data: Dict[str, str] = {}
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Line {line_no} is missing '=': {raw_line!r}")
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _read_cstring(data: bytes, size: int) -> str:
    trimmed = data[:size]
    nul = trimmed.find(b"\x00")
    if nul != -1:
        trimmed = trimmed[:nul]
    return trimmed.decode("ascii", errors="ignore")


def _u32_to_float(value: int) -> float:
    return struct.unpack("<f", struct.pack("<I", value))[0]


def _float_to_u32(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", float(value)))[0]


def _parse_entry(entry_bytes: bytes) -> dict:
    if len(entry_bytes) != ENTRY_SIZE:
        raise ValueError(f"Expected entry size {ENTRY_SIZE}, got {len(entry_bytes)}")

    header_values = struct.unpack_from("<10I", entry_bytes, HEADER_FIELD_OFFSET)
    header_map = dict(zip(HEADER_FIELD_NAMES, header_values))
    position = struct.unpack_from("<3f", entry_bytes, POSITION_OFFSET)

    entry: dict = {
        "name": _read_cstring(entry_bytes, NAME_SIZE),
        **header_map,
        "rate": _u32_to_float(header_map["rate_u32"]),
        "position": {"x": position[0], "y": position[1], "z": position[2]},
        "raw_entry_base64": base64.b64encode(entry_bytes).decode("ascii"),
    }
    return entry


def parse_trm_binary_bytes(data: bytes) -> dict:
    if len(data) < HEADER_OFFSET + FOOTER_SIZE:
        raise ValueError("File too small to be a binary TRM")

    entry_count = struct.unpack_from("<I", data, 0)[0]
    expected_size = HEADER_OFFSET + entry_count * ENTRY_SIZE + FOOTER_SIZE
    if len(data) < expected_size:
        raise ValueError("Binary TRM length does not match entry count")

    entries: List[dict] = []
    for i in range(entry_count):
        offset = HEADER_OFFSET + i * ENTRY_SIZE
        entries.append(_parse_entry(data[offset : offset + ENTRY_SIZE]))

    footer_offset = HEADER_OFFSET + entry_count * ENTRY_SIZE
    footer_floats = list(struct.unpack_from("<8f", data, footer_offset))

    return {"entry_count": entry_count, "entries": entries, "footer": {"floats": footer_floats}}


def _ensure_entry_bytes(base64_data: str | None) -> bytearray:
    if base64_data is None:
        return bytearray(ENTRY_SIZE)
    decoded = base64.b64decode(base64_data)
    if len(decoded) != ENTRY_SIZE:
        raise ValueError(f"raw_entry_base64 must decode to {ENTRY_SIZE} bytes")
    return bytearray(decoded)


def _write_entry(entry: dict) -> bytes:
    raw_bytes = _ensure_entry_bytes(entry.get("raw_entry_base64"))
    if len(raw_bytes) != ENTRY_SIZE:
        raise ValueError(f"Entry must be {ENTRY_SIZE} bytes long")

    name_bytes = entry.get("name", "").encode("ascii", errors="ignore")
    if len(name_bytes) >= NAME_SIZE:
        raise ValueError("Entry name must be shorter than 32 bytes")

    # write name (null-terminated, padded)
    raw_bytes[0:NAME_SIZE] = b"\x00" * NAME_SIZE
    raw_bytes[0 : len(name_bytes)] = name_bytes

    header_values: list[int] = []
    for field in HEADER_FIELD_NAMES:
        if field == "rate_u32":
            rate = entry.get("rate")
            if rate is None:
                rate_u32 = entry.get("rate_u32", 0)
            else:
                rate_u32 = _float_to_u32(rate)
            header_values.append(int(rate_u32))
            continue
        value = entry.get(field, 0)
        header_values.append(int(value))

    struct.pack_into("<10I", raw_bytes, HEADER_FIELD_OFFSET, *header_values)

    pos = entry.get("position") or {}
    coords = (
        float(pos.get("x", 0.0)),
        float(pos.get("y", 0.0)),
        float(pos.get("z", 0.0)),
    )
    struct.pack_into("<3f", raw_bytes, POSITION_OFFSET, *coords)
    return bytes(raw_bytes)


def _binary_json_to_bytes(data: dict) -> bytes:
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise ValueError("JSON must contain an 'entries' array for binary TRM output")

    entry_count = data.get("entry_count", len(entries))
    if entry_count != len(entries):
        raise ValueError("entry_count does not match number of entries")

    footer_floats: Iterable[float]
    footer = data.get("footer", {})
    if isinstance(footer, dict) and isinstance(footer.get("floats"), list):
        footer_floats = footer["floats"]
    else:
        footer_floats = [0.0] * FOOTER_FLOAT_COUNT

    footer_list = list(float(x) for x in footer_floats)
    if len(footer_list) != FOOTER_FLOAT_COUNT:
        raise ValueError("footer.floats must contain 8 float values")

    buffer = bytearray()
    buffer += struct.pack("<I", entry_count)

    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Each entry must be an object")
        buffer += _write_entry(entry)

    buffer += struct.pack("<8f", *footer_list)
    return bytes(buffer)


def trm_from_mapping(mapping: Dict[str, str]) -> str:
    lines = [f"{key} = {value}" for key, value in mapping.items()]
    return "\n".join(lines) + ("\n" if lines else "")


def trm_file_to_json(trm_path: Path) -> Dict[str, object]:
    raw_bytes = trm_path.read_bytes()
    try:
        return parse_trm_binary_bytes(raw_bytes)
    except ValueError:
        text = _decode_bytes_with_fallback(raw_bytes, ("utf-8", "cp1252", "latin-1"))
        return parse_trm_text(text)


def json_file_to_trm(json_path: Path) -> Dict[str, str] | bytes:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object mapping keys to values")

    if "__raw_binary_base64" in data:
        try:
            return base64.b64decode(data["__raw_binary_base64"], validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid base64 data for '__raw_binary_base64'") from exc

    if "entries" in data:
        return _binary_json_to_bytes(data)

    # Legacy text mapping
    return {str(key): str(value) for key, value in data.items()}


def write_json(data: Dict[str, object], output: Path) -> None:
    output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_trm(data: Dict[str, str], output: Path) -> None:
    output.write_text(trm_from_mapping(data), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert between TRM and JSON files.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    to_json = subparsers.add_parser("to-json", help="Convert TRM file to JSON.")
    to_json.add_argument("input", type=Path, help="Path to the source TRM file.")
    to_json.add_argument("output", type=Path, help="Path to write the JSON output.")

    to_trm = subparsers.add_parser("to-trm", help="Convert JSON file to TRM.")
    to_trm.add_argument("input", type=Path, help="Path to the source JSON file.")
    to_trm.add_argument("output", type=Path, help="Path to write the TRM output.")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "to-json":
            data = trm_file_to_json(args.input)
            write_json(data, args.output)
        elif args.command == "to-trm":
            data = json_file_to_trm(args.input)
            if isinstance(data, bytes):
                args.output.write_bytes(data)
            else:
                write_trm(data, args.output)
        else:  # pragma: no cover - argparse enforces allowed commands
            parser.error("Unknown command")
    except (UnicodeDecodeError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
