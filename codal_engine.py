#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""codal_engine.py — لایهٔ نازک روی codal_fetcher برای endpointهای app.py.

تاریخچه: v9.7.7 این ماژول استاب بود که «چرخش IP» را با فراخوانی خام adb
بازسازی میکرد (بدون قفل، بدون فاصلهٔ حداقلی، بدون تشخیص دستگاه، بدون
بازگردانی Wi-Fi در finally، بدون تأیید واقعی تغییر IP) و چهار حالت
همگام‌سازی را با پاسخ جعلی «ok» جواب میداد.

بازنویسی (پاک‌سازی): هیچ منطقی اینجا تکرار نمیشود؛ همه‌چیز به
codal_fetcher واگذار میشود — همان ماشینی که کارگرهای اسکن واقعاً
استفاده میکنند:
  * چرخش IP   → rotate_ip_via_adb با تمام گاردهایش (قفل غیرهم‌بلوکه،
    _ADB_MIN_GAP، Retry+Re-connect دستگاه، بازگردانی Wi-Fi در finally،
    تأیید واقعی تغییر IP)
  * همگام‌سازی → پروسهٔ جداگانهٔ codal_fetcher.py با فلگ‌های CLI واقعی
    (--update-symbols / --backfill / --feed update --optimized)، همان
    الگوی launcher های pipeline خود app.py — هرگز ترد درون‌پروسه‌ای که
    حلقهٔ uvicorn را قفل کند و هرگز پاسخ «ok» جعلی.
"""

import os
import subprocess
import sys

import requests

import codal_fetcher

# در حالت EXE، APP_DIR = _MEIPASS فقط‌خواندنی است؛ نوشتن log باید برود WORK_DIR.
try:
    from bors_config import WORK_DIR as _WDIR
except Exception:  # noqa: BLE001 — dev/standalone
    _WDIR = os.path.dirname(os.path.abspath(__file__))

# نگاشت حالت همگام‌سازی → آرگومان‌های واقعی CLI codal_fetcher.py.
# حالتی که نگاشت ندارد صادقانه error برمی‌گرداند، نه «ok» جعلی.
_SYNC_MODES = {
    # دلتا: بهروزرسانی افزایشی نمادهای موجود (FromDate delta + dedupe)
    "delta": ["--update-symbols", "40"],
    # پر کردن FS/MS نمادهایی که عنوان صورتمالی کدال دارند ولی ردیف ندارند
    "backfill": ["--backfill"],
    # کامل: همگام‌سازی هوشمند فید سراسری (بدون جستجوی تک‌نماد)
    "full": ["--feed", "update", "--optimized"],
}

# اجرای واچ‌لیست: یک پروسه، نمادها از خود user_watchlists خوانده میشوند
# (درون پروسه، نه از argv — تا نام فارسی سالم بماند) و برای هرکدام
# fetch_symbol واقعی codal_fetcher اجرا میشود.
_WATCHLIST_RUNNER = (
    "import sqlite3, codal_fetcher, watchlist_store; "
    "conn = sqlite3.connect(codal_fetcher.DB_PATH, timeout=30); "
    "watchlist_store.ensure_table(conn); "
    "syms = [r['symbol'] for r in watchlist_store.list_rows(conn) if r.get('symbol')]; "
    "conn.close(); "
    "print('watchlist sync:', len(syms), 'symbols', flush=True); "
    "[codal_fetcher.fetch_symbol(s) for s in syms]"
)


def _adb_rotate():
    """چرخش IP سلولی — کامل به codal_fetcher.rotate_ip_via_adb واگذار میشود.

    خروجی: IP تازه در موفقیت، None در شکست (adb نیست / دستگاه نیست /
    توگل رد شد / IP واقعاً عوض نشد). قراردادِ همان _adb_rotate قدیمی،
    این بار با تمام گاردهای codal_fetcher.
    """
    ok = codal_fetcher.rotate_ip_via_adb()
    if not ok:
        return None
    return getattr(codal_fetcher, "_ADB_LAST_IP", None)


def _get_public_ip():
    """IP عمومی فعلی (ipify)."""
    try:
        return requests.get("https://api.ipify.org", timeout=8).text.strip() or None
    except Exception:
        return None


def adb_status():
    """وضعیت واقعی ADB برای /api/adb/status — هیچ flag جعلی وجود ندارد."""
    adb = codal_fetcher._find_adb()
    device_ready = False
    if adb:
        try:
            ready, _unauth, _off = codal_fetcher._adb_devices(adb)
            device_ready = bool(ready)
        except Exception:
            device_ready = False
    return {
        "adb_available": bool(adb),
        "adb_path": adb or "",
        "enabled": bool(codal_fetcher._adb_enabled()),
        "device_ready": device_ready,
        "public_ip": _get_public_ip(),
        "last_rotated_ip": getattr(codal_fetcher, "_ADB_LAST_IP", None),
        "min_gap_sec": codal_fetcher._ADB_MIN_GAP,
    }


def run_sync_job(kind, **kwargs):
    """یک job همگام‌سازی واقعی (پروسهٔ پس‌زمینه) میسازد.

    برخلاف استاب v9.7.7 هیچ شمارندهٔ جعلی تولید نمیشود؛ پاسخ
    {status: started, pid, args} است و نتیجهٔ واقعی در خروجی پروسه و
    market.db ظاهر میشود. kwargsهای بدون نگاشت (symbols/days/user_id)
    پذیرفته میشوند تا امضای endpointهای app.py نشکند، ولی صادقانه در
    پاسخ گزارش میشوند.
    """
    frozen = bool(getattr(sys, "frozen", False))
    if kind == "watchlist":
        if frozen:
            cmd = [sys.executable, "--codal-worker", "watchlist"]
            args = ["--codal-worker watchlist"]
        else:
            cmd = [sys.executable, "-c", _WATCHLIST_RUNNER]
            args = ["-c <watchlist runner>"]
        note = "fetch_symbol() برای تک‌تک نمادهای user_watchlists"
    else:
        argv = _SYNC_MODES.get(kind)
        if not argv:
            return {"status": "error", "message": "Unknown sync mode: %s" % kind}
        if frozen:
            cmd = [sys.executable, "--codal-worker", kind]
        else:
            cmd = [sys.executable, "codal_fetcher.py"] + argv
        args = argv
        note = ""
    try:
        proc = subprocess.Popen(cmd, cwd=_WDIR,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        return {"status": "error", "message": str(e)[:160]}
    res = {"status": "started", "mode": kind, "pid": proc.pid, "args": args}
    if note:
        res["note"] = note
    if kwargs:
        res["ignored_kwargs"] = sorted(kwargs)
    return res
