"""بک‌فیلِ `price_history` از روزنۀِ منتشرشدۀِ TSETMC — تا پنجرۀِ `[ih]` واقعی شود.

چرا لازم است: پنج فیلترِ فایل مبناءِ حجم و پلکانِ مقاومت و کفِ ۲۹ روزه را از
`[ih]` می‌خوانند، و `[ih]` درِ موتورِ فیلترنویسِ خودِ سایت یعنی «آرایۀِ
روزنۀِ انتشاریافتهٔ همان نماد، نزولی بر dEven». بانکِ ما فقط ۲۲ نشستِ
`daily_prices` و برایِ نیمیِ نمادها هیچ `price_history` ندارد — پس پنجره یا
NaN است یا کوتاه، و داوریِ ما با TSETMC فرق می‌کند (سنجشِ ۱۴۰۵-۰۷-۰۵: چهار
ردیفِ «حجم مشکوک» و دو ردیفِ «نقطه‌زنیِ» مرجع هیچ مبنایی درِ بانکِ ما
نداشتند).

منبع: `ClosingPrice/GetInstrmentsHistoryInDay/{dEven}` — یکِ درخواست برایِ
کلِ بازار درِ یک نشست (~۹۰۰KB، ۲٬۲۰۰ نمادِ معاملۀ‌آن روز). شست نشست ≈ ۷۵
درخواست. این همان ردیف‌هایِ روزینۀِ `GetClosingPriceDailyAllInst` است که
`ExecFilter` با آن `[ih]` را می‌سازد؛ نشستی که در آن روز نماد معامله نشده
ردیف ندارد، دقیقاً مثلِ خودِ آرایه.

اجرا:
  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tools/backfill_daily_history.py [--sessions 60] [--dry]
"""
import argparse
import datetime as dt
import os
import sqlite3
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://cdn.tsetmc.com/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://tsetmc.com/",
    "Origin": "https://tsetmc.com",
}
KEY = "closingPriceDailyHistoryWithInstDetails"
DB = os.environ.get("BORS_DB", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "market.db"))
# روزهایِ تقویمی که تا آن‌ها به عقب می‌رویم تا ۶۰ نشستِ واقعی جور شود: جمعه
# تعطیل است و مناسبات هم هستند، پس ۲٫۵ برابرِ پنجره کافی است و اضافه‌ها
# پاسخِ تهی می‌دهند (بی‌هزینه: ۴۶ بایت).
LOOKAHEAD_DAYS = 150


def sessions_back(until):
    """تقویمِ نشست‌ها: هرچه روزنۀِ market_watch نشان بدهد یکِ نشستيِ واقعی است.

    این فقط «روزهایی که ممکن است نشست باشند» را می‌دهد؛ نشستنِ واقعی از خودِ
    پاسخِ سایت خوانده می‌شود (پاسخِ تهی = نشست نبود).
    """
    days, cur = [], until
    for _ in range(LOOKAHEAD_DAYS):
        days.append(cur)
        cur -= dt.timedelta(days=1)
    return days


def fetch_day(s, d):
    r = s.get(f"{BASE}/ClosingPrice/GetInstrmentsHistoryInDay/{d:%Y%m%d}", headers=HEADERS, timeout=90)
    if r.status_code != 200:
        return None, r.status_code
    try:
        return r.json().get(KEY) or [], None
    except ValueError:
        return None, "not-json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", type=int, default=60)
    ap.add_argument("--dry", action="store_true", help="بنویس نه؛ فقط اندازه‌گیری")
    args = ap.parse_args()

    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA journal_mode=WAL")
    latest = conn.execute("SELECT MAX(d_even) FROM market_watch").fetchone()[0]
    if not latest:
        sys.exit("bank: no market_watch rows")
    until = dt.datetime.strptime(str(latest), "%Y%m%d")
    print(f"پایانِ پنجره از market_watch: {until:%Y-%m-%d} — {args.sessions} نشست sought می‌شود")

    have = conn.execute("SELECT COUNT(DISTINCT date) FROM price_history WHERE date >= ?",
                        (f"{until:%Y-%m-%d}",)).fetchone()[0]
    print(f"ردیفِ روزینۀِ موجود درِ price_history برایِ این بازه: {have}")

    ins_map = {str(r[0]): r[1] for r in conn.execute(
        "SELECT ins_code, l_val18 FROM instruments WHERE l_val18 IS NOT NULL")}
    s = requests.Session()
    s.headers.update(HEADERS)

    written = days_done = 0
    for d in sessions_back(until):
        if days_done >= args.sessions:
            break
        try:
            rows, err = fetch_day(s, d)
        except Exception as e:  # noqa: BLE001
            print(f"  {d:%Y-%m-%d}: {type(e).__name__} — رد می‌شود")
            time.sleep(1.0)
            continue
        if err or not rows:
            continue                      # تعطیل یا انتشار نیافته — نشست نیست
        days_done += 1
        date = f"{d:%Y-%m-%d}"
        batch = []
        for x in rows:
            sym = ins_map.get(str(x.get("insCode"))) or x.get("lVal18AFC")
            if not sym:
                continue
            try:
                op = float(x.get("priceFirst") or 0)
                hi = float(x.get("priceMax") or 0)
                lo = float(x.get("priceMin") or 0)
                cl = float(x.get("pClosing") or 0)
                vol = float(x.get("qTotTran5J") or 0)
            except (TypeError, ValueError):
                continue
            batch.append((sym, date, op, hi, lo, cl, vol))
        if not args.dry:
            conn.executemany("INSERT OR REPLACE INTO price_history VALUES (?,?,?,?,?,?,?)", batch)
            conn.commit()
        written += len(batch)
        print(f"  {d:%Y-%m-%d}: {len(batch)} ردیف (نشستِ {days_done}/{args.sessions})")
        time.sleep(0.4)

    print(f"\n{'DRY ' if args.dry else ''}نوشته‌شد: {written} ردیف درِ {days_done} نشست")
    if not args.dry:
        per = conn.execute(
            "SELECT COUNT(DISTINCT symbol), COUNT(DISTINCT date) FROM price_history "
            "WHERE date >= date(?, '-60 days')", (f"{until:%Y-%m-%d}",)).fetchone()
        print(f"پوششِ ۶۰ روزۀِ price_history اکنون: {per[0]} نماد × {per[1]} روز")
    conn.close()


if __name__ == "__main__":
    main()
