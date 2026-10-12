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
import hashlib
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

# جدول‌های خامی که خود گوشی واقعاً می‌خواند. تنها دو کوئری روی جدول‌های خام
# درِ موبایل هست (resolvers.ts و selectionLocal.ts): کندل از price_history و
# نماد/جست‌وجو از instruments. بقیهٔ جدول‌ها — از جمله mstat_snap که یک‌تنه
# بزرگ‌ترین جزءِ بسته بود — هیچ‌جا خوانده نمی‌شوند: تابلو، نبض بازار و اسکرینر
# از بسته‌هایِ پختۀ baked می‌آیند و دادهٔ زنده را خودِ گوشی از TSETMC می‌گیرد.
# با ۴۳۳٬۹۲۲ ردیفِ تاریخچه، این فهرست حجمِ دانلود و حافظهٔ WebView را تعیین
# می‌کند، پس افزودنِ جدولِ «شاید لازمش داشته باشیم» اینجا ممنوع است.
RAW_TABLES = (
    "instruments",
    "price_history",
)

# نسخۀ قراردادِ manifest (`.meta.json`). کلاینت هر نسخۀ ناشناخته‌ای را **رد** می‌کند
# (نه پذیرشِ بی‌آزمون): `snapshotPackage.ts` همین عدد را می‌خواند.
# 1 = فقط app_version/built_at/baked_ok/gz_bytes
# 2 = + gz_sha256، package_id، min_app_version، db_bytes، tables، required_baked_keys
MANIFEST_SCHEMA_VERSION = 2

# نسخۀ **چیدمانِ دیتابیسِ بسته** (جدول‌های baked/meta/instruments/price_history).
# از قراردادِ manifest جدا است — گوشی ممکن است manifestِ v2 را با چیدمانِ ۱ بخواند.
# کلاینت این دو را با هم مقایسه می‌کند (`validateDatabase`) تا «سازنده چه نوشت» و
# «بسته چه هست» یکِ عدد بمانند؛ بی‌این سنجش، همان چک قبلی تنهایِ بی‌معنا بود.
DB_SCHEMA_VERSION = 1

# با `--require-signature` روشن می‌شود (مسیرِ انتشار). پیش‌فرض خاموش است تا بیلدِ
# کاندید/محلی بی‌کلید نشکند؛ artifactِ بی‌امضا درِ CI هرگز منتشر نمی‌شود.
REQUIRE_SIGNATURE = False

# price_history ستون‌به‌ستون برداشته می‌شود: value و src درِ هیچ کوئریِ
# موبایلی نیستند و رویِ همان ۴۳۳٬۹۲۲ ردیف مگابایتِ خامِ بی‌مصرف‌اند.
PH_COLUMNS = ("symbol", "date", "open", "high", "low", "close", "volume", "last")

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


def sign_manifest(meta_json: str, require: bool = False) -> dict:
    """امضایِ detached رویِ بایت‌هایِ manifest، با کلیدِ **خارجِ مخزن**.

    منبعِ کلید: `BORS_MOBILE_MANIFEST_KEY` (مسیرِ فایلِ PEM) یا
    `BORS_MOBILE_MANIFEST_KEY_PEM` (متنِ PEM — همان کاری که CI از secret می‌کند).
    نبودِ کلید ⇒ بیلدِ کاندید بی‌امضا ادامه می‌دهد و `signature:false` گزارش می‌شود؛
    با `--require-signature` (مسیرِ انتشار) همان‌جا می‌شکند. هیچ کلیدِ آزمایشیِ
    ساختگی جایِ کلیدِ انتشار را نمی‌گیرد و هیچِ کلیدِ خصوصی‌ای نوشته نمی‌شود.
    """
    import tempfile
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    try:
        import sign_mobile_manifest as sm
    except Exception as e:                                    # noqa: BLE001
        if require:
            raise SystemExit("BLOCKED: ابزارِ امضا بارگذاری نشد: %s" % e)
        return {"signature": False, "reason": "signer-unavailable: %s" % e}
    priv = os.environ.get("BORS_MOBILE_MANIFEST_KEY", "").strip()
    pem = os.environ.get("BORS_MOBILE_MANIFEST_KEY_PEM", "").strip()
    tmp = ""
    if not priv and pem:
        fd, tmp = tempfile.mkstemp(prefix="bors-mobile-sign-", text=True)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(pem)
        priv = tmp
        os.chmod(tmp, 0o600)
    if not priv:
        if require:
            raise SystemExit("BLOCKED: artifactِ امضاشدهٔ انتشار درِ نبودِ "
                             "BORS_MOBILE_MANIFEST_KEY(_PEM) ساخته نمی‌شود")
        return {"signature": False, "reason": "no-signing-key (کاندید بدونِ امضا منتشر نمی‌شود)"}
    try:
        res = sm.sign(meta_json, priv)
        # خودسنجی با همان فایلِ کلید (`_pub_der` هم private و هم public را می‌خواند)
        res["verified"] = sm.verify(meta_json, res["sig_path"], priv)
        if res["verified"] is not True:
            raise SystemExit("امضایِ ساخته‌شده با bors_minisign نخواند — انتشار ممنوع")
        res["signature"] = True
        return res
    finally:
        if tmp:
            os.unlink(tmp)


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
        have = [r[1] for r in dst.execute(f'PRAGMA src.table_info("{t}")')]
        if t == "price_history":
            take = [c for c in PH_COLUMNS if c in have]
            gone = [c for c in PH_COLUMNS if c not in have]
            if gone:
                print(f"  [note] price_history این ستون‌ها را ندارد: {gone}")
        else:
            take = have
        sel = ", ".join(f'"{c}"' for c in take)
        dst.execute(f'CREATE TABLE "{t}" AS SELECT {sel} FROM src."{t}"')
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
        ("schema", str(DB_SCHEMA_VERSION)),
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
    # همین فایلِ کوچک را روزانه از GitHub Releases چک می‌کند و بستۀ تازه را فقط
    # پس از **کامل شدنِ اعتبارسنجی** فعال می‌کند (localData.ts).
    #
    # پروتکل digest (عمداً بیرون از خودِ artifact): manifest فایلِ **جدا** است، پس
    # sha256 روی بایت‌های نهاییِ همان .gz که گوشی دانلود می‌کند گرفته می‌شود و هیچ
    # دورِ باطلی (هشِ فایلی که خودش را هش می‌کند) ندارد. ترتیب تحویل:
    #   ۱) gz دانلود می‌شود  ۲) طول و sha256 با manifest مقایسه می‌شود
    #   ۳) gunzip + بازگشایی SQLite + اعتبارسنجی ساختار  ۴) فعال‌سازی (آخرین گام)
    #
    # sha256 = تشخیص خرابی تصادفی / انتقال ناقص. این **امضا نیست**: بی کلیدِ عمومیِ
    # مستقل هیچ ادعایی درباره اصالت ناشر نمی‌کند (مستند در snapshotPackage.ts).
    h = hashlib.sha256()
    with open(gz, "rb") as fi:
        while True:
            blk = fi.read(1 << 20)
            if not blk:
                break
            h.update(blk)
    gz_hex = h.hexdigest()
    meta_json = out_db + ".meta.json"
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "package_id": "%s-%s" % (now.replace("-", "").replace(":", "").replace(" ", "T"), gz_hex[:8]),
        "app_version": APP_VERSION,
        # گوشیِ کهنه‌تر از این نسخه نباید بستۀ تازه را بپذیرد: پاسخِ پختۀ دسکتاپ با
        # نسخهٔ خودِ دسکتاپ قفل می‌شود.
        "min_app_version": APP_VERSION,
        "built_at": now,
        "gz_bytes": os.path.getsize(gz),
        "gz_sha256": gz_hex,
        "db_bytes": os.path.getsize(out_db),
        "baked_ok": ok,
        "baked_fail": fail,
        # قرارداد ساختار از خودِ همین سازنده: این چهار جدول ساخته می‌شود و گوشی هم
        # همین‌ها را می‌خواند (resolvers.ts ⇒ baked/meta/instruments/price_history).
        "tables": ["baked", "meta", "instruments", "price_history"],
        "required_baked_keys": ["market_board"],
        # چیدمانِ دیتابیسِ بسته — کلاینت با meta.schema داخلِ بسته می‌سنجد
        "db_schema": DB_SCHEMA_VERSION,
    }
    # امضا رویِ **بایت‌هایِ فایل** است، پس جداکننده‌هایِ خط باید بینِ Windows و
    # Linuxِ CI یکسان بمانند (با CRLF، هم digestِ manifest هم اعتبارِ امضا بهِ
    # ماشینِ سازنده بند می‌شد) ⇒ newline="LF" صریح.
    with open(meta_json, "w", encoding="utf-8", newline="\n") as fo:
        json.dump(manifest, fo, ensure_ascii=False, indent=1)
    print(f"[bake] {meta_json} · sha256={gz_hex[:16]}… · gz={manifest['gz_bytes']} B")
    signed = sign_manifest(meta_json, require=REQUIRE_SIGNATURE)
    if signed.get("signature"):
        print("[sign] manifest امضا شد · key_id=%s · alg=%s · verified=%s"
              % (signed["key_id"], signed["algorithm"], signed["verified"]))
    else:
        print("[sign] بی‌امضا: %s" % signed.get("reason"))

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
    ap.add_argument("--require-signature", action="store_true",
                    help="مسیرِ انتشار: بی‌کلیدِ امضا، بیلد **می‌شکند** (نه artifactِ بی‌امضا)")
    args = ap.parse_args()
    global REQUIRE_SIGNATURE
    REQUIRE_SIGNATURE = bool(args.require_signature)
    build(args.out, limit=args.limit, do_lzma=not args.no_lzma)


if __name__ == "__main__":
    main()
