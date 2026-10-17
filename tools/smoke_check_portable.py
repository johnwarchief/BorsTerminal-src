#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""smoke_check_portable.py — راستی‌آزماییِ نسخۀ *بسته‌شده* از روی ZIPِ منتشرشده.

چرا این فایل اینجا است: گیت‌هایِ Python/Vitest بیلدِ منجمد را نمی‌بینند. تنها چیزی که
ثابت می‌کند `execution_connect` و `api/execution` درِ EXE زنده‌اند، بالا آوردنِ همان
EXE است. ZIPِ Portable باِ `bors_portable.flag` کنارِ EXE می‌آید ⇒ پرتابیل است، پس
هم رویِ ۸۱۰۱ و هم درِ پوشۀ دادهِ جداِ خودِش می‌نشیند و به نصبیِ ۸۰۰۱ یا
`market.db`ِ کاریِ کاربر دست نمی‌زند. فرآیندی که می‌کشیم فقط PIDِ خودِ ماست.

مصرف:  python tools/smoke_check_portable.py <path/to/BorsTerminal_Ultimate.exe>
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

PORT = 8101
BASE = "http://127.0.0.1:%d" % PORT
ENDPOINTS = [
    ("/api/update/version", "نسخۀ باینری"),
    ("/api/execution/status", "وضعیتِ اجرا (کنترل‌کنندۀ مرکزی)"),
    ("/api/execution/connect", "لایۀ اتصالِ EasyTrader"),
    ("/api/execution/limits", "سقف‌هایِ ریسک"),
]

FAIL = 0


def ck(cond, label, got=""):
    global FAIL
    print(("  ok   " if cond else "  FAIL ") + label + ("" if cond else "  -> " + str(got)[:150]))
    if not cond:
        FAIL += 1
    return bool(cond)


def get(path, timeout=8.0):
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return None, {"error": "%s: %s" % (type(e).__name__, str(e)[:120])}


def main(exe: str) -> int:
    print("── اسموکِ نسخۀ منجمد:", exe)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.Popen([exe], cwd=os.path.dirname(exe), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        # فقط همین PID؛ انتظارِ آرام تا درِ ۸۱۰۱ باز شود (بیلدِ منجمد چندِ ثانیه طول می‌کشد)
        up = None
        deadline = time.time() + 90.0
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            st, _ = get("/api/update/version", timeout=3.0)
            if st == 200:
                up = st
                break
            time.sleep(2.0)
        ck(up == 200, "بیلدِ منجمد بالا آمد و API پاسخ می‌دهد", "process exited" if proc.poll() is not None else "timeout")
        if up != 200:
            return 1

        st, ver = get("/api/update/version")
        print("   version payload:", json.dumps(ver, ensure_ascii=False)[:160])
        ck(st == 200 and str(ver.get("version", "")).count(".") == 2,
           "نشانهٔ نسخه درِ باینری خوانده می‌شود", ver)

        st, conn = get("/api/execution/connect")
        ck(st == 200, "اندپوینتِ اتصال درِ EXE زنده است (hiddenimports درست)",
           conn if st != 200 else "")
        ck(conn.get("states_supported") == ["CONNECTED", "DISCONNECTED", "EXPIRED", "UNKNOWN"],
           "چهار حالتِ صریحِ نشست ازِ باینری بیرون می‌آید", conn.get("states_supported"))
        ck("profile_dir" not in json.dumps(conn, ensure_ascii=False),
           "نشانیِ پوشۀ موقتِ مرورگر درِ پاسخ نیست")
        b = conn.get("browser") or {}
        ck("profile_dir" not in b, "وضعیتِ پنجره هم نشانیِ دیسک نمی‌دهد", b)

        st, ex = get("/api/execution/status")
        ck(st == 200 and ex.get("status") == "success", "وضعیتِ اجرا پاسخ می‌دهد", st)
        gate = ex.get("risk_gate") or {}
        print("   risk gate:", json.dumps(gate, ensure_ascii=False)[:160])
        ck(ex.get("dry_run") is True or ex.get("live_enabled") is not True,
           "بیلدِ تازه‌نصب‌شده نه dry_run روشن است و نه live — هیچ ارسالِ واقعی ازِ این راه ممکن نیست",
           {"dry_run": ex.get("dry_run"), "live_enabled": ex.get("live_enabled")})

        st, lim = get("/api/execution/limits")
        ck(st == 200, "سقف‌هایِ ریسک ازِ باینری خوانده می‌شوند",
           json.dumps(lim, ensure_ascii=False)[:120])
        print("   limits:", json.dumps(lim, ensure_ascii=False)[:220])
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=20)
            except Exception:
                proc.kill()
        print("── processes killed: only our own PID", proc.pid)
    print("\nsmoke: %s" % ("OK" if not FAIL else "%d FAILED" % FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
