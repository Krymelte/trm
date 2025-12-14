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
import base64
import json
import sys
from pathlib import Path
from typing import Dict


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
    """Raise a helpful error if the text looks binary.

    The converter only supports the documented text-based TRM format. Files that
    contain NUL bytes or other binary data cannot be parsed and would otherwise
    surface confusing "missing '='" errors.
    """

    if "\x00" in text:
        raise ValueError(
            "TRM file appears to be binary (contains NUL bytes). "
            "This tool only supports text-based 'key = value' TRM files. "
            "If you want to try anyway, rerun with --allow-binary to strip NUL bytes first."
        )


def parse_trm_text(text: str, *, allow_binary: bool = False) -> Dict[str, str]:
    """Parse TRM content into a dictionary.

    Raises:
        ValueError: if a data line does not contain an equals sign.
    """

    if allow_binary:
        text = text.replace("\x00", "")
    else:
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


def _extract_printable_segments(raw_bytes: bytes, *, min_length: int = 3) -> list[dict[str, int | str]]:
    """Return human-friendly previews from a binary payload.

    The original bytes are also stored (base64-encoded) so we can always recreate
    the exact content. Printable previews are only a hint to help users locate
    embedded strings that might be worth editing or inspecting.
    """

    decoded = raw_bytes.decode("latin-1", errors="ignore")
    segments: list[dict[str, int | str]] = []

    current = ""
    start = 0
    for idx, ch in enumerate(decoded):
        is_printable = 32 <= ord(ch) <= 126
        if is_printable:
            if not current:
                start = idx
            current += ch
            continue
        if len(current) >= min_length:
            segments.append({"offset": start, "text": current})
        current = ""
    if len(current) >= min_length:
        segments.append({"offset": start, "text": current})

    return segments


def _binary_to_base64_dict(raw_bytes: bytes) -> Dict[str, object]:
    """Wrap binary data in a JSON-friendly mapping with preview strings."""

    payload: Dict[str, object] = {
        "__raw_binary_base64": base64.b64encode(raw_bytes).decode("ascii")
    }
    preview = _extract_printable_segments(raw_bytes)
    if preview:
        payload["__printable_preview"] = preview
    return payload


def trm_from_mapping(mapping: Dict[str, str]) -> str:
    """Serialize mapping into TRM text."""

    lines = [f"{key} = {value}" for key, value in mapping.items()]
    return "\n".join(lines) + ("\n" if lines else "")


def trm_file_to_json(trm_path: Path, *, allow_binary: bool = False) -> Dict[str, str]:
    if not allow_binary:
        return parse_trm_text(read_text_with_fallback(trm_path), allow_binary=False)

    raw_bytes = trm_path.read_bytes()
    try:
        text = _decode_bytes_with_fallback(raw_bytes, ("utf-8", "cp1252", "latin-1"))
    except UnicodeDecodeError:
        return _binary_to_base64_dict(raw_bytes)

    try:
        return parse_trm_text(text, allow_binary=True)
    except ValueError:
        return _binary_to_base64_dict(raw_bytes)


def json_file_to_trm(json_path: Path) -> Dict[str, str] | bytes:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object mapping keys to values")

    if "__raw_binary_base64" in data:
        try:
            return base64.b64decode(data["__raw_binary_base64"], validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid base64 data for '__raw_binary_base64'") from exc

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
    to_json.add_argument(
        "--allow-binary",
        action="store_true",
        help="Strip NUL bytes before parsing to attempt conversion of semi-binary files.",
    )

    to_trm = subparsers.add_parser("to-trm", help="Convert JSON file to TRM.")
    to_trm.add_argument("input", type=Path, help="Path to the source JSON file.")
    to_trm.add_argument("output", type=Path, help="Path to write the TRM output.")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "to-json":
            data = trm_file_to_json(args.input, allow_binary=args.allow_binary)
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
