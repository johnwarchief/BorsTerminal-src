"""v9.7.4 — گارد «رویکرد هشدار منعطف» (Soft Warning Approach).

چرا این تست متولد شد: در v9.7.3 اگر ستون بنیادی نمادی را «حذف خودکار» می‌کرد
(ماده ۱۴۱ / زیان‌ده) یا روند هفتگی نزولی بود، کل نماد VETOED می‌خورد و عملاً از
دیدهٔ کاربر بیرون می‌رفت. صفحهٔ ۲ متدولوژی FTS دقیقاً شکارچیِ همان سهم‌های
برگشتیِ ماده ۱۴۱ است — پس وتوی سخت، بهترین شکارها را پنهان می‌کرد.
این فایل قفل می‌کند که:
  ۱) وتو دیگر وجود ندارد؛ حالت چهارم «warn» است و سهم هرگز حذف نمی‌شود.
  ۲) warn در شمارش conf_count نمی‌آید (وگرنه نرم‌کردن یعنی تاییدِ جعلی).
  ۳) دروازهٔ هفتگی روی امتیازِ روزانه اثر نمی‌گذارد، فقط رنگِ وضعیت را عوض می‌کند.
  ۴) ستاپ‌های روزانه (breakout/pullback/fibonacci/CHoCH) گزارش می‌شوند، رأی نمی‌دهند.
  ۵) متن هشدار به conf_reasons می‌رسد (نه فقط یک bool خشک).

اجرا:  python dev/soft_warnings_v974.py
بخشِ دیتا اگر market.db نباشد SKIP می‌شود؛ گاردهای خالص همیشه اجرا می‌شوند.
"""
import io
import os
import re
import sqlite3
import sys
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))
    return cond


import confidence_engine as CE

C = dict(CE.CONF_DEFAULTS)


def weekly(closes, newest_first=True):
    """ردیف‌های هفتگیِ واقعی (۷ روز فاصله) تا کلید ISO هفته یکنواخت باشد."""
    start = date(2020, 1, 6)
    rows = [(start + timedelta(days=7 * i)).isoformat() for i in range(len(closes))]
    if newest_first:
        rows = list(reversed(rows))
        closes = list(closes)          # همان ترتیب: تازه‌ترین اول
    return [(rows[i], float(closes[i]), float(closes[i]) * 1.01,
             float(closes[i]) * 0.99, 1000.0) for i in range(len(closes))]


# ===================== گارد ۱: قرارداد وضعیت‌ها (ساختار، نه سلیقه) =========
ck(getattr(CE, "PILLAR_STATES", ()) == ("pass", "warn", "fail", "nodata"),
   "PILLAR_STATES is exactly the 4-state contract")
w = CE._pillar("tech", "warn", score=2, max_score=3, reasons=["⚠️ تست"])
ck(w["state"] == "warn" and w["warn"] is True, "warn state exposes warn=True")
ck(w["pass"] is False, "warn is NEVER pass (conf_count must not inflate)")
ck(w["nodata"] is False, "warn is not nodata either")
try:
    CE._pillar("tech", "maybe")
    ck(False, "unknown state must raise")
except ValueError:
    ck(True, "unknown state raises ValueError (no silent grey badge)")

# ===================== گارد ۲: حذف وتو از قرارداد خروجی ====================
src = io.open("confidence_engine.py", encoding="utf-8").read()
ck('verdict = "VETOED"' not in src, "no VETOED verdict left in the engine")
ck('"vetoed"' not in src, "no vetoed key left in the engine output")
ck(re.search(r'verdict = "WATCH"', src) is not None, "WATCH verdict replaces VETOED")
for fn in ("conf_tech", "conf_tape", "conf_fund"):
    body = re.search(r'\ndef %s\(.*?(?=\ndef |\Z)' % fn, src, re.S)
    body = body.group(0) if body else ""
    body = re.sub(r'"""[\s\S]*?"""|#[^\n]*', '', body)   # docstring/comments out
    ck('"warn"' in body or 'state = "warn"' in body,
       "%s can actually emit warn" % fn)
for f, pat in (("archive/legacy_static/selection.js", r"VETOED\s*[:=]"),   # کلیدِ نقشهٔ badge
               ("BACKEND", r'["\']VETOED["\']')):            # مقایسهٔ رشته‌ای
    # v9.8.1: handlers moved verbatim out of app.py into api/*.py, so the
    # "no vetoes" contract must be swept over the whole backend.
    files = (["app.py", "bors_config.py", "bors_flags.py"] + [
        os.path.join("api", x) for x in sorted(os.listdir("api"))
        if x.endswith(".py")] if os.path.isdir("api") else ["app.py"]
    ) if f == "BACKEND" else [f]
    s2 = "\n".join(io.open(x, encoding="utf-8").read()
                    for x in files if os.path.exists(x))
    ck(not re.search(pat, s2), "%s has no live VETOED reference" % f)
sel = io.open("archive/legacy_static/selection.js", encoding="utf-8").read()
ck(re.search(r"\bwarn:\s*\{", sel) is not None, "selection.js renders a warn state")
ck("conf_reasons" in sel, "selection.js surfaces conf_reasons in the tooltip")
# tooltipهای سرستون در HTML، قرارداد عمومی UI هستند — جایِ گارد نیست که فراموش شوند
html = io.open("archive/legacy_static/index.html", encoding="utf-8").read()
ck("VETOED" not in html, "index.html header tooltip has no VETOED")
ck("WATCH" in html, "index.html header tooltip advertises WATCH")
ck("⚠" in html, "index.html legend explains the warn mark")

# ===================== گارد ۳: RSI و بستهٔ هفتگی (ریاضیِ خالص) =============
up = [float(129 - i) for i in range(30)]           # صعودی، تازه‌ترین اول (129 آخرین است)
down = [float(100 + i) for i in range(30)]          # نزولی، تازه‌ترین اول (100 آخرین است)
ck(CE._rsi(up, 14) == 100.0, "rising series RSI=100 (direction sanity)")
ck(CE._rsi(down, 14) == 0.0, "falling series RSI=0 — locks the reversed-series bug")
ck(CE._rsi([10.0, 11.0], 14) is None, "too few closes -> None, not 0 or 50")
ck(CE._rsi(up, 1) is None, "period<2 is rejected instead of dividing by zero")
wc = CE._weekly_closes([("2024-03-08", 110.0, 0.0, 0.0, 0.0),
                        ("2024-03-07", 105.0, 0.0, 0.0, 0.0),
                        ("2024-03-01", 100.0, 0.0, 0.0, 0.0)])
ck(wc == [110.0, 100.0],
   "weekly bucket keeps each week's LATEST close, drops the rest (got %s)" % wc)
ck(CE._weekly_closes([]) == [], "empty rows -> empty weekly series (no crash)")
ck(CE._week_key("not-a-date") is None, "corrupt date yields None, not a bogus week")

# ===================== گارد ۴: دروازهٔ نرم هفتگی ===========================
g_up = CE._weekly_gate(weekly([100 + i for i in range(60)][::-1]), C)
ck(g_up["weak"] is False and g_up["bullish"] is True,
   "rising 60 weeks -> bullish, no warning")
g_dn = CE._weekly_gate(weekly([100 + i for i in range(60)]), C)
ck(g_dn["weak"] is True, "falling 60 weeks -> weak (warn trigger)")
ck(g_dn["rsi7"] == 0.0 and g_dn["oversold"] is True,
   "RSI7 weekly computed on weekly closes (got %s)" % g_dn["rsi7"])
g_short = CE._weekly_gate(weekly([100 + i for i in range(10)][::-1]), C)
ck(g_short["weak"] is None and g_short["bullish"] is None,
   "52 weeks unavailable -> weak=None: missing data is NOT a warning")
ck(g_short["w_bars"] == 10, "w_bars reports what it actually saw")
ck(CE._weekly_gate(weekly([100] * 60), C)["weak"] is True,
   "dead-flat price is neutral, and neutral warns (per FTS page-2 gate)")
# ====== گارد ۵: ستاپ‌های روزانه — گزارش‌اند، نه گیتِ رأی ======
flat = [100.0] * 31
spike = [2000.0] + [1000.0] * 30
s1 = CE._daily_setups([105.0] + flat[1:], [105.0] + flat[1:], flat, spike, C)
ck(s1["breakout"] is True, "breakout fires above the prior 20-bar high")
ck(s1["heavy_volume"] is True, "volume spike is reported with the breakout")
ck(s1["pullback"] is False, "a 5% gap above MA20 is not a pullback")
s2 = CE._daily_setups(flat, flat, flat, flat, C)
ck(s2["breakout"] is False, "a close level with the range is not a breakout")
ck(s2["heavy_volume"] is False, "flat volume is never 'heavy'")
ck(s2["pullback"] is False, "a close sitting ON MA20 is not a pullback")
s3 = CE._daily_setups([101.0] + flat[1:], [101.0] + flat[1:], flat, flat, C)
ck(s3["pullback"] is True, "close 1% above MA20 reads as a pullback")
ch_highs = [80.0, 85.0, 88.0, 84.0, 92.0, 88.0, 95.0, 90.0, 96.0, 92.0, 99.0, 95.0, 100.0, 96.0]
ck(CE._daily_setups([90.0] + [85.0] * 15, ch_highs, [80.0] * 16, [1000.0] * 16, C)["choch"] is True,
   "CHoCH = recent lower high (88) reclaimed by close (90)")
ck(CE._daily_setups([80.0] + [85.0] * 15, ch_highs, [80.0] * 16, [1000.0] * 16, C)["choch"] is False,
   "same structure, unreclaimed close -> no CHoCH")
ck(CE._choch([1.0] * 5, [1.0]) is None, "too few bars -> None (unknown), not False")
ck(all(v is None or isinstance(v, bool) for v in s1.values()),
   "every setup is bool-or-None (UI never receives a number it must guess)")
sr = CE._stop_refs([100.0] * 8 + [90.0] + [100.0] * 8,
                   [100.0] * 8 + [80.0] + [100.0] * 8, C)
ck(sr["ma14"] is not None and sr["rising_low"] == 80.0,
   "stop refs expose MA14 and the last major low for Phase 3")
ck(abs(sr["swing_stop"] - 76.0) < 1e-9,
   "swing stop = 5%% below the major low (got %s)" % sr["swing_stop"])
ck(CE._stop_refs(flat, flat, C)["rising_low"] is None,
   "a dead-flat series reports no fake swing low")

# ============ گارد ۶: نردبان داوری بدون وتو (تزریق ستون) ================
def P(state, reasons=(), verdict=None):
    return CE._pillar("tech", state, score=1, max_score=3,
                      reasons=list(reasons), detail={"verdict": verdict})


allpass = CE.triple(None, "فولاد", pillars={"tech": P("pass"), "tape": P("pass"),
                                            "fund": P("pass")})
ck(allpass["verdict"] == "CONFIRMED" and allpass["conf_count"] == 3,
   "3 pass -> CONFIRMED")
ck("vetoed" not in allpass, "triple() emits no 'vetoed' key at all")
# ---- گارد اصلی: نمادِ حذف‌شدهٔ FTS دیگر وتو نمی‌خورد ----
excl_txt = "⚠️ ماده ۱۴۱ / زیان‌ده — حذف نشد، فقط هشدار: زیان انباشته ۶۰٪"
o = CE.triple(None, "wahed", pillars={"tech": P("pass"), "tape": P("pass"),
                                      "fund": P("warn", [excl_txt], "EXCLUDED")})
ck(o["verdict"] == "PROBABLE", "FTS-excluded symbol is PROBABLE, not VETOED (got %s)" % o["verdict"])
ck(o["warns"] == ["fund"], "warns names the fund pillar (got %s)" % o["warns"])
ck(any("ماده ۱۴۱" in t for t in o["conf_reasons"]),
   "the warning text reaches conf_reasons, not just a boolean")
ck(o["conf_count"] == 2 and o["conf_fund"] is False,
   "warn keeps conf_count honest (no laundered confirmation)")
ck(o["verdict"] not in ("VETOED",) and any("هشدار" in n for n in o["notes"]),
   "notes carry the warning for the UI tooltip")
ck(len(o["notes"]) <= 2, "notes stay bounded (<=2) for the table cell")
w1 = CE.triple(None, "w", pillars={"tech": P("warn", ["⚠️ روند هفتگی ضعیف"]),
                                   "tape": P("pass"), "fund": P("nodata")})
ck(w1["verdict"] == "WATCH" and w1["coverage"] == 2,
   "1 pass + 1 warn -> WATCH (never dropped, never confirmed)")
w2 = CE.triple(None, "w", pillars={"tech": P("warn", ["⚠️ x"]), "tape": P("warn", ["⚠️ y"]),
                                   "fund": P("nodata")})
ck(w2["verdict"] == "WATCH" and w2["conf_count"] == 0,
   "warn with zero passes still yields a verdict, not an absence")
w3 = CE.triple(None, "w", pillars={"tech": P("fail"), "tape": P("fail"), "fund": P("fail")})
ck(w3["verdict"] == "WEAK", "0 pass + 0 warn -> WEAK")
w4 = CE.triple(None, "w", pillars={"tech": P("nodata"), "tape": P("nodata"),
                                   "fund": P("warn", ["⚠️ z"])})
ck(w4["verdict"] == "INSUFFICIENT", "below min_coverage still abstains even with a warn")

# ============ گارد ۷: دیتای واقعی — هیچ سهمی حذف نمی‌شود ============
if not os.path.exists("market.db"):
    ck(False, "market.db missing — live guards could not run")
else:
    conn = sqlite3.connect("file:market.db?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    ctx = CE.build_ctx(conn)

    # سیاست v9.7.5: ضعف هفتگی فقط ستاپِ «موفقِ روزانه» را warn می‌کند؛
    # ستاپِ بازنده همان fail (قرمز) می‌ماند. هر دو حالت باید در دادهٔ واقعی دیده شوند.
    wk_pass = wk_fail = bull_sym = None
    for sym in [r[0] for r in conn.execute(
            "SELECT symbol FROM price_history GROUP BY symbol HAVING COUNT(*) >= 300")][:600]:
        t = CE.conf_tech(conn, sym, ctx=ctx)
        wk = (t.get("detail") or {}).get("weekly") or {}
        if wk.get("weak") is True:
            if t["state"] == "warn" and wk_pass is None:
                wk_pass = sym
            elif t["state"] == "fail" and wk_fail is None:
                wk_fail = sym
        elif wk.get("weak") is False and bull_sym is None:
            bull_sym = sym
        if wk_pass and wk_fail and bull_sym:
            break

    ck(wk_pass is not None, "daily-pass + weak-weekly exists in live data")
    if wk_pass:
        t = CE.conf_tech(conn, wk_pass, ctx=ctx)
        ck(t["state"] == "warn", "daily pass + weak weekly -> warn (got %s)" % t["state"])
        ck(t["warn"] is True and t["pass"] is False, "warn surfaces to consumers")
        ck(t["score"] >= t["detail"]["need"],
           "warn was only allowed because the daily setup passes (score %s/%s)"
           % (t["score"], t["detail"]["need"]))
        ck(any("روند هفتگی ضعیف" in x for x in t["reasons"]),
           "the weak-trend reason text is present")
        r = CE.triple(conn, wk_pass, ctx=ctx)
        ck("vetoed" not in r and r["verdict"] != "VETOED", "no veto on live data")
        ck(any("روند هفتگی ضعیف" in x for x in r["conf_reasons"]),
           "weak-weekly reason reaches conf_reasons")
        ck(r["warns"] == [k for k in CE.PILLAR_ORDER if r["states"][k] == "warn"],
           "warns is always consistent with states")
        off = CE.conf_tech(conn, wk_pass, ctx=ctx, cfg={"tech_weekly_ma": 10 ** 6})
        ck(off["detail"]["weekly"]["weak"] is None,
           "with the gate unsatisfiable, weak reverts to None (no invented warning)")
        ck(off["state"] == "pass",
           "same symbol without the weekly gate is a clean pass (got %s)" % off["state"])
        ck(off["score"] == t["score"],
           "the weekly gate never touches the daily score (%s vs %s)" % (off["score"], t["score"]))

    ck(wk_fail is not None, "daily-fail + weak-weekly exists in live data")
    if wk_fail:
        tf = CE.conf_tech(conn, wk_fail, ctx=ctx)
        ck(tf["state"] == "fail",
           "daily setup fails -> stays fail even when weekly is weak (got %s)" % tf["state"])
        ck(tf["warn"] is False, "a failed pillar never reports warn")
        ck(not any(x.startswith("⚠️") and "روند هفتگی" in x for x in tf["reasons"]),
           "no ⚠️ weekly warning minted on a failing setup")
        ck(any("روند هفتگی هم ضعیف" in x for x in tf["reasons"]),
           "the weekly weakness is still explained, not hidden")
        off = CE.conf_tech(conn, wk_fail, ctx=ctx, cfg={"tech_weekly_ma": 10 ** 6})
        ck(off["state"] == "fail" and off["score"] == tf["score"],
           "weekly gate changes neither the verdict colour nor the score of a loser")

    if bull_sym:
        tb = CE.conf_tech(conn, bull_sym, ctx=ctx)
        ck(tb["detail"]["weekly"]["weak"] is False and "⚠️ روند هفتگی ضعیف" not in tb["reasons"],
           "a bullish-weekly symbol is never warned for the weekly gate")

    import fts_engine as FE
    bulk = FE.bulk_scan(conn)
    excl = [r.get("symbol") for r in bulk if r.get("excluded")][:4]
    ck(len(excl) > 0, "market.db really has FTS-excluded symbols (%d used)" % len(excl))
    probe = [s for s in (excl + [wk_pass, wk_fail, bull_sym]) if s]
    m = CE.triple_many(conn, probe, ctx=ctx, fund_rows=bulk)
    ck([x["symbol"] for x in m] == probe, "triple_many drops nothing, order preserved")
    ck(all(x["verdict"] != "VETOED" for x in m), "live matrix contains no VETOED")
    exrows = [x for x in m if x["symbol"] in excl]
    ck(all(x["pillars"]["fund"]["state"] == "warn" for x in exrows),
       "live EXCLUDED symbols report fund=warn (%d checked)" % len(exrows))
    ck(all(x["states"]["fund"] != "fail" for x in exrows),
       "EXCLUDED never reads as fund=fail anymore")
    ck(all(x["conf_reasons"] for x in exrows),
       "every excluded-but-kept symbol ships a reason to the UI")

    print("\n".join("  %s %s" % ("PASS" if ok else "FAIL", msg) for ok, msg in CHECKS))
    bad = [msg for ok, msg in CHECKS if not ok]
    print("\n%d checks, %d failed" % (len(CHECKS), len(bad)))
    sys.exit(1 if bad else 0)

