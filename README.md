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
> als Base64 (`__raw_binary_base64`) in JSON verpackt. Zusätzlich wird ein
> `__printable_preview` mit eingebetteten Klartext-Fragmenten erzeugt, damit
> Sie z. B. im Hexmix Zeichenketten wie Levelnamen oder Pfade sehen und
> gezielt in einem externen Tool bearbeiten können. Über denselben
> `__raw_binary_base64`-Schlüssel lässt sich die Binärdatei unverändert
> wiederherstellen.

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

# Falls die Datei nicht textbasiert ist, enthält `ausgabe.json` mindestens
# `{"__raw_binary_base64": "..."}` und optional einen `__printable_preview`.
# Sie können die Datei über `to-trm` wieder in die ursprüngliche Binärdatei
# zurückführen.

# JSON zurück nach TRM
python trm_converter.py to-trm eingabe.json ausgabe.trm
```

## Tests

```bash
python -m pytest
```
