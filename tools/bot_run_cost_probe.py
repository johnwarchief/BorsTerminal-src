#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اندازۀ واقعیِ هزینهٔ یکِ نشستِ ربات رویِ market.dbِ خودِ ریپو.

چرا این فایل هست: عددِ «ربات کار می‌کند» بدونِ هزینهٔ دیواریِ یکِ فشارِ دکمه
بی‌معنی است. دورِ پیشین همین سنجه ۱۲۹,۶۱۳ ردیف و ۱٬۴۵۷ ثانیه نشان داد؛ ازِ آن
زمان به این‌جا آمده تا مالک و هر ایجنتِ دیگری بتواند دوباره اندازه بگیرد.

نشتِ بی‌داده هم همین‌جا دیده می‌شود: داور باید به‌ازایِ هر فشارِ دکمه **یک‌بار**
صدا زده شود، و `_bars` فقط ردیفِ همان نشستِ بسته‌شدۀ نمادهایِ اقدام‌پذیر را بخواهد.

اجرا:  python tools/bot_run_cost_probe.py [--chain f_roobi] [--presses 3]
خروجی: `_audit/bot_run_cost.json` (+ سطرهایِ زنده رویِ stdout)
"""
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, ROOT)
os.environ.setdefault("BORS_CODAL_OFFLINE", "1")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import api.bot as B                                    # noqa: E402

OUT = os.path.join(ROOT, "_audit", "bot_run_cost.json")
chain, presses = [], 3
if "--chain" in sys.argv:
    chain = [c for c in sys.argv[sys.argv.index("--chain") + 1].split(",") if c]
if "--presses" in sys.argv:
    presses = int(sys.argv[sys.argv.index("--presses") + 1])

led = B.default_ledger()
cfg = dict(B.DEFAULTS)
cfg["enabled"] = True
cfg["chain"] = chain
prev_state = led.load_state(B.MEMBERSHIP_KEY) or {}

# شمارشِ صداهایِ داور: همان چیزی که دورِ پیشین ۱۵۶ تا در ۴۰۰ ردیف بود
_real_judge = B._judge


def counting_judge(c):
    inner = _real_judge(c)
    calls = []

    def judge(session):
        t0 = time.time()
        got = inner(session)
        calls.append({"session": str(session), "ms": int((time.time() - t0) * 1000),
                      "in": sum(1 for v in (got or {}).values() if v == "in")})
        judge.calls = calls
        return got
    return judge


B._judge = counting_judge
rows = []
try:
    for i in range(presses):
        t = time.time()
        day = B._board_day()
        r = B._step(cfg, led, int(day))
        wall = round(time.time() - t, 2)
        calls = getattr(getattr(B._judge(cfg), "calls", None), "__iter__", None)
        j = led.load_state(B.MEMBERSHIP_KEY) or {}
        pend = led.load_state("paper_pending") or {}
        row = {
            "press": i + 1, "session": str(day), "wall_s": wall,
            "bars": r and r["bars"], "symbols_in": r and r["symbols_in"],
            "unpriced": r and len(r["unpriced"] or []),
            "signals": r and sum(d["signals"] for d in r["decisions"]),
            "dispatched": r and sum(d["dispatched"] for d in r["decisions"]),
            "expired": r and len(r["expired"] or []),
            "inner_ms": r and r["ms"],
            "verdict_saved": bool(j.get("session")),
            "pending_drafts": len(pend.get("drafts") or []),
        }
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    judge_calls = getattr(B._judge(cfg), "calls", None)
finally:
    B._judge = _real_judge
    led.save_state(B.MEMBERSHIP_KEY, prev_state)

payload = {"chain": chain, "presses": rows,
           "note": "wall_s = زمانِ واقعیِ یکِ فشارِ دکمه; inner_ms = حلقۀ ربات بی‌داوری"}
io_dir = os.path.dirname(OUT)
os.makedirs(io_dir, exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=1)
print("wrote", OUT)
