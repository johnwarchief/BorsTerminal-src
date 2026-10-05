# -*- coding: utf-8 -*-
"""dev/single_writer_guard.py — گاردِ «یک نویسنده برایِ market.db»

چه چیزی را می‌گیرد: دورِ مصرف‌کنندهٔ TSETMC رویِ همین ماشین دو بک‌اند هم‌نام
`app:app` داشت (نوبتِ خودم + یک `nohup py -3.14 -m uvicorn app:app --port 8002`
ماندۀ ۱۴۰۵-۰۷-۱۲ که نسخۀ ۱٫۰٫۷۳ِ حافظه را می‌دوید). هر دو `WORK_DIR` یکی
داشتند، پس هر دو همان `market.db` و همان کشِ بدنهٔ تابلو را می‌نوشتند:
ستون‌هایِ تازه‌ای که دورِ P1 اضافه شده بودند با هر سینکِ نسخۀ قدیمی NULL
می‌شدند و یک سنجشِ زنده «موردی ثبت نشده» می‌داد در حالی که پنلِ کناری
«متوقف» می‌گفت. این گارد همان حالت را برمی‌گرداند.

قاعده: اگر بیش از یک پروسهٔ زندهٔ این ریپو (uvicorn/bors_entry/pythonw با
`app:app`) رویِ ماشین باشد ⇒ FAIL. پروسه‌ای که ما خودمان بالا آورده‌ایم هم
شمرده می‌شود؛ برایِ همین پیش از `run_all_tests.py` باید سرورها بسته باشند
(همان چیزی که AGENTS می‌گوید).

اگر ابزارِ شمارشِ پروسه در دسترس نبود (CI لینوکسی/بدونِ PowerShell) گارد
بی‌صدا رد می‌شود و صفر برمی‌گرداند — گاردِ محیطی نباید بلیطِ سبزِ کلِ سوئیت
را ببندد.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

PS_QUERY = r"""
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match '^(python|pythonw|py)\.exe$' -and
                 $_.CommandLine -match 'app:app|bors_entry|test_tsetmc' } |
  ForEach-Object { "$($_.ProcessId)|$($_.ParentProcessId)|$($_.CommandLine)" }
"""


def dedupe_tree(rows):
    """یک اجرا = یک نویسنده، نه دو.

    درِ ویندوز `python.exe` مسیری که WindowsApps اجرا می‌کند یک shim است: همان
    فرمان را به مفسرِ واقعی پاس می‌دهد و دو پروسه با دو خطِ فرمانِ *یکسان*
    می‌سازد (سنجیده: pid 25532 فرزندِ pid 40536، هر دو `-m uvicorn app:app`).
    بی‌این حذفِ فرزند، گارد یک بک‌اند را دو می‌شمارد و «تک‌نویسنده» را می‌شکند
    در حالی که هیچ نویسدۀ دومی وجود ندارد. دو اجرایِ مستقل (همان ماندۀ
    1405-07-12) فرزندِ یکدیگر نیستند، پس همان‌جا همچنان 2 شمرده می‌شوند.
    """
    pids = {int(r[0]) for r in rows}
    return [r for r in rows if int(r[1]) not in pids]


def windows_writers():
    """پروسه‌هایِ پایتونِ این ریپو که نویسدۀ market.db‌اند."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", PS_QUERY],
            capture_output=True, text=True, timeout=45).stdout
    except Exception as e:                                    # noqa: BLE002
        return None, f"powershell در دسترس نیست ({type(e).__name__})"
    rows = []
    for line in out.splitlines():
        line = line.strip()
        parts = line.split("|", 2)
        if len(parts) != 3 or not parts[0].isdigit():
            continue
        pid, ppid, cmd = int(parts[0]), int(parts[1]), parts[2][:200]
        if "app:app" in cmd or "bors_entry" in cmd or "test_tsetmc" in cmd:
            rows.append((pid, ppid, cmd))
    before = len(rows)
    rows = dedupe_tree(rows)
    return [f"{r[2]} (pid {r[0]})" for r in rows], (None if before == len(rows)
            else f"{before - len(rows)} فرزندِ هم‌خطِفرمان شمرده نشد (shimِ python.exe)")


def lock_probe(db_path):
    """آیا همین حالا قفلِ نوشتن دستِ کسِ دیگری است؟ (writer زنده، نه خواننده)"""
    if not os.path.exists(db_path):
        return None
    try:
        c = sqlite3.connect(db_path, timeout=1)
        try:
            c.execute("BEGIN IMMEDIATE")
            c.rollback()
        finally:
            c.close()
    except sqlite3.OperationalError as e:
        if "locked" in str(e) or "busy" in str(e):
            return str(e)
    return None


def main():
    try:
        import bors_config
        db = bors_config.DB_PATH
    except Exception:                                          # noqa: BLE002
        db = os.path.join(REPO, "market.db")
    rows, skip = windows_writers()
    if rows is None:
        print(f"single_writer_guard: SKIPPED — {skip}")
        return 0
    if skip:
        print(f"note: {skip}")
    # خودِ همین گارد هم پایتون است؛ خطوطِ بی‌«-m»/uvicorn/entry مربوط به ما نیست
    live = [r for r in rows if "uvicorn" in r or "bors_entry" in r or "-m app" in r]
    busy = lock_probe(db)
    print(json.dumps({"db": db, "writer_processes": len(live), "processes": live[:4],
                      "write_lock_busy": bool(busy)}, ensure_ascii=False, indent=1))
    if len(live) > 1:
        print(f"FAIL — {len(live)} بک‌اند رویِ یک market.db می‌نویسند؛ "
              "دو منبعِ حقیقت برایِ ستون‌هایِ canonical")
        return 1
    if busy:
        print(f"FAIL — قفلِ نوشتنِ {db} دستِ پروسۀ دیگری است: {busy}")
        return 1
    print("OK — تک‌نویسنده")
    return 0


def selftest():
    """کنترلِ منفیِ خودِ گارد: دو اجرایِ مستقل باید ۲ بماند، shim+فرزند ۱."""
    twin = [(100, 1, "python -m uvicorn app:app --port 8001"),
            (101, 100, "python -m uvicorn app:app --port 8001")]
    independent = [(200, 7, "python -m uvicorn app:app --port 8001"),
                   (201, 9, "python -m uvicorn app:app --port 8002")]
    assert len(dedupe_tree(twin)) == 1, "shim+فرزند باید یک اجرا شود"
    assert len(dedupe_tree(independent)) == 2, "دو اجرایِ مستقل باید دو بماند"
    print("single_writer_guard selftest OK (1 twin, 2 independent)")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
