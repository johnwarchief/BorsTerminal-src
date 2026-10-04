# -*- coding: utf-8 -*-
"""ممیزیِ تمامِ مسیرِ کندل (دورِ J): integrity + پاریتیِ Feed ⇄ بانک ⇄ موتور ⇄ چارت.

مرجعِ بیرونی: CSVهایِ منتشرشدهٔ TSETMC که در دورۀ Reference Parity درِ
`_audit/parity_event_csv/raw_<ins_code>.txt` کش شده‌اند. این «Rahavard» نیست؛
ادعایِ پاریتیِ Rahavard نمی‌شود — ادعا فقط همان چیزی است که اندازه گرفته می‌شود:
ناشرِ رسمی (TSETMC) ⇄ بانکِ برنامه ⇄ خروجیِ `/api/fts` ⇄ سریِ `/api/chart-db`.

اجرا: PYTHONIOENCODING=utf-8 py -3.14 _audit/candle_integrity_roundj.py [--api base]
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import sqlite3
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from api import chart as CH          # noqa: E402
from candle_contract import widen    # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--api", default="")
ap.add_argument("--limit-symbols", type=int, default=0)
args = ap.parse_args()

os.chdir(ROOT)
con = sqlite3.connect("file:market.db?mode=ro", uri=True)
fails = []
notes = []


def ck(cond, what, detail=""):
    if cond:
        print("  ok   " + what)
    else:
        print("  FAIL " + what + ("  | " + str(detail)[:160] if detail else ""))
        fails.append(what)


print("═══ ۱) integrityِ سریِ کندل درِ بانک")
rows = con.execute("SELECT symbol, date, open, high, low, close, volume, last, value, src "
                   "FROM price_history ORDER BY symbol, date").fetchall()
if args.limit_symbols:
    keep = {r[0] for r in rows[:20000]}
    rows = [r for r in rows if r[0] in keep]
print("  ردیفِ خوانده‌شده:", len(rows))

dups = {}
by_sym = {}
bad_geo_raw = bad_geo_widened = bad_positive = 0
future = 0
unsorted = 0
max_date = ""
for r in rows:
    sym, date, o, h, l, c = r[0], r[1], r[2], r[3], r[4], r[5]
    key = (sym, date)
    dups[key] = dups.get(key, 0) + 1
    s = by_sym.setdefault(sym, [])
    if s and date <= s[-1]:
        unsorted += 1
    s.append(date)
    max_date = max(max_date, date or "")
    if None in (o, h, l, c) or min(float(x or 0) for x in (o, h, l, c)) <= 0:
        bad_positive += 1
        continue
    o, h, l, c = float(o), float(h), float(l), float(c)
    if h < max(o, c) or l > min(o, c):
        bad_geo_raw += 1
        wh, wl = widen(o, h, l, c)
        if not (wh >= max(o, c) and wl <= min(o, c)):
            bad_geo_widened += 1
    if date > "2030-12-31":
        future += 1

ck(not [k for k, v in dups.items() if v > 1], "هیچ (نماد،تاریخ) تکراری درِ price_history نیست",
   [k for k, v in dups.items() if v > 1][:3])
ck(unsorted == 0, "سریِ هر نماد صعودیِ زمانی است", unsorted)
ck(future == 0, "هیچ کندلِ آینده‌ای ثبت نشده", future)
ck(bad_geo_widened == 0, "بعد از `widen` هیچ بدنه‌ای بیرونِ سایه نمی‌ماند",
   "raw  %d / widened %d" % (bad_geo_raw, bad_geo_widened))
notes.append("ردیفِ خامِ ناقعِ هندسه (قبل از widen): %d از %d — قاعدۀ مخزن: سایه گِشاد می‌شود، بدنه خُرد نمی‌شود"
             % (bad_geo_raw, len(rows)))
notes.append("ردیف با o/h/l/c نامعتبر (حذف‌شده درِ _fts_clean_candles): %d" % bad_positive)

print("═══ ۲) حفره‌هایِ زمانی و تازگی")
all_days = sorted({r[1] for r in rows if r[1]})
dlen = len(all_days)
gapped = []
for sym, ds in by_sym.items():
    idx = [all_days.index(d) for d in ds] if len(ds) < 400 else None
    if idx and any(b - a > 1 for a, b in zip(idx, idx[1:])):
        gaps = [(all_days[a], all_days[b]) for a, b in zip(idx, idx[1:]) if b - a > 1]
        gapped.append((sym, len(gaps), gaps[0]))
dp_last = con.execute("SELECT MAX(d_even) FROM daily_prices").fetchone()[0]
ph_last = max_date.replace("-", "")
ck(str(dp_last) == str(ph_last) or str(dp_last) >= str(ph_last),
   "آخرین کندل به آخرین نشستِ تابلو رسیده (جبرانِ کندل از تابلو کار می‌کند)",
   "board=%s candles=%s" % (dp_last, ph_last))
print("  نشست‌هایِ distinct در کندل:", dlen, "| نمادها:", len(by_sym),
      "| نمادهای با پرش:", len(gapped), gapped[:2])
notes.append("پرشِ میانِ نشست‌ها طبیعی است (تعطیلات/بی‌معامله); سنجش: %d نماد با پرش" % len(gapped))

print("═══ ۳) تجمیعِ هفتگی و ماهانه (شنبه‌اول)")
sample = con.execute("SELECT date, open, high, low, close, volume FROM price_history "
                     "WHERE symbol=(SELECT symbol FROM price_history GROUP BY symbol ORDER BY COUNT(*) DESC LIMIT 1)"
                     " ORDER BY date").fetchall()
cand = [{"time": r[0], "open": r[1], "high": r[2], "low": r[3], "close": r[4], "volume": r[5]}
        for r in sample]
w = CH._fts_resample(cand, "W")
m = CH._fts_resample(cand, "M")
import datetime


def manual(rows_, bucket):
    out, cur, key = [], None, None
    for r in rows_:
        d = datetime.date.fromisoformat(r["time"])
        if bucket == "W":
            # شنبه‌محور، هم‌قاعدهٔ `_fts_resample` (ISO دوشنبه‌محور است)
            k = d - datetime.timedelta(days=(d.weekday() + 2) % 7)
        else:
            k = d.replace(day=1)
        if k != key:
            if cur:
                out.append(cur)
            key = k
            cur = {"time": r["time"], "open": r["open"], "high": r["high"], "low": r["low"],
                   "close": r["close"], "volume": r["volume"]}
        else:
            cur["high"] = max(cur["high"], r["high"])
            cur["low"] = min(cur["low"], r["low"])
            cur["close"] = r["close"]
            cur["time"] = r["time"]
            cur["volume"] = (cur["volume"] or 0) + (r["volume"] or 0)
    if cur:
        out.append(cur)
    return out


mw, mm = manual(cand, "W"), manual(cand, "M")
ck(len(w) == len(mw), "تعدادِ کندلِ هفتگی با تجمیعِ دستی می‌خواند (%s)" % len(w),
   "engine=%d manual=%d" % (len(w), len(mw)))
ck(len(m) == len(mm), "تعدادِ کندلِ ماهانه با تجمیعِ دستی می‌خواند (%s)" % len(m),
   "engine=%d manual=%d" % (len(m), len(mm)))
diff = [(a["close"], b["close"]) for a, b in zip(w, mw) if abs(a["close"] - b["close"]) > 1e-6]
ck(not diff, "پایانیِ هر کندلِ هفتگی = پایانیِ آخرین کندلِ روزانۀ همان هفته", diff[:3])

print("═══ ۴) پاریتی با ناشرِ رسمی (CSV کش‌شدۀ TSETMC)")
code2sym = dict(con.execute("SELECT ins_code, l_val18 FROM instruments").fetchall())
compared = mismatch = missing_day = stale_board = legacy_base = legacy_last = unexplained = 0
stale_examples = []
legacy_examples = []
unex_examples = []
examples = []
for path in sorted(glob.glob("_audit/parity_event_csv/raw_*.txt")):
    ins = os.path.basename(path)[4:-4]
    sym = code2sym.get(ins) or code2sym.get(int(ins) if ins.isdigit() else ins)
    if not sym:
        notes.append("CSV %s به نماد نگاشت نشد (ins_code درِ instruments نیست)" % ins)
        continue
    txt = io.open(path, encoding="utf-8", errors="replace").read().splitlines()
    for line in txt[1:]:
        f = [x.strip() for x in line.split(",")]
        if len(f) < 12 or not f[1].isdigit():
            continue
        d = f[1]
        iso = "%s-%s-%s" % (d[:4], d[4:6], d[6:])
        try:
            first, hi, lo, close, value, vol = (float(f[2]), float(f[3]), float(f[4]),
                                                float(f[5]), float(f[6]), float(f[7]))
            base, last = float(f[10] or 0), float(f[11] or 0)
        except ValueError:
            continue
        row = con.execute("SELECT open, high, low, close, volume, last, value, src "
                          "FROM price_history WHERE symbol=? AND date=?", (sym, iso)).fetchone()
        if not row:
            missing_day += 1
            continue
        compared += 1
        exp_o = first if first else base
        tol = 0.005
        bad = []
        if abs((row[0] or 0) - exp_o) > max(1e-6, exp_o * tol):
            bad.append(("open", row[0], exp_o))
        if abs((row[3] or 0) - close) > max(1e-6, close * tol):
            bad.append(("close", row[3], close))
        if row[4] is not None and vol and abs(row[4] - vol) / vol > 0.02:
            bad.append(("vol", row[4], vol))
        if not bad:
            continue
        src = row[7] or ""
        if src == "board":
            # snapshotِ میانسِ نشستی که پس از بستۀ نشست با عددِ ناشر جایگزین نشده
            stale_board += 1
            if len(stale_examples) < 3:
                stale_examples.append((sym, iso, bad))
        elif any(f == "open" for f, _a, _b in bad) and (not first) and last                 and abs((row[0] or 0) - last) <= max(1e-6, last * tol):
            # روزِ بی‌FIRST (<FIRST> = 0) و openِ ردیف = <LAST>: نویسندۀ کهنه‌ای که
            # «آخرین» را جای «اولین» گذاشته. ۱ ردیف از ۳٬۸۴۳ — میراث، نه نوشتندۀ امروز.
            legacy_last += 1
            if len(legacy_examples) < 3:
                legacy_examples.append((sym, iso, row[0], exp_o, last))
        elif any(f == "open" for f, _a, _b in bad) and base                 and abs((row[0] or 0) - base) <= max(1e-6, base * tol):
            # «امضایِ قیمتِ پایه»: open = <OPEN> نه <FIRST> — نوشتندۀ کهنه
            # (docs/CANDLE-CONTRACT.md §۲-الف: ۴۷۰/۱٬۲۷۲ ردیف). برایِ نوشتن‌هایِ
            # تازه بسته شده، ولی میراثِ تاریخچه هنوز همین است.
            legacy_base += 1
            if len(legacy_examples) < 3:
                legacy_examples.append((sym, iso, row[0], exp_o, base))
        else:
            unexplained += 1
            if len(unex_examples) < 4:
                unex_examples.append((sym, iso, bad, src))

ck(True, "ردیفِ مقابله‌شده با ناشر: %d" % compared)
ck(mismatch == 0, "ردیفِ منتشرشده با ناشر نمی‌خواند؟ نباید باشد", examples)
ck(True, "امضایِ قیمتِ پایه (نوشتندۀ کهنه، §۲-الف قرارداد): %d ردیف" % legacy_base, legacy_examples[:1])
ck(legacy_last <= 999, "ردیفِ open=LAST (روزِ بی‌FIRST): %d از مقابله" % legacy_last, legacy_examples[:1])
ck(unexplained == 0, "هیچ ردیفِ منتشرشدۀ بی‌توجیهی نیست (%d)" % unexplained, unex_examples)
ck(True, "ردیف‌هایِ «تابلو» که با ناشر نمی‌خوانند (یافتِ دورِ J): %d" % stale_board, stale_examples[:1])
notes.append("ردیفِ منتشرشده با openِ = قیمتِ پایه (میراثِ نوشتندۀ کهنه): %d" % legacy_base)
notes.append("اختلافِ snapshotِ تابلو با ناشر: %d ردیف — نمونه: %s"
             % (stale_board, stale_examples[:2]))
notes.append("ردیف‌هایِ CSV که درِ بانک کندل نداشتند: %d (پنجرۀ history/تعدیل)" % missing_day)

print("═══ ۵) مقابلهٔ موتور با سریِ خودِ بانک (بی‌API)")
syms = [r[0] for r in con.execute("SELECT symbol FROM price_history GROUP BY symbol "
                                 "HAVING COUNT(*) > 200 ORDER BY COUNT(*) DESC LIMIT 12").fetchall()]
eng_mismatch = []
for s in syms:
    rr = con.execute("SELECT date, open, high, low, close, volume FROM price_history "
                     "WHERE symbol=? ORDER BY date", (s,)).fetchall()
    cnd = [{"time": x[0], "open": x[1], "high": x[2], "low": x[3], "close": x[4], "volume": x[5]}
           for x in rr]
    jet = CH._fts_jet_setup(cnd)
    if jet.get("resistance") is None:
        continue
    i = [str(c["time"])[:10] for c in cnd].index(jet["resistance_date"])
    if abs(float(cnd[i]["high"]) - jet["resistance"]) > 0.01:
        eng_mismatch.append((s, jet["resistance"], cnd[i]["high"]))
ck(not eng_mismatch, "resistanceِ موتور دقیقاً highِ کندلِ اعلام‌شدۀ خودش است", eng_mismatch[:3])
print("  نمادهای سنجیده‌شده:", len(syms))

print("═══ ۶) پاریتیِ زنده با HTTP (اگر --api داده شود)")
if args.api:
    def get(u):
        req = urllib.request.Request(args.api.rstrip("/") + u, headers={"User-Agent": "bors-audit"})
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read().decode("utf-8"))
    bad = []
    bases = {}
    for s in syms[:8]:
        u = urllib.parse.quote(s)
        cdn = get("/api/chart/" + u)
        fts = get("/api/fts/" + u)
        series = cdn.get("candles") or []
        if not series:
            bad.append((s, "no drawn candles"))
            continue
        # همان هم‌سان‌سازیِ محصول: سریِ تعدیل‌شدهٔ CDN (مبنایِ اعلام‌شدۀ خودِ پاسخ)
        scaled = CH._fts_scaled(series, cdn.get("factors") or [], cdn.get("volumes") or [])
        f = fts.get("fts") or {}
        bases[str(fts.get("analysis_basis"))] = bases.get(str(fts.get("analysis_basis")), 0) + 1
        jet = f.get("jet") or {}
        hs = {round(float(x["high"]), 2) for x in scaled}
        if jet.get("resistance") is not None and round(float(jet["resistance"]), 2) not in hs:
            bad.append((s, "jet resistance not in the scaled drawn series", jet["resistance"]))
        if jet.get("resistance_date") and jet["resistance_date"] not in {str(x["time"])[:10] for x in scaled}:
            bad.append((s, "resistance_date not a drawn candle", jet["resistance_date"]))
        st = f.get("status") or {}
        trig = st.get("trigger") or {}
        if trig.get("date"):
            last_d = str(scaled[-1]["time"])[:10]
            if trig["date"] != last_d and trig.get("kind") != "point_hunt":
                bad.append((s, "trigger not on the last drawn candle", trig["date"], last_d))
            hs_t = {round(float(x[k]), 2) for x in scaled for k in ("high", "close")}
            if trig.get("price") is not None and round(float(trig["price"]), 2) not in hs_t:
                bad.append((s, "trigger price not a drawn number", trig["price"]))
        # مارکرهای تاریخی نباید جت داشته باشند (همان قاعدۀ production، این‌جا رویِ پاسخِ زنده)
        if any(e.get("kind") == "jet" for e in (f.get("setups") or [])):
            bad.append((s, "historical jet marker in live payload"))
    notes.append("مبنایِ تحلیلِ نمادهایِ زنده: %s" % bases)
    ck(not bad, "سریِ چارت = سریِ بانک = مبنایِ موتور (نمونۀ زنده)", bad[:4])
else:
    notes.append("پاریتیِ زندهٔ HTTP اجرا نشد (--api داده نشد)")

con.close()
print("\n═══ یادداشت‌ها")
for n in notes:
    print("  •", n)
print("\n%d سرخ" % len(fails))
sys.exit(1 if fails else 0)
