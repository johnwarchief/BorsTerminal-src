# -*- coding: utf-8 -*-
"""build_mobile_snapshot.py — سازندهٔ اسنپ‌شات موبایل (فاز ۱ اپ اندروید).

معماری اپ موبایل (بدون سرور، بدون PC روشن):
  * دادهٔ کُند (بنیادی/FTS/اسکرینر) روی PC با «همین منطق دسکتاپ» پخته و
    داخل اسنپ‌شات می‌رود → گوشی فقط JSON آماده را می‌خواند.
  * دادهٔ زنده (تابلو/قیمت لحظه‌ای) را خود گوشی مستقیم از cdn.tsetmc.com
    می‌گیرد (IP ایرانی گوشی از هر سروری برای TSETMC بهتر است).
  * تاریخچهٔ چارت از جدول price_history داخل همین اسنپ‌شات، روی خود گوشی.

روش پخت: به‌جای بازنویسی منطق ۲۵۸۵ خطی بنیادی، از TestClient خودِ FastAPI
روی app.py استفاده می‌شود تا خروجیِ ذخیره‌شده «بایت‌به‌بایت» همان چیزی باشد
که اپ دسکتاپ می‌دهد — برابری تضمینی، بدون نگه‌داری دو نسخه منطق.

خروجی:
  mobile_snapshot.db        (SQLite: جدول baked + جدول‌های خام موردنیاز گوشی)
  mobile_snapshot.db.lzma   (برای آپلود روی GitHub Releases)

اجرا (روی PC یا CI، با market.db موجود):
  python scripts/build_mobile_snapshot.py [--out DIR] [--limit N] [--no-lzma]

ساختار جدول baked:
  baked(key TEXT PRIMARY KEY, json TEXT, fetched_at TEXT)
  کلیدها: screener · fts · fts_config · market_board · sectors ·
          fundamental/<نماد> · quarters/<نماد> · mstat/<نام> · calendar
"""
import argparse
import json
import lzma
import os
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)  # DB_PATH نسبی به CWD حل می‌شود (پروتکل ۲ در REPO_MAP)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError, OSError):
    pass

# جدول‌های خامی که خود گوشی لازم دارد (چارت آفلاین + fallback تابلو).
# جدول‌های کدال خام (financial_statements/monthly_sales/codal_notices) عمداً
# کپی نمی‌شوند: خروجی پخته‌شان در baked هست و حذفشان اسنپ‌شات را سبک می‌کند.
RAW_TABLES = (
    "instruments",
    "market_watch",
    "price_history",
    "boards",
    "market_index",
    "market_totals",
    "market_liquidity",
    "mstat_snap",
)

# اندپوینت‌های سراسری (یک‌بار پخت). نام کلید ↔ مسیر.
GLOBAL_ENDPOINTS = {
    "screener": "/api/screener",
    "fts": "/api/fts",
    "fts_config": "/api/fts/config",
    "market_board": "/api/market",
    "sectors": "/api/fundamental/sectors",
    "mstat/summary": "/api/mstat/summary",
    "mstat/thermometer": "/api/mstat/thermometer",
    "mstat/depth": "/api/mstat/depth",
    "mstat/industries": "/api/mstat/industries",
    "mstat/smart-money": "/api/mstat/smart-money",
    "mstat/timeline_cum": "/api/mstat/timeline?mode=cum",
    "index/tedpix": "/api/index/tedpix?limit=0",
    # بازه‌های پرکاربرد useCalendarUpcoming (پیش‌فرض ۱۴)
    "calendar/upcoming/7": "/api/calendar/upcoming?days=7",
    "calendar/upcoming/14": "/api/calendar/upcoming?days=14",
    "calendar/upcoming/30": "/api/calendar/upcoming?days=30",
    "calendar/upcoming/60": "/api/calendar/upcoming?days=60",
    "calendar/upcoming/90": "/api/calendar/upcoming?days=90",
}

# اندپوینت‌های هر-نماد: قالب کلید ↔ قالب مسیر
PER_SYMBOL_ENDPOINTS = (
    ("fundamental/{s}", "/api/fundamental/{s}"),
    ("quarters/{s}", "/api/fundamental/{s}/quarters"),
    ("fts/{s}", "/api/fts/{s}"),
    ("orderbook/{s}", "/api/order-book/{s}"),
    ("calendar/{s}", "/api/calendar/{s}"),
)


def _symbols_from_screener(payload) -> list:
    """فهرست نمادها از خروجی /api/screener (کلید data، ستون symbol)."""
    if not isinstance(payload, dict):
        return []
    rows = payload.get("data") or []
    out = []
    for r in rows:
        s = (r.get("symbol") or "").strip() if isinstance(r, dict) else ""
        if s:
            out.append(s)
    return out


def build(out_dir: str, limit: int = 0, do_lzma: bool = True) -> str:
    from fastapi.testclient import TestClient  # import دیرهنگام: بعد از chdir
    import app as appmod

    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    out_db = os.path.join(out_dir, "mobile_snapshot.db")
    if os.path.exists(out_db):
        os.remove(out_db)

    dst = sqlite3.connect(out_db)
    dst.execute("CREATE TABLE baked (key TEXT PRIMARY KEY, json TEXT, fetched_at TEXT)")
    dst.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")

    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    ok, fail = 0, 0

    def put(key: str, payload) -> None:
        nonlocal ok
        dst.execute(
            "INSERT OR REPLACE INTO baked(key, json, fetched_at) VALUES (?,?,?)",
            (key, json.dumps(payload, ensure_ascii=False, separators=(",", ":")), now),
        )
        ok += 1

    # گارد لوپ‌بک app.py میزبان testserver را رد می‌کند → base_url لوپ‌بک.
    with TestClient(appmod.app, base_url="http://127.0.0.1:8001") as client:

        def get(path: str):
            nonlocal fail
            try:
                r = client.get(path)
                if r.status_code == 200:
                    return r.json()
                print(f"  [skip] {path} → {r.status_code}")
            except Exception as e:  # noqa: BLE001 — پختِ ناقص بهتر از هیچ است
                print(f"  [skip] {path} → {type(e).__name__}: {e}")
            fail += 1
            return None

        # ۱) اندپوینت‌های سراسری
        screener_payload = None
        for key, path in GLOBAL_ENDPOINTS.items():
            data = get(path)
            if data is not None:
                put(key, data)
                if key == "screener":
                    screener_payload = data

        # ۲) کارت بنیادی + فصل‌ها برای هر نماد اسکرینر
        symbols = _symbols_from_screener(screener_payload)
        if limit:
            symbols = symbols[:limit]
        print(f"[bake] {len(symbols)} نماد × {len(PER_SYMBOL_ENDPOINTS)} اندپوینت…")
        from urllib.parse import quote
        for i, sym in enumerate(symbols, 1):
            enc = quote(sym, safe="")
            for key_t, path_t in PER_SYMBOL_ENDPOINTS:
                data = get(path_t.format(s=enc))
                if data is not None:
                    put(key_t.format(s=sym), data)
            if i % 100 == 0:
                print(f"  …{i}/{len(symbols)} ({time.time()-t0:.0f}s)")
                dst.commit()

    # ۳) تقویم رویدادها (فایل ایستا، بدون سرور)
    cal_path = os.path.join(ROOT, "static", "calendar", "cache.json")
    if os.path.exists(cal_path):
        try:
            with open(cal_path, encoding="utf-8") as f:
                put("calendar", json.load(f))
        except (OSError, ValueError) as e:
            print(f"  [skip] calendar → {e}")

    # ۴) کپی جدول‌های خام از market.db
    from bors_config import DB_PATH
    dst.execute("ATTACH DATABASE ? AS src", (DB_PATH,))
    src_tables = {
        r[0] for r in dst.execute(
            "SELECT name FROM src.sqlite_master WHERE type='table'")
    }
    for t in RAW_TABLES:
        if t not in src_tables:
            print(f"  [skip] جدول {t} در market.db نیست")
            continue
        dst.execute(f'CREATE TABLE "{t}" AS SELECT * FROM src."{t}"')
    dst.commit()
    try:
        dst.execute("DETACH DATABASE src")
    except sqlite3.OperationalError:
        # ترددهای پس‌زمینهٔ app.py (board/pulse) ممکن است WAL منبع را قفل
        # نگه دارند؛ بستن اتصال در انتها خودش DETACH می‌کند.
        pass
    # ایندکس‌های موردنیاز کوئری چارت روی گوشی
    if "price_history" in src_tables:
        dst.execute("CREATE INDEX idx_ph_symbol ON price_history(symbol, date)")

    # ۵) متادیتا (نسخه از همان لنگر رسمی)
    from bors_config import APP_VERSION
    for k, v in (
        ("app_version", APP_VERSION),
        ("built_at", now),
        ("schema", "1"),
        ("baked_ok", str(ok)),
        ("baked_fail", str(fail)),
    ):
        dst.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?,?)", (k, v))

    dst.commit()
    dst.execute("VACUUM")
    dst.close()

    size_mb = os.path.getsize(out_db) / 1048576
    print(f"[bake] baked={ok} skip={fail} · {out_db} = {size_mb:.1f}MB "
          f"· {time.time()-t0:.0f}s")

    # gzip اول و همیشه: خروجی اصلی گوشی است (DecompressionStream بومی WebView)
    # و حافظهٔ ناچیز می‌خواهد؛ lzma بعدش می‌آید تا اگر روی ماشین کم‌حافظه
    # OOM شد، دست‌کم gz سالم مانده باشد.
    import gzip
    gz = out_db + ".gz"
    with open(out_db, "rb") as fi, gzip.open(gz, "wb", compresslevel=9) as fo:
        while True:
            chunk = fi.read(1 << 24)
            if not chunk:
                break
            fo.write(chunk)
    print(f"[bake] {gz} = {os.path.getsize(gz)/1048576:.1f}MB")

    # متای کوچک کنار gz برای بروزرسانی خودکارِ درون‌برنامه‌ای: کلاینت روی گوشی
    # فقط همین فایل ~۲۰۰ بایتی را روزانه از GitHub Releases چک می‌کند و اگر
    # built_at جدیدتر بود gz کامل را در پس‌زمینه می‌کشد (localData.ts).
    meta_json = out_db + ".meta.json"
    with open(meta_json, "w", encoding="utf-8") as fo:
        json.dump({
            "app_version": APP_VERSION,
            "built_at": now,
            "baked_ok": ok,
            "gz_bytes": os.path.getsize(gz),
        }, fo, ensure_ascii=False, indent=1)
    print(f"[bake] {meta_json}")

    if do_lzma:
        lz = out_db + ".lzma"
        with open(out_db, "rb") as fi, lzma.open(lz, "wb", preset=6) as fo:
            while True:
                chunk = fi.read(1 << 24)
                if not chunk:
                    break
                fo.write(chunk)
        print(f"[bake] {lz} = {os.path.getsize(lz)/1048576:.1f}MB")
    return out_db


def main() -> None:
    ap = argparse.ArgumentParser(description="سازندهٔ اسنپ‌شات موبایل")
    ap.add_argument("--out", default=os.path.join(ROOT, "dist_mobile"),
                    help="پوشهٔ خروجی (پیش‌فرض: dist_mobile/ — gitignored)")
    ap.add_argument("--limit", type=int, default=0,
                    help="فقط N نماد اول (برای تست سریع)")
    ap.add_argument("--no-lzma", action="store_true", help="بدون فشرده‌سازی")
    args = ap.parse_args()
    build(args.out, limit=args.limit, do_lzma=not args.no_lzma)


if __name__ == "__main__":
    main()
