import base64
import json
import struct
from pathlib import Path

import pytest

from trm_converter import (
    ENTRY_SIZE,
    NAME_SIZE,
    json_file_to_trm,
    main,
    parse_trm_binary_bytes,
    parse_trm_text,
    trm_file_to_json,
)


FOOTER_FLOAT_COUNT = 8


if __name__ == "__main__":
    raise SystemExit(
        "Dieses Skript enthält nur Tests. Bitte mit 'python -m pytest' ausführen "
        "oder für Konvertierungen 'python trm_converter.py' verwenden."
    )


def _build_entry_bytes(name: str) -> bytes:
    raw = bytearray(ENTRY_SIZE)
    name_bytes = name.encode("ascii")
    raw[0 : len(name_bytes)] = name_bytes

    # header fields start at 0x20
    values = (
        0,  # difficulty
        0,  # time_flag
        1,  # stage_index
        2,  # group
        1,  # flags
        700,  # value
        5,  # count
        100,  # pass_value
        struct.unpack("<I", struct.pack("<f", 0.05))[0],  # rate_u32
        0,  # zero_unused
    )
    struct.pack_into("<10I", raw, 0x20, *values)
    struct.pack_into("<3f", raw, 0x54, 1.0, 2.0, 3.0)

    # tail data should be preserved across edits
    tail_offset = 0x60
    raw[tail_offset:] = b"\xAA" * (ENTRY_SIZE - tail_offset)
    return bytes(raw)


def _build_trm_file(tmp_path: Path, *, entry_count: int = 1) -> Path:
    entries = [_build_entry_bytes(f"Easy/S01/SABO{i}") for i in range(entry_count)]
    footer = struct.pack("<8f", *(i * 1.5 for i in range(FOOTER_FLOAT_COUNT)))

    payload = bytearray()
    payload += struct.pack("<I", entry_count)
    for entry in entries:
        payload += entry
    payload += footer

    trm_path = tmp_path / "sample.trm"
    trm_path.write_bytes(payload)
    return trm_path


def test_parse_binary_trm_to_json(tmp_path: Path):
    trm_path = _build_trm_file(tmp_path)

    parsed = trm_file_to_json(trm_path)

    assert parsed["entry_count"] == 1
    assert len(parsed["entries"]) == 1

    entry = parsed["entries"][0]
    assert entry["name"] == "Easy/S01/SABO0"
    assert entry["difficulty"] == 0
    assert pytest.approx(entry["rate"], rel=1e-6) == 0.05
    assert entry["position"] == {"x": 1.0, "y": 2.0, "z": 3.0}

    decoded_entry = base64.b64decode(entry["raw_entry_base64"])
    assert decoded_entry[:NAME_SIZE].startswith(b"Easy/S01/SABO0")

    footer = parsed["footer"]["floats"]
    assert footer == [i * 1.5 for i in range(FOOTER_FLOAT_COUNT)]


def test_binary_roundtrip_and_edit(tmp_path: Path):
    original_path = _build_trm_file(tmp_path)
    parsed = trm_file_to_json(original_path)

    entry = parsed["entries"][0]
    entry["count"] = 999
    entry["rate"] = 0.1
    entry["position"]["z"] = 9.5

    json_path = tmp_path / "payload.json"
    json_path.write_text(json.dumps(parsed), encoding="utf-8")

    rebuilt_bytes = json_file_to_trm(json_path)
    assert isinstance(rebuilt_bytes, bytes)

    reparsed = parse_trm_binary_bytes(rebuilt_bytes)
    rebuilt_entry = reparsed["entries"][0]

    assert rebuilt_entry["count"] == 999
    assert pytest.approx(rebuilt_entry["rate"], rel=1e-6) == 0.1
    assert rebuilt_entry["position"]["z"] == 9.5

    # Tail bytes remain intact because we start from raw_entry_base64
    original_tail = base64.b64decode(entry["raw_entry_base64"])[0x60:]
    rebuilt_tail = base64.b64decode(rebuilt_entry["raw_entry_base64"])[0x60:]
    assert original_tail == rebuilt_tail


def test_legacy_text_trm_still_parses(tmp_path: Path):
    content = "name = Example\nvalue = 42\n"
    trm_path = tmp_path / "text.trm"
    trm_path.write_text(content, encoding="utf-8")

    parsed = trm_file_to_json(trm_path)
    assert parsed == {"name": "Example", "value": "42"}

    reparsed = parse_trm_text(content)
    assert reparsed["name"] == "Example"


def test_cli_to_json_and_back(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    trm_path = _build_trm_file(tmp_path, entry_count=2)
    out_json = tmp_path / "out.json"

    main(["to-json", str(trm_path), str(out_json)])

    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["entry_count"] == 2

    data["entries"][0]["count"] = 77
    json_path = tmp_path / "edited.json"
    json_path.write_text(json.dumps(data), encoding="utf-8")

    out_trm = tmp_path / "restored.trm"
    main(["to-trm", str(json_path), str(out_trm)])

    repaired = parse_trm_binary_bytes(out_trm.read_bytes())
    assert repaired["entries"][0]["count"] == 77

    captured = capsys.readouterr()
    assert captured.err == ""
