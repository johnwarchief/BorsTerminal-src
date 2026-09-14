"""Shared plumbing: DB access, JSON/num helpers, process probes.

Split verbatim out of app.py (v9.8.1 modularisation).
Every statement is byte-for-byte identical to app.py; only the route
decorators changed from @app.<verb> to @router.<verb>.
Audit map of source line spans: MIGRATED_LINES.txt
"""
from bors_config import DB_PATH
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
