#!/usr/bin/env python3
"""Erzeugt aus data/route.json alle Deliverables:

  sparmania-karte.html   Karten-App (Leaflet eingebettet, offline bis auf Kacheln)
  sparmania-route.gpx    für Komoot / OsmAnd / Strava / Radcomputer
  sparmania-route.kml    für Google My Maps (Route + nummerierte Punkte)
  alle-muenzen.kml       alle aktiven Münzen inkl. Umland, nach Ort gruppiert

Aufruf:  python3 scripts/make_deliverables.py
"""
import json
import os
from datetime import datetime
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo


def de_date(iso):
    """UTC-Timestamp -> lokales Datum (Europe/Berlin), z.B. 01.08.2026."""
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Berlin"))
        return d.strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return str(iso)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(*parts, mode="r"):
    with open(os.path.join(BASE, *parts), mode) as f:
        return f.read()


def write(name, content):
    path = os.path.join(BASE, name)
    with open(path, "w") as f:
        f.write(content)
    print(f"-> {name} ({os.path.getsize(path)//1024} KB)")


def make_gpx(r):
    s = r["start"]
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<gpx version="1.1" creator="Sparmania Routenplaner" xmlns="http://www.topografix.com/GPX/1/1">',
           f'<metadata><name>Sparmania Rundkurs ({len(r["route"])} Münzen, ~{r["totalKm"]} km)</name>'
           f'<time>{r["generatedAt"]}</time></metadata>',
           f'<wpt lat="{s["lat"]}" lon="{s["lon"]}"><name>START {escape(s["title"])}</name><sym>Flag</sym></wpt>']
    for c in r["route"]:
        out.append(f'<wpt lat="{c["lat"]}" lon="{c["lon"]}">'
                   f'<name>{c["num"]:03d} {escape(c["title"])}</name>'
                   f'<desc>{escape(c["place"])} | km {c["kmFromStart"]} ab Start | {c["kmHome"]} km heim</desc></wpt>')
    out.append('<trk><name>Sparmania Rundkurs</name><trkseg>')
    out.append(f'<trkpt lat="{s["lat"]}" lon="{s["lon"]}"/>')
    for c in r["route"]:
        out.append(f'<trkpt lat="{c["lat"]}" lon="{c["lon"]}"/>')
    out.append(f'<trkpt lat="{s["lat"]}" lon="{s["lon"]}"/>')
    out.append('</trkseg></trk></gpx>')
    return "\n".join(out)


KML_HEAD = '<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
KML_STYLES = ('<Style id="core"><IconStyle><color>ff00b8f5</color>'
              '<Icon><href>https://maps.google.com/mapfiles/kml/paddle/wht-blank.png</href></Icon></IconStyle></Style>'
              '<Style id="ring"><IconStyle><color>ff327d2e</color>'
              '<Icon><href>https://maps.google.com/mapfiles/kml/paddle/wht-blank.png</href></Icon></IconStyle></Style>'
              '<Style id="start"><IconStyle><color>ff2828c6</color>'
              '<Icon><href>https://maps.google.com/mapfiles/kml/paddle/red-stars.png</href></Icon></IconStyle></Style>'
              '<Style id="line"><LineStyle><color>ff327d2e</color><width>3</width></LineStyle></Style>')


def make_kml_route(r):
    s = r["start"]
    out = [KML_HEAD, f'<name>Sparmania Rundkurs ({len(r["route"])} Münzen)</name>', KML_STYLES]
    out.append('<Folder><name>Route</name><Placemark><name>Rundkurs</name><styleUrl>#line</styleUrl>'
               '<LineString><tessellate>1</tessellate><coordinates>')
    coords = [f'{s["lon"]},{s["lat"]},0']
    coords += [f'{c["lon"]},{c["lat"]},0' for c in r["route"]]
    coords.append(f'{s["lon"]},{s["lat"]},0')
    out.append(" ".join(coords))
    out.append('</coordinates></LineString></Placemark></Folder>')
    out.append('<Folder><name>Münzen</name>')
    out.append(f'<Placemark><name>START {escape(s["title"])}</name><styleUrl>#start</styleUrl>'
               f'<Point><coordinates>{s["lon"]},{s["lat"]},0</coordinates></Point></Placemark>')
    for c in r["route"]:
        style = "core" if c["core"] else "ring"
        # KML-2.2-Schema verlangt description VOR styleUrl
        out.append(f'<Placemark><name>{c["num"]:03d} {escape(c["title"])}</name>'
                   f'<description>{escape(c["place"])} | km {c["kmFromStart"]} ab Start | {c["kmHome"]} km heim</description>'
                   f'<styleUrl>#{style}</styleUrl>'
                   f'<Point><coordinates>{c["lon"]},{c["lat"]},0</coordinates></Point></Placemark>')
    out.append('</Folder></Document></kml>')
    return "\n".join(out)


def make_kml_all(r):
    out = [KML_HEAD, '<name>Sparmania: alle Münzen</name>', KML_STYLES]
    by_place = {}
    for c in r["route"]:
        by_place.setdefault(c["place"], []).append((c["title"], c["lat"], c["lon"], f'Route #{c["num"]}'))
    for c in r["outsideActive"]:
        by_place.setdefault(c["place"], []).append((c["title"], c["lat"], c["lon"], "aktiv, außerhalb der Radroute"))
    for place in sorted(by_place, key=lambda p: -len(by_place[p])):
        out.append(f'<Folder><name>{escape(place)} ({len(by_place[place])})</name>')
        for title, lat, lon, desc in by_place[place]:
            out.append(f'<Placemark><name>{escape(title)}</name><description>{escape(desc)}</description>'
                       f'<Point><coordinates>{lon},{lat},0</coordinates></Point></Placemark>')
        out.append('</Folder>')
    if r["future"]:
        out.append(f'<Folder><name>Bald aktiv ({len(r["future"])})</name>')
        for c in r["future"]:
            out.append(f'<Placemark><name>{escape(c["title"])}</name>'
                       f'<description>{escape(c["place"])} | aktiv ab {de_date(c["activeFrom"])}</description>'
                       f'<Point><coordinates>{c["lon"]},{c["lat"]},0</coordinates></Point></Placemark>')
        out.append('</Folder>')
    out.append('</Document></kml>')
    return "\n".join(out)


def check_app_syntax():
    """Node-Syntaxprüfung des App-Scripts, falls node vorhanden (fängt z.B.
    gerade Anführungszeichen in deutschen Zitaten ab, bevor die App still bricht)."""
    import re
    import shutil
    import subprocess
    import tempfile
    if not shutil.which("node"):
        return
    tpl = load("app", "karte.template.html")
    app_js = re.findall(r"<script>(.*?)</script>", tpl, re.S)[-1]
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(app_js)
        path = f.name
    res = subprocess.run(["node", "--check", path], capture_output=True, text=True)
    os.remove(path)
    if res.returncode != 0:
        raise SystemExit("App-Script-Syntaxfehler:\n" + res.stderr)
    print("App-Script-Syntax ok (node --check)")


PWA_HEAD = """<link rel="manifest" href="manifest.webmanifest">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Sparmania">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="192x192" href="icons/icon-192.png">
<script>
if("serviceWorker" in navigator){window.addEventListener("load",function(){navigator.serviceWorker.register("sw.js").catch(function(){});});}
</script>"""


def make_html(r, logo=True, pwa_head=""):
    check_app_syntax()
    tpl = load("app", "karte.template.html")
    html = tpl.replace("__LEAFLET_CSS__", load("app", "vendor", "leaflet.css"))
    html = html.replace("__LEAFLET_JS__", load("app", "vendor", "leaflet.js"))
    logo_svg = ""
    if logo and os.path.exists(os.path.join(BASE, "app", "vendor", "logo.svg")):
        logo_svg = load("app", "vendor", "logo.svg")   # nur lokal vorhanden, gitignored
    html = html.replace("__LOGO_SVG__", logo_svg)
    html = html.replace("__PWA_HEAD__", pwa_head)
    html = html.replace("__DATA__", json.dumps(r, ensure_ascii=False, separators=(",", ":")))
    return html


# ---- PWA-Icons (rote Münze, ohne Zusatz-Bibliothek) -------------------------
import math
import struct
import zlib

RED, DARK, RED_HI, RED_LO, WHITE = (238, 0, 0), (26, 17, 16), (255, 96, 84), (176, 0, 0), (255, 255, 255)


def _png(size, pixel_fn):
    rows = b""
    for y in range(size):
        rows += b"\x00"
        for x in range(size):
            rows += bytes(pixel_fn(x, y, size))

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def _coin_px(x, y, size):
    """Rote Münze auf transparentem Grund (purpose: any)."""
    cx = cy = size / 2.0
    r = math.hypot(x - cx + 0.5, y - cy + 0.5) / (size / 2.0)
    if r > 1.0:
        return (0, 0, 0, 0)
    aa = min(1.0, (1.0 - r) * size * 0.5)
    if r > 0.92:
        c = DARK
    elif r > 0.82:
        c = RED_LO
    elif r > 0.60:
        c = RED
    elif r > 0.52:
        c = RED_LO
    else:
        t = max(0.0, 1.0 - ((x / size) + (y / size)))
        c = tuple(int(RED[i] + (RED_HI[i] - RED[i]) * t) for i in range(3))
    return (c[0], c[1], c[2], int(255 * aa))


def _filled_px(x, y, size):
    """Roter Vollhintergrund mit weißer Münze in der Mitte (maskable + apple-touch)."""
    cx = cy = size / 2.0
    cr = size * 0.34
    d = math.hypot(x - cx, y - cy)
    if d < cr * 0.78:
        c = WHITE
    elif d < cr * 0.88:
        c = RED
    elif d <= cr:
        c = WHITE
    else:
        c = RED
    return (c[0], c[1], c[2], 255)


def build_webapp(r):
    web = os.path.join(BASE, "webapp")
    icons = os.path.join(web, "icons")
    os.makedirs(icons, exist_ok=True)

    with open(os.path.join(web, "index.html"), "w") as f:
        f.write(make_html(r, logo=False, pwa_head=PWA_HEAD))

    manifest = {
        "name": "Sparmania Route", "short_name": "Sparmania",
        "description": "Fahrrad-Routenplaner für die Sparmania-Münzjagd (inoffiziell)",
        "start_url": ".", "scope": ".", "display": "standalone",
        "orientation": "portrait", "background_color": "#FFFFFF", "theme_color": "#EE0000",
        "icons": [
            {"src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "icons/icon-512-maskable.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    with open(os.path.join(web, "manifest.webmanifest"), "w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    sw = (
        'var CACHE="sparmania-shell-v1";\n'
        'self.addEventListener("install",function(e){self.skipWaiting();});\n'
        'self.addEventListener("activate",function(e){e.waitUntil(caches.keys().then(function(ks){'
        'return Promise.all(ks.map(function(k){if(k!==CACHE)return caches.delete(k);}));})'
        '.then(function(){return self.clients.claim();}));});\n'
        'self.addEventListener("fetch",function(e){var req=e.request;if(req.method!=="GET")return;'
        'var url=new URL(req.url);if(url.origin!==location.origin)return;'  # Kacheln/OSRM/Sparkasse direkt aus dem Netz
        'e.respondWith(fetch(req).then(function(res){var copy=res.clone();'
        'caches.open(CACHE).then(function(c){c.put(req,copy);});return res;})'
        '.catch(function(){return caches.match(req).then(function(m){return m||caches.match("./index.html");});}));});\n'
    )
    with open(os.path.join(web, "sw.js"), "w") as f:
        f.write(sw)

    for name, size, fn in [
        ("icon-192.png", 192, _coin_px), ("icon-512.png", 512, _coin_px),
        ("icon-512-maskable.png", 512, _filled_px), ("apple-touch-icon.png", 180, _filled_px),
    ]:
        with open(os.path.join(icons, name), "wb") as f:
            f.write(_png(size, fn))

    total = sum(os.path.getsize(os.path.join(web, p)) for p in ("index.html", "manifest.webmanifest", "sw.js"))
    print(f"-> webapp/ (index+manifest+sw {total // 1024} KB, 4 Icons)")


def main():
    r = json.loads(load("data", "route.json"))
    write("sparmania-route.gpx", make_gpx(r))
    write("sparmania-route.kml", make_kml_route(r))
    write("alle-muenzen.kml", make_kml_all(r))
    write("sparmania-karte.html", make_html(r, logo=False))  # APK-Asset & Browser-Datei (ohne Logo)
    build_webapp(r)                                           # öffentliche PWA (ohne Logo)


if __name__ == "__main__":
    main()
