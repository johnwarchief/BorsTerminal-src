#!/usr/bin/env python3
"""select_symbols.py — انتخابِ ۳۰ نمادِ فاز ۴٫۵ از روی نسخهٔ آزمایشگاهیِ بانک.

چرا این اسکریپت و نه یک کوئریِ دستی: مأموریت §2 می‌خواهد ترکیبِ نقدشوندگی،
رویدادِ شرکتی، توقف، طولِ تاریخچه، شکافِ پوشش و دادهٔ خاص با دلیلِ ثبت‌شده
انتخاب شود. دلیل باید از خودِ بانک بازتولیدشدنی باشد، نه از حافظهٔ من.

سه تله‌ای که اندازه‌گیری شد و این‌جا بسته شده است:

  ۱) `price_history.value` فقط ۹۷٬۶۶۹ ردیف (از ۲۰۲۶-۰۸-۲۰) پر است و نسبتِ آن
     به `close*volume` برای ۱٬۸۵۹ نماد ≈۱۰۰۰ و برای بقیه ≈۱ است (حجمِ برخی
     نمادها در «لات» است). رتبه‌بندیِ خام یا value را حذف می‌کرد یا نمادهای
     لات‌محور را ۱۰۰۰ برابر کم‌می‌شمرد. این‌جا میانهٔ ۹۰ جلسهٔ `close*volume`
     با ضریبِ واحدِ همان نماد (از شاهدِ خودش) اصلاح می‌شود.
  ۲) `paper_type=8` هم سهام است هم صندوق و هم اوراق؛ فیلترِ سهام با ISIN و
     واژه‌های نام انجام می‌شود، نه با paper_type تنها.
  ۳) `adjust_events` دو املاي عربي/فارسي دارد (`كگل` ۵۷ و `کگل` ۳۹ ردیف).
     همهٔ جدول‌های رویداد با `symbol_identity.key()` تجمیع می‌شوند تا یک نماد
     با دو املا دو نمادِ разных شمرده نشود.

ورودی‌ها فقط‌خواندنی‌اند: `--db` نسخهٔ lab و `--pack` پکِ live40 (نگاشتِ
Rahavard). هیچ نوشتنی در بانک انجام نمی‌شود.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import re
import sqlite3
import statistics
import sys
from collections import Counter
from datetime import date

KEY_TABLE = str.maketrans({"\u064a": "\u06cc", "\u0643": "\u06a9", "\u0649": "\u06cc"})
KEY_SEPS = (" ", "\u00a0", "\u200c", "\u200f", "\u200e", "\u202f")

FUND_WORDS = ("صندوق", "س. ", "س.اعتماد", "س سپر", "س.درآمد", "س.كالا", "س. کالا")
BOND_WORDS = ("مرابحه", "اسناد", "اختيار", "امتياز", "اجاره", "تسهيلات", "سلف")

STRATA_FA = {
    "high_liquidity": "نقدشوندگیِ بالا",
    "mid_liquidity": "نقدشوندگیِ میانه",
    "low_liquidity": "نقدشوندگیِ پایین",
    "corporate_events": "رویدادهایِ شرکتی",
    "halt_reopen": "توقف/بازگشایی",
    "long_history": "تاریخچهٔ بلند",
    "coverage_gap": "شکافِ پوشش",
    "incomplete_special": "دادهٔ ناقص/خاص",
}
QUOTA = {
    "high_liquidity": 6, "mid_liquidity": 5, "low_liquidity": 4,
    "corporate_events": 5, "halt_reopen": 3, "long_history": 3,
    "coverage_gap": 2, "incomplete_special": 2,
}
ANCHORS = {
    453: ("high_liquidity", "فولاد"),
    462: ("high_liquidity", "وبملت"),
    484: ("high_liquidity", "شپنا"),
    149: ("corporate_events", "فنوال"),
    599: ("corporate_events", "ولانا"),
    167: ("coverage_gap", "خودرو"),
}
CSV_COLS = ["symbol", "ins_code", "isin", "asset_id", "stratum", "reason",
            "first_date", "last_date", "candles", "zero_volume", "max_gap",
            "adjust_events", "share_events", "correction_pack", "halt_state",
            "rahavard_access", "raw_status", "adjusted_status"]


def key(text) -> str:
    s = "" if text is None else str(text)
    for sep in KEY_SEPS:
        s = s.replace(sep, "")
    return s.translate(KEY_TABLE).lower()


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_equity(name, paper_type, isin) -> bool:
    if paper_type not in (1, 2, 8):
        return False
    nm = str(name or "")
    if any(w in nm for w in FUND_WORDS) or any(w in nm for w in BOND_WORDS):
        return False
    return (isin or "").upper().startswith(("IRO1", "IRO3", "IRO5", "IRO7"))


def median(values):
    vals = sorted(v for v in values if v is not None)
    return statistics.median(vals) if vals else None


def load_pack(pack_dir: str):
    rows = []
    path = os.path.join(pack_dir, "factors.jsonl")
    with io.open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    by_key = {}
    for r in rows:
        k = key(r.get("symbol"))
        if not k:
            continue
        e = by_key.setdefault(k, {"asset_id": str(r.get("asset_id") or ""),
                                  "ins_code": str(r.get("ins_code") or ""),
                                  "symbol": r.get("symbol"), "n": 0,
                                  "first": None, "last": None})
        e["n"] += 1
        d = r.get("effective_date")
        if d:
            e["first"] = d if not e["first"] or d < e["first"] else e["first"]
            e["last"] = d if not e["last"] or d > e["last"] else e["last"]
    return rows, by_key


def load_r32(pack_dir: str):
    """شمارِ کندل‌هایِ مرجعِ R32 برایِ۶ نمادِ لنگر (D/W/M)."""
    counts, by_symbol = {}, {}
    path = os.path.join(pack_dir, "bars_capture.ndjson.gz")
    if not os.path.exists(path):
        return counts, by_symbol
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            sid = str(r.get("symbol_id") or "")
            tf = r.get("timeframe")
            counts[(sid, tf)] = counts.get((sid, tf), 0) + 1
            by_symbol.setdefault(key(r.get("symbol")), {"symbol": r.get("symbol"),
                                                        "symbol_id": sid,
                                                        "D": 0, "W": 0, "M": 0})
            by_symbol[key(r.get("symbol"))][tf] = by_symbol[key(r.get("symbol"))].get(tf, 0) + 1
    return counts, by_symbol


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--r32", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    con = sqlite3.connect("file:%s?mode=ro" % args.db, uri=True)
    con.row_factory = sqlite3.Row

    # ── هویت: یک ins_code برایِ هر کلید، با ترجیحِ ردیفِ دارایِ ISIN ──────────
    inst = {}
    for r in con.execute("SELECT ins_code,l_val18,l_val30,paper_type,isin,updated_at "
                         "FROM instruments ORDER BY ins_code"):
        raw = r["l_val18"]
        if not raw or not str(raw).strip():
            continue
        k = key(raw)
        cand = (0 if r["isin"] else 1, 0 if r["paper_type"] in (1, 2, 8) else 1,
                str(r["updated_at"] or ""), str(r["ins_code"]))
        cur = inst.get(k)
        curk = (0 if cur and cur["isin"] else 1,
                0 if cur and cur["pt"] in (1, 2, 8) else 1,
                str(cur["upd"] or "") if cur else "",
                cur["ins_code"] if cur else "")
        if cur is None or cand > curk:
            inst[k] = {"ins_code": str(r["ins_code"]), "raw": str(raw),
                       "name": r["l_val30"], "pt": r["paper_type"],
                       "isin": r["isin"], "upd": r["updated_at"]}

    # ── تاریخچهٔ محلی و تجمیعِ رویدادها با کلیدِ هویت ─────────────────────────
    hist = {}
    for r in con.execute("""SELECT symbol, COUNT(*) AS n, MIN(date) AS first,
                                   MAX(date) AS last,
                                   SUM(CASE WHEN COALESCE(volume,0)=0 THEN 1 ELSE 0 END) AS zero
                            FROM price_history GROUP BY symbol"""):
        hist[str(r["symbol"])] = {"n": r["n"], "first": r["first"],
                                  "last": r["last"], "zero": r["zero"] or 0}
    by_key_hist = {}
    for s in hist:
        by_key_hist.setdefault(key(s), []).append(s)

    ev = {}
    spellings = {}
    source_fields = (("adjust_events", "adjust"), ("share_change_events", "share"),
                     ("price_adjust_events", "pa"))
    for table, field in source_fields:
        for (s,) in con.execute("SELECT symbol FROM %s" % table):
            if s is None:
                continue
            k = key(s)
            e = ev.setdefault(k, {"adjust": 0, "share": 0, "pa": 0})
            e[field] += 1
            spellings.setdefault(k, set()).add(str(s))

    state = {}
    for r in con.execute("SELECT ins_code, c_etaval_title, d_even FROM instrument_state "
                         "ORDER BY d_even"):
        state[str(r["ins_code"])] = r["c_etaval_title"]
    halt_titles = [str(r[0]) for r in con.execute(
        "SELECT title FROM tsetmc_messages WHERE title LIKE '%توقف%' "
        "OR title LIKE '%بازگشاي%' OR title LIKE '%بازگشای%'")]

    # اعلان‌ها فقط داخلِ پرانتز نامِ نماد را دارند: «توقف نماد (فساپ1)».
    # تطبیقِ زیررشته‌ای، «زر» را در هر تیترِ «بازگشايي» می‌دید (۳٬۳۰۰ شمارشِ
    # کاذب)؛ پس توکنِ پرانتز استخراج و رقمِ خطِ پایانی حذف می‌شود.
    TOKEN_RE = re.compile(r"[\(\（]([^\)\）]+)[\)\）]")
    halt_count, reopen_count = Counter(), Counter()
    for title in halt_titles:
        target = halt_count if "توقف" in title else reopen_count
        for group in TOKEN_RE.findall(title):
            for token in re.split(r"[،,]", group):
                name = re.sub(r"[0-9۰-۹]+\s*$", "", token.strip()).strip()
                k = key(name)
                if len(k) >= 2:
                    target[k] += 1

    def max_gap(symbol):
        ds = [date.fromisoformat(r[0]) for r in con.execute(
            "SELECT date FROM price_history WHERE symbol=? ORDER BY date", (symbol,))]
        return max(((ds[i] - ds[i - 1]).days for i in range(1, len(ds))), default=0)

    pack_rows, pack = load_pack(args.pack)
    r32_counts, r32_symbols = load_r32(args.r32)

    # ── نقدشوندگیِ ۹۰ جلسه با اصلاحِ واحدِ حجم ────────────────────────────────
    dates90 = [r[0] for r in con.execute(
        "SELECT DISTINCT date FROM price_history ORDER BY date DESC LIMIT 90")]
    floor = dates90[-1]
    liq_rows = {}
    for r in con.execute("SELECT symbol, date, close, volume, value FROM price_history "
                         "WHERE date>=?", (floor,)):
        liq_rows.setdefault(str(r["symbol"]), []).append(
            (r["close"] or 0.0, r["volume"] or 0.0, r["value"]))

    def liquidity(symbol):
        rows = liq_rows.get(symbol, [])
        ratios = [v / (c * vol) for c, vol, v in rows if v is not None and c > 0 and vol > 0]
        m = median(ratios)
        factor = 1000.0 if (m and m > 100) else 1.0
        return (median([c * vol for c, vol, _ in rows if c > 0]) or 0.0) * factor, factor

    # ── جهانِ سهام و استخرهایِ طبقه‌ها ────────────────────────────────────────
    universe, short_pool = [], []
    for k, it in inst.items():
        if not is_equity(it["name"], it["pt"], it["isin"]):
            continue
        raws = by_key_hist.get(k, [])
        if not raws:
            continue
        local = max(raws, key=lambda s: (hist[s]["n"], s))
        h = hist[local]
        liq, factor = liquidity(local)
        e = ev.get(k, {"adjust": 0, "share": 0, "pa": 0})
        rec = {"key": k, "symbol": local, "ins_code": it["ins_code"],
               "isin": it["isin"], "name": it["name"], "paper_type": it["pt"],
               "n": h["n"], "first": h["first"], "last": h["last"],
               "zero": h["zero"], "liq": liq, "unit_factor": factor,
               "events": e["adjust"] + e["share"], "adjust": e["adjust"],
               "share": e["share"], "pa": e["pa"],
               "pack": pack.get(k), "aliases": sorted(spellings.get(k, ())),
               "halt_state": state.get(it["ins_code"]),
               "halt_notices": halt_count.get(k, 0),
               "reopen_notices": reopen_count.get(k, 0)}
        if h["n"] >= 120:
            universe.append(rec)
        elif h["n"] >= 60 and rec["pack"]:
            short_pool.append(rec)

    universe.sort(key=lambda x: (-x["liq"], x["symbol"]))
    for i, rec in enumerate(universe, 1):
        rec["rank"] = i

    selected = {}

    def record(rec, stratum, reason):
        selected[rec["key"]] = {
            "symbol": rec["symbol"], "ins_code": rec["ins_code"],
            "isin": rec["isin"] or "", "asset_id": (rec["pack"] or {}).get("asset_id", ""),
            "stratum": stratum, "reason": reason, "first_date": rec["first"],
            "last_date": rec["last"], "candles": rec["n"],
            "zero_volume": rec["zero"], "max_gap": max_gap(rec["symbol"]),
            "adjust_events": rec["adjust"], "share_events": rec["share"],
            "correction_pack": (rec["pack"] or {}).get("n", 0),
            "halt_state": rec["halt_state"] or "",
            "rahavard_access": "pack-mapped" if rec["pack"] else "unmapped",
            "raw_status": "NOT_MEASURED", "adjusted_status": "NOT_MEASURED",
            "_json": {"identity_key": rec["key"], "name": rec["name"],
                      "paper_type": rec["paper_type"], "liquidity_rank": rec.get("rank"),
                      "liquidity_value": rec["liq"], "liquidity_unit_factor": rec["unit_factor"],
                      "liquidity_method": "median(close*volume) x unit_factor over last 90 sessions",
                      "price_adjust_events": rec["pa"], "event_score": rec["events"],
                      "zero_volume_ratio": round(rec["zero"] / rec["n"], 4) if rec["n"] else 0,
                      "aliases": rec["aliases"],
                      "halt_notices": rec["halt_notices"],
                      "reopen_notices": rec["reopen_notices"],
                      "r32_reference": r32_symbols.get(rec["key"])}}

    def remaining(stratum):
        return QUOTA[stratum] - sum(1 for s in selected.values() if s["stratum"] == stratum)

    def take(cands, stratum, reason_fn, limit=None):
        want = remaining(stratum)
        if limit is not None:
            want = min(want, limit)
        if want <= 0:
            return 0
        n = 0
        for rec in cands:
            if n >= want:
                break
            if rec["key"] in selected:
                continue
            record(rec, stratum, reason_fn(rec))
            n += 1
        return n

    # ── ۱) لنگرهایِ R32 (پیش از هر طبقه‌ای) ──────────────────────────────────
    all_recs = {r["key"]: r for r in universe + short_pool}
    for asset_id, (stratum, sym) in ANCHORS.items():
        rec = all_recs.get(key(sym))
        if rec is None:
            raise SystemExit("R32 anchor missing from local history: %s" % sym)
        if not rec["pack"] or rec["pack"]["asset_id"] != str(asset_id):
            raise SystemExit("R32 anchor %s asset mismatch: %r" % (sym, rec["pack"]))
        r32 = r32_symbols.get(rec["key"], {})
        record(rec, stratum,
               "لنگرِ R32 (asset %s): %s کندلِ محلی، مرجع %sD/%sW/%sM؛ رتبهٔ نقدشوندگی %s"
               % (asset_id, rec["n"], r32.get("D", "-"), r32.get("W", "-"),
                  r32.get("M", "-"), rec.get("rank", "-")))

    # ── ۲) توقف/بازگشایی: وضعیتِ متوقف + شکافِ تقویمی ─────────────────────────
    halt_pool = []
    for rec in universe + short_pool:
        if rec["key"] in selected:
            continue
        if rec["halt_state"] and "متوقف" in str(rec["halt_state"]):
            gap = max_gap(rec["symbol"])
            if gap >= 7:
                rec["_gap"] = gap
                halt_pool.append(rec)
    halt_pool.sort(key=lambda x: (-x["_gap"], x["symbol"]))
    take(halt_pool, "halt_reopen",
         lambda r: "وضعیت «%s»؛ بزرگ‌ترین شکافِ تقویمی %d روز در %d کندل؛ %d اعلانِ توقف"
                   % (r["halt_state"], r["_gap"], r["n"], r["halt_notices"]), limit=2)

    # بازگشایی: نمادی که اعلانِ بازگشایی دارد، اکنون متوقف نیست، و شکافِ
    # تقویمی دارد. سه حالتِ «متوقف/ممنوع» کنار گذاشته می‌شود تا ادعایِ
    # «بازگشایی» با وضعیتِ فعلی تناقض نداشته باشد.
    reopen_pool = []
    for rec in universe + short_pool:
        if rec["key"] in selected:
            continue
        if str(rec["halt_state"] or "") in ("ممنوع", "مجاز-متوقف", "ممنوع-متوقف"):
            continue
        if rec["reopen_notices"] >= 2:
            gap = max_gap(rec["symbol"])
            if gap >= 7:
                rec["_gap"] = gap
                reopen_pool.append(rec)
    reopen_pool.sort(key=lambda x: (-x["_gap"],
                                    -(x["halt_notices"] + x["reopen_notices"]),
                                    x["symbol"]))
    take(reopen_pool, "halt_reopen",
         lambda r: "بازگشایی: %d اعلانِ توقف + %d اعلانِ بازگشایی؛ شکافِ %d روز؛ وضعیتِ فعلی %s"
                   % (r["halt_notices"], r["reopen_notices"], r["_gap"],
                      r["halt_state"] or "در instrument_state ثبت نشده"), limit=1)

    # ── ۳) شکافِ پوشش: تاریخچهٔ کوتاهِ محلی با نگاشتِ مرجع ─────────────────────
    cov_pool = sorted(short_pool, key=lambda x: (-x["events"], x["n"], x["symbol"]))
    take(cov_pool, "coverage_gap",
         lambda r: "%d کندلِ محلی از %s؛ نگاشتِ مرجع asset %s؛ پوششِ مرجع باید جدا سنجیده شود"
                   % (r["n"], r["first"], (r["pack"] or {}).get("asset_id", "-")))

    # ── ۴) رویدادهایِ شرکتی: بیشترین رویدادِ تجمیع‌شده زیر یک هویت ─────────────
    ev_pool = sorted([r for r in universe if r["events"] >= 20],
                     key=lambda x: (-x["events"], -(x["pack"] or {}).get("n", 0), x["symbol"]))
    take(ev_pool, "corporate_events",
         lambda r: "%d رویداد (adjust %d + share %d + price-adjust %d) زیرِ کلیدِ %s%s"
                   % (r["events"], r["adjust"], r["share"], r["pa"], r["key"],
                      "؛ دو املا: " + "، ".join(r["aliases"]) if len(r["aliases"]) > 1 else ""))

    # ── ۵) دادهٔ خاص: حجمِ صفرِ مکرر، سپس دو املايِ یک هویت ────────────────────
    zero_pool = sorted([r for r in universe if r["zero"] / r["n"] >= 0.35 and r["pack"]],
                       key=lambda x: (-(x["zero"] / x["n"]), x["symbol"]))
    take(zero_pool, "incomplete_special",
         lambda r: "%d از %d کندل حجمِ صفر/تهی (%.0f%%؛ رتبهٔ نقدشوندگی %d)"
                   % (r["zero"], r["n"], 100.0 * r["zero"] / r["n"], r["rank"]))
    alias_pool = sorted([r for r in universe if len(r["aliases"]) > 1 and r["events"] >= 20],
                        key=lambda x: (-x["events"], x["symbol"]))
    take(alias_pool, "incomplete_special",
         lambda r: "یک هویت با دو املاي در جدول‌ها (%s)؛ %d رویداد؛ آزمونِ یکسان‌سازی"
                   % ("، ".join(r["aliases"]), r["events"]))

    # ── ۶) تاریخچهٔ بلند ─────────────────────────────────────────────────────
    long_pool = sorted([r for r in universe if r["n"] >= 450 and r["pack"]],
                       key=lambda x: (-x["n"], x["symbol"]))
    take(long_pool, "long_history",
         lambda r: "%d جلسه (بیشینهٔ محلی ۵۲۹)؛ asset %s"
                   % (r["n"], (r["pack"] or {}).get("asset_id", "-")))

    # ── ۷) نقدشوندگی: بالا، میانه، دُمِ پایین ──────────────────────────────────
    by_liq = sorted(universe, key=lambda x: (-x["liq"], x["symbol"]))
    take(by_liq, "high_liquidity",
         lambda r: "رتبهٔ %d از %d سهمِ ≥۱۲۰ جلسه؛ ارزشِ میانهٔ ۹۰ جلسه ≈ %.2e (ضریبِ واحد %g)"
                   % (r["rank"], len(universe), r["liq"], r["unit_factor"]))
    take(by_liq, "mid_liquidity",
         lambda r: "رتبهٔ %d از %d (باندِ میانه)؛ ارزشِ میانهٔ ۹۰ جلسه ≈ %.2e"
                   % (r["rank"], len(universe), r["liq"]))
    low_pool = sorted([r for r in universe if r["rank"] >= max(1, len(universe) - 60)
                       and r["pack"] and r["zero"] / r["n"] < 0.35
                       and not (r["halt_state"] and "متوقف" in str(r["halt_state"]))],
                      key=lambda x: (-x["rank"], x["symbol"]))
    take(low_pool, "low_liquidity",
         lambda r: "دُمِ پایینِ نقدشوندگی: رتبهٔ %d از %d؛ %d کندل؛ asset %s"
                   % (r["rank"], len(universe), r["n"],
                      (r["pack"] or {}).get("asset_id", "-")))

    # ── اعتبارسنجی و خروجی ───────────────────────────────────────────────────
    gaps = []
    if len(selected) != 30:
        gaps.append("تعدادِ انتخاب‌شده %d است، نه ۳۰" % len(selected))
    for stratum, quota in QUOTA.items():
        got = sum(1 for s in selected.values() if s["stratum"] == stratum)
        if got != quota:
            gaps.append("%s: %d از %d" % (stratum, got, quota))
    anchor_keys = {key(sym) for _, sym in ANCHORS.values()}
    missing_anchors = [sym for _, sym in ANCHORS.values() if key(sym) not in selected]
    if missing_anchors:
        gaps.append("لنگرهایِ غایب: " + "، ".join(missing_anchors))

    order = {name: i for i, name in enumerate(STRATA_FA)}
    rows = sorted(selected.values(), key=lambda s: (order[s["stratum"]], s["symbol"]))
    csv_path = os.path.join(args.out, "SYMBOLS-30.csv")
    with io.open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLS)
        w.writeheader()
        for row in rows:
            w.writerow({c: row[c] for c in CSV_COLS})

    n90 = sum(1 for h in hist.values() if h["n"] == 90)
    n90_june = sum(1 for h in hist.values()
                   if h["n"] == 90 and h["first"] >= "2026-06-01")
    all_factor_1000 = sum(1 for sym in liq_rows if liquidity(sym)[1] > 1)
    summary = {
        "generated_at": "2026-11-09",
        "db": os.path.basename(args.db), "db_sha256": sha256(args.db),
        "db_wal_sha256": sha256(args.db + "-wal") if os.path.exists(args.db + "-wal") else None,
        "db_shm_sha256": sha256(args.db + "-shm") if os.path.exists(args.db + "-shm") else None,
        "pack": os.path.basename(os.path.normpath(args.pack)),
        "pack_factors_sha256": sha256(os.path.join(args.pack, "factors.jsonl")),
        "pack_rows": len(pack_rows), "pack_assets": len(pack),
        "sessions": con.execute("SELECT COUNT(DISTINCT date) FROM price_history").fetchone()[0],
        "date_range": list(con.execute("SELECT MIN(date), MAX(date) FROM price_history").fetchone()),
        "price_history_symbols": len(hist), "instruments": len(inst),
        "history_symbols_without_instrument": sum(1 for s in hist if key(s) not in inst),
        "equity_universe_ge120": len(universe),
        "equity_universe_pack_mapped": sum(1 for u in universe if u["pack"]),
        "equity_unit_factor_1000": sum(1 for u in universe if u["unit_factor"] > 1),
        "all_unit_factor_1000": all_factor_1000,
        "symbols_with_90_sessions": n90,
        "symbols_with_90_sessions_since_2026_06": n90_june,
        "duplicate_instrument_keys": sum(1 for r in con.execute(
            "SELECT l_val18 FROM instruments WHERE l_val18 IS NOT NULL AND TRIM(l_val18)<>'' "
            "GROUP BY l_val18 HAVING COUNT(*)>1")),
        "quotas": QUOTA,
        "selected_by_stratum": {s: sum(1 for x in selected.values() if x["stratum"] == s)
                                for s in QUOTA},
        "selected": len(selected), "gaps": gaps,
        "r32_anchors": {str(a): {"symbol": sym, "stratum": stratum,
                                 "reference": r32_symbols.get(key(sym))}
                        for a, (stratum, sym) in ANCHORS.items()},
        "r32_counts_D": {("%s|%s" % k): v for k, v in sorted(r32_counts.items())
                         if k[1] == "D"},
    }
    json_path = os.path.join(args.out, "SYMBOLS-30.json")
    with io.open(json_path, "w", encoding="utf-8") as fh:
        json.dump({"summary": summary,
                   "symbols": [{k: v for k, v in r.items() if k != "_json"} | r["_json"]
                               for r in rows]},
                  fh, ensure_ascii=False, indent=1)
    with io.open(os.path.join(args.out, "SYMBOLS-30.summary.json"), "w",
                 encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)

    md = [
        "# انتخابِ ۳۰ نماد — فاز ۴٫۵", "",
        "| قلم | مقدار |", "| --- | --- |",
        "| بانک | `%s` |" % summary["db"],
        "| SHA-256 بانک | `%s` |" % summary["db_sha256"],
        "| جلسه‌هایِ محلی | %d (%s → %s) |" % tuple(
            [summary["sessions"]] + summary["date_range"]),
        "| نمادهایِ `price_history` | %d |" % summary["price_history_symbols"],
        "| جهانِ سهامِ ≥۱۲۰ جلسه | %d (از این تعداد %d دارایِ نگاشتِ پک) |"
        % (summary["equity_universe_ge120"], summary["equity_universe_pack_mapped"]),
        "| پکِ مرجع | `%s`، %d ردیف، %d دارایی |"
        % (summary["pack"], summary["pack_rows"], summary["pack_assets"]),
        "| نمادهایِ ۹۰ جلسه‌ای با شروعِ ژوئن ۲۰۲۶ | %d |" % n90_june,
        "", "## روشِ انتخاب", "",
        "- هویت: `symbol_identity.key()` (عربي←فارسي و حذفِ فاصله/نیم‌فاصله) و `ins_code`؛",
        "- نقدشوندگی: میانهٔ ۹۰ جلسهٔ `close*volume` با ضریبِ واحدِ هر نماد از شاهدِ",
        "  `value/(close*volume)` (۱ یا ۱۰۰۰) — چون `value` فقط از ۲۰۲۶-۰۸-۲۰ پر است؛",
        "- جهانِ سهام: `paper_type` ∈ {1,2,8} + ISINِ `IRO1/3/5/7` + نامِ بی‌واژهٔ صندوق/اوراق؛",
        "- هر نماد به یک طبقه و یک دلیل تعلق دارد؛ لنگرهایِ R32 پیش از بقیه جای می‌گیرند.",
        "", "## کووتا و نتیجه", "",
        "| طبقه | سهم | انتخاب‌شده |", "| --- | --- | --- |",
    ]
    for s in STRATA_FA:
        md.append("| %s | %d | %d |" % (STRATA_FA[s], QUOTA[s],
                                       summary["selected_by_stratum"][s]))
    md += ["", "## نمادها", "",
           "| # | نماد | ins_code | asset | طبقه | دلیل | کندل | بازه | حجمِ صفر | شکاف | رویداد | توقف/بازگشایی |",
           "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for i, r in enumerate(rows, 1):
        notices = "%d/%d" % (r["_json"]["halt_notices"], r["_json"]["reopen_notices"])
        md.append("| %d | %s | %s | %s | %s | %s | %d | %s→%s | %d | %d | %d | %s |"
                  % (i, r["symbol"], r["ins_code"], r["asset_id"] or "-",
                     STRATA_FA[r["stratum"]], r["reason"], r["candles"],
                     r["first_date"], r["last_date"], r["zero_volume"],
                     r["max_gap"], r["adjust_events"] + r["share_events"], notices))
    md += ["", "## شکاف‌ها و محدودیت‌ها", ""]
    if gaps:
        for g in gaps:
            md.append("- " + g)
    else:
        md.append("- همهٔ کووتاها پر شد؛ هیچ طبقه‌ای بی‌نماینده نماند.")
    md += [
        "- `value` در بانک فقط ۹۷٬۶۶۹ ردیف (۲۰۲۶-۰۸-۲۰ به بعد) پر است و نسبتِ آن به",
        "  `close*volume` در %d نمادِ کلِ بانک ≈۱۰۰۰ است (همه غیرِسهام: اوراق/صندوق/اختیار)،"
        % summary["all_unit_factor_1000"],
        "  و در جهانِ سهام %d نماد؛ رتبه‌بندیِ خام این ناسازگاری را نادیده می‌گرفت"
        % summary["equity_unit_factor_1000"],
        "  و این خودش یک یافتهٔ §8 است.",
        "- تاریخچهٔ محلی %d جلسه از %s است، ولی %d نماد فقط ۹۰ جلسه از"
        % (summary["sessions"], summary["date_range"][0], n90_june),
        "  ژوئنِ ۲۰۲۶ دارند (مرزِ backfill تابلویی)؛ این «نبودِ رویداد» نیست،",
        "  «نبودِ ردیف» است.",
        "- %d گروه `l_val18` تکراری در `instruments` و %d نمادِ `price_history`"
        % (summary["duplicate_instrument_keys"], summary["history_symbols_without_instrument"]),
        "  بدونِ ردیفِ `instruments` دیده شد؛ انتخاب‌گر برای هر کلید یک ردیفِ ترجیحی",
        "  (دارایِ ISIN) برمی‌دارد و بقیه را در S8 گزارش می‌کند.",
        "- ستونِ «توقف/بازگشایی» در جدول، شمارِ اعلان‌هایِ داخلِ پرانتز در",
        "  `tsetmc_messages` است (توقف/بازگشایی)؛ تطبیقِ زیررشته‌ای کنار گذاشته شد",
        "  چون نام‌هایِ کوتاه را در تیترهایِ بی‌ربط می‌دید.",
        "- `raw_status`/`adjusted_status` تا S4/S6 برابرِ `NOT_MEASURED` می‌مانند؛",
        "  خروجیِ این فایل انتخاب است، نه ادعایِ تطابق.",
        "", "## بازتولید", "",
        "```bash",
        "python tools/phase45/select_symbols.py \\",
        "  --db _audit/phase45/lab/market.db \\",
        "  --pack data/ra365_corrections/ra365-live40-v1 \\",
        "  --r32 <reference-pack> \\",
        "  --out docs/opportunity-center/phase45",
        "```",
    ]
    with io.open(os.path.join(args.out, "SYMBOLS-30.md"), "w", encoding="utf-8",
                 newline="\n") as fh:
        fh.write("\n".join(md))
    con.close()

    print(json.dumps({"selected": len(selected), "gaps": gaps,
                      "strata": summary["selected_by_stratum"],
                      "anchors": [sym for _, sym in ANCHORS.values()]},
                     ensure_ascii=False, indent=1))
    return 0 if not gaps else 1


if __name__ == "__main__":
    sys.exit(main())
