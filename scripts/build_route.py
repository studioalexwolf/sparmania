#!/usr/bin/env python3
"""Sparmania Routenplaner.

Liest data/coins-raw.json, rechnet die optimierte Fahrrad-Rundroute ab dem
Startpunkt und schreibt data/route.json. Danach erzeugt scripts/make_deliverables.py
GPX, KML und die Karten-App daraus.

Aufruf:  python3 scripts/build_route.py
"""
import json
import math
import os
import subprocess
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

START = {"lat": 51.34445, "lon": 12.36019, "title": "Start/Ziel: Hinrichsenstraße 21"}
RADIUS_KM = 10.0      # Münzen bis zu dieser Luftlinie vom Start kommen in die Route
ROAD_FACTOR = 1.35    # Luftlinie -> realistische Fahrstrecke auf Straßen/Radwegen
CORE_KM = 3.0         # "Kern"-Zone (gelbe Marker, bestes km-pro-Münze-Verhältnis)


def haversine(a, b):
    R = 6371.0
    la1, lo1, la2, lo2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def classify(coins):
    now = datetime.now(timezone.utc).isoformat()
    active, future = [], []
    for c in coins:
        af, at = c.get("activeFrom"), c.get("activeTo")
        if af and af > now:
            future.append(c)
        elif at and at < now:
            continue  # abgelaufen
        else:
            active.append(c)
    return active, future


def tour_length(order, pts):
    total = haversine(pts[-1], pts[order[0]])  # Start -> erste Münze (Start ist pts[-1])
    for i in range(len(order) - 1):
        total += haversine(pts[order[i]], pts[order[i + 1]])
    total += haversine(pts[order[-1]], pts[-1])  # letzte Münze -> Start
    return total


def nearest_neighbor(pts):
    n = len(pts) - 1  # letzter Punkt ist der Start
    unvisited = set(range(n))
    order = []
    cur = pts[-1]
    while unvisited:
        nxt = min(unvisited, key=lambda i: haversine(cur, pts[i]))
        order.append(nxt)
        unvisited.discard(nxt)
        cur = pts[nxt]
    return order


def two_opt(order, pts):
    # Geschlossene Tour Start -> order -> Start; Start bleibt fixiert.
    path = [len(pts) - 1] + order + [len(pts) - 1]
    improved = True
    while improved:
        improved = False
        for i in range(1, len(path) - 2):
            for j in range(i + 1, len(path) - 1):
                a, b = path[i - 1], path[i]
                c, d = path[j], path[j + 1]
                delta = (haversine(pts[a], pts[c]) + haversine(pts[b], pts[d])
                         - haversine(pts[a], pts[b]) - haversine(pts[c], pts[d]))
                if delta < -1e-9:
                    path[i:j + 1] = reversed(path[i:j + 1])
                    improved = True
    return path[1:-1]


def or_opt(order, pts):
    # Verschiebt Segmente der Länge 1-3 an bessere Stellen.
    path = [len(pts) - 1] + order + [len(pts) - 1]
    improved = True
    while improved:
        improved = False
        for seglen in (1, 2, 3):
            i = 1
            while i < len(path) - seglen:
                seg = path[i:i + seglen]
                pre, post = path[i - 1], path[i + seglen]
                removed = (haversine(pts[pre], pts[seg[0]]) + haversine(pts[seg[-1]], pts[post])
                           - haversine(pts[pre], pts[post]))
                rest = path[:i] + path[i + seglen:]
                best_gain, best_k = 0.0, None
                for k in range(1, len(rest)):
                    a, b = rest[k - 1], rest[k]
                    added = (haversine(pts[a], pts[seg[0]]) + haversine(pts[seg[-1]], pts[b])
                             - haversine(pts[a], pts[b]))
                    gain = removed - added
                    if gain > best_gain + 1e-9:
                        best_gain, best_k = gain, k
                if best_k is not None:
                    path = rest[:best_k] + seg + rest[best_k:]
                    improved = True
                else:
                    i += 1
    return path[1:-1]


def dedupe(coins):
    # Die API liefert manche Standorte doppelt (gleiche id + Position,
    # unterschiedlicher Token). Für Route und Karte zählt der Standort.
    seen, uniq = set(), []
    for c in coins:
        key = (c["id"], c["lat"], c["lon"])
        if key in seen:
            continue
        seen.add(key)
        c["title"] = c.get("title") or c.get("place") or f"Münze {c['id']}"
        uniq.append(c)
    return uniq


def main():
    raw = json.load(open(os.path.join(BASE, "data", "coins-raw.json")))
    coins = dedupe(raw)
    print(f"{len(raw)} Einträge, {len(coins)} eindeutige Standorte")
    active, future = classify(coins)

    start_pt = (START["lat"], START["lon"])
    in_route = [c for c in active if haversine(start_pt, (c["lat"], c["lon"])) <= RADIUS_KM]
    outside = [c for c in active if c not in in_route]

    pts = [(c["lat"], c["lon"]) for c in in_route] + [start_pt]
    order = nearest_neighbor(pts)
    order = two_opt(order, pts)
    order = or_opt(order, pts)
    order = two_opt(order, pts)

    # Laufrichtung: dichter Kern zuerst. Richtung mit kleinerer mittlerer
    # Startdistanz über die ersten 40 Stopps gewinnt.
    def early_mean(o):
        return sum(haversine(start_pt, pts[i]) for i in o[:40]) / min(40, len(o))
    if early_mean(list(reversed(order))) < early_mean(order):
        order = list(reversed(order))

    total_air = tour_length(order, pts)

    route_coins, cum = [], 0.0
    prev = start_pt
    for num, idx in enumerate(order, 1):
        c = in_route[idx]
        p = (c["lat"], c["lon"])
        cum += haversine(prev, p)
        prev = p
        route_coins.append({
            "num": num, "id": c["id"], "title": c["title"], "place": c["place"],
            "lat": c["lat"], "lon": c["lon"],
            "kmFromStart": round(cum * ROAD_FACTOR, 1),
            "kmHome": round(haversine(p, start_pt) * ROAD_FACTOR, 1),
            "core": haversine(start_pt, p) <= CORE_KM,
        })

    generated = subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                               capture_output=True, text=True).stdout.strip()
    result = {
        "generatedAt": generated,
        "start": START,
        "roadFactor": ROAD_FACTOR,
        "radiusKm": RADIUS_KM,
        "totalKm": round(total_air * ROAD_FACTOR, 1),
        "route": route_coins,
        "outsideActive": [{"id": c["id"], "title": c["title"], "place": c["place"],
                           "lat": c["lat"], "lon": c["lon"]} for c in outside],
        "future": [{"id": c["id"], "title": c["title"], "place": c["place"],
                    "lat": c["lat"], "lon": c["lon"], "activeFrom": c["activeFrom"]}
                   for c in future],
    }
    out = os.path.join(BASE, "data", "route.json")
    json.dump(result, open(out, "w"), ensure_ascii=False, indent=1)

    core_n = sum(1 for c in route_coins if c["core"])
    print(f"Route: {len(route_coins)} Münzen, {result['totalKm']} km gesamt "
          f"(davon {core_n} im {CORE_KM:.0f}km-Kern)")
    for n in (30, 50, 80, len(route_coins)):
        if n <= len(route_coins):
            c = route_coins[n - 1]
            ride = round(c["kmFromStart"] + c["kmHome"], 1)
            print(f"  Abbruch nach {n:3d} Münzen: {ride:6.1f} km gefahren+heim "
                  f"({ride / n:.2f} km/Münze)")
    print(f"Außerhalb ({RADIUS_KM:.0f}km): {len(outside)} aktive Münzen | "
          f"Bald aktiv: {len(result['future'])}")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
