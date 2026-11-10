#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage B (finalization): whole-DB inventory on the isolated restored work DB.

Answers: how many symbols exist / have history; candle counts; time coverage;
raw and adjustment coverage; quality flags; gaps; conflicts; which symbols
have no adjustment evidence; and the exact status of the Phase 4.9 30.
Read-only.
"""
import collections
import csv
import gzip
import json
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(ROOT, "_audit", "phase49-finalization", "db", "restored-work.db")
EVID = os.path.join(ROOT, "_audit", "phase49-finalization", "evidence")
PACK = os.path.join(ROOT, "data", "ra365_corrections", "ra365-r32b-v2")
OUT_JSON = os.path.join(EVID, "db-inventory.json")
OUT_MD = os.path.join(ROOT, "_audit", "phase49-finalization", "DB-INVENTORY.md")
SYMS30 = os.path.join(ROOT, "_audit", "phase49", "continuation", "symbols30.csv")


def load_pack():
    by = collections.defaultdict(lambda: {"replace": [], "suppress": []})
    for line in open(os.path.join(PACK, "factors.jsonl"), encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        sym = str(r.get("symbol") or "")
        if not sym:
            continue
        if r.get("action") == "suppress_step":
            by[sym]["suppress"].append(str(r.get("effective_date"))[:10])
        else:
            by[sym]["replace"].append(
                {"date": str(r.get("effective_date"))[:10], "ratio": r.get("ratio")})
    return by


def main():
    os.makedirs(EVID, exist_ok=True)
    con = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
    cur = con.cursor()
    dates = [r[0] for r in cur.execute("SELECT DISTINCT date FROM price_history ORDER BY date")]
    dindex = {d: i for i, d in enumerate(dates)}
    pack = load_pack()
    symbols30 = [r["symbol"] for r in csv.DictReader(open(SYMS30, encoding="utf-8-sig"))]

    per = {}
    src_counts = collections.Counter()
    for sym, n, first, last, dmin, dmax, srcs in cur.execute(
            "SELECT symbol, COUNT(*), MIN(date), MAX(date), MIN(date), MAX(date), "
            "GROUP_CONCAT(DISTINCT src) FROM price_history GROUP BY symbol"):
        per[sym] = {"rows": n, "first": first, "last": last,
                    "srcs": (srcs or "").split(",")}
        for s in (srcs or "").split(","):
            src_counts[s] += 1
    # second pass: quality metrics per symbol (single scan)
    zero = collections.Counter()
    oeqc = collections.Counter()
    hl_bad = collections.Counter()
    vol0 = collections.Counter()
    prev = {}
    for sym, d, o, h, l, c, vol, last_ in cur.execute(
            "SELECT symbol,date,open,high,low,close,volume,last FROM price_history "
            "ORDER BY symbol,date"):
        p = per[sym]
        p.setdefault("zero_field_rows", 0)
        p.setdefault("open_eq_prev_close", 0)
        p.setdefault("hl_invalid_rows", 0)
        p.setdefault("zero_volume_rows", 0)
        if not o or not h or not l or not c:
            p["zero_field_rows"] += 1
        if h and l and (h < l or (c and (c > h or c < l))):
            p["hl_invalid_rows"] += 1
        if not vol:
            p["zero_volume_rows"] += 1
        pc = prev.get(sym)
        if pc and o and pc == o:
            p["open_eq_prev_close"] += 1
        prev[sym] = c
    # gaps against the global trading calendar
    for sym, p in per.items():
        if p["rows"] < 2:
            p["missing_sessions"] = 0
            p["max_gap_sessions"] = 0
            continue
        lo, hi = dindex[p["first"]], dindex[p["last"]]
        sym_dates = [d for (d,) in cur.execute(
            "SELECT date FROM price_history WHERE symbol=? ORDER BY date", (sym,))]
        have = set(sym_dates)
        miss = 0
        gap = 0
        run = 0
        for i in range(lo, hi + 1):
            if dates[i] in have:
                run = 0
            else:
                miss += 1
                run += 1
                gap = max(gap, run)
        p["missing_sessions"] = miss
        p["max_gap_sessions"] = gap
    # stored adjustment events
    ae = collections.defaultdict(list)
    for sym, d, r in cur.execute("SELECT symbol,date,ratio FROM adjust_events ORDER BY date"):
        ae[sym].append((str(d)[:10], r))
    # official ledger
    pae = collections.Counter()
    sce = collections.Counter()
    sym2ins = {}
    for ins, sym in cur.execute(
            "SELECT ins_code,l_val18 FROM instruments WHERE l_val18 IS NOT NULL"):
        sym2ins.setdefault(sym, ins)
    ins_pae = {ins for (ins,) in cur.execute("SELECT DISTINCT ins_code FROM price_adjust_events")}
    ins_sce = {ins for (ins,) in cur.execute("SELECT DISTINCT ins_code FROM share_change_events")}
    for sym, ins in sym2ins.items():
        if ins in ins_pae:
            pae[sym] = 1
        if ins in ins_sce:
            sce[sym] = 1

    total_syms = len(per)
    in_instruments = set(sym for (sym,) in con.execute(
        "SELECT DISTINCT l_val18 FROM instruments WHERE l_val18 IS NOT NULL"))
    con.close()
    only_db = total_syms - len(set(per) & in_instruments)
    no_history = len(in_instruments - set(per))

    def years(sym):
        p = per[sym]
        return (dindex[p["last"]] - dindex[p["first"]] + 1) / 252.0

    buckets = collections.Counter()
    for sym in per:
        y = years(sym)
        if y < 1:
            buckets["<1y"] += 1
        elif y < 5:
            buckets["1-5y"] += 1
        elif y < 10:
            buckets["5-10y"] += 1
        else:
            buckets["10y+"] += 1
    last_date = dates[-1]
    stale = collections.Counter()
    for sym, p in per.items():
        lag = len(dates) - 1 - dindex[p["last"]]
        if lag == 0:
            stale["last_session"] += 1
        elif lag <= 5:
            stale["1-5 sessions"] += 1
        elif lag <= 21:
            stale["6-21 sessions"] += 1
        else:
            stale[">21 sessions"] += 1

    flag_counts = collections.Counter()
    for sym in sorted(set(per) | set(pack) | set(ae) | in_instruments):
        p = per.get(sym, {})
        flags = []
        has_ae = bool(ae.get(sym))
        has_pack = bool(pack.get(sym))
        pre2020 = [e for e in ae.get(sym, []) if e[0] < "2020-01-01"]
        if p:
            if p["rows"] < 2:
                flags.append("single_candle")
            if p.get("zero_field_rows"):
                flags.append("zero_fields")
            if p.get("hl_invalid_rows"):
                flags.append("hl_invalid")
            if p.get("missing_sessions"):
                flags.append("calendar_gaps")
            if p.get("open_eq_prev_close"):
                flags.append("open_eq_prev_close")
        if has_ae:
            flags.append("has_product_events")
        if pre2020:
            flags.append("has_pre2020_events")
        if has_pack:
            flags.append("has_pack_steps")
            if any(s["date"] < "2020-01-01" for s in pack[sym]["replace"]):
                flags.append("pack_pre2020")
        if not has_ae and not has_pack:
            flags.append("no_adjustment_evidence")
        if not p:
            flags.append("no_price_history")
        if pae.get(sym) or sce.get(sym):
            flags.append("has_official_ledger")
        for f in flags:
            flag_counts[f] += 1

    def status30(sym):
        p = dict(per.get(sym) or {})
        p["adjust_events"] = len(ae.get(sym, []))
        p["pre2020_events"] = sum(1 for e in ae.get(sym, []) if e[0] < "2020-01-01")
        p["pack_steps"] = len(pack.get(sym, {}).get("replace", []))
        p["pack_pre2020"] = sum(1 for s in pack.get(sym, {}).get("replace", [])
                                if s["date"] < "2020-01-01")
        p["official_ledger"] = bool(pae.get(sym) or sce.get(sym))
        return p

    out = {
        "schema": "phase49-finalization-db-inventory-v1",
        "db": os.path.relpath(DB, ROOT).replace("\\", "/"),
        "price_history_rows": sum(p["rows"] for p in per.values()),
        "trading_dates": len(dates),
        "date_min": dates[0],
        "date_max": dates[-1],
        "symbols_with_history": total_syms,
        "symbols_in_instruments": len(in_instruments),
        "symbols_instruments_without_history": no_history,
        "symbols_history_not_in_instruments": only_db,
        "symbols_with_product_events": len(ae),
        "symbols_with_pack_steps": len(pack),
        "symbols_with_official_ledger": len(set(pae) | set(sce)),
        "pack_replace_steps_total": sum(len(v["replace"]) for v in pack.values()),
        "pack_suppress_steps_total": sum(len(v["suppress"]) for v in pack.values()),
        "product_events_total": sum(len(v) for v in ae.values()),
        "product_events_pre2020": sum(1 for v in ae.values() for e in v
                                      if e[0] < "2020-01-01"),
        "pack_steps_pre2020": sum(1 for v in pack.values() for s in v["replace"]
                                  if s["date"] < "2020-01-01"),
        "src_symbol_counts": dict(src_counts),
        "coverage_buckets": dict(buckets),
        "staleness": dict(stale),
        "flags": dict(flag_counts),
        "symbols30": {s: status30(s) for s in symbols30},
        "per_symbol": {s: per[s] for s in sorted(per)},
    }
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)

    lines = []
    A = lines.append
    A("# Phase 4.9 finalization — DB-wide inventory")
    A("")
    A("- DB: `%s` (restored isolated copy of the Phase 4.8 work DB)" % out["db"])
    A("- Price rows: **%d**; trading dates: **%d** (%s .. %s)"
      % (out["price_history_rows"], out["trading_dates"], out["date_min"], out["date_max"]))
    A("- Symbols with history: **%d**; in `instruments`: **%d**"
      % (out["symbols_with_history"], out["symbols_in_instruments"]))
    A("- Instruments without history: **%d**; history not in instruments: **%d**"
      % (out["symbols_instruments_without_history"], out["symbols_history_not_in_instruments"]))
    A("")
    A("## Coverage")
    A("")
    A("| metric | value |")
    A("| --- | ---: |")
    A("| Product events (stored) | %d |" % out["product_events_total"])
    A("| Product events pre-2020 | %d |" % out["product_events_pre2020"])
    A("| Symbols with product events | %d |" % out["symbols_with_product_events"])
    A("| Pack replace steps | %d |" % out["pack_replace_steps_total"])
    A("| Pack steps pre-2020 | %d |" % out["pack_steps_pre2020"])
    A("| Symbols with pack steps | %d |" % out["symbols_with_pack_steps"])
    A("| Symbols with official ledger rows | %d |" % out["symbols_with_official_ledger"])
    A("")
    A("| history depth | symbols |")
    A("| --- | ---: |")
    for k in ("10y+", "5-10y", "1-5y", "<1y"):
        A("| %s | %d |" % (k, buckets[k]))
    A("")
    A("| freshness vs last DB session | symbols |")
    A("| --- | ---: |")
    for k in ("last_session", "1-5 sessions", "6-21 sessions", ">21 sessions"):
        A("| %s | %d |" % (k, stale[k]))
    A("")
    A("## Quality flags")
    A("")
    A("| flag | symbols |")
    A("| --- | ---: |")
    for k, v in flag_counts.most_common():
        A("| %s | %d |" % (k, v))
    A("")
    A("## The Phase 4.9 30")
    A("")
    A("| symbol | rows | first | last | events | pre-2020 | pack | pack pre-2020 | ledger |")
    A("| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | --- |")
    for s in symbols30:
        p = out["symbols30"][s]
        A("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            s, p.get("rows", 0), p.get("first", "-"), p.get("last", "-"),
            p["adjust_events"], p["pre2020_events"], p["pack_steps"],
            p["pack_pre2020"], "yes" if p["official_ledger"] else "no"))
    A("")
    A("**This is not Full Database Coverage.** Raw OHLC exists for %d symbols; "
      "adjustment evidence exists for %d (product) / %d (pack) symbols; "
      "independent reference validation exists only where measured elsewhere."
      % (total_syms, len(ae), len(pack)))
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(json.dumps({k: out[k] for k in (
        "price_history_rows", "trading_dates", "symbols_with_history",
        "symbols_in_instruments", "symbols_with_product_events",
        "symbols_with_pack_steps", "product_events_total",
        "product_events_pre2020", "pack_replace_steps_total",
        "pack_steps_pre2020", "coverage_buckets", "staleness")},
        ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
