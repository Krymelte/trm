# TRM Converter

Dieses kleine Werkzeug wandelt einfache TRM-Dateien in JSON um und wieder zurück. Es
versucht TRM-Dateien zuerst als UTF-8 zu lesen und fällt bei Bedarf automatisch auf
Windows-1252/Latin-1 zurück.

> Hinweis: Das Tool unterstützt nur textbasierte TRM-Dateien nach dem unten
> beschriebenen Schlüssel/Wert-Format. Binäre TRM-Dateien mit NUL-Bytes oder
> proprietären Strukturen können nicht automatisch in JSON umgewandelt werden;
> in solchen Fällen beendet sich die CLI mit einer klaren Fehlermeldung ohne
> Python-Traceback. Falls Sie es trotzdem versuchen möchten, können Sie mit
> `--allow-binary` NUL-Bytes entfernen lassen. Wenn das Ergebnis danach noch
> immer nicht als Text geparst werden kann, wird die Datei stattdessen roh
> als Base64 (`__raw_binary_base64`) in JSON verpackt und kann über denselben
> Schlüssel wieder zurück in eine Binärdatei konvertiert werden.

## TRM-Format

* Jede Datenzeile enthält `key = value`.
* Kommentare beginnen mit `#` und werden ignoriert.
* Leerzeilen werden ignoriert.

Das JSON-Ergebnis ist ein flaches Objekt mit Schlüssel-Wert-Paaren als Strings.

## Verwendung

```bash
# TRM nach JSON konvertieren
python trm_converter.py to-json eingabe.trm ausgabe.json

# Optional: NUL-Bytes vor dem Parsen entfernen
python trm_converter.py to-json --allow-binary eingabe.trm ausgabe.json

# Falls die Datei nicht textbasiert ist, erhalten Sie in `ausgabe.json`
# einen Eintrag `{"__raw_binary_base64": "..."}`. Dieser lässt sich mit
# `to-trm` wieder in die ursprüngliche Binärdatei zurückführen.

# JSON zurück nach TRM
python trm_converter.py to-trm eingabe.json ausgabe.trm
```

## Tests

```bash
python -m pytest
```
