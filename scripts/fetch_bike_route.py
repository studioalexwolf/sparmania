#!/usr/bin/env python3
"""Stufe 3: echtes Fahrrad-Routing via OSRM (routing.openstreetmap.de, Profil bike).

Liest data/route.json (Luftlinien-optimiert aus build_route.py), holt die reale
Radweg-Distanzmatrix, re-optimiert die Reihenfolge darauf und speichert die
echte Routen-Geometrie plus reale km-Angaben zurück nach data/route.json.

Aufruf:  python3 scripts/fetch_bike_route.py
"""
import json
import math
import os
import subprocess
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OSRM = "https://routing.openstreetmap.de/routed-bike"
MAX_TABLE = 100          # Koordinaten-Limit des Table-Service
CHUNK = 24               # Legs pro Route-Request (25 Punkte)
SIMPLIFY_EPS = 0.00008   # ~9 m Douglas-Peucker-Toleranz für die Übersichts-Geometrie


def curl_json(url):
    out = subprocess.run(["curl", "-sL", "--max-time", "120",
                          "-A", "sparmania-routenplaner", url],
                         capture_output=True, text=True).stdout
    return json.loads(out)


def coord_str(pts):
    return ";".join(f"{lon:.6f},{lat:.6f}" for lon, lat in pts)


def haversine_m(a, b):
    R = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, [a[1], a[0], b[1], b[0]])
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def fetch_matrix(pts):
    """Volle NxN-Distanz/Dauer-Matrix, in Blockpaaren unter dem 100er-Limit.
    Wird in data/bike-matrix.json gecacht (Schonung des freien OSRM-Servers)."""
    n = len(pts)
    cache_path = os.path.join(BASE, "data", "bike-matrix.json")
    if os.path.exists(cache_path):
        try:
            c = json.load(open(cache_path))
            if c.get("coords") == [list(p) for p in pts]:
                print("  (aus Cache data/bike-matrix.json)")
                return c["dist"], c["dur"]
        except (ValueError, KeyError):
            pass
    nb = math.ceil(n / (MAX_TABLE // 2))          # Blockanzahl, Paar <= Limit
    size = math.ceil(n / nb)
    blocks = [list(range(i, min(i + size, n))) for i in range(0, n, size)]
    dist = [[None] * n for _ in range(n)]
    dur = [[None] * n for _ in range(n)]
    pairs = [(a, b) for i, a in enumerate(blocks) for b in blocks[i:]]
    for k, (ba, bb) in enumerate(pairs, 1):
        idx = ba if ba == bb else ba + bb
        url = f"{OSRM}/table/v1/bike/{coord_str([pts[i] for i in idx])}?annotations=distance,duration"
        d = curl_json(url)
        if d.get("code") != "Ok":
            raise RuntimeError(f"Table-Request {k}: {d.get('code')} {d.get('message')}")
        for r, i in enumerate(idx):
            for c, j in enumerate(idx):
                dist[i][j] = d["distances"][r][c]
                dur[i][j] = d["durations"][r][c]
        print(f"  Matrix-Block {k}/{len(pairs)} ok")
        time.sleep(1)
    # unroutbare Zellen: Luftlinie * 1.5 als Strafe
    for i in range(n):
        for j in range(n):
            if dist[i][j] is None:
                dist[i][j] = haversine_m(pts[i], pts[j]) * 1.5
                dur[i][j] = dist[i][j] / 4.2
    json.dump({"coords": [list(p) for p in pts], "dist": dist, "dur": dur},
              open(cache_path, "w"))
    return dist, dur


def tour_len(order, D):
    t = D[0][order[0]]
    for i in range(len(order) - 1):
        t += D[order[i]][order[i + 1]]
    return t + D[order[-1]][0]


def optimize(D, n):
    """NN + 2-opt + Or-opt auf symmetrisierter Matrix; Knoten 0 = Start, fixiert."""
    S = [[(D[i][j] + D[j][i]) / 2 for j in range(n)] for i in range(n)]
    unvisited, order, cur = set(range(1, n)), [], 0
    while unvisited:
        nxt = min(unvisited, key=lambda j: S[cur][j])
        order.append(nxt); unvisited.discard(nxt); cur = nxt

    def two_opt(path):
        improved = True
        while improved:
            improved = False
            for i in range(1, len(path) - 2):
                for j in range(i + 1, len(path) - 1):
                    a, b, c, d = path[i - 1], path[i], path[j], path[j + 1]
                    if S[a][c] + S[b][d] < S[a][b] + S[c][d] - 1e-9:
                        path[i:j + 1] = reversed(path[i:j + 1]); improved = True
        return path

    def or_opt(path):
        improved = True
        while improved:
            improved = False
            for seglen in (1, 2, 3):
                i = 1
                while i < len(path) - seglen:
                    seg = path[i:i + seglen]
                    pre, post = path[i - 1], path[i + seglen]
                    removed = S[pre][seg[0]] + S[seg[-1]][post] - S[pre][post]
                    rest = path[:i] + path[i + seglen:]
                    best_gain, best_k = 1e-9, None
                    for k in range(1, len(rest)):
                        a, b = rest[k - 1], rest[k]
                        gain = removed - (S[a][seg[0]] + S[seg[-1]][b] - S[a][b])
                        if gain > best_gain:
                            best_gain, best_k = gain, k
                    if best_k is not None:
                        path[:] = rest[:best_k] + seg + rest[best_k:]; improved = True
                    else:
                        i += 1
        return path

    path = [0] + order + [0]
    path = or_opt(two_opt(path))
    path = two_opt(path)
    return path[1:-1]


def fetch_geometry(pts_ordered):
    """Route-Geometrie + reale Leg-Distanzen/-Dauern entlang der finalen Reihenfolge."""
    coords, leg_m, leg_s = [], [], []
    i = 0
    while i < len(pts_ordered) - 1:
        seg = pts_ordered[i:i + CHUNK + 1]
        url = (f"{OSRM}/route/v1/bike/{coord_str(seg)}"
               f"?overview=full&geometries=geojson&steps=false&continue_straight=false")
        d = curl_json(url)
        if d.get("code") != "Ok":
            raise RuntimeError(f"Route-Request ab Punkt {i}: {d.get('code')}")
        r = d["routes"][0]
        g = r["geometry"]["coordinates"]
        coords.extend(g if not coords else g[1:])
        for leg in r["legs"]:
            leg_m.append(leg["distance"]); leg_s.append(leg["duration"])
        print(f"  Geometrie {min(i + CHUNK, len(pts_ordered) - 1)}/{len(pts_ordered) - 1} Legs ok")
        i += CHUNK
        time.sleep(1)
    return coords, leg_m, leg_s


def simplify(coords, eps):
    """Iteratives Douglas-Peucker auf [lon,lat]-Liste."""
    if len(coords) < 3:
        return coords
    keep = [False] * len(coords)
    keep[0] = keep[-1] = True
    stack = [(0, len(coords) - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        ax, ay = coords[a]; bx, by = coords[b]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy)
        best_d, best_i = 0.0, None
        for i in range(a + 1, b):
            if norm < 1e-12:
                # degeneriertes Segment (geschlossener Rundkurs: Start == Ende):
                # Abstand zum Punkt statt zur Linie
                d = math.hypot(coords[i][0] - ax, coords[i][1] - ay)
            else:
                d = abs(dx * (ay - coords[i][1]) - dy * (ax - coords[i][0])) / norm
            if d > best_d:
                best_d, best_i = d, i
        if best_d > eps:
            keep[best_i] = True
            stack.append((a, best_i)); stack.append((best_i, b))
    return [c for c, k in zip(coords, keep) if k]


def main():
    r = json.load(open(os.path.join(BASE, "data", "route.json")))
    coins = r["route"]
    pts = [(r["start"]["lon"], r["start"]["lat"])] + [(c["lon"], c["lat"]) for c in coins]
    n = len(pts)

    print(f"[1/3] Fahrrad-Distanzmatrix {n}x{n}")
    dist, dur = fetch_matrix(pts)

    print("[2/3] Reihenfolge auf Radweg-Distanzen optimieren")
    old_order = list(range(1, n))
    new_order = optimize(dist, n)
    old_km = tour_len(old_order, dist) / 1000
    new_km = tour_len(new_order, dist) / 1000
    print(f"  Luftlinien-Reihenfolge auf echten Wegen: {old_km:.1f} km")
    print(f"  Radweg-optimierte Reihenfolge:           {new_km:.1f} km")
    if new_km >= old_km:
        new_order = old_order
        print("  (keine Verbesserung, alte Reihenfolge bleibt)")

    # Laufrichtung: dichter Kern zuerst, damit früher Abbruch billig bleibt
    def early_mean(o):
        return sum(dist[0][i] for i in o[:40]) / min(40, len(o))
    if early_mean(list(reversed(new_order))) < early_mean(new_order):
        new_order = list(reversed(new_order))
        print("  Laufrichtung gedreht (Kern zuerst)")

    print("[3/3] Routen-Geometrie holen")
    pts_ordered = [pts[0]] + [pts[i] for i in new_order] + [pts[0]]
    coords, leg_m, leg_s = fetch_geometry(pts_ordered)

    new_route, cum_m, cum_s = [], 0.0, 0.0
    for num, idx in enumerate(new_order, 1):
        c = dict(coins[idx - 1])
        cum_m += leg_m[num - 1]; cum_s += leg_s[num - 1]
        c.update(num=num,
                 kmFromStart=round(cum_m / 1000, 1),
                 kmHome=round(dist[idx][0] / 1000, 1),
                 minFromStart=round(cum_s / 60))
        new_route.append(c)

    r.update(route=new_route,
             totalKm=round(sum(leg_m) / 1000, 1),
             totalMin=round(sum(leg_s) / 60),
             bikeRouting=True,
             geometry=[[round(lat, 5), round(lon, 5)]
                       for lon, lat in simplify(coords, SIMPLIFY_EPS)])
    r.pop("roadFactor", None)
    json.dump(r, open(os.path.join(BASE, "data", "route.json"), "w"),
              ensure_ascii=False, indent=1)
    print(f"Rundkurs real: {r['totalKm']} km, ~{r['totalMin']} min reine Fahrzeit, "
          f"{len(r['geometry'])} Geometrie-Punkte -> data/route.json")


if __name__ == "__main__":
    main()
