# 🪙 Sparmania Route

**Fahrrad-Routenplaner & Navigations-App für die Münzjagd der [Sparmania-Schatzsuche](https://sparmania-200.de/schatzkarte).**
Sammle möglichst viele Münzen mit dem Rad – optimierte Route, Turn-by-Turn-Navigation, Touren nach Zeit, Münz-Signal bei Reichweite und Google-Maps-Export.

Ein Projekt von **[Alex Wolf](https://alexwolf.studio)** — Strategic Product Design &amp; Vibecoding · [alexwolf.studio](https://alexwolf.studio)

> [!IMPORTANT]
> **Inoffizielles, privates Projekt.** Nicht von der Sparkasse Leipzig, keine offizielle
> Verbindung oder Unterstützung. Die Farbwelt orientiert sich an der Marke; das offizielle
> Logo wird in den veröffentlichten Versionen bewusst **nicht** verwendet. Münzen werden
> ausschließlich über die offizielle Seite eingesammelt – diese App plant und navigiert nur.

| | | |
|---|---|---|
| ![Übersicht](docs/screenshots/01-uebersicht.png) | ![Karte](docs/screenshots/03-karte.png) | ![Navigation](docs/screenshots/04-navigation.png) |
| **Übersicht & Touren** | **Karte mit allen Münzen** | **Turn-by-Turn-Navigation** |

## 🚀 Nutzen

- **📱 iPhone / Android – Web-App (PWA):** **[Web-App öffnen »](https://studioalexwolf.github.io/sparmania/)**
  In Safari (iPhone) bzw. Chrome (Android) öffnen → Teilen/Menü → **„Zum Home-Bildschirm"**.
  Läuft dann im Vollbild wie eine App, inkl. GPS.
- **🤖 Android – native App (APK):** **[Neueste APK herunterladen »](https://github.com/studioalexwolf/sparmania/releases/latest)**
  APK aufs Handy, antippen, „Unbekannte Apps installieren" für den Browser/Dateimanager erlauben, installieren.

## ✨ Funktionen im Überblick

| Funktion | Beschreibung |
|---|---|
| **Optimierte Radroute** | 106 Münzen im 10-km-Kern um den Start, per echtem Fahrrad-Routing (OSRM) sortiert – nicht Luftlinie. ~181 km Rundkurs, Kern zuerst. |
| **Touren wählen** | Nach Zeitbudget (Slider), Presets (Schnellrunde / Halbtag / Ganztour) oder **„In der Nähe"** ab GPS-Standort. Route, Liste und Export passen sich an. |
| **Turn-by-Turn-Navigation** | Wie ein Navi von Münze zu Münze: Live-Fahrradroute, Abbiege-Ansagen, Karte dreht in Fahrtrichtung (Heading-up), automatisches Rerouting. |
| **Google-Maps-Export** | Tour als Etappen (max. 9 Zwischenstopps pro Etappe, Google-Limit) direkt in Google Maps im Fahrrad-Modus öffnen. |
| **Münz-Signal** | Ton + Vibration, sobald du in Reichweite (< 70 m) einer offenen Münze bist. |
| **Schnell einsammeln** | Reichweiten-Leiste mit einem Tap zur offiziellen Sammel-Seite; in der Android-App per In-App-Browser mit QR-Scanner und „‹ Zur Route"-Rücksprung. |
| **Fortschritt & Sync** | Eingesammelte Münzen abhaken (bleibt gespeichert); Android-App kann den offiziellen Sammelstand aus dem Sparmania-Profil übernehmen. |
| **Dark Mode** | Folgt dem System; Karte wird nachts abgedunkelt. |

Ausführlich mit Screenshots: **[docs/FUNKTIONEN.md](docs/FUNKTIONEN.md)**

## 🧭 So läuft eine Tour

1. **Tour wählen** (Übersicht) – z. B. „Halbtag" oder ein Zeitbudget einstellen.
2. **Navigation starten** – die App führt dich per Fahrradroute zur nächsten Münze.
3. **In Reichweite** klingelt es – tippe **„Einsammeln"** und scanne den QR-Code vor Ort auf der offiziellen Seite.
4. **„Abhaken & weiter"** – die App springt zur nächsten Münze. Wiederholen bis die Tour voll ist. 🎉

## 🗂️ Projektstruktur

```
app/karte.template.html   Quell-Template der App (eine Datei, Leaflet eingebettet)
webapp/                   Gebaute PWA (index.html, manifest, sw.js, icons) → GitHub Pages
android/                  Native WebView-App (Java, ohne Gradle gebaut)
scripts/                  Daten holen, Route optimieren, Deliverables/PWA bauen
data/route.json           Optimierte Route (ohne geheime Tokens)
docs/                     Dokumentation + Screenshots
sparmania-route.gpx/.kml  Export für Komoot/OsmAnd/Google My Maps
```

- **[docs/ARCHITEKTUR.md](docs/ARCHITEKTUR.md)** – wie Datenpipeline, Routing, PWA und APK zusammenspielen.
- **[docs/ENTWICKLUNG.md](docs/ENTWICKLUNG.md)** – neu bauen, Daten aktualisieren, APK signieren.

## 🔧 Neu bauen (Kurzfassung)

```bash
bash scripts/fetch_coins.sh          # frische Münzdaten von der API (erzeugt data/coins-raw.json)
rm -f data/bike-matrix.json          # Routing-Cache verwerfen (Koordinaten haben sich geändert)
python3 scripts/build_route.py       # Vorauswahl + Luftlinien-Optimierung
python3 scripts/fetch_bike_route.py  # echtes Fahrrad-Routing (OSRM)
python3 scripts/make_deliverables.py # baut sparmania-karte.html, webapp/ und die Exporte
export SPARMANIA_KEYSTORE_PASS=…      # Keystore-Passwort (nicht im Repo)
bash android/build_apk.sh            # signierte APK
```

## 👋 Autor

Entworfen und gebaut von **Alex Wolf** — Strategic Product Design &amp; Vibecoding.
Von der ersten Idee über Kundenverständnis und Produktdesign bis zum lauffähigen Code.
Diese App ist so ein Solo-Build: Datenanalyse, Routen-Optimierung, native App, PWA und Design
aus einer Hand.

**Du hast ein Produkt im Kopf? → [alexwolf.studio](https://alexwolf.studio)**

## ⚖️ Rechtliches

Privates, nicht-kommerzielles Hilfswerkzeug. „Sparkasse", „Sparmania" und zugehörige Logos
sind Marken ihrer jeweiligen Inhaber; dieses Projekt steht in keiner Verbindung zur Sparkasse
Leipzig. Kartendaten © [OpenStreetMap](https://www.openstreetmap.org/copyright)-Mitwirkende,
Routing über [OSRM](https://routing.openstreetmap.de). Leaflet unter BSD-2-Clause.
