"""dev/loopback_guard_v1029.py — دروازهٔ حلقهٔ محروی روی /api/* سرِ جایِ خودش بایستد

چرا: لاگین محلی فقط UI است (frontend/src/shared/stores/authStore) و هیچ مسیری در
API هیچ اعتبارنامه‌ای نمی‌خواهد. پس هر صفحه‌وبی که کاربر باز می‌کند می‌تواند با
POST به 127.0.0.1:8001 اثر جانبیِ واقعی بسازد (بازنویسی market.db، رانِ نصابِ
سایلنت، انداختنِ IP با ADB). CORS فقط جلوی *خواندن* پاسخ را می‌گیرد، نه انجام
شدنِ کار. `app.py → loopback_guard` میزبان/Originِ غیرمحلی را رد می‌کند.

این گارد دو چیز را می‌سنجد که با یک ویرایشِ بی‌دقت می‌شکنند:
  • خودِ برنامه باید رد نشود: Host محلی و Origin محلی می‌گذرند، و درخواستِ
    بدونِ Origin (کالِ درونِ فرآیند) هم می‌گذرد.
  • درخواستِ بیرونی باید رد شود: Host یا Origin غیرمحلی روی /api/* → 403؛
    «Origin: null» هم رد می‌شود چون کروم آن را برای سندِ file:// می‌فرستد —
    یعنی یک HTMLِ دانلودشدهٔ محلی. مسیرهای غیرِ API (خودِ SPA) بسته به
    Origin نمی‌شوند.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

import app as appmod  # noqa: E402

FAILS = []


def ck(label, cond):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        FAILS.append(label)


# بدونِ context-manager: از lifespan (سینکِ بازارِ رویِ شروع) رد نمی‌شویم
# base_url محلاًست چون دروازه دقیقاً همین را می‌سنجد: hostِ غیرمحلی باید رد شود
# (TestClient به‌تنهایی «testserver» می‌فرستد و همه‌چیز 403 می‌شود).
client = TestClient(appmod.app, base_url="http://127.0.0.1:8001")

r = client.get("/api/update/version")
ck(" Host محلی: /api کار می‌کند (%s)" % r.status_code, r.status_code == 200)

r = client.get("/api/update/version", headers={"host": "evil.example.com"})
ck(" Host غیرمحلی → 403 (نه %s)" % r.status_code, r.status_code == 403)

r = client.get("/api/update/version", headers={"origin": "http://evil.example.com"})
ck(" Origin غیرمحلی → 403 (نه %s)" % r.status_code, r.status_code == 403)

r = client.get("/api/update/version", headers={"origin": "null"})
ck(" Origin «null» (سندِ file://) هم رد می‌شود", r.status_code == 403)

r = client.get("/api/update/version", headers={"origin": ""})
ck(" بدونِ Origin (کالِ درونِ فرآیند/curl) می‌گذرد", r.status_code == 200)

r = client.get("/api/update/version", headers={"origin": "http://localhost:8001"})
ck(" Origin localhost می‌گذرد", r.status_code == 200)

r = client.get("/", headers={"origin": "http://evil.example.com"})
ck(" مسیرِ غیرِ API با Origin بیرونی رد نمی‌شود (SPA نمی‌شکند)", r.status_code != 403)

# اثر جانبی‌ها باید پشتِ همین دروازه باشند، نه فقط /api/update
for path in ("/api/watchlist", "/api/sync/market"):
    r = client.post(path, headers={"origin": "https://evil.example.com"})
    ck(" POST %s با بیرونی → 403 (%s)" % (path, r.status_code), r.status_code == 403)

# نشانی/امضای دستِ سوم باید در مسیرِ آپدیت پذیرفته نشود
import api.update as upd  # noqa: E402

src = open("api/update.py", encoding="utf-8").read()
ck(" update/download نشانیِ مانیفست‌نخوان را رد می‌کند",
   "با مانیفستِ به‌روزرسانی" in src and "req.url or platform.get" not in src)
ck(" اسکریپتِ توسعه 0.0.0.0 را نمی‌بندد",
   "--host 0.0.0.0" not in open("run_terminal.sh", encoding="utf-8").read())

if FAILS:
    print("\nLOOPBACK GUARD FAILED: %d" % len(FAILS))
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("\nLOOPBACK GUARD OK")
