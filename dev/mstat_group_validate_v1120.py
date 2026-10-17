#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mstat_group_validate_v1120 — گروه/تبِ نامعتبر نباید «صفرِ معتبر» بدهد.

نقصِ زندۀ 2026-10-17: `thermometer?group=eq` ⇒ `status:"ok"` با ۰/۰/۰، و
`clientsplit?tab=<بیگانه>` بی‌صدا به «کل بازار» تبدیل می‌شد. این سنجه همان را
قفل می‌کند — و مهم‌تر: **صفرِ واقعی** (دستۀ معتبری که امروز معامله‌ای ندارد)
باید همچنان ۲۰۰ بماند؛ وگرنه «رفعِ نقص» به «ردِّ همهٔ صفرها» تبدیل می‌شود.

بی‌نیاز ازِ market.db: `_mstat_call` جای‌گذاری می‌شود تا دروازۀ HTTP و داوریِ
پارامتر سنجیده شود، نه موتورِ محاسبه (مotor در `dev/mstat_local_v975.py` و
`dev/board_freshness…` پوشش دارد). کنترلِ منفیِ آخر ثابت می‌کند سنجه کور نیست.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS = FAIL = 0


def ck(cond, label, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("ok   " + label)
    else:
        FAIL += 1
        print("FAIL " + label + "  -> " + str(detail)[:200])


import api.market_status as MS                                      # noqa: E402
import mstat_engine as _mstat                                        # noqa: E402
from fastapi import FastAPI                                          # noqa: E402
from fastapi.testclient import TestClient                            # noqa: E402

CALLED = []


def _stub_engine(name):
    def fn(*args, **kw):
        # امضاهایِ موتور متفاوت است: group/tab همیشه اولین آرگومانِ کلیدواژه‌ای
        # یا موقعیتی‌اش همین‌جا خوانده می‌شود
        arg = None
        if kw:
            arg = list(kw.values())[0]
        elif args:
            arg = args[0]
        CALLED.append((name, arg))
        out = {"status": "ok", "panel": name, "group": arg}
        if name == "thermometer":
            # `silver_fund` امروز واقعاً بی‌معامله است ⇒ صفرِ **مشروع**
            zero = 0 if str(arg) == "silver_fund" else 7
            out.update({"positive": zero, "negative": zero, "zero": 0,
                        "not_traded": 0, "positive_pct": None, "negative_pct": None})
        return out
    return fn


MS._mstat_call = lambda fn, *a, **k: fn(*a, **k)
MS._mstat.histogram = _stub_engine("histogram")
MS._mstat.thermometer = _stub_engine("thermometer")
MS._mstat.depth = _stub_engine("depth")
MS._mstat.client_split = _stub_engine("clientsplit")
MS._mstat.mainwatch = _stub_engine("mainwatch")
MS._attach_tape_flags = lambda p: p


def main() -> int:
    app = FastAPI()
    app.include_router(MS.router)
    c = TestClient(app, base_url="http://127.0.0.1:8001", raise_server_exceptions=False)

    valid = sorted(MS._VALID_GROUP)
    print("\n── ۱) هر groupِ معتبر: ۲۰۰ و همان گروه بهِ موتور می‌رسد ──")
    bad200 = []
    for g in valid:
        n0 = len(CALLED)
        r = c.get("/api/mstat/thermometer?group=" + g)
        if r.status_code != 200 or not CALLED[n0:] or CALLED[-1][1] != g:
            bad200.append((g, r.status_code, CALLED[-1][1] if CALLED[-1:] else None))
    ck(not bad200, "الف) هر %d گروهِ معتبر ۲۰۰ می‌گیرد و رد می‌شود" % len(valid), bad200[:3])
    ck("all" in valid and "eq_all" in valid and "silver_fund" in valid,
       "پ) سه اسمِ کلیدی درِ فهرستِ مجاز هستند", valid)

    print("\n── ۲) گروه نامعتبر: ۴۰۰ با کدِ روشن، و موتور اصلاً صدا زده نمی‌شود ──")
    invalid = ["eq", "idx", "fund", "right", "bond", "am", "tf", "mutual",
               "fund_etf", "ALL", "", "  ", "all;drop", "top50 ", "universe"]
    for g in invalid:
        n0 = len(CALLED)
        r = c.get("/api/mstat/thermometer?group=" + (g if g != "  " else "%20%20"))
        reached = CALLED[n0:]
        if r.status_code != 400:
            ck(False, "«%s» ⇒ ۴۰۰" % g, r.status_code)
            continue
        try:
            body = r.json()
        except Exception as e:
            ck(False, "«%s» ⇒ بدنه JSON" % g, type(e).__name__)
            continue
        if not (body.get("code") == "UNKNOWN_GROUP" and body.get("group") == g
                and isinstance(body.get("allowed"), list) and not reached):
            ck(False, "«%s» ⇒ کد+پارامتر+allowed و صفر تماس با موتور" % g,
               {k: body.get(k) for k in ("code", "group", "allowed")}, )
    ck(True, "همۀ موارد نامعتبر سنجیده شد (شکست‌ها بالا چاپ شده)")
    r = c.get("/api/mstat/thermometer?group=nonsense")
    ck("<html" not in r.text[:120].lower(), "پاسخ ۴۰۰ HTML نیست (همان قاعدۀ /api/*)",
       r.text[:90])

    print("\n── ۳) صفرِ **واقعی** هنوز ۲۰۰ است (تفکیکِ عمدی) ──")
    r = c.get("/api/mstat/thermometer?group=silver_fund")
    j = r.json() if r.status_code == 200 else {}
    ck(r.status_code == 200 and j.get("positive") == 0 and j.get("negative") == 0,
       "دسته‌ای که امروز بی‌معامله است ⇒ ۲۰۰ با صفرهایِ خودش", (r.status_code, j))
    r2 = c.get("/api/mstat/thermometer?group=eq_all")
    ck(r2.status_code == 200 and r2.json().get("positive") == 7,
       "دسته‌ای با داده ⇒ ۲۰۰ با عددِ غیرصفر", r2.json())

    print("\n── ۴) `tab` درِ clientsplit: بیگانه به «کل بازار» بدل نمی‌شود ──")
    n0 = len(CALLED)
    r = c.get("/api/mstat/clientsplit?tab=not_a_tab")
    ck(r.status_code == 400 and CALLED[n0:] == [],
       "الف) تبِ بیگانه ⇒ ۴۰۰، نه جایگزینیِ بی‌صدا با all",
       (r.status_code, CALLED[n0:]))
    body = r.json() if r.status_code == 400 else {}
    ck(body.get("tab") == "not_a_tab", "پ) نامِ پارامتر درِ پاسخ درست است", body.get("tab"))
    for t in ("all", "stock", "gold", "fixed", "top50"):
        rr = c.get("/api/mstat/clientsplit?tab=" + t)
        if rr.status_code != 200:
            ck(False, "تبِ معتبر «%s» باید ۲۰۰ بدهد" % t, rr.status_code)
    ck(True, "ت) تب‌هایِ معتبرِ رابط (all/stock/gold/fixed/top50) پذیرفته شدند")

    print("\n── ۵) سه اندپوینت دیگر هم همین دروازه را دارند ──")
    for path, param in (("/api/mstat/histogram", "group"), ("/api/mstat/depth", "group"),
                        ("/api/mstat/mainwatch", "group")):
        rr = c.get("%s?%s=not_a_group" % (path, param))
        ck(rr.status_code == 400 and (rr.json() or {}).get("code") == "UNKNOWN_GROUP",
           "%s ⇒ ۴۰۰" % path, rr.status_code)

    print("\n── ۶) کنترلِ منفی: اگر دروازه برداشته شود، سنجه باید قرمز شود ──")
    keep = MS._check_group
    try:
        MS._check_group = lambda param, value: True          # «دروازۀ خاموش»
        CALLED.clear()
        rr = c.get("/api/mstat/thermometer?group=nonsense")
        ck(rr.status_code == 200 and CALLED and CALLED[-1][1] == "nonsense",
           "الف) با دروازۀ خاموش، گروه بیگانه به موتور می‌رسد (پس سنجه کور نیست)",
           (rr.status_code, CALLED[-1] if CALLED else None))
    finally:
        MS._check_group = keep
    CALLED.clear()
    rr = c.get("/api/mstat/thermometer?group=nonsense")
    ck(rr.status_code == 400 and not CALLED,
       "پ) با دروازۀ روشن همان درخواست ۴۰۰ است و موتور صدا زده نمی‌شود",
       (rr.status_code, CALLED))

    print("\n%d checks, %d failed" % (PASS + FAIL, FAIL))
    print("MSTAT GROUP VALIDATION " + ("OK" if FAIL == 0 else "FAILED"))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
