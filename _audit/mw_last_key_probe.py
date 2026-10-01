# -*- coding: utf-8 -*-
"""قدمِ ۲ — نگاشتِ کلیدهایِ GetMarketWatch به ستون‌هایِ رسمیِ CSV (سنجشِ لحظه، نه فرض).

چرا این سنجش لازم است: `test_tsetmc.py:1309-1313` کلیدِ `pcl` را `p_closing` می‌نامد و
«آخرین» را از `py + pc` می‌سازد، و inventory (§۱) صریح نوشته ««آخرینِ» خام درِ تابلو
نیست». پیش از پرکردنِ ستونِ `last` درِ price_history از مسیرِ تابلو باید عددِ خامِ خودش
پیدا شود، نه جمعِ دو عدد.

روش: بعد از بستنِ نشست، برایِ هر نماد، ردیفِ تابلو با ردیفِ *همان روز* درِ فایلِ رسمیِ
خودِ TSETMC مقابله می‌شود (تاریخ را CSV می‌دهد، نه `dEven`ِ تابلو — سنجشِ اول نشان داد
`dEven` درِ پاسخِ `hEven=0` صفر است و به آن نمی‌شود تکیه کرد). تطبیق با تلورانسِ ۰٫۵ ریال
(عددِ تابلو ریالِ کامل است) و آراِ «کلید == ستون» شمرده گزارش می‌شود؛ کلیدی که درِ هیچ
ستونی نیفتد صریح «بی‌تطبیق» چاپ می‌شود.
"""
import csv
import io
import json
import sys
import urllib.request

sys.path.insert(0, ".")
import test_tsetmc as T  # noqa: E402

# ins_codeها از جدولِ instrumentsِ بانکِ خودِ برنامه (read-only) — بی‌دست‌نویس
CANDIDATES = ["فولاد", "خودرو", "شبندر", "وغدير", "خگستر", "پارس", "تجارت", "zamاد"]
PRICE_KEYS = ("pcl", "pdv", "pmd", "py", "pf", "pc", "pmn", "pmx", "pMax", "pMin",
              "pClosing", "pDrCotVal", "ztd", "vc", "ztt", "qtj", "qtc",
              "qTotTran5J", "qTotCap", "hEven", "dEven")
CSV_COLS = ("FIRST", "HIGH", "LOW", "CLOSE", "OPEN", "LAST", "VOL", "VALUE")
NEAR = 0.5


def board_rows():
    s = T.make_session()
    j = json.loads(s.get(T.MW_URL, headers=T.HEADERS, timeout=120).text)
    return {str(r.get("insCode")): r for r in (j.get("marketwatch") or [])}


def pick_ins(limit=8):
    """(symbol, ins_code) برایِ نمادهایی که درِ price_history کندل دارند (سهامیِ واقعی)."""
    import sqlite3
    from pathlib import Path
    conn = sqlite3.connect(Path(T.DB_PATH).as_uri() + "?mode=ro", uri=True, timeout=30)
    try:
        rows = conn.execute(
            "SELECT ph.symbol, i.ins_code, COUNT(*) n FROM price_history ph "
            "JOIN instruments i ON (i.l_val18 = ph.symbol OR i.l_val30 = ph.symbol) "
            "WHERE ph.symbol IN (%s) GROUP BY ph.symbol ORDER BY n DESC LIMIT ?"
            % ",".join("?" * limit), (*CANDIDATES[:limit], limit)).fetchall()
    finally:
        conn.close()
    return [(s, str(i)) for s, i, _ in rows]


def csv_latest(ins, frm):
    u = f"{T.BASE}/ClosingPrice/GetClosingPriceDailyListCSV/{ins}/{frm}"
    txt = urllib.request.urlopen(urllib.request.Request(u, headers=T.HEADERS),
                                 timeout=150).read().decode("utf-8", "replace")
    rr = list(csv.reader(io.StringIO(txt)))
    head = [h.strip("<>") for h in rr[0]]
    ix = {n: i for i, n in enumerate(head)}
    live = [f for f in rr[1:] if len(f) >= len(head) and f[ix["DTYYYYMMDD"]].strip().isdigit()]
    live.sort(key=lambda f: f[ix["DTYYYYMMDD"]])
    f = live[-1]
    d = f[ix["DTYYYYMMDD"]]
    return f"{d[:4]}-{d[4:6]}-{d[6:]}", {k: float(f[ix[k]]) for k in CSV_COLS if f[ix[k]].strip()}


def main():
    mw = board_rows()
    picks = pick_ins()
    print(f"ردیفِ تابلو: {len(mw):,} | نمادهايِ سنجش: {len(picks)} -> {[p[0] for p in picks]}")
    tally, per_key = {}, {}
    for name, ins in picks:
        row = mw.get(ins)
        if not row:
            print(f"  {name}: درِ پاسخِ تابلو نیست")
            continue
        day, c = csv_latest(ins, "20260920")
        eq = {}
        for k in PRICE_KEYS:
            v = row.get(k)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not v:
                continue
            hits = [col for col in CSV_COLS if c.get(col) and abs(float(v) - c[col]) <= NEAR]
            eq[k] = (v, hits)
            for col in hits:
                tally[(k, col)] = tally.get((k, col), 0) + 1
            per_key.setdefault(k, []).append((name, day, v, hits))
        print(f"  {name} {day} | CSV " + " ".join(f"{k}={c.get(k):.0f}" for k in CSV_COLS))
        print("     " + "  ".join(f"{k}={v:.0f}->{','.join(h) or 'بی‌تطبیق'}"
                                  for k, (v, h) in list(eq.items())[:10]))
    n = len(per_key.get("qtj", []))
    print(f"\nآراِ تطبیق رویِ {n} نماد (کلید == ستونِ CSV، تعدادِ نماد):")
    for (k, col), v in sorted(tally.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"   {k:<12} == {col:<6} : {v}/{n}")
    for k in PRICE_KEYS:
        only = [x for x in per_key.get(k, []) if not x[3]]
        if only and len(only) == len(per_key.get(k, [])):
            print(f"   {k:<12} بی‌تطبیق درِ همهٔ {len(only)} نماد")
    json.dump({"symbols": [p[0] for p in picks],
               "tally": {f"{k}=={c}": v for (k, c), v in sorted(tally.items())},
               "per_key": {k: v for k, v in per_key.items()}},
              open("_audit/mw_key_to_csv_column.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("نوشته شد: _audit/mw_key_to_csv_column.json")


if __name__ == "__main__":
    main()
