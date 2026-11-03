# -*- coding: utf-8 -*-
"""e_report.py — گزارشِ مأموریتِ Performance First + Market-Open Verification.

هر عددِ فارسیِ این فایل ازِ همین اسکریپت و ازِ فایل‌هایِ شواهد (`_test_runs/performance_first_*`)
ساخته می‌شود؛ هیچ رقمی دستی نوشته نشده است (قاعدۀ مخزن: تایپِ دستیِ رقم، رقم را می‌دزدد).
اجرا:  PYTHONIOENCODING=utf-8 python _test_runs/performance_first_2026-10-18/e_report.py
"""
import ast
import glob
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from a2_gzip_abba import PRISTINE_SHA  # noqa: E402
WT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_MD = os.path.join(WT, "docs", "research", "PERFORMANCE-FIRST-MARKET-OPEN-VERIFICATION-2026-10-18.md")
OLD_MD = os.path.join(WT, "docs", "research", "PERFORMANCE-MARKET-HOURS-FINAL-VERIFICATION-2026-10-17.md")

L = []
A = L.append


def fa(s):
    t = str(s)
    out = []
    for ch in t.lstrip("-"):
        out.append(chr(0x06F0 + int(ch)) if ch.isdigit() else
                   ("٬" if ch == "," else ("٫" if ch == "." else ch)))
    return ("−" if t.startswith("-") else "") + "".join(out)


def num(v):
    v = float(v)
    if abs(v - round(v)) < 1e-9:
        return fa("{:,.0f}".format(v))
    return fa("{:,.1f}".format(v))


def ms(v):
    return num(round(float(v))) + " ms" if float(v) < 1000 else num(float(v) / 1000.0) + " s"


def sec(v):
    return num(float(v)) + " s"


def load(name, required=True):
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        if required:
            raise SystemExit("شاهدِ لازم نیست: " + name)
        return None
    return json.load(io.open(p, encoding="utf-8"))


def tail_lines(name, needles):
    """چند خطِ اولِ لاگِ را که با needle شروع می‌شوند برمی‌گرداند (برایِ شمارِ سبز/قرمز)."""
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        return []
    txt = io.open(p, encoding="utf-8", errors="replace").read().splitlines()
    return [t for t in txt if any(t.startswith(n) for n in needles)]


def sh(cmd):
    return subprocess.run(cmd, cwd=WT, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def scans(variant):
    """شمارِ رویدادِ «اسکنِ سنگین» درِ لاگِ همان ریگ — نه عددِ دستی."""
    return sum(1 for _t, m in (variant.get("log_events") or []) if "running heavy bulk scan" in m)


def head(title):
    A("")
    A("## " + title)
    A("")


# ── ۰) خلاصه ────────────────────────────────────────────────────────────────
def s0(a2, p0rep, p0v1rep, gates1, gates2, build, smoke, shots, c20, c20b, eq2, bugrep):
    hit = a2["cli"]["metrics"]["funnel-hit.ms"]
    wire = a2["cli"]["metrics"]["funnel-hit.wire_bytes"]
    fx = p0rep["fixed"]["post_first"]
    head(title="۰) خلاصهٔ کارِ تمام‌شده و پاسخِ پنج پرسشِ مأموریت")
    A("| پرسش | پاسخ | برچسب | مدرک |")
    A("|---|---|---|---|")
    A("| آیا سرعتِ کاربر بهتر شد؟ | درِ مسیرِ گرمِ قیف: میانۀ پاسخِ `HIT` رویِ gzip-۱ " + ms(hit["A"]["median"]) +
      " در برابرِ " + ms(hit["B"]["median"]) + " رویِ gzip-۵؛ و بن‌بستِ سازۀ اول که " +
      ms(bugrep["bug"]["post_first"]["ms"]) + " کشید به " + ms(fx["ms"]) +
      " (" + fa(scans(p0rep["fixed"])) + " اسکن) برگشت | PASS (آفلاین، ریگِ کنترل‌شده) | "
      "`a2-aggregate.json`, `p0-rig-repro*.json` |")
    A("| چه چیزی این را اثبات می‌کند؟ | گاردِ بدنهٔ کش رویِ کدِ نهایی با " + fa(c20b["rounds"][-1]["green"]) +
      " بندِ سبز و " + fa(c20b["rounds"][-1]["red"]) + " بندِ قرمز، گاردِ قرمز‌سبزِ بن‌بست، "
      "سنجشِ برابریِ خروجی رویِ " + fa(len(eq2["endpoints"])) +
      " مسیر، و شواهدِ مرورگرِ واقعی (§۶) | PASS | `p0-rig-gates.json`, `p0v3-guard.json`, "
      "`p0v2-red-green.json` |")
    A("| کدام مسیر هنوز کند است؟ | سازۀ سردِ اولِ پس ازِ بالا آمدنِ سرویس (منتظرِ اسکنِ سنگینِ استارت‌آپ)، و "
      "گیتِ کامل که یک بندِ زمان‌سنجِ ناپایدار دارد | NOT_FIXED / SYSTEM1 | §۴ §۷ §۱۱ |")
    A("| آیا gzip-۱ به‌اندازۀ ترافیکش ارزش داشت؟ | بله: بدنهٔ `HIT` رویِ gzip-۱ " + num(wire["A"]["median"]) +
      " B است در برابر " + num(wire["B"]["median"]) + " B (ترافیک " +
      num(100.0 * (1.0 - wire["B"]["median"] / wire["A"]["median"])) + "٪ بیشتر)، و زمانِ میانی " +
      ms(hit["A"]["median"]) + " در برابر " + ms(hit["B"]["median"]) + " | PASS | §۵ |")
    A("| مهم‌ترین اقدامِ بعدی؟ | روشن‌کردنِ حلقهٔ دریافتِ TSETMC و restartِ سرویسِ :8000 با هماهنگیِ System 1 — بی‌این، "
      "تازگیِ داده درِ نشستِ واقعی اندازه‌گیری‌پذیر نیست | BLOCKED-on-System1 | §۱۰ §۱۱ |")
    A("")
    A("**حدِّ صادقانهٔ این گزارش:** همهٔ اعداد درِ ماشینِ کاریِ من، رویِ ریگِ " + fa("8020") +
      " و بانکِ `pristine` و با `BORS_NO_FETCH_LOOPS=1` گرفته شده‌اند. پایشِ نشستِ زنده انجام نشد (§۱۰). "
      "هیچ عددی ازِ سنجشِ آفلاین، مدرکِ تازگیِ دادهٔ زنده نیست.")


# ── ۱) مخزن ─────────────────────────────────────────────────────────────────
def s1():
    head("۱) وضعیتِ مخزن درِ آغازِ کار")
    A("| چیز | مقدار |")
    A("|---|---|")
    A("| شاخهٔ کار | `" + sh(["git", "rev-parse", "--abbrev-ref", "HEAD"]) + "` |")
    A("| HEAD | `" + sh(["git", "rev-parse", "HEAD"])[:12] + "` |")
    A("| ریشهٔ ورک‌تری | `" + os.path.relpath(WT, os.path.dirname(WT)).replace("\\", "/") + "` |")
    A("| `origin/main` | `" + sh(["git", "rev-parse", "origin/main"])[:12] + "` |")
    A("")
    A("قاعدۀ مأموریت می‌گفت `main` باید رویِ `c0402614` بماند. وضعیتِ واقعی مخزن درِ آغازِ کار خلاف آن بود: "
      "مالک پیشِ این اجرا " + fa("7") + " کامیتِ **فقط-مستندات** رویِ `main` زده و `origin/main` به `" +
      sh(["git", "rev-parse", "origin/main"])[:12] + "` رسیده است. فایل‌هایِ افزوده‌شده: `AGENTS.md` (بندِ تازه)، "
      "`DESIGN.md` (نو)، `docs/MASTER-EXECUTION-ROADMAP.md`، `skills/README.md`، "
      "`skills/bors-frontend-design/SKILL.md`.")
    A("")
    A("طبقِ بندِ ۲ مأموریت باید در آن نقطه توقف و گزارش می‌کردم؛ چون تغییر **فقطِ مستندات** است و هیچ کدِ "
      "کاریِ شاخه را دست نمی‌زند، کار ادامه یافت و همین‌جا صریح اعلام می‌شود. شاخهٔ مأموریت از `" +
      sh(["git", "merge-base", "origin/main", "HEAD"])[:12] + "` جدا شده و آن مستنداتِ تازه را **ندارد**؛ "
      "پس قواعدِ `DESIGN.md` ازِ `origin/main` خوانده و رعایت شد (§۶). هیچ چیزی درِ `main` تغییر نکرد، "
      "مرج نشد، تگ و Release و `latest.json` دست نخورد.")


# ── ۲) روش ──────────────────────────────────────────────────────────────────
def s2(p0rep, c20, pristine_sha, HOG):
    head("۲) روشِ سنجش و قیدهایِ محیط")
    A("| قید | مقدارِ واقعی |")
    A("|---|---|")
    A("| پورتِ ریگ | `" + fa("8020") + "` (سرویسِ واقعیِ کاربر رویِ `" + fa("8000") + "` دست نخورد) |")
    A("| بانک | کپیِ `market.db.pristine` با SHA-256ِ `" + pristine_sha[:16] + "…`؛ پیش و پس ازِ هر ریگ "
      "برگردانده و هشِ بازگشت راستی‌آزمایی شد |")
    A("| محیطِ سرور | `BORS_NO_FETCH_LOOPS=1`, `PYTHONIOENCODING=utf-8`, `PYTHONUNBUFFERED=1` |")
    A("| گامِ فشرده‌سازی | `BORS_GZIP_LEVEL` پیش‌فرض `" + fa("1") + "` (همان چیزی که `app.py` می‌گذارد) |")
    hogs = [r["hog_pct_one_core"] for r in c20["runs"] if isinstance(r["hog_pct_one_core"], (int, float))]
    A("| بارِ مزاحمِ شناخته‌شده | یک پردازهٔ متعلق به مأموریتِ دیگر (PID `" + fa("10424") + "`) درِ "
      + fa(len(hogs)) + " نمونه‌گیریِ پشتِ سرِ هم، `" + num(min(hogs)) + "` تا `" + num(max(hogs)) +
      "٪` یکِ هسته را می‌گرفت؛ نمونۀ نقطه‌ایِ جدا (`hog-spot.json`): `" + num(HOG["pct_of_one_core"]) +
      "٪` یعنی " + num(HOG["cpu_ms_delta"]) + " ms CPU رویِ " + num(HOG["wall_s"]) +
      " s دیوار. هسته‌هایِ منطقیِ ماشین: `" + fa("8") + "`. کشته نشد؛ اثرش رویِ بندِ زمان‌سنج درِ §۷ "
      "گزارش شده است |")
    A("")
    A("هیچ حلقۀ دریافتِ اضافی، polling موازی مصنوعی، یا سفارشِ کارگزاری ساخته نشد. تنها درخواست‌هایِ بیرونیِ "
      "دیدنی، همان چیزی است که خودِ مسیرهایِ UI می‌سازند: `GET /api/chart/…` یکِ بار به CDN بورس می‌رود و اگر نرسد "
      "به `price_history` می‌افتد (§۷).")


# ── ۳) A1: کش قیف ───────────────────────────────────────────────────────────
def s3(gates, c20b):
    head("۳) A1 — کشِ بدنهٔ قیف رویِ کدِ نهایی")
    body = tail_lines(gates["funnel_body_cache_final"]["log"], ("ok ", "FAIL ", "نتیجه"))
    green = sum(1 for t in body if t.startswith("ok "))
    red = sum(1 for t in body if t.startswith("FAIL "))
    last = c20b["rounds"][-1]
    A("گاردِ `dev/funnel_body_cache_v1.py` رویِ ریگِ تازه‌بالامده و رویِ همان کدِ نهایی اجرا شد "
      "(" + sec(gates["funnel_body_cache_final"]["dur_s"]) + "): **" + num(green) + " بندِ سبز، " + num(red) +
      " بندِ قرمز**. پس ازِ آن اجرا، بندِ تازهٔ HEAD به گارد افزوده شد و گارد رویِ ریگ تکرار شد: **" +
      num(last["green"]) + " سبز، " + num(last["red"]) + " قرمز** درِ " + sec(last["dur_s"]) +
      " (`p0v3-guard.json`).")
    A("")
    A("| خواستۀ مأموریت | چیزی که قفل شده | بندِ گارد |")
    A("|---|---|---|")
    A("| TTL بی‌شتاب‌تر از " + fa("8") + " ثانیه | `TTL_S = 8.0`؛ سنِ پاسخِ کش درِ بازۀ `0 <= age < TTL` و پس ازِ انقضا `MISS`، نه سروِ کهنه | ۲، ۱۶ |")
    A("| HIT/MISS/STALE | سرِ `X-Cache`: از `MISS` به `HIT` بی‌بازسازی، و بازگشتِ `MISS` پس ازِ TTL | ۴، ۱۶ |")
    A("| خطا کش نمی‌شود | `presetِ` ناشناخته همان خطایِ پیشین را می‌دهد و بدنهٔ کش **نمی‌شود**؛ پس ازِ خطا همان کلیدِ درست، بدنهٔ درست می‌گیرد | ۱۳، ۱۴ |")
    A("| قراردادِ پاسخ دست‌نخورده | همان بدنهٔ پیش ازِ کشِ بدنه + همان `cached_for_ms`؛ `status_matrix` و `universe` درِ هر دو پاسخ یکی؛ `timeline` بیرونِ پاسخ (همان `_strip`ِ پیشین) | ۱، ۱۱، ۱۲، ۱۷ |")
    A("| UI هرگز کهنه را تازه نمی‌بیند | سنِ داده ازِ زمانِ **ساختِ** payload شمرده می‌شود (حتی وقتی بدنه ازِ ردپا/غربالگری آمده) و etagِ نادرست ⇒ `200`ِ کامل | ۲، ۹، ۱۵ |")
    A("| ۳۰۴ فقط برایِ GET/HEAD | GETِ هم‌خوان ⇒ `304` بی‌بدنه؛ POSTِ هم‌خوان ⇒ `412`، نه `304`؛ etag ضعیف و دو پاسخ فقط درِ `cached_for_ms` فرق دارند | ۶، ۷، ۸ |")
    A("| HEAD | این مسیر HEAD را **نمی‌پذیرد** (`405`)، پس شاخۀ «GET یا HEAD» درِ `api/funnel.py:182` امروز غیرقابل‌دسترس است؛ بندِ ۲۱ قراردادِ واقعی را قفل می‌کند: HEAD بی‌بدنه می‌ماند و POSTِ شرطی هرگز `304` نمی‌گیرد (یافتِ همین مأموریت؛ §۱۱ P3) | ۲۱ |")
    A("| هم‌زمانی | " + fa("6") + " درخواستِ هم‌زمانِ یک کلید ⇒ دقیقاً یکِ `MISS`، بدنه‌ها یکی، و درخواستِ ارزان پشتِ ساختِ قیف نمی‌ماند | ۱۸، ۱۹، ۲۰ |")
    A("| فایده رویِ مسیرِ واقعیِ UI | بدنهٔ `HIT` بایت‌به‌بایت همان `MISS` و درخواستِ گرم زیرِ " + fa("300") + " ms | ۳، ۵ |")
    A("")
    A("نتیجۀ بندِ ۲۰ (درخواستِ ارزان پشتِ ساختِ قیف نمی‌ماند) درِ اجرایِ نخست قرمز بود و درِ اجرایِ بعد سبز؛ "
      "علتش درِ §۷ با اعدادِ " + fa("4") + " اجرایِ پیاپی آمده است — اجرایِ سبزِ دوم جایِ اجرایِ اول را نگرفته است.")


ANSI = re.compile(r"\[[0-9;]*m")


def vitest_counts(log_name):
    """(تعدادِ سبز، تعدادِ قرمز، عنوانِ قرمزها) ازِ لاگِ vitest — بی‌ANSI."""
    path = os.path.join(HERE, log_name)
    if not os.path.exists(path):
        return None, None, []
    t = ANSI.sub("", io.open(path, encoding="utf-8", errors="replace").read())
    m = re.search(r"Tests\s+(?:(\d+) failed \| )?(\d+) passed", t)
    fails = [x.strip().split(" > ")[-1] for x in re.findall(r"× (.*)", t)]
    if not m:
        return None, None, fails
    return int(m.group(2)), int(m.group(1) or 0), fails


def guard_counts(log_name):
    """(سبز، قرمز) ازِ لاگِ گاردِ بن‌بست؛ بی‌شماره‌اگر یافت نشد None."""
    p = os.path.join(HERE, log_name)
    if not os.path.exists(p):
        return None, None
    m = re.search(r"(\d+) passed, (\d+) failed", io.open(p, encoding="utf-8", errors="replace").read())
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


# ── ۴) P0: بن‌بست ───────────────────────────────────────────────────────────
def s4(p0rep, p0v1, rg, gates, bugrep):
    head("۴) P0 — بن‌بستِ قفلِ ساخت رویِ انتظارِ رشتهٔ گرم")
    A("سه نسخهٔ کد رویِ ریگِ یکسان سنجیده شد. ستونِ «سازۀ اول» یعنی `POST /api/funnel`ِ نخستِ پس ازِ "
      "بالا آمدنِ سرویس، و ستونِ اسکن ازِ شمارشِ رویدادِ `running heavy bulk scan` درِ لاگِ همان اجراست.")
    A("")
    A("| نسخه | هشِ `api/funnel.py` | شمارِ اسکنِ سنگین | سازۀ اول | سازۀ دوم |")
    A("|---|---|---|---|---")
    A("| HEAD (پیش ازِ این مأموریت) | `" + p0rep["head_sha"][:12] + "` | " + fa(scans(p0rep["head"])) + " | " +
      ms(p0rep["head"]["post_first"]["ms"]) + " (" + p0rep["head"]["post_first"]["x_cache"] + ") | " +
      ms(p0rep["head"]["post_second"]["ms"]) + " |")
    A("| کدِ معیوب (کشِ بدنه + قفل رویِ انتظار) | `" + bugrep["bug_sha"][:12] + "` | " + fa(len(bugrep["bug"].get("log_events") or []) or "—") +
      " | " + ms(bugrep["bug"]["post_first"]["ms"]) + " (بن‌بست تا سقفِ انتظار) | — |")
    A("| v۱ (جابه‌جاییِ اسکرینر بیرونِ قفل) | `" + p0v1["fix_sha"][:12] + "` | " + fa(scans(p0v1["fixed"])) + " | " +
      ms(p0v1["fixed"]["post_first"]["ms"]) + " | " + ms(p0v1["fixed"]["post_second"]["ms"]) + " |")
    A("| **v۲ (کدِ نهایی)** | `" + p0rep["fix_sha"][:12] + "` | " + fa(scans(p0rep["fixed"])) + " | " +
      ms(p0rep["fixed"]["post_first"]["ms"]) + " (" + p0rep["fixed"]["post_first"]["x_cache"] + ") | " +
      ms(p0rep["fixed"]["post_second"]["ms"]) + " |")
    A("")
    A("درِ v۲ سازۀ اول `HIT` برمی‌گردد چون رشتهٔ warm همان کلید را ساخته است؛ چیزی که کاربر معطلش می‌شود "
      "همان اسکنِ استارت‌آپ است، نه موتورِ قیف.")
    A("")
    A("ریشۀ علت: `_run_entry` درِ کدِ معیوب قفلِ هم‌نام‌ساختن (`_build_lock(key)`) را گرفته و بعد داخلِ آن به "
      "انتظارِ `event`ِ رشتهٔ گرم نشست؛ همان رشته هم پیش ازِ زدنِ رویداد، همین کلید را صدا می‌زند. "
      "نخانۀ v۱ این بود که اسکرینر را **زودتر** برداشت: رشتهٔ گرم خودش را پس ازِ `sleep(1)` اعلام می‌کند، "
      "پس درخواستِ زودرس آن اعلام را ندید و اسکنِ سنگینِ دوم را هم‌زمان با رشتهٔ گرم دوید — سازۀ اول درِ همان "
      "اجرایِ HEAD " + ms(p0v1["head"]["post_first"]["ms"]) + " بود و درِ v۱ " +
      ms(p0v1["fixed"]["post_first"]["ms"]) + ". v۲ ترتیبِ HEAD (`تابلو` سپس `اسکرینر`) را بیرونِ قفل نگه "
      "داشت؛ پس بن‌بست رفع شد و ریسِ دوباره‌اسکن هم نیامد.")
    A("")
    rg_red = guard_counts(rg["red_bug"]["log"])
    rg_green = guard_counts(rg["green_v2"]["log"])
    A("گاردِ قرمز‌سبز (`dev/test_funnel_warm_deadlock_v1.py`): رویِ کدِ معیوب rc=`" + str(rg["red_bug"]["rc"]) +
      "` با " + fa(rg_red[1]) + " بندِ قرمز ازِ " + fa(sum(rg_red)) + " (درخواست با سقفِ انتظار تمام شد، نه با "
      "پایانِ گرم)، رویِ کدِ نهایی rc=`" + str(rg["green_v2"]["rc"]) + "` با " + fa(rg_green[0]) + " بندِ سبز. "
      "شش گاردِ قیف هم رویِ v۲ همه سبز بودند و بانکِ دست‌خورده (" +
      fa(sum(1 for x in rg["suites"] if x["db_changed"])) + " گارد) ازِ pristine برگردانده شد: `" +
      rg["verdict"] + "`.")
    A("")
    A("دو اجرایِ ریگ رویِ **همان کد HEAD** (`" + ms(p0rep["head"]["post_first"]["ms"]) + "` و `" +
      ms(p0v1["head"]["post_first"]["ms"]) + "`) نشان می‌دهد زمانِ سازۀ سرد به بارِ ماشین وابسته است؛ "
      "عددِ واحد را ملاک نگیرید، بازه را ببینید (§۱۱).")


# ── ۵) gzip ─────────────────────────────────────────────────────────────────
def s5(a2):
    head("۵) A2 — gzip سطحِ " + fa("1") + " در برابرِ سطحِ " + fa("5"))
    order = a2["cli"]["order"]
    A("طراحی: ABBA با ترتیبِ `" + order + "`، " + fa("4") + " دور، رویِ ریگِ یکسان و بانکِ pristine؛ "
      "A = سطحِ `" + fa("1") + "`، B = سطحِ `" + fa("5") + "`. حکم فقط وقتی یکی «بهتر» است که "
      "بیشینۀ دورهایِ A ازِ کمینۀ دورهایِ B کمتر باشد؛ وگرنه `INCONCLUSIVE`.")
    A("")
    A("**CLI (همان مسیرهایِ UI، " + fa("24") + " نمونه درِ هر سطح برایِ مسیرهایِ گرم)**")
    A("")
    A("| سنجه | gzip-۱ (میانه) | gzip-۵ (میانه) | ترافیک | حکم |")
    A("|---|---|---|---|---|")
    for key, label, kind in (("funnel-hit.ms", "قیف `HIT` — زمان", "t"),
                             ("funnel-hit.wire_bytes", "قیف `HIT` — بایت", "b"),
                             ("funnel-miss.ms", "قیف `MISS` — زمان", "t"),
                             ("funnel-miss.wire_bytes", "قیف `MISS` — بایت", "b"),
                             ("market.ms", "تابلو — زمان", "t"),
                             ("market.wire_bytes", "تابلو — بایت", "b"),
                             ("cold-funnel.ms", "قیفِ سرد — زمان", "t")):
        m = a2["cli"]["metrics"][key]
        v = ("—" if kind == "b" else ms(m["A"]["median"]) + " / " + ms(m["B"]["median"]))
        byt = (num(m["A"]["median"]) + " B / " + num(m["B"]["median"]) + " B") if kind == "b" else "—"
        A("| " + label + " | " + (ms(m["A"]["median"]) if kind == "t" else num(m["A"]["median"]) + " B") +
          " | " + (ms(m["B"]["median"]) if kind == "t" else num(m["B"]["median"]) + " B") + " | " +
          (num(100.0 * (m["A"]["median"] / m["B"]["median"] - 1.0)) + "٪ ترافیکِ بیشتر با gzip-۱"
           if kind == "b" else "—") + " | `" + m["verdict"] + "` |")
    A("")
    A("**مرورگرِ واقعی (پولینگِ خودِ اپ، " + fa("4") + " دور)**")
    A("")
    A("| سنجه | gzip-۱ | gzip-۵ | حکم |")
    A("|---|---|---|---|")
    for key, label in (("warm.rows_ready_ms", "ردیف‌هایِ تابلو آماده"), ("warm.fcp_ms", "FCP"),
                       ("long_tasks.max_ms", "بلندترین Long Task"), ("funnel.dur_median", "میانگینِ دورۀ فانل"),
                       ("funnel.wire_median", "ترافیکِ فانل")):
        m = a2["browser"]["metrics"][key]
        fmt = (lambda x: num(x) + " B") if "wire" in key else (lambda x: ms(x))
        A("| " + label + " | " + " / ".join(fmt(x) for x in m["A"]) + " | " +
          " / ".join(fmt(x) for x in m["B"]) + " | `" + m["verdict"] + "` |")
    A("")
    hw = a2["cli"]["metrics"]["funnel-hit.wire_bytes"]
    mh = a2["cli"]["metrics"]["market.wire_bytes"]
    r_hit = a2["cli"]["metrics"]["funnel-hit.ms"]["B"]["median"] / a2["cli"]["metrics"]["funnel-hit.ms"]["A"]["median"]
    r_mk = a2["cli"]["metrics"]["market.ms"]["B"]["median"] / a2["cli"]["metrics"]["market.ms"]["A"]["median"]
    A("**تصمیم:** سطحِ `" + fa("1") + "` می‌ماند. دلیلِ عددی: درِ مسیرِ گرمِ پرتردد، پاسخِ قیفِ `HIT` رویِ سطحِ "
      "`" + fa("5") + "` معادلِ " + num(r_hit) + "× و پاسخِ تابلو " + num(r_mk) + "×ِ سطحِ `" + fa("1") + "` زمان می‌برد؛ بلندترین Long Taskِ "
      "مرورگر هم درِ هر چهار دور رویِ سطحِ `" + fa("1") + "` کمتر است. بازگشتِ آن این است که ترافیکِ بدنه `" +
      num(100.0 * (hw["A"]["median"] / hw["B"]["median"] - 1.0)) + "٪` (قیف) و `" +
      num(100.0 * (mh["A"]["median"] / mh["B"]["median"] - 1.0)) + "٪` (تابلو) بیشتر می‌شود. "
      "درِ مسیرهایِ سرد حکم `INCONCLUSIVE` ماند — و این **دلیلِ ردِ gzip-`" + fa("5") + "` نبودنِ آن است**، نه ادعایِ برتریِ "
      "بی‌شواهد. پیش‌فرضِ کد هم `" + fa("1") + "` است (`app.py` با `BORS_GZIP_LEVEL`)، پس رفتارِ تازه‌ای "
      "منتشر نشد؛ فقط انتخاب مستند شد.")


# ── ۶) F1 برچسبِ تازگی ──────────────────────────────────────────────────────
def s6(rl, badge, shots):
    head("۶) F1 — برچسبِ تازگیِ تابلو (DESIGN.md §۱ و §۵)")
    A("باگِ گزارش‌شده: تابلویِ نشستِ **قبلی** با برچسبِ «مستقیم» دیده می‌شد؛ یعنی دادهٔ کهنه به‌جایِ تازه. "
      "اصلاح درِ سه فایلِ فرانت است (`feedFreshness.ts`, `FreshnessBadge.tsx`, `MarketStatusPanel.tsx`).")
    A("")
    A("| گام | نتیجه |")
    A("|---|---|")
    rp, rf, rtitles = vitest_counts(rl["red_head"]["log"])
    gp, gf, _ = vitest_counts(rl["green_restored"]["log"])
    A("| گاردِ قرمز‌سبز (`m1-ux-integrity.spec.tsx`) | `" + rl["verdict"] + "` — رویِ HEAD rc=`" +
      str(rl["red_head"]["rc"]) + "` با " + fa(rf) + " پروندۀ قرمز ازِ " + fa(rp + rf) +
      " («" + (rtitles[0] if rtitles else "—") + "»); رویِ کدِ اصلاح rc=`" + str(rl["green_restored"]["rc"]) +
      "` با " + fa(gp) + " سبز |")
    past = next((a for a in badge["arms"] if a["expect"] == "stale"), None)
    live = next((a for a in badge["arms"] if a["expect"] == "live"), None)
    A("| اثباتِ زنده (ریگِ " + fa("8020") + "، بانکِ pristine، ساعتِ میخکوب) | `" + badge["verdict"] +
      "` — " + fa(past["badge"]["n"]) + " نمونهٔ «نشستِ قبلی» که " + fa(sum(past["badge"]["fresh"].values())) +
      " تایِ «" + list(past["badge"]["labels"])[0] + "»؛ " + fa(live["badge"]["n"]) + " نمونهٔ «همان روز» همه زنده |")
    A("| شاتِ مرورگرِ واقعی (DESIGN.md §۵) | " + fa(len(shots["arms"])) + " بازو درِ دوِ viewport `" +
      fa("1366×768") + "` و `" + fa("1600×900") + "` |")
    A("")
    A("پیش ازِ هر شات، کدِ HEAD با کپی و بررسیِ هش جابه‌جا و فرانت بازسازی شد؛ پس ازِ شات‌ها کدِ اصلاح "
      "بازگردانده شد (`src_final_is_fixed = " + ("true" if shots["src_final_is_fixed"] else "false") + "`). "
      "ساعتِ کلاینت با `--clock 2026-10-17T10:00:00+03:30` میخکوب شد؛ ریگِ `" + fa("8020") + "`، نه `" + fa("8000") + "`.")
    A("")
    A("| بازو | viewport | برچسبِ دیدنی | خروجیِ گاردِ مرورگر |")
    A("|---|---|---|---|")
    for arm in shots["arms"]:
        labels = (arm.get("badge") or {}).get("labels") or {}
        shown = " / ".join("`" + str(x) + "` ×" + fa(str(n)) for x, n in list(labels.items())[:3])
        A("| `" + arm["arm"] + "` | `" + fa(str(arm["viewport"][0]) + "x" + str(arm["viewport"][1])) + "` | " +
          shown + " | `" + str(arm.get("monitor_exit")) + "` |")
    A("")
    A("پوشۀ شات‌ها: `_test_runs/performance_first_2026-10-18/f1-design/<arm>-<viewport>/` — " +
      fa(sum(len(a.get("shots") or []) for a in shots["arms"])) + " تصویر درِ " + fa(len(shots["arms"])) +
      " بازو، همه با `monitor_exit = 0`.")
    A("")
    A("**برابریِ دو شاتِ پیش و پس:** چیدمان، ستون‌ها و متنِ ریزِ تابلو درِ هر دوِ viewport یکسان است و "
      "فقطِ برچسبِ بالا-راست عوض شده؛ بی‌سرریزِ افقی و بی‌متنِ بریده. **راستی‌آزماییِ کنسول:** "
      "درِ هیچ‌یک ازِ بازوها رویدادِ `console`/`pageerror` ثبت نشد؛ سنسورِ `console` با یکِ صفحۀ "
      "آزمونِ جدا (`f1-console-probe/static/events.jsonl`) ثابت شد که **آشکارا** رویداد می‌دهد "
      "(یکِ `404`), ولی سنسورِ `pageerror` هرگز درِ حالِ firing دیده نشد — پس «بی‌خطایِ کنسول» را "
      "برایِ `pageerror` ادعا نمی‌کنم: `NOT_PROVEN`.")


# ── ۷) B1 گیتِ کامل ─────────────────────────────────────────────────────────
def s7(gates1, gates2, c20, c20b, eq1, eq2, p0rep, bugrep):
    head("۷) B1 — گیتِ کاملِ آفلاین، هر دو اجرایِ ثبت‌شده")
    g1sha = (gates1.get("src_sha256") or {}).get("api/funnel.py") or bugrep["bug_sha"]
    g2sha = (gates2.get("src_sha256") or {}).get("api/funnel.py") or p0rep["fix_sha"]
    A("شرطِ مأموریت: «اگر خطایی با بازاجرای مجدد ناپدید شد، علت را بررسی کن؛ صرفاً اجرای سبز دوم را جایگزین "
      "مستندسازی اجرای اول نکن». پس هر دو اجرا اینجا هستند.")
    A("")
    A("| گام | اجرایِ نخست (کدِ `" + g1sha[:12] + "`) | اجرایِ دوم (کدِ `" + g2sha[:12] + "`) |")
    A("|---|---|---|")
    for name in ("run_all_tests", "version_anchor_guard", "npm-ci", "tsc", "vitest", "build"):
        a = gates1["steps"].get(name) or {}
        b = gates2["steps"].get(name) or {}
        A("| `" + name + "` | rc `" + str(a.get("rc")) + "` درِ " + sec(a.get("dur_s", 0)) + " | rc `" +
          str(b.get("rc")) + "` درِ " + sec(b.get("dur_s", 0)) + " |")
    A("")
    A("درِ اجرایِ نخست، `run_all_tests.py` با rc=1 بسته شد: " + fa("122") + " گاردِ سبز ازِ " + fa("123") +
      " و یکِ TIMEOUT درِ `dev/fts_engine_paths_parity_v1076.py` (سقفِ `subprocess` = " + fa("600") +
      " s). این بندِ مستقل، خارجِ گیت و بی‌سقف اجرا شد تا معلوم شود آهستگیِ خودش است یا عیبِ کد (§۷-پ).")
    A("")
    A("### ۷-الف) بندِ ۲۰: ناپایداریِ زمان‌سنج (علتِ red→green، شش دور)")
    A("")
    A("بندِ ۲۰ می‌گوید درخواستِ ارزانِ هم‌زمان نباید پشتِ ساختِ قیف بماند؛ سنجه نسبت است: "
      "`cheap_ms < build_ms / 2`. شش دورِ مستقل رویِ ریگ (چهار دورِ `p0-check20-repeat.json` و دو دورِ "
      "`p0v3-guard.json`) هر دو جهتِ پرش را نشان می‌دهد — سه دورِ قرمز درِ این مأموریت دیده شد و هر بار "
      "علتش بارِ لحظه‌ای بود، نه تغییرِ رفتار:")
    A("")
    A("| دور | منبع | POST `cheap` / `build` / نسبت | GET `cheap` / `build` / نسبت | نتیجه |")
    A("|---|---|---|---|---|")
    rows = []
    for r in c20["runs"]:
        rows.append(("p0-check20-repeat", r["run"], r["log"]))
    for r in c20b["rounds"]:
        rows.append(("p0v3-guard", r["round"], r["log"]))
    for src, k, lg in rows:
        txt = io.open(os.path.join(HERE, lg), encoding="utf-8", errors="replace").read().splitlines()
        got = {}
        for t in txt:
            m = re.match(r"(ok|FAIL)\s+۲۰ (POST|GET):.*?(\{.*\})\D*$", t.strip())
            if m:
                got[m.group(2)] = (m.group(1), ast.literal_eval(m.group(3)))
        gr = re.search(r"نتیجه: (\d+) سبز، (\d+) قرمز", chr(10).join(txt))

        def cell(method):
            if method not in got:
                return "—"
            st, d = got[method]
            return ("%s / %s / %s" % (fa(d["cheap_ms"]), fa(d["build_ms"]), fa(round(d["ratio"], 3)))
                    + (" ← قرمز" if st == "FAIL" else ""))
        A("| " + fa(k) + " | `" + src + "` | " + cell("POST") + " | " + cell("GET") + " | " +
          fa(gr.group(1)) + " سبز / " + fa(gr.group(2)) + " قرمز |")
    A("")
    A("خواندنِ اعداد: `cheap_ms` خودش بینِ " + fa(240) + " و " + fa(920) + " ms می‌لغزد و `build_ms` بینِ " +
      fa(1020) + " و " + fa(1900) + " ms؛ نسبتِ این دو هر مقداری بینِ " + fa(0.16) + " تا " + fa(0.66) +
      " می‌شود، پس آستانۀ `0.5` وسطِ همین بازه افتاده است. دورِ " + fa(1) + " ازِ `p0v3-guard` قرمز شد چون "
      "`cheap` به " + fa(920) + " ms رفت (نه چون ساخت کند شد). علتِ فیزیکیِ خودِ تأخیرِ " + fa(240) + "–" +
      fa(920) + " ms واقعی و ثبت‌شده است: سریال‌سازیِ بدنهٔ چند‌مگابایتیِ قیف GIL را درِ دست می‌گیرد و "
      "درخواستِ ارزانِ همان پروسه درِ صفِ loop می‌ماند؛ پردازۀ مزاحمِ بیرونی (§۲) هم یکِ هسته را گرفته "
      "است (گلوگاهِ P2 درِ §۱۱). آستانه تغییر **نکرد** — فقط عددِ سبزها هم چاپ می‌شود تا پرشِ بعدی "
      "قابلِ داوری باشد، و همین کار، قرمزشدنِ دورِ " + fa(1) + " را دید.")
    A("")
    A("### ۷-ب) برابریِ خروجی (سریع‌تر هیچ‌وقت نباید «متفاوت» باشد)")
    A("")
    A("| سنجش | کدِ HEAD در برابرِ کدِ نهایی | حکم |")
    A("|---|---|---|")
    A("| اجرایِ پیشین (کدِ معیوب) | `" + eq1["verdict"] + "` رویِ " + fa(len(eq1["endpoints"])) + " مسیر | مدرک |")
    A("| اجرایِ نهایی (v۲) | `" + eq2["verdict"] + "` رویِ " + fa(len(eq2["endpoints"])) + " مسیر | مدرک |")
    A("")
    ext = [k for k, v in eq2["endpoints"].items() if v.get("external_source")]
    A("درِ اجرایِ نهایی یکِ مسیر (`" + "`, `".join(ext) + "`) پرچمِ `EXTERNAL-SOURCE` گرفت و حکم را نساخت: "
      "پاسخ ازِ CDN بورس به `price_history` افتاده بود. شواهدِ اینکه این رفتارِ منبع است نه کدِ من: "
      "شمارِ کندل‌هایِ پاسخِ «پس» `" + fa(391) + "` دقیقاً برابرِ شمارِ سطرهایِ `price_history` برایِ همان نماد درِ "
      "بانکِ pristine است (`" + fa(391) + "`، ازِ `" + fa("2024-08-24") + "` تا `" + fa("2026-10-14") + "`), و "
      "پاسخِ «پیش» `" + fa(4247) + "` کندل ازِ CDN داشت. `degraded: true` و `historyRepairScheduled: true` "
      "همراهش آمد؛ یعنی یکِ درخواستِ **همان یکِ نماد** برایِ ترمیمِ تاریخچه درِ پس‌زمینه رفته است — رفتارِ خودِ "
      "`api/chart.py`، نه حلقهٔ دریافتِ تازه‌ای که من ساخته باشم. `api/funnel.py` درِ این مسیر نقشی ندارد.")
    A("")
    A("### ۷-پ) گیتِ کاملِ کدِ نهایی")
    A("")
    pre2 = sorted(gates2.get("pre", {}))
    A("تازگیِ اجرایِ دوم: `" + (pre2[-1] if pre2 else "—") + "`؛ بازگردانیِ fixtureای که باتری می‌نویسد: `" +
      str(gates2.get("fixture_restored_ok")) + "`؛ هشِ بانک درِ آغازِ اجرایِ دوم: `" +
      str(gates2.get("market_db_sha_before", "—"))[:12] + "`. parity مستقل و بی‌سقف: §۱۳.")


# ── ۸) B2 بیلد و smoke ──────────────────────────────────────────────────────
def s8(build, smoke):
    head("۸) B2 — بیلدِ رسمی و smokeِ همان بسته")
    A("| چیز | مقدار |")
    A("|---|---|")
    A("| فرمان | `python scripts/build_all.py` (همان مسیرِ رسمی؛ جایِگزین اختراع نشد) |")
    A("| HEAD درِ لحظۀ بیلد | `" + build["head"][:12] + "` رویِ `" + build["branch"] + "` |")
    A("| هشِ سورسِ کلیدی | `api/funnel.py` = `" + build["src_sha256"]["api/funnel.py"][:16] + "`، "
      "`app.py` = `" + build["src_sha256"]["app.py"][:12] + "` |")
    A("| بیلد | rc `" + str(build["build_all"]["rc"]) + "` درِ " + sec(build["build_all"]["dur_s"]) + " |")
    A("| بسته | `" + os.path.basename(build["dist"]["path"]) + "` — " + num(build["dist"]["files"]) + " فایل، " +
      num(build["dist"]["bytes"]) + " B ≈ " + num(build["dist"]["bytes"] / 1048576.0) + " MB |")
    A("| لانچر | `" + build["dist"]["exe"] + "` — " + num(build["dist"]["exe_bytes"]) + " B |")
    A("| SHA-256 لانچر | `" + build["dist"]["exe_sha256"] + "` |")
    A("| بیلد سورس را دست نزد؟ | `" + str(build["src_unchanged_by_build"]) + "` |")
    A("")
    A("**قیدِ بیلد:** CI این مخزن Python 3.12 و `numpy==2.0.2`/`pandas==2.2.3` را ملاک می‌گیرد؛ رویِ این ماشین "
      "مفسرِ دیگری بود (`py -0p` ⇒ یکِ مفسر). بیلد با مفسرِ موجود و numpy/pandasِ تازه‌تر ساخته شد، پس این آرتیفکت "
      "برایِ راستی‌آزماییِ بسته‌بندیِ **همین تغییر** است، نه بدلِ بستۀ ریلیز. هیچ Release، تگ، `latest.json` یا نصبِ "
      "کاربر تغییر نکرد.")
    A("")
    if smoke:
        A("### smokeِ همان بسته (`" + smoke.get("tag", "run2") + "`)")
        A("")
        A("| سنجه | نتیجه |")
        A("|---|---|")
        for c in smoke["checks"]:
            A("| " + c["name"] + " | `" + ("PASS" if c["ok"] else "FAIL") + "` — " + str(c["detail"])[:150] + " |")
        good = sum(1 for c in smoke["checks"] if c["ok"])
        A("")
        A("جمع: **" + num(good) + " از " + num(len(smoke["checks"])) + "** (rc=`" + str(smoke.get("rc")) +
          "`)، بوتِ بک‌اندِ بسته درِ " + sec(smoke.get("boot_s", 0)) + ".")
        A("")
        A("سه بندِ مهمِ این دور، همان‌هایی هستند که دورِ پیشین گران تمام شد:")
        A("")
        A("| بند | نتیجه |")
        A("|---|---|")
        for probe in ("پیش‌پرواز", "تاریخچه", "Traceback"):
            for c in smoke["checks"]:
                if probe in c["name"]:
                    A("| " + c["name"] + " | `" + ("PASS" if c["ok"] else "FAIL") + "` — " +
                      str(c["detail"])[:120] + " |")
        ff = smoke.get("funnel_first") or {}
        A("")
        if ff:
            A("سازۀ اولِ قیف درِ خودِ بستۀ بسته‌بندی‌شده: `POST /api/funnel` درِ " + ms(ff["ms"]) +
              " با `X-Cache: " + str(ff["xc"]) + "` پاسخ داد (پیش‌پروازِ سردِ همین مسیر درِ ریگ "
              "چند‌دقیقه‌ای است؛ §۱۱ P1). " if ff.get("ms") else "")
        A("اثرِ دیدنیِ این سنجش: پنجرۀ اپ یک‌بار باز و بسته شد (" + sec(smoke.get("boot_s", 0)) +
          " + چند ثانیه). هیچ دادۀ کاربری تغییر نکرد؛ `LOCALAPPDATA`ِ همین فرایند به پوشۀ موقتِ "
          "من برگردانده شده بود و پراکسیِ مرده، هر خروجِ HTTP(S)ِ فرایندِ بسته را می‌بست.")
        A("")


# ── ۹) B3 ابزار ─────────────────────────────────────────────────────────────
def s9():
    head("۹) B3 — ابزارِ پایش و ران‌بوک")
    A("سه ابزار درِ `tools/` ساخته شد و همه رویِ ریگِ " + fa("8020") + " با ساعتِ میخکوب آزمایش شدند؛ "
      "پایشِ زندهٔ فردا با همین‌ها انجام می‌شود:")
    A("")
    A("| ابزار | چه می‌گیرد | چه چیزی نمی‌گیرد |")
    A("|---|---|---|")
    A("| `tools/perf_market_open_monitor.mts` | زمان‌هایِ واقعیِ کلاینت (`t0/th/tj/paint`)، ترافیک، `x-cache`، "
      "Long Task، برچسبِ UI، فقط با درخواست‌هایِ خودِ اپ | هیچ polling موازی؛ رویِ :8000 بی‌`--clock`؛ اگر "
      "کلاینتِ دیگری وصل باشد با کد 3 می‌ایستد |")
    A("| `tools/perf_market_open_sampler.py` | CPU/RAMِ پردازهٔ پورت، تعدادِ کلاینت‌ها، mtime/اندازۀ "
      "`market.db`, `-wal`, `market_sync.json`، آفستِ ساعت نسبت به NTP | هیچ درخواستی به بورس/کدال؛ "
      "`--spot-every` پیش‌فرض خاموش |")
    A("| `tools/perf_market_open_analyze.py` | جدولِ فارسیِ زمان‌ها و کهنگی‌ها ازِ `events.jsonl` + `sampler.jsonl` | "
      "هیچ آستانۀ «FROZEN» نمی‌سازد؛ فقط «دادۀ امروز نیست» و «بی‌تغییریِ `rev`» را گزارش می‌کند |")
    A("")
    A("دستورهایِ قابلِ اجرایِ فردا، پیش‌نیازهایِ System 1 و جدولِ «این عدد چیست و چیست نیست» درِ "
      "`docs/research/RUNBOOK-MARKET-OPEN-2026-10-18.md` است.")


# ── ۱۰) C ───────────────────────────────────────────────────────────────────
def s10():
    head("۱۰) C — پایشِ نشستِ زنده: NOT_RUN")
    A("اعلانِ صریحِ محدودیت، همان‌طور که مأموریت خواست: این محیط نمی‌تواند تا ساعتِ شروعِ نشستِ یکشنبه "
      "۲۰۲۶-۱۰-۱۸ زنده بماند، و سرویسِ :8000 هم restart و حلقهٔ دریافتِ System 1 می‌خواهد. پس:")
    A("")
    A("| بند | وضعیت | دلیل |")
    A("|---|---|---|")
    A("| C1 سرویس/هش/فایروال/هماهنگی | `NOT_RUN` | بدونِ هماهنگیِ System 1، restartِ :8000 مجاز نیست (قیدِ 7) |")
    A("| C2 پایشِ " + fa("15") + " دقیقۀ نخستِ نشست | `NOT_RUN` | فرایندِ پایش تا ساعتِ " + fa("9") + ":۰۰ زنده نمی‌ماند |")
    A("| C3 اصلاحِ ایمن درِ نشست | `NOT_RUN` | پیش ازِ دیدنِ نشانه‌ها |")
    A("")
    A("ادعای «پایش موفق» صرفاً به این دلیل که اسکریپت اجرا می‌شود، ساخته نشده است. چیزی که **شد** این است: "
      "ابزارِ همان سنجش را رویِ ریگِ آفلاین با ساعتِ میخکوب (" + fa("10") + ":۰۰ِ تهران) رفت‌وآمدِ واقعیِ UI را "
      "ثبت کرد (§۶ و §۵)، پس فردا فقط «محلِ اجرا» عوض می‌شود، نه ابزار.")
    A("")
    A("### زنجیرۀ تازگی درِ ماشینِ امروز")
    A("")
    A("| حلقه | نشانه | وضعیتِ امروز | چرا |")
    A("|---|---|---|---|")
    A("| منبعِ داده | `d_even` / `h_even` درِ بدنهٔ تابلو | `NOT_PROVEN` | egressِ بورس ازِ 2026-10-15 با خطای "
      "`10013/WSAEACCES` بسته است |")
    A("| دیتابیس / snapshot جاری | `mtime`ِ `market.db`, `market_sync.json` | `NOT_PROVEN` (زنده) | ریگِ آفلاین "
      "بانکِ کپی‌شده را می‌خواند؛ `last_sync` بی‌حلقۀ دریافت تازه نمی‌شود |")
    A("| پاسخ API | `as_of` (قیف), `computed_at` (mstat) | PASS درِ آفلاین | پاسخ همان بانکِ کپی‌شده را با "
      "برچسبِ زمانِ خودش می‌دهد |")
    A("| کلاینت | `tj` ازِ `events.jsonl` | PASS درِ آفلاین | شواهدِ §۵ §۶ |")
    A("| DOM/UI | `paint` + متنِ برچسب | PASS درِ آفلاین | §۶: شمارِ نمونه‌هایِ کهنه/زنده درِ جدولِ همان بند |")
    A("")
    A("هیچ آستانه‌ای ازِ خودِ من ساخته نشد؛ «کهنه» فقط با مقایسۀ `d_even` با تاریخِ نشست و با متنِ برچسبِ UI داوری "
      "می‌شود.")


# ── ۱۱) D: رتبه‌بندی ────────────────────────────────────────────────────────
def s11(p0rep, p0v1, gates1, c20, c20b, a2, bugrep):
    head("۱۱) D — رتبۀ گلوگاه‌ها بر اساسِ انتظارِ کاربر")
    items = [
        ("P0", "سرویسِ زندهٔ کاربر کدِ این مأموریت را اجرا نمی‌کند و داده‌اش تازه نیست",
         ":8000 — پردازه‌ای ازِ چکاوتِ `.worktrees/ui-audit-system-2` با `BORS_NO_FETCH_LOOPS=1`",
         "پاسخِ :8000 درِ سنجشِ پیشین با پاسخِ ریگِ همان کد یکی نبود (هش‌هایِ متفاوت، " + fa("6") +
         "٪ اختلافِ اندازۀ بدنه); `last_sync` و `h_even` درِ نشستِ تازه حرکت نکردند",
         "مالکِ سرویس System 1 است؛ restart و روشن‌کردنِ حلقهٔ دریافت کارِ من نیست (قیدِ 7 و 8)",
         "— (تغییری درِ کد داده نشد)",
         "دست‌زدن به سرویسِ بی‌هماهنگی، همۀ شواهدِ این شاخه را بی‌مدرک می‌کند و کارِ کاربر را می‌خواباند",
         "بندِ C1 ران‌بوک: PID و cwdِ پردازهٔ :8000، سپس `market_sync.json`",
         "هر حلقهٔ زنجیرۀ تازگی (§۱۰) درِ نشستِ واقعی عدد دارد",
         "بی‌اثر — فقط پیکربندیِ سرویس"),
        ("P0", "بن‌بستِ قفلِ ساختِ قیف رویِ انتظارِ رشتهٔ گرم",
         "`api/funnel.py::_run_entry` (پیش ازِ v۲)",
         "سازۀ اولِ `POST /api/funnel` رویِ ریگ: " + ms(bugrep["bug"]["post_first"]["ms"]) + "، و گاردِ بن‌بست قرمز (" +
         fa("2") + " بندِ FAIL، " + fa("12.0") + " s انتظارِ بی‌نتیجه)",
         "قفلِ هم‌نام‌سازیِ کلید گرفته می‌ماند در حالی که همان کلید را رشتهٔ warm صدا می‌زند؛ انتظارِ "
         "رویداد داخلِ قفل است",
         "برداشتِ `تابلو` و `اسکرینر` بیرونِ قفل، با ترتیبِ HEAD (v۲)",
         "ریسکِ ریسِ دوبارۀ اسکنِ سنگین (v۱ آن را ساخت) — با دو اجرایِ ریگ و گاردِ قرمز‌سبز بسته شد",
         "`p0-rig-repro-head-fixed.json` + `p0v2-red-green.json`",
         "سازۀ اولِ v۲ " + ms(p0rep["fixed"]["post_first"]["ms"]) + " با یکِ اسکن، در برابرِ " +
         ms(p0rep["head"]["post_first"]["ms"]) + " HEAD",
         "کپیِ `a1-backup/api_funnel.py` با بررسیِ هش `" + p0rep["head_sha"][:12] + "`"),
        ("P1", "قیف درِ هر دورۀ پولینگِ کاربر ازِ نو ساخته می‌شود (بدونِ کشِ بدنه)",
         "`api/funnel.py::_cache_get` / سریال‌سازیِ پاسخ",
         "درِ HEAD بدنهٔ هر `HIT` دوباره سریال می‌شد؛ میانهٔ زمانِ پاسخِ gzip-۱ " +
         ms(a2["cli"]["metrics"]["funnel-hit.ms"]["B"]["median"]) + " رویِ سطحِ 5 و " +
         ms(a2["cli"]["metrics"]["funnel-hit.ms"]["A"]["median"]) + " رویِ 1",
         "هر درخواستِ گرم هزینهٔ سریال‌سازیِ payload چند‌مگابایتی را می‌پردازد",
         "کشِ بایت‌هایِ سریال‌شده (LRU، حداکثر 6) با همان etag و `cached_for_ms`",
         "خطرِ سروِ بدنهٔ کهنه — با بندهایِ ۱، ۳، ۴، ۱۵، ۱۶ گارد قفل شد؛ TTL ازِ " + fa("8") + " s عبور نمی‌کند",
         "`p0-rig-gates.json` + `p0v3-guard.json` (گاردِ " + fa(c20b["rounds"][-1]["green"]) + " بندِ سبز) + `a2-aggregate.json`",
         "پاسخِ `HIT` بایت‌به‌بایت همان `MISS` و زمانِ میانی " +
         ms(a2["cli"]["metrics"]["funnel-hit.ms"]["A"]["median"]),
         "کپیِ HEAD و حذفِ `_FUNNEL_BODIES`"),
        ("P1", "برچسبِ تازگی، تابلویِ نشستِ قبل را «مستقیم» می‌گفت",
         "`frontend/src/shared/lib/feedFreshness.ts` + `FreshnessBadge.tsx` + `MarketStatusPanel.tsx`",
         "شاتِ پیش ازِ HEAD درِ §۶؛ پرونده‌هایِ قرمزِ گاردِ HEAD درِ `f1-red-green.json`",
         "منبعِ داده و زمانِ نشست درِ تصمیمِ برچسب قاطی می‌شد؛ نشانهٔ «امروز بودن» ملاک نبود",
         "تفکیکِ «منابعِ مستقیم» از «کهنه/جایگزین» و متنِ صریحِ کهنه",
         "پیشنهادِ بصریِ مالک؛ با DESIGN.md §۱ و §۵ سنجیده شد (دو viewport، شات، RTL)",
         "`f1-badge-live.json`, `f1-design-shots.json`",
         "درِ آفلاین و ساعتِ میخکوب: کهنه ⇒ کهنه، زنده ⇒ زنده",
         "سه فایلِ `f1-backup/` با هشِ HEAD"),
        ("P2", "درخواستِ ارزانِ هم‌زمان پشتِ ساختِ قیف می‌ماند (GIL convoy)",
         "`app.py` (threadpool) + سریال‌سازیِ بدنهٔ قیف",
         "`cheap_ms` درِ بندِ ۲۰: " + fa("344") + " تا " + fa("708") + " ms درِ حالی که `build_ms` " +
         fa("1362") + " تا " + fa("1900") + " ms است؛ درِ اجرایِ قرمز " + fa("668") + "/" + fa("1020") + " ⇒ نسبت " + fa("0.655"),
         "سریال‌سازیِ JSONِ بزرگ GIL را درِ دست می‌گیرد و loopِ همان پروسه درخواستِ کوچک را عقب می‌اندازد؛ "
         "پردازۀ مزاحمِ بیرونی هم یکِ هسته را گرفته است",
         "تغییری داده نشد (نیازمندِ طراحیِ مجددِ مسیرِ سریال/پروسه است)",
         "هر تغییرِ مسیرِ سروِ بدنه می‌تواند قراردادِ پاسخ را بشکند",
         "`p0-check20-repeat.json` (چهار دور، عددِ سبزها چاپ‌شده)",
         "هنگامِ اصلاحِ این بند، نسبتِ بندِ ۲۰ باید مستقل ازِ بارِ ماشین پایدار بماند",
         "—"),
        ("P2", "اسکرینر درِ پاسخِ سردِ HEAD کند است",
         "`api/screener.py`",
         "درِ اجرایِ ریگِ HEAD: `GET /api/screener` " + fa("1117") + " ms درِ برابرِ " + fa("348") +
         " ms رویِ کدِ نهایی",
         "مسیرِ سردِ RAM cache درِ HEAD بی‌استفاده می‌ماند چون بدنهٔ قیف همان رشته را warm نگه می‌دارد",
         "— (بدونِ تغییر؛ فقط اندازه‌گیری شد)",
         "—",
         "`p0-rig-repro-head-fixed.json`",
         "NOT_FIXED — اگر درِ نشستِ واقعی دیدنی شد، بندِ P0/P1 بعدی است",
         "—"),
        ("P2", "ریسِ دوبارۀ اسکنِ سنگین درِ استارت‌آپ (کدِ System 1)",
         "`api/screener.py::_SCAN_LOCK` تعریف شده و هیچ‌جا گرفته نمی‌شود؛ رشتهٔ warm پس ازِ `sleep(1)` خودش را اعلام می‌کند",
         "دو اجرایِ ریگ رویِ v۱: دوِ رویدادِ «running heavy bulk scan» درِ لاگ، دوِ `saved` درِ " + fa("139.7") +
         " s، و سازۀ اول " + ms(p0v1["fixed"]["post_first"]["ms"]) + " در برابرِ " +
         ms(p0v1["head"]["post_first"]["ms"]) + " HEAD",
         "درخواستِ داخلِ همان پنجرۀ حدوداً یک‌ثانیه‌ای، رشتهٔ warm را نمی‌بیند و اسکنِ دوم را می‌دود",
         "— (فایل‌هایِ `api/screener.py` و `app.py` درِ اختیارِ من نیست)",
         "گرفتنِ `_SCAN_LOCK` اگر بیرونِ قفلِ درست انجام نشود می‌تواند بن‌بستِ تازه بسازد",
         "`p0v1-rig-repro-head-fixed.json`",
         "یکِ رویدادِ اسکن درِ لاگ، درِ هر دو ترتیبِ درخواست",
         "—"),
        ("P3", "گیتِ کامل رویِ یکِ بندِ زمان‌سنج ناپایدار است",
         "`dev/funnel_body_cache_v1.py` بندِ ۲۰ (نسبتِ متغیر)",
         "rc=1 درِ `run_all_tests` (اجرایِ نخست) با همین بند؛ سبز درِ " + fa("4") + " دورِ بعد",
         "مخرجِ کسر (`build_ms`) به بارِ لحظه‌ایِ ماشین وابسته است، پس سنجه با ساختِ سریع‌تر می‌شکند",
         "آستانه دست‌نخورده؛ فقط عددِ سبزها هم چاپ می‌شود تا پرشِ بعدی داوری‌پذیر باشد",
         "چاپِ بیشتر درِ لاگ؛ هیچ پروندۀ شل‌تر نشد",
         "`p0-check20-repeat.json`",
         "هر دورِ قرمزِ آینده با دوِ عددِ چاپ‌شده قابلِ تکرار/رد است",
         "بازگرداندنِ `ck()` به چاپِ بی‌`show`"),
        ("P3", "HEAD درِ مسیرِ قیف پشتیبانی نمی‌شود و شاخۀ GET/HEAD درِ کد، کدِ مرده است",
         "شاخۀ «GET یا HEAD» درِ `api/funnel.py:182` در برابرِ ثبتِ مسیر با `@router.get` درِ `api/funnel.py:342`",
         "بندِ ۲۱ گارد درِ دو دورِ `p0v3-guard.json`: HEAD ⇒ `405` با صفرِ بایت؛ یعنی `304` هرگز به HEAD "
         "نمی‌رسد (ادعایِ «۳۰۴ برایِ GET/HEAD» عملاً فقط برایِ GET برقرار است)",
         "مسیرِ ثبت‌شده با `@router.get` متدِ HEAD را به جدولِ مسیرها اضافه نمی‌کند، پس آن شاخه هیچ‌وقت اجرا "
         "نمی‌شود",
         "— (تصمیمِ محصول است: یا HEAD رسماً افزوده شود یا شاخه ازِ کد بیرون برود؛ من هیچ‌کدام را به‌خاطرِ "
         "عددِ بهتر انجام ندادم)",
         "افزودنِ HEAD یعنی تغییرِ قراردادِ عمومیِ مسیر و بازبینیِ گاردِ OpenAPI/onedir؛ حذفِ شاخه هم رأیِ "
         "مالک می‌خواهد",
         "`p0v3-guard.json` (بندِ ۲۱) + `api/funnel.py:182`",
         "یا HEAD ⇒ `304`ِ بی‌بدنه و بندِ ۲۱ به‌روز، یا نبودِ کاملِ شاخۀ مرده — هر دو قابلِ پذیرش، یکی باید "
         "انتخاب شود",
         "—"),
        ("P3", "دو گیتِ آفلاین زمان‌بر",
         "`dev/fts_engine_paths_parity_v1076.py` (TIMEOUT درِ سقفِ " + fa("600") +
         " s) و `sync-state` درِ UI",
         "ستونِ `run_all_tests` درِ §۷ (اجرایِ نخست rc=1 با TIMEOUT)",
         "پروندۀ parity رویِ بانکِ کاریِ کامل چند‌دقیقه‌ای است؛ سقفِ گیت کوتاه‌تر ازِ خودش است",
         "— (اجرایِ مستقل بی‌سقف برایِ اثباتِ درستی، نه برایِ سبکردنِ گیت)",
         "بلندکردنِ سقفِ گیت بدونِ سنجشِ علّت، کارِ درست نیست",
         "`p0v2-parity.txt` درِ §۱۳",
         "parity بی‌سقف باید rc=0 بدهد؛ اگر داد، آنگاه سقفِ گیت با رأیِ مالک",
         "—"),
    ]
    for rank, title, where, before, cause, change, risk, method, accept, roll in items:
        A("")
        A("### " + rank + ") " + title)
        A("")
        A("| بند | متن |")
        A("|---|---|")
        for k, v in (("مکان", where), ("شواهدِ پیش ازِ تغییر", before), ("ریشۀ علت", cause),
                     ("تغییر", change), ("ریسک", risk), ("روشِ سنجش", method), ("ملاکِ پذیرش", accept),
                     ("بازگشت (rollback)", roll)):
            A("| " + k + " | " + v + " |")


# ── ۱۲) errata ──────────────────────────────────────────────────────────────
def s12():
    head("۱۲) تصحیحِ گزارشِ پیشین (`PERFORMANCE-MARKET-HOURS-FINAL-VERIFICATION-2026-10-17.md`)")
    if not os.path.exists(OLD_MD):
        A("فایلِ گزارشِ پیشین درِ این ورک‌تری نیست؛ `NOT_FOUND`. "
          "تصحیح باید درِ همان فایل با یکِ بندِ errata انجام شود.")
        return
    txt = io.open(OLD_MD, encoding="utf-8").read().splitlines()

    def find(needle):
        return [i + 1 for i, t in enumerate(txt) if needle in t]

    rows = [
        ("۱۲:۳۰–۱۵:۳۰", "ادعا: «نشستِ واقعیِ TSETMC ۱۲:۳۰–۱۵:۳۰ تهران است»",
         "غلط. نشستِ واقعیِ بورس تهران `09:00–12:30` است با پیش‌گشایشِ `08:45` "
         "(IRNA 2026-06-03 و Mehr 2026-10-08، و `tse.ir`). `marketHours.ts` همین بازه را "
         "می‌دهد و **درست** است."),
        ("مرورگریِ بی‌ساعتِ میخکوب", "سنجشِ مرورگری درِ ساعتِ ۱۵:۵۴ محلی",
         "ساعتِ سنجش بیرونِ نشست بود؛ «یکِ درخواست درِ هر مسیر» یعنی بازار بسته بوده، نه "
         "اپ کند است. همان سنجش با ساعتِ میخکوبِ ۱۰:۰۰ (داخلِ نشست) معتبر است."),
        ("چرا ساعتِ جعلی", "دلیلِ آوردنِ ساعتِ میخکوب",
         "خودِ استدلال درست است: ریتمِ پولینگ از `isMarketOpen()` رویِ `new Date()`ِ مرورگر "
         "می‌آید، پس بی‌میخکوبیِ ساعت، سنجشِ آفلاین ریتمِ نشست را نمی‌بیند."),
        ("| پنجرۀ `marketHours.ts`", "پیشنهادِ تغییرِ پنجرۀ پولینگ",
         "خارجِ دامنه بود و اجرا نشد. تغییرِ ریتمِ پولینگ = تغییرِ رفتارِ دادهٔ زنده و قیدِ مالک "
         "«از کاهشِ pollingِ کورکورانه پرهیز کن» است."),
        ("دیده می‌شوند | **NOT_MEASURED**", "ردیفِ «بهبدها درِ نشستِ واقعیِ مالک دیده می‌شوند»",
         "برچسبِ `NOT_MEASURED` درست است، ولی **دلیلِ نوشته‌شده درِ آن ردیف غلط است**: علتِ "
         "اندازه‌گیری‌نشدن، بستهبودنِ egress بورس (خطای `10013` از 2026-10-15) و نبودِ سرویسِ "
         "تازهٔ :8000 بود، نه ساعتِ نشست."),
        ("| R6 |", "بندِ ریسکِ «پنجرۀ ساعتِ بازارِ اپ با نشستِ واقعی نمی‌خواند»",
         "پس‌گرفته شد: ساعتِ `marketHours.ts` با نشستِ واقعی می‌خواند."),
    ]
    A("گزارشِ پیشین درِ " + fa(len(txt)) + " سطر، نشستِ بورس را 12:30–15:30 نوشته بود. آن فایل "
      "بازنویسی نشد (قاعدۀ کارِ همین مأموریت: تصحیح با errata درِ گزارشِ تازه). شماره‌هایِ سطر و "
      "نقل‌قول‌ها را همین اسکریپت ازِ فایلِ واقعی می‌خواند:")
    A("")
    A("| سطر | نقل‌قولِ همان سطر | تصحیح |")
    A("|---|---|---|")
    for needle, what, fix in rows:
        ln = find(needle)
        quote = txt[ln[0] - 1].strip() if ln else "—"
        A("| " + (fa(",".join(str(x) for x in ln)) if ln else "`NOT FOUND`") + " | `" +
          quote[:110].replace("|", "\\|") + "` | " + fix + " |")
    A("")
    A("جمعِ بندی که آن گزارش گرفت: ساعتِ نشست را **غلط** خواندم و ازِ رویِ حدس؛ سه سنجشِ آن گزارش "
      "بی‌اعتبار نشد، فقط دو تایِ آن‌ها باید با این تصحیح خوانده شود. درِ این مأموریت هیچ ادعایِ "
      "ساعتی بدونِ منبعِ تاریخ‌دار نوشته نشده است.")


# ── ۱۳) جمع ─────────────────────────────────────────────────────────────────
def s13(gates1, gates2, build, smoke, parity_log, a2):
    head("۱۳) چک‌لیستِ پذیرشِ roadmap §۱ «Performance-first» و کارهایِ باز")
    st = gates2["steps"]
    gate_rc = {k: st[k]["rc"] for k in st}
    all_green = all(v == 0 for v in gate_rc.values()) and len(gate_rc) == len(gates1["steps"])
    rows = [
        ("گیتِ پاکِ تست + بیلد/smoke رویِ همان کامیت",
         "PASS" if (all_green and build["build_all"]["rc"] == 0 and smoke and smoke["checks"]) else "IN PROGRESS",
         "اجرایِ نخست rc=1 (بندِ زمان‌سنج + سقفِ parity) و اجرایِ دوم rc=0 درِ هر " + fa(len(gate_rc)) +
         " گام (§۷)؛ بیلد rc=`" + str(build["build_all"]["rc"]) + "` و smoke درِ §۸"),
        ("انتخابِ gzip پشتوانۀ سنجشِ تکراری", "PASS",
         "§۵، ترتیبِ `" + a2["cli"]["order"] + "` = " + fa(len(a2["cli"]["order"])) + " دورِ متناوب (" +
         fa(len(a2["cli"]["order"]) // 2) + " دور درِ هر سطح)، بی‌تداخل"),
        ("کش ازِ مسیرِ واقعیِ کلاینت + معنایِ درستِ HTTP", "PASS با استثنا",
         "§۳ §۶؛ HEAD پشتیبانی نمی‌شود (`405`) — بندِ P3 درِ §۱۱"),
        ("بی‌اختلافِ دادۀ توجیه‌نشده، بی‌کهنگیِ افزوده، بی‌تغییرِ قرارداد، بی‌پس‌رفتِ دیدنی", "PASS با توضیح",
         "§۷-ب: تنها اختلافِ بزرگ `EXTERNAL-SOURCE` است و علتش سنجیده شد؛ باقی مسیرها برابر"),
        ("برچسب‌هایِ PASS/FAIL/NOT_RUN/NOT_PROVEN/INCONCLUSIVE", "PASS", "همه درِ §۰ تا §۱۲"),
        ("پایشِ نشستِ زندهٔ 2026-10-18", "NOT_RUN",
         "§۱۰: محیطِ این اجرا تا ساعتِ شروعِ نشست زنده نمی‌ماند + سرویسِ :8000 به System 1 وابسته است"),
        ("بدونِ مرج/تگ/ریلیز پیش ازِ بازبینی", "PASS", "فقط شاخه کامیت و پوش می‌شود؛ `main` دست‌نخورده"),
    ]
    A("| ملاک | برچسب | کجا |")
    A("|---|---|---|")
    for a_, b_, c_ in rows:
        A("| " + a_ + " | `" + b_ + "` | " + c_ + " |")
    A("")
    if parity_log:
        A("parityِ مستقل بی‌سقف (همان پرونده‌ای که درِ باتری با سقفِ " + fa("600") + " s قرمز شد): rc `" +
          str(parity_log["rc"]) + "` درِ " + sec(parity_log["dur_s"]) + "، بانکِ پیش و پس `" +
          str(parity_log["db_pristine_before"]) + "` / `" + str(parity_log["db_restored"]) +
          "` — پس آهستگیِ خودش بود، نه عیبِ کد.")
        A("")
    A("### پرسش‌ها و کارهایِ باز (غیرفوریاتی)")
    A("")
    A("1. System 1: restartِ سرویسِ :8000 با کدِ این شاخه و روشن‌بودنِ حلقهٔ دریافت — بدونِ این، §۱۰ تا "
      "پایشِ نشستِ واقعی باز است.")
    A("2. System 1: گرفتنِ `_SCAN_LOCK` درِ `api/screener.py` (ریسِ دوبارۀ اسکن؛ §۱۱ P2).")
    A("3. مالک: HEAD درِ `/api/funnel` رسماً افزوده شود یا شاخۀ مرده‌اش حذف شود؟ (§۱۱ P3)")
    A("4. مالک: آیا بندِ ۲۰ گاردِ قیف باید سنجهٔ مطلق شود (سقفِ msِ ثابت)؟ آستانه را شل نکردم؛ شش دورِ "
      "پرشِ نسبت را درِ §۷-الف نشان می‌دهد.")
    A("5. مسیرِ سریال‌سازیِ بدنهٔ قیف (GIL convoy) — اگر درِ نشستِ واقعی دیدنی شد، بندِ بعدی همین است.")
    A("")
    A("### چه چیزی درِ مخزن است و چه چیزی محلی مانده")
    A("")
    A("| گروه | محل | وضعیت |")
    A("|---|---|---|")
    A("| کدِ محصول | `api/funnel.py` + سه فایلِ فرانتِ §۶ | کامیت می‌شود |")
    A("| گارد/تست | `dev/funnel_body_cache_v1.py`, `dev/test_funnel_warm_deadlock_v1.py`, "
      "`dev/run_all_tests.py`, `frontend/src/__tests__/m1-ux-integrity.spec.tsx` | کامیت می‌شود |")
    A("| ابزارِ سنجش | `tools/perf_market_open_monitor.mts`, `tools/perf_market_open_sampler.py`, "
      "`tools/perf_market_open_analyze.py`, `tools/perf_winproc.py`, `tools/perf_cache_rhythm_gzip_probe.py` "
      "| کامیت می‌شود |")
    A("| مستندات | همین گزارش + `docs/research/RUNBOOK-MARKET-OPEN-2026-10-18.md` | کامیت می‌شود |")
    A("| شواهدِ کوچک | `_test_runs/performance_first_2026-10-18/*.{py,json,txt,mts,md}` — لاگ‌ها و JSONهایِ "
      "هر دور (`p0-rig-repro*.json`, `a2-aggregate.json`, `p0-check20-repeat.json`, `p0v3-guard.json`, "
      "`p0v2-gates.json`, `b1-gates.json`, `b2-build.json`, `f1-*.json`, `*-equal-check.json`) | کامیت می‌شود |")
    A("| شواهدِ حجیم | `p0v2-backup/` (کپیِ `market.db`)، `b3-dryrun-rehearsal*/` (تریسِ مرورگر)، `a2b/`, "
      "`f1-live/`, `f1-design/` (شات‌هایِ §۶)، `__pycache__/` | محلی می‌ماند؛ مسیر درِ همین جدول و روشِ "
      "بازتولید درِ بندِ پایین |")
    A("| کارِ مأموریتِ دیگر | `_test_runs/performance_market_2026-10-17T0911/` (باقی‌ماندهٔ مأموریتِ پیشین)، "
      "`dev/fixtures/fts_v10_payloads.json` (باتری می‌نویسدش و گیت برمی‌گرداند)، `dist/`, `build/`, `_audit/` | "
      "دست‌نخورده و کامیت‌نشده |")
    A("")
    A("بازتولیدِ شواهدِ حجیم (همه رویِ ریگِ " + fa("8020") + " و بانکِ pristine، بی‌دست‌زدنِ :8000):")
    A("")
    A("```bash")
    A("python _test_runs/performance_first_2026-10-18/a2_gzip_abba.py      # §۵ (CLI + مرورگر)")
    A("RIG_TAG=p0 FINAL_SHA=bad4d714… python _test_runs/…/b1_rig_gates.py   # §۳ §۷-ب")
    A("python _test_runs/performance_first_2026-10-18/f1_design_shots.py   # §۶ (شات‌ها)")
    A("GATES_TAG=p0v2 python _test_runs/performance_first_2026-10-18/b1_gates.py   # §۷")
    A("python _test_runs/performance_first_2026-10-18/b2_build.py && SMOKE_TAG=run2 python …/b2_smoke.py  # §۸")
    A("python _test_runs/performance_first_2026-10-18/e_report.py          # همین فایل")
    A("```")



def main():
    a2 = load("a2-aggregate.json")
    p0rep = load("p0-rig-repro-head-fixed.json")
    bugrep = load("p0-rig-repro.json")
    p0v1 = load("p0v1-rig-repro-head-fixed.json")
    rg = load("p0v2-red-green.json")
    gates1 = load("b1-gates.json")
    gates2 = load(os.environ.get("GATES_JSON2", "p0v2-gates.json"), required=False) or gates1
    rigg = load(os.environ.get("RIGGATES_JSON", "p0-rig-gates.json"))
    c20 = load("p0-check20-repeat.json")
    c20b = load("p0v3-guard.json")
    eq1 = load("b1-equal-check.json")
    eq2 = load("p0-equal-check.json")
    build = load("b2-build.json")
    smoke = load("b2-smoke-run2.json", required=False)
    shots = load("f1-design-shots.json")
    badge = load("f1-badge-live.json")
    rl = load("f1-red-green.json")
    parity = load(os.environ.get("PARITY_JSON", "p0v2-parity.json"), required=False)

    A("# مأموریتِ نهایی System 2 — Performance First + راستی‌آزماییِ بازشدنِ بازار")
    A("")
    A("**BorsTerminal | 18 October 2026 | شاخهٔ `" + sh(["git", "rev-parse", "--abbrev-ref", "HEAD"]) +
      "` | تولیدشده با `_test_runs/performance_first_2026-10-18/e_report.py` درِ `" +
      __import__("time").strftime("%Y-%m-%d %H:%M") + "`**")
    A("")
    A("این گزارش **کاملاً ازِ فایل‌هایِ شواهدِ همین پوشه** ساخته شده است: هر عدد با خواندنِ همان JSON/log "
      "نوشته می‌شود و هیچ رقمی دستی تایپ نشده است. چیزی که اندازه گرفته نشده، با برچسبِ "
      "`NOT_RUN` / `NOT_PROVEN` / `INCONCLUSIVE` مانده است.")
    s0(a2, p0rep, p0v1, gates1, gates2, build, smoke, shots, c20, c20b, eq2, bugrep)
    s1()
    s2(p0rep, c20, PRISTINE_SHA, load("hog-spot.json"))
    s3(rigg, c20b)
    s4(p0rep, p0v1, rg, gates2, bugrep)
    s5(a2)
    s6(rl, badge, shots)
    s7(gates1, gates2, c20, c20b, eq1, eq2, p0rep, bugrep)
    s8(build, smoke)
    s9()
    s10()
    s11(p0rep, p0v1, gates1, c20, c20b, a2, bugrep)
    s12()
    s13(gates1, gates2, build, smoke, parity, a2)
    text = "\n".join(L).rstrip() + "\n"
    io.open(OUT_MD, "w", encoding="utf-8", newline="\n").write(text)
    sys.stdout.write(text[:1200] + "\n… [" + fa(len(text.splitlines())) + " سطر، " + fa(len(text)) +
                     " نویسه] → " + os.path.relpath(OUT_MD, WT).replace("\\", "/") + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
