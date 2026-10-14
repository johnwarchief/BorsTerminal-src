"""Shared plumbing: DB access, JSON/num helpers, process probes.

Split verbatim out of app.py (v9.8.1 modularisation).
Every statement is byte-for-byte identical to app.py; only the route
decorators changed from @app.<verb> to @router.<verb>.
Audit map of source line spans: MIGRATED_LINES.txt
"""
from bors_config import DB_PATH, USER_DB_PATH
from fastapi import HTTPException
import json
import math
import os
import sqlite3
import subprocess
import threading
import time

import sys


def codal_crawler_available():
    """آیا می‌شود خزندۀ کدال را به‌صورت زیرپروسه اجرا کرد؟ (برایِ endpointهایِ sync)

    هر سه مسیرِ «کدال را بخوان» با `[sys.executable, "codal_fetcher.py", …]`
    Popen می‌کردند. درِ بیلدِ فریزشده `sys.executable` **خودِ EXE** است، پس آن
    فرمان نه خزنده را اجرا می‌کند و نه چیزی می‌سازد — دومینِ نسخهٔ برنامه بالا
    می‌آید (و یکِ مسیرِ فرعیِ بدونِ dispatch، با connectِ خالی، market.db را
    ناقص گذاشته است — bors_config:452). کاربر درِ نسخهٔ نصبی برایِ دادهٔ تازه
    دکمۀ «بروزرسانی دیتابیس کدال» را می‌زند که snapshotِ گیت‌هاب را merge می‌کند.
    """
    return not bool(getattr(sys, "frozen", False))

def _sel_ddl() -> str:
    """DDL مشترک جدول تصمیمات سبد — یک متن برای هر دو بانک (market.db و user.db).

    دو نسخهٔ دستی از یک DDL یعنی «ستون در یک بانک هست و در دیگری نه»؛ همین‌جا
    منبع یکتاست. #106 (PORT-1): «تعداد» اضافه شد تا وزن از قیمت×تعداد بیاید.
    """
    return """
        CREATE TABLE IF NOT EXISTS selection_decisions (
            symbol       TEXT PRIMARY KEY,
            name         TEXT DEFAULT '',
            status       TEXT NOT NULL DEFAULT 'pending',
            reason       TEXT DEFAULT '',
            note         TEXT DEFAULT '',
            stop_loss    TEXT DEFAULT '',
            asset_kind   TEXT DEFAULT '',
            weight_pct   REAL DEFAULT 0,
            price        REAL DEFAULT 0,
            qty          REAL DEFAULT 0,
            score        INTEGER DEFAULT 0,
            pricing_mode TEXT DEFAULT '',
            sector       TEXT DEFAULT '',
            updated_at   TEXT DEFAULT ''
        )
    """


def ensure_selection_schema(conn: sqlite3.Connection) -> None:
    """جدول تصمیمات سبد + ADD COLUMN افزایندهٔ «تعداد».

    CREATE TABLE IF NOT EXISTS جدولِ موجود را به‌روز نمی‌کند، پس برای بانک‌هایی
    که از نسخهٔ قبل مانده‌اند ALTER لازم است. ALTER فقط «افزودن» است: هیچ ستون
    یا ردیفی حذف یا بازنویسی نمی‌شود (user.db خط‌قرمزِ حذفِ داده است).
    """
    try:
        conn.execute(_sel_ddl())
    except Exception:
        pass
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(selection_decisions)")}
        if cols and "qty" not in cols:
            conn.execute("ALTER TABLE selection_decisions ADD COLUMN qty REAL DEFAULT 0")
    except Exception:
        pass


def ensure_market_schema(conn: sqlite3.Connection) -> None:
    """ستونِ «تعدادِ معاملاتِ روزانه» را رویِ بانک‌هایِ قدیمی می‌سازد.

    فیلترِ کف‌روبیِ جزوه چهارمین قیدش را رویِ `qd1` (تعدادِ معاملاتِ نشستِ پیش)
    می‌بندد. `daily_prices` تا امروز فقط حجم و ارزش را نگه می‌داشت، پس آن عدد
    هیچ‌جا وجود نداشت و کد «تعدادِ امروز» را جانشینش می‌کرد — یعنی ردیف‌هایی
    را قبول می‌کرد که فرمولِ مالک رد می‌کند. ستون افزوده می‌شود (هیچ ردیفی
    حذف/بازنویسی نمی‌شود) و از نخستین سینکِ موفق پر می‌گردد؛ تا وقتی پر نشده،
    فیلتر آن قید را نمی‌سنجد و عددِ جعلی نمی‌سازد.
    """
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(daily_prices)")}
        if cols and "z_tot_tran" not in cols:
            conn.execute("ALTER TABLE daily_prices ADD COLUMN z_tot_tran REAL")
    except Exception:
        pass


def get_db():
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=500, detail="Database market.db not found.")
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    # WAL: خواندنیها همزمان با نوشتن (sync های پسزمینه) قفل DB را نمیگیرند
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    # v7.3: cache 64MB برای کوئریهای سنگین اسکرینر/چارت (دستور بهینهسازی دیتابیس)
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA mmap_size=268435456")
    # v9.7.3: norm_fa به‌عنوان تابع SQL ثبت می‌شود تا هر فیلترِ سمتِ SQL روی
    # نوشتارِ عربی/فارسی safe باشد. توجه: در کوئری‌های تک‌نمادیِ پرتکرار استفاده
    # نمی‌شود (اندازه‌گیری: 5.74ms در برابر 0.01ms با ایندکس) — fts_engine برای
    # آن مسیر symbol_aliases/sym_in را می‌فرستد. اینجا برای فیلترهای کل‌بازاری
    # ثبت می‌شود که از قبل جدول را کامل می‌خوانند.
    try:
        import fts_engine as _fts
        _fts.register_sql(conn)
    except Exception:
        pass
    # ایندکسهای پرفورمنس (یک‌بار، idempotent)
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS ix_ct_ins_deven ON client_type(ins_code, d_even)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_ph_sym_date2 ON price_history(symbol, date DESC)")
    except Exception:
        pass
    ensure_market_schema(conn)
    # v9.0 — جدول سبک تصمیمات سبد (Accept/Reject/Monitor). idempotent و هم‌جای
    # ایندکسها؛ با «هر اتصال» تضمین میشود موجود است بدون نیاز به مایگریشن جدا.
    ensure_selection_schema(conn)
    # v9.7.3 — واچ‌لیست کاربر. همان الگوی بالا: idempotent و همراه هر اتصال،
    # بدون مایگریشن جدا. DDL داخل watchlist_store است تا تست‌ها بدون FastAPI
    # بتوانند همان جدول را بسازند.
    try:
        import watchlist_store
        watchlist_store.ensure_table(conn)
    except Exception:
        pass
    # v9.7.5 فاز ۱ — ستون‌های عمق/paper_type و جدول نقطه‌های تایم‌لاین. همان
    # الگوی «همراه هر اتصال»: درخواستِ mstat روی بانکِ نسخهٔ قبلی هم کار می‌کند
    # (فقط آن پنل‌ها «بی‌داده» می‌شوند، نه ۵۰۰).
    try:
        import mstat_engine
        mstat_engine.ensure_schema(conn)
    except Exception:
        pass
    return conn


def get_user_db() -> sqlite3.Connection:
    """اتصال به دیتابیس اختصاصی کاربر (user.db).

    این فایل کنار EXE (یا ریشه ریپو در dev) قرار دارد و با هیچ آپدیتی
    جایگزین نمی‌شود. جداول user_watchlists و selection_decisions فقط اینجا
    ساخته و نگهداری می‌شوند.

    migration خودکار: اگر این جداول داخل market.db داده دارند (نسخه‌های
    قبلی) ردیف‌ها به user.db کپی و از market.db حذف می‌شوند تا کاربر هیچ
    داده‌ای گم نکند.
    """
    conn = sqlite3.connect(USER_DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    # ساخت جداول کاربر (idempotent)
    try:
        import watchlist_store
        watchlist_store.ensure_table(conn)
    except Exception:
        pass

    ensure_selection_schema(conn)

    # migration یک‌باره از market.db به user.db
    # (برای کاربرانی که نسخهٔ قبلی نصب داشتند)
    _migrate_user_tables_from_market(conn)

    conn.commit()
    return conn


def _migrate_user_tables_from_market(user_conn: sqlite3.Connection) -> None:
    """اگر جداول کاربر در market.db داده دارند → کپی به user.db → حذف از market.db.

    این تابع idempotent است: بار دوم جداول market.db خالی‌اند و هیچ کاری
    نمی‌کند. خطاها بی‌صدا نادیده گرفته می‌شوند تا باز شدن برنامه را
    مسدود نکنند.
    """
    if not os.path.exists(DB_PATH):
        return
    try:
        mconn = sqlite3.connect(DB_PATH, timeout=10)
        mconn.row_factory = sqlite3.Row
        mconn.execute("PRAGMA journal_mode=WAL")

        # migration واچ‌لیست
        try:
            src_rows = mconn.execute(
                "SELECT * FROM user_watchlists"
            ).fetchall()
            if src_rows:
                user_conn.executemany(
                    "INSERT OR IGNORE INTO user_watchlists"
                    " (symbol_norm, symbol, name, note, added_at)"
                    " VALUES (:symbol_norm, :symbol, :name, :note, :added_at)",
                    [dict(r) for r in src_rows]
                )
                mconn.execute("DELETE FROM user_watchlists")
                mconn.commit()
        except Exception:
            pass

        # migration تصمیمات سبد
        try:
            src_rows = mconn.execute(
                "SELECT * FROM selection_decisions"
            ).fetchall()
            if src_rows:
                user_conn.executemany(
                    "INSERT OR IGNORE INTO selection_decisions"
                    " (symbol, name, status, reason, note, stop_loss, asset_kind,"
                    "  weight_pct, price, qty, score, pricing_mode, sector, updated_at)"
                    " VALUES (:symbol, :name, :status, :reason, :note, :stop_loss,"
                    "  :asset_kind, :weight_pct, :price, :qty, :score, :pricing_mode,"
                    "  :sector, :updated_at)",
                    # بانکِ منبع ممکن است نسخهٔ بی‌«تعداد» باشد؛ کلیدِ غایب صفر
                    # می‌خورد وگرنه INSERT پارامترِ ناموجود می‌شکند و کل
                    # مایگریشن (بی‌صدا) رد می‌شود.
                    [{**dict(r), "qty": dict(r).get("qty") or 0} for r in src_rows]
                )
                mconn.execute("DELETE FROM selection_decisions")
                mconn.commit()
        except Exception:
            pass

        mconn.close()
    except Exception:
        pass

def _safe_read_json(path):
    try:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None

def _num(v):
    """تبدیل مطمئن به float: None/NaN/Inf → 0 (چون pandas NULL ها را NaN میکند نه None)."""
    try:
        f = float(v)
        return f if math.isfinite(f) else 0
    except (TypeError, ValueError):
        return 0

# ── کشِ شمارشِ فرایند (بندِ ۶ مأموریتِ کاراییِ بازارِ زنده، ۱۴۰۵-۰۷-۲۷) ──────
# اندازه‌گیریِ این نشست رویِ بک‌اندِ زنده (۲۰ نمونه، ۱۰:۴۲:۵۹→۱۰:۴۷:۱۵):
#   GET /api/market/sync-state  p50 = 573.1 ms  (بدنۀ پاسخ ۱۴۱ بایت!)
# و تنها کارِ آن endpoint یکِ `_count_procs("test_tsetmc")` است. رویِ ویندوز هر
# شمارش یعنی بالا آوردنِ یکِ `powershell.exe` و `Get-CimInstance Win32_Process`
# رویِ **همهٔ** فرایندهای سیستم. `/api/sync/status` هم درِ یکِ درخواست دو تا سه
# بار این را صدا می‌زند ⇒ UI با هر پولینگِ ۳۰ ثانیه‌ای چند صد میلی‌ثانیه CPU بابت
# چیزی می‌پردازد که دقیقه‌ها عوض نمی‌شود.
# کشِ ttl-ثانیه‌ای رفتار را عوض نمی‌کند: «آیا سینکر در کار است؟» boolean است و
# مصرف‌کننده‌ها (نشانۀ زنده، heuristicِ status_frozen با آستانۀ ۶۰ ثانیه) با ۳
# ثانیه کهنگی هیچ حکمی را برعکس نمی‌کنند. بی‌کش هم هنوز با `ttl_s=0` ممکن است.
_PROC_CACHE: dict = {}
_PROC_LOCK = threading.Lock()
_PROC_TTL_S = 10.0
_PROC_WAIT: dict = {}


def _count_procs_raw(pattern):
    """تعداد پروسههای python در حال اجرا که CommandLine شامل pattern است.
    کراس-پلتفرم: ویندوز → PowerShell/CimInstance؛ لینوکس/macOS → pgrep.
    این بدنه دست‌نخورده است؛ کش لایۀ رویش است."""
    try:
        if os.name == "nt":
            out = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command",
                 f"(Get-CimInstance Win32_Process | Where-Object {{ $_.Name -eq 'python.exe' -and $_.CommandLine -match '{pattern}' }}).Count"],
                capture_output=True, text=True, timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return out.returncode == 0 and out.stdout.strip().isdigit() and int(out.stdout.strip()) > 0
        out = subprocess.run(["pgrep", "-f", pattern],
                             capture_output=True, text=True, timeout=15)
        return bool(out.stdout.strip())
    except Exception:
        return False


def _count_procs(pattern, ttl_s=None, now=None, refresh="bg"):
    """`_count_procs_raw` با کشِ ttl-ثانیه‌ای، stale-while-revalidate و تک‌پروازگی.

    چرا این لایه: خودِ شمارش رویِ ویندوز ~۵۹۰ms است (PowerShell + CIM؛ با queryِ
    فیلترشده هم بهتر نمی‌شود — سنجیده شد: ۵۸۹ در برابر ۵۷۹ms). اگر پاسخِ هر
    پولینگِ UI این را بپردازد، `sync-state` با بدنۀ ۱۴۱ بایت ۵۷۳ms کشیده می‌شود.
    «آیا سینکر در کار است؟» boolean است و تازگیِ **داده** از `last`ِ همان
    `market_sync.json` می‌آید، نه از این شمارش ⇒ کهنه‌دادنِ حداکثر به اندازهٔ ttl
    هیچ عددی از تابلو را کهنه نمی‌کند.

    `refresh`: `bg` ⇒ پاسخِ کهنه فوراً + بازسازیِ پس‌زمینه (پیش‌فرضِ تولید)؛
    `inline` ⇒ همان مسیرِ قدیمی، درخواست‌کننده می‌سازد؛ `none` ⇒ فقط پاسخِ کهنه،
    بی‌هیچ کاری (برایِ آزمونِ قطعی). `ttl_s=0` ⇒ بی‌کش، لحظه‌ای (تصمیمِ کشتن).
    """
    ttl = _PROC_TTL_S if ttl_s is None else float(ttl_s)
    if ttl <= 0:
        return _count_procs_raw(pattern)
    t = time.monotonic() if now is None else float(now)
    with _PROC_LOCK:
        hit = _PROC_CACHE.get(pattern)
        fresh = hit is not None and (t - hit[0]) < ttl
        if fresh:
            return hit[1]
        stale = hit[1] if hit is not None else None
        waiter = _PROC_WAIT.get(pattern)
        if waiter is not None:
            owner, ev = False, waiter
        else:
            if stale is not None and refresh != "inline":
                if refresh == "bg":
                    _PROC_WAIT[pattern] = ev = threading.Event()
                    owner = True
                else:                       # refresh="none"
                    return stale
            else:
                _PROC_WAIT[pattern] = ev = threading.Event()
                owner = True
    if not owner:
        # شمارشِ اول دارندگانِ دیگرِ همین الگو را بلوکه نمی‌کند که بج‌بخورد؛
        # فقط منتظرِ همان یکِ نتیجه می‌مانند (سقفِ منطقی، بی‌بن‌بست).
        ev.wait(timeout=max(5.0, ttl + 5.0))
        with _PROC_LOCK:
            hit = _PROC_CACHE.get(pattern)
        if hit is not None:
            return hit[1]
        return stale if stale is not None else False
    try:
        if stale is None:
            val = _count_procs_raw(pattern)
            with _PROC_LOCK:
                # همان `t` ذخیره می‌شود، نه ساعتِ دوباره‌خوانده‌شده — وگرنه
                # آزمونِ ttl با ساعتِ تزریقی معنایش را از دست می‌داد.
                _PROC_CACHE[pattern] = (t, val)
            return val
        threading.Thread(target=_proc_refresh, args=(pattern,), daemon=True).start()
        return stale
    finally:
        if stale is None:
            with _PROC_LOCK:
                _PROC_WAIT.pop(pattern, None)
            ev.set()


def _proc_refresh(pattern):
    """بازسازیِ پس‌زمینه؛ خطا نباید تردِ درخواست‌کننده را بمیراند."""
    try:
        val = _count_procs_raw(pattern)
        with _PROC_LOCK:
            _PROC_CACHE[pattern] = (time.monotonic(), val)
    except Exception:
        pass
    finally:
        with _PROC_LOCK:
            ev = _PROC_WAIT.pop(pattern, None)
    if ev is not None:
        ev.set()


def _proc_cache_clear():
    """فقط برایِ آزمون — کشِ شمارشِ فرایند را خالی می‌کند."""
    with _PROC_LOCK:
        _PROC_CACHE.clear()
        _PROC_WAIT.clear()

def _kill_procs(pattern):
    """کشتن همه پروسههای python دارای pattern در CommandLine — کراس-پلتفرم."""
    try:
        if os.name == "nt":
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command",
                 f"Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                 f"Where-Object {{ $_.CommandLine -match '{pattern}' }} | "
                 f"ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}"],
                capture_output=True, timeout=20,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            subprocess.run(["pkill", "-f", pattern],
                           capture_output=True, timeout=20)
    except Exception:
        pass


# ==================================== تطبیقِ هویتِ نماد (Stage 1.2)
# ستون symbol در بانک‌های کدال/تابلو برای شماری از نمادها با «ك/ي» عربی یا
# نیم‌فاصله ذخیره شده، ولی ورودیِ کاربر/واچلیست/اسکرینر نوشتارِ فارسی می‌دهد.
# تطبیقِ `symbol = ?` برای آن‌ها بی‌صدا صفر ردیف برمی‌گرداند (تاریخچۀ خالی،
# بج خالی، چارت بی‌سری). راه‌حلِ پیشین «ساختنِ جایگشتِ نوشتارها در پایتون» بود؛
# Stage 1.2 آن را با نامزدهایِ واقعیِ همان بانک عوض کرد (`symbol_identity`),
# چون جایگشت هیچ‌وقت نیم‌فاصله را نمی‌ساخت و کارت را از ۶ از ۷ ردیفِ یک
# صادرکننده بی‌خبر می‌گذاشت، در حالی که قیف هر ۷ را می‌دید.
# شکلِ خروجی عوض نشده (`col IN (?,?)`) تا ایندکس بماند: اندازه‌گیریِ همین بانک
# `norm(col)=?` را ~۵٫۷ms در برابرِ ~۰٫۰۱ms برای `symbol=?` نشان داد.
def sym_pred(conn, col: str, symbol, domain=None):
    """(شرح SQL, پارامترها) برای «همۀ نوشتارهایِ این نماد در همین بانک».

    مثال: pred, params = sym_pred(conn, "symbol", "داریک")
    ورودیِ تهی ⇒ شرطی که هرگز درست نمی‌شود (رفتارِ «بدون داده» حفظ می‌شود).
    `conn` اجباری است: بدونِ بانک نمی‌شود دانست کدامِ نوشتار واقعاً وجود دارد.
    """
    try:
        import fts_engine
        return fts_engine.sym_in(conn, col, symbol, domain)
    except Exception:
        return "%s = ?" % col, [symbol]
