# dev/test_market_state_stages_v1.py — بند ۲/۳/۴/۶ مأموریت 1405-07-20:
# «وضعیت بازار هوشمند و زمان‌مند» — حکم بی‌مرحل ممنوع، ابتدای روز با کل روز مقایسه نشود
"""دو لایه:

    الف) سناریوهایِ کنترل‌شدهٔ bi‑دیتابیس روی day_verdict/_market_state:
       پیش‌آغاز با فلوئِ منفیِ دیروز ⇒ نه «وارد نشو»؛ نقدینگیِ یک‌طرفه در
       نشستِ جاری؛ تازگیِ client_type؛ آستانهٔ «شواهدِ اولیه» تا ۰۹:۳۰؛
       رأیِ منفی فقط با ۳ اختلافِ پیاپی؛ نشستِ بسته همان رفتارِ کهنی.
    ب) replayِ بی‌آینده از mstat_snapِ واقعی (market.db، فقط‑خواندنی):
       هر نقطه فقط با نقطه‌های h_even<= خودش داوری می‌شود؛ کنترلِ منفی با
       کاشتنِ نقطۀ «آینده» ثابت می‌کند درِ trend کور نیست و نگاه به آینده
       ندارد؛ و کنترلِ «روزِ بدِ تمام‌شده» ثابت می‌کند درِ منفی بکُند نمی‌کند.

نتیجه با همان قالبِ `X_pass / Y_fail / Z_skip` (سه فرمتِ قابل‌پارسِ run_all_tests).
"""
import datetime
import io
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8")

import mstat_engine as ME                      # noqa: E402

PASS = FAIL = SKIP = 0


def ck(label, cond, detail=""):
    global PASS, FAIL, SKIP
    if cond is None:
        SKIP += 1
        print(f"  SKIP  {label}")
        return
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL  {label}  {detail}")


def ph(p, allowed, live, comp, why=None, day=20261012):
    return {"phase": p, "label": {"pre_open": "پیش از آغازِ معاملات",
                                  "continuous": "معاملات جاری",
                                  "closed": "پایانِ نشست"}.get(p, p),
            "verdict_allowed": allowed, "is_live": live, "computable": comp,
            "why_not": why or {}, "session_day": day,
            "not_computable": [k for k, v in comp.items() if not v]}


COMP_CONT = {"realized_flow": True, "order_pressure": True,
             "session_vs_threshold": True, "close_price_final": False}
COMP_PRE = {"realized_flow": False, "order_pressure": True,
            "session_vs_threshold": False, "close_price_final": False}
COMP_FINAL = {"realized_flow": True, "order_pressure": False,
              "session_vs_threshold": True, "close_price_final": True}
PH_CONT = ph("continuous", True, True, COMP_CONT)
PH_PRE = ph("pre_open", False, False, COMP_PRE,
            {"realized_flow": "هنوز معامله‌ای ثبت نشده"})
PH_CLOSED = ph("closed", True, False, COMP_FINAL)


def sm(flow=None, macro=None, asof=None):
    base = {"macro": macro or {}, "watch_entry": {}, "flow": flow or {},
            "asof": asof if asof is not None else
            {"d_even": 20261012, "h_even": 90500,
             "client_d_even": 20261012, "client_lag_days": False}}
    return base


def fresh_db(points):
    """mstat_snapِ ساختگی: points = [(day, h_even, flow_eq_bt)]"""
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE mstat_snap (d_even int, h_even int, ts text, agg text)")
    for d, h, f in points:
        con.execute("INSERT INTO mstat_snap VALUES (?,?,?,?)",
                    (d, h, "x", json.dumps({"flow_eq_bt": f, "val_bt": 30000})))
    con.commit()
    return con


STALE = {"d_even": 20261012, "h_even": 61105, "client_d_even": 20261011,
         "client_lag_days": True}
NEG_FLOW = {"eq_flow_b_toman": -280.8, "fixed_flow_b_toman": -1417.9,
            "eq_inflow": False, "fixed_outflow": True, "gold_flow_b_toman": 0.0}

# ── الف) سناریوهایِ کنترل‌شده ────────────────────────────────────────────────
con = fresh_db([])

v = ME.day_verdict(con, sm(flow=NEG_FLOW, asof=STALE), phase=PH_PRE)
ck("پیش‌آغاز + فلوئِ منفیِ دیروز ⇒ حکم صادر نمی‌شود (بند ۶: نه «وارد نشو»)",
   v["verdict"] == "nodata" and "وارد نشو" not in v["label"], v["label"])
f = [g for g in v["gates"] if g["key"] == "flow"][0]
ck("درِ پولِ حقیقی با client_lag «بدون داده» است، نه «خروج»",
   f["state"] == "nodata" and f["vote"] == 0, f)
ck("مرحلِ بی‌اجازه درِ حکم دیده می‌شود (phase در payload)",
   v.get("phase", {}).get("phase") == "pre_open" and
   v.get("phase", {}).get("verdict_allowed") is False)
ck("وضعیتِ مرحله‌مند پیش‌آغاز: pre_open", v["market_state"]["stage"] == "pre_open",
   v["market_state"])

v = ME.day_verdict(con, sm(macro={"value_hemat": 4.2, "state": "bad",
                                  "label": "نامساعد", "partial_session": True},
                           flow=NEG_FLOW,
                           asof={"d_even": 20261012, "h_even": 90500,
                                 "client_d_even": 20261012, "client_lag_days": False}),
                   phase=PH_CONT)
lq = [g for g in v["gates"] if g["key"] == "liquidity"][0]
ck("09:05 با ۴ همتِ ناقص ⇒ نقدینگی رأیِ منفی نمی‌دهد (بند ۳: ابتدای روز ≠ کل روز)",
   lq["vote"] == 0 and lq["state"] == "mid", lq)
ck("09:05 فلوئِ منفی فقط «شواهدِ اولیه» است، نه حکم",
   v["verdict"] != "avoid" and
   [g for g in v["gates"] if g["key"] == "flow"][0]["vote"] == 0, v["verdict"])
ck("مرحلۀ ۰۹:۰۵ = شکل‌گیریِ داده با شمارۀ دقیقِ دقیقه",
   v["market_state"]["stage"] == "forming" and v["market_state"]["minutes_since_open"] == 5,
   v["market_state"])

pos_pts = [(20261012, h, fl) for h, fl in
           [(93500, 10), (93800, 20), (94100, 30), (94400, 45)]]
con2 = fresh_db(pos_pts)
NEG_BIG = {"eq_flow_b_toman": -50.0, "fixed_flow_b_toman": 10,
           "eq_inflow": False, "fixed_outflow": False, "gold_flow_b_toman": None}
v = ME.day_verdict(con2, sm(macro={"value_hemat": 18.0, "state": "mid",
                                   "label": "متوسط", "partial_session": True},
                            flow=NEG_BIG,
                            asof={"d_even": 20261012, "h_even": 94400,
                                  "client_d_even": 20261012, "client_lag_days": False}),
                   phase=PH_CONT)
f = [g for g in v["gates"] if g["key"] == "flow"][0]
ck("تجمعیِ منفی ولی روندِ امروز صعودی ⇒ رأیِ منفیِ قاطع نمی‌دهد (§۴ تغییرِ جهت)",
   f["vote"] == 0, f)

bad_pts = [(20261012, h, fl) for h, fl in
           [(92000, -10), (93000, -30), (93500, -60), (94000, -100), (94400, -150)]]
con3 = fresh_db(bad_pts)
v = ME.day_verdict(con3, sm(macro={"value_hemat": 18.0, "state": "mid",
                                   "label": "متوسط", "partial_session": True},
                            flow={"eq_flow_b_toman": -150.0, "fixed_flow_b_toman": 10,
                                  "eq_inflow": False, "fixed_outflow": False,
                                  "gold_flow_b_toman": None},
                            asof={"d_even": 20261012, "h_even": 94400,
                                  "client_d_even": 20261012, "client_lag_days": False}),
                   phase=PH_CONT)
f = [g for g in v["gates"] if g["key"] == "flow"][0]
ck("پس از ۰۹:۳۰ با ۳ اختلافِ نزولیِ پیاپی ⇒ رأیِ منفیِ قاطع آزاد می‌شود",
   f["vote"] == -1 and v["verdict"] == "avoid", (f, v["verdict"]))
ck("وضعیتِ «پرریسک» جدا از حکمِ ورود در payload است",
   v["market_state"]["stage"] == "risky" and v["market_state"]["against"],
   v["market_state"])

v = ME.day_verdict(con3, sm(macro={"value_hemat": 6.2, "state": "bad",
                                   "label": "نامساعد", "bad_max": 10.0},
                            flow=NEG_BIG), phase=PH_CLOSED)
ck("رفتارِ کهنیِ نشستِ بسته (جمعِ نهایی ۶.۲ همت ⇒ وارد نشو) دست‌نخورده",
   v["verdict"] == "avoid" and v["market_state"]["stage"] == "after_close",
   (v["verdict"], v["market_state"]["stage"]))

v = ME.day_verdict(con, sm(macro={"value_hemat": 27.0, "state": "good",
                                  "label": "مساعد", "partial_session": True,
                                  "good_min": 20.0},
                           flow={"eq_flow_b_toman": 120.0, "fixed_flow_b_toman": -80.0,
                                 "eq_inflow": True, "fixed_outflow": True,
                                 "gold_flow_b_toman": None},
                           asof={"d_even": 20261012, "h_even": 103000,
                                 "client_d_even": 20261012, "client_lag_days": False}),
                   phase=PH_CONT)
lq = [g for g in v["gates"] if g["key"] == "liquidity"][0]
ck("نقدینگیِ یک‌طرفه: ۲۷ همتِ میانهٔ روز رأیِ مثبتِ قطعی است",
   lq["vote"] == 1, lq)
ck("جهتِ شواهد مثبت + مرحلهٔ تأیید",
   v["market_state"]["evidence_direction"] == "مثبت" and
   v["market_state"]["stage"] in ("confirmed", "establishing"), v["market_state"])

# کنترلِ منفیِ درِ trend: کاشتنِ نقطۀ «آینده» نباید داوریِ لحظۀ پیش را عوض کند
pts = [(20261012, h, fl) for h, fl in
       [(92000, 10), (93000, 20), (93500, 30), (94000, 40)]]
con4 = fresh_db(pts + [(20261012, 95500, -9999)])
v_now = ME.day_verdict(con4, sm(macro={"value_hemat": 18.0, "state": "mid",
                                       "label": "متوسط", "partial_session": True},
                                flow=NEG_BIG,
                                asof={"d_even": 20261012, "h_even": 94000,
                                      "client_d_even": 20261012, "client_lag_days": False}),
                       phase=PH_CONT)
ck("بی‌نگاه‌به‌آینده: نقطۀ ۰۹:۵۵ِ کاشته‌شده در داوریِ ۰۹:۴۰ راه ندارد",
   [g for g in v_now["gates"] if g["key"] == "flow"][0]["vote"] == 0, v_now)
trend, n = ME._flow_trend(con4, 20261012, 94000)
ck("trend فقط نقاطِ <= لحظه را می‌شمارد", n == 3 and trend == "improving", (trend, n))

# متن‌ها: رقمِ لاتین در هیچ متنِ دیدنیِ جدیدی نباشد
ms = v["market_state"]
txt = "".join([str(ms.get(k)) for k in ("stage_label", "since_open_text",
                                        "evidence_strength", "pace_note")])
ck("متنِ وضعیت با رقمِ فارسی نوشته می‌شود",
   not any(c.isascii() and c.isdigit() for c in txt), txt)

# ── ب) replayِ mstat_snapِ واقعی (بی‌آینده، روزهایِ رفتارِ متفاوت) ──────────
DB = os.path.join(ROOT, "market.db")
if not os.path.exists(DB):
    SKIP += 1
    print("  SKIP  market.db نیست — replayِ تاریخی انجام نشد")
else:
    con5 = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    days = [int(r[0]) for r in con5.execute(
        "SELECT d_even, COUNT(*) c FROM mstat_snap GROUP BY d_even HAVING c>=40"
        " ORDER BY d_even DESC LIMIT 8").fetchall()]
    if len(days) < 3:
        ck("دست‌کم ۳ روزِ پرنقطه برای replay", None)
    else:
        n_days = 0
        for d in days:
            rows = con5.execute(
                "SELECT h_even, agg FROM mstat_snap WHERE d_even=? AND h_even>=? AND h_even<=?"
                " ORDER BY h_even", (d, ME.SESSION_OPEN_HM, ME.SESSION_CLOSE_HM)).fetchall()
            pts = []
            for h, a in rows:
                try:
                    j = json.loads(a)
                except Exception:
                    continue
                if isinstance(j.get("flow_eq_bt"), (int, float)):
                    pts.append((int(h), float(j["flow_eq_bt"]), float(j.get("val_bt") or 0)))
            if len(pts) < 40:
                continue
            n_days += 1
            ph_day = ph("continuous", True, True, COMP_CONT, day=d)
            # داوریِ هر نقطه فقط با تاریخچۀ <= همان نقطه (ساختِ replay با کپیِ تدریجی)
            seen = []
            bad_early = bad_formation = 0
            last_avoid = None
            for i, (h, fl, val) in enumerate(pts):
                seen.append((d, h, fl))
                if h < 93000:                      # پیش از ۰۹:۳۰
                    conr = fresh_db(seen)
                    vr = ME.day_verdict(conr, sm(
                        macro={"value_hemat": None, "state": "nodata",
                               "partial_session": True},
                        flow={"eq_flow_b_toman": fl, "fixed_flow_b_toman": 0.0,
                              "eq_inflow": fl > 0, "fixed_outflow": False,
                              "gold_flow_b_toman": None},
                        asof={"d_even": d, "h_even": h, "client_d_even": d,
                              "client_lag_days": False}), phase=ph_day)
                    if vr["verdict"] == "avoid":
                        bad_early += 1
                    if vr["market_state"]["stage"] != "forming":
                        bad_formation += 1
            ck(f"replay {d}: هیچ «وارد نشو»ای در نیم‌ساعتِ اول صادر نشد ({len(pts)} نقطه)",
               bad_early == 0, bad_early)
            ck(f"replay {d}: هر نقطۀ پیش از ۰۹:۳۰ در مرحلۀ شکل‌گیری است",
               bad_formation == 0, bad_formation)
            # کنترلِ instrument: درِ منفی روی همین روزِ واقعی کار می‌کند؟
            # آخرین ۶ نقطه اگر پیوسته نزولی باشند، داوریِ آخر باید قاطع شود
            tail = [p[1] for p in pts[-ME.FLOW_CONFIRM_DELTAS - 1:]]
            deltas = [tail[i + 1] - tail[i] for i in range(len(tail) - 1)]
            if all(dl <= 0 for dl in deltas) and pts[-1][1] < 0:
                conr = fresh_db([(d, h, fl) for h, fl, _v in pts])
                vr = ME.day_verdict(conr, sm(
                    macro={"value_hemat": 18.0, "state": "mid", "label": "متوسط",
                           "partial_session": True},
                    flow={"eq_flow_b_toman": pts[-1][1], "fixed_flow_b_toman": 0.0,
                          "eq_inflow": False, "fixed_outflow": False,
                          "gold_flow_b_toman": None},
                    asof={"d_even": d, "h_even": pts[-1][0], "client_d_even": d,
                          "client_lag_days": False}), phase=ph_day)
                last_avoid = vr["verdict"]
                ck(f"replay {d}: روزِ نزولیِ پایانی ⇒ درِ منفی زنده است (کنترلِ instrument)",
                   last_avoid == "avoid", vr["label"])
        ck("دست‌کم ۳ روزِ واقعی replay شد", (n_days >= 3) if n_days >= 1 else None, n_days)
    con5.close()

print("─" * 72)
print(f"نتیجۀِ گاردِ وضعیتِ زمان‌مند: {PASS}_pass / {FAIL}_fail / {SKIP}_skip")
sys.exit(1 if FAIL else 0)
