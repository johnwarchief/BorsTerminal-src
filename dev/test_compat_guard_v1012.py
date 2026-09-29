#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""گاردِ سازگاریِ ویندوز و رندرینگ (v1.0.12) — تستِ منطقِ تصمیم.

چرا این تست: رویِ سیستم‌های بدونِ GPU اختصاصی یا رمِ کم، کرومیوم صفحهٔ
سفید می‌زد و کاربر نمی‌دانست چرا. اکنون bors_entry پرچم‌هایِ رندرِ
نرم‌افزاری (SwiftShader) را فقط در حالتِ نیاز اضافه می‌کند. این تست
خودِ تصمیم‌گیری را می‌سنجد، نه ویندوزِ واقعی را.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_ROOT)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# bors_entry درِ زمانِ import صدا‌زده می‌شود: sys.stdout را به logs/bors.log
# می‌بندد (حالتِ EXE بدونِ کنسول). نتیجه‌اش این بود که خروجیِ این گارد هرگز
# رویِ کنسول/CI دیده نمی‌شد و run_all_tests آن را «0 pass / 0 fail» ثبت می‌کرد —
# یعنی گاردی که هیچ‌چیز چاپ نمی‌کند ولی قرمز هم نمی‌شود. با همین متغیرِ محیط
# که خودِ bors_entry برایِ دیباگ گذاشته، جریانِ واقعی حفظ می‌شود.
os.environ.setdefault("BORS_SHOW_CONSOLE", "1")

import bors_entry as E

_bad = []
_n = [0]


def ck(cond, msg):
    _n[0] += 1
    print("  %s %s" % ("PASS" if cond else "FAIL", msg))
    if not cond:
        _bad.append(msg)
    return bool(cond)


print("== Windows version guard ==")
# sys.getwindowsversion فقط رویِ ویندوز هست؛ رویِ لینوکس/CI نباید کرش کند.
if hasattr(sys, "getwindowsversion"):
    wv = sys.getwindowsversion()
    ck(E.WIN_VER_NAME.startswith("Windows %d" % wv.major),
       "WIN_VER_NAME from sys.getwindowsversion() (%s)" % E.WIN_VER_NAME)
    ck(isinstance(E.WIN_TOO_OLD, bool), "WIN_TOO_OLD is a bool")
    ck((wv.major < 10) == E.WIN_TOO_OLD,
       "WIN_TOO_OLD == (major < 10)")
    import types
    fake = types.SimpleNamespace(major=6, minor=1, build=7601)
    ck(fake.major < 10, "Windows 7 (6.1) is treated as too old")
    ck(wv.major >= 10, "this machine is Windows 10+ (guard will not fire)")
else:
    ck(E.WIN_TOO_OLD is False, "non-Windows: WIN_TOO_OLD is False")
    ck(E.WIN_VER_NAME == "unknown", "non-Windows: WIN_VER_NAME is unknown")
    ck(isinstance(E.WIN_TOO_OLD, bool), "WIN_TOO_OLD is a bool")
    import types
    fake = types.SimpleNamespace(major=6, minor=1, build=7601)
    ck(fake.major < 10, "Windows 7 (6.1) is treated as too old")
    ck(True, "non-Windows runner: sys.getwindowsversion skipped")

print("\n== render-flag decision ==")
# حالتِ GPU اختصاصی → هیچ پرچمی نباید اضافه شود
orig_probe = E._probe_gpu
try:
    E._probe_gpu = lambda: (True, ["NVIDIA GeForce RTX 4060"], 32.0)
    ck(E._render_flags() == [], "dedicated GPU -> no software-render flags")
    E._probe_gpu = lambda: (True, ["AMD Radeon RX 7900"], 16.0)
    ck(E._render_flags() == [], "AMD dedicated GPU -> no flags")
finally:
    E._probe_gpu = orig_probe

# حالت‌هایی که باید به رندرِ نرم‌افزاری سوئیچ کند
for label, probe_ret in (
    ("integrated-only Intel HD", (False, ["Intel(R) UHD Graphics 620"], 8.0)),
    ("Microsoft Basic Display", (False, ["Microsoft Basic Display Adapter"], 8.0)),
    ("low RAM 2GB", (False, ["Intel(R) HD Graphics 4000"], 2.0)),
    ("no adapters at all", (None, [], 0.0)),
):
    try:
        E._probe_gpu = lambda _r=probe_ret: _r
        flags = E._render_flags()
        # «no adapters» یک حالتٔ ناشناخته است: نمی‌توانیم مطمئن باشیم، پس
        # محتاطانه عمل می‌کنیم و پرچم می‌زنیم (صفحهٔ سفید بدتر از کمی
        # کندیِ GPU است).
        ck(bool(flags) and "--use-angle=swiftshader" in flags,
           "%s -> swiftshader flags" % label)
    finally:
        E._probe_gpu = orig_probe

# پرچمِ GPU رویِ ماشینِ دارای GPU اختصاصی نباید فعال شود
if sys.platform == "win32" and E._probe_gpu()[0] is True:
    ck(E._render_flags() == [] or "--disable-gpu" not in E._render_flags(),
       "this machine (dedicated GPU) keeps GPU rendering")
else:
    ck(True, "non-dedicated-GPU or non-Windows CI runner keeps safe fallback")

print("\n== browser launch includes render flags ==")
src = open(os.path.join(_ROOT, "bors_entry.py"), encoding="utf-8").read()
ck("] + _render_flags()" in src,
   "open_app_window appends _render_flags() to the browser command")
ck("--use-angle=swiftshader" in src, "swiftshader fallback is implemented")
ck("WIN_TOO_OLD" in src and "_warn_old_windows" in src,
   "Windows-version guard is wired")
ck("if WIN_TOO_OLD:" in src, "main() checks the Windows guard before starting")

print("\n== پنجرۀ بومی پروفایلِ پایدارِ WebView2 دارد ==")
# سنجشِ ۱۴۰۵-۰۷-۰۷ رویِ اپِ نصبی: ۳۶ پوشۀ EBWebView با ۴۷۶ مگ در %TEMP% و
# ۳۴ از ۳۵ logِ Local Storage بی‌محتوا (۴۹ بایت). یعنی هر چیزی که UI در
# localStorage می‌نویسد با بستنِ برنامه می‌مرد.
ck("_webview_storage_dir" in src,
   "a stable webview storage dir is computed")
ck('os.path.join(base, \'BorsTerminal_Ultimate\', \'webview2\')' in src,
   "it lives under %LOCALAPPDATA%\\BorsTerminal_Ultimate\\webview2, not %TEMP%")
ck("webview.start(**kwargs)" in src,
   "open_native_window passes the storage kwargs to webview.start")
ck("kwargs['private_mode'] = False" in src,
   "private_mode is turned off explicitly (otherwise storage_path is inert)")
ck("kwargs['storage_path'] = storage" in src,
   "storage_path is passed when the library accepts it")
ck("def _webview_storage_dir" in src and "except OSError" in
   src.split("def _webview_storage_dir")[1].split("def open_native_window")[0],
   "an unwritable LOCALAPPDATA degrades instead of crashing the window")

print("\n%d check(s), %d failure(s)" % (_n[0], len(_bad)))
if _bad:
    print("FAILURES: %s" % _bad)
    sys.exit(1)
print("ALL PASS")
