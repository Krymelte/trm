# TRM Converter

Dieses Werkzeug liest das Little-Endian TRM-Format mit festen 6692-Byte-Records
pro Eintrag und wandelt es in ein bearbeitbares JSON um. Beim Rückweg wird aus
dem JSON wieder eine gültige Binär-TRM erzeugt, wobei unbekannte Bytes dank des
`raw_entry_base64`-Feldes unverändert erhalten bleiben.

## Binärformat – Überblick
- Offset `0x00`: `entry_count` (u32, LE)
- Danach `entry_count` Einträge à 6692 Bytes
- Footer: 8 × float32 (32 Bytes)

### Entry-Felder
- `name`: `char[32]` (nullterminiert)
- Header ab `0x20` als 10 × u32
  - `difficulty`, `time_flag`, `stage_index`, `group`, `flags`, `value`,
    `count`, `pass_value`, `rate_u32`, `zero_unused`
  - `rate` wird zusätzlich als float aus `rate_u32` bereitgestellt
- Position ab `0x54`: 3 × float32 (`x`, `y`, `z`)
- Rest des Records: wird als Base64 (`raw_entry_base64`) gespeichert, damit der
  Roundtrip verlustfrei bleibt

### JSON-Struktur
```jsonc
{
  "entry_count": 30,
  "entries": [
    {
      "name": "Easy/S01/SABO",
      "difficulty": 0,
      "time_flag": 0,
      "stage_index": 0,
      "group": 2,
      "flags": 1,
      "value": 700,
      "count": 5,
      "pass_value": 100,
      "rate": 0.05,
      "zero_unused": 0,
      "position": {"x": 1.0, "y": 2.0, "z": 3.0},
      "raw_entry_base64": "..." // kompletter 6692-Byte-Record
    }
  ],
  "footer": {"floats": [f0, f1, f2, f3, f4, f5, f6, f7]}
}
```

Bearbeiten Sie gewünschte Felder (z. B. `count`, `pass_value`, `rate`,
`position`) und lassen Sie `raw_entry_base64` unverändert, damit unbekannte
Bytes erhalten bleiben. Falls Sie neue Einträge anlegen, können Sie das Feld
weglassen; der Converter füllt fehlende Bytes mit Nullen.

## Verwendung
```bash
# TRM → JSON (binär zu editierbaren Feldern aufschlüsseln)
python trm_converter.py to-json training.trm ausgabe.json

# JSON → TRM (mit den angepassten Werten zurückschreiben)
python trm_converter.py to-trm ausgabe.json neues_training.trm
```

Die CLI versucht immer zuerst das binäre Layout zu parsen und fällt nur dann auf
legacy Text-TRM-Dateien zurück, wenn die Binärstruktur nicht passt.

## Tests
```bash
python -m pytest
```
