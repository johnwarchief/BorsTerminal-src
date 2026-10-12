# -*- coding: utf-8 -*-
"""گاردِ هم‌کلیدیِ پخت و اجرا — ریشۀ `baked_fail: 1` درِ بستۀ کاملِ موبایل.

شاهدِ خام (سازندۀ واقعی روی snapshotِ مستقل، ۲۰۲۶-۱۰-۱۳، پیش ازِ اصلاح):

    [bake] 922 نماد × 5 اندپوینت…
      [skip] /api/fundamental/%D9%85%D8%B9%D9%8A%D8%A7%D8%B1 → 404
    [bake] baked=4627 skip=1

و سنجشِ خودِ داده درِ همان snapshot (جدول‌به‌جدول، با نامِ ستونِ درست):

    instruments.l_val18      'معيار '  length 6  (ي عربی U+064A + فاصلۀ انتهایی)
    price_history.symbol     'معيار '  365 ردیف
    financial_statements     'معيار '  8 ردیف   + 'عیار' (بی‌«مع») ۱ ردیف
    monthly_sales            'معيار '  3 ردیف   + 'معیار' (ی فارسی) ۱ ردیف
    codal_notices            'معيار '  39 ردیف  + 'معیار' ۱ ردیف

یعنی نماد درِ بانک **با فاصلۀ انتهایی** ذخیره شده؛ رابطِ کاربر همان را عیناً
می‌فرستد (`useFtsCard.ts: encodeURIComponent(symbol)`) و `resolvers.ts:201`
هم کلید را از مسیرِ decodeشده می‌سازد، ولی سازنده درِ `_symbols_from_screener`
با `.strip()` فاصله را می‌کَند. پس:

  • درخواستِ بیلد `/api/fundamental/معيار` (بی‌فاصله) ⇒ ۴۰۴ ⇒ همان یکِ skip؛
  • و مهم‌تر: **کلیدِ پختۀ آفلاین** با «کلیدِ درخواستِ موقعِ اجرا» یکی نبود،
    یعنی کارتِ آن نماد رویِ گوشی خالی می‌ماند حتی اگر بیلد سبز شده بود.

این گارد همان هم‌کلیدی را می‌سنجد. **کلیدِ داوری این است: پخت و اجرا باید یکِ
 رشته را بخوانند، نه دو رشتهٔ نرمال‌شدهٔ متفاوت** — نرمال‌سازیِ یک‌طرفه
 (clamp در یک سو) حقیقتِ دوم می‌سازد، نه رفعِ مشکل.

  ت۱  سازنده نماد را عیناً نگه می‌دارد و فقط ردیفِ بی‌نماد/فضا را می‌اندازد
  ت۲  مسیرِ encodeشده بعد ازِ decode دقیقاً همان نماد می‌شود (پس درخواست و کلید
      یکی‌اند) — با نویسه‌هایِ دردسر‌ساز: فضا، /، ـ، %، '، (، )، *، ~، ZWNJ
  ت۳  کنترلِ منفی: همان داده با رفتارِ پیشین (`.strip()`) کلیدِ ناهمخوان
      می‌سازد و گارد می‌فهمد (سنجه کور نیست)
  ت۴  رویِ snapshotِ واقعی: نمادِ خام ۲۰۰ می‌گیرد و نمادِ بریده‌شده ۴۴۰/۴۰۴ —
      یعنی strip نکردن، درخواستِ درست است نه دور زدنِ خطا
  ت۵  هیچ کلیدِ تکراری‌ای از فهرستِ نمادها درنمی‌آید (یک ردیف، یک بسته)
  ت۶  شمارندۀ سازنده دست‌نخورده است (رفع با پنهان‌کردنِ شکست نبود)

اجرا:  python dev/mobile_bake_key_parity_v1079.py
"""
import os
import sys
import importlib.util
from urllib.parse import quote, unquote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SNAP = os.path.join(ROOT, "_audit", "tmp", "stage4", "market_src.db")
PASS = FAIL = 0


def chk(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   %s" % label)
    else:
        FAIL += 1
        print("  FAIL %s   %s" % (label, str(extra)[:200]))


def load_builder():
    spec = importlib.util.spec_from_file_location(
        "bms_under_test", os.path.join(ROOT, "scripts", "build_mobile_snapshot.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


bms = load_builder()

# ── ت۱ ──────────────────────────────────────────────────────────────────────
DIRTY = "معيار "            # همان چیزی که اسکرینر می‌دهد: ي عربی + فاصلۀ انتهایی
FA = "معیار"
payload = {"data": [{"symbol": DIRTY}, {"symbol": FA}, {"symbol": "  "},
                    {"symbol": None}, {"symbol": ""}, {"symbol": "شپنا"}]}
syms = bms._symbols_from_screener(payload)
chk(DIRTY in syms, "ت۱الف: نمادِ فاصلهدار عیناً می‌ماند (strip نمی‌شود)", repr(syms))
chk("  " not in syms and "" not in syms and None not in syms,
    "ت۱ب: فقط ردیفِ بی‌نماد/فضا انداخته می‌شود", repr(syms))
chk(len(syms) == 3, "ت۱پ: سه نمادِ واقعی از شش ردیف", len(syms))

# ── ت۲ ──────────────────────────────────────────────────────────────────────
TRICKY = [DIRTY, "حق تقدم/آذر2", "عىار", "آ س پ3", "a'b(c)*~d", "100%", "ف\u200cص",
          "di\u00e7", "  leading"]
bad = []
for s in TRICKY:
    enc = quote(s, safe="")
    if unquote("/api/fundamental/" + enc).split("/api/fundamental/")[1] != s:
        bad.append(s)
chk(not bad, "ت۲: مسیرِ encodeشده بعد ازِ decode همان نماد می‌ماند (کلیدِ پخت = کلیدِ اجرا)", bad)

# همان زنجیرۀ واقعی: کلیدِ پخت (`fundamental/<sym>`) با کلیدِ resolver
# (`decodeURIComponent(pathname)` ⇒ `fundamental/<sym>`) مقایسه می‌شود
keys_baked = ["fundamental/" + s for s in syms]
keys_runtime = ["fundamental/" + unquote("/api/fundamental/" + quote(s, safe="")).split("/")[-1]
                for s in syms]
chk(keys_baked == keys_runtime, "ت۲ب: کلیدهایِ پخت و اجرا سطر‌به‌سطر یکی‌اند",
    "%r vs %r" % (keys_baked, keys_runtime))

# ── ت۳ ──────────────────────────────────────────────────────────────────────
old_style = [(r.get("symbol") or "").strip() for r in payload["data"] if (r.get("symbol") or "").strip()]
chk(DIRTY not in old_style and DIRTY.strip() in old_style,
    "ت۳ کنترلِ منفی: رفتارِ پیشین نمادِ خام را به رشتهٔ دیگری بدل می‌کند ⇒ گارد این را می‌بیند",
    repr(old_style))
chk("fundamental/" + DIRTY != "fundamental/" + DIRTY.strip(),
    "ت۳ب: خودِ تفاوتِ کلید (فاصله/بی‌فاصله) هم اثبات شده")

# ── ت۴ ──────────────────────────────────────────────────────────────────────
if os.path.exists(SNAP):
    import bors_config
    bors_config.DB_PATH = SNAP
    user_c = os.path.join(ROOT, "_audit", "tmp", "stage4", "user.db")
    if os.path.exists(user_c):
        bors_config.USER_DB_PATH = user_c
    from fastapi.testclient import TestClient
    import app as appmod
    c = TestClient(appmod.app, base_url="http://127.0.0.1:8001")
    r_raw = c.get("/api/fundamental/" + quote(DIRTY, safe=""))
    r_cut = c.get("/api/fundamental/" + quote(DIRTY.strip(), safe=""))
    chk(r_raw.status_code == 200, "ت۴الف: رویِ دادۀِ واقعی، نمادِ خام کارت می‌دهد", r_raw.status_code)
    chk(r_cut.status_code == 404, "ت۴ب: نمادِ بریده‌شده وجود ندارد ⇒ ۴۰۴ می‌ماند (بی‌اختراع)",
        r_cut.status_code)
    dirty_rows = [s for s in bms._symbols_from_screener(
        {"data": c.get("/api/screener").json().get("data", [])}) if s != s.strip()]
    print("       (سنجشِ واقعی: %d نمادِ اسکرینر، %d تای آنها فاصلۀ انتهایی/اولیه دارند: %r)"
          % (len(bms._symbols_from_screener({"data": c.get("/api/screener").json().get("data", [])})),
             len(dirty_rows), dirty_rows[:4]))
    chk(len(dirty_rows) >= 1, "ت۴پ: حداقلِ یکِ نمادِ فاصلهدار درِ جهانِ واقعی هست (سنجه بی‌مورد نیست)")
else:
    print("       (ت۴ رویِ snapshotِ مستقل سنجیده می‌شود؛ نبودش رأی نمی‌شمارد: %s)" % SNAP)

# ── ت۵ ──────────────────────────────────────────────────────────────────────
real = bms._symbols_from_screener(payload)
chk(len(set(real)) == len(real), "ت۵: کلیدِ تکراری ازِ فهرستِ نماد درنمی‌آید", real)

# ── ت۶ ──────────────────────────────────────────────────────────────────────
src = open(os.path.join(ROOT, "scripts", "build_mobile_snapshot.py"), encoding="utf-8").read()
chk("fail += 1" in src and '"baked_fail": fail' in src,
    "ت۶: سازنده هنوز هر خطای واقعی را می‌شمارد و درِ manifest می‌نویسد")
chk(".strip() if isinstance(r, dict)" not in src,
    "ت۶ب: stripِ قدیمی درِ خوانندۀ نمادها نمانده است")

print("\nmobile_bake_key_parity_v1079: %d passed / %d failed" % (PASS, FAIL))
sys.exit(0 if FAIL == 0 else 1)
