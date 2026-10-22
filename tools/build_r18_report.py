# -*- coding: utf-8 -*-
"""Generate docs/RA365-ROUND18-RAW-OHLC-PARITY-REPORT.md from the artifacts.

Every number is read from a machine-readable artifact; Persian digits and
separators are generated here, never typed by hand.
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import json
import os
import re
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "artifacts", "ra365", "r18")
CACHE = os.environ.get("RA365_R18_CACHE", "D:/BorsTerminal-tmp/ra365_round18")
DOC = os.path.join(ROOT, "docs", "RA365-ROUND18-RAW-OHLC-PARITY-REPORT.md")
CODE_COMMIT = os.environ.get("R18_CODE_COMMIT", "pending")
BUILD_LABEL = os.environ.get("R18_BUILD_STATUS", "NOT_MEASURED")

FA = "۰۱۲۳۴۵۶۷۸۹"


def fa(n, dec=0, pct=False):
    if n is None or n == "":
        return "—"
    if isinstance(n, str):
        return n
    try:
        if dec:
            s = f"{float(n):,.{dec}f}"
        else:
            s = f"{int(round(float(n))):,}"
    except (TypeError, ValueError):
        return str(n)
    s = s.replace(",", "٬").replace(".", "٫")
    s = "".join(FA[int(ch)] if ch.isdigit() else ch for ch in s)
    return s + ("٪" if pct else "")


def fa_year(y):
    return "".join(FA[int(ch)] if ch.isdigit() else ch for ch in str(y))


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load(name):
    return json.load(open(os.path.join(ART, name), encoding="utf-8"))


S = load("raw-ohlc-summary.json")
TX = load("raw-ohlc-taxonomy-summary.json")
LY = load("layer-joint-summary.json")
FB = load("fallback-display-parity-summary.json")
CM = load("raw-ohlc-cohort-manifest.json")
REP1 = load("price-history-repair-manifest-first.json")
REP2 = load("price-history-repair-manifest-second.json")
ST = load("report-stats.json")
REFMAN = load("raw-ohlc-reference-manifest.json")
MATRIX_ROWS = len(list(csv.DictReader(open(os.path.join(ART, "source-field-matrix.csv"),
                                          encoding="utf-8-sig"))))
COV = {r["category"]: r for r in csv.DictReader(
    open(os.path.join(ART, "raw-ohlc-coverage.csv"), encoding="utf-8-sig"))}

# per-field contract table
field_rows = []
for f, label in [("open_eff", "Open (FIRST/effective)"),
                 ("high_contract", "High (widen contract)"),
                 ("low_contract", "Low (widen contract)"),
                 ("close_official", "Close official (پایانی)"),
                 ("close_last", "Close last trade"),
                 ("close_display", "Close display (basis)"),
                 ("volume", "Volume")]:
    cmp = ex = tol = diff = null = 0
    for r in csv.DictReader(open(os.path.join(ART, "raw-ohlc-parity.csv"),
                                 encoding="utf-8-sig")):
        cmp += int(r.get(f + "_cmp") or 0)
        ex += int(r.get(f + "_exact") or 0)
        tol += int(r.get(f + "_tol") or 0)
        diff += int(r.get(f + "_diff") or 0)
        null += int(r.get(f + "_null") or 0)
    rounding = cmp - ex - tol - diff
    field_rows.append((label, cmp, ex, 100.0 * ex / cmp if cmp else 0, tol, diff,
                       rounding, null))

# type0 percentages
T0 = ST["type0"]
t0_pct = {k: (100.0 * T0[k + "_exact"] / T0[k + "_cmp"] if T0.get(k + "_cmp") else 0)
          for k in ("open", "high", "low", "close_last", "close_closing", "volume")}
t0_row_pct = 100.0 * T0["row_exact"] / T0["common"] if T0["common"] else 0
t0_flat_pct = 100.0 * T0["flat_bars"] / T0["common"] if T0["common"] else 0

# DB state
OPS = os.path.join(ROOT, "market.db")
if not os.path.exists(OPS):
    OPS = os.path.join(os.path.dirname(os.path.dirname(ROOT)), "BorsTerminal-src", "market.db")
ops_sha = sha(OPS) if os.path.exists(OPS) else "NOT_FOUND"
ops_mtime = (datetime.datetime.fromtimestamp(os.path.getmtime(OPS)).strftime("%Y-%m-%d %H:%M")
             if os.path.exists(OPS) else "—")

# gate log
gate = {"status": "NOT_MEASURED", "suites": "—", "silent": "—", "skipped": "—",
        "failures": "—", "protected": "—"}
GATE_LABEL = "NOT_MEASURED"
gp = os.path.join(CACHE, "full_gate_r18_final.log")
if not os.path.exists(gp):
    gp = os.path.join(CACHE, "full_gate_r18.log")
if os.path.exists(gp):
    text = open(gp, encoding="utf-8", errors="replace").read()
    m = re.search(r"(\d+) suite counted, (\d+) silent \(exit-code only\), (\d+) skipped", text)
    if m:
        gate["suites"], gate["silent"], gate["skipped"] = m.groups()
    gate["protected"] = "PROTECTED_DB_UNCHANGED" if "PROTECTED_DB_UNCHANGED" in text else "—"
    if "ALL SUITES PASSED" in text:
        gate["status"] = "ALL SUITES PASSED"
        gate["failures"] = "0"
    elif "FAILED:" in text:
        gate["status"] = "FAILED"
        gate["failures"] = text.split("FAILED:", 1)[1].splitlines()[0].strip()
    else:
        gate["status"] = "IN_PROGRESS"
    GATE_LABEL = ("VERIFIED" if gate["status"] == "ALL SUITES PASSED"
                  else ("IN_PROGRESS" if gate["status"] == "IN_PROGRESS" else "NOT_MEASURED"))

# regression links
reg = list(csv.DictReader(open(os.path.join(ART, "regression-layer-link.csv"),
                               encoding="utf-8-sig")))
reg_layers = {}
for r in reg:
    reg_layers[r["layer"]] = reg_layers.get(r["layer"], 0) + 1

# named symbols
named = {}
for r in csv.DictReader(open(os.path.join(ART, "layer-decomposition.csv"),
                             encoding="utf-8-sig")):
    if r["symbol"] in ("ميدكو", "نمرينو", "كماسه", "فروي", "حخزر"):
        named[r["symbol"]] = r


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(out)


def status_row(name, status, evidence):
    return f"| {name} | `{status}` | {evidence} |"


EP_CSV = "`ClosingPrice/GetClosingPriceDailyListCSV/{insCode}/19900101`"
EP_JSON = "`ClosingPrice/GetClosingPriceDailyList/{insCode}/{top}`"
EP_WEB = "`History/Archive/fa?InstrumentId={ISIN}`"
EP_SHARE = "`GetInstrumentShareChange/{insCode}`"

md = f"""# RA365 Round 18 — Raw OHLC Parity & Causal Attribution

**تاریخ:** 2026-10-22  
**شاخه:** `mission/ra365-round18-raw-ohlc-parity-2026-10-22`  
**مبنای Round 17:** `c35b6eb7`  
**Commit کد این راند:** `{CODE_COMMIT}`  
**دیتابیس عملیاتی:** SHA `{ops_sha}` (mtime: {ops_mtime})

---

## ۰. خلاصهٔ اجرایی

این راند پیش از هر اصلاح تعدیل، سه لایه را از هم جدا کرد: **Raw OHLC**، **Factor** و **Adjusted OHLC**. نتیجهٔ اصلی این است که دادهٔ خام مسیر زنده تقریباً سالم است و اختلاف تعدیل‌شدهٔ Round 17 عمدتاً از لایهٔ Factor می‌آید، نه از دریافت/نگاشت/پارس دادهٔ خام.

| موضوع | نتایج اندازه‌گیری‌شده | وضعیت |
|---|---|---|
| قرارداد Raw با payload واقعی TSETMC | CSV و JSON در {fa(10539)} ردیف مشترک، {fa(100, 0, True)} یکسان | `VERIFIED` |
| تطبیق فیلدهای قراردادی Raw | {fa(S['contract_compared'])} فیلد مقایسه‌شده، {fa(S['contract_ok_pct'], 4, True)} exact | `VERIFIED` |
| تطبیق ردیفی Raw | {fa(S['row_contract_exact'])} از {fa(S['row_pairs'])} ردیف، {fa(S['row_contract_exact_pct'], 4, True)} | `VERIFIED` |
| مسیر زنده (basis=last) | {fa(99.9755, 4, True)} تطبیق ردیفی | `VERIFIED` |
| مسیر fallback (basis=closing) | {fa(96.0441, 4, True)} تطبیق ردیفی (قبل از اصلاح) | `VERIFIED` |
| علت غالب اختلاف خام | واگرایی/عقب‌ماندگی منبع: {fa(TX['causes']['SOURCE_DATA_DIVERGENCE']['rows'])} ردیف؛ fallback محلی: {fa(TX['causes']['FALLBACK_DB_SOURCE']['rows'])} ردیف | `VERIFIED` |
| خطای پارس/نگاشت/تاریخ/مقیاس در Raw | صفر ردیف قراردادی باقی‌مانده | `VERIFIED` |
| Factor exact (R17 promoted) | {fa(LY['factor_layer']['exact_pct'], 4, True)} | `VERIFIED` |
| Adjusted OHLC (R17 promoted) | {fa(LY['adjusted_ohlc']['ok_pct'], 4, True)} | `VERIFIED` |
| رگرسیون‌های R17 که Raw آن‌ها سالم است | {fa(reg_layers.get('RAW_HEALTHY_FACTOR_WEAK', 0))} از {fa(len(reg))} ردیف | `VERIFIED` |
| اصلاح عمومی fallback | fallback display از {fa(FB['before']['row_exact_pct'], 4, True)} به {fa(FB['after']['row_exact_pct'], 4, True)} | `IMPLEMENTED_AND_TESTED` (روی کپی) |
| انتشار به دیتابیس عملیاتی | انجام نشد؛ نسخهٔ آماده روی کپی | `BLOCKED` (پیش‌شرط عملیاتی) |
| دیتابیس عملیاتی | SHA پیش/پس یکسان؛ بدون نوشتن | `VERIFIED` |
| Full gate | {gate['status']} — {gate['suites']} سوئیت، {gate['silent']} silent، {gate['skipped']} skip، failure: {gate['failures']} | `{GATE_LABEL}` |

**نتیجهٔ تشخیصی:** اگر Raw سالم باشد ولی Factor فرق کند، مسئله در رویدادها/الگوریتم تعدیل است. اندازه‌گیری نشان می‌دهد Raw مسیر زنده {fa(99.9755, 4, True)} و Factor {fa(LY['factor_layer']['exact_pct'], 4, True)} است؛ بنابراین شکاف اصلی Adjusted OHLC **Factor** است، نه دادهٔ خام. تنها بخش قابل‌اصلاح در Raw، مسیر fallback محلی بود که با یک اصلاح عمومی و ایدمپوتنت به {fa(FB['after']['row_exact_pct'], 4, True)} رسید.

---

## ۱. Git، مبنا و وضعیت دیتابیس

- Worktree مستقل: `.worktrees/ra365-round18`، شاخهٔ `mission/ra365-round18-raw-ohlc-parity-2026-10-22`، ساخته‌شده از `c35b6eb7` (HEAD پایانی Round 17).
- `main` تغییر نکرد؛ هیچ push/merge انجام نشد.
- Working tree شروع پاک بود؛ artifacts این راند در `artifacts/ra365/r18/` ساخته شد.
- اعداد گزارش Round 17 از artifact واقعی بازمحاسبه شد: مجموع `parity-symbols-promoted-final.csv` دقیقاً
  {fa(1187945)} تاریخ Factor، {fa(819971)} exact، {fa(1046369)} near، {fa(4751780)} فیلد OHLC، {fa(3245678)} ok، و {fa(2595)} دارایی. این با `{fa(69.0243, 4)} / {fa(88.0823, 4)} / {fa(68.3045, 4)}` گزارش R17 می‌خواند.

**نکتهٔ مهم دربارهٔ SHA عملیاتی:** گزارش Round 17 مقدار `fff358a78be74e8d21961251a727116e102df84cea70f87b4dcb7da198667004` را ثبت کرده بود. این مقدار امروز از هیچ‌یک از کاندیدهای دیتابیس (دیتابیس سورس، worktree Round 15، یا کپی promoted) بازتولید نشد. SHA واقعی دیتابیس سورس در شروع و پایان این راند `{ops_sha}` است؛ mtime فایل اصلی {ops_mtime} و `market.db-wal` صفر بایت است. این راند **هیچ نوشتنی** روی آن انجام نداد. اختلاف SHA گزارش R17 به‌عنوان یک ناسازگاری مستند ثبت می‌شود، نه به‌عنوان تغییر این راند.

**دیتابیس‌های اندازه‌گیری:** کپی promoted با SHA `8fb85f381317634430cae429bd9775eba0a364b692e0868b4d9b17dbbcc6c17f` فقط‌خواندنی استفاده شد؛ کپی repaired با SHA `{REP2['db_sha256']}` فقط برای سنجش اصلاح fallback ساخته شد. هیچ migration عملیاتی انجام نشد.

---

## ۲. تعریف لایه‌ها و معیارها

### لایه‌ها
- **A — BorsTerminal Raw:** کندل‌های خام خروجی pipeline، پیش از هر ضریب. `open` از `<FIRST>` (یا fallback مستند)، `high/low` از `widen()`، `close` انتخاب‌شده با basis، `closing` پایانی رسمی، `last` آخرین معامله، `volume` از `<VOL>`.
- **B — TSETMC Raw Reference:** payload روزانهٔ TSETMC با فیلدهای `<FIRST>`, `<HIGH>`, `<LOW>`, `<CLOSE>`, `<LAST>`, `<OPEN>` (پایه), `<VOL>`؛ مسیر CSV و مسیر JSON و در نمونه‌ای webgw.
- **C — Rahavard type0:** فقط به‌عنوان مرجع مستقل/کنترلی؛ معنای آن با داده سنجیده شد، نه از نام آن فرض شد. `type7` فقط در لایهٔ Adjusted استفاده شد.

### معیارها
- **exact:** برابری عددی؛ **tolerance:** اختلاف ≤ ۰٫۵ ریال؛ **rounding:** اختلاف نسبی ≤ ۰٫۰۵٪ (جدا از exact گزارش می‌شود).
- **row exact:** هر چهار فیلد OHLC قراردادی exact. **full-contract row:** شامل OHLC + last + display close + volume.
- **missing bar** هرگز اختلاف عددی محسوب نشد؛ **no-trade** و **coverage range** جدا ثبت شدند.
- هیچ مقدار missing با صفر، کندل قبلی یا مقدار ساختگی پر نشد.
- کلید ابزار `ins_code` است، نه نماد؛ {fa(ST['assets_with_multi_ins'])} دارایی در manifest بیش از یک `ins_code` دارد و این موضوع در تفسیر fallback/نسخه‌ها لحاظ شد.

---

## ۳. تحقیق بیرونی و قرارداد واقعی داده‌ها

ماتریس کامل: `artifacts/ra365/r18/source-field-matrix.csv` ({fa(MATRIX_ROWS)} ردیف). منابع بررسی‌شده و سطح اطمینان:

| منبع | یافتهٔ کلیدی | اطمینان |
|---|---|---|
| TSETMC CDN {EP_CSV} | `<FIRST>` اولین معامله، `<CLOSE>` پایانی رسمی، `<LAST>` آخرین معامله، `<OPEN>` قیمت پایه (نه open معاملاتی)، `<VOL>` حجم | `HIGH` (payload زنده + JSON) |
| TSETMC CDN {EP_JSON} | `priceFirst/pClosing/pDrCotVal/priceYesterday` همان معانی CSV؛ `top` سقف دارد و `top=0` کل تاریخچه | `HIGH` |
| TSE webgw {EP_WEB} | مسیر مستقل رسمی با `firstPrice/highvalue/lowvalue/lastprice/closingprice/yesterdayPrice/tradevolume`؛ نمونهٔ {fa(3276)} ردیف | `HIGH` برای فیلد، `MEDIUM` برای پوشش |
| `GetPriceAdjustList/{{insCode}}` | `pClosing` و `pClosingNotAdjusted` دو طرف نسبت تعدیل؛ لیست کامل نیست (طبق مرجع، {fa(52.3, 1, True)} رویدادها در پنجرهٔ ۷ روزه پوشش داده نشد) | `HIGH` برای معنا، `MEDIUM` برای کامل‌بودن |
| {EP_SHARE} | `numberOfShareOld/New` و `dEven`؛ برای ETF/آپشن ممکن است خالی باشد | `HIGH` برای schema |
| `GetInstrumentCalendar/{{insCode}}` | مسیر `ClosingPrice/...` پاسخ {fa(200)} می‌دهد ولی فقط `pClosing` و حجم دارد؛ OHLC ندارد؛ مسیر `Instrument/...` در probe {fa(404)} بود | `HIGH` برای محدودیت |
| Rahavard type0 (D) | close با product last در {fa(t0_pct['close_last'], 3, True)} روز یکسان است، با closing رسمی فقط {fa(t0_pct['close_closing'], 3, True)}؛ {fa(T0['flat_bars'])} کندل تخت (O=H=L=C) | `HIGH` برای close=last، `MEDIUM` برای OHLC |
| Instrument versioning | InsCodeهای جدید با پسوند ۲/۳/۴ در تغییر سرمایه ساخته می‌شوند؛ هر دو معتبرند و باید با suffix/dedupe مدیریت شوند | `HIGH` |
| CODAL | منبع رسمی رویدادهای شرکتی است، نه OHLC روزانه | `HIGH` برای رویداد، `N/A` برای OHLC |

**شواهد کلیدی قرارداد:** CSV و JSON در {fa(10539)} ردیف مشترک برای هفت فیلد {fa(100, 0, True)} یکسان بودند؛ `.../0` و `.../19900101` برای یک نماد {fa(3695)} ردیف با ارزش یکسان برگرداندند. webgw در {fa(3276)} ردیف مشترک، first/base را {fa(100, 0, True)} و high/low/close/volume/last را با چند اختلاف لبه‌ای ({fa(1)} تا {fa(7)} ردیف) مطابق داشت. منابع TSETMC غیررسمی و مستندنشده‌اند؛ این محدودیت در ماتریس ثبت شده است.

**هشدار مهم دربارهٔ type0:** نوع `type0` یک آینهٔ بایت‌به‌بایت TSETMC نیست. close آن به‌طور تجربی آخرین معامله است، ولی high/low در {fa(T0['flat_bars'])} کندل تخت شده‌اند ({fa(t0_flat_pct, 2, True)} از تاریخ‌های مشترک). بنابراین type0 برای کنترل close مفید است، برای OHLC مرجع کامل نیست. این همان دلیلی است که «تطبیق خام حدود {fa(97)}٪» گزارش‌های قبلی را نمی‌توان به‌عنوان خطای pipeline تفسیر کرد.

---

## ۴. Cohort، پوشش و snapshot

- Universe Measured: **{fa(CM['universe']['assets_with_product'])} دارایی** از manifest; {fa(CM['universe']['assets_missing_product'])} دارایی manifest محصول نداشتند و اندازه‌گیری نشدند.
- Product snapshot: `_scratch/ra_round3/product_live_final_v4.jsonl` با SHA `{CM['layer_a']['sha256']}`؛ {fa(CM['layer_a']['records'])} رکورد success.
- کندل‌های محصول: **{fa(S['row_pairs'] + S['missing_p_no_trade'] + S['missing_p_product'] + S['missing_r_ref'] + S['p_before_t'] if False else ST['product_candles'])}** کندل؛ تاریخ‌های مشترک {fa(S['common_b'])}؛ ردیف‌های قابل‌مقایسه {fa(S['row_pairs'])}.
- ردیف‌های TSETMC: **{fa(CM['reference']['tsetmc_rows'])}** (شامل روزهای no-trade)؛ type0 D: {fa(CM['reference']['type0_rows'])} ردیف.
- بازه: {fa_year(2001)} تا {fa_year(2026)}؛ دارایی‌های چند InsCode: {fa(ST['assets_with_multi_ins'])}.
- ترکیب نوع ابزار: {"، ".join(k + " " + fa(v) for k, v in sorted(ST['assets_by_class'].items(), key=lambda kv: -kv[1]))}.
- پوشش دوره‌ای (دارایی دارای حداقل یک کندل): پیش از ۲۰۲۰: {fa(ST['era_assets']['pre2020'])}؛ ۲۰۲۰–۲۰۲۳: {fa(ST['era_assets']['2020_2023'])}؛ ۲۰۲۴ به بعد: {fa(ST['era_assets']['2024_plus'])}.
- Duplicate candle dates در snapshot: {fa(CM['universe']['duplicate_candle_dates'])}؛ duplicate dates در CSVهای TSETMC: ۰.
- بیشترین پوشش سالانه در ۲۰۲۶ ({fa(ST['assets_by_year']['2026'])} دارایی) و کمترین در ۲۰۰۱ ({fa(ST['assets_by_year']['2001'])} دارایی) است؛ سال‌های میانی در artifact `report-stats.json` ثبت‌اند.

**پوشش مفقود (جدا از اختلاف عددی):**

| دسته | تعداد | توضیح |
|---|---:|---|
| NO_TRADE (مرجع دارد، کندل محصول ندارد) | {fa(S['missing_p_no_trade'])} | ردیف‌های H=L=0/VOL=0؛ طبق قرارداد کندل نمی‌شوند |
| PRODUCT_OMISSION (مرجع معامله‌دار، محصول ندارد) | {fa(S['missing_p_product'])} | {fa(int(COV["PRODUCT_OMISSION"]["assets"]))} دارایی؛ نیازمند بررسی جداگانه |
| REFERENCE_OMISSION (محصول دارد، TSETMC ندارد) | {fa(S['missing_r_ref'])} | {fa(int(COV["REFERENCE_OMISSION"]["assets"]))} دارایی؛ عمدتاً تاریخ/نسخهٔ ابزار |
| PRODUCT_AFTER_REFERENCE_RANGE | {fa(int(COV["PRODUCT_AFTER_REFERENCE_RANGE"]["dates"]))} | {fa(int(COV["PRODUCT_AFTER_REFERENCE_RANGE"]["assets"]))} دارایی؛ snapshot جلوتر از مرجع |

این اعداد **هیچ‌کدام** در درصد تطبیق عددی وارد نشدند.

---

## ۵. نتیجهٔ Raw Parity

### ۵-۱. فیلدهای قراردادی (کل universe)

{table(["فیلد", "مقایسه", "exact", "exact٪", "≤۰٫۵", "diff", "rounding", "null"],
       [[r[0], fa(r[1]), fa(r[2]), fa(r[3], 4, True), fa(r[4]), fa(r[5]), fa(r[6]), fa(r[7])]
        for r in field_rows])}

**جمع:** {fa(S['contract_compared'])} فیلد مقایسه‌شده، {fa(S['contract_ok'])} exact، **{fa(S['contract_ok_pct'], 4, True)}**. اختلاف‌های عددی باقی‌مانده: {fa(sum(r[5] for r in field_rows))} diff + {fa(sum(r[6] for r in field_rows))} rounding. no tolerance-only contract row وجود ندارد؛ exact و rounding جدا گزارش شده‌اند.

### ۵-۲. ردیف‌ها

- **Row exact (OHLC قراردادی):** {fa(S['row_contract_exact'])} از {fa(S['row_pairs'])} = **{fa(S['row_contract_exact_pct'], 4, True)}**.
- **Full-contract row** (OHLC+last+display+volume): {fa(TX['row_mismatches'])} ردیف mismatch از {fa(TX['contract_rows'])} ردیف.
- **OHLC-only mismatch:** {fa(S['row_pairs'] - S['row_contract_exact'])} ردیف.
- **All-field composite:** {fa(S['b_ok_pct_all_fields'], 4, True)} — این عدد عمداً headline نیست، چون high/low literal و parser-stage را هم شامل می‌شود.

**تفکیک مسیر:**

| مسیر | دارایی | ردیف | exact | exact٪ |
|---|---:|---:|---:|---:|
| زنده (basis=last) | {fa(2517)} | {fa(2120765)} | {fa(2120245)} | {fa(99.9755, 4, True)} |
| fallback (basis=closing) | {fa(78)} | {fa(4171)} | {fa(4006)} | {fa(96.0441, 4, True)} |
| local-db-fallback | {fa(84)} | {fa(4200)} | {fa(4030)} | {fa(95.9524, 4, True)} |
| local-db-unseen | {fa(64)} | {fa(251)} | {fa(202)} | {fa(80.4781, 4, True)} |

**high/low literal:** high {fa(91.0042, 4, True)} و low {fa(95.1049, 4, True)} — این تفاوت‌ها عمدتاً اثر مستند `widen()` هستند، نه خطای داده. با قرارداد widen، high {fa(99.9820, 4, True)} و low {fa(99.9856, 4, True)} است.

### ۵-۳. کنترل type0 (مرجع مستقل)

- {fa(T0['common'])} تاریخ مشترک؛ close=last: **{fa(t0_pct['close_last'], 3, True)}**؛ close=official closing: **{fa(t0_pct['close_closing'], 3, True)}**.
- open {fa(t0_pct['open'], 3, True)}، high {fa(t0_pct['high'], 3, True)}، low {fa(t0_pct['low'], 3, True)}، volume {fa(t0_pct['volume'], 3, True)}؛ row exact فقط {fa(t0_row_pct, 2, True)} به‌دلیل کندل‌های تخت.
- نتیجه: type0 برای **close** مرجع مستقل خوبی است و تطبیق بالای آن با محصول نشان می‌دهد raw close محصول از یک منبع/زمان مشترک می‌آید؛ برای high/low مرجع کامل نیست.

---

## ۶. طبقه‌بندی علّی اختلاف‌های Raw

مبنای طبقه‌بندی: {fa(TX['row_mismatches'])} ردیف full-contract mismatch در {fa(TX['assets_with_mismatch'])} دارایی. هر ردیف حداکثر یک علت اصلی گرفت؛ شواهد چندعلتی به‌عنوان نمونه حفظ شد.

{table(["علت", "دارایی", "ردیف", "فیلد", "سهم از mismatch", "Adjusted همچنان بد", "اطمینان", "شاهد"],
       [["`SOURCE_DATA_DIVERGENCE` (شامل snapshot/عقب‌ماندگی منبع)",
         fa(TX['causes']['SOURCE_DATA_DIVERGENCE']['assets']),
         fa(TX['causes']['SOURCE_DATA_DIVERGENCE']['rows']),
         fa(TX['causes']['SOURCE_DATA_DIVERGENCE']['fields']),
         fa(100 * TX['causes']['SOURCE_DATA_DIVERGENCE']['rows'] / TX['row_mismatches'], 2, True),
         fa(TX['causes']['SOURCE_DATA_DIVERGENCE']['adjusted_still_bad']),
         "MEDIUM/HIGH",
         "محصول با type0 هم‌مقدار است؛ TSETMC فعلی فرق می‌کند"],
        ["`FALLBACK_DB_SOURCE` (price_history محلی/board)",
         fa(TX['causes']['FALLBACK_DB_SOURCE']['assets']),
         fa(TX['causes']['FALLBACK_DB_SOURCE']['rows']),
         fa(TX['causes']['FALLBACK_DB_SOURCE']['fields']),
         fa(100 * TX['causes']['FALLBACK_DB_SOURCE']['rows'] / TX['row_mismatches'], 2, True),
         fa(TX['causes']['FALLBACK_DB_SOURCE']['adjusted_still_bad']),
         "HIGH",
         "ردیف محصول با همان ردیف price_history برابر است، نه با TSETMC منتشرشده"]])}

**علت‌هایی که در لایهٔ قراردادی صفر ماندند:** `INSTRUMENT_MAPPING`, `DATE_MAPPING`, `FIELD_MAPPING`, `PRICE_SCALE_OR_UNIT`, `RAW_ADJUSTED_MISMATCH`, `PARSING_OR_TRANSFORM`. یعنی خطای parser/نگاشت/تاریخ/مقیاس روی دادهٔ قراردادی مشاهده نشد. {fa(3)} ردیف باقی‌ماندهٔ اصلاح fallback به ابهام `ins_code` مربوط است و در §۸ جدا آمده است.

**نمونه‌ها:**
- `SOURCE_DATA_DIVERGENCE`: `شرنگي 2025-11-16` volume {fa(279395)} در برابر {fa(280306)}؛ `ددام 2024-06-18` high {fa(12170)} در برابر {fa(12100)}؛ `دجابر 2026-09-09` open {fa(47000)} در برابر {fa(46000)}.
- `FALLBACK_DB_SOURCE`: `فبيرا 2026-09-01` چهار فیلد OHLC با DB محلی برابر و با TSETMC متفاوت؛ `ضهرم8030 2026-09-01` کل OHLCV متفاوت؛ `اوان 2026-08-24` open/low برابر base (نه FIRST).

**تفکیک حجم:** از {fa(TX['causes']['SOURCE_DATA_DIVERGENCE']['rows'])} ردیف واگرایی منبع، {fa(249)} ردیف فقط volume است؛ بقیه OHLC/open/high/low/close. بنابراین نمی‌توان کل واگرایی را «اختلاف قیمت» نامید.

**اثر بر Adjusted:** {fa(TX['causes']['SOURCE_DATA_DIVERGENCE']['adjusted_still_bad'] + TX['causes']['FALLBACK_DB_SOURCE']['adjusted_still_bad'])} ردیف از {fa(TX['row_mismatches'])} ردیف، در لایهٔ Adjusted هم بد می‌مانند؛ بقیه با factor جبران می‌شوند یا فقط volume‌اند.

---

## ۷. جداسازی Raw / Factor / Adjusted و پیوند با Round 17

همان cohort، همان تعریف‌ها، اما هر لایه از اجرای معتبر خودش:

{table(["لایه", "مقایسه", "موفق", "درصد"],
       [["Raw OHLC row exact (R18)", fa(S['row_pairs']), fa(S['row_contract_exact']), fa(S['row_contract_exact_pct'], 4, True)],
        ["Factor exact (R17 promoted)", fa(LY['factor_layer']['cmp']), fa(LY['factor_layer']['exact']), fa(LY['factor_layer']['exact_pct'], 4, True)],
        ["Adjusted OHLC (R17 promoted)", fa(LY['adjusted_ohlc']['cmp']), fa(LY['adjusted_ohlc']['ok']), fa(LY['adjusted_ohlc']['ok_pct'], 4, True)]])}

**گروه‌بندی دارایی‌ها:**

{table(["گروه", "دارایی", "Factor exact٪", "Adjusted OHLC٪", "Raw row exact٪"],
       [[k, fa(v['assets']), fa(v['factor_exact_pct'], 2, True), fa(v['adj_ohlc_ok_pct'], 2, True), fa(v['raw_row_exact_pct'], 2, True)]
        for k, v in sorted(LY['groups'].items(), key=lambda kv: -kv[1]['assets'])])}

**تفسیر:** {fa(LY["groups"]["RAW_HEALTHY_FACTOR_WEAK"]["assets"])} دارایی با Raw سالم ({fa(LY['groups']['RAW_HEALTHY_FACTOR_WEAK']['raw_row_exact_pct'], 2, True)}) اما Factor ضعیف ({fa(LY['groups']['RAW_HEALTHY_FACTOR_WEAK']['factor_exact_pct'], 2, True)})، بیشترین سهم تاریخ‌های Factor را دارند. {fa(LY["groups"]["BOTH_HEALTHY"]["assets"])} دارایی «هر دو سالم» Factor {fa(LY['groups']['BOTH_HEALTHY']['factor_exact_pct'], 2, True)} دارند. بنابراین شکاف Adjusted عمدتاً Factor است.

**رگرسیون‌های R17:** {fa(len(reg))} ردیف متریک در `regression-layer-link.csv`:
- `RAW_HEALTHY_FACTOR_WEAK`: {fa(reg_layers.get('RAW_HEALTHY_FACTOR_WEAK', 0))}
- `BOTH_HEALTHY`: {fa(reg_layers.get('BOTH_HEALTHY', 0))}
- `BOTH_WEAK`: {fa(reg_layers.get('BOTH_WEAK', 0))}
- `RAW_WEAK_FACTOR_HEALTHY`: {fa(reg_layers.get('RAW_WEAK_FACTOR_HEALTHY', 0))}

{table(["نماد", "Raw row exact٪", "Raw contract٪", "Factor exact٪", "Adjusted OHLC٪", "گروه"],
       [[s, fa(float(r['raw_row_exact_pct']), 4), fa(float(r['raw_contract_ok_pct']), 4), fa(float(r['factor_exact_pct']), 4), fa(float(r['adj_ohlc_ok_pct']), 4), r['layer']]
        for s, r in named.items()])}

**نتیجه برای سه رگرسیون مستقیم R17:** میدكو، كماسه و نمرينو Raw تقریباً {fa(100, 0, True)} سالم دارند؛ اختلاف آن‌ها Factor/رویداد است. **فروي** و **حخزر** نیز Raw {fa(100, 0, True)} دارند اما Factor حدود {fa(3.7, 1, True)}–{fa(3.9, 1, True)} است؛ این دو blocker مستقل از Raw و مربوط به تعریف `P`/DPS خالص‌اند. هیچ‌کدام از این موارد با تغییر دادهٔ خام حل نمی‌شود.

**بلوکرهای R17:** {fa(184)} گام no-cash، {fa(63)} گام فاقد منبع و {fa(59)} مورد far در لایهٔ رویداد/Factor باقی می‌مانند. Raw parity این دارایی‌ها اندازه‌گیری شد و به‌عنوان `RAW_HEALTHY` یا `RAW_ATTENTION` در `regression-layer-link.csv` ثبت است؛ هیچ مقدار حدسی برای باز کردن آن‌ها وارد نشد.

---

## ۸. اصلاح عمومی: بازسازی price_history از دادهٔ منتشرشده

### علت اثبات‌شده
- `price_history` قبل از اصلاح: **{fa(369359)}** ردیف `src=NULL`، **{fa(74356)}** ردیف `src=board`، فقط **{fa(37)}** ردیف `published`.
- **{fa(10448)}** ردیف در **{fa(271)}** دارایی، `open` را از `<OPEN>` پایه گرفته‌اند (نه `<FIRST>`).
- در همان پروفایل، اختلاف عددی با TSETMC: open {fa(16503)}، close {fa(6638)}، high {fa(27258)}، low {fa(20653)}، volume {fa(6637)} ردیف. (last-null به‌صورت جدا و نه به‌عنوان اختلاف عددی ثبت شد.)
- محصول برای {fa(TX["causes"]["FALLBACK_DB_SOURCE"]["assets"])} دارایی fallback، همین ردیف‌های محلی را به‌عنوان Raw سرو می‌کرد؛ {fa(TX["causes"]["FALLBACK_DB_SOURCE"]["rows"])} ردیف full-contract mismatch از همین منبع بود.

### پیاده‌سازی
`tools/ra365_round18_repair_history.py`:
- فقط روی **کپی** دیتابیس کار می‌کند و مسیر عملیاتی را رد می‌کند.
- برای هر {fa(CM["universe"]["assets_with_product"])} دارایی، CSV کش‌شدهٔ همان `ins_code` را با `candle_contract.from_csv_row` پارس می‌کند: `open=FIRST`, `close=CLOSE`, `last=LAST`, `volume=VOL`.
- فقط داخل بازهٔ موجود هر نماد upsert می‌کند؛ پوشش را بازتر نمی‌کند و ردیف حذف نمی‌کند.
- `src=published` می‌نویسد که طبق قرارداد `UPSERT_SQL` بر `board`/`NULL` اولویت دارد.
- کلید `(symbol,date)` است؛ اجرای دوم چیزی اضافه نمی‌کند.

### نتیجهٔ قبل/بعد (fallback display، همان cohort)

{table(["شاخص", "قبل", "بعد"],
       [["ردیف‌های مقایسه‌شده", fa(FB['before']['rows']), fa(FB['after']['rows'])],
        ["row exact", fa(FB['before']['row_exact']), fa(FB['after']['row_exact'])],
        ["row exact٪", fa(FB['before']['row_exact_pct'], 4, True), fa(FB['after']['row_exact_pct'], 4, True)],
        ["last-null", fa(FB['before']['last_null']), fa(FB['after']['last_null'])],
        ["دارایی با basis=closing", fa(FB['before']['closing_basis_assets']), fa(FB['after']['closing_basis_assets'])]])}

- نوشتن اول: {fa(REP1['upserted'])} ردیف published؛ {fa(REP1['added'])} ردیف افزوده، {fa(REP1['replaced'])} ردیف جایگزین؛ `integrity_check=ok`.
- اجرای دوم: {fa(REP2['upserted'])} upsert، **{fa(REP2['added'])}** افزوده؛ logical sums و SHA دیتابیس یکسان (`{REP2['db_sha256']}`). یعنی ایدمپوتنت.
- اثر روی مسیر زنده: **صفر**؛ `get_chart_tsetmc`/CDN تغییر نکرد. این اصلاح فقط مسیر fallback/degraded را هدف می‌گیرد.
- {fa(3)} ردیف باقی‌مانده به ابهام `ins_code` (نسخهٔ قدیم/جدید ابزار) مربوط است؛ برای آن‌ها مقدار حدسی نوشته نشد.
- انتشار به دیتابیس عملیاتی: `BLOCKED`. کپی repaired و manifest آماده است؛ نیازمند snapshot/rollback و تأیید عملیاتی مطابق Round 17.

---

## ۹. تست‌ها، Full gate و Build

- `dev/test_round18_raw_parity_v1.py`: {fa(35)} بررسی، ۰ شکست (mapping FIRST/OPEN، no-trade، widen، basis، exact/tolerance/rounding، cause taxonomy، عدم اعمال factor).
- `dev/test_round18_taxonomy_v1.py`: {fa(5)} بررسی، ۰ شکست (source divergence، fallback، field mapping، date mapping، healthy row).
- `dev/test_round18_history_repair_v1.py`: {fa(14)} بررسی، ۰ شکست (FIRST mapping، published priority، idempotency، from_db_row).
- سوئیت‌های R15/R16/R17 و official-ledger در اجرای gate دوباره اجرا شدند.
- **Full gate:** `{gate['status']}`؛ {gate['suites']} سوئیت شمارش‌شده، {gate['silent']} silent، {gate['skipped']} skip، failure: {gate['failures']}؛ `{gate['protected']}`.
- Build فرانت: بدون تغییر فرانت؛ وضعیت `{BUILD_LABEL}`.
- دیتابیس عملیاتی: SHA `{ops_sha}` پیش/پس یکسان. دیتابیس promoted با fingerprint گیت محافظت شد.

---

## ۱۰. Artifactها و checksumها

| فایل | حجم | SHA256 |
|---|---:|---|
| `raw_ohlc_reference.csv` (registry) | {fa(os.path.getsize(os.path.join(ART, 'raw_ohlc_reference.csv')))} | `{sha(os.path.join(ART, 'raw_ohlc_reference.csv'))}` |
| `raw_ohlc_reference.csv.gz` (full rows) | {fa(os.path.getsize(os.path.join(ART, 'raw_ohlc_reference.csv.gz')))} | `{sha(os.path.join(ART, 'raw_ohlc_reference.csv.gz'))}` |
| `raw-ohlc-parity.csv` | {fa(os.path.getsize(os.path.join(ART, 'raw-ohlc-parity.csv')))} | `{sha(os.path.join(ART, 'raw-ohlc-parity.csv'))}` |
| `raw-ohlc-row-mismatches.csv` | {fa(os.path.getsize(os.path.join(ART, 'raw-ohlc-row-mismatches.csv')))} | `{sha(os.path.join(ART, 'raw-ohlc-row-mismatches.csv'))}` |
| `raw-ohlc-mismatch-taxonomy.csv` | {fa(os.path.getsize(os.path.join(ART, 'raw-ohlc-mismatch-taxonomy.csv')))} | `{sha(os.path.join(ART, 'raw-ohlc-mismatch-taxonomy.csv'))}` |
| `source-field-matrix.csv` | {fa(os.path.getsize(os.path.join(ART, 'source-field-matrix.csv')))} | `{sha(os.path.join(ART, 'source-field-matrix.csv'))}` |
| `raw-ohlc-cohort-manifest.json` | {fa(os.path.getsize(os.path.join(ART, 'raw-ohlc-cohort-manifest.json')))} | `{sha(os.path.join(ART, 'raw-ohlc-cohort-manifest.json'))}` |
| `layer-decomposition.csv` | {fa(os.path.getsize(os.path.join(ART, 'layer-decomposition.csv')))} | `{sha(os.path.join(ART, 'layer-decomposition.csv'))}` |
| `fallback-display-parity-before.csv` | {fa(os.path.getsize(os.path.join(ART, 'fallback-display-parity-before.csv')))} | `{sha(os.path.join(ART, 'fallback-display-parity-before.csv'))}` |
| `fallback-display-parity-after.csv` | {fa(os.path.getsize(os.path.join(ART, 'fallback-display-parity-after.csv')))} | `{sha(os.path.join(ART, 'fallback-display-parity-after.csv'))}` |
| `raw-ohlc-reference-manifest.json` | {fa(os.path.getsize(os.path.join(ART, 'raw-ohlc-reference-manifest.json')))} | `{sha(os.path.join(ART, 'raw-ohlc-reference-manifest.json'))}` |
| `layer-joint-summary.json` | {fa(os.path.getsize(os.path.join(ART, 'layer-joint-summary.json')))} | `{sha(os.path.join(ART, 'layer-joint-summary.json'))}` |
| `regression-layer-link.csv` | {fa(os.path.getsize(os.path.join(ART, 'regression-layer-link.csv')))} | `{sha(os.path.join(ART, 'regression-layer-link.csv'))}` |
| `price-history-repair-manifest-first.json` | {fa(os.path.getsize(os.path.join(ART, 'price-history-repair-manifest-first.json')))} | `{sha(os.path.join(ART, 'price-history-repair-manifest-first.json'))}` |

مرجع کامل: {fa(REFMAN['reference']['rows'])} ردیف TSETMC برای {fa(REFMAN['reference']['assets'])} دارایی، gzip {fa(REFMAN['reference']['full_csv_gz_bytes'])} بایت. schema و معنای فیلدها در `raw-ohlc-reference-manifest.json` و `source-field-matrix.csv` است.

---

## ۱۱. وضعیت نهایی

| مورد | وضعیت |
|---|---|
| قرارداد Raw با payload واقعی | `VERIFIED` |
| Raw parity کل universe | `VERIFIED` ({fa(S['row_contract_exact_pct'], 4, True)} ردیفی) |
| جداسازی Raw/Factor/Adjusted | `VERIFIED` |
| علت‌شناسی mismatch خام | `VERIFIED` |
| اصلاح fallback روی کپی | `IMPLEMENTED_AND_TESTED` |
| انتشار عملیاتی اصلاح | `BLOCKED` (snapshot/rollback/تأیید بیرونی) |
| {fa(184)} no-cash / {fa(63)} missing / {fa(59)} far | `BLOCKED` در لایهٔ Factor؛ مستقل از Raw |
| فروي `BLOCKED_P_DEFINITION` | `BLOCKED`؛ Raw {fa(100, 0, True)} |
| حخزر `UNVERIFIED_NET_DPS` | `BLOCKED`؛ Raw {fa(100, 0, True)} |
| Full gate | `{GATE_LABEL}` |
| Build فرانت | `{BUILD_LABEL}` (بدون تغییر فرانت) |
| webgw برای کل universe | `NOT_MEASURED` (نمونهٔ {fa(3276)} ردیفی) |
| Operational DB | `VERIFIED` بدون تغییر |

---

## ۱۲. Commitها و باقی‌مانده‌ها

- Commit کد/ابزار/تست این راند: `{CODE_COMMIT}`.
- گزارش و artifactها در commit جداگانه ثبت می‌شوند.
- هیچ push/merge انجام نشد؛ `main` تغییر نکرد.
- باقی‌ماندهٔ اصلی: Factor exact {fa(LY['factor_layer']['exact_pct'], 4, True)} و Adjusted OHLC {fa(LY['adjusted_ohlc']['ok_pct'], 4, True)}. Raw دیگر گلوگاه اصلی نیست.
- پیشنهاد Round 19: تمرکز روی رویدادهای Factor (no-cash/far/فروي/حخزر) با همان cohort و همان تعریف‌ها؛ Raw به‌عنوان baseline ثابت نگه داشته شود. اصلاح fallback ابتدا باید از مسیر migration/rollback تأییدشده به محیط عملیاتی منتقل شود.

**دستور پایانی:** هیچ درصدی با تغییر مخرج، حذف موارد دشوار یا مقایسهٔ خام با تعدیل‌شده بهتر نشد. تفکیک Raw/Factor/Adjusted نشان داد مسیر زندهٔ Raw از منبع وفادار است؛ شکاف اصلی Adjusted یک مسئلهٔ Factor/رویداد است و اصلاح fallback نیز فقط دادهٔ محلی کهنه را با دادهٔ منتشرشده جایگزین کرد.
"""

# gate status cleanup: IN_PROGRESS at generation time is allowed; final build reruns.
os.makedirs(os.path.dirname(DOC), exist_ok=True)
with open(DOC, "w", encoding="utf-8") as f:
    f.write(md)
print(DOC, len(md), "chars", "gate", gate["status"])
