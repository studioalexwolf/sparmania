#!/usr/bin/env python3
"""Erzeugt das App-Icon (goldene Münze) als PNG in allen Dichten — ohne Abhängigkeiten."""
import math
import os
import struct
import zlib

BASE = os.path.dirname(os.path.abspath(__file__))
DENSITIES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}

DUNKEL = (26, 17, 16)     # Sparkasse-Schwarz (Prägerand)
GOLD = (238, 0, 0)        # Sparkasse-Rot (Münzfläche)
GOLD_HELL = (255, 96, 84)
GOLD_DUNKEL = (176, 0, 0)


def px(x, y, size):
    """Farbe+Alpha für Pixel (x,y) einer Münze mit Prägering."""
    cx = cy = size / 2.0
    r = math.hypot(x - cx + 0.5, y - cy + 0.5) / (size / 2.0)  # 0..1
    if r > 1.0:
        return (0, 0, 0, 0)
    aa = min(1.0, (1.0 - r) * size * 0.5)  # Kantenglättung außen
    if r > 0.92:
        c = DUNKEL          # dunkler Außenring
    elif r > 0.82:
        c = GOLD_DUNKEL     # Prägerand
    elif r > 0.60:
        c = GOLD
    elif r > 0.52:
        c = GOLD_DUNKEL     # innerer Ring
    else:
        # leichter Verlauf von hell (oben links) nach gold
        t = max(0.0, 1.0 - ((x / size) + (y / size)))
        c = tuple(int(GOLD[i] + (GOLD_HELL[i] - GOLD[i]) * t) for i in range(3))
    return (c[0], c[1], c[2], int(255 * aa))


def make_png(size):
    rows = b""
    for y in range(size):
        row = b"\x00"
        for x in range(size):
            row += bytes(px(x, y, size))
        rows += row
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


for name, size in DENSITIES.items():
    d = os.path.join(BASE, "res", f"mipmap-{name}")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "ic_launcher.png")
    with open(path, "wb") as f:
        f.write(make_png(size))
    print(f"-> res/mipmap-{name}/ic_launcher.png ({size}px)")
