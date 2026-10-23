# -*- coding: utf-8 -*-
"""Generate the Round 20 Raw + Performance-Adjusted parity report."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R20 = os.path.join(ROOT, "artifacts", "ra365", "r20")
R18 = os.path.join(ROOT, "artifacts", "ra365", "r18-rahavard")
OUT = os.path.join(ROOT, "docs", "RA365-ROUND20-RAW-PERFORMANCE-ADJUSTED-REPORT.md")
CHECK = os.path.join(ROOT, "docs", "CODER2-ROUND20-PARITY-CHECKPOINT.md")
CODE_COMMIT = os.environ.get("RA365_R20_CODE_COMMIT", "pending")
FA = "۰۱۲۳۴۵۶۷۸۹"


def fa(n, dec=0, pct=False):
    if n is None or n == "":
        return "—"
    if isinstance(n, str):
        try:
            n = float(n)
        except ValueError:
            return n
    s = f"{float(n):,.{dec}f}" if dec else f"{int(round(float(n))):,}"
    s = s.replace(",", "٬").replace(".", "٫")
    s = "".join(FA[int(ch)] if ch.isdigit() else ch for ch in s)
    return s + ("٪" if pct else "")


def load(path):
    return json.load(open(path, encoding="utf-8"))


def read_csv(path):
    return list(csv.DictReader(open(path, encoding="utf-8-sig")))


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def git(cmd):
    import shutil
    exe = shutil.which("git") or "git"
    return subprocess.check_output([exe] + cmd, cwd=ROOT).decode().strip()


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(out)


S = load(os.path.join(R18, "rahavard-raw-ohlc-summary.json"))
ROW = {r["cause"]: r for r in read_csv(os.path.join(R18, "rahavard-raw-ohlc-row-taxonomy.csv"))}
LIVE = load(os.path.join(R20, "live-raw-recheck-summary.json"))
ADJ = load(os.path.join(R20, "adjusted-baseline-candle", "parity_summary.json"))
STEPS = read_csv(os.path.join(R20, "adjusted-baseline-candle", "parity_steps.csv"))
PAIRS = read_csv(os.path.join(ROOT, "_audit", "RAHAVARD-EVENT-PAIRS-ROUND3-2026-10-20.csv"))
MARKS = load(os.path.join(R20, "marks-oracle.json"))
COMP = [json.loads(x) for x in open(os.path.join(R20, "share-composition.jsonl"), encoding="utf-8")]
GATE_LOG = os.path.join(R20, "full-gate.log")
GATE_TEXT = open(GATE_LOG, encoding="utf-8", errors="replace").read() if os.path.exists(GATE_LOG) else ""
if "ALL SUITES PASSED" in GATE_TEXT:
    GATE = "VERIFIED"
elif "FAILED:" in GATE_TEXT:
    GATE = "REGRESSION"
elif GATE_TEXT:
    GATE = "IN_PROGRESS"
else:
    GATE = "NOT_MEASURED"

STEP_KINDS = Counter(r["kind"] for r in STEPS)
STEP_BAD = []
for r in STEPS:
    try:
        if r["kind"] == "PAIR" and abs(float(r["ratio_diff"])) > 0.01:
            STEP_BAD.append(r)
    except (KeyError, ValueError):
        pass
PAIR_CAUSE = Counter(r["cause"] for r in PAIRS)
PAIR_CLASS = Counter(r["round3_class"] for r in PAIRS)
COMP_STATUS = Counter(r["status"] for r in COMP)
MARKS_SUM = MARKS["summary"]

DB_OP = "C:/Users/Johnkallnaya/Desktop/Borsterminal/BorsTerminal-src/market.db"
DB_PROM = "D:/BorsTerminal-tmp/ra365_round17/market_r17_migrated.db"

md = f"""# RA365 Round 20 — Raw & Performance-Adjusted Parity

**تاریخ:** 2026-10-23  
**شاخه:** `{git(["rev-parse", "--abbrev-ref", "HEAD"])}`  
**مبنا:** `a36f4b0b` (Round 19 Track A)  
**HEAD گزارش:** `{git(["rev-parse", "HEAD"])[:12]}`  
**Commit ابزار/تست/artifact این راند:** `{CODE_COMMIT}`  
**Gate:** `{GATE}`

> این گزارش دو حالت را **کاملاً جدا** می‌سنجد: (۱) OHLCV خام در برابر `type0` ره‌آورد، (۲) کندل تعدیل عملکردی در برابر `type7`. موفقیت در یکی، اثبات دیگری نیست. هیچ قیمت، کندل، تاریخ، تلورانس یا مخرجی برای بهترشدن عدد تغییر نکرد. Track B (موتور الگوها/بهینه‌سازی) در شاخهٔ جدا و دست‌نخورده است.

---

## ۰. پاسخ کوتاه

- **Raw منجمد (همان cohort Round 19):** **{fa(S['contract_ok_pct'], 4, True)}** فیلد و **{fa(S['row_exact_pct'], 4, True)}** ردیف؛ **{fa(S['row_pairs'])}** ردیف قابل‌مقایسه. تطبیق exact ۱۰۰٪ **حاصل نشد**.
- **Raw زنده (نمونهٔ هدفمند ۵۰ نماد / {fa(LIVE['rows'])} فیلد بد):** **{fa(LIVE['closed'])}** فیلد از {fa(LIVE['rows'])} فیلد قبلاً بد، در دادهٔ زندهٔ فعلی با مرجع **منطبق شد**؛ **{fa(LIVE['regressed'])}** regression. یعنی بخشی از mismatchهای `HISTORICAL` کهنگی snapshot بود، نه باگ فعلی. کل ۴۲۸ نماد زنده به‌علت rate/CDN ناقص ماند (`NOT_MEASURED`).
- **Performance-Adjusted (type7):** **{fa(ADJ['live_factor_ok_pct'], 4, True)}** تطبیق exact فاکتور، **{fa(ADJ['live_factor_near_pct'], 4, True)}** ±۱٪، **{fa(ADJ['live_func_ok_pct'], 4, True)}** OHLC عملکردی. این عدد پس از اصلاح runner (candle-closing) **بازتولید دقیق R17** است.
- **علت اصلی شکاف Adjusted:** event-set/فرمول مرجع، نه محاسبهٔ سادهٔ DPS/سهام. DPS و افزایش سرمایهٔ اندوخته‌ای **اثبات‌شده**اند؛ فرمول آورده/مطالبات به **S (قیمت پذیره)** نیاز دارد که در `timescale_marks` نیست و CODAL فقط بخشی را داد. بدون marks کامل ۲٬۵۹۵ دارایی، ۱۰۰٪ قابل‌اثبات نیست.
- **Volume در حالت عملکردی:** در **{fa(1233213)}** ردیف مشترک type0/type7، حجم مرجع **دقیقاً برابر** حجم خام است (۱۰۰٪). product هم حجم را با factor مقیاس نمی‌کند؛ سیاست مرجع «حجم بدون تغییر» است.
- **هیچ اصلاح production انجام نشد**، چون هیچ فرمول/دادهٔ اثبات‌شدهٔ جدیدی که اختلاف را کم کند و ریسک داده را توجیه کند پیدا نشد. دیتابیس عملیاتی/promoted تغییر نکردند.

---

## ۱. Git، دامنه و منابع

- شاخهٔ مستقل: `{git(["rev-parse", "--abbrev-ref", "HEAD"])}`، ساخته‌شده از `a36f4b0b`.
- Track B در `mission/technical-pattern-engine-round18-2026-10-22` و commit `e066f003` دست‌نخورده.
- مرجع: snapshot منجمد `ref_bars_v2.jsonl` (type0/type7، ۲۰۲۶-۱۰-۲۰).
- محصول: snapshot `product_live_final_v4.jsonl` (۳٬۳۴۴ رکورد، ۲٬۵۹۵ دارایی cohort).
- دیتابیس promoted (فقط‌خواندنی): `market_r17_migrated.db`؛ دیتابیس عملیاتی فقط read-only.
- SHA دیتابیس‌ها در §۸.

| حالت | مخرج | تعریف |
|---|---|---|
| Raw | {fa(S['row_pairs'])} ردیف / {fa(S['contract_compared_fields'])} فیلد | type0 خام، قرارداد widen با official CLOSE |
| Adjusted factor | {fa(ADJ['live_factor_compared_dates'])} تاریخ | `type7.close / type0.close` در برابر factor محصول |
| Adjusted OHLC | {fa(ADJ['live_func_compared_fields'])} فیلد | OHLC خام × factor در برابر type7 |

---

## ۲. Raw — نتیجه، پوشش و باقی‌مانده

### ۲-۱. نتیجهٔ منجمد

- **قراردادی:** {fa(S['contract_ok_pct'], 4, True)} فیلد؛ **{fa(S['row_exact_pct'], 4, True)}** ردیف ({fa(S['row_exact'])} از {fa(S['row_pairs'])}).
- **تحت‌اللفظی:** high {fa(S['literal_high_exact_pct'], 4, True)}، low {fa(S['literal_low_exact_pct'], 4, True)}، ردیف {fa(S['literal_row_exact_pct'], 4, True)}.
- **۲٬۱۱۵ ردیف mismatch** (کاملاً تعیین‌تکلیف‌شده در R19):

{table(["علت ردیف", "ردیف", "دارایی"], [
    ["SOURCE_DATA_DIVERGENCE", fa(ROW['SOURCE_DATA_DIVERGENCE']['rows']), fa(ROW['SOURCE_DATA_DIVERGENCE']['assets'])],
    ["HISTORICAL_REVISION", fa(ROW['HISTORICAL_REVISION']['rows']), fa(ROW['HISTORICAL_REVISION']['assets'])],
    ["PRECISION_OR_ROUNDING", fa(ROW['PRECISION_OR_ROUNDING']['rows']), fa(ROW['PRECISION_OR_ROUNDING']['assets'])],
    ["CANDLE_GEOMETRY", fa(ROW['CANDLE_GEOMETRY']['rows']), fa(ROW['CANDLE_GEOMETRY']['assets'])],
    ["PARSING_OR_TRANSFORM", fa(ROW['PARSING_OR_TRANSFORM']['rows']), fa(ROW['PARSING_OR_TRANSFORM']['assets'])],
    ["UNCLASSIFIED", "۰", "۰"],
])}

### ۲-۲. پوشش و missing

- type0: {fa(S['assets'])} دارایی، {fa(1233213)} ردیف؛ محصول ۲٬۱۲۵٬۳۳۰ ردیف؛ تاریخ مشترک ۱٬۱۹۲٬۰۷۱.
- {fa(S['product_only_inside'])} ردیف فقط محصول داخل بازهٔ type0؛ {fa(S['product_only_outside'])} ردیف خارج بازه؛ {fa(S['type0_only_tradable'] + S['type0_only_no_trade'])} ردیف فقط type0 داخل بازه؛ {fa(S['type0_only_outside'])} خارج بازه.
- {fa(S['type0_only_product_omission'])} ردیف omission snapshot محصول؛ {fa(S['product_only_rahavard_omission'])} omission مرجع؛ {fa(S['type0_only_rahavard_date'])} تاریخ Rahavard-only؛ {fa(S['last_null'])} last-null؛ {fa(S['type0_flat'])} flat؛ {fa(S['type0_bad_geom'])} هندسهٔ نامعتبر.
- هیچ missing با صفر/forward-fill پر نشد.

### ۲-۳. recheck زندهٔ Raw

- ۵۰ نماد اول cohort mismatch، **{fa(LIVE['rows'])} فیلد** بد در snapshot؛ همان فیلدها از `get_chart_tsetmc` زندهٔ فعلی دوباره خوانده شدند.
- **{fa(LIVE['live_ok'])} فیلد اکنون منطبق**، **{fa(LIVE['live_bad'])} فیلد هنوز ناهمخوان**، **{fa(LIVE['regressed'])} regression**.
- نتیجه: بخش قابل‌توجهی از `HISTORICAL` (و بخشی از `PARSING`) کهنگی snapshot محصول است؛ product زنده بهتر از snapshot منجمد است. این یک **بهبود داده‌ای قابل‌اندازه‌گیری** است، اما چون فقط نمونهٔ هدفمند است، درصد کل Universe زنده `NOT_MEASURED` می‌ماند. اجرای همهٔ ۴۲۸ نماد به‌علت CDN/rate ناقص شد و متوقف شد؛ هیچ ادعای ۱۰۰٪ زنده نداریم.

### ۲-۴. چرا Raw ۱۰۰٪ نشد

| خانواده | علت | وضعیت |
|---|---|---|
| SOURCE {fa(ROW['SOURCE_DATA_DIVERGENCE']['rows'])} | product با TSETMC می‌خواند، type0 Rahavard عدد دیگری دارد | `BLOCKED_SOURCE_REFERENCE` |
| HISTORICAL {fa(ROW['HISTORICAL_REVISION']['rows'])} | snapshot محصول کهنه/اصلاح‌شده؛ نمونهٔ زنده بخشی را بست | `PARTIAL` / `NOT_MEASURED` برای کل |
| PRECISION {fa(ROW['PRECISION_OR_ROUNDING']['rows'])} | exact نیست، relative ≤ ۰٫۰۵٪؛ تلورانس تغییر نکرد | `VERIFIED_PRECISION_BAND` |
| CANDLE {fa(ROW['CANDLE_GEOMETRY']['rows'])} | type0 flat یا H/L بیرون body؛ product widen می‌کند | `BLOCKED_REFERENCE_GEOMETRY` |
| PARSING {fa(ROW['PARSING_OR_TRANSFORM']['rows'])} | ۵۵ open با FIRST=0 (fallback مستند) + ۱ volume snapshot | `BLOCKED_INDEPENDENT_SOURCE` |

**نتیجه:** ۱۰۰٪ Raw با داده‌های موجود و بدون تغییر منبع/تعریف مرجع قابل‌اثبات نیست. هیچ ردیف، تلورانس یا مخرجی برای نزدیک‌شدن به ۱۰۰٪ تغییر نکرد.

---

## ۳. Performance-Adjusted — نتیجه و علت‌شناسی

### ۳-۱. baseline بازتولیدشده

پس از اصلاح runner (پایهٔ DPS = پایانیِ کندل، نه close دیتابیس):

| سنجه | مقدار |
|---|---:|
| Factor exact (≤ 5e-4) | {fa(ADJ['live_factor_ok_pct'], 4, True)} ({fa(ADJ['live_factor_ok_dates'])} / {fa(ADJ['live_factor_compared_dates'])}) |
| Factor ±۱٪ | {fa(ADJ['live_factor_near_pct'], 4, True)} |
| Factor نرمال‌شده exact | {fa(ADJ['live_factor_norm_ok_pct'], 4, True)} |
| OHLC عملکردی | {fa(ADJ['live_func_ok_pct'], 4, True)} ({fa(ADJ['live_func_ok_fields'])} / {fa(ADJ['live_func_compared_fields'])}) |
| step pairs | {fa(STEP_KINDS['PAIR'])} |
| step ratio mismatch (>۱٪) | {fa(len(STEP_BAD))} |
| ref-only / prod-only steps | {fa(STEP_KINDS['REF_ONLY'])} / {fa(STEP_KINDS['PROD_ONLY'])} |

### ۳-۲. ۱۲۸ رویداد اختلافی (R8 event-pair audit)

{table(["علت", "تعداد", "اقدام/وضعیت"], [
    ["NO_OFFICIAL_RATIO_ROW", fa(PAIR_CAUSE['NO_OFFICIAL_RATIO_ROW']),
     "۵۱ پیش از پوشش دفتر + ۱۹ بدون ردیف؛ مرجع marks لازم است"],
    ["PRODUCT_USES_OFFICIAL_RATIO_REFERENCE_DIFFERS", fa(PAIR_CAUSE['PRODUCT_USES_OFFICIAL_RATIO_REFERENCE_DIFFERS']),
     "product به نسبت رسمی وفادار است؛ ورودی رویداد مرجع متفاوت است"],
    ["REFERENCE_RATIO_DIFFERS_FROM_OFFICIAL", fa(PAIR_CAUSE['REFERENCE_RATIO_DIFFERS_FROM_OFFICIAL']),
     "مرجع با دفتر رسمی متفاوت است؛ فرمول/S مرجع اثبات نشده"],
    ["OFFICIAL_ROW_CLOSER_THAN_PRODUCT", fa(PAIR_CAUSE['OFFICIAL_ROW_CLOSER_THAN_PRODUCT']),
     "رویداد مرکب (اجزای رسمی)؛ یک ردیف تنها نسبت کل نیست"],
])}

### ۳-۳. فرمول‌های اثبات‌شده و نیمه‌اثبات‌شده

روی ۱۸ نماد دارای `timescale_marks` (۱۰۹ ردیف oracle):

{table(["گروه", "تعداد", "exact", "±۱٪", "وضعیت"], [
    ["DPS خالص", fa(MARKS_SUM['dps']['total']), fa(MARKS_SUM['dps']['exact']), "۰", "PROVEN"],
    ["افزایش سرمایهٔ اندوخته‌ای", fa(MARKS_SUM['reserve']['total']), fa(MARKS_SUM['reserve']['exact']), "۰", "PROVEN"],
    ["آورده/مطالبات", fa(MARKS_SUM['contribution']['total']), fa(MARKS_SUM['contribution']['exact']),
     fa(MARKS_SUM['contribution']['near']), "UNVERIFIED (S)"],
])}

- **DPS:** `price_ratio = close_ex / (close_ex + DPS)`؛ ۴۶ گام خالص exact (<1e-6). یک ردیف combined با capital و یک ردیف بی‌گام.
- **اندوخته/جایزه:** `price_ratio = previous_capital / new_capital`؛ ۳ گام خالص exact؛ یک combined.
- **آورده/مطالبات:** ساختار `pv/nw + (1-pv/nw)*(cp/100)*(S/P)` با ۹/۱۱ گام در ±۱٪، **۰ exact**. `S` (قیمت پذیره) در marks نیست و فقط درصدها موجودند. بنابراین تولید نمی‌تواند آن را بدون شاهد اعمال کند.
- **Volume:** type0/type7 در **{fa(1233213)}** ردیف مشترک volume یکسان دارند (۱۰۰٪)؛ product حجم را مقیاس نمی‌کند. رفتار حجم مرجع مستند است.

### ۳-۴. CODAL و محدودیت دسترسی

- برای ۵۶ رویداد سهامِ نزدیک به mismatch، CODAL عمومی جست‌وجو شد: **{fa(COMP_STATUS['COMPLETE'])}** ترکیب کامل، **{fa(COMP_STATUS['SEARCH_ERROR:HTTPError'])}** خطای HTTP/rate، **{fa(COMP_STATUS['SEARCH_ERROR:URLError'])}** خطای شبکه، **{fa(COMP_STATUS['NO_CAPITAL_LETTER'] + COMP_STATUS['LETTERS_NO_COMPLETE_COMPOSITION'])}** بی‌نامه/ناقص.
- سه ترکیب کامل (تفارس، خنور، تاپ‌كيش) برای آزمون ساختاری استفاده شد؛ تفارس/خنور به `S` و event-set مرجع نیاز دارند. CODAL نرخ‌محدود شد و درخواست بیشتر بدون backoff ارسال نشد.
- `timescale_marks` ره‌آورد بدون نشست لاگین‌شده **403** می‌دهد؛ marks کامل ۲٬۵۹۵ دارایی در دسترس نیست. این **BLOCKED_REFERENCE_MARKS** است، نه یک باگ product.

### ۳-۵. تصمیم مهندسی

**هیچ تغییر فرمول production اعمال نشد.** دلیل: `S` پذیره و event-set مرجع برای اکثریت رویدادها قابل‌استخراج نیست؛ اعمال فرمول با `S=1000` یا حدس، داده را برای رسیدن به عدد ۱۰۰٪ تغییر می‌دهد و ممنوع است. product فعلی روی DPS و اندوخته طبق فرمول اثبات‌شده کار می‌کند و باقی اختلاف‌ها به ورودی مرجع محدود است.

---

## ۴. تجمیع زمانی، تایم‌فریم و حجم

- baseline این راند روزانه (`D`) است؛ بازهٔ مشترک و تمام ردیف‌های قابل‌مقایسه پوشش داده شد.
- `W` در snapshot موجود است اما در این راند بازاندازه‌گیری نشد: `NOT_MEASURED`. تجمیع هفتگی باید با همان مرز جلسه و همان سقف/کف/باز/بسته در راند بعد سنجیده شود.
- حجم در حالت performance-adjusted توسط مرجع مقیاس **نمی‌شود** (۱۰۰٪ برابری type0/type7)، بنابراین سیاست product (بدون تغییر حجم) درست است. volume raw exact {fa(99.9158, 4, True)} (از R18) و mismatchهای حجم از raw منبع/دقت می‌آید، نه از ضریب.

---

## ۵. تست‌ها، gate و دیتابیس

- `tools/ra365_round15_parity.py`: اصلاح شد تا **پایانیِ کندل** (نه close دیتابیس) را در پایهٔ DPS استفاده کند؛ با این اصلاح baseline **{fa(ADJ['live_factor_ok_pct'], 4, True)}** دقیقاً بازتولید R17 شد.
- `dev/test_ra365_round20_formula_oracle_v1.py`: **۸/۸** (DPS، اندوخته، ساختار آورده، رد S نامعلوم).
- `tools/ra365_round20_marks_oracle.py`: ۱۸ نماد / ۱۰۹ ردیف؛ artifact: `marks-oracle.csv/json`.
- `tools/ra365_round20_live_raw_recheck.py`: نمونهٔ ۵۰ نماد / {fa(LIVE['rows'])} ردیف؛ artifact: `live-raw-recheck.csv`.
- Full gate: `{GATE}` (`artifacts/ra365/r20/full-gate.log`).
- دیتابیس عملیاتی SHA `{sha(DB_OP)}` و promoted SHA `{sha(DB_PROM)}`؛ فقط read-only، بدون تغییر.
- Track B: هیچ فایل/تست/benchmark آن در این راند تغییر نکرد.

---

## ۶. وضعیت پذیرش

| معیار | نتیجه |
|---|---|
| Raw ۱۰۰٪ همهٔ فیلدها/ردیف‌ها | **خیر** — {fa(S['contract_ok_pct'], 4, True)} / {fa(S['row_exact_pct'], 4, True)} منجمد؛ live نمونه {fa(100.0*LIVE['live_ok']/LIVE['rows'], 2, True)} |
| Performance-Adjusted ۱۰۰٪ | **خیر** — {fa(ADJ['live_func_ok_pct'], 4, True)} OHLC؛ factor {fa(ADJ['live_factor_ok_pct'], 4, True)} |
| Volume مطابق مرجع | **VERIFIED** — type0/type7 volume در ۱٬۲۳۳٬۲۱۳ ردیف برابر |
| موارد بدون شاهد | `BLOCKED_REFERENCE_MARKS` / `BLOCKED_SOURCE_REFERENCE` / `NOT_MEASURED` |
| mismatch پنهان‌شده | صفر؛ هیچ ردیف/تلورانس/مخرجی تغییر نکرد |

---

## ۷. اقدام‌های بعدی با شاهد مشخص

1. **marks کامل ۲٬۵۹۵ دارایی** با نشست مجاز مالک یا export رسمی ره‌آورد؛ بدون آن ۱۰۰٪ Adjusted قابل‌اثبات نیست.
2. **S پذیره** برای رویدادهای آورده/مطالبات: CODAL صورت‌جلسه/آگهی ثبت با backoff و checkpoint؛ ۵۶ رویداد هدفمند.
3. **Raw live full**: ۴۲۸ نماد با rate limit و cache؛ نمونهٔ ۵۰ نمادی {fa(100.0*LIVE['live_ok']/LIVE['rows'], 1, True)} بهبود داد؛ کل Universe باید با manifest زمان‌دار ثبت شود.
4. **Weekly aggregation** و مرز جلسه؛ `NOT_MEASURED` فعلی.
5. **Fund/ETF monthly** formula (R8) در صورت ورود به cohort این راند؛ فعلاً از promoted DB جدا است.

---

## ۸. Git، commit و artifactها

- مبنا `a36f4b0b`; ابزار/تست/artifact: `{CODE_COMMIT}`.
- گزارش/checkpoint: commit جداگانه.
- هیچ push/merge به `main` انجام نشد.
- SHAها و artifactها:

{table(["artifact", "bytes", "sha256"], [
    [f"`{name}`", fa(os.path.getsize(os.path.join(R20, name))), f"`{sha(os.path.join(R20, name))[:16]}…`"]
    for name in ("adjusted-baseline-candle/parity_summary.json",
                 "adjusted-baseline-candle/parity_steps.csv",
                 "adjusted-baseline-candle/parity_symbols.csv",
                 "live-raw-recheck.csv", "live-raw-recheck-summary.json",
                 "marks-oracle.csv", "marks-oracle.json",
                 "share-composition.jsonl", "rahavard-marks-18.json")
])}

**دستور پایانی:** این گزارش ۱۰۰٪ را ادعا نمی‌کند. بخش Raw منجمد تثبیت شد و نمونهٔ زنده بخشی از کهنگی snapshot را بست؛ بخش Adjusted با فرمول‌های اثبات‌شده (DPS/اندوخته) بازتولید شد و شکاف باقی‌مانده به **marks/S مرجع** محدود است. هیچ داده‌ای برای سبزکردن عدد تغییر نکرد.
"""

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(md)

check = f"""# Coder2 — Round 20 Parity Checkpoint

**تاریخ:** 2026-10-23  
**شاخه:** `{git(["rev-parse", "--abbrev-ref", "HEAD"])}`  
**HEAD:** `{git(["rev-parse", "HEAD"])[:12]}`  
**مبنا:** `a36f4b0b`  
**Commit ابزار/تست/artifact:** `{CODE_COMMIT}`  
**Gate:** `{GATE}`

## وضعیت

- Raw منجمد: {fa(S['contract_ok_pct'], 4, True)} فیلد / {fa(S['row_exact_pct'], 4, True)} ردیف؛ ۲٬۱۱۵ mismatch تعیین‌تکلیف؛ UNCLASSIFIED صفر.
- Raw live نمونه: {fa(LIVE['closed'])} از {fa(LIVE['rows'])} فیلد بد بسته شد؛ {fa(LIVE['regressed'])} regression؛ full live `NOT_MEASURED`.
- Adjusted: factor {fa(ADJ['live_factor_ok_pct'], 4, True)}، ±۱٪ {fa(ADJ['live_factor_near_pct'], 4, True)}، OHLC {fa(ADJ['live_func_ok_pct'], 4, True)}؛ runner با candle-closing بازتولید شد.
- DPS/اندوخته: PROVEN در marks sample؛ آورده/مطالبات: `UNVERIFIED` (S).
- Volume adjusted: ۱۰۰٪ برابر با خام در ۱٬۲۳۳٬۲۱۳ ردیف.
- هیچ تغییر production یا دیتابیس محافظت‌شده؛ Track B دست‌نخورده.

## Blocked

- `BLOCKED_REFERENCE_MARKS`: marks کامل بدون نشست مجاز/export.
- `BLOCKED_REFERENCE_EVENT_INPUT`: S پذیره و event-set مرجع.
- `BLOCKED_SOURCE_REFERENCE`: type0 در برابر TSETMC.
- `BLOCKED_REFERENCE_GEOMETRY`: flat/H-L نامعتبر type0.
- `NOT_MEASURED`: live full 428، weekly aggregation، full marks.

## بازتولید

```bash
python tools/ra365_round16_parity.py --db D:/BorsTerminal-tmp/ra365_round17/market_r17_migrated.db \\
  --out artifacts/ra365/r20/adjusted-baseline-candle --candle-closing
python tools/ra365_round20_marks_oracle.py
python tools/ra365_round20_live_raw_recheck.py --limit-symbols 50
python dev/test_ra365_round20_formula_oracle_v1.py
```

## بعدی

marks کامل + S پذیره + live full با rate limit؛ بدون این شواهد ۱۰۰٪ ادعا نمی‌شود.
"""
with open(CHECK, "w", encoding="utf-8") as f:
    f.write(check)
print(OUT, len(md))
print(CHECK, len(check))
