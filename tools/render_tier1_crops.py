#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render one tight crop per featured pattern of a tier for the Phase D visual audit."""
from __future__ import annotations

import argparse
import csv
import json
import os
from PIL import Image, ImageDraw, ImageFont

SRC = "D:/BorsTerminal-data/phase-d/pattern-audit.json"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "_audit", "rebuild", "technical-phase-d", "2026-11-06")
W, H = 1000, 620
BG = (15, 18, 22)
FG = (220, 225, 232)
DIM = (130, 140, 150)
UP = (45, 150, 95)
DOWN = (190, 70, 85)
GOLD = (210, 180, 90)


def featured(patterns):
    out = []
    for family in ("reversal", "continuation"):
        fam = [p for p in patterns if p.get("family") == family]
        forming = sorted([p for p in fam if p.get("status") == "forming"],
                         key=lambda p: p["anchor"]["index"])[-1:]
        confirmed = sorted([p for p in fam if p.get("status") == "confirmed"],
                           key=lambda p: p["anchor"]["index"])[-1:]
        out.extend(forming + confirmed)
    return out


def color(p):
    return {"bullish": (75, 160, 115), "bearish": (200, 95, 115),
            "neutral": GOLD}.get(p.get("direction"), GOLD)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", type=int, default=1, choices=(1, 2))
    args = parser.parse_args()
    tier = args.tier
    crops = os.path.join(OUT, f"tier{tier}")
    data = json.load(open(SRC, encoding="utf-8"))
    os.makedirs(crops, exist_ok=True)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 18)
        small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 14)
    except Exception:
        font = small = ImageFont.load_default()
    rows = []
    for item in data:
        if "error" in item:
            continue
        symbol, tf = item["symbol"], item["timeframe"]
        candles = item["candles"]
        # Default chart shows tier-1 only; tier-2 is selected separately when the
        # toggle is on. Mirroring that order avoids tier-2 displacing a tier-1 shape.
        pool = item["patterns"] if tier == 2 else [
            p for p in item["patterns"] if int(p.get("tier", 1)) != 2]
        for p in featured(pool):
            if int(p.get("tier", 1)) != tier:
                continue
            idxs = [p["anchor"]["index"]] + [x["index"] for x in p.get("points", [])]
            lo, hi = min(idxs), max(idxs)
            start = max(0, lo - 25)
            end = min(len(candles) - 1, hi + 18)
            if end - start < 50:
                end = min(len(candles) - 1, start + 50)
            view = candles[start:end + 1]
            if not view:
                continue
            lo_p = min(c["low"] for c in view)
            hi_p = max(c["high"] for c in view)
            pad = (hi_p - lo_p) * 0.08 or 1
            lo_p -= pad
            hi_p += pad
            img = Image.new("RGB", (W, H), BG)
            d = ImageDraw.Draw(img)
            left, right, top, bottom = 55, 35, 55, 45
            step = (W - left - right) / max(1, len(view))

            def x_of(i):
                return left + (i - start) * step + step / 2

            def y_of(price):
                return top + (hi_p - price) / (hi_p - lo_p) * (H - top - bottom)

            for k in range(5):
                price = lo_p + (hi_p - lo_p) * k / 4
                y = y_of(price)
                d.line([(left, y), (W - right, y)], fill=(35, 40, 48), width=1)
                d.text((6, y - 8), f"{price:,.0f}", fill=DIM, font=small)
            body = max(1, step * 0.6)
            for i, c in enumerate(view):
                x = x_of(start + i)
                col = UP if c["close"] >= c["open"] else DOWN
                d.line([(x, y_of(c["high"])), (x, y_of(c["low"]))], fill=col, width=1)
                y1, y2 = y_of(max(c["open"], c["close"])), y_of(min(c["open"], c["close"]))
                d.rectangle([x - body / 2, y1, x + body / 2, max(y2, y1 + 1)], fill=col)
            col = color(p)
            for line in (p.get("upper"), p.get("lower"), p.get("neckline")):
                if not line:
                    continue
                d.line([(x_of(line["from"]["index"]), y_of(line["from"]["price"])),
                        (x_of(line["to"]["index"]), y_of(line["to"]["price"]))], fill=col, width=2)
            for point in p.get("points", []):
                x, y = x_of(point["index"]), y_of(point["price"])
                d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=col)
            anchor = p["anchor"]
            x, y = x_of(anchor["index"]), y_of(anchor["price"])
            label = f'{p["kind"]}  T{tier}  {p.get("status","")}  Q{round(p.get("quality",0))}'
            tx, ty = min(max(x + 10, 5), W - 360), min(max(y - 30, 5), H - 30)
            d.rectangle([tx - 4, ty - 3, tx + 350, ty + 24], fill=(25, 30, 36))
            d.text((tx, ty), label, fill=col, font=font)
            d.text((left, 12), f"{symbol} {tf}  view {start}..{end}", fill=FG, font=font)
            name = f'{symbol}-{tf}-{p["kind"]}-{anchor["index"]}.png'
            img.save(os.path.join(crops, name))
            rows.append({"symbol": symbol, "timeframe": tf, "kind": p["kind"],
                         "status": p.get("status"), "quality": round(p.get("quality", 0)),
                         "anchor_index": anchor["index"], "image": name})
    with open(os.path.join(OUT, f"tier{tier}.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["symbol"])
        w.writeheader()
        w.writerows(rows)
    print(f"tier{tier} crops", len(rows))


if __name__ == "__main__":
    main()
