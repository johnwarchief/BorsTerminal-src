#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/fts_defaults_parity_guard.py -- «پیش‌فرضِ جزوه» فقط یک بار نوشته می‌شود.

چرا: کشوی تنظیماتِ فرانت‌اند روی کلید «Reset to FTS Defaults» همان عددی را به
سرور POST می‌کند که در `useFtsConfig.ts` دست‌نویس شده، در حالی که مرجعِ واقعی
`bors_config.FTS_DEFAULTS` است. دو بار این واگرایی رخ داده و هر بار بی‌صدا بوده:
کفِ شاخص ۴ در فرانت ۰٫۵ و در بک‌اند ۱٫۰ بود، و آستانهٔ پتانسیل سود ۳۰/۳۳ در
برابر ۴۰. کاربری که Reset می‌زد حدِ آستانه را عوض می‌کرد بدون اینکه بداند.

این گارد هر کلیدِ مشترک را مقایسه می‌کند و تعدادی کلیدِ حساسِ عددی را الزامی
می‌کند تا حذفِ بی‌صداشان از یک طرف شکست بدهد، نه اینکه تست سبز بماند.

خروج: کد ۰ اگر همه یکسان، ۱ در غیر این صورت.
اجرا:  python dev/fts_defaults_parity_guard.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TS_PATH = os.path.join("frontend", "src", "features", "fundamental", "api", "useFtsConfig.ts")

# کلیدهایی که حذف‌شان از هر یک از دو طرف باید گارد را قرمز کند، نه بی‌صدا رد شود.
CRITICAL = ("growth_min", "margin_min", "margin_optimal", "sales_to_mcap_min",
            "profit_potential_min", "eps_years", "industry_mode",
            "v10_sales_to_mcap_min", "v10_potential_min", "v10_margin_min",
            "v10_margin_ideal", "v10_eps_years",
            "v10_inflation_basis", "hourglass_rsi_period",
            "hourglass_rsi_oversold", "hourglass_ma52_position")

# «همهٔ صنایعِ دستوری» در کشوی تنظیمات فهرستِ سخت‌گیرانه‌تری نسبت به پیش‌فرضِ
# سرور می‌فرستد: سرور دارو/غذا را در فهرست وتو ندارد چون استثنای v2.1 با گیتِ
# حاشیهٔ ناخالص > ۵۰٪ اداره می‌شود (fts_engine:428)، و کلیدِ میانیِ کشو همان
# دو را از فهرستِ سخت کم می‌کند. پس برابری اینجا معنا ندارد؛ تنها چیزی که
# باید درست باشد این است که Reset هیچ‌گاه وتویِ صنایعِ سرور را کم نکند.
STRICT_SUPERSET = {"mandatory_sectors": ("دارو", "غذا")}

BLOCK_RE = re.compile(r"export const FTS_GUIDE_DEFAULTS\s*=\s*\{(.*?)\n\} as const", re.S)
KEY_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+?),\s*$", re.M)
CONST_RE = re.compile(r"export const SALES_TO_MCAP_GUIDE_DEFAULT\s*=\s*([0-9.]+)")


def _parse_scalar(raw):
    v = raw.strip()
    if v in ("true", "false"):
        return v == "true"
    if v.startswith("["):
        return re.findall(r"'([^']*)'", v)
    if v.startswith("'"):
        return v.strip("'")
    m = re.fullmatch(r"-?\d+(?:\.\d+)?", v)
    return float(v) if m else None


def guide_defaults():
    with open(os.path.join(ROOT, TS_PATH), encoding="utf-8") as f:
        src = f.read()
    block = BLOCK_RE.search(src)
    if not block:
        raise SystemExit("بلوک FTS_GUIDE_DEFAULTS در useFtsConfig.ts پیدا نشد")
    out = {}
    for key, raw in KEY_RE.findall(block.group(1)):
        val = _parse_scalar(raw)
        if val is not None:
            out[key] = val
    m = CONST_RE.search(src)
    out["__SALES_TO_MCAP_GUIDE_DEFAULT"] = float(m.group(1)) if m else None
    return out


def _same(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < 1e-9
    return a == b


def main():
    ts = guide_defaults()
    import bors_config
    py = bors_config.FTS_DEFAULTS

    checks = []

    def ck(cond, msg):
        checks.append((bool(cond), msg))

    for key in CRITICAL:
        ck(key in py, f"{key}: در bors_config.FTS_DEFAULTS وجود دارد")
        ck(key in ts, f"{key}: در FTS_GUIDE_DEFAULTS وجود دارد")

    shared = sorted(set(py) & set(ts) - {"__SALES_TO_MCAP_GUIDE_DEFAULT"}
                    - set(STRICT_SUPERSET))
    for key in shared:
        ck(_same(py[key], ts[key]),
           f"{key} یکسان است — سرور {py[key]!r} ⇄ فرانت {ts[key]!r}")

    for key, extra in STRICT_SUPERSET.items():
        srv, ui = set(py.get(key) or []), set(ts.get(key) or [])
        ck(srv <= ui, f"{key}: فهرستِ سرور زیرمجموعهٔ فهرستِ کشو است "
                      f"(Reset هیچ وتویی را کم نمی‌کند) — سرور {sorted(srv)} ⇄ کشو {sorted(ui)}")
        ck(srv <= ui and (ui - srv) == set(extra),
           f"{key}: اختلافِ کشو دقیقاً {list(extra)} است (استثنای v2.1)، نه چیزی دیگر")

    # سومین لایه: فال‌بک‌هایِ متنِ fts_engine (وقتی کلید از config بیفتد) هم باید
    # همان عددِ سرور باشند — واگراییِ این‌ها scoresِ scan_symbol و bulk_scan را
    # از هم دور می‌کند و گاردِ پاریتی آن را می‌گیرد، اما دیر.
    import fts_engine
    for key, dflt in sorted(fts_engine.DEFAULT_TH.items()):
        ck(key in py and _same(py[key], dflt),
           f"fts_engine.DEFAULT_TH[{key}] == سرور ({dflt!r} ⇄ {py.get(key)!r})")

    ck(_same(ts.get("__SALES_TO_MCAP_GUIDE_DEFAULT"), py.get("sales_to_mcap_min")),
       "SALES_TO_MCAP_GUIDE_DEFAULT == sales_to_mcap_min سرور"
       f" ({ts.get('__SALES_TO_MCAP_GUIDE_DEFAULT')!r} ⇄ {py.get('sales_to_mcap_min')!r})")

    failed = 0
    for ok, msg in checks:
        print(("  PASS " if ok else "  FAIL ") + msg)
        failed += 0 if ok else 1
    print(f"\n{len(checks)} checks, {failed} failed")
    print("FTS DEFAULTS PARITY " + ("OK" if failed == 0 else "FAILED"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
