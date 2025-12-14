# TRM Converter

Dieses kleine Werkzeug wandelt einfache TRM-Dateien in JSON um und wieder zurück. Es
versucht TRM-Dateien zuerst als UTF-8 zu lesen und fällt bei Bedarf automatisch auf
Windows-1252/Latin-1 zurück.

## TRM-Format

* Jede Datenzeile enthält `key = value`.
* Kommentare beginnen mit `#` und werden ignoriert.
* Leerzeilen werden ignoriert.

Das JSON-Ergebnis ist ein flaches Objekt mit Schlüssel-Wert-Paaren als Strings.

## Verwendung

```bash
# TRM nach JSON konvertieren
python trm_converter.py to-json eingabe.trm ausgabe.json

# JSON zurück nach TRM
python trm_converter.py to-trm eingabe.json ausgabe.trm
```

## Tests

```bash
python -m pytest
```
