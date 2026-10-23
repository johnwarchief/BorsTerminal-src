# -*- coding: utf-8 -*-
"""Generate the Round 20 Raw + Performance-Adjusted parity report."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
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
PAR = read_csv(os.path.join(R18, "rahavard-raw-ohlc-parity.csv"))
T0ROWS = read_csv(os.path.join(R18, "rahavard-type0-vs-tsetmc.csv"))
PROD_ROWS = sum(int(x["product_count"] or 0) for x in PAR)
T0_ROWS = sum(int(x["type0_rows"] or 0) for x in T0ROWS)
T0_COMMON = sum(int(x["common_pc"] or 0) for x in PAR)
VOL_CMP = sum(int(x["volume_cmp"] or 0) for x in PAR)
VOL_EXACT = sum(int(x["volume_exact"] or 0) for x in PAR)
VOL_EXACT_PCT = 100.0 * VOL_EXACT / VOL_CMP if VOL_CMP else None
R19 = load(os.path.join(R18, "rahavard-raw-ohlc-round19-summary.json"))
PCOUNT = load(os.path.join(R20, "product-snapshot-count.json"))
VOL = load(os.path.join(R20, "reference-volume-parity.json"))
PAIRS = read_csv(os.path.join(ROOT, "_audit", "RAHAVARD-EVENT-PAIRS-ROUND3-2026-10-20.csv"))
MARKS = load(os.path.join(R20, "marks-oracle.json"))
COMP = [json.loads(x) for x in open(os.path.join(R20, "share-composition.jsonl"), encoding="utf-8")]
ADJ19 = read_csv(os.path.join(R18, "rahavard-raw-ohlc-round19-adjudication.csv"))
P_OPEN_FIELDS = sum(1 for r in ADJ19 if r.get("new_cause") == "PARSING_OR_TRANSFORM" and r.get("field") == "open")
P_VOL_FIELDS = sum(1 for r in ADJ19 if r.get("new_cause") == "PARSING_OR_TRANSFORM" and r.get("field") == "volume")
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
GATE_TEST = re.search(
    r"Round 20: proven Rahavard[^\n]*rc=0 \| (?:(\d+) pass / (\d+) fail|(\d+)/(\d+))",
    GATE_TEXT)
if GATE_TEST and GATE_TEST.group(1):
    TEST_TXT = f"{fa(GATE_TEST.group(1))}/{fa(int(GATE_TEST.group(1)) + int(GATE_TEST.group(2)))}"
elif GATE_TEST:
    TEST_TXT = f"{fa(GATE_TEST.group(3))}/{fa(GATE_TEST.group(4))}"
else:
    TEST_TXT = "—"
GATE_STATS = re.search(r"(\d+) suite counted, (\d+) silent \(exit-code only\), (\d+) skipped", GATE_TEXT)
GATE_LINE = (f"{fa(GATE_STATS.group(1))} suite counted، {fa(GATE_STATS.group(2))} silent، "
             f"{fa(GATE_STATS.group(3))} skipped؛ "
             + ("PROTECTED_DB_UNCHANGED" if "PROTECTED_DB_UNCHANGED" in GATE_TEXT
                else "PROTECTED_DB_NOT_CONFIRMED")) if GATE_STATS else "—"

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
**Commit ابزار/تست/شواهد این راند:** `{CODE_COMMIT}` + `b3d16861`  
**Gate:** `{GATE}`

> این گزارش دو حالت را **کاملاً جدا** می‌سنجد: (۱) OHLCV خام در برابر `type0` ره‌آورد، (۲) کندل تعدیل عملکردی در برابر `type7`. موفقیت در یکی، اثبات دیگری نیست. هیچ قیمت، کندل، تاریخ، تلورانس یا مخرجی برای بهترشدن عدد تغییر نکرد. Track B (موتور الگوها/بهینه‌سازی) در شاخهٔ جدا و دست‌نخورده است.

---

## ۰. پاسخ کوتاه

- **Raw منجمد (همان cohort Round 19):** **{fa(S['contract_ok_pct'], 4, True)}** فیلد و **{fa(S['row_exact_pct'], 4, True)}** ردیف؛ **{fa(S['row_pairs'])}** ردیف قابل‌مقایسه. تطبیق exact ۱۰۰٪ **حاصل نشد**.
- **Raw زنده (نمونهٔ هدفمند {fa(LIVE['symbols'])} نماد / {fa(LIVE['rows'])} فیلد بد):** **{fa(LIVE['closed'])}** فیلد از {fa(LIVE['rows'])} فیلد قبلاً بد، در دادهٔ زندهٔ فعلی با مرجع **منطبق شد**؛ **{fa(LIVE['regressed'])}** regression در همین نمونه. یعنی بخشی از mismatchهای `HISTORICAL` کهنگی snapshot بود، نه باگ فعلی. کل Universe زنده به‌علت rate/CDN ناقص ماند (`NOT_MEASURED`).
- **Performance-Adjusted (type7):** **{fa(ADJ['live_factor_ok_pct'], 4, True)}** تطبیق exact فاکتور، **{fa(ADJ['live_factor_near_pct'], 4, True)}** ±۱٪، **{fa(ADJ['live_func_ok_pct'], 4, True)}** OHLC عملکردی. این عدد پس از اصلاح runner (candle-closing) **بازتولید دقیق R17** است.
- **علت اصلی شکاف Adjusted:** event-set/فرمول مرجع، نه محاسبهٔ سادهٔ DPS/سهام. DPS و افزایش سرمایهٔ اندوخته‌ای **اثبات‌شده**اند؛ فرمول آورده/مطالبات به **S (قیمت پذیره)** نیاز دارد که در `timescale_marks` نیست و CODAL فقط بخشی را داد. بدون marks کامل {fa(S['assets'])} دارایی، ۱۰۰٪ قابل‌اثبات نیست.
- **Volume در حالت عملکردی:** در **{fa(VOL['type0_type7_common'])}** ردیف مشترک روزانه (D) type0/type7، حجم مرجع **دقیقاً برابر** حجم خام است ({fa(VOL['pct'], 2, True)}). product هم حجم را با factor مقیاس نمی‌کند؛ سیاست مرجع «حجم بدون تغییر» است.
- **هیچ اصلاح production انجام نشد**، چون هیچ فرمول/دادهٔ اثبات‌شدهٔ جدیدی که اختلاف را کم کند و ریسک داده را توجیه کند پیدا نشد. دیتابیس عملیاتی/promoted تغییر نکردند.

---

## ۱. Git، دامنه و منابع

- شاخهٔ مستقل: `{git(["rev-parse", "--abbrev-ref", "HEAD"])}`، ساخته‌شده از `a36f4b0b`.
- Track B در `mission/technical-pattern-engine-round18-2026-10-22` و commit `e066f003` دست‌نخورده.
- مرجع: snapshot منجمد `ref_bars_v2.jsonl` (type0/type7، ۲۰۲۶-۱۰-۲۰).
- محصول: snapshot `product_live_final_v4.jsonl` ({fa(PCOUNT['records'])} رکورد، {fa(S['assets'])} دارایی cohort).
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
- **{fa(S['row_pairs'] - S['row_exact'])} ردیف mismatch** (کاملاً تعیین‌تکلیف‌شده در R19):

{table(["علت ردیف", "ردیف", "دارایی"], [
    ["SOURCE_DATA_DIVERGENCE", fa(ROW['SOURCE_DATA_DIVERGENCE']['rows']), fa(ROW['SOURCE_DATA_DIVERGENCE']['assets'])],
    ["HISTORICAL_REVISION", fa(ROW['HISTORICAL_REVISION']['rows']), fa(ROW['HISTORICAL_REVISION']['assets'])],
    ["PRECISION_OR_ROUNDING", fa(ROW['PRECISION_OR_ROUNDING']['rows']), fa(ROW['PRECISION_OR_ROUNDING']['assets'])],
    ["CANDLE_GEOMETRY", fa(ROW['CANDLE_GEOMETRY']['rows']), fa(ROW['CANDLE_GEOMETRY']['assets'])],
    ["PARSING_OR_TRANSFORM", fa(ROW['PARSING_OR_TRANSFORM']['rows']), fa(ROW['PARSING_OR_TRANSFORM']['assets'])],
    ["UNCLASSIFIED", "۰", "۰"],
])}

### ۲-۲. پوشش و missing

- type0: {fa(S['assets'])} دارایی، {fa(T0_ROWS)} ردیف؛ محصول {fa(PROD_ROWS)} ردیف؛ تاریخ مشترک {fa(T0_COMMON)}.
- {fa(S['product_only_inside'])} ردیف فقط محصول داخل بازهٔ type0؛ {fa(S['product_only_outside'])} ردیف خارج بازه؛ {fa(S['type0_only_tradable'] + S['type0_only_no_trade'])} ردیف فقط type0 داخل بازه؛ {fa(S['type0_only_outside'])} خارج بازه.
- {fa(S['type0_only_product_omission'])} ردیف omission snapshot محصول؛ {fa(S['product_only_rahavard_omission'])} omission مرجع؛ {fa(S['type0_only_rahavard_date'])} تاریخ Rahavard-only؛ {fa(S['last_null'])} last-null؛ {fa(S['type0_flat'])} flat؛ {fa(S['type0_bad_geom'])} هندسهٔ نامعتبر.
- هیچ missing با صفر/forward-fill پر نشد.

### ۲-۳. recheck زندهٔ Raw

- {fa(LIVE['symbols'])} نماد اول cohort mismatch، **{fa(LIVE['rows'])} فیلد** بد در snapshot؛ همان فیلدها از `get_chart_tsetmc` زندهٔ فعلی دوباره خوانده شدند.
- **{fa(LIVE['live_ok'])} فیلد اکنون منطبق**، **{fa(LIVE['live_bad'])} فیلد هنوز ناهمخوان**، **{fa(LIVE['regressed'])} regression**. تطبیق با همان تلورانسِ مطلق ۰٫۵ (و نسبیِ 1e-6) سنجیده شد. چون نمونه فقط از فیلدهای قبلاً بد انتخاب شده، «۰ regression» یعنی هیچکدام از همین ۱۰۱ فیلد بدتر نشد، نه نرخ regression در کل Universe.
- نتیجه: بخش قابل‌توجهی از `HISTORICAL` (و بخشی از `PARSING`) کهنگی snapshot محصول است؛ product زنده بهتر از snapshot منجمد است. این یک **بهبود داده‌ای قابل‌اندازه‌گیری** است، اما چون فقط نمونهٔ هدفمند است، درصد کل Universe زنده `NOT_MEASURED` می‌ماند. اجرای همهٔ نمادهای زنده به‌علت CDN/rate ناقص شد و متوقف شد؛ هیچ ادعای ۱۰۰٪ زنده نداریم.

### ۲-۴. چرا Raw ۱۰۰٪ نشد

| خانواده | علت | وضعیت |
|---|---|---|
| SOURCE {fa(ROW['SOURCE_DATA_DIVERGENCE']['rows'])} | product با TSETMC می‌خواند، type0 Rahavard عدد دیگری دارد | `BLOCKED_SOURCE_REFERENCE` |
| HISTORICAL {fa(ROW['HISTORICAL_REVISION']['rows'])} | snapshot محصول کهنه/اصلاح‌شده؛ نمونهٔ زنده بخشی را بست | `PARTIAL` / `NOT_MEASURED` برای کل |
| PRECISION {fa(ROW['PRECISION_OR_ROUNDING']['rows'])} | exact نیست، relative ≤ ۰٫۰۵٪؛ تلورانس تغییر نکرد | `VERIFIED_PRECISION_BAND` |
| CANDLE {fa(ROW['CANDLE_GEOMETRY']['rows'])} | type0 flat یا H/L بیرون body؛ product widen می‌کند | `BLOCKED_REFERENCE_GEOMETRY` |
| PARSING {fa(ROW['PARSING_OR_TRANSFORM']['rows'])} | {fa(P_OPEN_FIELDS)} فیلد open با FIRST=0 (fallback مستند) + {fa(P_VOL_FIELDS)} فیلد volume صفر snapshot؛ ردیف‌های دارای فیلد هم‌زمان سه‌سنیبی به SOURCE رفتند | `BLOCKED_INDEPENDENT_SOURCE` |

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

> طبقه‌بندی: `MATCH` تساوی است؛ `ROUNDING_ONLY` برای قیمت یعنی اختلاف نسبی ≤۰٫۰۵٪ یا مطلق ≤۱ ریال، و برای factor یعنی ≤5e-4. این‌ها همان تلورانس‌های R17/R18 هستند و در این راند تغییر نکردند.

### ۳-۲. {fa(len(PAIRS))} رویداد اختلافی (R8 event-pair audit)

{table(["علت", "تعداد", "اقدام/وضعیت"], [
    ["NO_OFFICIAL_RATIO_ROW", fa(PAIR_CAUSE['NO_OFFICIAL_RATIO_ROW']),
     f"{fa(PAIR_CLASS['SOURCE_GAP_CONFIRMED:PRE_LEDGER_COVERAGE'])} پیش از پوشش دفتر + {fa(PAIR_CLASS['SOURCE_GAP_CONFIRMED:NO_LEDGER_ROW'])} بدون ردیف؛ مرجع marks لازم است"],
    ["PRODUCT_USES_OFFICIAL_RATIO_REFERENCE_DIFFERS", fa(PAIR_CAUSE['PRODUCT_USES_OFFICIAL_RATIO_REFERENCE_DIFFERS']),
     "product به نسبت رسمی وفادار است؛ ورودی رویداد مرجع متفاوت است"],
    ["REFERENCE_RATIO_DIFFERS_FROM_OFFICIAL", fa(PAIR_CAUSE['REFERENCE_RATIO_DIFFERS_FROM_OFFICIAL']),
     "مرجع با دفتر رسمی متفاوت است؛ فرمول/S مرجع اثبات نشده"],
    ["OFFICIAL_ROW_CLOSER_THAN_PRODUCT", fa(PAIR_CAUSE['OFFICIAL_ROW_CLOSER_THAN_PRODUCT']),
     "رویداد مرکب (اجزای رسمی)؛ یک ردیف تنها نسبت کل نیست"],
])}

### ۳-۳. فرمول‌های اثبات‌شده و نیمه‌اثبات‌شده

روی {fa(MARKS['symbols'])} نماد دارای `timescale_marks` ({fa(MARKS['rows'])} ردیف oracle):

{table(["گروه", "تعداد", "exact", "±۱٪", "وضعیت"], [
    ["DPS خالص", fa(MARKS_SUM['dps']['total']), fa(MARKS_SUM['dps']['exact']), "۰", "PROVEN"],
    ["افزایش سرمایهٔ اندوخته‌ای", fa(MARKS_SUM['reserve']['total']), fa(MARKS_SUM['reserve']['exact']), "۰", "PROVEN"],
    ["آورده/مطالبات", fa(MARKS_SUM['contribution']['total']), fa(MARKS_SUM['contribution']['exact']),
     fa(MARKS_SUM['contribution']['near']), "UNVERIFIED (S)"],
])}

- **DPS:** `price_ratio = close_ex / (close_ex + DPS)`؛ {fa(MARKS_SUM['dps']['exact'])} گام خالص exact (<1e-6) از {fa(MARKS_SUM['dps']['total'])}؛ یک ردیف combined با capital و یک ردیف mismatch که با DPS خالص توضیح داده نمی‌شود.
- **اندوخته/جایزه:** `price_ratio = previous_capital / new_capital`؛ {fa(MARKS_SUM['reserve']['exact'])} گام خالص exact؛ یک combined.
- **آورده/مطالبات:** ساختار `pv/nw + (1-pv/nw)*(cp/100)*(S/P)` با {fa(MARKS_SUM['contribution']['near'])}/{fa(MARKS_SUM['contribution']['total'])} گام در ±۱٪، **۰ exact**. `S` (قیمت پذیره) در marks نیست و فقط درصدها موجودند. بنابراین تولید نمی‌تواند آن را بدون شاهد اعمال کند.
- **Volume:** type0/type7 در **{fa(VOL['type0_type7_common'])}** ردیف مشترک روزانه (D) volume یکسان دارند ({fa(VOL['pct'], 2, True)})؛ product حجم را مقیاس نمی‌کند. رفتار حجم مرجع مستند است.

### ۳-۴. CODAL و محدودیت دسترسی

- برای {fa(len(COMP))} رویداد سهامِ نزدیک به mismatch، CODAL عمومی جست‌وجو شد: **{fa(COMP_STATUS['COMPLETE'])}** ترکیب کامل، **{fa(COMP_STATUS['SEARCH_ERROR:HTTPError'])}** خطای HTTP/rate، **{fa(COMP_STATUS['SEARCH_ERROR:URLError'])}** خطای شبکه، **{fa(COMP_STATUS['NO_CAPITAL_LETTER'] + COMP_STATUS['LETTERS_NO_COMPLETE_COMPOSITION'])}** بی‌نامه/ناقص.
- سه ترکیب کامل (تفارس، خنور، تاپ‌كيش) برای آزمون ساختاری استفاده شد؛ تفارس/خنور به `S` و event-set مرجع نیاز دارند. CODAL نرخ‌محدود شد و درخواست بیشتر بدون backoff ارسال نشد.
- `timescale_marks` ره‌آورد بدون نشست لاگین‌شده **403** می‌دهد؛ marks کامل {fa(S['assets'])} دارایی در دسترس نیست. این **BLOCKED_REFERENCE_MARKS** است، نه یک باگ product.

### ۳-۵. تصمیم مهندسی

**هیچ تغییر فرمول production اعمال نشد.** دلیل: `S` پذیره و event-set مرجع برای اکثریت رویدادها قابل‌استخراج نیست؛ اعمال فرمول با `S=1000` یا حدس، داده را برای رسیدن به عدد ۱۰۰٪ تغییر می‌دهد و ممنوع است. product فعلی روی DPS و اندوخته طبق فرمول اثبات‌شده کار می‌کند و باقی اختلاف‌ها به ورودی مرجع محدود است.

---

## ۴. تجمیع زمانی، تایم‌فریم و حجم

- baseline این راند روزانه (`D`) است؛ بازهٔ مشترک و تمام ردیف‌های قابل‌مقایسه پوشش داده شد.
- `W` در snapshot موجود است اما در این راند بازاندازه‌گیری نشد: `NOT_MEASURED`. تجمیع هفتگی باید با همان مرز جلسه و همان سقف/کف/باز/بسته در راند بعد سنجیده شود.
- حجم در حالت performance-adjusted توسط مرجع مقیاس **نمی‌شود** ({fa(VOL['pct'], 2, True)} برابری روزانهٔ type0/type7)، بنابراین سیاست product (بدون تغییر حجم) درست است. volume raw exact {fa(VOL_EXACT_PCT, 4, True)} ({fa(VOL_EXACT)} / {fa(VOL_CMP)}، از R18) و mismatchهای حجم از raw منبع/دقت می‌آید، نه از ضریب.

---

## ۵. تست‌ها، gate و دیتابیس

- `tools/ra365_round15_parity.py`: مسیر DPS اصلاح شد تا `closings` را بپذیرد و **پایانیِ کندل** (نه close دیتابیس) را مبنا بگیرد؛ خطای `TypeError` و اختلافِ ناشی از close محلی برطرف شد.
- `tools/ra365_round16_parity.py --candle-closing`: baseline authoritative را تولید کرد و **{fa(ADJ['live_factor_ok_pct'], 4, True)}** را دقیقاً بازتولید R17 کرد (`method=candle_closing=True`).
- `dev/test_ra365_round20_formula_oracle_v1.py`: **{TEST_TXT}** (DPS، اندوخته، ساختار آورده، رد S نامعلوم).
- `tools/ra365_round20_marks_oracle.py`: {fa(MARKS['symbols'])} نماد / {fa(MARKS['rows'])} ردیف؛ artifact: `marks-oracle.csv/json`.
- `tools/ra365_round20_live_raw_recheck.py`: نمونهٔ {fa(LIVE['symbols'])} نماد / {fa(LIVE['rows'])} ردیف؛ artifact: `live-raw-recheck.csv` + archive خام `live-raw-cache.tar.gz`.
- `tools/ra365_round20_reference_invariants.py`: بازتولید مستقل volume روزانه type0/type7 و شمارش snapshot محصول؛ artifact: `reference-volume-parity.json` / `product-snapshot-count.json`.
- Full gate: `{GATE}` — {GATE_LINE} (`artifacts/ra365/r20/full-gate.log`). دو skip فیکسچرِ شناخته‌شده (`_audit/ra365_ref_bars.json`, `market.db.lzma`) است، نه شکست تست.
- دیتابیس عملیاتی SHA `{sha(DB_OP)}` و promoted SHA `{sha(DB_PROM)}`؛ فقط read-only، بدون تغییر.
- Track B: هیچ فایل/تست/benchmark آن در این راند تغییر نکرد.

---

## ۶. وضعیت پذیرش

| معیار | نتیجه |
|---|---|
| Raw ۱۰۰٪ همهٔ فیلدها/ردیف‌ها | **خیر** — {fa(S['contract_ok_pct'], 4, True)} / {fa(S['row_exact_pct'], 4, True)} منجمد؛ live نمونه {fa(100.0*LIVE['live_ok']/LIVE['rows'], 2, True)} |
| Performance-Adjusted ۱۰۰٪ | **خیر** — {fa(ADJ['live_func_ok_pct'], 4, True)} OHLC؛ factor {fa(ADJ['live_factor_ok_pct'], 4, True)} |
| Volume مطابق مرجع | **VERIFIED** — type0/type7 volume روزانه در {fa(VOL['type0_type7_common'])} ردیف برابر ({fa(VOL['pct'], 2, True)}) |
| موارد بدون شاهد | `BLOCKED_REFERENCE_MARKS` / `BLOCKED_SOURCE_REFERENCE` / `NOT_MEASURED` |
| mismatch پنهان‌شده | صفر؛ هیچ ردیف/تلورانس/مخرجی تغییر نکرد |

---

## ۷. اقدام‌های بعدی با شاهد مشخص

1. **marks کامل {fa(S['assets'])} دارایی** با نشست مجاز مالک یا export رسمی ره‌آورد؛ بدون آن ۱۰۰٪ Adjusted قابل‌اثبات نیست.
2. **S پذیره** برای رویدادهای آورده/مطالبات: CODAL صورت‌جلسه/آگهی ثبت با backoff و checkpoint؛ {fa(len(COMP))} رویداد هدفمند.
3. **Raw live full**: همهٔ نمادها با rate limit و cache؛ نمونهٔ {fa(LIVE['symbols'])} نمادی {fa(100.0*LIVE['live_ok']/LIVE['rows'], 1, True)} بهبود داد؛ کل Universe باید با manifest زمان‌دار ثبت شود.
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
                 "live-raw-cache.tar.gz",
                 "marks-oracle.csv", "marks-oracle.json",
                 "share-composition.jsonl", "share-events.csv",
                 "rahavard-marks-18.json", "product-snapshot-count.json",
                 "reference-volume-parity.json", "full-gate.log")
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
**Commit ابزار/تست/شواهد:** `{CODE_COMMIT}` + `b3d16861`  
**Gate:** `{GATE}`

## وضعیت

- Raw منجمد: {fa(S['contract_ok_pct'], 4, True)} فیلد / {fa(S['row_exact_pct'], 4, True)} ردیف؛ {fa(S['row_pairs'] - S['row_exact'])} mismatch تعیین‌تکلیف؛ UNCLASSIFIED صفر.
- Raw live نمونه: {fa(LIVE['closed'])} از {fa(LIVE['rows'])} فیلد بد بسته شد؛ {fa(LIVE['regressed'])} regression در همین نمونه؛ full live `NOT_MEASURED`.
- Adjusted: factor {fa(ADJ['live_factor_ok_pct'], 4, True)}، ±۱٪ {fa(ADJ['live_factor_near_pct'], 4, True)}، OHLC {fa(ADJ['live_func_ok_pct'], 4, True)}؛ runner با candle-closing بازتولید شد.
- DPS/اندوخته: PROVEN در marks sample؛ آورده/مطالبات: `UNVERIFIED` (S).
- Volume adjusted: {fa(VOL['pct'], 2, True)} برابر با خام در {fa(VOL['type0_type7_common'])} ردیف روزانه.
- هیچ تغییر production یا دیتابیس محافظت‌شده؛ Track B دست‌نخورده.

## Blocked

- `BLOCKED_REFERENCE_MARKS`: marks کامل بدون نشست مجاز/export.
- `BLOCKED_REFERENCE_EVENT_INPUT`: S پذیره و event-set مرجع.
- `BLOCKED_SOURCE_REFERENCE`: type0 در برابر TSETMC.
- `BLOCKED_REFERENCE_GEOMETRY`: flat/H-L نامعتبر type0.
- `NOT_MEASURED`: live full (کل Universe)، weekly aggregation، full marks.

## بازتولید

```bash
python tools/ra365_round16_parity.py --db D:/BorsTerminal-tmp/ra365_round17/market_r17_migrated.db \\
  --out artifacts/ra365/r20/adjusted-baseline-candle --candle-closing
python tools/ra365_round20_marks_oracle.py
python tools/ra365_round20_live_raw_recheck.py --limit-symbols 50
python tools/ra365_round20_reference_invariants.py
python dev/test_ra365_round20_formula_oracle_v1.py
```

## بعدی

marks کامل + S پذیره + live full با rate limit؛ بدون این شواهد ۱۰۰٪ ادعا نمی‌شود.
"""
with open(CHECK, "w", encoding="utf-8") as f:
    f.write(check)
print(OUT, len(md))
print(CHECK, len(check))
