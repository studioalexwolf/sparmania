# Entwicklung & Neu bauen

## Voraussetzungen

- **Python 3** (Standardbibliothek reicht – keine Pakete nötig).
- **Node.js** (optional, für die automatische Syntaxprüfung des App-Scripts).
- Für die APK: **JDK** + **Android SDK** (build-tools ≥ 34, platform android-34). Einmalig:
  `bash android/setup_toolchain.sh` (installiert OpenJDK + command-line-tools über Homebrew,
  bestätigt die Google-SDK-Lizenzen).

## Daten aktualisieren & alles neu bauen

```bash
bash scripts/fetch_coins.sh          # frische Münzdaten (erzeugt data/coins-raw.json)
rm -f data/bike-matrix.json          # Routing-Cache verwerfen, sonst gilt die alte Koordinatenliste
python3 scripts/build_route.py       # Vorauswahl + Luftlinien-Optimierung → data/route.json
python3 scripts/fetch_bike_route.py  # echtes OSRM-Fahrrad-Routing (Matrix, Geometrie)
python3 scripts/make_deliverables.py # baut sparmania-karte.html, webapp/ und GPX/KML
```

Sinnvoll z. B. wenn neue Münzen freischalten. `make_deliverables.py` prüft das App-Script
vorher mit `node --check` (fängt u. a. gerade Anführungszeichen in deutschen Zitaten ab, die
den JS-String still zerbrechen würden).

## APK bauen

```bash
export SPARMANIA_KEYSTORE_PASS=<keystore-passwort>   # NICHT im Repo
bash android/build_apk.sh                            # → sparmania.apk (signiert)
```

- Der **Keystore** (`android/sparmania-release.keystore`) ist per `.gitignore` ausgeschlossen
  und liegt nur lokal. Er wird für App-Updates gebraucht: Android akzeptiert Updates nur mit
  derselben Signatur. **Aufheben** – ohne ihn müssten Nutzer deinstallieren und neu
  installieren.
- Fehlt der Keystore, erzeugt `build_apk.sh` beim ersten Lauf einen neuen (mit dem gesetzten
  Passwort).
- `build_apk.sh` nimmt automatisch die neueste installierte `build-tools`-Version (das ältere
  `d8` aus build-tools 34 verträgt aktuelles `javac`-Output nicht).

## Web-App lokal testen

```bash
python3 -m http.server 8734        # im Projektordner
# dann http://127.0.0.1:8734/webapp/index.html öffnen
```

Nützliche Query-Parameter der App:

- `?demo=1` – simuliert eine GPS-Fahrt (~8 m/s entlang der Route) zum Testen der Navigation.
- `?dark=1` – erzwingt den Dark Mode.

## GitHub Pages (Web-App-Hosting)

Die PWA im Ordner `webapp/` wird per GitHub Actions deployt
(`.github/workflows/deploy-pages.yml`). Ein Push auf `main` baut und veröffentlicht sie unter
`https://studioalexwolf.github.io/sparmania/`. Pages-Quelle steht auf „GitHub Actions".

## Screenshots für die Doku neu erzeugen

Die Bilder in `docs/screenshots/` wurden mit einem Headless-Browser (Playwright) bei
iPhone-Größe von der laufenden Web-App aufgenommen. Zum Aktualisieren die Web-App lokal starten
und die vier Tabs (plus Demo-Navigation und Reichweiten-Leiste) abfotografieren.

## Startadresse / Stellschrauben

In `scripts/build_route.py`:

- `START` – Startadresse (aktuell Hinrichsenstraße 21, Leipzig).
- `RADIUS_KM` – welche Münzen in die Route kommen (Luftlinie vom Start).
- `CORE_KM` – Grenze der „Kern-Zone".
