# -*- coding: utf-8 -*-
"""_audit/ta_fixture_check.py — پخشِ دوبارۀ فیکسچرهایِ TradersArena از مسیرِ محاسباتیِ خودِ برنامه

منطقِ داوری (هر سه درِ اجرا حساب می‌شوند؛ هیچ شمارِ ثابتی در فایل نیست):
  1) هویت‌هایِ درونِ فیکسچر — اتحادی‌هایِ جبریِ خودِ TA (m=st+sf+nsf؛ i5=i7−i10؛
     market0.s==histo.s1[1:13]؛ pp+pm==sum(s1)؛ plus[-1]==pp[0]). شکستنِ هر یک
     یعنی رمزگشاییِ docs/TA-SCOPE-DECODE.md رویِ این فیکسچر باطل است ⇒ unexplained.
  2) ثباتِ مسیرِ ما — مقدارِ «ما» درِ ماتریس باید با بازمحاسبۀ mstat_engine (بانکِ
     خودی، mode=ro) بخواند. اگر asof (h_even) تکان خورده باشد و عدد عوض شود:
     «snapshot-moved» — توضیح دارد (همین قانونِ دو-فید-در-دو-ساعت که هشدارِ جعلی
     ساخت؛ پس صریح برچسب می‌خورد و شمار می‌شود). اگر asof یکی باشد و عدد بیرونِ
     تلورانس فرق کند ⇒ unexplained.
  3) پوششِ طبقه — هر سطرِ غیروِ «match» باید طبقه‌اش یکی از پنج‌گانۀ
     rounding / snapshot-timing / unit-scale / definition divergence /
     genuinely missing data باشد و «شاهدِ عددی» داشته باشد؛ نداشتن ⇒ unexplained.
  4) کنترلِ منفی (حساسیت) — دو تخریبِ عمدی رویِ کپیِ حافظه: درصدِ شاخص (سطرِ
     match) 0٫35 واحد جابه‌جا می‌شود و s1 یک سطلِ دروغین می‌گیرد. اگر چک‌کننده
     این دو را نگیرد، «۰ ناهمخوانی» بی‌معناست ⇒ CONTROL=FAILED.

اجرا (بی‌شبکه؛ فقط فیکسچرها + market.db با قفلِ خواندنی):
    cd BorsTerminal && export PYTHONIOENCODING=utf-8
    python _audit/ta_fixture_check.py
خروجِ صفر ⇔ «0 unexplained discrepancies».
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import bors_config                       # noqa: E402
import mstat_engine as ME                # noqa: E402
import ta_parity_matrix as T             # noqa: E402  (برای normname/ثابت‌های یکا)

RIAL_TO_BT = T.RIAL_TO_BT
RIAL_TO_MTON = T.RIAL_TO_MTON
SHARES_TO_B = T.SHARES_TO_B
FIX = os.path.join(HERE, "fixtures")


def load_fixtures():
    out = {}
    for key in ("market0", "histo", "totals0", "industries", "mainwatch"):
        p = os.path.join(FIX, "ta_%s.json" % key)
        blob = json.load(open(p, encoding="utf-8"))
        out[key] = {"payload": blob["payload"], "fetched_at": blob.get("fetched_at_local")}
    return out


class Ck:
    """شمارشگرِ حساس — هر «بررسی» یک record می‌گیرد؛ جمع‌ها هیچ‌وقت دستی نیستند."""

    def __init__(self):
        self.records = []

    def add(self, name, kind, status, detail=""):
        self.records.append({"name": name, "kind": kind, "status": status, "detail": detail})

    def counts(self):
        c = {}
        for r in self.records:
            c[r["status"]] = c.get(r["status"], 0) + 1
        c["total"] = len(self.records)
        return c


def identity_checks(fx, ck):
    m0 = fx["market0"]["payload"]
    histo = fx["histo"]["payload"]
    tot = fx["totals0"]["payload"]
    for i, label in ((0, "حجم"), (1, "ارزش"), (5, "جریان")):
        m = float(m0["m"][i])
        s = sum(float(m0[k][i]) for k in ("st", "sf", "nsf"))
        rel = abs(s - m) / m if m else 0.0
        ok = rel <= 2e-12      # تلورانسِ سرگردانیِ float؛ «۰٫۰۰۰٪» یعنی همین
        ck.add("m = st+sf+nsf (%s)" % label, "identity",
               "ok" if ok else "UNEXPLAINED",
               "m=%s sum=%s rel=%.2e" % (m, s, rel))
    for key in ("m", "st", "sf", "nsf", "cf", "scf", "lf", "afl"):
        a = m0.get(key) or []
        if len(a) <= 10:
            continue
        lhs, rhs = float(a[T.I_FLOW] or 0.0), float(a[T.I_RBUY] or 0.0) - float(a[T.I_RSELL] or 0.0)
        if abs(lhs) < 1.0:
            continue
        rel = abs(lhs - rhs) / abs(lhs)
        # st/afl طبقِ TA-SCOPE-DECODE §۴ «سه سطرِ بی‌اتحاد»اند — شکستشان تعریفِ شناخته‌شده است،
        # نه رمزگشاییِ شکسته؛ برایِ همین «known-exception» می‌شوند (با عدد، بی‌ادعایِ برابری).
        known = key in ("st", "afl", "um") and rel > 1e-9
        ck.add("%s: i5=i7−i10" % key, "identity",
               "ok" if rel <= 1e-9 else ("known-exception" if known else "UNEXPLAINED"),
               "i5=%.0f i7−i10=%.0f rel=%.2e" % (lhs, rhs, rel))
    s_ok = (m0.get("s") == histo["s1"][1:13])
    ck.add("market0.s == s1[1:13]", "identity", "ok" if s_ok else "UNEXPLAINED",
           "%s vs %s" % (m0.get("s"), histo["s1"][1:13]))
    pp = float((m0.get("pp") or [0])[0]); pm = float((m0.get("pm") or [0])[0])
    ck.add("pp+pm == sum(s1)", "identity",
           "ok" if pp + pm == sum(histo["s1"]) else "UNEXPLAINED",
           "pp=%s pm=%s sum_s1=%s" % (pp, pm, sum(histo["s1"])))
    ck.add("totals0.plus[-1] == pp", "identity",
           "ok" if float(tot["plus"][-1]) == pp else "UNEXPLAINED",
           "plus_last=%s pp=%s" % (tot["plus"][-1], pp))


def our_values(conn):
    """همه‌چیز از لایۀ محاسباتیِ خودِ برنامه — بی‌HTTP، بی‌عددِ واردشده."""
    s = ME.summary(conn)
    rows = {r["key"]: r for r in s["rows"]}
    th = ME.thermometer(conn, "all")
    de = ME.depth(conn, "all")
    deq = ME.depth(conn, "eq_all")
    cs = ME.client_split(conn, "all")
    sm = ME.smart_money(conn)
    ind = ME.industries(conn)
    hist = ME.histogram(conn, "all")
    mw = ME.mainwatch(conn, "eq_all", "", "clock", True, 20)
    return {"asof": s["asof"], "s": s, "rows": rows, "th": th, "de": de, "deq": deq,
            "cs": cs, "sm": sm, "ind": ind, "hist": hist, "mw": mw}


def pair_metrics(env, fx):
    """(نامِ سطرِ ماتریس، ما، او، تلورانس) — همان نام‌ها؛ ماتریس فقط طبقه‌اش را می‌دهد."""
    m0 = fx["market0"]["payload"]
    tot = fx["totals0"]["payload"]
    rows, th, de, deq, cs = env["rows"], env["th"], env["de"], env["deq"], env["cs"]
    idx = (env["sm"].get("macro") or {}).get("index") or {}
    ind_rows = env["ind"]["rows"] or []
    ta_ind = fx["industries"]["payload"]
    matched = []
    for tr in ta_ind:
        k = T.normname(str(tr[1]))
        for orow in ind_rows:
            k2 = T.normname(orow["industry"])
            if k == k2 or k in k2 or k2 in k:
                matched.append((tr[1], tr[9], orow["avg_pct"]))
                break
    mv = lambda v: None if v is None else float(v)
    def top(seq, gi):
        vals = [x for x in seq if x[gi] is not None]
        vals.sort(key=lambda x: x[gi], reverse=True)
        return (vals[0][gi] if vals else None), (vals[-1][gi] if vals else None)
    o_top = top(matched, 2)
    t_top = top(matched, 1)
    pp = firstn(m0, "pp"); pm = firstn(m0, "pm")
    ratio = None
    if pp and pm:
        ratio = round(100.0 * pp / (pp + pm), 1)
    return [
        ("شاخص کل (مقدار)", idx.get("last"), mv((m0.get("iw") or [None])[0]), 0.05),
        ("شاخص کل (تغییر روز)", idx.get("change"), mv((m0.get("iw") or [None, None])[1]), 0.05),
        ("شاخص کل (درصد روز)", idx.get("pct"), mv((m0.get("iw") or [None, None, None])[2]), 0.02),
        ("تعداد مثبت", th.get("positive"), pp, 0),
        ("تعداد منفی", th.get("negative"), pm, 0),
        ("درصد مثبت/منفی", th.get("positive_pct"), ratio, 0.5),
        ("صف خرید (شمارِ نماد در صف)", de.get("buy_queue_count"), (tot.get("bq") or [None])[-1], 0),
        ("صف فروش (شمارِ نماد در صف)", de.get("sell_queue_count"), (tot.get("sq") or [None])[-1], 0),
        ("ارزش معاملات — کل بازار (م.ت)", rows.get("all", {}).get("value_b_toman"),
         mv(m0["m"][T.I_VAL]) / RIAL_TO_BT, 30.0),
        ("ارزش — سهام و حق تقدم (م.ت)", rows.get("stock_right", {}).get("value_b_toman"),
         mv(m0["st"][T.I_VAL]) / RIAL_TO_BT, 30.0),
        ("ارزش — ص.سهامی و مختلط (م.ت)", rows.get("eq_fund", {}).get("value_b_toman"),
         mv(m0["sf"][T.I_VAL]) / RIAL_TO_BT, 30.0),
        ("ارزش — ص.درآمد ثابت (م.ت)", rows.get("fixed_fund", {}).get("value_b_toman"),
         mv(m0["nsf"][T.I_VAL]) / RIAL_TO_BT, 30.0),
        ("حجم معاملات — کل بازار (میلیارد سهم)", rows.get("all", {}).get("volume_b_shares"),
         mv(m0["m"][T.I_VOL]) / SHARES_TO_B, 0.6),
        ("ورود/خروج پول — کل بازار (م.ت)", rows.get("all", {}).get("money_flow_b_toman"),
         mv(m0["m"][T.I_FLOW]) / RIAL_TO_BT, 40.0),
        ("ورود/خروج پول — سهام و حق تقدم (م.ت)", rows.get("stock_right", {}).get("money_flow_b_toman"),
         mv(m0["st"][T.I_FLOW]) / RIAL_TO_BT, 40.0),
        ("ورود/خروج پول — ص.درآمد ثابت (م.ت)", rows.get("fixed_fund", {}).get("money_flow_b_toman"),
         mv(m0["nsf"][T.I_FLOW]) / RIAL_TO_BT, 40.0),
        ("قدرت خریدار (نسرتِ سرانه) — کل بازار", rows.get("all", {}).get("buy_power"),
         mv(m0["m"][T.I_POW]), 0.02),
        ("سرانۀ خرید (م.ت) — کل بازار", rows.get("all", {}).get("pc_buy_m_toman"),
         mv(m0["m"][T.I_PC_BUY]) / RIAL_TO_MTON, 1.0),
        ("سرانۀ فروش (م.ت) — کل بازار", rows.get("all", {}).get("pc_sell_m_toman"),
         mv(m0["m"][T.I_PC_SELL]) / RIAL_TO_MTON, 1.0),
        ("تعداد خریدارِ حقیقی (شمار)", (cs.get("retail") or {}).get("buy_count"),
         mv(m0["m"][T.I_COUNT_BUY]), 0),
        ("تعداد فروشنندۀ حقیقی (شمار)", (cs.get("retail") or {}).get("sell_count"),
         mv(m0["m"][T.I_COUNT_SELL]), 0),
        ("صنایع — برترین صنعتِ مثبت (%)", o_top[0], t_top[0], 0.3),
        ("صنایع — بدترین صنعتِ منفی (%)", o_top[1], t_top[1], 0.3),
        ("صنایع — پوششِ گروه‌ها (شمار)", len(ind_rows), len(ta_ind), 0),
        ("پهنای بازار — شمارِ کلِ سطل‌ها (breadth)",
         sum(x["count"] for x in env["hist"]["histo12"]), sum(fx["histo"]["payload"]["s1"]), 0),
    ]


def firstn(m0, key):
    a = m0.get(key)
    return None if not a else float(a[0])


CLASS5 = ("rounding", "snapshot-timing", "unit-scale", "definition divergence",
          "genuinely missing data")


def coverage_and_stability(mat, env, fx, ck):
    row_by_metric = {r["metric"]: r for r in mat["rows"]}
    ours_now = dict((n, (ov, tv, tol)) for n, ov, tv, tol in pair_metrics(env, fx))
    stored_asof = (mat.get("meta") or {}).get("our_asof") or {}
    moved = stored_asof.get("h_even") != (env.get("asof") or {}).get("h_even") or \
        stored_asof.get("d_even") != (env.get("asof") or {}).get("d_even")
    for name, r in row_by_metric.items():
        if r["verdict"] == "missing-source":
            if r.get("cause_class") == "genuinely missing data" or "بدونِ منبع" in (r["their_ref"] + r["note"]):
                ck.add(name, "coverage", "ok", "بی‌منبعِ مستند: " + (r.get("cause_evidence") or r["note"])[:60])
            else:
                ck.add(name, "coverage", "UNEXPLAINED", "missing-source بی‌مستند")
            continue
        cur = ours_now.get(name)
        if cur is None:
            # سطرهایِ بی‌مقدارِ عددی (مثل صفِ ارزشِ ترکیبی) — فقط طبقات باید اعلام‌شده باشد
            if r.get("cause_class") in CLASS5 and r.get("cause_evidence"):
                ck.add(name, "coverage", "ok", "طبقه+شاهد دارد")
            else:
                ck.add(name, "coverage", "UNEXPLAINED", "بی‌طبقه/بی‌شاهد")
            continue
        ov, tv, tol = cur
        # (الف) ثباتِ مسیرِ ما: «ما»یِ ذخیرۀ ماتریس در برابرِ بازمحاسبه
        sv = r.get("our")
        try:
            svf, ovf = float(sv), float(ov)
            d = ovf - svf
            if abs(d) <= max(tol, 1e-9):
                ck.add(name + " ⇄ path", "stability", "ok", "بازمحاسبه خواند")
            elif moved:
                ck.add(name + " ⇄ path", "stability", "snapshot-moved",
                       "Δ=%s (h_even %s→%s)" % (round(d, 2), stored_asof.get("h_even"),
                                                env["asof"].get("h_even")))
            else:
                ck.add(name + " ⇄ path", "stability", "UNEXPLAINED",
                       "مقدارِ خودی بی‌تکانیِ asof جابه‌جا شد: Δ=%s" % round(d, 3))
        except (TypeError, ValueError):
            ck.add(name + " ⇄ path", "stability", "ok-nonnumeric", "مقدارِ ذخیره ترکیبی/متنی")
        # (ب) طبقهٔ غیروِ-match
        if r["verdict"] == "match":
            if ov is None or tv is None:
                ck.add(name + " ⇄ delta", "delta", "UNEXPLAINED", "match بی‌عدد")
            elif abs(float(ov) - float(tv)) <= max(tol, 1e-9):
                ck.add(name + " ⇄ delta", "delta", "ok", "match همچنان برقرار")
            elif moved:
                ck.add(name + " ⇄ delta", "delta", "snapshot-moved",
                       "match با تکانِ asof شکست — باید بازسنجیده شود")
            else:
                ck.add(name + " ⇄ delta", "delta", "UNEXPLAINED",
                       "match شکست بی‌تغییرِ asof: Δ=%s" % round(float(ov) - float(tv), 4))
        else:
            if r.get("cause_class") in CLASS5 and r.get("cause_evidence"):
                ck.add(name + " ⇄ class", "delta", "ok", "طبقه+شاهد: %s" % r["cause_class"])
            else:
                ck.add(name + " ⇄ class", "delta", "UNEXPLAINED", "واگرایی بی‌طبقهٔ پنج‌گانه")


def negative_control(mat, env, fx):
    """دو تخریبِ عمدی؛ چک‌کننده باید حساس باشد وگرنه «۰ ناهمخوانی» هیچ نیست."""
    hits = 0
    # 1) سطرِ match: درصدِ شاخص را ۰٫۳۵ واحد جابه‌جا کن
    m0 = json.loads(json.dumps(fx["market0"]["payload"]))
    m0["iw"][2] = float(m0["iw"][2]) + 0.35
    fx1 = dict(fx); fx1["market0"] = {"payload": m0, "fetched_at": None}
    for name, ov, tv, tol in pair_metrics(env, fx1):
        if name == "شاخص کل (درصد روز)" and abs(float(ov) - float(tv)) > tol:
            hits += 1
    # 2) اتحادِ s==s1[1:13] را بشکن
    m2 = json.loads(json.dumps(fx["market0"]["payload"]))
    h2 = json.loads(json.dumps(fx["histo"]["payload"]))
    h2["s1"][3] += 1
    fx2 = dict(fx); fx2["market0"] = {"payload": m2, "fetched_at": None}
    fx2["histo"] = {"payload": h2, "fetched_at": None}
    ck2 = Ck()
    identity_checks(fx2, ck2)
    if any(r["status"] == "UNEXPLAINED" for r in ck2.records):
        hits += 1
    return hits


def main():
    mat = json.load(open(os.path.join(HERE, "ta_parity_matrix.json"), encoding="utf-8"))
    fx = load_fixtures()
    db = bors_config.DB_PATH.replace(chr(92), "/")
    conn = sqlite3.connect("file:" + db + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    ck = Ck()
    try:
        env = our_values(conn)
    finally:
        conn.close()
    identity_checks(fx, ck)
    coverage_and_stability(mat, env, fx, ck)
    ctrl = negative_control(mat, env, fx)
    c = ck.counts()
    unexplained = c.get("UNEXPLAINED", 0)
    stored_d = (mat.get("meta") or {}).get("our_asof", {}).get("d_even")
    same_session = stored_d == (env.get("asof") or {}).get("d_even")
    ck.add("session-match", "identity", "ok" if same_session else "TIMING-CHECK",
           "ta j=%s d=%s | ours now d_even=%s | matrix d_even=%s"
           % (fx["market0"]["payload"].get("j"), fx["market0"]["payload"].get("d"),
              env["asof"].get("d_even"), stored_d))
    print("ta_fixture_check — پخشِ فیکسچرها از مسیرِ mstat_engine (بانکِ ro)")
    print("fixtures :", ", ".join(sorted(os.path.splitext(f)[0] for f in os.listdir(FIX)
                                         if f.startswith("ta_") and f.endswith(".json"))))
    print("fetched  :", ", ".join("%s=%s" % (k, v.get("fetched_at")) for k, v in fx.items()))
    print("ta stamp :", fx["market0"]["payload"].get("j"), fx["market0"]["payload"].get("d"),
          "| ours now:", env["asof"].get("d_even"), env["asof"].get("h_even"),
          "| matrix then:", (mat.get("meta") or {}).get("our_asof", {}).get("h_even"))
    print("checks   : total=%(total)s ok=%(ok)s snapshot-moved=%(snapshot-moved)s "
          "known-exception=%(known-exception)s UNEXPLAINED=%(UNEXPLAINED)s"
          % {"total": c.get("total", 0), "ok": c.get("ok", 0),
             "snapshot-moved": c.get("snapshot-moved", 0),
             "known-exception": c.get("known-exception", 0),
             "UNEXPLAINED": unexplained})
    print("negative control: %s/2 تخریب گرفته شد" % ctrl)
    for r in ck.records:
        if r["status"] in ("UNEXPLAINED", "snapshot-moved", "known-exception", "TIMING-CHECK"):
            print("  [%s] %s — %s" % (r["status"], r["name"], r["detail"]))
    if unexplained or ctrl < 2:
        print("RESULT: FAIL (%s unexplained; control=%s/2)" % (unexplained, ctrl))
        return 1
    print("RESULT: 0 unexplained discrepancies (محاسبه‌شده درِ اجرا)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
