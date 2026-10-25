# -*- coding: utf-8 -*-
"""wm_calendar.py — historical bridge for the non-comparable W/M keys.

Round 32D rebuilt the weekly/monthly bar of every non-comparable key from the
reference's own daily type7 bars.  This module loads that frozen pack so the
FTS weekly/monthly analysis sees the same bar as Rahavard for the keys where
the product's daily history cannot build it.

It is a **historical bridge**, not a runtime dependency: no network, no
subscription call.  Keys absent from the pack fall back to the product's own
resample.  The pack carries only the 5,635 W/M bars (no daily series).

Week keys are the Saturday-anchored week index used by the Round 32 audit;
month keys are Jalali months (the market calendar and the reference calendar).
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import os
import threading

ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_VERSION = "ra365-r32d"
DEFAULT_DIR = os.path.join(ROOT, "data", "ra365_calendar", DEFAULT_VERSION)


class CalendarPackError(RuntimeError):
    pass


# jalaali-js algorithm; the same conversion as frontend/src/shared/lib/jalaliDate.ts
# and tools/ra_parity.py, which validated it against Rahavard's own jalali column.
_GDM = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)


def g2j(gy, gm, gd):
    gy2 = gy + 1 if gm > 2 else gy
    days = (355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100
            + (gy2 + 399) // 400 + gd + _GDM[gm - 1])
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return int(jy), int(jm), int(jd)


def month_key(date_str):
    d = dt.date.fromisoformat(str(date_str)[:10])
    jy, jm, _ = g2j(d.year, d.month, d.day)
    return jy * 12 + (jm - 1)


def week_key(date_str):
    d = dt.date.fromisoformat(str(date_str)[:10])
    day = (d - dt.date(1970, 1, 1)).days
    return (day - 2) // 7


def _norm(symbol):
    return str(symbol or "").strip().replace("\u064A", "\u06CC").replace(
        "\u0643", "\u06A9")


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Pack:
    def __init__(self, directory):
        self.directory = directory
        mpath = os.path.join(directory, "manifest.json")
        if not os.path.exists(mpath):
            raise CalendarPackError("manifest missing: %s" % mpath)
        with open(mpath, encoding="utf-8") as fh:
            self.manifest = json.load(fh)
        files = self.manifest.get("files") or {}
        name = files.get("bars") or "wm_calendar_bars.ndjson.gz"
        path = name if os.path.isabs(name) else os.path.join(directory, name)
        if not os.path.exists(path):
            raise CalendarPackError("bars missing: %s" % path)
        expected = (self.manifest.get("file_sha256") or {}).get("bars")
        if expected and _sha256(path) != expected:
            raise CalendarPackError("calendar bars hash mismatch: %s" % path)
        self.version = self.manifest.get("version") or DEFAULT_VERSION
        self.rows = {}
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                if r.get("unavailable"):
                    continue
                r["_key"] = (r.get("symbol"), r.get("timeframe"), int(r.get("key")))
                self.rows[r["_key"]] = r
        self.index = {}
        for r in self.rows.values():
            self.index[(_norm(r.get("symbol")), r.get("timeframe"), int(r.get("key")))] = r

    def bar(self, symbol, timeframe, key):
        row = self.index.get((_norm(symbol), timeframe, int(key)))
        if not row:
            return None
        out = {"time": row.get("date_to"),
               "open": row.get("open"), "high": row.get("high"),
               "low": row.get("low"), "close": row.get("close")}
        if row.get("volume") is not None:
            out["volume"] = float(row["volume"])
        return out


_LOCK = threading.Lock()
_CACHE = {}


def pack_dir():
    if os.environ.get("BORS_WM_CALENDAR_DISABLE", "").strip().lower() in (
            "1", "true", "yes", "on"):
        return None
    return os.environ.get("BORS_WM_CALENDAR_DIR") or DEFAULT_DIR


def load_pack(directory=None):
    d = directory or pack_dir()
    if not d:
        return None
    if not os.path.exists(os.path.join(d, "manifest.json")):
        return None
    try:
        stamp = tuple(os.path.getmtime(os.path.join(d, f))
                      for f in os.listdir(d) if f.endswith((".json", ".gz")))
    except OSError:
        stamp = ()
    with _LOCK:
        cached = _CACHE.get(d)
        if cached and cached[0] == stamp:
            if isinstance(cached[1], CalendarPackError):
                raise cached[1]
            return cached[1]
        try:
            pack = Pack(d)
        except CalendarPackError as e:
            _CACHE[d] = (stamp, e)
            raise
        _CACHE[d] = (stamp, pack)
        return pack


def get_pack():
    try:
        return load_pack()
    except CalendarPackError:
        return None


def bar(symbol, timeframe, key):
    pack = get_pack()
    if pack is None:
        return None
    try:
        return pack.bar(symbol, timeframe, key)
    except (TypeError, ValueError):
        return None


def capability(symbol=None):
    pack = get_pack()
    if pack is None:
        return {"enabled": False, "version": None, "covered": False}
    covered = 0
    if symbol:
        sym = _norm(symbol)
        covered = sum(1 for k in pack.index if k[0] == sym)
    return {"enabled": True, "version": pack.version, "covered": covered > 0,
            "bars": len(pack.rows), "symbol_bars": covered}
