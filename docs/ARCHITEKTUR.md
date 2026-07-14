# Architektur

## Überblick

Eine Codebasis, drei Auslieferungen: dieselbe HTML-App läuft als **Browser-Datei**, als
**installierbare PWA** (GitHub Pages) und als **Asset in der nativen Android-App**.

```
                      data/coins-raw.json  (API-Snapshot, mit geheimen Tokens – gitignored)
                               │
        scripts/build_route.py │  Dedupe, aktive Münzen im 10-km-Radius, NN + 2-opt (Luftlinie)
                               ▼
                      data/route.json (Vorauswahl, ohne Tokens)
                               │
   scripts/fetch_bike_route.py │  OSRM-Fahrrad-Distanzmatrix, Re-Optimierung, echte Geometrie
                               ▼
                      data/route.json (final, mit Geometrie & realen km)
                               │
 scripts/make_deliverables.py  │  Template + Leaflet + Daten
        ┌──────────────────────┼───────────────────────────┐
        ▼                      ▼                           ▼
 sparmania-karte.html    webapp/ (PWA)              android/assets/karte.html
 (+ GPX/KML-Exporte)     → GitHub Pages             → APK (build_apk.sh)
```

## Datenpipeline

- **`scripts/fetch_coins.sh`** holt den JSON der offenen Karten-API
  (`https://sparmania-200.de/api/coins/map?includeCollected=1`). Die API liefert manche
  Standorte doppelt (gleiche id + Position, anderer Token) und enthält pro Münze einen
  geheimen `token` → wird **nicht** veröffentlicht.
- **`scripts/build_route.py`** dedupliziert auf eindeutige Standorte, filtert die aktuell
  aktiven Münzen im 10-km-Radius um den Start (Hinrichsenstraße 21) und erzeugt eine erste
  Reihenfolge per Nearest-Neighbor + 2-opt + Or-opt auf Luftlinie. Schreibt `data/route.json`
  **ohne** Tokens.
> **Zur Laufzeit einstellbar:** Der Startpunkt ist zwar der Default aus `build_route.py`, kann in
> der App aber pro Gerät geändert werden. Bei einer neuen Home plant die App **on-device** neu –
> eine JS-Portierung der Pipeline: Münzen im Umkreis filtern, Reihenfolge optimieren
> (`optimizeOrder` = NN + 2-opt + or-opt; bei ≤100 Münzen auf echter OSRM-Matrix, sonst Luftlinie),
> echte Geometrie + Etappen-km über OSRM `/route`, Ergebnis in `localStorage` (`sparmania-home`)
> gecacht. `applyRoutePlan` ersetzt `DATA.start/route/geometry/…` und zeichnet Karte + Liste neu.

- **`scripts/fetch_bike_route.py`** holt vom OSRM-Fahrradprofil
  (`routing.openstreetmap.de/routed-bike`) die echte Wege-Distanzmatrix (in Blöcken, da das
  Table-Limit bei 100 Koordinaten liegt; gecacht in `data/bike-matrix.json`), re-optimiert die
  Reihenfolge darauf und lädt die tatsächliche Routen-Geometrie. Ergebnis: realistische
  km/Zeit statt Luftlinie×Faktor.

## Die App (`app/karte.template.html`)

Eine einzelne HTML-Datei mit **eingebettetem Leaflet** (kein CDN → funktioniert offline bis auf
die Kartenkacheln). Reines ES5-JavaScript ohne Framework. Platzhalter, die der Build ersetzt:

| Platzhalter | Inhalt |
|---|---|
| `__LEAFLET_CSS__` / `__LEAFLET_JS__` | eingebettetes Leaflet 1.9.4 |
| `__DATA__` | `route.json` als JSON |
| `__PWA_HEAD__` | nur im Web-App-Build: Manifest, Apple-Meta, Service-Worker-Registrierung |
| `__LOGO_SVG__` | leer in allen veröffentlichten Builds (Logo nur lokal) |

Kernbausteine im Script: Touren-Engine (`activeTour`, `rebuildTour`, `prefixFit`, `nearTour`),
Navigation (`navSeq`, `fetchNavRoute`, `navTick` mit Heading-up-Rotation), Proximity + Sound
(`checkProximity`, `coinChime` via WebAudio), Google-Maps-Export (`gmapsLegs`/`gmapsUrl`) und
GPS/Wake-Lock.

### Design-Grundlage

Die Optik ist Material-Design in Sparkassen-Rot, verfeinert mit dem Token- und
Interaktionsmodell des Design-Systems [Astryx](https://github.com/facebook/astryx) – dessen
Idee „ein Theme ist ein Satz CSS-Custom-Property-Overrides" passt direkt zu unseren CSS-Variablen.
Übernommen (in reinem CSS, ohne die React-Library): mittlere Radien (Container 12 px / Element
10 px), dezelerierendes Easing `cubic-bezier(.24,1,.4,1)` mit 125/300 ms, State-Overlays für
Hover/Pressed plus Press-Scale, Tastatur-Fokusringe (auf Touch unterdrückt), `prefers-reduced-motion`
und weichere, border-basierte Elevation. Astryx' Marken-Hook ist `--color-accent`; bei uns bleibt
das konstant **Sparkassen-Rot `#EE0000`** (`--brand`), alle Zustände leiten sich daraus ab.

## Web-App / PWA

`scripts/make_deliverables.py → build_webapp()` erzeugt `webapp/`:

- **`index.html`** – die App ohne Logo, mit PWA-`<head>`.
- **`manifest.webmanifest`** – `display: standalone`, Theme `#EE0000`, relative Pfade
  (`start_url: "."`), damit es unter dem Pages-Unterpfad `/sparmania/` funktioniert.
- **`sw.js`** – Service-Worker, **network-first** mit Cache-Fallback für den eigenen Origin
  (App-Shell offline verfügbar, aber immer aktuell), Kacheln/OSRM/Sparkasse direkt aus dem
  Netz.
- **`icons/`** – rote Münz-Icons (192/512 „any", 512 maskable, 180 apple-touch), zur Bauzeit
  aus reinem Python (zlib/struct) generiert.

Auslieferung über **GitHub Pages** (GitHub Actions, siehe `.github/workflows/`). GPS/WebAudio
brauchen einen Secure Context – Pages liefert HTTPS, daher funktioniert beides in Safari/Chrome.

### iOS-Besonderheiten

- **Kein `navigator.vibrate`** auf iOS → dort nur Ton, keine Vibration (sauber abgefangen).
- **Wake Lock** hält den Bildschirm während der Navigation an (iOS 16.4+).
- **Profil-Sync** geht in der Web-App nicht automatisch (die Sparmania-API sendet keine
  CORS-Header, und das Session-Cookie ist `SameSite=lax` + `HttpOnly` – ein `fetch` von
  fremder Herkunft wird doppelt blockiert). Lösung: ein **Bookmarklet**, das auf
  sparmania-200.de läuft (dort same-origin, Cookie wird gesendet), die eingesammelten IDs holt
  und per `location.href = <app-url>#sync=[…]` an die App zurückgibt; die App liest den Hash
  beim Laden (`checkHashSync` → `importCollectedIds`). Rückfall bleibt der manuelle
  Paste-Import (`applySync`). Die Android-App braucht beides nicht, sie holt die Daten nativ.

## Android-App (`android/`)

Minimaler nativer WebView-Wrapper (Java, **ohne Gradle** – direkt mit `aapt2`, `javac`, `d8`,
`apksigner` gebaut, siehe `build_apk.sh`).

- Lädt die App über den fiktiven Secure-Origin `https://appassets.local`
  (`shouldInterceptRequest` liefert die Assets) – nötig, damit GPS im WebView funktioniert
  (`file://` blockiert es).
- **JS-Bridge `AndroidApp`** (nur am lokalen App-WebView, nicht am Sparmania-WebView):
  `openOfficial` (nur sparmania-200.de), `openExternal` (nur http/https/geo, z. B. Google Maps),
  `syncCollected` (holt den Profil-Sammelstand über die Session-Cookies).
- Zweiter WebView als Overlay für die offizielle Seite (Login, QR-Scan mit Kamera), mit
  schwebendem „‹ Zur Route"-Button.

## Sicherheit

- API-Titel/Orte werden vor der Ausgabe in Popups **HTML-escaped** (`esc()`), kein XSS über
  manipulierte API-Daten.
- Intent-Weiterleitung im WebView nur für `http`/`https`/`geo` (blockt `tel:`/`intent:` u. a.).
- **Nichts Sensibles im öffentlichen Repo:** Keystore, Keystore-Passwort und die
  Münz-`token` sind per `.gitignore` ausgeschlossen.
