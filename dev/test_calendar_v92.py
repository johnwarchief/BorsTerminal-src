# -*- coding: utf-8 -*-
"""v9.2 — تست یکا (parity) طبقه‌بندی تقویم: category_of() پایتون ≡ classify() فرانت.

اگر این دو نسخه از هم فاصله بگیرند، رویدادی که در cache.json دسته‌بندی شده
در UI دسته‌ای دیگر می‌نشیند (دقیقاً همان کلاس باگی که در v2.2 دیدیم).

v9.3 — بخش ۳: گاردِ تمرکزِ چرخش IP. adb_rotate_ip نباید منطقِ توگلِ خودی
بنویسد؛ باید codal_fetcher.rotate_ip_via_adb (۸۰s+۲۰s + تأیید IP) را صدا
بزند. کپیِ محلیِ قبلی توگلِ کوتاه (۲s+۸s) می‌زد که PDP context را تخریب
نمی‌کرد → IP پین می‌ماند → backoff ریست نمی‌گشت → اسکریپت روی بن می‌ماند.
این بخش با stub کردنِ تابع مرجع کار می‌کند — هیچ دستگاهی لمس نمی‌شود.
"""
import io, os, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calendar_fetcher as cf

CASES = [
    # (عنوان، tid انتظار، دسته انتظار)
    # نکتهٔ v9.2: برای «لغو/تغییر زمان» و «افزایش سرمایه» صراحتاً tid=0 انتظار
    # می‌رود، چون classify_tid آن را به منطق عنوان‌محور فرانت می‌سپارد.
    ("آگهی دعوت به مجمع عمومی عادی سالیانه دوره ۱۲ ماهه منتهی به ۱۴۰۲/۱۲/۲۹", 1, "assembly"),
    ("تصمیمات مجمع عمومی عادی به طور فوق العاده دوره ۱۲ ماهه", 2, "assemblyExtra"),
    ("تصمیمات مجمع عمومی عادی سالیانه: تقسیم سود نقدی به ازای هر سهم", 3, "dividend"),
    ("لغو مجمع عمومی فوق العاده مورخ ۱۴۰۵/۰۶/۲۰", 0, "assemblyChange"),
    ("تغییر زمان برگزاری مجمع عمومی عادی", 0, "assemblyChange"),
    ("اطلاعیه سررسید اوراق بهادار اجاره (صکوک)", 0, "bondMaturity"),
    ("افشای اطلاعات بااهمیت - پذیرش بازارگردانی اوراق مرابحه", 0, "bondMaturity"),
    ("امیدنامه پذیرش در بورس / فرابورس ایران", 0, "ipo"),
    ("نشریه عرضه اوراق بهادار با ضمانت اصل سرمایه و سود", 0, "ipo"),
    ("اطلاعیه عرضه اولیه سهام شرکت ...", 0, "ipo"),
    ("تصمیمات مجمع درباره افزایش سرمایه از محل آورده نقدی", 0, "capitalIncrease"),
    ("معرفی /تغییر در ترکیب اعضای هیئت مدیره/مدیر عامل", 0, "other"),
]

fails = []
print("─" * 74)
print("۱) classify_tid + category_of (پایتون)")
print("─" * 74)
for title, want_tid, want_cat in CASES:
    got_tid = cf.classify_tid(title)
    got_cat = cf.category_of(title, got_tid)
    ok = (got_tid == want_tid and got_cat == want_cat)
    print("  %s tid=%-2s cat=%-16s | %s" % (
        "OK " if ok else "FAIL", got_tid, got_cat, title[:52]))
    if not ok:
        fails.append("py: %r → tid %s (انتظار %s), cat %s (انتظار %s)"
                     % (title[:40], got_tid, want_tid, got_cat, want_cat))

# ── ۲) همان عنوان‌ها را با classifyِ واقعیِ calendarService.js بسنج ─────────
# نکته: تابع از خود فایل استخراج می‌شود (نه کپی دست‌دوم)، وگرنه تست می‌تواند
# از کد واقعی drift کند و یکا بودن را دروغ تأیید کند.
SVC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                   "static", "calendar", "calendarService.js")
src = io.open(SVC, encoding="utf-8").read()
i = src.index("function classify(")
depth, j, started = 0, i, False
while j < len(src):
    if src[j] == "{":
        depth += 1; started = True
    elif src[j] == "}":
        depth -= 1
        if started and depth == 0:
            j += 1
            break
    j += 1
CLASSIFY_SRC = src[i:j]
assert "return 'other'" in CLASSIFY_SRC, "classify() extraction failed"

JS = (CLASSIFY_SRC + "\n"
      "var cases = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));\n"
      "console.log(JSON.stringify(cases.map(function (c) { return classify(c[0], '', c[1]); })));\n")
pairs = [[t, cf.classify_tid(t)] for t, _, _ in CASES]
tf = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
tf.write(__import__("json").dumps(pairs, ensure_ascii=False))
tf.close()
jf = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8")
jf.write(JS); jf.close()
try:
    res = subprocess.run(["node", jf.name, tf.name], capture_output=True, text=True,
                         encoding="utf-8")
    if res.returncode != 0:
        print("\n  (node در دسترس نیست یا خطا — تست یکا رد شد: %s)" % res.stderr[:200])
        fails.append("node unavailable: " + res.stderr[:120])
    else:
        js_out = __import__("json").loads(res.stdout.strip())
        print("\n" + "─" * 74)
        print("۲) یکای پایتون ↔ JS")
        print("─" * 74)
        for (title, _, want_cat), js_cat in zip(CASES, js_out):
            py_cat = cf.category_of(title, cf.classify_tid(title))
            ok = py_cat == js_cat == want_cat
            print("  %s py=%-16s js=%-16s | %s" % ("OK " if ok else "FAIL",
                                                   py_cat, js_cat, title[:44]))
            if not ok:
                fails.append("parity: %r py=%s js=%s" % (title[:40], py_cat, js_cat))
finally:
    os.unlink(tf.name); os.unlink(jf.name)

# ── ۳) چرخش IP روی یک تابع مرجع (v9.3) ──────────────────────────────────────
print("\n" + "─" * 74)
print("۳) تمرکز چرخش IP — adb_rotate_ip → codal_fetcher.rotate_ip_via_adb")
print("─" * 74)


def _check(cond, msg):
    print("  %s %s" % ("PASS" if cond else "FAIL", msg))
    if not cond:
        fails.append(msg)


# بدنهٔ محلی حذف شده و فقط واگذاری می‌کند — نه توگلِ خودی.
_src = __import__("inspect").getsource(cf.adb_rotate_ip)
_check("rotate_ip_via_adb(" in _src,
       "adb_rotate_ip به codal_fetcher.rotate_ip_via_adb واگذار می‌کند")
_check("subprocess.run" not in _src,
       "بدنهٔ محلیِ توگلِ adb حذف شده (دو منبع حقیقت نبود)")
_check("time.sleep" not in _src,
       "هیچ مکثِ توگلِ محلی‌ای باقی نمانده — تأخیرها مالِ تابع مرجع هستند")
_check(not getattr(cf.adb_rotate_ip, "__defaults__", None),
       "پارامترهای enable_wait/recover_waitِ توگلِ کوتاه حذف شده‌اند")

# واگذاری واقعاً به همان تابع می‌رود و خروجی‌اش bool است.
_calls = []
_orig = cf._cf.rotate_ip_via_adb
cf._cf.rotate_ip_via_adb = lambda quiet=False: (_calls.append(quiet) or True)
try:
    _r = cf.adb_rotate_ip()
    _check(_r is True, "adb_rotate_ip() خروجیِ تابع مرجع را bool برمی‌گرداند")
    _check(len(_calls) == 1, "تابع مرجع دقیقاً یک‌بار فراخوانی شد (نه بیشتر)")
finally:
    cf._cf.rotate_ip_via_adb = _orig

# مسیرِ واقعیِ مصرف‌کننده: polite_get روی ۴۲۹/WAF باید به همان تابع مرجع برسد.
# نکته: polite_get ابتدا session.get(...) را صدا می‌زند، پس فیک باید متد get
# داشته باشد که یک response با status_code=429 برمی‌گرداند (بدنهٔ HTMLِ WAF).
_calls.clear()
cf._cf.rotate_ip_via_adb = lambda quiet=False: (_calls.append(quiet) or True)
try:
    class _Resp429:
        status_code, headers = 429, {}

        def json(self):
            raise ValueError("WAF html")

    class _BlockedSession:
        def get(self, *a, **k):
            return _Resp429()

    _st = {"req": 0}
    try:
        cf.polite_get(_BlockedSession(), {}, rotate=True,
                      max_backoffs=2, stats=_st)
    except RuntimeError:
        pass            # انتظار می‌رود — همهٔ تلاش‌ها ۴۲۹ می‌شوند
    _check(len(_calls) >= 1,
           "polite_get روی ۴۲۹/WAF به تابع مرجع می‌رسد (rotate واقعاً وصل است)")
finally:
    cf._cf.rotate_ip_via_adb = _orig

print("\n" + "=" * 74)
if fails:
    print("❌ %d شکست:" % len(fails))
    for f in fails:
        print("   - " + f)
    sys.exit(1)
print("✅ همهٔ %d حالت + یکای JS + تمرکز چرخش IP پاس شد" % len(CASES))
