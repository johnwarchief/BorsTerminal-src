# -*- coding: utf-8 -*-
"""dev/qa_routes_guard.py — ابزارِ آزمون نباید جدولِ routeی از خودِ بسازد

چرا: `tools/clip_audit.mts` رویِ main ده سطرِ دستی داشت که باِ `routes.tsx`
هم‌خوان نبود — '#/' را «تابلو» می‌شمرد (آن مسیر به /master redirect می‌شود) و
چهار صفحۀ بعداً‌اضافه‌شده را اصلاً نمی‌شناخت. نتیجۀ عملی: آزمونِ ریسپانسیو
`/master` را سه بار سنجید و `market-status`/`notifications`/`watch`/`engine-lab`
را هرگز. هیچ‌کس نگرفت، چون جدولِ دستی هیچ‌وقت با کد مقایسه نمی‌شد.

دو سنجه:
  Q1  هر tools/*.mts که آرایۀ ROUTES دستی دارد باید از qa_routes.mts بخواند.
  Q2  شمارِ routeهایِ پارس‌شده باید با شمارِ `path:` در routes.tsx بخورد؛
      پارسرِ شکسته نباید «پوششِ کامل» دروغ بگوید.

اجرا:  python dev/qa_routes_guard.py [--selftest]
"""
from __future__ import annotations

import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROUTES_TSX = "frontend/src/routes.tsx"
PARSER = "tools/qa_routes.mts"

results = []


def chk(ok: bool, label: str) -> bool:
    results.append(bool(ok))
    print(("  ok   " if ok else "  FAIL ") + label)
    return bool(ok)


def read(path: str) -> str:
    if not os.path.exists(path):
        return ""
    return io.open(path, encoding="utf-8", errors="replace").read()


def count_paths(src: str) -> int:
    # هر شکلِ `{ path: '…' }` — تک‌سطری و چندقطری. نسخهٔ اول `^\s*path:` بود و
    # سه ورودیِ تک‌سطری (`{ path: '', … }`) را نمی‌دید؛ گارد همین را قرمز کرد.
    return len(re.findall(r"\bpath:\s*'", src))


# ── Q1: جدولِ دستیِ بی‌منبع ─────────────────────────────────────────────────
tools = sorted(
    os.path.join("tools", f) for f in os.listdir("tools") if f.endswith(".mts")
)
manual = []
for tf in tools:
    s = read(tf)
    if re.search(r"const ROUTES\s*:\s*Array<[^>]*>\s*=\s*\[", s):
        if "qa_routes.mts" not in s and "readRoutes" not in s:
            manual.append(tf)
chk(not manual,
    "Q1 هیچ ابزارِ آزمونِ tools/*.mts جدولِ ROUTES دستی بی‌منبع ندارد"
    + ((" — متخلف: " + ", ".join(manual)) if manual else ""))

# ── Q2: پارسر باید همان شمارِ router را بدهد ───────────────────────────────
tsx = read(ROUTES_TSX)
expected = count_paths(tsx)
chk(expected > 0, "Q2-الف routes.tsx خوانده شد و `path:` دارد (%d)" % expected)

if "--selftest" in sys.argv:
    # سم: یکِ route کم می‌شود؛ چک باید قرمز شود
    tmp = tsx.replace("    path: 'watch',\n", "", 1)
    if count_paths(tmp) >= expected:
        chk(False, "Q2-ب selftest: حذفِ path اثری بر شمارشِ انتظاری نداشت")
    else:
        print("  info  selftest: شمارشِ انتظاری با حذفِ یکِ route کم می‌شود "
              "(%d → %d)" % (expected, count_paths(tmp)))

node = subprocess.run(
    ["node", "--experimental-strip-types", "-e",
     "import('./tools/qa_routes.mts').then(async m => "
     "{const r=m.readRoutes('.');console.log(r.length)})"],
    capture_output=True, text=True, encoding="utf-8", errors="replace",
)
got = (node.stdout or "").strip().splitlines()
parsed = int(got[-1]) if got and got[-1].isdigit() else -1
chk(parsed == expected,
    "Q2-پ پارسرِ qa_routes.mts %d route می‌بیند، router واقعی %d تا دارد"
    % (parsed, expected))

# ── Q3: مقصدِ redirect باید از همان فایل خوانده شود ─────────────────────────
target = ""
m = re.search(r'Navigate\s+to="([^"]+)"', tsx)
if m:
    target = m.group(1)
rd = subprocess.run(
    ["node", "--experimental-strip-types", "-e",
     "import('./tools/qa_routes.mts').then(async m => "
     "{console.log(m.redirectTarget('.'))})"],
    capture_output=True, text=True, encoding="utf-8", errors="replace",
)
chk((rd.stdout or "").strip() == target and bool(target),
    "Q3 مقصدِ redirect (%s) از خودِ router خوانده می‌شود، نه از متنِ ابزار" % (target or "-"))

passed = sum(results)
failed = len(results) - passed
print("qa_routes_guard: %d passed / %d failed" % (passed, failed))
sys.exit(1 if failed else 0)
