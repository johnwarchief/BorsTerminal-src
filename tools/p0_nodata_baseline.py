# -*- coding: utf-8 -*-
"""P0 — سنجشِ خطِ پایهٔ «بدون داده» به تفکیکِ پنج ناحیه (فقط‌خواندنی).

خروجی: _audit/p0_nodata_baseline.json + جدولِ RTL رویِ stdout.
قاعده: هیچ مقدارِ ساختگی‌ای ساخته نمی‌شود؛ هر «نسنج» به یکی از علت‌های
missing_data / insufficient_history / invalid_data / not_applicable ردیف می‌شود.

بخش‌ها:
  A) تابلو/هفت فیلتر — بازسازیِ ورودی‌ها با همان SQLِ api/market.py و اجرایِ
     tape_flags.apply_tape_flags از همین worktree (خطِ پایهٔ کدِ جاری).
  B) قیفِ بنیادی — پوششِ هر شاخص از رویِ جدول‌هایِ منبع.
  C) تکنیکال — توزیعِ تعدادِ کندل در برابرِ حدِ هر موتور.
  D) وضعیت بازار — کامل‌بودنِ فیلدهایِ mstat_snap.
  E) حقیقی/حقوقی — ارجاع به نتیجۀ امروز (ctv_stepper).
  F) APIِ زنده (اختیاری) — آمارِ payloadِ /api/market از فرآیندِ محلی.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "market.db"
OUT = ROOT / "_audit" / "p0_nodata_baseline.json"

BOARD_SQL = """
WITH iso AS (SELECT MAX(d_even) AS d FROM market_watch),
     fv AS (
        WITH th AS MATERIALIZED (
            SELECT ins_code,
                   ROW_NUMBER() OVER (PARTITION BY ins_code
                                      ORDER BY d_even DESC) AS srn,
                   price_min, price_max, q_tot_tran5j AS volume
            FROM tape_history
        )
        SELECT ins_code,
               SUM(CASE WHEN srn <= 30 THEN volume END) AS prior30_vol,
               MAX(srn) AS hist_sessions,
               CASE WHEN COUNT(CASE WHEN srn <= 29 THEN 1 END) < 29 THEN 0
                    ELSE MIN(CASE WHEN srn <= 29 THEN price_min END) END AS min_low_29,
               MAX(CASE WHEN srn = 3  THEN price_max END) AS h2_max,
               MAX(CASE WHEN srn = 6  THEN price_max END) AS h5_max,
               MAX(CASE WHEN srn = 10 THEN price_max END) AS h9_max,
               MAX(CASE WHEN srn = 20 THEN price_max END) AS h19_max,
               MAX(CASE WHEN srn = 30 THEN price_max END) AS h29_max,
               MAX(CASE WHEN srn = 40 THEN price_max END) AS h39_max,
               MAX(CASE WHEN srn = 50 THEN price_max END) AS h49_max,
               MAX(CASE WHEN srn = 60 THEN price_max END) AS h59_max
        FROM th WHERE srn <= 60
        GROUP BY ins_code
     ),
     ctm AS (SELECT ins_code, MAX(d_even) AS d FROM client_type
             WHERE d_even <= (SELECT d FROM iso) GROUP BY ins_code),
     ph AS (SELECT symbol, volume, low,
                   ROW_NUMBER() OVER (PARTITION BY symbol
                                      ORDER BY date DESC) AS rn
            FROM price_history
            WHERE date < (SELECT printf('%04d-%02d-%02d', d/10000,
                                         (d/100)%100, d%100)
                          FROM (SELECT MAX(d_even) AS d FROM market_watch))),
     v AS (SELECT symbol,
                  AVG(CASE WHEN rn <= 30 THEN volume END) AS month_avg_vol,
                  MIN(CASE WHEN rn <= 29 AND low > 0 THEN low END) AS min30_low
           FROM ph WHERE rn <= 60 GROUP BY symbol)
SELECT m.ins_code, i.l_val18 AS symbol, m.p_closing, m.p_last,
       m.q_tot_tran AS tvol, m.z_tot_tran, m.price_yesterday AS py,
       m.allowed_min AS tmin, m.buy_q1_cnt, m.buy_q1_vol,
       COALESCE(ct.buy_i_vol, 0) AS buy_i_vol,
       COALESCE(ct.buy_n_vol, 0) AS buy_n_vol,
       COALESCE(ct.sell_i_vol, 0) AS sell_i_vol,
       COALESCE(ct.sell_n_vol, 0) AS sell_n_vol,
       COALESCE(ct.buy_count_i, 0) AS buy_count_i,
       COALESCE(ct.sell_count_i, 0) AS sell_count_i,
       ct.d_even AS ct_d,
       fv.prior30_vol, fv.hist_sessions, fv.min_low_29,
       fv.h2_max, fv.h5_max, fv.h9_max, fv.h19_max, fv.h29_max,
       fv.h39_max, fv.h49_max, fv.h59_max,
       v.month_avg_vol, v.min30_low
FROM market_watch m
JOIN instruments i ON i.ins_code = m.ins_code
LEFT JOIN ctm ON ctm.ins_code = m.ins_code
LEFT JOIN client_type ct ON ct.ins_code = m.ins_code AND ct.d_even = ctm.d
LEFT JOIN fv ON fv.ins_code = m.ins_code
LEFT JOIN v ON v.symbol = i.l_val18
WHERE m.d_even = (SELECT d FROM iso)
"""


def load_frame(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql_query(BOARD_SQL, conn)
    df["is_live"] = True
    py = pd.to_numeric(df["py"], errors="coerce")
    pl = pd.to_numeric(df["p_last"], errors="coerce")
    df["plp_raw"] = ((pl - py) / py * 100).where(py > 0)
    return df


def tape_baseline(conn: sqlite3.Connection) -> dict:
    sys.path.insert(0, str(ROOT))
    import tape_flags as tf

    df = load_frame(conn)
    flagged = tf.apply_tape_flags(df)

    n = len(df)
    hs = pd.to_numeric(df["hist_sessions"], errors="coerce")
    has_tape = hs.notna()
    hs30 = has_tape & (hs >= 30)
    hs29 = has_tape & (hs >= 29)
    hs60 = has_tape & (hs >= 60)
    has_ct = df["ct_d"].notna()
    bp_nan = flagged["buyer_power_raw"].isna()
    bp_no_side = has_ct & bp_nan  # ردیفِ ct هست ولی یک سمت صفر است
    untraded = (pd.to_numeric(df["tvol"], errors="coerce").fillna(0) <= 0)

    res: dict = {
        "universe": int(n),
        "session": int(pd.read_sql_query(
            "SELECT MAX(d_even) FROM market_watch", conn).iloc[0, 0]),
        "untraded_today": int(untraded.sum()),
        "no_tape_history": int((~has_tape).sum()),
        "hist_sessions_lt30": int((has_tape & (hs < 30)).sum()),
        "hist_sessions_30_59": int((hs30 & ~hs60).sum()),
        "hist_sessions_ge60": int(hs60.sum()),
        "no_client_type_row": int((~has_ct).sum()),
        "buyer_power_unavailable_with_ct": int(bp_no_side.sum()),
        "depth_missing_buy_q1": int(df["buy_q1_cnt"].isna().sum()),
        "filters": {},
    }

    def cause_for(f: str, i) -> str:
        if f in ("f_clock", "f_susp", "f_smart", "f_legal"):
            if not has_tape.iat[i]:
                return "missing_data"
            if not hs30.iat[i]:
                return "insufficient_history"
            if f in ("f_smart", "f_legal"):
                if not has_ct.iat[i]:
                    return "missing_data"
                if bp_nan.iat[i]:
                    return "not_applicable"
            if f == "f_legal" and flagged["f_smart"].iat[i] is False:
                return "available"
            return "available"
        if f == "f_jet":
            if not has_tape.iat[i]:
                return "missing_data"
            if not hs60.iat[i]:
                return "insufficient_history"
            if not has_ct.iat[i]:
                return "missing_data"
            if bp_nan.iat[i]:
                return "not_applicable"
            return "available"
        if f == "f_noqteh":
            if not has_tape.iat[i]:
                return "missing_data"
            if not hs29.iat[i]:
                return "insufficient_history"
            if pd.to_numeric(df["min_low_29"], errors="coerce").iat[i] == 0:
                return "invalid_data"
            return "available"
        if f == "f_roobi":
            if df["buy_q1_cnt"].isna().iat[i]:
                return "missing_data"
            return "available"
        return "available"

    for f in ("f_clock", "f_susp", "f_jet", "f_roobi",
              "f_noqteh", "f_smart", "f_legal"):
        col = flagged[f].fillna(False).astype(bool)
        causes: dict[str, int] = {}
        true = int(col.sum())
        for i in range(n):
            if col.iat[i]:
                continue
            c = cause_for(f, i)
            if c == "available":
                continue
            causes[c] = causes.get(c, 0) + 1
        res["filters"][f] = {
            "true": true,
            "false_measured": int((~col).sum() - sum(causes.values())),
            "not_evaluated": causes,
        }
    return res


def funnel_baseline(conn: sqlite3.Connection) -> dict:
    iso = conn.execute("SELECT MAX(d_even) FROM market_watch").fetchone()[0]
    uni = conn.execute(
        "SELECT COUNT(*) FROM market_watch WHERE d_even=?", (iso,)).fetchone()[0]

    def c(sql, args=()):
        return conn.execute(sql, args).fetchone()[0]

    monthly_cov = c(
        "SELECT COUNT(DISTINCT symbol) FROM monthly_sales"
        " WHERE monthly_revenue IS NOT NULL")
    monthly_12m = c(
        "SELECT COUNT(DISTINCT symbol) FROM ("
        " SELECT symbol FROM monthly_sales"
        " WHERE monthly_revenue IS NOT NULL"
        " GROUP BY symbol HAVING COUNT(*) >= 6)")
    annual_rev = c(
        "SELECT COUNT(DISTINCT symbol) FROM financial_statements"
        " WHERE period_months >= 12 AND revenue IS NOT NULL")
    annual_gp = c(
        "SELECT COUNT(DISTINCT symbol) FROM financial_statements"
        " WHERE period_months >= 12 AND gross_profit IS NOT NULL")
    annual_np = c(
        "SELECT COUNT(DISTINCT symbol) FROM financial_statements"
        " WHERE period_months >= 12 AND net_profit IS NOT NULL")
    annual_eps = c(
        "SELECT COUNT(DISTINCT symbol) FROM financial_statements"
        " WHERE period_months >= 12 AND basic_eps IS NOT NULL")
    eps_instr = c(
        "SELECT COUNT(*) FROM instruments WHERE eps IS NOT NULL AND eps != 0")
    mcap_dp = c(
        "SELECT COUNT(DISTINCT ins_code) FROM daily_prices"
        " WHERE market_cap > 0")
    mcap_snap = c("SELECT COUNT(DISTINCT symbol) FROM market_cap_snapshots"
                  if conn.execute(
                      "SELECT 1 FROM sqlite_master WHERE name='market_cap_snapshots'"
                  ).fetchone() else "SELECT 0")
    fts_rows = c("SELECT COUNT(*) FROM fts_results")

    tech = conn.execute(
        "SELECT tech_status, COUNT(*) FROM funnel_tech_scan"
        " GROUP BY tech_status ORDER BY 2 DESC").fetchall()
    as_of = conn.execute(
        "SELECT as_of, COUNT(*) FROM funnel_tech_scan"
        " GROUP BY as_of ORDER BY as_of DESC LIMIT 5").fetchall()

    return {
        "universe_board": int(uni),
        "symbols_with_monthly_sales": int(monthly_cov),
        "symbols_with_monthly_ge6": int(monthly_12m),
        "symbols_with_annual_revenue": int(annual_rev),
        "symbols_with_annual_gross_profit": int(annual_gp),
        "symbols_with_annual_net_profit": int(annual_np),
        "symbols_with_annual_eps": int(annual_eps),
        "instruments_with_eps": int(eps_instr),
        "symbols_with_mcap_daily_prices": int(mcap_dp),
        "symbols_with_mcap_snapshots": int(mcap_snap),
        "fts_results_rows": int(fts_rows),
        "funnel_tech_scan_total": int(c("SELECT COUNT(*) FROM funnel_tech_scan")),
        "funnel_tech_scan_by_status": {str(k): int(v) for k, v in tech},
        "funnel_tech_scan_as_of_top": {str(k): int(v) for k, v in as_of},
    }


def technical_baseline(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        "SELECT symbol, COUNT(*) AS n FROM price_history GROUP BY symbol").fetchall()
    counts = pd.Series({s: n for s, n in rows})
    wk = conn.execute(
        "SELECT symbol, COUNT(DISTINCT substr(date,1,4)||'W'||"
        " CAST(((CAST(substr(date,6,2) AS INTEGER)-1)*4 +"
        " (CAST(substr(date,9,2) AS INTEGER)-1)/7) AS INTEGER)) AS w"
        " FROM price_history GROUP BY symbol").fetchall()
    wcounts = pd.Series({s: w for s, w in wk})

    def buckets(s: pd.Series) -> dict:
        return {
            "symbols": int(len(s)),
            "ge15": int((s >= 15).sum()),
            "ge40": int((s >= 40).sum()),
            "ge52": int((s >= 52).sum()),
            "ge60": int((s >= 60).sum()),
            "lt15": int((s < 15).sum()),
            "between15_59": int(((s >= 15) & (s < 60)).sum()),
            "zero": int((s == 0).sum()),
        }

    dp_rows = conn.execute(
        "SELECT ins_code, COUNT(*) FROM daily_prices GROUP BY ins_code").fetchall()
    dp_counts = pd.Series({s: n for s, n in dp_rows})
    return {
        "price_history_daily": buckets(counts),
        "price_history_weekly_approx": buckets(wcounts),
        "daily_prices_rows": buckets(dp_counts),
    }


def mstat_baseline(conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        "SELECT d_even, h_even, ts, agg FROM mstat_snap"
        " ORDER BY d_even DESC, h_even DESC LIMIT 1").fetchone()
    if not row:
        return {"available": False}
    agg = json.loads(row[3])
    total = nulls = nodata = nameh = dash = 0
    samples = []

    def walk(o, path=""):
        nonlocal total, nulls, nodata, nameh, dash
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")
        else:
            total += 1
            if o is None:
                nulls += 1
                if len(samples) < 20:
                    samples.append(("null", path))
            elif isinstance(o, str):
                t = o.strip()
                if "بدون داده" in t or "داده کافی" in t or "سنجیده نشده" in t:
                    nodata += 1
                    if len(samples) < 20:
                        samples.append(("nodata_msg", path + "=" + t[:40]))
                elif t in ("نامعلوم", "—", "-", ""):
                    nameh += 1
                    if len(samples) < 20:
                        samples.append(("vague", path + "=" + t[:40]))

    walk(agg)
    return {
        "available": True,
        "d_even": int(row[0]), "h_even": int(row[1]), "ts": row[2],
        "scalar_values": total, "nulls": nulls,
        "nodata_messages": nodata, "vague_tokens": nameh,
        "samples": samples,
    }


def ctv_reference() -> dict:
    stepper = ROOT / "_audit" / "ctv_stepper.json"
    if not stepper.exists():
        return {"available": False}
    d = json.loads(stepper.read_text(encoding="utf-8"))
    steps = d.get("steps", [])
    last = steps[-1] if steps else {}
    return {
        "available": bool(steps),
        "day": last.get("day"),
        "rows_day_last": last.get("rows_day"),
        "day_target": last.get("day_target"),
        "native_last": last.get("native"),
        "pct_of_target_last": last.get("pct_of_target"),
        "native_ceiling_note": "measured: ~670 tail symbols 500 directly from TSETMC; ceiling ~75% per session",
        "steps_written": [s.get("run", {}).get("written") for s in steps],
    }


def api_probe(port: int = 8002) -> dict:
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/market", timeout=30) as r:
            payload = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # pragma: no cover - probe
        return {"available": False, "error": str(e)[:200]}
    rows = payload.get("data") or payload.get("rows") or []
    if isinstance(rows, dict):
        rows = list(rows.values())
    meta = payload.get("meta", {})
    n = len(rows)
    live = [x for x in rows if isinstance(x, dict) and x.get("is_live")]
    out = {
        "available": True, "port": port, "rows": n,
        "live_rows": len(live), "meta": meta,
        "filters_true": {}, "helper_nulls": {},
    }
    for f in ("f_clock", "f_susp", "f_jet", "f_roobi",
              "f_noqteh", "f_smart", "f_legal"):
        out["filters_true"][f] = sum(
            1 for x in live if isinstance(x, dict) and x.get(f) is True)
    for h in ("vol_ratio_file", "hist_sessions", "min_low_29",
              "buyer_power_raw", "resistance_59"):
        out["helper_nulls"][h] = sum(
            1 for x in live
            if isinstance(x, dict) and x.get(h) is None)
    return out


def fa(t: str) -> str:
    return "".join(chr(0x06F0 + int(c)) if c.isdigit() else c for c in t)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    report = {
        "schema": "p0-nodata-baseline/v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "db": "market.db (read-only)",
        "tape": tape_baseline(conn),
        "funnel": funnel_baseline(conn),
        "technical": technical_baseline(conn),
        "mstat": mstat_baseline(conn),
        "ctv": ctv_reference(),
        "api_8002": api_probe(8002),
    }
    conn.close()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                   encoding="utf-8")

    t = report["tape"]
    print(fa("== الف) تابلو — نشستِ {s} | کلِ تابلو: {u} | بی‌معامله: {ut}")
          .format(s=t["session"], u=t["universe"], ut=t["untraded_today"]))
    print(fa("پنجرهٔ [ih]: بدونِ تاریخچه={m} | <۳۰ نشست={i} | ۳۰–۵۹={b} | ≥۶۰={g}")
          .format(m=t["no_tape_history"], i=t["hist_sessions_lt30"],
                  b=t["hist_sessions_30_59"], g=t["hist_sessions_ge60"]))
    print(fa("client_type بدونِ ردیف={nc} | buyer_power ناممکن با ct={bp} | عمقِ buy_q1 تهی={d}")
          .format(nc=t["no_client_type_row"], bp=t["buyer_power_unavailable_with_ct"],
                  d=t["depth_missing_buy_q1"]))
    hdr = fa("فیلتر | درست | نادرستِ سنجیده | نسنج:missing | نسنج:ناکافی | نسنج:نامعتبر | نسنج:کاربردندارد")
    print(hdr)
    for f, s in t["filters"].items():
        ne = s["not_evaluated"]
        print(fa("{f} | {t} | {fm} | {m} | {i} | {iv} | {na}")
              .format(f=f, t=s["true"], fm=s["false_measured"],
                      m=ne.get("missing_data", 0), i=ne.get("insufficient_history", 0),
                      iv=ne.get("invalid_data", 0), na=ne.get("not_applicable", 0)))
    print("report:", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
