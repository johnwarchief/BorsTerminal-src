# -*- coding: utf-8 -*-
"""گاردِ قراردادِ محیطیِ ترمیمِ تاریخچه — `BORS_NO_FETCH_LOOPS` دربِ *همهٔ* درخواست‌هاست.

چرا این فایل متولد شد: اندازه‌گیریِ مرحلۀ B (۲۰۲۶-۱۰-۱۸، شاخهٔ مأموریتِ چارت) نشان داد
با `BORS_NO_FETCH_LOOPS=1` پاسخِ چارت همچنان `historyRepairScheduled: True` می‌دهد و
تردِ `hist-repair` واقعاً از TSETMC می‌گیرد و درِ `price_history` می‌نویسد
(فولاد: ۳۹۱ کندل → ۳۹۲ کندل). یعنی همان اجرایِ «فقط بخوان» که برایِ بازِ نگه‌داشتنِ
IPِ نشستِ واقعیِ مالک ساخته شده بود، ازِ دری می‌رفت که app.py نمی‌پاید.

قراردادِ حفظ‌شده:
  • درب در `bors_flags.fetch_loops_enabled()` است (یگانہ منبع؛ app.py هم همان را صدا می‌زند).
  • با دربِ بسته `_schedule_history_repair` هیچ تردی نمی‌سازد، هیچ درخواستی نمی‌فرستد،
    و `BORS_NO_FETCH_LOOPS=1` است.
  • علامتِ زمانِ تلاش (`_HISTORY_REPAIR_AT`) هم زده نمی‌شود — تاِ برداشتنِ درب، نماد
    معطلِ سقفِ ۱۵ دقیقه نماند.
  • با دربِ باز، رفتارِ قبلی دست‌نخورده است: یکِ نماد، سقفِ ۱۵ دقیقه، و همان
    `test_tsetmc.fetch_price_history` (که خودش min_interval و سقفِ ۴۲۹ دارد).

هیچ درخواستِ شبکه‌ای درِ این گارد نمی‌دود: `test_tsetmc` باِ یکِ ناظرِ بی‌شبکه
جایگزین می‌شود و درِ پایانِ سنجه پس داده می‌شود.
"""
import os
import sys
import threading
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import api.chart as C          # noqa: E402
import bors_flags              # noqa: E402

P = F = 0


def ck(cond, msg, detail=""):
    """یکِ سنجه؛ خطا رأیِ کلِ فایل را عوض نمی‌کند تاِ همه دیده شوند."""
    global P, F
    if cond:
        P += 1
        print("  ✓ %s%s" % (msg, ("   ← %s" % detail) if detail else ""))
    else:
        F += 1
        print("  ✗ %s%s" % (msg, ("   ← %s" % detail) if detail else ""))


# ---------- ۱) خودِ پرچم: یگانہ منبع، دو مصرف‌کننده ----------
_SAVED = os.environ.get("BORS_NO_FETCH_LOOPS")


def _setenv(val):
    if val is None:
        os.environ.pop("BORS_NO_FETCH_LOOPS", None)
    else:
        os.environ["BORS_NO_FETCH_LOOPS"] = val


for val, want in ((None, True), ("0", True), ("", True),
                  ("1", False), ("true", False), ("YES", False), (" 1 ", False)):
    _setenv(val)
    got = bors_flags.fetch_loops_enabled()
    ck(got is want, "پرچم: BORS_NO_FETCH_LOOPS=%r ⇒ %s" % (val, want), "واقعاً=%s" % got)

_setenv("1")
import app as A  # noqa: E402  (دربِ حلقه‌هایِ app باید همان داوری باشد)
ck(A._fetch_loops_enabled() is False, "app._fetch_loops_enabled درِ حالتِ درب‌بسته False است")
_setenv(None)
ck(A._fetch_loops_enabled() is True, "app._fetch_loops_enabled درِ حالتِ باز True است")

# ---------- ۲) ناظرِ بی‌شبکه به‌جایِ test_tsetmc ----------
CALLS = []


class _SpyTsetmc(types.ModuleType):
    def fetch_price_history(self, symbol, *a, **kw):
        CALLS.append(symbol)
        return []


_REAL_TSETMC = sys.modules.get("test_tsetmc")
sys.modules["test_tsetmc"] = _SpyTsetmc("test_tsetmc")


def _repair_threads():
    return [t.name for t in threading.enumerate() if "hist-repair" in t.name.lower()]


def _reset(symbol="فولاد"):
    CALLS.clear()
    C._HISTORY_REPAIR_AT.clear()
    return symbol


# ---------- ۳) دربِ بسته: هیچ تردی، هیچ درخواستی، هیچ علامتی ----------
_setenv("1")
_sym = _reset()
due = C._history_repair_due("2026-10-14", "2026-10-18", _sym)
ck(due is True, "پیش‌سنج: شکافِ واقعی وجود دارد (باِ دربِ باز طلبِ ترمیم می‌شد)")
r0 = C._schedule_history_repair(_sym, "2026-10-14", "2026-10-18")
time.sleep(0.4)
ck(r0 is False, "درب‌بسته ⇒ `_schedule_history_repair` False می‌دهد")
ck(_repair_threads() == [], "درب‌بسته ⇒ تردِ hist-repair زاده نمی‌شود", str(_repair_threads()))
ck(CALLS == [], "درب‌بسته ⇒ هیچ فراخوانیِ دریافتِ تاریخچه نمی‌شود", str(CALLS))
ck(_sym not in C._HISTORY_REPAIR_AT,
   "درب‌بسته ⇒ زمانِ تلاش علامت نمی‌خورد (برداشتنِ درب بی‌انتظارِ ۱۵ دقیقه کار می‌کند)")

# ---------- ۴) همانِ سنجه باِ دربِ باز (رفتارِ سابق نباید عوض شود) ----------
_setenv(None)
_sym = _reset()
r1 = C._schedule_history_repair(_sym, "2026-10-14", "2026-10-18")
_deadline = time.time() + 3.0
while not CALLS and time.time() < _deadline:
    time.sleep(0.05)
ck(r1 is True, "درب‌باز ⇒ همان نمادِ دارایِ شکاف دوباره طلبِ ترمیم می‌شود")
ck(CALLS == [_sym], "درب‌باز ⇒ درست یکِ دریافتِ تاریخچه برایِ همانِ یک نماد", str(CALLS))
ck(_sym in C._HISTORY_REPAIR_AT, "درب‌باز ⇒ علامتِ زمانِ تلاش زده می‌شود (سقفِ نرخ فعال)")
r2 = C._schedule_history_repair(_sym, "2026-10-14", "2026-10-18")
ck(r2 is False, "سقفِ ۱۵ دقیقه: فراخوانِ دومِ همان نماد درِ همانِ دور رد می‌شود")
r3 = C._schedule_history_repair("شستا", "2026-10-14", "2026-10-18")
ck(r3 is True, "سقفِ نرخ هر نماد جداست: نمادِ دیگر باِ شکاف می‌گذرد")
C._HISTORY_REPAIR_AT.clear()
r4 = C._schedule_history_repair("ولش", "2026-10-17", "2026-10-17")
ck(r4 is False, "بی‌شکاف (target ≤ last) ⇒ ترمیم حتی باِ دربِ باز درخواست نمی‌فرستد")

# ---------- ۵) مسیرِ واقعیِ پاسخ: علامتِ دروغ نمی‌گوید ----------
_setenv("1")
CALLS.clear()                             # فراخوانی‌هایِ بخشِ ۴ (درب‌باز) این‌جا حساب نیست
C._HISTORY_REPAIR_AT.clear()
C.CHART_CACHE.clear()
_old_offline_until = C.CDN_OFFLINE_UNTIL
C.CDN_OFFLINE_UNTIL = time.time() + 120          # اجبارِ مسیرِ جایگزین، بی‌شبکه
try:
    payload = C.get_chart_tsetmc("فولاد")
    ck(payload.get("degraded") is True, "مسیرِ جایگزین همچنان `degraded: True` اعلام می‌کند")
    ck(payload.get("candles") and len(payload["candles"]) > 0,
       "مسیرِ جایگزین سریِ محلی را می‌دهد (نه پاسخِ خالی)", "n=%s" % len(payload.get("candles") or []))
    ck(payload.get("historyRepairScheduled") is False,
       "درب‌بسته ⇒ `historyRepairScheduled` درِ پاسخ False است، نه Trueِ گمراه‌کننده",
       "واقعاً=%r" % payload.get("historyRepairScheduled"))
    ck(CALLS == [], "درِ همانِ پاسخِ واقعی هم هیچ دریافتی رویِ سیم نرفت", str(CALLS))
finally:
    C.CDN_OFFLINE_UNTIL = _old_offline_until
    C.CHART_CACHE.clear()

# ---------- ۶) پس‌دادنِ محیط ----------
if _REAL_TSETMC is not None:
    sys.modules["test_tsetmc"] = _REAL_TSETMC
else:
    sys.modules.pop("test_tsetmc", None)
_setenv(_SAVED)

print()
print("نتیجه: %d سبز، %d قرمز" % (P, F))
sys.exit(0 if F == 0 else 1)
