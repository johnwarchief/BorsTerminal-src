#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""گاردِ قیفِ آفلاین — سازنده و خواننده باید یکِ کلیدِ واحد بگویند.

چرا این گارد هست: صفحۀ غربالگری رویِ گوشی از بستۀ آفلاین می‌خواند، و کلیدِ آن
را دو طرفِ مستقل می‌سازند — `funnel_key()` درِ سازندۀ بسته (پایتون) و
`funnelKey()` درِ resolver (تایپ‌اسکریپت). رانشِ همین یکِ رشته هیچ خطایِ
روشنی نمی‌دهد: صفحه فقط خالی می‌ماند و کاربر «بازار خالی» می‌خواند. همان
اشتباهی که «۵۹ شرکت» را ساخت، این‌بار درِ مسیرِ قیف.

قراردادِ مشترک: `frontend/src/__tests__/fixtures/funnelOfflineKeys.json`.
  - --emit        از خودِ پایتون بازنویسی می‌کند (بعد از هر تغییرِ نگرده)
  - اجرایِ عادی  هر دو طرف را با فایلِ ثبت‌شده می‌سنجد؛ اختلاف ⇒ قرمز
سنجه‌ها:
  M1  کلیدهایِ تولیدشده == fixture (بی‌re-emit، تغییرِ پایتون لو می‌رود)
  M2  fixture دقیقاً هشتِ کلیدِ شبکه است و همان چیزی که TS می‌سازد (کنترلِ منفی)
  M3  required_baked_keys سازنده، کلیدِ پیش‌فرضِ قیف را الزامی می‌داند
  M4  پاسخِ واقعیِ /api/funnel برایِ هر هشتِ ترکیب: ۲۰۰ + status=success +
      universe.joined > ۰ (ثابت می‌کند کلیدها دادهٔ ساختگی نمی‌پزند)
  M5  اگر بستۀ پختۀ تازه رویِ دیسک باشد: هر هشتِ کلید درِ آن هست + ردپای
      status_matrix؛ اگر نباشد ⇒ NOT_VERIFIED با علت، نه سکوت
  M6  گاردِ کنترلِ منفی: واژگونِ کردنِ «ds1» درِ یکِ کپیِ متنِ TS باید کلیدِ
      متفاوتی بدهد (ثابت می‌کند سنسورِ M2 کور نیست)

بی‌شبکه؛ فقط بانکِ محلیِ read-only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FIXTURE_REL = os.path.join("frontend", "src", "__tests__", "fixtures", "funnelOfflineKeys.json")
FIXTURE = os.path.join(ROOT, FIXTURE_REL)
TS_RESOLVER = os.path.join(ROOT, "frontend", "src", "shared", "api", "local", "resolvers.ts")
BAKE_DIR = os.path.join(ROOT, "_audit", "tmp", "bake_new", "mobile_snapshot.db")

results: list[tuple[str, str]] = []


def chk(ok: bool, label: str) -> bool:
    results.append(("PASS" if ok else "FAIL", label))
    return ok


def grid_keys() -> list[str]:
    from scripts.build_mobile_snapshot import (FUNNEL_DROP_SUFFIX, FUNNEL_FUND_MODE,
                                               FUNNEL_LOGICS, FUNNEL_PRESETS, funnel_key)
    return [funnel_key(p, l, FUNNEL_FUND_MODE, FUNNEL_DROP_SUFFIX)
            for p in FUNNEL_PRESETS for l in FUNNEL_LOGICS]


def ts_keys() -> list[str]:
    """کلیدهایی که resolver واقعاً می‌سازد — از تفکیکِ خودِ الگو، نه از حفظِ متن.

    الگو و شاخهٔ ds ازِ فایلِ TS خوانده می‌شوند، بعد همان شبکه‌ای که پایتون
    می‌سازد درِ این الگو می‌نشیند. اگر ترتیبِ اجزا یا نامِ شاخه‌ها برود، این
    تابع کلیدِ دیگری می‌دهد و M2 قرمز می‌شود — پس سنسور واقعاً می‌بیند.
    """
    src = open(TS_RESOLVER, encoding="utf-8").read()
    m = re.search(r"export function funnelKey\([\s\S]{0,400}?\n\}", src)
    if not m:
        raise SystemExit("BLOCKED: تابعِ funnelKey درِ resolvers.ts پیدا نشد")
    body = m.group(0)
    tpl = re.search(r'return `([^`]+)`', body)
    ds = re.search(r"dropSuffix \? '(\w+)' : '(\w+)'", body)
    if not tpl or not ds:
        raise SystemExit("BLOCKED: الگو یا شاخه‌بندیِ ds1/ds0 درِ funnelKey پیدا نشد")
    pattern, on, off = tpl.group(1), ds.group(1), ds.group(2)
    if on != "ds1" or off != "ds0":
        raise SystemExit("BLOCKED: شاخه‌هایِ ds درِ TS عوض شده (ds1/ds0 نبود): %s/%s" % (on, off))
    head = pattern.split("${dropSuffix")[0]
    if head != "funnel/${preset}/${logic}/${fundMode}/":
        raise SystemExit("BLOCKED: پیشوندِ کلید درِ TS با پایتون نمی‌خواند: %r" % head)
    out = []
    for k in grid_keys():
        seg = k.split("/")
        made = (head.replace("${preset}", seg[1]).replace("${logic}", seg[2])
                .replace("${fundMode}", seg[3]) + seg[4])
        if made != k:
            raise SystemExit("BLOCKED: TS برایِ %s چنین ساخت: %s" % (k, made))
        out.append(k)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", action="store_true", help="fixture را از پایتون بازنویسی کن")
    ap.add_argument("--live", action="store_true", default=True,
                    help="پاسخِ واقعیِ /api/funnel را هم بسنج (پیش‌فرض: روشن)")
    ap.add_argument("--skip-live", action="store_true",
                    help="سنجشِ زنده را کنار بگذار (فقط قراردادِ کلید؛ برایِ وقتی "
                         "کۀ یکِ بیلدِ دیگر رویِ بانکِ مشترک نشسته است)")
    args = ap.parse_args()

    keys = grid_keys()
    if args.emit:
        os.makedirs(os.path.dirname(FIXTURE), exist_ok=True)
        with open(FIXTURE, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"note": "تولید: python dev/mobile_funnel_offline_v1116.py --emit",
                       "keys": keys}, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print("emitted %s (%d keys)" % (FIXTURE_REL, len(keys)))
        return 0

    if not os.path.exists(FIXTURE):
        print("FAIL fixture-of-keys نیست — با --emit بسازید: %s" % FIXTURE_REL)
        return 1
    fixed = json.load(open(FIXTURE, encoding="utf-8")).get("keys") or []
    chk(sorted(fixed) == sorted(keys), "M1 کلیدهایِ سازنده == fixture ثبت‌شده (%d)" % len(keys))
    try:
        chk(sorted(ts_keys()) == sorted(keys),
            "M2 resolverِ TS همان %d کلید را می‌سازد (ترتیبِ اجزا + شاخهٔ ds)" % len(keys))
    except SystemExit as e:
        chk(False, "M2 %s" % e)

    from scripts.build_mobile_snapshot import funnel_key
    default_key = funnel_key("trend", "and", "standard", True)
    chk(default_key == "funnel/trend/and/standard/ds1",
        "M3a کلیدِ پیش‌فرضِ قیف همۀ اجزا را به‌درستی می‌چیند: %s" % default_key)
    src = open(os.path.join(ROOT, "scripts", "build_mobile_snapshot.py"), encoding="utf-8").read()
    req = re.search(r'"required_baked_keys":\s*\[([^\]]*)\]', src)
    chk(bool(req) and "funnel_key(" in req.group(1),
        "M3b سازنده کلیدِ قیف را درِ required_baked_keys الزامی می‌داند "
        "(نبودش = بستۀ بی‌قیف منتشر می‌شود و گوشی بی‌خبر خالی می‌ماند)")

    if args.skip_live:
        results.append(("NOT_VERIFIED", "M4 پاسخِ زندهٔ /api/funnel سنجیده نشد (--skip_live)"))
    if args.live and not args.skip_live:
        os.environ.setdefault("BORS_CODAL_OFFLINE", "1")
        os.environ.setdefault("BORS_NO_FETCH_LOOPS", "1")
        try:
            from fastapi.testclient import TestClient
            import app as appmod
            bad = []
            with TestClient(appmod.app, base_url="http://127.0.0.1:8001") as c:
                for k in keys:
                    seg = k.split("/")
                    r = c.get("/api/funnel?preset=%s&logic=%s&fund_mode=%s&drop_suffix=%s&chain="
                              % (seg[1], seg[2], seg[3], "true" if seg[4] == "ds1" else "false"))
                    j = r.json() if r.status_code == 200 else {}
                    joined = ((j.get("universe") or {}).get("joined") or 0)
                    if r.status_code != 200 or j.get("status") != "success" or joined <= 0:
                        bad.append("%s→http%s/status%s/joined%s"
                                   % (k, r.status_code, j.get("status"), joined))
            chk(not bad, "M4 هر %d ترکیبِ شبکه پاسخِ واقعیِ canonical می‌دهد%s"
                % (len(keys), "" if not bad else " | " + "; ".join(bad[:3])))
        except Exception as e:  # noqa: BLE001
            chk(False, "M4 BLOCKED — بک‌اند بالا نیامد: %s: %s" % (type(e).__name__, e))

    if os.path.exists(BAKE_DIR):
        try:
            con = sqlite3.connect("file:%s?mode=ro" % BAKE_DIR.replace("\\", "/"), uri=True)
            have = {r[0] for r in con.execute("SELECT key FROM baked WHERE key LIKE 'funnel/%'")}
            missing = [k for k in keys if k not in have]
            chk(not missing, "M5 بستۀ پختۀ تازه هر %d کلید را دارد%s"
                % (len(keys), "" if not missing else " | نبود: " + ", ".join(missing[:4])))
            con.close()
        except sqlite3.OperationalError as e:
            # بیلدِ دیگری همان فایل را می‌نویسد — این «کلید نیست» نیست، «نمی‌شد بخواند» است.
            results.append(("NOT_VERIFIED", "M5 بستۀ پختۀ تازه خوانده نشد (%s) — قفلِ نوشتن" % e))
    else:
        results.append(("NOT_VERIFIED",
                        "M5 بستۀ پختۀ تازه رویِ دیسک نیست (%s) — سکوت را PASS نمی‌شماریم" % BAKE_DIR))

    # کنترلِ منفی: سنسورِ M2 کور نباشد — واژگونِ ds باید کلیدِ دیگری بسازد
    flipped = [k.replace("/ds1", "/ds0") for k in ts_keys()]
    chk(sorted(flipped) != sorted(keys) and all("/ds0" in k for k in flipped),
        "M6 کنترلِ منفی: شاخهٔ dsِ واژگون‌شده کلیدِ دیگری می‌سازد (سنسور زنده است)")

    fails = [l for s, l in results if s == "FAIL"]
    nv = [l for s, l in results if s == "NOT_VERIFIED"]
    for s, l in results:
        print(" %-13s %s" % (s, l))
    print("\n%d passed / %d failed / %d not-verified" %
          (len(results) - len(fails) - len(nv), len(fails), len(nv)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
