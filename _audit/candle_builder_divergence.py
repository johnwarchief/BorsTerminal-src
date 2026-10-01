# -*- coding: utf-8 -*-
"""Step 4 — نقشۀ واگراییِ سازنده‌هایِ کندل، اندازه‌گیری‌شده.

قرارداد (§۱-ت/§۱-ث) و موجودی (§۴) می‌گویند هشت سازندۀ کندل داریم. سؤالِ این قدم نیست
«چند تاست» (آن شمارش شد)، سؤال این است: **رویِ یکِ دادۀ یکسان، چند عددِ مختلف
می‌سازند؟** این فایل همان را می‌سنجد — نه با خواندنِ کد، با عبورِ دادنِ ردیف‌هایِ واقعی
از هر مسیر و diffِ عددی.

مسیرهایِ سنجیده‌شده (همۀ ورودی‌شان یکی است: ردیف‌هایِ CSVِ خودِ تپ‌سیت‌مک و ردیف‌هایِ
daily_pricesِ همان بانک):

  A `_parse_tsetmc_csv`            — کندلِ RAMِ `/api/chart`
  B `fetch_price_history`          — CSV → `price_history`
  C `sync_price_history_from_daily` — تابلو (daily_prices) → `price_history`
  D `get_chart_db`                 — `price_history` → payload
  E `get_key_levels` / F `get_patterns` / G `/api/ma` — همان تاریخچه با مصرف‌کنندهٔ خودش
  H `confidence_engine._bars`      — سریِ تکنیکالِ واچ‌لیست
  I `api/screener.get_history`     — سریِ غربگر
  J `api/market_index`             — کندلِ شاخص (open ساختگی — درِ این سنجش بیرون است)

برایِ هر جفت، رویِ روزهایِ مشترک شمرده می‌شود: mismatchِ open/high/low/close/last/volume،
و نوعِ واگرایی (field-mapping / geometry / dedupe / adjustment / missing).
خروجی: `_audit/candle_builder_divergence.json`
"""
import json
import os
import sqlite3
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import price_basis  # noqa: E402
import test_tsetmc as T  # noqa: E402

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "market.db")
SYMS = [("فولاد", "46348559193224090"), ("خگستر", "48990026850202503"),
        ("شبندر", "35366681030756042")]
SINCE = "2026-06-01"
FIELDS = ("open", "high", "low", "close", "last", "volume")


def norm(d):
    """کندل → dictِ واحدِ روز→مقادیر، بی‌تعدادِ رقمِ اعشار."""
    return {c["time"] or c.get("date"): {k: (round(float(c[k]), 4) if c.get(k) is not None else None)
                                          for k in FIELDS} for c in d}


def diff(a, b, la, lb):
    days = sorted(set(a) & set(b))
    # فقط فیلدهایی که دو طرف **هر دو** می‌فرستند مقابله می‌شوند؛ مثلاً
    # `confidence_engine._bars` عمداً open/high/low را درِ بازگشتِاش ندارد، پس
    # نبودنشان واگرایی نیست — اگر شمردنشان می‌شد سنجشِ پوچ تولید می‌شد.
    fields = [f for f in FIELDS
              if any(f in v for v in a.values()) and any(f in v for v in b.values())]
    out = {"pair": f"{la} ⇄ {lb}", "fields_compared": fields,
           "shared_days": len(days),
           "only_in_a": len(set(a) - set(b)), "only_in_b": len(set(b) - set(a)),
           "field_mismatch": {}, "examples": []}
    for f in fields:
        bad = [d for d in days if a[d].get(f) != b[d].get(f)]
        out["field_mismatch"][f] = len(bad)
        for d in bad[:2]:
            out["examples"].append({"day": d, "field": f, la: a[d].get(f), lb: b[d].get(f)})
    geo = [e for e in out["examples"] if e["field"] in ("high", "low")]
    mapping = [e for e in out["examples"] if e["field"] in ("open", "last")]
    out["class_geometry"] = len(geo)
    out["class_field_mapping"] = len(mapping)
    return out


def main():
    work = tempfile.mkdtemp(prefix="cbd_")
    import bors_config
    bors_config.PRICE_BASIS_PATH = os.path.join(work, "price_basis.json")
    price_basis._cache["sig"] = None
    copy = os.path.join(work, "copy.db")
    a = sqlite3.connect(Path(DB).as_uri() + "?mode=ro", uri=True, timeout=30)
    b = sqlite3.connect(copy)
    with b:
        a.backup(b)
    a.close(); b.close()
    import mstat_engine
    c = sqlite3.connect(copy)
    mstat_engine.ensure_schema(c); c.close()
    T.DB_PATH = copy
    import api._core as CORE
    import api.chart as CH
    import api.screener as SC
    CORE.DB_PATH = CH.DB_PATH = SC.DB_PATH = copy

    report = {"since": SINCE, "symbols": {}, "pairs": [], "notes": []}
    for name, ins in SYMS:
        entry = {"A_ram": None, "B_CSV_to_db": None, "C_board_to_db": None}
        # A: RAM candles از همان CSV
        txt = urllib.request.urlopen(urllib.request.Request(
            f"{T.BASE}/ClosingPrice/GetClosingPriceDailyListCSV/{ins}/{SINCE.replace('-', '')}",
            headers=T.HEADERS), timeout=150).read().decode("utf-8", "replace")
        candles_a, _vols, _all = CH._parse_tsetmc_csv(txt)
        entry["A_ram"] = norm(candles_a)
        # B: همان CSV → بانکِ کپی (increment بسته به دادهٔ موجود، پس پنجره صریح)
        n = T.fetch_price_history(name, since=SINCE)
        entry["B_rows_written"] = n
        # C: تابلو → بانک (رویِ همان کپی، اگر daily_prices آن روزها را داشته باشد)
        sc = T.sync_price_history_from_daily(sqlite3.connect(copy), full=True)
        entry["C_board_rows"] = sc.get("rows")

        con = sqlite3.connect(copy)
        rows = {r[0]: {k: (round(float(x), 4) if x is not None else None)
                       for k, x in zip(FIELDS, r[1:])}
                for r in con.execute(
                    "SELECT date, open, high, low, close, volume, last FROM price_history "
                    "WHERE symbol=? AND date>=?", (name, SINCE)).fetchall()}
        con.close()
        entry["D_db_after_B_and_C"] = rows
        # D/E/F/G/H/I: مصرف‌کننده‌ها
        price_basis.set_basis("closing")
        db_res = CH.get_chart_db(name)
        entry["D_chartdb"] = norm(db_res.get("candles") or [])
        entry["G_ma"] = {(m[0]): {"close": round(float(m[1]), 4) if m[1] is not None else None}
                         for m in (CH.get_ma_events(name, 730).get("ma", {}).get("ma5") or [])
                         if m[1] is not None}
        hl = CH.get_key_levels(name)
        entry["E_keylevels_n"] = len(hl.get("levels") or [])
        pt = CH.get_patterns(name)
        entry["F_patterns_n"] = len(pt.get("overlays") or [])
        import confidence_engine as CE
        con = sqlite3.connect(copy)
        bars, _used = CE._bars(con, name, None, limit=250)
        con.close()
        entry["H_confidence"] = {r[0]: {"close": round(float(r[1]), 4)} for r in bars}
        hist = SC.get_history(name)
        entry["I_screener"] = norm(hist.get("candles") or [])
        report["symbols"][name] = {k: (len(v) if isinstance(v, dict) else v)
                                   for k, v in entry.items() if k != "pairs"}
        p = []
        p.append(diff(entry["A_ram"], entry["D_chartdb"], "A_ram", "D_chartdb"))
        p.append(diff(entry["D_chartdb"], entry["I_screener"], "D_chartdb", "I_screener"))
        p.append(diff(entry["D_chartdb"], entry["H_confidence"], "D_chartdb", "H_confidence"))
        p.append(diff(entry["A_ram"], entry["D_db_after_B_and_C"], "A_ram", "B+C_db"))
        for x in p:
            x["symbol"] = name
            report["pairs"].append(x)
        print(f"--- {name}: A={len(entry['A_ram'])} db={len(entry['D_chartdb'])} "
              f"screener={len(entry['I_screener'])} confidence={len(entry['H_confidence'])} "
              f"| B نوشت {n} | C نوشت {sc.get('rows')}")
        for x in p:
            if any(x["field_mismatch"].values()) or x["only_in_a"] or x["only_in_b"]:
                print("   ", json.dumps({k: v for k, v in x.items()
                                         if k in ("pair", "shared_days", "only_in_a",
                                                  "only_in_b", "field_mismatch")}, ensure_ascii=False))
    # خلاصۀ کلِ جفت‌ها
    agg = {}
    for x in report["pairs"]:
        k = x["pair"]
        a0 = agg.setdefault(k, {"shared": 0, "mismatch": {f: 0 for f in FIELDS},
                               "only_left": 0, "only_right": 0, "worst": []})
        a0["shared"] += x["shared_days"]
        a0["only_left"] += x["only_in_a"]
        a0["only_right"] += x["only_in_b"]
        for f, n2 in x["field_mismatch"].items():
            a0["mismatch"][f] = a0["mismatch"].get(f, 0) + n2
        a0["worst"].extend(x["examples"][:2])
    report["aggregate"] = agg
    print("\n=== aggregate ===")
    print(json.dumps({k: {"shared": v["shared"], "mismatch": v["mismatch"],
                          "only_left": v["only_left"], "only_right": v["only_right"]}
                      for k, v in agg.items()}, ensure_ascii=False, indent=1))
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "candle_builder_divergence.json")
    json.dump(report, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    import shutil
    shutil.rmtree(work, ignore_errors=True)
    print("نوشته شد:", p)


if __name__ == "__main__":
    main()
