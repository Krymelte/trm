"""Simple converter between TRM and JSON formats.

TRM format supported by this tool is a line-oriented key-value file. Each
non-empty, non-comment line must contain a key and value separated by an
equals sign ("="). Whitespace around keys and values is trimmed. Lines
starting with "#" are treated as comments. Blank lines and comments are
ignored when converting to JSON.

The JSON representation is a flat object mapping keys to string values.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict


def read_text_with_fallback(path: Path, encodings: tuple[str, ...] = ("utf-8", "cp1252", "latin-1")) -> str:
    """Read text trying several encodings.

    Tries each encoding in order and returns the first successful decode. Raises
    the last UnicodeDecodeError if all attempts fail.
    """

    last_error: UnicodeDecodeError | None = None
    for encoding in encodings:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:  # pragma: no cover - exercised via fallback success
            last_error = exc
    if last_error:
        raise last_error
    raise UnicodeDecodeError("unknown", b"", 0, 1, "no encodings provided")


def parse_trm_text(text: str) -> Dict[str, str]:
    """Parse TRM content into a dictionary.

    Raises:
        ValueError: if a data line does not contain an equals sign.
    """

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


def trm_from_mapping(mapping: Dict[str, str]) -> str:
    """Serialize mapping into TRM text."""

    lines = [f"{key} = {value}" for key, value in mapping.items()]
    return "\n".join(lines) + ("\n" if lines else "")


def trm_file_to_json(trm_path: Path) -> Dict[str, str]:
    return parse_trm_text(read_text_with_fallback(trm_path))


def json_file_to_trm(json_path: Path) -> Dict[str, str]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object mapping keys to values")
    return {str(key): str(value) for key, value in data.items()}


def write_json(data: Dict[str, str], output: Path) -> None:
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

    if args.command == "to-json":
        data = trm_file_to_json(args.input)
        write_json(data, args.output)
    elif args.command == "to-trm":
        data = json_file_to_trm(args.input)
        write_trm(data, args.output)
    else:
        parser.error("Unknown command")


if __name__ == "__main__":
    main()
