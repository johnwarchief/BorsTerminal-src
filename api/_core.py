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
    # v9.0 — جدول سبک تصمیمات سبد (Accept/Reject/Monitor). idempotent و هم‌جای
    # ایندکسها؛ با «هر اتصال» تضمین میشود موجود است بدون نیاز به مایگریشن جدا.
    try:
        conn.execute("""
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
                score        INTEGER DEFAULT 0,
                pricing_mode TEXT DEFAULT '',
                sector       TEXT DEFAULT '',
                updated_at   TEXT DEFAULT ''
            )
        """)
    except Exception:
        pass
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

    try:
        conn.execute("""
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
                score        INTEGER DEFAULT 0,
                pricing_mode TEXT DEFAULT '',
                sector       TEXT DEFAULT '',
                updated_at   TEXT DEFAULT ''
            )
        """)
    except Exception:
        pass

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
                    "  weight_pct, price, score, pricing_mode, sector, updated_at)"
                    " VALUES (:symbol, :name, :status, :reason, :note, :stop_loss,"
                    "  :asset_kind, :weight_pct, :price, :score, :pricing_mode,"
                    "  :sector, :updated_at)",
                    [dict(r) for r in src_rows]
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

def _count_procs(pattern):
    """تعداد پروسههای python در حال اجرا که CommandLine شامل pattern است.
    کراس-پلتفرم: ویندوز → PowerShell/CimInstance؛ لینوکس/macOS → pgrep."""
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


# ==================================== تطبیق نمادِ چند-نویشتاری (رفع باگ ک/ي عربی)
# ستون symbol در price_history/instruments برای شماری از نمادها با «ك/ي» عربی
# ذخیره شده (۳۴۴ نماد با ك عربی و ۵۵۴ با ي عربی، از ۲۵۱۵ نماد price_history)
# ولی ورودیِ کاربر/واچلیست/اسکرینر نوشتار فارسی می‌دهد (fts_engine.norm_fa).
# تطبیقِ دقیقِ `symbol = ?` برای این نمادها بی‌صدا صفر ردیف برمی‌گرداند →
# تاریخچهٔ خالی، بج/تحلیل FTS خالی، چارت بی‌سری. sym_pred همهٔ نوشتارهای یک
# نماد را در پایتون می‌سازد و به شکل `col IN (?,?)` به SQL می‌فرستد تا از
# ایندکس (ix_ph_sym_date2) استفاده شود — نه `norm_fa(col) = ?` که اسکن کامل
# می‌خورد (۵۷۴× کندتر؛ همان اندازه‌گیریِ fts_engine). این همان الگوی
# موردتأییدِ پروژه است: confidence_engine._bars و fundamental.sym_in.
def sym_pred(col: str, symbol):
    """(شرطِ SQL, پارامترها) برای تطبیق «هر نوشتارِ» نماد روی ستونِ نماد.

    مثال: pred, params = sym_pred("symbol", "داریک")
           f"... WHERE {pred}"  →  "symbol IN (?,?)"  (فارسی + عربی).
    ورودیِ تهی → شرطی که هرگز درست نمی‌شود (رفتار «بدون داده» حفظ می‌شود).
    """
    try:
        import fts_engine
        return fts_engine.sym_in(col, symbol)
    except Exception:
        return "%s = ?" % col, [symbol]
