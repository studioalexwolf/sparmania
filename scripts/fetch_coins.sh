#!/bin/bash
# Holt die aktuellen Münzdaten von der Sparmania-API.
# Danach: python3 scripts/build_route.py  (baut Route + alle Dateien neu)
cd "$(dirname "$0")/.."
curl -sL --max-time 30 \
  -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36" \
  "https://sparmania-200.de/api/coins/map?includeCollected=1" \
  -o data/coins-raw.json
python3 -c "import json; d=json.load(open('data/coins-raw.json')); print(f'{len(d)} Münzen geladen')"
