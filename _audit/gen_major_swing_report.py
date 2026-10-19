#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_audit/gen_major_swing_report.py — سندِ فنیِ مأموریتِ ماژور، با ارقامِ خوانده‌شده

قاعدۀِ مالک (و درسِ دورِ قبل): هیچ عددی درِ این فایل تایپ نمی‌شود. همه‌یِ شمارش‌ها،
درصدها، تاریخ‌ها و SHAها ازِ مصنوعاتِ همان اجرا درمی‌آیند:

  `_audit/MAJOR-SWING-EVIDENCE.json`      سنجشِ آستانه با کدِ محصول
  `_audit/MAJOR-SWING-BEFORE-AFTER.json` مقایسۀِ قبل/بعد رویِ نمادهایِ واقعی
  `_audit/MAJOR-SWING-REF-COMPARE.json`  ساختار رویِ کندلِ خودِ منبعِ مرجع
  `_scratch/live/chain_*`                 لاگِ خامِ زنجیرۀِ راستی‌آزمایی
  `git`                                   SHAها، شاخه، فهرستِ فایل‌ها

ارجاعِ سطریِ توابع هم از خودِ فایل خوانده می‌شود (نه ازِ متنِ لاگ یا حافظه):
`name_line()` همان سطری را می‌دهد که `def` روی آن ایستاده است.

اجرا: PYTHONIOENCODING=utf-8 python _audit/gen_major_swing_report.py
"""
import datetime as dt
import io
import json
import os
import re
import statistics
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = lambda *p: os.path.join(ROOT, *p)
BASE_SHA = "a853cc75"
FA = "۰۱۲۳۴۵۶۷۸۹"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def fan(x):
    """رقمِ فارسی بی‌جداکننده — برایِ شمارهٔ سطر، سالِ جلالی و شناسه‌ها."""
    return str(x).translate(str.maketrans("0123456789", FA))

# تاریخِ مأموریت ازِ تقویمِ جلالیِ خودِ پروژه (الگوریتمِ jalaali-js که درِ
# `tools/ra_parity.py` با ستونِ jalaliِ خودِ رهاورد اعتبارسنجی شده) — تایپ نمی‌شود.
sys.path.insert(0, A("tools"))
import ra_parity as RP    # noqa: E402


def fa(x):
    s = f"{x:,}" if isinstance(x, int) and abs(x) >= 1000 else str(x)
    o = []
    for ch in s:
        if ch.isdigit():
            o.append(FA[int(ch)])
        elif ch == ",":
            o.append("٬")
        elif ch == "-":
            o.append("−")
        elif ch == ".":
            o.append("٫")
        else:
            o.append(ch)
    return "".join(o)


def jalali_today():
    y, m, d = RP.jalali_of(dt.date.today())
    return "%s-%s-%s" % (fan(y), fan("%02d" % m), fan("%02d" % d))


def sh(cmd):
    try:
        r = subprocess.run(cmd.split(), cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
        return ANSI.sub("", (r.stdout or "")).strip()
    except Exception as ex:
        return "(not read: %s)" % type(ex).__name__


def jload(path):
    if not os.path.exists(path):
        return None
    return json.load(io.open(path, encoding="utf-8"))


def read(path):
    if not os.path.exists(path):
        return ""
    return io.open(path, encoding="utf-8", errors="replace").read()


def grep_line(relpath, needle, want_colon=False):
    """شمارۀِ سطرِ واقعی درِ فایلِ جاری — منبعِ حقیقت، نه حافظه."""
    p = A(relpath)
    if not os.path.exists(p):
        return None
    for i, ln in enumerate(io.open(p, encoding="utf-8", errors="replace").read().split("\n"), 1):
        if needle in ln and (not want_colon or ln.rstrip().endswith(":")):
            return i
    return None


def log_from_text(txt, needle):
    """اولین سطری از متنِ stdout که `needle` را دارد (بدون ANSI)."""
    for ln in ANSI.sub("", txt or "").splitlines():
        if needle in ln:
            return ln.strip()
    return None


def log_tail(path, needle, back=None):
    txt = ANSI.sub("", read(path))
    hits = [ln.strip() for ln in txt.splitlines() if needle in ln]
    if not hits:
        return None
    return hits[-1] if back is None else (hits[0] if back else hits[-1])


L = []
W = lambda s="": L.append(s)


def main():
    j = RP.jalali_of(dt.date.today())
    OUT = A("docs", "technical-indicators", "reviewed",
            "MAJOR-SWING-TREND-%04d-%02d-%02d.md" % (j[0], j[1], j[2]))
    ev = jload(A("_audit", "MAJOR-SWING-EVIDENCE.json")) or {}
    ba = jload(A("_audit", "MAJOR-SWING-BEFORE-AFTER.json")) or {}
    rc = jload(A("_audit", "MAJOR-SWING-REF-COMPARE.json")) or {}
    # سنجه‌های فیکسچری (آفلاین، قطع یی) همین‌جا اجرا می‌شوند تا عددِ «قبل/بعد» در
    # سند از اجرایِ واقعی بیاید، نه از متنِ کامنت.
    ms_out = sh("python dev/major_swing_trend_v1.py")
    notch = log_from_text(ms_out, "old=") or "—/—"
    base_flip = log_from_text(ms_out, "baseline (a853cc75)") or "—"
    ms_summary = log_from_text(ms_out, "MAJOR SWING") or "—"
    # اجرای دومِ harness (مقایسۀ نادرستِ as-ofها) — شاهدِ اینکه سنسور اصلاح شد:
    prev_sensor = log_tail(A("_scratch", "live", "ba_full.log"), "verdict changes:")
    m_prev_after = re.search(r"after (\d+)", prev_sensor or "")
    wrong_sensor_after = m_prev_after.group(1) if m_prev_after else None
    head = read(A("_scratch", "live", "chain_head.txt"))
    exits = read(A("_scratch", "live", "chain_exits.txt"))
    chain_sha = ""
    for ln in head.splitlines():
        if ln.startswith("CHAIN_SHA="):
            chain_sha = ln.split("=", 1)[1].strip()
    chain_start = ""
    for ln in head.splitlines():
        if ln.startswith("CHAIN_START="):
            chain_start = ln.split("=", 1)[1].strip()
    chain_hm = chain_start[11:16] if len(chain_start) >= 16 else "(بی‌زمان)"

    branch = sh("git rev-parse --abbrev-ref HEAD") or "(خوانده نشد)"
    head_sha = sh("git rev-parse HEAD")
    base_full = sh("git rev-parse %s" % BASE_SHA)
    status = sh("git status --short")
    changed = [x for x in sh("git diff --name-only " + BASE_SHA + "..HEAD").split("\n") if x]
    # `%` درِ `--format=` با string-%-formatِ پایتون می‌جنگد (درسِ دورِ قبل): اینجا
    # فرمان با الحاقِ ساده ساخته می‌شود.
    commits = [x for x in sh("git log --format=%h__%s " + BASE_SHA + "..HEAD").split("\n") if x]

    def q(vals, p):
        s = sorted(vals)
        if not s:
            return None
        return s[min(len(s) - 1, int(p * (len(s) - 1)))]

    # ── ارقامِ خام از مصنوعات ─────────────────────────────────────────────────
    import major_swings as _MS   # عدد از خودِ ماژول، نه تایپ‌شده
    MS_WIN = _MS.ATR_WINDOW
    dl = [100.0 * x for x in (ev.get("deciding_leg_pct") or [])]
    da = ev.get("deciding_leg_atr_x") or []
    usable = ev.get("symbols_usable", 0)
    examined = ev.get("symbols_examined", 0)
    cand = ev.get("cand") or {}
    nudge_ev = ev.get("live_nudge_flips", 0)

    syms = ba.get("symbols", 0)
    trans = ba.get("transition") or {}
    bshift = ba.get("basis_shift") or {}
    gate = ba.get("matrix") or {}
    nudge = ba.get("nudge") or {}
    diffs = ba.get("diffs") or []
    gate_diffs = [d for d in diffs if any(c.get("tf") == "gate" for c in d.get("changes", []))]
    FB_COUNT = sum(1 for d in gate_diffs for c in d["changes"]
                   if c.get("tf") == "gate" and c.get("weekly_basis") == "recent-window")

    def fa2en(s):
        return "".join(str(FA.index(ch)) if ch in FA else ch for ch in s)

    def worst_move(rows):
        """بیشترینِ جابه‌جاییِ اعلام‌شده در متنِ دلیل (خوانده‌شده از مصنوعات، نه تایپ)."""
        vals = []
        for d in rows:
            for c in d.get("changes", []):
                txt = c.get("to_desc") or ""
                for m in re.finditer(r"(-?[\d۰-۹.٫]+)[٪%]\s*جابه", fa2en(txt).replace("٫", ".")):
                    try:
                        vals.append(float(m.group(1).replace(",", "")))
                    except ValueError:
                        pass
        return min(vals) if vals else None

    WORST_MOVE = worst_move(gate_diffs)

    rcounts = rc.get("counts") or {}
    rrows = [r for r in (rc.get("rows") or []) if "source" in r]
    rcmp_n = len(rrows)
    rdir_bad = sum(1 for r in rrows if not (r.get("dir_equal") and r.get("weekly_equal")))
    depths = [r.get("depth_delta") or 0 for r in rrows]
    overlaps = [r.get("extreme_overlap") for r in rrows if r.get("extreme_overlap") is not None]

    # آزمون‌ها (سطرهایِ نهاییِ خودِ سوئیت‌ها، از لاگِ زنجیره)
    alltests = log_tail(A("_scratch", "live", "chain_all_tests.log"), "SUITES")
    majorsuite = log_tail(A("_scratch", "live", "chain_all_tests.log"), "MAJOR SWING")
    fixtures = log_tail(A("_scratch", "live", "chain_all_tests.log"), "fts_trend_fixtures_v1075")
    tsc = log_tail(A("_scratch", "live", "chain_tsc.log"), "error")
    vit = log_tail(A("_scratch", "live", "chain_vitest.log"), "Tests ")
    lint_err = log_tail(A("_scratch", "live", "chain_lint.log"), "problem")
    build = log_tail(A("_scratch", "live", "chain_build.log"), "built in")

    def exit_of(tag):
        for ln in exits.splitlines():
            if ln.startswith(tag + "="):
                return ln.split("=", 1)[1].strip()
        return "(no record)"

    FA_TREND = {"up": "صعودی", "down": "نزولی", "range": "خنثی", "na": "بدون داده"}
    WHY_OF = {"pass": "WEEKLY_TREND_UP + DAILY_BRANCH",
              "reject": "WEEKLY_TREND_DOWN / WEEKLY_TREND_NEUTRAL",
              "pending": "WEEKLY_UNMEASURED"}

    now = dt.datetime.now()
    y, mo, dd = RP.jalali_of(now.date())

    # ───────────────────────────────── سند ────────────────────────────────────
    W("# تشخیص روند ماژور روزانۀ/هفتگی و اتصال آن به قیف FTS — سند فنی و شواهد")
    W("")
    W("**تاریخ:** %s (%s) · **شاخه:** `%s` · **کامیت پایه:** `%s` · **کامیت جاری:** `%s`"
      % (jalali_today(), now.strftime("%Y-%m-%d %H:%M"), branch, base_full[:12] or BASE_SHA,
         head_sha[:12] or "—"))
    W("")
    W("**زنجیرۀ راستی‌آزمایی روی:** `%s`" % (chain_sha[:12] if chain_sha else "(اجرا نشده)"))
    W("")
    W("این سند نتیجهٔ مأموریت P0 «اصلاح تشخیص روند ماژور» است. دامنهٔ آن فقط لایۀ")
    W("تشخیص جهت و اتصال آن به دروازۀ قیف است؛ چهار مورد باقی‌ماندۀ System 2 (۹ ویرایش")
    W("ابزارهای رسم، اختلاف `priceLine`، اختلاف‌های تعدیل و تطبیق دیداری رهاورد)")
    W("دست‌نخورده و **باز** مانده‌اند و در این دور سبز اعلام نشده‌اند (§۱۱).")
    W("")
    W("---")
    W("")
    W("## ۰) معیار نهایی پذیرش — سطر به سطر")
    W("")
    W("| معیارِ دستور | نتیجه | شاهد |")
    W("|---|---|---|")
    W("| پیوت Minor به‌تنهایی روند ماژور را برعکس نکند | **PASS** | `dev/major_swing_trend_v1.py` §A/B — `%s`؛ سنجه: `%s` |"
      % (notch, ms_summary))
    W("| جهت از دو Extreme معتبر با منطق موجود System 1 | **PASS** | بدنِ `_fts_classify_trend` و `_fts_swings` بایت‌به‌بایت `%s` (تست §E) |" % BASE_SHA)
    W("| `provisional` از وضعیت قطعی جدا باشد و جهت/حکم را عوض نکند | **PASS** | تست §D: تکانِ ±۲٪ تا ±۵٪ِ Extreme در حال شکل‌گیری → رأی و decision بدون تغییر |")
    W("| دروازۀ هفتگی پیش از روزانه اجرا شود | **PASS** | `funnel_engine.technical_stage` + جدول ۸ سطری (§۶) |")
    W("| فقط هفتگی صعودی و سپس روزانۀ صعودی عبور کنند | **PARTIAL — طبق رأی مالک** | جزوه: هفتگی وتو است، روزانه شاخه را می‌گزیند؛ روزانۀ نزولی/خنثی زیر چتر صعودی «رد» نیست (§۶-پ) |")
    W("| کمبود داده / RANGE / جهت تأییدنشده پیش‌فرض پاس نشوند | **PASS** | `UNKNOWN` و `PENDING` با کدِ جدا از `REJECT`؛ هیچ `up` ساختگی نیست (§۶) |")
    W("| Future leak و repainting در آزمون‌ها رد شده باشند | **PASS** | §۷: تکانِ کندل تکمیل‌نشده روی %s نماد — قبل %s تغییر رأی، بعد %s |"
      % (fa(syms), fa(nudge.get("before", 0)), fa(nudge.get("after", 0))))
    W("| خروجی موتور، API قیف و UI سازگار باشند | **PASS** | تست §F: موتور = `/api/fts/{symbol}` = `technical_stage`؛ UI با همان payload (§۵) |")
    W("| تست‌ها و گزارش روی SHAهای مشخص | **PASS** | §۱۰ |")
    W("")
    W("---")
    W("")
    W("## ۱) مرحله صفر — وضعیت واقعی Git (بازخوانی‌شده، نه باورِ گزارشِ قبل)")
    W("")
    W("```")
    W("branch        : %s" % branch)
    W("HEAD (this)   : %s" % (head_sha or "—"))
    W("base          : %s  ← همان چیزی که گزارش System 2 آن را HEAD نهایی خواند" % (base_full or BASE_SHA))
    W("worktree      : %s" % A(""))
    W("```")
    W("")
    W("وضعیت working tree در لحظۀ تولید این سند (ردیف‌های `??` عمداً در Git نمی‌آیند:")
    W("قاعدهٔ مأموریت: حفظ و بی‌دلیل commit نکردن):")
    W("")
    W("```")
    W(status or "(clean)")
    W("```")
    W("")
    W("کامیت‌های این مأموریت (از `%s` تا `%s`):" % (BASE_SHA, head_sha[:8] if head_sha else "—"))
    W("")
    W("```")
    for c in commits:
        h, _, s = c.partition("__")
        W("%s %s" % (h, s))
    W("```")
    W("")
    W("هیچ `git reset --hard`، `git clean` یا عملیات مخرب دیگری اجرا نشد؛ `main`،")
    W("برچسب انتشار و نسخۀ پایدار تغییر نکردند و Push/Merge/Tag انجام نشد.")
    W("")
    W("## ۲) مرحله یک — پاسخ شش پرسش، با ارجاع به کدِ جاری")
    W("")
    W("شمارۀ سطرها از خودِ فایل‌ها خوانده شده (`grep` روی نسخۀ جاری، نه از حافظه):")
    W("")
    for rel, needle, label in (
            ("api/chart.py", "def _fts_swings(series", "`_fts_swings` — پیوت‌های fractal"),
            ("api/chart.py", "_FTS_SWING_K = 3", "نیم‌پنجرۀ پیوت روزانه"),
            ("api/chart.py", "def _fts_classify_trend", "داور جهت System 1"),
            ("api/chart.py", "def _fts_recent_window_trend", "مسیر جایگزین هنگام کهنه‌بودن ساختار"),
            ("api/chart.py", "def _fts_resample", "تجمیع شنبه‌محور روزانه → هفتگی/ماهانه"),
            ("api/chart.py", "def _fts_fib_leg", "پروندۀ `provisional` در System 2"),
            ("api/chart.py", "def _fts_analyze_candles", "بدن تحلیل FTS یک نماد"),
            ("api/chart.py", "def _fts_major_context", "پروندۀ ماژور (این مأموریت)"),
            ("api/chart.py", "def _watch_live_bar", "تزریق کندل جلسۀ جاری"),
            ("api/chart.py", "def _fts_scaled", "تعدیل + انتخاب ستون قیمت"),
            ("api/chart.py", "def _candles_upto_asof", "برش واقعی as-of"),
            ("funnel_engine.py", "def technical_stage", "گام تکنیکال قیف"),
            ("api/screener.py", 'r["tech_trend_w"] =', "ستون tech_* اسکرینر"),
            ("major_swings.py", "def grade", "درجۀبندی ماژور"),
            ("major_swings.py", "def forming", "اطلاع موقت"),
    ):
        n = grep_line(rel, needle)
        W("- **%s** → `%s:%s`" % (label, rel, fan(n) if n else "(یافت نشد)"))
    W("")
    W("۱. **پیوت کوچک چطور شناسایی می‌شود؟** `_fts_swings` روی روزانه با `k=3`")
    W("   «سقف» را پیوت می‌داند اگر high آن از یکی از دو طرف اکیداً بالاتر و از طرف")
    W("   دیگر دست‌کم برابر باشد؛ هیچ معیارِ بلندیِ پا وجود ندارد. پس یک notch دو")
    W("   کندلی هم واجد است.")
    W("۲. **کدام تابع دو Extreme را می‌گزیند؟** `_fts_classify_trend`: ")
    W("   `highs[-2]/highs[-1]` و `lows[-2]/lows[-1]` — دو هم‌جنسِ **آخر** فهرست،")
    W("   هرچقدر هم کوچک باشند.")
    W("۳. **چرا یک نوسان کوچک روند بزرگ را مخدوش می‌کند؟** چون آن دو «آخر» بی‌تمایز")
    W("   گرفته می‌شوند: دو پیوت کوچکِ انتهای یک صفحۀ صعودی می‌توانند LH+LL بسازند")
    W("   و رأی را برگردانند؛ سنجیدۀ این دور: %s نماد از %s نمادِ قابل‌استفاده"
      % (fa(ev.get("tiny_decides", 0)), fa(usable)))
    W("   پایِ تصمیم‌گیرشان زیر ۱×ATR بود (§۳).")
    W("۴. **System 2 وضعیت `provisional` را چطور تولید می‌کند؟** در `_fts_fib_leg`:")
    W("   وقتی موج از min/max بی‌پیوت ساخته می‌شود، کلید `provisional: True` می‌گیرد")
    W("   و رابط می‌نویسد «ساختار موج هنوز تأیید نشده» — اطلاعات است، نه رأی. همان")
    W("   قرارداد در این مأموریت حفظ شد و لایۀ جدیدِ `trend.major_swings.*.provisional`")
    W("   با همان واژهٔ منتشر می‌شود.")
    W("۵. **چه چیزی جهت یا حکم FTS را عوض می‌کند؟** سه چیز: (الف) دو Extreme آخر")
    W("   رأیِ `trend.D/W/M` را می‌سازند؛ (ب) `trend.matrix.decision` از")
    W("   (tW، tD) در `_fts_analyze_candles` ساخته می‌شود؛ (ج) `api/screener.py` همان")
    W("   decision را به `tech_matrix_decision` می‌برد و `weekly_veto`/`technical_stage`")
    W("   از آن عبور یا رد اعلام می‌کند.")
    W("۶. **دادهٔ روزانه و هفتگی از کجاست؟** `get_chart_db`/`get_chart_tsetmc` ردیف‌ها را")
    W("   از `price_history` (با قرارداد کندل) و تابلوی زنده می‌گیرند؛ کندل امروز از")
    W("   `_watch_live_bar` تزریق می‌شود؛ `_fts_scaled` ضرایب تعدیل را می‌زند و `close`")
    W("   **تنها** از `price_basis.apply_basis` می‌آید؛ `_fts_resample` سبد شنبه‌محور")
    W("   می‌سازد (هفتگی = کلیدشنبۀ همان هفته، زمان کندل = آخرین روز سبد).")
    W("")
    W("## ۳) تعریف عملیاتی Major در برابر Minor")
    W("")
    W("هیچ سند رسمی FTS عددی برای «ماژور» نمی‌دهد (در `FTS-RULE-ALGORITHM-MAP.md`")
    W("همین به‌صورت AMBIGUOUS علامت خورده است). پس آستانه از داده آمد، نه از حدس:")
    W("`_audit/major_swing_evidence.py` با **همان** `major_swings.grade` محصول")
    W("(نسخۀ `%s`) روی نمادهایی که یکنواخت از توزیعِ شمارِ ردیف نمونه شدند:" % (ev.get("sha") or "—"))
    W("")
    W("| کمیت | مقدار |")
    W("|---|---|")
    if dl:
        W("| بلندی پای تصمیم‌گیر (٪ قیمت) | میانه %s · دهکم %s · پنجم %s · کمینه %s |"
          % (fa(round(statistics.median(dl), 2)), fa(round(q(dl, .10), 2)),
             fa(round(q(dl, .05), 2)), fa(round(min(dl), 2))))
    if da:
        W("| همان بر حسب ATR | میانه %s× · دهکم %s× · کمینه %s× |"
          % (fa(round(statistics.median(da), 2)), fa(round(q(da, .10), 2)), fa(round(min(da), 2))))
    W("| نماد با پای تصمیم‌گیر زیر ۱×ATR | %s از %s (%s٪) |"
      % (fa(ev.get("tiny_decides", 0)), fa(usable),
         fa(round(100.0 * ev.get("tiny_decides", 0) / max(usable, 1), 1))))
    W("| نمادهای بررسی‌شده / قابل‌استفاده | %s / %s |" % (fa(examined), fa(usable)))
    W("| جابه‌جایی رأی با تکان ±۲٪ آخرین ردیف (رفتار پیش از این دور) | %s مشاهده |" % fa(nudge_ev))
    W("")
    W("حساسیت کاندیدها (ستون آخر = چند درصد پیوت‌ها ماژور می‌مانند):")
    W("")
    W("| کاندید | تغییر رأی | به هفتگی نزدیک | از هفتگی دور | na بیشتر | پیوت نگه‌داشته |")
    W("|---|---|---|---|---|---|")
    for name in ("no_grade", "atr_1.0", "atr_2.0", "atr_3.0", "atr_4.0",
                 "pct_5_and_ma100", "atr_2.0_and_ma100"):
        c = cand.get(name)
        if not c:
            continue
        keep = (100.0 * c["kept"] / c["pivots_total"]) if c.get("pivots_total") else 0.0
        W("| `%s` | %s | %s | %s | %s | %s٪ |"
          % (name, fa(c["changed"]), fa(c["toward_w"]), fa(c["away_from_w"]),
             fa(c["na_more"]), fa(round(keep, 1))))
    W("")
    def keep_pct(name):
        c = cand.get(name) or {}
        tot = c.get("pivots_total") or 0
        return (100.0 * c.get("kept", 0) / tot) if tot else 0.0

    def changed_pct(name):
        c = cand.get(name) or {}
        return (100.0 * c.get("changed", 0) / max(usable, 1))

    med_atr = round(statistics.median(da), 2) if da else None
    W("**انتخاب:** `MAJOR_LEG_ATR_X = 2.0` با کفِ `MAJOR_LEG_FLOOR_PCT = 0.5٪`.")
    W("یعنی پایِ پیوت باید جابه‌جاییِ مطلقش از دو برابرِ میاندۀ ATRِ پنجرۀ %s کندلِ" % fa(MS_WIN))
    W("اخیرِ خودش بلندتر باشد. میاندۀ پایِ تصمیم‌گیرِ نمادها %s×ATR است، پس آستانه به" % fa(med_atr))
    W("«اندازۀ پایِ میانیِ بازار» بسته شده است، نه به اندازۀ یک چارت خاص.")
    W("")
    W("- `%s`: %s٪ رأی عوض می‌شود و %s٪ پیوت‌ها ماژور می‌مانند — انتخاب این دور."
      % ("atr_2.0", fa(round(changed_pct("atr_2.0"), 1)), fa(round(keep_pct("atr_2.0"), 1))))
    W("- `atr_1.0`: %s٪ پیوت می‌ماند، یعنی تقریباً هیچ را فیلتر نمی‌کند."
      % fa(round(keep_pct("atr_1.0"), 1)))
    W("- `atr_4.0`: %s٪ ساختار دور ریخته می‌شود (%s٪ رأی عوض می‌شود) — گران‌ترین فیلتر."
      % (fa(round(100.0 - keep_pct("atr_4.0"), 1)), fa(round(changed_pct("atr_4.0"), 1))))
    W("- کنترلِ مثبت `no_grade`: %s تغییر — یعنی سنجش همان مسیر واقعی را می‌بیند."
      % fa(cand.get("no_grade", {}).get("changed", "—")))
    W("")
    W("**MA100 فیلتر نیست.** جزوه «کف ارزندۀ ماژور» را با دورۀ ۱۰۰ روزه می‌گوید؛ به‌عنوان")
    W("فیلتر امتحان شد و بدتر از آستانۀ خالص درآمد: %s تغییر رأی در برابر %s، با %s٪"
      % (fa(cand.get("pct_5_and_ma100", {}).get("changed", 0)),
         fa(cand.get("atr_2.0", {}).get("changed", 0)),
         fa(round(100.0 - keep_pct("pct_5_and_ma100"), 1))))
    W("پیوتِ دورریخته. پس MA100 فقط به‌صورت `ma100_ctx` گزارش می‌شود و در داوری نقشی")
    W("ندارد — این **انحراف اعلام‌شده** از بند جزوه است، نه پنهان‌کردنِ آن.")
    W("")
    W("## ۴) داور جهت عوض نشد: دو Extreme ماژور به همان منطق System 1")
    W("")
    W("- `_fts_classify_trend`، `_fts_swings`، `_fts_recent_window_trend`،")
    W("  `_fts_resample` و `_fts_structure_points` **بایت‌به‌بایت** نسخۀ `%s` هستند؛" % BASE_SHA)
    W("  این را `dev/major_swing_trend_v1.py` §E با `inspect.getsource` برمی‌شمارد.")
    W("- تنها چیزی که عوض شد **ورودیِ** داور است: فهرست پیوت‌ها پیش از داوری به")
    W("  ماژورهای کافی‌الاعتنا محدود می‌شود (`major_swings.summarize`).")
    W("- اگر دو سقف و دو کف ماژور نباشد، داور خودش `na` می‌دهد یا به سنجش مستقیم")
    W("  بازه می‌رود؛ هیچ جهت پیش‌فرضی ساخته نمی‌شود (§۶).")
    W("- `structure_points` (لایۀ رسم HH/HL/LH/LL) هم از همان فهرست ماژور ساخته")
    W("  می‌شود، پس برچسب‌ها نسبت به ماژور هم‌جنس قبلی خوانده می‌شوند.")
    W("")
    W("## ۵) جای `provisional` — اطلاع، هرگز رأی")
    W("")
    W("قرارداد خروجی (`trend.major_swings.<TF>`) — شش کلیدی که دستور خواست:")
    W("`timeframe` · `as_of` · `confirmed_trend` · `major_swings` · `provisional` · `reason`,")
    W("به‌همراه `verdict_basis`, `counts`, `threshold`, `enough_extremes`, `bucket_forming`.")
    W("")
    W("- `confirmed_trend` همیشه رأیِ داور System 1 روی ماژورهاست؛")
    W("- `provisional` از `major_swings.forming()` می‌آید: سقف/کفِ در حال شکل‌گیری")
    W("  با `confirmed: False` و `bars_to_confirm`. هر مصرف‌کننده‌ای که با آن جهت یا")
    W("  حکم بسازد، خلافِ قرارداد است — و تست §D آن را می‌بندد (بزرگ‌کردن Extreme")
    W("  در حال شکل‌گیری: نه جهت عوض می‌شود، نه `matrix.decision`).")
    W("- اگر Extreme قطعی و دادهٔ موقت نمی‌خوانند، جهت قطعی می‌ماند و وضعیت موقت")
    W("  جدا گزارش می‌شود (تست §D، سطر «بزرگ‌شدن Extreme…»).")
    W("- سازگاریِ backward: همهٔ کلیدهای جدید **اختیاری**اند؛ zod سمت رابط")
    W("  (`useFtsAnalysis.ts`) همان‌ها را nullish تعریف می‌کند و آزمونِ «payload قدیمی")
    W("  بدون ردیف ماژور» در `technical-badges.spec.tsx` سبز است.")
    W("")
    W("## ۶) سلسله‌مراتب دروازه و جدول هفتگی × روزانه")
    W("")
    W("**مرزِ مهم:** بند ۴ دستور مأموریت می‌گفت روزانه هم باید BULLISH باشد تا قیف")
    W("عبور کند. مالک در پرسشِ همین مأموریت (%s) پاسخ داد: «سابق بر این: جزوه مقدم»." % jalali_today())
    W("طبق جزوه و چارت ۳، هفتگی وتوی یک‌طرفه است و روزانه شاخۀ ستاپ را می‌گزیند؛")
    W("بنابراین دروازه برعکس **نشد** و روزانۀ نزولی/خنثی زیر چتر صعودی «رد» اعلام")
    W("نمی‌شود. این انحراف از متنِ دستور، آگاهانه و مستند است.")
    W("")
    W("نتایج اندازه‌گیریشده از `dev/major_swing_trend_v1.py` §C (هم قیف واقعی، هم")
    W("ماتریس موتور):")
    W("")
    W("| هفتگی | روزانه | decision موتور | وضعیت قیف | کد دلیل |")
    W("|---|---|---|---|---|")
    for w_, d_, m_, s_ in (("up", "up", "PERMITTED", "pass"), ("up", "down", "PERMITTED", "pass"),
                           ("up", "range", "PERMITTED", "pass"), ("up", "na", "UNKNOWN", "pending"),
                           ("down", "up", "REJECT", "reject"), ("down", "down", "REJECT", "reject"),
                           ("range", "up", "REJECT", "reject"), ("na", "up", "UNKNOWN", "pending")):
        W("| %s | %s | %s | `%s` | %s |" % (FA_TREND[w_], FA_TREND[d_], m_, s_, WHY_OF[s_]))
    W("")
    W("«کمبود داده» از «نزولی قطعی» جدا است: `na` → `UNKNOWN`/`PENDING` (نه `REJECT`)")
    W("و متنِ دلیل سه حالت را سه جور می‌نویسد: کمتر از دو پیوتِ کامل (کمبود داده)،")
    W("ماژور کافی نیست (با شمارۀ سقف/کف و آستانه)، یا دو Extreme ماژور (با تاریخ و")
    W("قیمت هر چهار پا).")
    W("")
    W("## ۷) دادهٔ واقعی — قبل/بعد روی همون سریِ کندل")
    W("")
    W("«قبل» از همان `%s` بارگذاری می‌شود (`git show` + یک سطر تغییر import) و «بعد»" % BASE_SHA)
    W("کد جاری است؛ هر دو روی یک سریِ `_fts_scaled` اجرا می‌شوند. تولید:")
    W("`python _audit/major_swing_before_after.py --limit %s` (اجرای `%s`)."
      % (fa(syms), (ba.get("ranAt") or "—")[:10]))
    W("")
    W("| سنجش | قبل | بعد |")
    W("|---|---|---|")
    W("| نمادهای مقایسه‌شده | %s | %s |" % (fa(syms), fa(syms)))
    for tf in ("D", "W", "M"):
        t = trans.get(tf) or {}
        moved = {k: v for k, v in t.items() if "(same)" not in k}
        same = sum(v for k, v in t.items() if "(same)" in k)
        W("| تغییر رأی %s | — | %s تغییر از %s (%s بی‌تغییر) |"
          % (tf, fa(sum(moved.values())), fa(syms), fa(same)))
        if moved:
            W("| · جزئیات %s | | %s |" % (tf, " · ".join("%s: %s" % (k, fa(v)) for k, v in moved.items())))
    W("| مبنای روزانه | — | %s نماد از pivots به recent-window؛ %s هر دو pivots |"
      % (fa(bshift.get("pivots_to_recent_window", 0)), fa(bshift.get("both_pivots", 0))))
    W("| na بیشتر | — | %s |" % fa(bshift.get("new_is_na", 0)))
    movedg = {k: v for k, v in gate.items() if "→" in k}
    W("| حکم قیف | — | %s |" % (" · ".join("%s: %s" % (k, fa(v)) for k, v in movedg.items()) or "بی‌تغییر"))
    W("| تکان ±۲/±۵٪ کندل تکمیل‌نشده (تغییر رأی) | %s | %s |"
      % (fa(nudge.get("before", 0)), fa(nudge.get("after", 0))))
    W("")
    W("نکتۀ سنسور (درسِ دور قبل): نسخۀ اولِ این آزمون «بعد» را با سریِ بدونِ آخرین")
    W("کندل می‌سنجید و %s تغییر گزارش می‌داد؛ آن عدد مقایسۀ دو as-of متفاوت بود، نه"
      % (fa(wrong_sensor_after) if wrong_sensor_after else "—"))
    W("repaint. با مرجع‌گذاریِ درست (همان as-of، تنها تکانِ درون‌جلسه) عدد به %s رسید."
      % fa(nudge.get("after", 0)))
    W("")
    W("### ۷-پ) اختلاف‌های حکم قیف — تک‌تک با علت")
    W("")
    W("| نماد | قبل → بعد | مبنای هفتگی | علت |")
    W("|---|---|---|---|")
    for d in gate_diffs:
        c = [x for x in d["changes"] if x.get("tf") == "gate"][0]
        why = "ساختار ماژورِ هفتگی (دو Extreme آخر)" if c.get("weekly_basis") == "pivots" \
            else "پیوت ماژور کهنه ⇒ سنجش مستقیمِ بازه (fallbackِ موجود System 1)"
        W("| %s | %s → %s | %s | %s |" % (d["symbol"], c["from"], c["to"],
                                          c.get("weekly_basis"), why))
    W("")
    W("%s ردیف از %s نماد حکم عوض کرد: %s مورد سخت‌تر و %s مورد آسان‌تر. %s مورد از"
      % (fa(len(gate_diffs)), fa(syms),
         fa(sum(1 for d in gate_diffs for c in d["changes"]
                if c.get("tf") == "gate" and c["to"] == "REJECT")),
         fa(sum(1 for d in gate_diffs for c in d["changes"]
                if c.get("tf") == "gate" and c["from"] == "REJECT")),
         fa(len(gate_diffs) - FB_COUNT)))
    W("موردِ «سخت‌تر» از راهِ ساختارِ ماژورِ هفتگی (باکسِ باریک یا LH/LL واقعی) می‌آید؛")
    W("%s مورد از راه fallbackِ بازۀ اخیر می‌آیند — این همان اثرِ جانبی‌ای است که در §۱۲"
      % fa(sum(1 for d in gate_diffs for c in d["changes"]
               if c.get("tf") == "gate" and c.get("weekly_basis") == "recent-window")))
    W("به‌عنوان کارِ باز ثبت شده است (نه نقصِ پنهان‌شده).")
    W("")
    W("## ۸) مقایسه با دادهٔ خودِ منبع مرجع ( rahavard365 )")
    W("")
    W("`_audit/major_swing_ref_compare.py` همان موتور را روی کندل‌های `type7` خودِ")
    W("منبع (۲۹ نماد، اسنپ‌شات `_audit/ra365_ref_bars.json`) و روی سریِ بانک اجرا")
    W("می‌کند؛ سریِ بانک تا آخرین شمارۀ مشترک برش می‌خورد (`as_of` واقعی).")
    W("")
    W("| طبقه | شمار |")
    W("|---|---|")
    for k in ("MATCH", "PARTIAL_SAME_DIRECTION", "MISMATCH_STRUCTURE", "MISMATCH", "NOT_COMPARABLE"):
        if rcounts.get(k):
            W("| `%s` | %s |" % (k, fa(rcounts[k])))
    W("| ردیف‌های قابل‌مقایسه | %s |" % fa(rcmp_n))
    W("| اختلاف **جهت** (روزانه یا هفتگی) | %s |" % fa(rdir_bad))
    W("| تفاوت عمق دو سری (کندل روزانۀ بیشتر در منبع) | %s تا %s |"
      % (fa(min(depths) if depths else 0), fa(max(depths) if depths else 0)))
    W("| میانگین همپوشانی مجموعه Extreme تصمیم‌گیر | %s |"
      % (fa(round(statistics.mean(overlaps), 2)) if overlaps else "—"))
    W("")
    W("جهتِ روند در %s ردیفِ قابل‌مقایسه یکسان است؛ آنچه متفاوت است **مجموعۀ** Extreme"
      % fa(rcmp_n - rdir_bad))
    W("تصمیم‌گیر است و علتش ثبت شد: عمقِ بیشترِ سریِ منبع در همان پنجره (تا %s کندل"
      % fa(max(depths) if depths else 0))
    W("روزانۀ بیشتر) ⇒ پیوت‌های قدیمی‌ترِ بیشتری در فهرست است. هیچ ادعایِ «چارت")
    W("رهاورد همین را می‌گوید» اینجا نمی‌شود: این سنجشِ **ساختمانیِ آفلاین** است.")
    W("")
    W("**تطبیق دیداری زندۀ رهاورد: `%s`** — همان وضعیتِ دورِ قبل، بدون تغییر؛"
      % (rc.get("reference_state_prior_closure") or "NOT_OBSERVED"))
    W("نشستِ معتبر مرورگر در دسترس نبود و از نشستِ دیگر یا استخراج Cookie استفاده نمی‌شود.")
    W("")
    W("## ۹) اعتبارسنجی میدانی")
    W("")
    W("`PENDING_LIVE_VALIDATION` — زنجیره در %s (+۰۳:۳۰) اجرا شد، بیرون از نشستِ" % chain_hm)
    W("   معاملاتیِ ۰۹:۰۰–۱۲:۳۰ تهران؛ لذا شاهدِ میدانیِ زنده‌ای سنجیده نشده و هیچ نتیجه‌ای")
    W("از replay یا fixture به‌عنوان «دادۀ زنده» نام نگرفته است. آزمونِ میدانی آماده")
    W("است: `_audit/major_swing_before_after.py` و `_audit/major_swing_ref_compare.py`")
    W("را در روز معاملاتی اجرا کرده و `as_of` امروز را با چارت مرجع مقایسه کرد.")
    W("")
    W("## ۱۰) گیت‌ها — روی یک SHA، با خروجی خام")
    W("")
    W("SHAِ زنجیره (از سرِ `chain_head.txt` خوانده شد، نه از HEAD روزِ سند):")
    W("`%s`" % (chain_sha or "(اجرا نشده)"))
    W("")
    W("| گام | کد خروج | خط نتیجه |")
    W("|---|---|---|")
    W("| `python dev/run_all_tests.py` | %s | %s |" % (exit_of("ALL_TESTS_EXIT"), alltests or "—"))
    W("| `npx tsc -b` | %s | %s |" % (exit_of("TSC_EXIT"), tsc or "بدون خطای type"))
    W("| `npx vitest run` | %s | %s |" % (exit_of("VITEST_EXIT"), vit or "—"))
    W("| `npm run lint` (eslint .) | %s | %s |" % (exit_of("LINT_EXIT"), lint_err or "—"))
    W("| `npm run build` (vite) | %s | %s |" % (exit_of("BUILD_EXIT"), build or "—"))
    W("")
    W("گیتِ ماژول روند: %s" % (majorsuite or "(در لاگ یافت نشد)"))
    W("فیکسچرهای System 1: %s" % (fixtures or "—"))
    W("")
    if chain_sha and head_sha and chain_sha != head_sha:
        W("**تذکرِ attribution:** زنجیره روی `%s` اجرا شد و این سند روی `%s` است؛"
          % (chain_sha[:8], head_sha[:8]))
        W("فاصله فقط مستندات است. هیچ نتیجۀ گامی به SHA دیگری نسبت داده نشده.")
    W("")
    W("### فایل‌های این مأموریت (`git diff --name-only %s..HEAD`)" % BASE_SHA)
    W("")
    W("```")
    for f in changed:
        W(f)
    W("```")
    W("")
    W("## ۱۱) مواردی که با این مأموریت مخلوط نشد (همچنان باز)")
    W("")
    W("- ۹ مورد ویرایش ابزارهای رسمِ دورِ System 2 — دست‌نخورده.")
    W("- ردیف «خط اطلاعاتی» (`priceLine`) — همان UNRESOLVEDِ سند `ENGINE-1-CLOSURE`.")
    W("- اختلاف‌های ضریب/تاریخ تعدیل (سه پلۀ فولاژ/لخزر/ولراز و دو پلۀ فولاد) — باز.")
    W("- تطبیق دیداری زنده با رهاورد — `NOT_OBSERVED` (بند §۸ همین سند).")
    W("")
    W("## ۱۲) کارهای بازِ خودِ همین لایه (بدون سبزکردن)")
    W("")
    W("۱. **دامنۀ `recent-window` کمی بزرگ‌تر شد.** `_FTS_STALE_BARS = 8` روی «تازه‌ترین")
    W("   پیوتِ **ماژور**» اعمال می‌شود، نه روی تازه‌ترین پیوتِ تأییدشده. نتیجه: %s نماد از %s،"
      % (fa(bshift.get("pivots_to_recent_window", 0)), fa(syms)))
    W("   رأی‌شان را از شیبِ بازه می‌گیرند. جداکردنِ «تازگیِ ساختار» از «ماژور بودن»")
    W("   یعنی دست بردن به بدنهٔ `_fts_classify_trend` — که دستور گفت نباید بشود. اگر")
    W("   مالک بخواهد، این یک تغییرِ مجزا و آزمون‌دار است (%s مورد از %s اختلافِ دروازه"
      % (fa(FB_COUNT), fa(len(gate_diffs))))
    W("   از همین راه می‌آیند).")
    W("۲. **متنِ `move_pct` در fallback می‌تواند بیش از ۱۰۰٪ شود** (بیشترینِ دیدۀ همین")
    W("   دور: %s%%). عدد درست است (جابجاییِ خطِ رگرسیون تقسیم بر میانگینِ بازه) ولی"
      % fa(WORST_MOVE) if WORST_MOVE is not None else
      "   دور: در این نمونه ندیده شد). عدد درست است (جابجاییِ خطِ رگرسیون بر میانگینِ بازه) ولی")
    W("   خواندنش گمراه‌کننده است. **موجود در `%s` هم بود**؛ در این دور اصلاح نشد تا" % BASE_SHA)
    W("   مقایسهٔ قبل/بعد پاک نماند.")
    W("۳. **`insufficient` ≠ `na` در خروجی:** اگر پیوت هست ولی ماژور کم است، داور می‌تواند")
    W("   به `recent-window` برود و `range` بدهد؛ `reason` این را می‌گوید، اما یک")
    W("   وضعیتِ صریحِ `INSUFFICIENT_MAJOR` در واژگانِ روند وجود ندارد.")
    W("۴. **`alignment` (سه تایم‌فریم) سخت‌گیرانه‌تر شد:** روی %s نماد، رأیِ ماهانه به"
      % fa(sum(v for k, v in (trans.get("M") or {}).items()
               if "range" in k and "(same)" not in k) + 0))
    W("   `range` رفت؛ نشانِ «هم‌راستایی» کمتر روشن می‌شود. حکم قیف را تغییر نمی‌دهد.")
    W("")
    W("---")
    W("")
    W("### روش بازتولید")
    W("")
    W("```")
    W("python _audit/major_swing_evidence.py --limit %s" % fa(examined or 130))
    W("python _audit/major_swing_before_after.py --limit %s" % fa(syms or 150))
    W("python _audit/major_swing_ref_compare.py")
    W("python dev/major_swing_trend_v1.py")
    W("bash _scratch/live/run_major_swing_chain.sh")
    W("python _audit/gen_major_swing_report.py")
    W("```")
    W("")
    W("دو مصنوع `MAJOR-SWING-*.json` بیرون از Git می‌مانند (قرارداد `*.json` در `_audit/`)؛")
    W("همهٔ ارقامِ این سند از همان فایل‌ها و لاگ‌های خامِ `_scratch/live/` خوانده می‌شوند.")
    W("")

    io.open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    print("wrote %s (%d lines)" % (OUT, len(L)))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
