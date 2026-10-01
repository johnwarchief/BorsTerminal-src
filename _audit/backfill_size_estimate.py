# -*- coding: utf-8 -*-
"""برایِ تصمیمِ مالک — حجمِ تقریبیِ backfillِ عمق، اندازه گرفته شده نه حدس.

پرسش: با لغوِ هرسِ ۷۳۰روزه، «اولینِ اجرایِ `--backfill-history`» چند ردیف و چند بایت
به `price_history` اضافه می‌کند؟

روش (بی‌اجرایِ backfillِ کامل):
  ۱) نمادهایِ فعال از خودِ بانک (read-only) — همان تعریفی که `/api/chart` می‌شناسد.
  ۲) بیستِ آن‌ها (لایۀ اول/وسط/آخرِ فهرستِ الفبایی، تا نمونه تک‌رنگ نباشد) از منبع
     CSV با کفِ ۱۹۹۰۰۱۰۱ خوانده می‌شوند: تعدادِ ردیفِ *منتشرشده* و اولین/آخرینِ روز.
  ۳) درِ همان لحظه از بانک خوانده می‌شود: چند ردیف *داریم* و اولینِ روزمان چیست.
  ۴) تفاضلِ اندازه‌گیریشده × تعدادِ نمادهایِ فعال = تخمینِ ردیفِ اضافه.
  ۵) بایتِ هر ردیف از خودِ بانکِ کپی‌شده با `dbstat` (و فال‌بکِ اندازه‌یِ ردیفِ نمونه)
     در می‌آید، پس تبدیلِ ردیف→مگابایت هم اندازه است نه فرض.

خروجی درِ `_audit/backfill_size_estimate.json` می‌نشیند.
"""
import json
import os
import sqlite3
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import test_tsetmc as T  # noqa: E402

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "market.db")
SAMPLE = 20


def published(ins_code):
    u = f"{T.BASE}/ClosingPrice/GetClosingPriceDailyListCSV/{ins_code}/{T.CSV_FLOOR}"
    txt = urllib.request.urlopen(urllib.request.Request(u, headers=T.HEADERS),
                                 timeout=150).read().decode("utf-8", "replace")
    rows = [r for r in txt.splitlines()[1:] if r.strip()]
    days = sorted(r.split(",")[1] for r in rows if len(r.split(",")) > 2)
    return len(rows), (days[0] if days else None), (days[-1] if days else None)


def stored(conn, sym):
    r = conn.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM price_history WHERE symbol=?",
                     (sym,)).fetchone()
    return r[0] or 0, r[1], r[2]


def _day(i):
    import datetime as _dt
    return (_dt.date(1980, 1, 1) + _dt.timedelta(days=i)).isoformat()


def row_bytes(conn):
    """بایتِ واقعیِ هر ردیف — تجربی، نه فرمولِ تقریبی.

    dbstat در buildهایِ پایتونِ ویندوز معمولاً نیست (اینجا نبود)، و طولِ ستون‌ها هم
    overhead صفحۀ SQLite را نمی‌دهد. پس اندازه‌گیریِ مستقیم: رویِ یکِ کپیِ موقت،
    ۵٬۰۰۰ ردیفِ نمونه می‌نویسیم و تفاضلِ اندازهٔ فایل را بر تعدادِ ردیف تقسیم می‌کنیم.
    """
    import shutil
    import tempfile
    src = conn.execute("SELECT symbol, date, open, high, low, close, volume, last, value "
                       "FROM price_history ORDER BY RANDOM() LIMIT 400").fetchall()
    if not src:
        return None, "no rows"
    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        a = sqlite3.connect(Path(DB).as_uri() + "?mode=ro", uri=True, timeout=30)
        b = sqlite3.connect(tmp)
        with b:
            a.backup(b)
        a.close()
        b.isolation_level = None   # autocommit: VACUUM درِ میانهٔ تراکنش مجاز نیست
        b.execute("PRAGMA journal_mode=DELETE")
        b.execute("VACUUM")
        base = os.path.getsize(tmp)
        n = 5000
        b.executemany("INSERT INTO price_history (symbol, date, open, high, low, close, volume)"
                      " VALUES (?,?,?,?,?,?,?)",
                      [("__probe__", _day(i), 1.0, 2.0, 0.5, 1.5, 1.0) for i in range(n)])
        b.commit()
        b.execute("VACUUM")
        grown = (os.path.getsize(tmp) - base) / n
        # و همان با ردیفِ پُر (last/value پر) تا سقفِ بالایی هم داشته باشیم
        b.execute("DELETE FROM price_history WHERE symbol LIKE '__probe%__'")
        b.execute("VACUUM")
        base2 = os.path.getsize(tmp)
        b.executemany("INSERT INTO price_history (symbol, date, open, high, low, close, volume, last, value)"
                      " VALUES (?,?,?,?,?,?,?,?,?)",
                      [("__probef__", _day(i), 1.0, 2.0, 0.5, 1.5, 1.0, 1.4, 1.2e12)
                       for i in range(n)])
        b.commit()
        b.execute("VACUUM")
        full = (os.path.getsize(tmp) - base2) / n
        return (round(grown, 2), round(full, 2)), "vacuum-delta (sparse, full)"
    finally:
        b.close()
        os.unlink(tmp)


def main():
    conn = sqlite3.connect(Path(DB).as_uri() + "?mode=ro", uri=True, timeout=30)
    # نمونۀ **تصادفی** با seedِ ثابت. اولینِ اجرای این فایلِ همان نمادها را به‌صورت
    # الفبایی برمی‌داشت و نتیجه را بالا می‌برد (غمينو/واميد3 عمقِ پرتاریخچه دارند؛
    # صندوق‌هایِ تازه تأسیس صفر اضافه می‌گیرند). تخمینِ سوگرفته برایِ تصمیمِ مالک نیست.
    picks = [r[0] for r in conn.execute(
        "SELECT symbol FROM (SELECT DISTINCT symbol FROM price_history) ORDER BY RANDOM() LIMIT ?",
        (SAMPLE,)).fetchall()]
    active = conn.execute("SELECT COUNT(*) FROM instruments WHERE ins_code IS NOT NULL").fetchone()[0]
    with_hist = conn.execute("SELECT COUNT(DISTINCT symbol) FROM price_history").fetchone()[0]
    out = {"sampled": len(picks), "symbols_with_history": with_hist,
           "instruments": active, "per_symbol": [], "rows_bytes_source": None,
           "sampling": "ORDER BY RANDOM() LIMIT %d (unbiased, seedless — تکرارِ اجرا عدد را عوض می‌کند)" % SAMPLE}
    for sym in picks:
        ins = conn.execute("SELECT ins_code FROM instruments WHERE l_val18=? OR l_val30=? LIMIT 1",
                           (sym, sym)).fetchone()
        if not ins:
            continue
        try:
            p_n, p_first, p_last = published(str(ins[0]))
        except Exception as e:  # noqa: BLE001
            print(f"  {sym}: منبع پاسخ نداد ({type(e).__name__})")
            continue
        s_n, s_first, s_last = stored(conn, sym)
        delta = max(0, p_n - s_n)
        out["per_symbol"].append({"symbol": sym, "published": p_n, "stored": s_n,
                                  "delta": delta, "source_first": p_first,
                                  "stored_first": s_first})
        print(f"  {sym:<10} منبع={p_n:>5} ما={s_n:>5} اضافهٔ تخمینی={delta:>5}  "
              f"(اولینِ منبع {p_first} | اولینِ ما {s_first})")
    conn.close()
    if not out["per_symbol"]:
        print("نمونه‌ای سنجیده نشد — عددی گزارش نمی‌شود")
        return 1
    deltas = sorted(x["delta"] for x in out["per_symbol"])
    mean_delta = sum(deltas) / len(deltas)
    median_delta = deltas[len(deltas) // 2]
    cp = sqlite3.connect(Path(DB).as_uri() + "?mode=ro", uri=True, timeout=30)
    rb, src = row_bytes(cp)
    cp.close()
    out["delta_mean"] = round(mean_delta, 1)
    out["delta_median"] = median_delta
    out["delta_min"], out["delta_max"] = deltas[0], deltas[-1]
    out["row_bytes"] = rb
    out["row_bytes_source"] = src
    for tag, d in (("mean", mean_delta), ("median", median_delta)):
        out[f"estimated_added_rows_{tag}"] = int(round(d * with_hist))
        if rb:
            sparse, full = rb
            out[f"estimated_added_mb_{tag}"] = [round(d * with_hist * sparse / 2**20, 1),
                                                round(d * with_hist * full / 2**20, 1)]
    out["note"] = ("دو عددِ MB = [حالتِ کم، حالتِ پُر]: rowsِ بدونِ last/value و rowsِ کامل. "
                   "میانگینِ نمونۀ %d نماد ضرب‌درِ %s نمادِ دارایِ تاریخچه؛ میانه گزارش می‌شود "
                   "چون توزیعِ دمِ سنگین است." % (len(out["per_symbol"]), f"{with_hist:,}"))
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backfill_size_estimate.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n" + json.dumps({k: v for k, v in out.items() if k != "per_symbol"},
                            ensure_ascii=False, indent=1))
    print("نوشته شد:", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
