#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اندازۀ واقعیِ پاسخِ /api/funnel — تصمیمِ پختِ آفلاین باید با عدد گرفته شود.

چرا: غربالگری رویِ گوشی هیچ‌وقت پخت نمی‌شد (نه در resolver، نه در سازندهٔ بستۀ
داده)، پس صفحۀ غربالگری ۴۰۴ می‌گیرد. پیش از افزودنِ کلیدِ تازه باید دانست یک
پاسخِ canonical چقدر جا می‌گیرد؛ بستۀ موبایل داخلِ APK است و هر مگابایتِ خامِ
افزوده شده رویِ sizesِ اعلام‌شدۀ ریلیز اثر می‌گذارد.

اجرا (بازارِ محلی لازم نیست؛ بی‌شبکه):
    BORS_CODAL_OFFLINE=1 BORS_NO_FETCH_LOOPS=1 python tools/mobile_funnel_offline_probe.py
"""
from __future__ import annotations

import gzip
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("BORS_CODAL_OFFLINE", "1")
os.environ.setdefault("BORS_NO_FETCH_LOOPS", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from fastapi.testclient import TestClient  # noqa: E402
import app as appmod  # noqa: E402

CASES = [
    ("trend", "and", "standard", True, ""),
    ("swing", "and", "standard", True, ""),
    ("hourglass", "and", "standard", True, ""),
    ("trend", "or", "standard", True, ""),
    ("trend", "and", "strict", True, ""),
    ("custom", "and", "standard", True, ""),
]


def size_of(text: str) -> tuple[int, int]:
    return len(text.encode("utf-8")), len(gzip.compress(text.encode("utf-8"), 5))


out = {"cases": [], "top_keys_seen": None}
with TestClient(appmod.app, base_url="http://127.0.0.1:8001") as client:
    for preset, logic, fund_mode, drop_suffix, chain in CASES:
        q = ("preset=%s&logic=%s&fund_mode=%s&drop_suffix=%s&chain=%s"
             % (preset, logic, fund_mode, str(drop_suffix).lower(), chain))
        r = client.get("/api/funnel?" + q)
        rec = {"preset": preset, "logic": logic, "fund_mode": fund_mode,
               "chain": chain, "http": r.status_code}
        if r.status_code != 200:
            rec["error"] = str(r.text[:160])
            out["cases"].append(rec)
            continue
        raw = r.text
        n, gz = size_of(raw)
        payload = json.loads(raw)
        if out["top_keys_seen"] is None:
            out["top_keys_seen"] = sorted(payload.keys())
        sm = payload.get("status_matrix") or {}
        rows = payload.get("rows") or payload.get("data") or []
        rec.update({"raw_bytes": n, "gz_bytes": gz, "top_keys": sorted(payload.keys()),
                    "status_matrix_symbols": len(sm), "list_rows": len(rows),
                    "universe": payload.get("universe"),
                    "engine_version": payload.get("engine_version"),
                    "ruleset_version": payload.get("ruleset_version")})
        per = {}
        for k, v in payload.items():
            try:
                per[k] = size_of(json.dumps(v, ensure_ascii=False,
                                            separators=(",", ":")))[0]
            except TypeError:
                per[k] = -1
        rec["bytes_per_top_key"] = dict(sorted(per.items(), key=lambda kv: -kv[1])[:8])
        out["cases"].append(rec)

json.dump(out, io.open(os.path.join(ROOT, "_audit", "mobile_funnel_size.json"),
                       "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for c in out["cases"]:
    if c.get("http") != 200:
        print("%-9s %-4s %-8s chain=%-14s HTTP %s %s"
              % (c["preset"], c["logic"], c["fund_mode"], c["chain"] or "-",
                 c["http"], c.get("error", "")))
        continue
    print("%-9s %-4s %-8s chain=%-14s raw=%9d gz=%8d matrix=%5d rows=%5d"
          % (c["preset"], c["logic"], c["fund_mode"], c["chain"] or "-",
             c["raw_bytes"], c["gz_bytes"], c["status_matrix_symbols"], c["list_rows"]))
print("\ntop-level keys of a canonical funnel payload:")
print("  " + ", ".join(out["top_keys_seen"] or []))
print("wrote _audit/mobile_funnel_size.json")
