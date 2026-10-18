# -*- coding: utf-8 -*-
"""گاردِ تازگیِ `docs/AGENT-INDEX.md`.

چرا لازم است: نقشۀ کد اگر کهنه باشد از نبودنش بدتر است — ایجنت به خطِ اشتباه
اعتماد می‌کند و همان grep سراسری را می‌کند، فقط با یک دروغِ اضافه. بی‌شبکه،
بی‌market.db.

جایِ اجرا: این گارد **عمداً** درِ `dev/run_all_tests.py` ثبت نشده — رأیِ مالک
(کامیت `935c690`: «نقشۀ کم‌توکنِ ایجنت — پارک‌شده، بی‌اتصال به CI»). یعنی پیش ازِ
هر کامیتِ ساختاری باید دستی دو فرمان اجرا شوند؛ بی‌تازگی درِ CI خطا نیست:
    python tools/build_agent_index.py && python dev/code_index_guard_v1065.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import build_agent_index as B  # noqa: E402

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))


def read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


gen = B.build()
idx_path = os.path.join(ROOT, "docs", "AGENT-INDEX.md")
ck(os.path.exists(idx_path), "docs/AGENT-INDEX.md وجود دارد")
cur = read(idx_path) if os.path.exists(idx_path) else ""
ck(cur == gen, "نقشه با سورسِ فعلی می‌خواند (بی‌تازگی = خطا)")

# آن‌چه نقشه باید داشته باشد، وگرنه برای ایجنت بی‌فایده است
for needle, why in (
    ("/api/screener", "اندپوینتِ اسکرینر با خطِ خودش هست"),
    ("/api/calendar/upcoming", "اندپوینتِ تقویم (مجمع) هست"),
    ("ind3_na", "توابعِ کلیدیِ موتور بنیادی فهرست شده"),
    ("FtsScreenTable", "برشِ بنیادیِ فرانت فهرست شده"),
    ("FtsFunnelStages", "برشِ مستر/قیف فهرست شده"),
    ("run_all_tests", "سوئیت‌های dev با توصیف از خودِ SUITES خوانده می‌شوند"),
    ("OWNER_RULINGS", "راه‌نمایِ رأی‌هایِ مالک ذکر شده"),
):
    ck(needle in gen, why)
# سقفِ ۴۰۰ درِ دورِ ادغامِ System 2 (۱۴۰۵-۰۷-۲۸) رد شد: نقشه ۴۱۶ سطر شد و
#دلیلِ سنجیده‌شدۀ این رشد این است که نسخۀ پیشین *کهنه* بود — `tools/build_agent_index.py`
# حالا ۲۹ اندپوینتِ `api/execution.py`، مسیرهایِ `api/chart.py` و چهار دروازۀ
# رابطِ تازه را هم فهرست می‌کند؛ بیرونِ نقشه هیچ فایلِ شاهدِ (`_audit/`،
# `_test_runs/`) فهرست نشده (دو سطر). پس این سطرهایِ اضافه *سطحِ محصول* است، نه
# پُرتُش. ۴۸۰ = ۴۱۶ + سرِ جایِ یکِ دروازۀ APIِ تازه؛ کوتاه‌کردنِ نقشه باِ حذفِ
# سطرِ اندپوینت انجام نشد، چون همان چیزی است که ایجنت برایِ مسیر‌یابی لازم دارد.
ck(len(gen.splitlines()) < 480, "نقشه کوتاه می‌ماند (< ۴۸۰ سطر) تا هزینه‌اش از فایدۀش بیشتر نشود")

# بازتولید باید قطعی باشد: دو بار ساختن، یک خروجی
ck(B.build() == gen, "بازتولید قطعی است (بی‌ترتیبِ تصادفی در فایل‌ها)")

# AGENTS.md باید به نقشه اشاره کند، وگرنه ایجنتِ تازه‌وارد پیدایش نمی‌کند
agents = read(os.path.join(ROOT, "AGENTS.md"))
ck("AGENT-INDEX.md" in agents, "AGENTS.md به نقشۀ کد لینک دارد")

bad = [m for ok, m in CHECKS if not ok]
for ok, m in CHECKS:
    print(("  ok  " if ok else "  FAIL ") + m)
if bad:
    print("AGENT-INDEX GUARD FAILED — %d/%d" % (len(CHECKS) - len(bad), len(CHECKS)))
    print("بازتولید: python tools/build_agent_index.py")
    sys.exit(1)
print("AGENT-INDEX GUARD OK — %d/%d" % (len(CHECKS), len(CHECKS)))
sys.exit(0)
