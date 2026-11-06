#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render one audit chart per symbol/timeframe with the featured patterns.

Featured = last forming + last confirmed per family (max 6), the same rule the
chart overlay uses. Each image shows the candles around the featured anchors,
the pattern boundaries/neckline and a compact label, so a human can judge fake
or missed patterns without reading the feed.
"""
from __future__ import annotations

import csv
import json
import os
from PIL import Image, ImageDraw, ImageFont

SRC = "D:/BorsTerminal-data/phase-d/pattern-audit.json"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "_audit", "rebuild", "technical-phase-d", "2026-11-06")
CHARTS = os.path.join(OUT, "charts")
W, H = 1600, 900
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
    data = json.load(open(SRC, encoding="utf-8"))
    os.makedirs(CHARTS, exist_ok=True)
    rows = []
    font_path = "C:/Windows/Fonts/arial.ttf"
    try:
        font = ImageFont.truetype(font_path, 17)
        small = ImageFont.truetype(font_path, 13)
    except Exception:
        font = small = ImageFont.load_default()
    for item in data:
        if "error" in item:
            continue
        symbol, tf = item["symbol"], item["timeframe"]
        candles = item["candles"]
        # The default chart keeps tier-2 hidden before featured selection.
        pats = featured([p for p in item["patterns"] if int(p.get("tier", 1)) != 2])
        if pats:
            lo = min(min(p["anchor"]["index"], p["points"][0]["index"]) for p in pats)
            hi = max(p["anchor"]["index"] for p in pats)
            start = max(0, lo - 25)
            end = min(len(candles) - 1, hi + 15)
            if end - start < 60:
                start = max(0, end - 60)
        else:
            end = len(candles) - 1
            start = max(0, end - 120)
        if end - start > 420:
            start = end - 420
        view = candles[start:end + 1]
        if not view:
            continue
        lo_p = min(c["low"] for c in view)
        hi_p = max(c["high"] for c in view)
        pad = (hi_p - lo_p) * 0.06 or 1
        lo_p -= pad
        hi_p += pad
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        left, right, top, bottom = 60, 40, 70, 60
        step = (W - left - right) / max(1, len(view))
        def x_of(index):
            return left + (index - start) * step + step / 2
        def y_of(price):
            return top + (hi_p - price) / (hi_p - lo_p) * (H - top - bottom)
        # grid / price labels
        for k in range(6):
            price = lo_p + (hi_p - lo_p) * k / 5
            y = y_of(price)
            d.line([(left, y), (W - right, y)], fill=(35, 40, 48), width=1)
            d.text((6, y - 8), f"{price:,.0f}", fill=DIM, font=small)
        # candles
        body = max(1, step * 0.62)
        for i, c in enumerate(view):
            idx = start + i
            x = x_of(idx)
            col = UP if c["close"] >= c["open"] else DOWN
            d.line([(x, y_of(c["high"])), (x, y_of(c["low"]))], fill=col, width=1)
            y1, y2 = y_of(max(c["open"], c["close"])), y_of(min(c["open"], c["close"]))
            d.rectangle([x - body / 2, y1, x + body / 2, max(y2, y1 + 1)], fill=col)
        # featured patterns
        for p in pats:
            col = color(p)
            for line in (p.get("upper"), p.get("lower"), p.get("neckline")):
                if not line:
                    continue
                x1, y1 = x_of(line["from"]["index"]), y_of(line["from"]["price"])
                x2, y2 = x_of(line["to"]["index"]), y_of(line["to"]["price"])
                d.line([(x1, y1), (x2, y2)], fill=col, width=2)
            for point in p.get("points", []):
                x, y = x_of(point["index"]), y_of(point["price"])
                d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=col)
            anchor = p["anchor"]
            x, y = x_of(anchor["index"]), y_of(anchor["price"])
            label = f'{p["kind"]}  T{p.get("tier", 1)}  {p.get("status", "")}  Q{round(p.get("quality", 0))}'
            tx = min(max(x + 8, 5), W - 380)
            ty = min(max(y - 28, 5), H - 30)
            d.rectangle([tx - 3, ty - 2, tx + 370, ty + 22], fill=(25, 30, 36))
            d.text((tx, ty), label, fill=col, font=font)
        d.text((left, 12), f"{symbol}  {tf}  bars={len(candles)}  featured={len(pats)}", fill=FG, font=font)
        d.text((left, H - 28), f"view {start}..{end}", fill=DIM, font=small)
        path = os.path.join(CHARTS, f"{symbol}-{tf}.png")
        img.save(path)
        for p in pats:
            rows.append({
                "symbol": symbol, "timeframe": tf, "kind": p["kind"],
                "tier": p.get("tier", 1), "status": p.get("status"),
                "direction": p.get("direction"), "quality": round(p.get("quality", 0)),
                "anchor_index": p["anchor"]["index"], "anchor_time": p["anchor"]["timestamp"],
                "points": len(p.get("points", [])), "chart": path,
            })
        print(symbol, tf, "featured", len(pats), "view", start, end)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "featured.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["symbol"])
        w.writeheader()
        w.writerows(rows)
    print("charts", len(os.listdir(CHARTS)), "rows", len(rows))


if __name__ == "__main__":
    main()
