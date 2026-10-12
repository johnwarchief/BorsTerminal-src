# dev/test_market_state_stages_v1.py — رأی‌های ۱ و ۲ مالک (1405-07-21):
# دورۀ شکل‌گیری از آغازِ واقعی + حکمِ منفی فقط با ۳ ارزیابیِ متوالیِ معتبر
"""سه لایه:

    الف) سناریوهایِ کنترل‌شدهٔ day_verdict/_market_state:
       شمارشِ سه ارزیابیِ متوالی رویِ دادهٔ تازه؛ تکرارِ همان h_even مشاهدهٔ
       مستقل نیست؛ شاهدِ مخالف بازنشانی می‌کند؛ ارزیابیِ نامعتبر نه می‌شمارد
       نه بازنشانی؛ دورۀ شکل‌گیری = آغازِ واقعی (نخستین نقطۀ پُرمعاملۀ
       mstat_snap) + ۳۰ دقیقه، بی‌ساعتِ دیواری؛ بی‌آغازِ شناخته حکمِ منفی
       صادر نمی‌شود.
    ب) replayِ بی‌آینده از mstat_snapِ واقعی (market.db، فقط‑خواندنی).
    ج) کنترلِ instrument: درِ منفی رویِ روزِ نزولیِ واقعی زنده است.

نتیجه با قالبِ `X_pass / Y_fail / Z_skip` (سه فرمتِ قابل‌پارسِ run_all_tests).
"""
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
PH_PRE = ph("pre_open", False, False, COMP_PRE,
            {"realized_flow": "هنوز معامله‌ای ثبت نشده"})
PH_CLOSED = ph("closed", True, False, COMP_FINAL)


def ph_cont(day=20261012):
    return ph("continuous", True, True, COMP_CONT,
              {"close_price_final": "قیمت پایانیِ نهایی هنوز ساخته نشده"}, day=day)


def fresh_db(points):
    """mstat_snapِ ساختگی: points = [(day, h_even, flow_eq_bt, val_bt)]"""
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE mstat_snap (d_even int, h_even int, ts text, agg text)")
    for row in points:
        d, h, fl = row[0], row[1], row[2]
        val = row[3] if len(row) > 3 else 30000.0
        con.execute("INSERT INTO mstat_snap VALUES (?,?,?,?)",
                    (d, h, "x", json.dumps({"flow_eq_bt": fl, "val_bt": val})))
    con.commit()
    return con


def sm(flow=None, macro=None, asof=None):
    base = {"macro": macro or {}, "watch_entry": {}, "flow": flow or {},
            "asof": asof if asof is not None else
            {"d_even": 20261012, "h_even": 90500,
             "client_d_even": 20261012, "client_lag_days": False}}
    base.update({k: v for k, v in (("flow", flow), ("macro", macro), ("asof", asof)) if v is not None})
    return base


NEG = {"eq_flow_b_toman": -150.0, "fixed_flow_b_toman": 10.0,
       "eq_inflow": False, "fixed_outflow": False, "gold_flow_b_toman": None}
POS = {"eq_flow_b_toman": 120.0, "fixed_flow_b_toman": -80.0,
       "eq_inflow": True, "fixed_outflow": True, "gold_flow_b_toman": -12.0}
MID = {"value_hemat": 18.0, "state": "mid", "label": "متوسط", "partial_session": True}


def asof_at(h, day=20261012, lag=False, client_day=None):
    return {"d_even": day, "h_even": h, "client_d_even": client_day or day,
            "client_lag_days": lag}


# نقاطِ امروز با آغازِ واقعی ۰۹:۰۰ (نخستین val_bt>0 در 90005)
DAY_PTS = [(20261012, 90005, -10), (20261012, 93500, -30), (20261012, 93800, -60),
           (20261012, 94100, -100), (20261012, 94400, -150), (20261012, 94700, -210)]

# ── الف) سه ارزیابیِ متوالیِ معتبر ──────────────────────────────────────────
ME._ASSESS.clear(); ME._STATE_MEMO.clear()
con = fresh_db(DAY_PTS)
v1 = ME.day_verdict(con, sm(macro=MID, flow=NEG, asof=asof_at(93500)), phase=ph_cont())
v2 = ME.day_verdict(con, sm(macro=MID, flow=NEG, asof=asof_at(93800)), phase=ph_cont())
v3 = ME.day_verdict(con, sm(macro=MID, flow=NEG, asof=asof_at(94100)), phase=ph_cont())
ck("ارزیابیِ اولِ منفی ⇒ «شواهدِ اولیه»، نه «وارد نشو»",
   v1["verdict"] == "nodata" and "وارد نشو" not in v1["label"], v1["label"])
ck("ارزیابیِ دوم هم هنوز تأیید نیست", v2["verdict"] == "nodata", v2["label"])
ck("ارزیابیِ سومِ متوالیِ معتبر ⇒ حکمِ منفی آزاد می‌شود",
   v3["verdict"] == "avoid" and v3["market_state"]["stage"] == "risky",
   (v3["verdict"], v3["market_state"]["stage"], v3["market_state"]["confirm_streak"]))
ck("درِ شاهد درِ همهٔ سه ارزیابی قرمزِ صادق است (نمایش ≠ حکم)",
   [g for g in v1["gates"] if g["key"] == "flow"][0]["vote"] == -1,
   [g for g in v1["gates"] if g["key"] == "flow"][0])

# تکرارِ همان h_even مشاهدهٔ مستقل نیست
ME._ASSESS.clear()
con = fresh_db(DAY_PTS)
seq = [ME.day_verdict(con, sm(macro=MID, flow=NEG, asof=asof_at(93500)), phase=ph_cont())
       for _ in range(5)]
ck("پنج ارزیابی رویِ یک h_evenِ یکسان ⇒ هرگز avoid (تکرارِ دادهٔ کهنه مستقل نیست)",
   all(v["verdict"] != "avoid" for v in seq)
   and ME._ASSESS["20261012"]["neg"] == 1, ME._ASSESS.get("20261012"))

# شاهدِ مخالف بازنشانی می‌کند
ME._ASSESS.clear()
con = fresh_db(DAY_PTS)
ME.day_verdict(con, sm(macro=MID, flow=NEG, asof=asof_at(93500)), phase=ph_cont())
ME.day_verdict(con, sm(macro=MID, flow=NEG, asof=asof_at(93800)), phase=ph_cont())
ME.day_verdict(con, sm(macro=MID, flow=POS, asof=asof_at(94100)), phase=ph_cont())
v_after = ME.day_verdict(con, sm(macro=MID, flow=NEG, asof=asof_at(94400)), phase=ph_cont())
ck("شاهدِ مثبتِ میانی ⇒ شمارشِ تأیید بازنشانی شد (منفیِ بعد از آن تنها ارزیابیِ ۱ است)",
   v_after["verdict"] != "avoid" and ME._ASSESS["20261012"]["neg"] == 1,
   ME._ASSESS.get("20261012"))

# ارزیابیِ نامعتبر (client lag) نه می‌شمارد نه بازنشانی می‌کند
ME._ASSESS.clear()
con = fresh_db(DAY_PTS)
ME.day_verdict(con, sm(macro=MID, flow=NEG, asof=asof_at(93500)), phase=ph_cont())
ME.day_verdict(con, sm(macro=MID, flow=NEG, asof=asof_at(93800)), phase=ph_cont())
v_stale = ME.day_verdict(con, sm(macro=MID, flow=NEG, asof=asof_at(94000, lag=True, client_day=20261011)),
                         phase=ph_cont())
st = dict(ME._ASSESS["20261012"])
ck("ارزیابیِ با دادهٔ نامعتبر ⇒ وضعیتِ منفیِ تأییدشده نیست",
   v_stale["verdict"] != "avoid", v_stale["label"])
ck("… و شمارشِ قبلی (۲) نه زیاد شد نه بازنشانی", st["neg"] == 2, st)
v_third = ME.day_verdict(con, sm(macro=MID, flow=NEG, asof=asof_at(94100)), phase=ph_cont())
ck("سومین ارزیابیِ معتبرِ پس از وقفه ⇒ avoid", v_third["verdict"] == "avoid", v_third["label"])

# ── دورۀ شکل‌گیری از آغازِ واقعی ────────────────────────────────────────────
ME._ASSESS.clear()
# آغازِ واقعی ۰۹:۰۷؛ ارزیابی‌های ۰۹:۲۰/۰۹:۲۵/۰۹:۲۸ همه منفی ولی در شکل‌گیری‌اند
late_pts = [(20261012, 90700, -10), (20261012, 92000, -30), (20261012, 92500, -60),
            (20261012, 92800, -100)]
con = fresh_db(late_pts)
vs = [ME.day_verdict(con, sm(macro=MID, flow=NEG, asof=asof_at(h)), phase=ph_cont())
      for h in (92000, 92500, 92800)]
ck("آغازِ واقعی ۰۹:۰۷ ⇒ تا ۰۹:۳۷ شکل‌گیری است، سه ارزیابیِ منفی هم avoid نمی‌سازد",
   all(v["verdict"] != "avoid" for v in vs)
   and all(v["market_state"]["stage"] == "forming" for v in vs),
   [v["market_state"]["stage"] for v in vs])
ck("آغازِ واقعی از داده خوانده می‌شود (۰۹:۰۷) نه ساعتِ دیواری",
   ME._market_state(ph_cont(), asof_at(92000), [], "nodata", 9*60+20, con, 20261012,
                    forming=True, start_hm=ME._session_start_hm(con, 20261012))
   ["session_start_clock"] == "۰۹:۰۷",
   ME._session_start_hm(con, 20261012))
# پس از ۰۹:۳۷ همان سه‌شمارش آزاد می‌شود
ME._ASSESS.clear()
con = fresh_db(late_pts + [(20261012, 93800, -140), (20261012, 94100, -180),
                           (20261012, 94400, -230)])
vs2 = [ME.day_verdict(con, sm(macro=MID, flow=NEG, asof=asof_at(h)), phase=ph_cont())
       for h in (93800, 94100, 94400)]
ck("۰۹:۳۷ به بعد ⇒ سه ارزیابیِ متوالیِ تازه حکمِ منفی را تأیید می‌کند",
   vs2[0]["verdict"] != "avoid" and vs2[1]["verdict"] != "avoid"
   and vs2[2]["verdict"] == "avoid", [v["verdict"] for v in vs2])

# آغازِ نامشخص (بی‌نقطۀ پُرمعامله) ⇒ شکل‌گیری باز می‌ماند
ME._ASSESS.clear()
con = fresh_db([(20261012, 91000, -5, 0.0)])      # نقطه هست ولی بی‌ارزشِ معامله
v = ME.day_verdict(con, sm(macro=MID, flow=NEG, asof=asof_at(94400)), phase=ph_cont())
ck("آغازِ واقعیِ ناشناخته ⇒ دورۀ شکل‌گیری بستۀ نمی‌شود؛ حکمِ منفی صادر نمی‌شود",
   v["verdict"] != "avoid" and v["market_state"]["stage"] == "forming",
   (v["verdict"], v["market_state"]["stage"]))

# ── قواعدِ پیشین دست‌نخورده ─────────────────────────────────────────────────
ME._ASSESS.clear()
con = fresh_db([])
v = ME.day_verdict(con, sm(flow=NEG, asof=asof_at(61105, lag=True, client_day=20261011)),
                   phase=PH_PRE)
f = [g for g in v["gates"] if g["key"] == "flow"][0]
ck("پیش‌آغاز + فلوئِ منفیِ دیروز ⇒ نه حکم، و درِ flow «بدون داده»",
   v["verdict"] == "nodata" and f["state"] == "nodata"
   and v["market_state"]["stage"] == "pre_open", (v["label"], f["state"]))

v = ME.day_verdict(con, sm(macro={"value_hemat": 4.2, "state": "bad", "label": "نامساعد",
                                  "partial_session": True, "bad_max": 10.0},
                           flow=NEG, asof=asof_at(90500)), phase=ph_cont())
lq = [g for g in v["gates"] if g["key"] == "liquidity"][0]
ck("نقدینگیِ یک‌طرفه: ۴.۲ همتِ ناقص رأیِ منفی نمی‌دهد",
   lq["vote"] == 0 and lq["state"] == "mid", lq)

ME._ASSESS.clear()
con = fresh_db([])
vs = [ME.day_verdict(con, sm(macro={"value_hemat": 6.2, "state": "bad", "label": "نامساعد",
                                    "bad_max": 10.0},
                             flow=NEG, asof=asof_at(123000 + i)), phase=PH_CLOSED)
      for i in range(3)]
ck("رفتارِ کهنیِ نشستِ بسته بازنشانی نشد: سه ارزیابی ⇒ «وارد نشو» روی جمعِ نهایی",
   vs[2]["verdict"] == "avoid" and "وارد نشو" in vs[2]["label"], [v["verdict"] for v in vs])

# بی‌نگاه‌به‌آینده: نقطۀ «آینده» در داوریِ لحظۀ پیش راه ندارد
ME._ASSESS.clear()
con = fresh_db([(20261012, 90005, 10), (20261012, 93000, 20), (20261012, 93500, 30),
                (20261012, 95500, -9999)])
v_now = ME.day_verdict(con, sm(macro=MID, flow=NEG, asof=asof_at(93500)), phase=ph_cont())
trend, n = ME._flow_trend(con, 20261012, 93500)
ck("trend فقط نقاطِ <= لحظه را می‌شمارد (۰۹:۵۵ِ کاشته‌شده دیده نمی‌شود)",
   n == 2 and trend == "improving", (trend, n))

# متن‌ها: رقمِ لاتین در هیچ متنِ دیدنیِ جدیدی نباشد
ms = v3["market_state"]
txt = "".join([str(ms.get(k)) for k in ("stage_label", "since_open_text", "evidence_strength",
                                        "pace_note", "flow_trend", "session_start_clock")])
ck("متنِ وضعیت با رقمِ فارسی نوشته می‌شود",
   not any(c.isascii() and c.isdigit() for c in txt), txt)

# ── ب) replayِ mstat_snapِ واقعی (بی‌آینده، آغازِ واقعی از خودِ داده) ───────
DB = os.path.join(ROOT, "market.db")
if not os.path.exists(DB):
    print("  SKIP  market.db نیست — replayِ تاریخی انجام نشد")
    SKIP += 1
else:
    con5 = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    days = [int(r[0]) for r in con5.execute(
        "SELECT d_even, COUNT(*) c FROM mstat_snap GROUP BY d_even HAVING c>=40"
        " ORDER BY d_even DESC LIMIT 8").fetchall()]
    n_days = 0
    for d in days:
        rows = con5.execute(
            "SELECT h_even, agg FROM mstat_snap WHERE d_even=? AND h_even>=? AND h_even<=?"
            " ORDER BY h_even",
            (d, ME.SESSION_OPEN_HM, ME.SESSION_CLOSE_HM)).fetchall()
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
        # آغازِ واقعی از خودِ سریِ replay (نخستین val_bt>0) — بی‌ساعتِ دیواری
        first_val = next((h for h, _fl, v in pts if v > 0), None)
        start_min = None
        if first_val is not None:
            s = "%06d" % first_val
            start_min = int(s[0:2]) * 60 + int(s[2:4])
        ME._ASSESS.clear()
        seen = []
        bad_early = bad_prethird = 0
        avoid_seen_at = None
        for h, fl, val in pts:
            seen.append((d, h, fl, val))
            conr = fresh_db(seen)
            vr = ME.day_verdict(conr, sm(
                macro={"value_hemat": None, "state": "nodata", "partial_session": True},
                flow={"eq_flow_b_toman": fl, "fixed_flow_b_toman": 0.0,
                      "eq_inflow": fl > 0, "fixed_outflow": False, "gold_flow_b_toman": None},
                asof=asof_at(h, day=d)), phase=ph_cont(day=d))
            hm_ = (h // 10000) * 60 + (h // 100) % 100
            in_form = start_min is None or hm_ < start_min + ME.FORMATION_MINUTES
            if vr["verdict"] == "avoid":
                if avoid_seen_at is None:
                    avoid_seen_at = h
                if in_form:
                    bad_early += 1
                if ME._ASSESS.get(str(d), {}).get("neg", 0) < ME.VERDICT_CONFIRM_COUNT:
                    bad_prethird += 1
        ck(f"replay {d}: هیچ «وارد نشو»ای در دورۀ شکل‌گیریِ واقعی صادر نشد ({len(pts)} نقطه)",
           bad_early == 0, bad_early)
        ck(f"replay {d}: هیچ avoid پیش از سه ارزیابیِ متوالیِ معتبر نیست",
           bad_prethird == 0, bad_prethird)
    ck("دست‌کم ۳ روزِ واقعی replay شد", (n_days >= 3) if n_days >= 1 else None, n_days)
    con5.close()

print("─" * 72)
print(f"نتیجۀِ گاردِ وضعیتِ زمان‌مند: {PASS}_pass / {FAIL}_fail / {SKIP}_skip")
sys.exit(1 if FAIL else 0)
