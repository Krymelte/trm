import json
from pathlib import Path

import pytest

from trm_converter import (
    json_file_to_trm,
    parse_trm_text,
    trm_file_to_json,
    trm_from_mapping,
    read_text_with_fallback,
)


if __name__ == "__main__":
    raise SystemExit(
        "Dieses Skript enthält nur Tests. Bitte mit 'python -m pytest' ausführen "
        "oder für Konvertierungen 'python trm_converter.py' verwenden."
    )


def test_parse_trm_text_with_comments_and_blank_lines(tmp_path: Path):
    content = """
# example trm file
name = Example

version = 1.0
# trailing comment
"""
    trm_path = tmp_path / "sample.trm"
    trm_path.write_text(content, encoding="utf-8")

    parsed = trm_file_to_json(trm_path)
    assert parsed == {"name": "Example", "version": "1.0"}


def test_json_roundtrip(tmp_path: Path):
    mapping = {"key1": "value1", "key2": "value2"}

    trm_path = tmp_path / "output.trm"
    trm_text = trm_from_mapping(mapping)
    trm_path.write_text(trm_text, encoding="utf-8")

    parsed = trm_file_to_json(trm_path)
    assert parsed == mapping

    json_path = tmp_path / "data.json"
    json_path.write_text(json.dumps(mapping), encoding="utf-8")

    back_to_trm = json_file_to_trm(json_path)
    assert back_to_trm == mapping


def test_invalid_line_raises(tmp_path: Path):
    trm_path = tmp_path / "bad.trm"
    trm_path.write_text("invalid line", encoding="utf-8")

    with pytest.raises(ValueError):
        trm_file_to_json(trm_path)


def test_json_root_must_be_object(tmp_path: Path):
    json_path = tmp_path / "bad.json"
    json_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError):
        json_file_to_trm(json_path)


def test_trm_reading_with_encoding_fallback(tmp_path: Path):
    # Contains "¼" encoded as cp1252 to simulate Windows-encoded TRM files
    content = "name = Café\nnote = ¼\n".encode("cp1252")
    trm_path = tmp_path / "windows.trm"
    trm_path.write_bytes(content)

    parsed = trm_file_to_json(trm_path)
    assert parsed == {"name": "Café", "note": "¼"}

    # helper is exposed for completeness
    assert read_text_with_fallback(trm_path).startswith("name = Café")


def test_binary_file_gives_clear_error(tmp_path: Path):
    # A binary-looking payload containing NUL bytes should raise a clear message
    binary_bytes = b"\x00\x00\x00Easy/S01/SABO\x00\x00\x00"
    trm_path = tmp_path / "binary.trm"
    trm_path.write_bytes(binary_bytes)

    with pytest.raises(ValueError, match="binary"):
        trm_file_to_json(trm_path)
