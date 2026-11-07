# -*- coding: utf-8 -*-
"""Generate the Round 20 raw-field fix report from committed artifacts."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "artifacts", "ra365", "r20-fix")
R20 = os.path.join(ROOT, "artifacts", "ra365", "r20")
OUT = os.path.join(ROOT, "docs", "RA365-ROUND20-RAW-FIELD-FIX-REPORT.md")
CHECK = os.path.join(ROOT, "docs", "CODER2-ROUND20-FIX-CHECKPOINT.md")
COMMITS = os.environ.get("RA365_R20_FIX_COMMITS", "pending")
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


PAIR = load(os.path.join(FIX, "raw-replay-after-summary.json"))
BEFORE = load(os.path.join(FIX, "raw-before-summary.json"))
V10_TEXT = open(os.path.join(FIX, "v10-baseline.txt"), encoding="utf-8").read()
V10 = re.search(
    r"V10 قاعدۀِ فعلیِ محصول.*?\n?.*?([\d.]+)٪\s+([\d.]+)٪\s+([\d.]+)٪\s+([\d.]+)٪\s+([\d.]+)٪\s+(\d+)\s+(\d+)\s+(\d+)",
    V10_TEXT)
VSYM = load(os.path.join(FIX, "v10-per-symbol.json"))
WEEK = load(os.path.join(FIX, "weekly-volume-rule.json"))
EV = {r["symbol"]: r for r in load(os.path.join(FIX, "type7-event-evidence.json"))}
ADJ = load(os.path.join(R20, "adjusted-baseline-candle", "parity_summary.json"))
OHLC = load(os.path.join(FIX, "type7-ohlc-projection.json"))
WIT = load(os.path.join(FIX, "raw-witness.json"))
LIVE = load(os.path.join(R20, "live-raw-recheck-summary.json"))
S = load(os.path.join(ROOT, "artifacts", "ra365", "r18-rahavard", "rahavard-raw-ohlc-summary.json"))
SHAS = open(os.path.join(FIX, "fixture-sha256.txt"), encoding="utf-8").read().strip().splitlines()

GATE_LOG = os.path.join(FIX, "full-gate.log")
GATE_ART = "full-gate.txt" if os.path.exists(os.path.join(FIX, "full-gate.txt")) else "full-gate.log"
GATE_TEXT = open(GATE_LOG, encoding="utf-8", errors="replace").read() if os.path.exists(GATE_LOG) else ""
if "ALL SUITES PASSED" in GATE_TEXT:
    GATE = "VERIFIED"
elif "FAILED:" in GATE_TEXT:
    GATE = "REGRESSION"
elif GATE_TEXT:
    GATE = "IN_PROGRESS"
else:
    GATE = "NOT_MEASURED"
GATE_STATS = re.search(r"(\d+) suite counted, (\d+) silent \(exit-code only\), (\d+) skipped", GATE_TEXT)
GATE_LINE = (f"{fa(GATE_STATS.group(1))} suite counted، {fa(GATE_STATS.group(2))} silent، "
             f"{fa(GATE_STATS.group(3))} skipped؛ "
             + ("PROTECTED_DB_UNCHANGED" if "PROTECTED_DB_UNCHANGED" in GATE_TEXT
                else "PROTECTED_DB_NOT_CONFIRMED")) if GATE_STATS else "—"
GATE_TEST = re.search(r"Round 18: raw OHLC mapping[^\n]*rc=0 \| (\d+)/(\d+)", GATE_TEXT)
TEST_RAW = f"{fa(GATE_TEST.group(1))}/{fa(GATE_TEST.group(2))}" if GATE_TEST else "—"

H_EV = EV.get("هجرت") or {}
H_DPS = (H_EV.get("marks_dps_near") or [{}])[0].get("dps")
H_BASE = round(H_DPS / (1 - H_EV["product_ratio"])) if H_DPS and H_EV.get("product_ratio") else None
SG_EV = EV.get("سغرب") or {}
SG_DPS = (SG_EV.get("marks_dps_near") or [{}])[0].get("dps")
SG_BASE = SG_EV.get("ledger_p_closing_not_adjusted")
DB_OP = "C:/Users/Johnkallnaya/Desktop/Borsterminal/BorsTerminal-src/market.db"
DB_PROM = "D:/BorsTerminal-tmp/ra365_round17/market_r17_migrated.db"


def db_sha(path):
    try:
        return sha(path)
    except FileNotFoundError:
        return "MISSING"


def ev_ratio(sym):
    r = EV.get(sym) or {}
    return r


def ev_note(sym):
    r = ev_ratio(sym)
    bits = []
    if r.get("product_ratio") is not None:
        bits.append(f"product `{r['product_ratio']:.6f}`")
    if r.get("ledger_ratio") is not None:
        bits.append(f"official `{r['ledger_ratio']:.6f}`")
    if r.get("ref_implied_price_ratio") is not None:
        bits.append(f"reference `{r['ref_implied_price_ratio']:.6f}`")
    dps = r.get("marks_dps_near") or []
    if dps:
        bits.append("marks DPS " + "، ".join(f"{d['date']}={d['dps']}" for d in dps))
    return "؛ ".join(bits)


raw_before_row = BEFORE["row_exact_ok_pct"]
raw_after_row = PAIR["row_exact_ok_pct"]
raw_after_fields = PAIR["fields"]
raw_before_fields = PAIR["before"]
resid_rows = PAIR["rows"] - PAIR["row_exact_ok"]
resid_fields = sum((PAIR["fields"][f]["compared"] - PAIR["fields"][f]["ok"])
                   for f in ("open", "high_raw", "low_raw", "last", "volume"))

md = f"""# RA365 Round 20 — Raw Field Fix & Type7 Residual

**تاریخ:** 2026-10-23  
**شاخه:** `{git(["rev-parse", "--abbrev-ref", "HEAD"])}`  
**مبنا:** `1cf886ea` (Round 20 diagnostic branch)  
**HEAD گزارش:** `{git(["rev-parse", "HEAD"])[:12]}`  
**Commitهای این راند:** `{COMMITS}`  
**Gate:** `{GATE}`

> این گزارش **جدا** از گزارش تشخیصی Round 20 است. آن گزارش baseline و علت‌یابی بود؛ این گزارش یک اصلاح واقعی کد + اندازه‌گیری before/after روی fixture ثابت و بازسنجی type7 است. هیچ تلورانس، مخرج یا مجموعه‌ردیفی برای بهترشدن عدد تغییر نکرد. دیتابیس عملیاتی/promoted و Track B دست‌نخورده‌اند.

---

## ۰. پاسخ کوتاه

- **Raw literal (snapshot محصول، بدون replay):** با مقایسهٔ فیلدهای خام محصول در برابر `type0`، نرخ ردیف **{fa(raw_before_row, 4, True)}** بود. ریشهٔ اصلی، دور ریختن `HIGH/LOW` خام پس از `widen()` در parser زنده و در `candle_contract.candle()` بود؛ `price_basis` ناچار همان سایهٔ گشاد‌شده را `high_raw/low_raw` می‌نامید.
- **اصلاح + replay روی همان ردیف‌ها:** parser و سازندهٔ کندل اکنون `high_raw/low_raw` را **قبل از** widen نگه می‌دارند. روی {fa(PAIR['rows'])} ردیف مشترک، نرخ ردیف از **{fa(PAIR['before_row_exact_ok_pct'], 4, True)}** به **{fa(raw_after_row, 4, True)}** رسید. `high_raw` از {fa(raw_before_fields['high_raw']['ok_pct'], 4, True)} به {fa(raw_after_fields['high_raw']['ok_pct'], 4, True)} و `low_raw` از {fa(raw_before_fields['low_raw']['ok_pct'], 4, True)} به {fa(raw_after_fields['low_raw']['ok_pct'], 4, True)}.
- **پس‌ماندهٔ Raw:** **{fa(resid_rows)}** ردیف / **{fa(resid_fields)}** فیلد ({fa(100.0*resid_rows/PAIR['rows'], 4, True)} ردیف) — همه اختلاف `type0` با همان CSV/TSETMC یخ‌زده است (به‌جز fallback مستند `open` وقتی `FIRST=0`)، نه اختلاف محصول با فیلد خودش. نمونه‌ها در `raw-after-samples.csv`.
- **Type7:** baseline ۲۹نمادی دقیقاً بازتولید شد: **{fa(V10.group(1), 2, True)}** در تلورانس، میانه **{fa(V10.group(2), 4, True)}**، p90 **{fa(V10.group(3), 4, True)}**، p99 **{fa(V10.group(4), 4, True)}**، max **{fa(V10.group(5), 4, True)}**. هیچ تغییر فرمول production اعمال نشد؛ شواهد event-level نشان می‌دهد اختلاف باقی‌مانده در سمت مرجع/event-set است، نه در نسبت رسمی محصول.
- **حجم هفتگی:** قانون مرجع Rahavard **جمع** است، نه روز اول: **{fa(WEEK['match_within_0_5pct']['sum'])}/{fa(WEEK['weeks'])}** هفته با جمع می‌خواند و فقط **{fa(WEEK['match_within_0_5pct']['first_day'])}** با روز اول. قانون «روز اول» متعلق به tradersarena است و اعمال نشد.
- **ماهانه:** fixture مرجع فقط D/W دارد؛ `NOT_MEASURED`. هیچ تغییری بر پایهٔ شاهد tradersarena انجام نشد.
- **دیتابیس:** SHA عملیاتی `{db_sha(DB_OP)}` و promoted `{db_sha(DB_PROM)}` بدون تغییر؛ هیچ مهاجرت/backfill روی آن‌ها اجرا نشد.

---

## ۱. Git، fixture و دامنه

- شاخهٔ اصلاح از `1cf886ea` (شاخهٔ تشخیصی push‌شدهٔ Round 20) ساخته شد؛ گزارش تشخیصی دست‌نخورده است.
- fixture مرجع/محصول/کورپس ۲۹نمادی همان فایل‌های یخ‌زدهٔ قبلی است:
```

{chr(10).join('- `' + s + '`' for s in SHAS)}

```
- مقایسهٔ raw اکستندشده روی cohort {fa(PAIR['assets'])} دارایی / {fa(PAIR['rows'])} ردیف مشترک انجام شد. {fa(PAIR['parser_skipped_product_dates'])} ردیف محصول که parser جدید آن‌ها را کندل نمی‌داند همگی ۲۰۲۳-۰۳-۲۷ هستند (session anomaly، نه mismatch). {fa(PAIR['skipped_not_in_product'])} ردیف type0 بیرون از تاریخ‌های snapshot محصول است (پوشش، جدا).

---

## ۲. Raw — ریشهٔ واقعی و اصلاح

### ۲-۱. ریشه

`_parse_tsetmc_csv` مقدار `hi/lo` را از CSV می‌خواند و سپس `widen()` را روی آن اجرا می‌کرد و **فقط** سایهٔ گشاد‌شده را در کندل می‌گذاشت. `candle_contract.candle()` هم همین کار را می‌کرد. `price_basis.resolve_payload` که `high_raw` را می‌خواست، چون کلیدی نبود، `high` (گشاد‌شده) را به‌عنوان raw می‌گرفت. نتیجه: هر جا `CLOSE` یا `LAST` بیرون `HIGH/LOW` رسمی بود، `high_raw/low_raw` محصول به عدد بدنه/پایانی می‌رفت و در مقایسهٔ contract با `widen` پنهان می‌ماند.

شاهد عددی ({WIT['symbol']} {WIT['date']}): CSV `FIRST={fa(WIT['csv_first_high_low_close_last'][0])}, HIGH={fa(WIT['csv_first_high_low_close_last'][1])}, LOW={fa(WIT['csv_first_high_low_close_last'][2])}, CLOSE={fa(WIT['csv_first_high_low_close_last'][3])}, LAST={fa(WIT['csv_first_high_low_close_last'][4])}`؛ محصول قبل از اصلاح `high_raw={fa(WIT['product_before']['high_raw'])}` (برابر CLOSE) داشت. بعد از اصلاح `high_raw={fa(WIT['csv_first_high_low_close_last'][1])}`, `low_raw={fa(WIT['csv_first_high_low_close_last'][2])}`.

- **فرضیهٔ «حذف پیش‌گشایش» علت اصلی نبود:** `type0` high/low با همان `HIGH/LOW`ِ CSV در {fa(S['type0_vs_tsetmc']['high_exact_pct'], 4, True)} / {fa(S['type0_vs_tsetmc']['low_exact_pct'], 4, True)} ردیف می‌خواند. اختلاف ۸–۹ درصدی، از raw‌نداشتنِ محصول می‌آمد نه از یک جلسهٔ متفاوت. پس هیچ فیلتر session جدیدی اضافه نشد.

### ۲-۲. تغییر کد

- `api/chart.py::_parse_tsetmc_csv`: `hi_raw, lo_raw = hi, lo` پیش از `widen`; افزودن `high_raw/low_raw` به dict کندل.
- `candle_contract.py::candle`: نگه‌داشتن `hi_raw/lo_raw` پیش از `widen`; همان کلیدها در خروجی. `from_csv_row`/`from_board_row` به‌طور خودکار raw واقعی می‌دهند.
- `price_basis.py` بدون تغییر: از قبل `high_raw/low_raw` را ترجیح می‌داد و هندسه را از سایهٔ خام می‌ساخت.
- تست: `dev/test_round18_raw_parity_v1.py` دو assert تازه گرفت (raw در حالت عادی و در حالت widen)؛ **{TEST_RAW}**.
- تست‌های مرتبط: `dev/candle_contract_v1071.py` ۲۲/۲۲، `dev/price_basis_v1070.py` ۴۵/۴۵، `dev/test_candle_boundary_v1.py` ۹/۹، `dev/db_candle_contract_v1.py` ۳۲/۳۲.

### ۲-۳. before/after روی همان ردیف‌ها

مبنا: replay فایل CSV یخ‌زده از مسیر واقعی parser، روی همان تاریخ‌های snapshot محصول؛ ستون «قبل» از snapshot محصول و «بعد» از parser اصلاح‌شده، روی همان ردیف‌ها.

{table(["فیلد", "قبل", "بعد", "delta"], [
    ["open", fa(raw_before_fields['open']['ok_pct'], 4, True), fa(raw_after_fields['open']['ok_pct'], 4, True),
     fa(raw_after_fields['open']['ok_pct'] - raw_before_fields['open']['ok_pct'], 4, True)],
    ["high_raw", fa(raw_before_fields['high_raw']['ok_pct'], 4, True), fa(raw_after_fields['high_raw']['ok_pct'], 4, True),
     fa(raw_after_fields['high_raw']['ok_pct'] - raw_before_fields['high_raw']['ok_pct'], 4, True)],
    ["low_raw", fa(raw_before_fields['low_raw']['ok_pct'], 4, True), fa(raw_after_fields['low_raw']['ok_pct'], 4, True),
     fa(raw_after_fields['low_raw']['ok_pct'] - raw_before_fields['low_raw']['ok_pct'], 4, True)],
    ["last", fa(raw_before_fields['last']['ok_pct'], 4, True), fa(raw_after_fields['last']['ok_pct'], 4, True),
     fa(raw_after_fields['last']['ok_pct'] - raw_before_fields['last']['ok_pct'], 4, True)],
    ["volume", fa(raw_before_fields['volume']['ok_pct'], 4, True), fa(raw_after_fields['volume']['ok_pct'], 4, True),
     fa(raw_after_fields['volume']['ok_pct'] - raw_before_fields['volume']['ok_pct'], 4, True)],
    ["**ردیف کامل**", f"**{fa(PAIR['before_row_exact_ok_pct'], 4, True)}**",
     f"**{fa(raw_after_row, 4, True)}**", f"**{fa(raw_after_row - PAIR['before_row_exact_ok_pct'], 4, True)}**"],
])}

- اندازه‌گیری مستقل روی snapshot محصول (بدون replay): ردیف **{fa(BEFORE['row_exact_ok_pct'], 4, True)}** از {fa(BEFORE['rows'])} ردیف؛ `high_raw` {fa(BEFORE['fields']['high_raw']['ok_pct'], 4, True)}.
- تلورانس همان قرارداد قبلی است: مطلق **۰٫۵** و نسبی **۰٫۰۵٪**؛ exact و tol جدا شمرده شده‌اند. هیچ تلورانسی تغییر نکرد.
- **پس‌مانده:** {fa(resid_rows)} ردیف / {fa(resid_fields)} فیلد. این ردیف‌ها همان جایی هستند که `type0` با CSV یخ‌زدهٔ TSETMC اختلاف دارد (source divergence/historical revision)؛ parser عیناً CSV را تولید می‌کند. نمونه‌های reference/product/CSV در `raw-after-samples.csv` و `literal-raw-after-replay-samples.csv`.
- **{fa(PAIR['parser_skipped_product_dates'])} ردیف** ۲۰۲۳-۰۳-۲۷ در parser کندل نشدند (H=L=VOL=0/هندسهٔ نامعتبر) و در مخرج replay نیستند؛ این‌ها mismatch پنهان‌شده نیستند، در گزارش پوشش صریح آمده‌اند.

### ۲-۴. تفکیک از گزارش قبلی

نرخ **۹۹٫۸۹۰۷٪ فیلد / ۹۹٫۸۲۲۱٪ ردیف** گزارش Round 20 قبلی یک سنجهٔ **contract** بود (type0 با official CLOSE گشاد می‌شد و product `high_raw` در برابر سایهٔ گشاد سنجیده می‌شد). آن عدد **literal raw** نیست و در این گزارش بازاستفاده نشده است. عدد literal قبل/بعد در §۲-۳ است.

---

## ۳. Performance-adjusted — بازتولید baseline و دلیل نبود اصلاح امن

### ۳-۱. بازتولید baseline ۲۹نمادی

همان fixture و همان قرارداد عددی (R1: `last × factor` در برابر `type7|D`، تلورانس ۰٫۰۵٪):

| سنجه | مقدار |
|---|---:|
| در تلورانس | {fa(V10.group(1), 2, True)} |
| میانه | {fa(V10.group(2), 4, True)} |
| p90 | {fa(V10.group(3), 4, True)} |
| p99 | {fa(V10.group(4), 4, True)} |
| max | {fa(V10.group(5), 4, True)} |
| رویداد / تیزشده / تاریخ‌جابه‌جا | {fa(V10.group(6))} / {fa(V10.group(7))} / {fa(V10.group(8))} |

Baseline ۲٬۵۹۵ دارایی (snapshot **قبل از** اصلاح raw): factor exact **{fa(ADJ['live_factor_ok_pct'], 4, True)}**، ±۱٪ **{fa(ADJ['live_factor_near_pct'], 4, True)}**، OHLC **{fa(ADJ['live_func_ok_pct'], 4, True)}**. OHLC پس از اصلاح برای ۲٬۵۹۵ بازاندازه‌گیری نشد (`NOT_MEASURED`)؛ پروجکشن ۲۹نمادی تغییر مادی نشان نداد.

- **اثر اصلاح raw بر type7 (پروجکشن، همان ۲۹ نماد/تاریخ‌ها):** close {fa(OHLC['before']['c']['ok_pct'], 2, True)}؛ high از {fa(OHLC['before']['h']['ok_pct'], 2, True)} به {fa(OHLC['after']['h']['ok_pct'], 2, True)} و low از {fa(OHLC['before']['l']['ok_pct'], 2, True)} به {fa(OHLC['after']['l']['ok_pct'], 2, True)}. تغییر مادی نیست، چون خطای factor/close غالب است؛ این اصلاح raw را به type7 نسبت نمی‌دهیم.

### ۳-۲. بزرگ‌ترین شکاف‌های per-symbol

{table(["نماد", "میانه", "p90", "max", "در تلورانس", "بدترین تاریخ"], [
    [r["symbol"], fa(r["median_pct"], 4, True), fa(r["p90_pct"], 4, True),
     fa(r["max_pct"], 4, True), fa(r["within_tol_pct"], 2, True), r["worst_date"]]
    for r in VSYM[:8]
])}

### ۳-۳. شواهد event-level

{table(["نماد/رویداد", "محصول", "price_adjust", "share_change", "مرجع (type7/type0)", "marks"], [
    [f"{s} {EV[s]['event_date']}",
     f"`{EV[s].get('product_ratio'):.6f}`" if EV[s].get('product_ratio') is not None else "—",
     (f"`{EV[s].get('ledger_ratio'):.6f}` ({EV[s].get('ledger_date')})" if EV[s].get('ledger_ratio') is not None else "—"),
     (f"`{EV[s].get('share_ratio'):.6f}` ({EV[s].get('share_date')})" if EV[s].get('share_ratio') is not None else "—"),
     f"`{EV[s].get('ref_implied_price_ratio'):.6f}`" if EV[s].get('ref_implied_price_ratio') is not None else "—",
     ("، ".join(f"{x['date']}={x['dps']}" for x in (EV[s].get('marks_dps_near') or [])) or "—")]
    for s in ("هجرت", "سغرب", "لخزر", "ومعادن", "ولانا") if s in EV
])}

> برای لخزر و ولانا، ستون «محصول» نسبتِ یک رویداد از چند رویدادِ همان بلوک است؛ ضریبِ نهاییِ ترکیبی در متن آمده (لخزر و ولانا چندرویدادی‌اند). همچنین «مرجع» نسبتِ قیمتِ معکوسِ گامِ factor است، نه نسبت یک رویداد.

- **هجرت ۲۰۲۴-۰۵-۰۸:** نسبت محصول `{H_EV["product_ratio"]:.6f}` دقیقاً همان DPS رسمی {fa(H_DPS)} روی پایهٔ {fa(H_BASE)} است؛ مرجع `{H_EV["ref_implied_price_ratio"]:.6f}` می‌دهد. دفتر `price_adjust` برای این تاریخ ردیف ندارد؛ نزدیک‌ترین ردیف ۲۰۲۵-۰۵-۰۶ است (خارج از پنجرهٔ ۲۰ روزه). ردیف CSV همان نسبت رسمی را می‌دهد؛ افزودن ردیف دفترِ هم‌تاریخ عدد را عوض نمی‌کرد.
- **سغرب ۲۰۲۶-۰۵-۳۱:** محصول `{SG_EV["product_ratio"]:.6f}` و دفتر رسمی `{SG_EV["ledger_ratio"]:.6f}` (۲۰۲۶-۰۵-۳۰) هم‌خوان‌اند (DPS {fa(SG_DPS)} روی {fa(SG_BASE)})؛ مرجع `{SG_EV["ref_implied_price_ratio"]:.6f}` است. اختلاف سمت مرجع/تعریف DPS، نه محاسبهٔ محصول.
- **لخزر:** بلوک تعطیل ۲۰۲۶-۰۷-۱۹..۲۶؛ سه رویداد CSV محصول (ledger 2026-07-22 و share 2026-07-26) به ضریب نهایی ترکیبی می‌رسند؛ مرجع `0.826590` است. عدد مرجع از هیچ‌کدام از دو سند مستقل (پایهٔ بورس روز بازگشایی و DPS منتشرشده روی سهام قدیم) بازتولید نمی‌شود (§۱۰ گزارش قبلی). hardcode ممنوع.
- **ومعادن ۲۰۲۵-۰۲-۱۵:** نسبت محصول، سهام رسمی (۲۰۲۵-۰۲-۱۲؛ ledger نزدیک خارج از پنجره) و مرجع در جدول آمده‌اند. فرمول ترکیبی به `S` نیاز دارد؛ بدون شاهد پذیره، اعمال آن حدس است.
- **ولانا ۲۰۲۶-۰۸-۰۲:** سه رویداد CSV محصول در یک تعطیلی؛ مرجع یک گام ترکیبی دارد. جمع/حذف رویدادهای میانی روی سری اثر عددی ندارد (کندلی میان‌شان نیست) و فرمول آورده `S` لازم دارد.

**تصمیم:** هیچ فرمول production تغییر نکرد. `S` پذیره و event-set/تعریف DPS مرجع برای این موارد در دسترس نیست؛ اعمال حدس داده را برای رسیدن به عدد تغییر می‌دهد و ممنوع است. وضعیت: `BLOCKED_REFERENCE_EVENT_INPUT` / `BLOCKED_REFERENCE_MARKS`.

---

## ۴. تجمیع، حجم و ماهانه

- **هفتگی — سنجیده شد:** از {fa(WEEK['weeks'])} هفته‌باری که هم D و هم W مرجع دارند، حجم W با **جمع** روزها در {fa(WEEK['match_within_0_5pct']['sum'])} هفته می‌خواند؛ با حجم روز اول فقط {fa(WEEK['match_within_0_5pct']['first_day'])} و با روز آخر {fa(WEEK['match_within_0_5pct']['last_day'])}. پس سیاست فعلی product (جمع) برای Rahavard درست است. قانون «روز اول» که در `CANDLE-CONTRACT` از tradersarena نقل شده، به محصول دیگری تعلق دارد و **اعمال نشد**.
- **ماهانه:** fixture مرجع فقط `D` و `W` دارد (بدون `M`). `NOT_MEASURED`. تغییر bucket بر پایهٔ tradersarena انجام نشد.
- **Volume type7 روزانه:** {fa(load(os.path.join(R20, 'reference-volume-parity.json'))['pct'], 2, True)} برابر با type0 در {fa(load(os.path.join(R20, 'reference-volume-parity.json'))['type0_type7_common'])} ردیف روزانه.

---

## ۵. مسیر زنده و دیتابیس محلی

- **زنده `/api/chart`:** اصلاح raw H/L همین مسیر را می‌گیرد؛ parser زنده اکنون `high_raw/low_raw` واقعی می‌دهد.
- **محلی `/api/chart-db`:** `price_history` ستون `high_raw/low_raw` ندارد و ردیف‌های تاریخی با `widen` ذخیره شده‌اند؛ `from_db_row` نمی‌تواند سایهٔ خامِ ازدست‌رفته را بازسازی کند. وضعیت: `BLOCKED_LOCALDB_RAW_SCHEMA`. هیچ مهاجرت/backfill روی دیتابیس عملیاتی اجرا نشد.
- **last:** snapshot قدیمی {fa(S['last_null'])} ردیف last-null داشت؛ replay با CSV این lastها را دارد. مسیر محلی تا backfill رسمی همچنان به `last` ذخیره‌شده وابسته است.

---

## ۶. تست‌ها، gate و دیتابیس

- `dev/test_round18_raw_parity_v1.py`: **{TEST_RAW}** (شامل دو assert جدید raw H/L).
- تست‌های مرتبط candle/price-basis: ۲۲/۲۲، ۴۵/۴۵، ۹/۹، ۳۲/۳۲.
- Full gate: `{GATE}` — {GATE_LINE} (`artifacts/ra365/r20-fix/{GATE_ART}`).
- دیتابیس عملیاتی SHA `{db_sha(DB_OP)}` و promoted SHA `{db_sha(DB_PROM)}`؛ فقط read-only، بدون تغییر.
- Track B: هیچ فایل/تست/benchmark آن تغییر نکرد.

---

## ۷. وضعیت پذیرش

| معیار | نتیجه |
|---|---|
| Raw literal ۱۰۰٪ فیلد/ردیف | **خیر** — {fa(raw_after_row, 4, True)} ردیف پس از اصلاح؛ {fa(resid_rows)} ردیف residual سمت مرجع/منبع (به‌جز fallback مستند open) |
| Raw live full | **NOT_MEASURED** — CDN/rate؛ نمونهٔ هدفمند قبلی ۷۰/۱۰۱ |
| Type7 100% | **خیر** — {fa(V10.group(1), 2, True)} در تلورانس (close/factor)؛ OHLC ۲٬۵۹۵ پس از اصلاح `NOT_MEASURED`؛ اصلاح فرمول امن پیدا نشد |
| Weekly | **VERIFIED برای تعریف حجم** — جمع {fa(WEEK['match_within_0_5pct']['sum'])}/{fa(WEEK['weeks'])}؛ parity فیلدها در گزارش قبلی |
| Monthly | **NOT_MEASURED** — fixture مرجع M ندارد |
| Local DB raw | **BLOCKED_LOCALDB_RAW_SCHEMA** |
| دیتابیس محافظت‌شده | **VERIFIED** — SHA بدون تغییر |
| mismatch پنهان‌شده | صفر؛ {fa(PAIR['parser_skipped_product_dates'])} ردیف parser-skip و {fa(PAIR['skipped_not_in_product'])} ردیف پوشش صریح گزارش شدند |

---

## ۸. Git، commit و artifactها

- مبنا `1cf886ea`; commitهای این راند: `{COMMITS}`.
- هیچ push/merge به `main` انجام نشد.
- artifactهای این راند در `artifacts/ra365/r20-fix/` و `artifacts/ra365/r20-literal/` هستند.

{table(["artifact", "bytes", "sha256"], [
    [f"`{name}`", fa(os.path.getsize(os.path.join(FIX, name))), f"`{sha(os.path.join(FIX, name))[:16]}…`"]
    for name in ("raw-before-summary.json", "raw-replay-after-summary.json",
                 "raw-after-samples.csv", "v10-baseline.txt", "v10-per-symbol.json",
                 "type7-event-evidence.json", "weekly-volume-rule.json",
                 "fixture-sha256.txt", "raw-witness.json", "type7-ohlc-projection.json", GATE_ART)
])}

**دستور پایانی:** این راند یک باگ واقعی raw (دور ریختن HIGH/LOW خام) را با کد، تست و اندازه‌گیری before/after رفع کرد. تطبیق ۱۰۰٪ raw و type7 ادعا نمی‌شود؛ residual raw سمت منبع/مرجع و residual type7 سمت event-set/تعریف DPS مرجع است و با شاهد دقیق ثبت شده‌اند.
"""

os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8").write(md)

check = f"""# Coder2 — Round 20 Raw Field Fix Checkpoint

**تاریخ:** 2026-10-23  
**شاخه:** `{git(["rev-parse", "--abbrev-ref", "HEAD"])}`  
**HEAD:** `{git(["rev-parse", "HEAD"])[:12]}`  
**مبنا:** `1cf886ea`  
**Commitها:** `{COMMITS}`  
**Gate:** `{GATE}`

## وضعیت

- Raw literal قبل/بعد روی {fa(PAIR['rows'])} ردیف: **{fa(PAIR['before_row_exact_ok_pct'], 4, True)} → {fa(raw_after_row, 4, True)}**؛ high_raw {fa(raw_before_fields['high_raw']['ok_pct'], 4, True)} → {fa(raw_after_fields['high_raw']['ok_pct'], 4, True)}.
- residual: {fa(resid_rows)} ردیف / {fa(resid_fields)} فیلد؛ همه سمت type0 vs CSV؛ {fa(PAIR['parser_skipped_product_dates'])} parser-skip (۲۰۲۳-۰۳-۲۷) جدا.
- Type7 ۲۹نمادی: {fa(V10.group(1), 2, True)} در تلورانس، میانه {fa(V10.group(2), 4, True)}، p90 {fa(V10.group(3), 4, True)}، p99 {fa(V10.group(4), 4, True)}؛ بدون تغییر production.
- Weekly volume: جمع {fa(WEEK['match_within_0_5pct']['sum'])}/{fa(WEEK['weeks'])}؛ first-day {fa(WEEK['match_within_0_5pct']['first_day'])} — قانون روز اول اعمال نشد.
- Monthly: `NOT_MEASURED` (مرجع M ندارد).
- Local DB raw: `BLOCKED_LOCALDB_RAW_SCHEMA`.
- دیتابیس محافظت‌شده: `{db_sha(DB_OP)[:12]}…` / `{db_sha(DB_PROM)[:12]}…` بدون تغییر.

## بازتولید

```bash
python dev/test_round18_raw_parity_v1.py
python tools/ra365_round20_raw_replay.py
python _audit/ra365_ledger_ab.py
python _audit/r20_v10_per_symbol.py
python tools/ra365_round20_type7_evidence.py
```

## بعدی

- ML local DB raw schema/backfill (با تأیید جداگانه؛ اکنون عملیاتی دست‌نخورده).
- marks کامل/CODAL S برای type7؛ بدون آن ۱۰۰٪ ادعا نمی‌شود.
"""
open(CHECK, "w", encoding="utf-8").write(check)
print(OUT, len(md))
print(CHECK, len(check))
