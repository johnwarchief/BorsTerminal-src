#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""قراردادِ بیلدِ onedir (Phase B) — جلوگیری از مرگِ سایلنتِ فریزِشده.

دو چکِ اصلی:

  ۱) hiddenimports کامل است:
     api_router() در api/__init__.py ماژول‌های api/* را داخلِ بدنهٔ تابع
     import می‌کند، پس اسکنِ استاتیکِ PyInstaller آن‌ها را نمی‌بیند. اگر
     یکی در spec نباشد، EXE بالا می‌آید ولی اولین درخواست با
     ModuleNotFoundError می‌میرد. این «رایج‌ترین راهی است که این ریفاکتور
     بیلد را می‌کشد» (plans/velopack-onedir-data-layer.md). این تست لیست را
     از api/__init__.py استخراج می‌کند تا هیچ ماژولِ جدیدی فراموش نشود.

  ۲) شکلِ خروجی onedir است:
     _internal/ باید وجود داشته باشد (تفاوتِ onedir با onefile). بدونِ این،
     مسیردهیِ bors_config._app_dir() درست کار نمی‌کند.

استفاده:
    python dev/onedir_contract_v11.py                 # فقط چکِ سورس (سریع)
    python dev/onedir_contract_v11.py --dist dist     # چکِ خروجیِ بیلد هم
"""
import argparse
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SPEC = os.path.join(_ROOT, "fts_terminal.spec")
API_INIT = os.path.join(_ROOT, "api", "__init__.py")


def router_modules():
    """ماژول‌هایِ api.* که api_router() import می‌کند — منبعِ یگانه حقیقت."""
    src = open(API_INIT, encoding="utf-8").read()
    m = re.search(r"from \. import \(([^)]+)\)", src)
    if not m:
        return []
    return [x.strip() for x in m.group(1).split(",") if x.strip()]


def spec_hiddenimports():
    """همهٔ 'api.xxx' هایی که در spec لیست شده‌اند."""
    src = open(SPEC, encoding="utf-8").read()
    return set(re.findall(r"'(api\.[A-Za-z0-9_]+)'", src))


def check_hiddenimports():
    """چکِ ۱: هر ماژولِ router باید در hiddenimports باشد."""
    mods = router_modules()
    hid = spec_hiddenimports()
    missing = sorted("%s.%s" % ("api", m) for m in mods
                     if "api.%s" % m not in hid)
    ok = not missing
    print("  hiddenimports: %d router modules, %d listed in spec"
          % (len(mods), len(hid)))
    if ok:
        print("  [ok] every api.* router module is in hiddenimports")
    else:
        print("  [FAIL] missing from fts_terminal.spec: %s" % missing)
        print("         api_router() imports these inside a function body, so")
        print("         PyInstaller cannot see them -> ModuleNotFoundError at")
        print("         runtime. Add them to hiddenimports.")
    return ok, missing


def check_dist(dist_dir):
    """چکِ ۲: خروجیِ onedir باید _internal/ داشته باشد."""
    if not dist_dir or not os.path.isdir(dist_dir):
        print("  [skip] no dist dir given (--dist)")
        return True, None
    internal = os.path.join(dist_dir, "BorsTerminal_Ultimate", "_internal")
    exe = os.path.join(dist_dir, "BorsTerminal_Ultimate",
                       "BorsTerminal_Ultimate.exe")
    ok = os.path.isdir(internal) and os.path.isfile(exe)
    if ok:
        print("  [ok] onedir shape: %s + %s" % (
            os.path.relpath(exe, _ROOT), os.path.relpath(internal, _ROOT)))
    else:
        print("  [FAIL] not an onedir build: missing %s or %s" % (
            internal, exe))
    return ok, None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dist", default=None,
                    help="dist/ directory to verify (optional)")
    args = ap.parse_args()

    print("== onedir contract (Phase B) ==")
    ok1, missing = check_hiddenimports()
    ok2, _ = check_dist(args.dist)
    ok = ok1 and ok2

    print("\n[onedir contract] PASS" if ok else "\n[onedir contract] FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
