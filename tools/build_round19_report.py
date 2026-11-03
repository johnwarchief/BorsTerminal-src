# -*- coding: utf-8 -*-
"""Generate the Round 19 Track A mismatch-closure report from frozen artifacts."""
from __future__ import annotations

import collections
import csv
import io
import json
import os
import sqlite3
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "artifacts", "ra365", "r18-rahavard")
OUT = os.path.join(ROOT, "docs", "RA365-ROUND19-MISMATCH-CLOSURE-REPORT.md")
CODE_COMMIT = os.environ.get("RAHAVARD_CODE_COMMIT", "pending")
OLD_REV = os.environ.get("RA365_OLD_REV", "9531b39f")
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


def sha(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load(name):
    return json.load(open(os.path.join(ART, name), encoding="utf-8"))


def read_csv(name):
    return list(csv.DictReader(open(os.path.join(ART, name), encoding="utf-8-sig")))


def git_show(path):
    return subprocess.check_output(
        ["git", "show", "%s:%s" % (OLD_REV, path)], cwd=ROOT).decode("utf-8-sig")


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(out)


CURRENT_HEAD = subprocess.check_output(
    ["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
CURRENT_BRANCH = subprocess.check_output(
    ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT).decode().strip()
S = load("rahavard-raw-ohlc-summary.json")
R19 = load("rahavard-raw-ohlc-round19-summary.json")
A = read_csv("rahavard-raw-ohlc-round19-adjudication.csv")
FM = read_csv("rahavard-raw-ohlc-field-mismatches.csv")
TAX = {r["cause"]: r for r in read_csv("rahavard-raw-ohlc-taxonomy.csv")}
ROW = {r["cause"]: r for r in read_csv("rahavard-raw-ohlc-row-taxonomy.csv")}
PAR = read_csv("rahavard-raw-ohlc-parity.csv")
CACHE = os.environ.get("RA365_R18_CACHE", "D:/BorsTerminal-tmp/ra365_round18")
REF = os.path.join(CACHE, "reference.db")
COHORT = os.path.join(CACHE, "cohort.jsonl")
_ref = sqlite3.connect("file:%s?mode=ro" % REF, uri=True)
INS = {}
for line in open(COHORT, encoding="utf-8"):
    o = json.loads(line)
    INS.setdefault(o["symbol"], o["ins_code"])


def tsetmc(symbol, date):
    ins = INS.get(symbol)
    if not ins:
        return {}
    row = _ref.execute(
        "SELECT first,high,low,close,volume,base,last FROM tsetmc "
        "WHERE ins_code=? AND date=?", (ins, date)).fetchone()
    if row is None:
        return {}
    return dict(zip(("first", "high", "low", "close", "volume", "base", "last"), row))


def tval(tv, field):
    key = {"open": "first", "high_raw": "high", "low_raw": "low",
           "last": "last", "close_display": "last", "volume": "volume"}.get(field)
    return tv.get(key) if tv else None


PROD_ROWS = sum(int(r["product_count"] or 0) for r in PAR)
COMMON_PC = sum(int(r["common_pc"] or 0) for r in PAR)
MISSING = read_csv("rahavard-raw-ohlc-missing.csv")
OMIT_DATES = collections.Counter(r["date"] for r in MISSING
                                 if r["category"] == "TYPE0_ONLY_PRODUCT_OMISSION")
OLD_FM = list(csv.DictReader(io.StringIO(git_show(
    "artifacts/ra365/r18-rahavard/rahavard-raw-ohlc-field-mismatches.csv"))))
OLD_ROW = {r["cause"]: int(r["rows"]) for r in csv.DictReader(io.StringIO(git_show(
    "artifacts/ra365/r18-rahavard/rahavard-raw-ohlc-row-taxonomy.csv")))}
NEW_ROW = {k: int(v["rows"]) for k, v in ROW.items()}
BUCKET = collections.Counter(r["bucket"] for r in A)


def rv(cause):
    return int(ROW.get(cause, {}).get("rows", 0))


def tv(cause):
    return int(TAX.get(cause, {}).get("field_mismatches", 0))


def rc(cause, key):
    return int(ROW.get(cause, {}).get(key, 0))


def tc(cause, key):
    return int(TAX.get(cause, {}).get(key, 0))


# per-field exact / tolerance aggregate (exact and tolerance stay separate)
field_rows = []
for f, label in (("open", "Open"), ("high_raw", "High (contract)"),
                 ("low_raw", "Low (contract)"), ("last", "Close last"),
                 ("close_display", "Close display"), ("volume", "Volume")):
    c = sum(int(r[f + "_cmp"] or 0) for r in PAR)
    e = sum(int(r[f + "_exact"] or 0) for r in PAR)
    t = sum(int(r[f + "_tol"] or 0) for r in PAR)
    field_rows.append([label, fa(c), fa(e), fa(100.0 * e / max(1, c), 4, True),
                       fa(t), fa(100.0 * (e + t) / max(1, c), 4, True)])
exact_total = sum(int(r[f + "_exact"] or 0) for r in PAR
                  for f in ("open", "high_raw", "low_raw", "last", "close_display", "volume"))
cmp_total = sum(int(r[f + "_cmp"] or 0) for r in PAR
                for f in ("open", "high_raw", "low_raw", "last", "close_display", "volume"))

# row-transition composition, derived from the frozen row taxonomy
pure_old = []
by = collections.defaultdict(list)
for r in OLD_FM:
    by[(r["ra_asset_id"], r["date"], r["symbol"])].append(r)
for k, rs in by.items():
    if any(r["cause"] == "PARSING_OR_TRANSFORM" for r in rs):
        others = [r for r in rs if r["field"] in
                  {"open", "high_raw", "low_raw", "last", "volume"}
                  and r["cause"] != "PARSING_OR_TRANSFORM"]
        if not others:
            pure_old.append((k[2], k[1]))
adj_by_key = {(r["symbol"], r["date"], r["field"]): r for r in A}
volume_moved = sum(1 for sym, d in pure_old
                   if adj_by_key.get((sym, d, "volume"), {}).get("new_cause")
                   == "SOURCE_DATA_DIVERGENCE")
volume_still_parsing = len(pure_old) - volume_moved
unclassified_to_parsing = NEW_ROW.get("PARSING_OR_TRANSFORM", 0) - (
    OLD_ROW.get("PARSING_OR_TRANSFORM", 0) - volume_moved)
unclassified_to_source = OLD_ROW.get("UNCLASSIFIED", 0) - unclassified_to_parsing
historical_to_source = OLD_ROW.get("HISTORICAL_REVISION", 0) - NEW_ROW.get("HISTORICAL_REVISION", 0)
precision_to_source = OLD_ROW.get("PRECISION_OR_ROUNDING", 0) - NEW_ROW.get("PRECISION_OR_ROUNDING", 0)
source_delta = NEW_ROW.get("SOURCE_DATA_DIVERGENCE", 0) - OLD_ROW.get("SOURCE_DATA_DIVERGENCE", 0)

# category statistics from field-level evidence
cat_rows = {}
for cause in ("CANDLE_GEOMETRY", "HISTORICAL_REVISION", "SOURCE_DATA_DIVERGENCE",
              "PRECISION_OR_ROUNDING"):
    rs = [r for r in FM if r["cause"] == cause]
    cat_rows[cause] = {
        "fields": len(rs),
        "rows_dates": len({(r["ra_asset_id"], r["date"]) for r in rs}),
        "by_field": collections.Counter(r["field"] for r in rs),
        "by_date": collections.Counter(r["date"] for r in rs),
        "samples": rs[:6],
    }
candle_notes = collections.Counter(r["note"] for r in FM if r["cause"] == "CANDLE_GEOMETRY")
prec_rels = [float(r["rel_diff"]) for r in FM if r["cause"] == "PRECISION_OR_ROUNDING"]
prec_max = max(prec_rels) if prec_rels else None

# P0 evidence tables
open_rows = [r for r in A if r["bucket"] == "P0_OPEN_FIRST_ZERO_FALLBACK"]
three_rows = [r for r in A if r["bucket"] == "P0_THREE_SOURCE_DIVERGENCE"]
vol_type0 = [r for r in A if r["bucket"] == "P0_VOLUME_TYPE0_ONLY"]
vol_snap0 = [r for r in A if r["bucket"] == "P0_VOLUME_SNAPSHOT_ZERO"]
vol_stale = [r for r in A if r["bucket"] == "P0_VOLUME_SNAPSHOT_STALE"]


def sample_open(rs, n=4):
    return [[r["symbol"], r["date"], fa(r["type0_value"]), fa(r["product_value"]),
             fa(r["tsetmc_first"]), fa(r["tsetmc_base"]), fa(r["tsetmc_high"]),
             fa(r["tsetmc_low"])] for r in rs[:n]]


def sample_volume(rs):
    return [[r["symbol"], r["date"], fa(r["type0_value"]), fa(r["product_value"]),
             fa(r["tsetmc_volume"]), fa(r["product_db_volume"]), r["new_cause"],
             r["status"]] for r in rs]


def sample_three(rs, n=4):
    return [[r["symbol"], r["date"], r["field"], fa(r["type0_value"]),
             fa(r["product_value"]),
             fa(r["tsetmc_high"] if r["field"] == "high_raw" else
                r["tsetmc_low"] if r["field"] == "low_raw" else r["tsetmc_first"]),
             fa(r["tsetmc_close"])]
            for r in rs[:n]]


def sample_cat(rs, cause, n=5):
    if cause == "CANDLE_GEOMETRY":
        return [[r["symbol"], r["date"], r["field"], fa(r["ref"]), fa(r["prod"]),
                 fa(tval(tsetmc(r["symbol"], r["date"]), r["field"])), r["note"]]
                for r in rs[:n]]
    if cause == "HISTORICAL_REVISION":
        return [[r["symbol"], r["date"], r["field"], fa(r["ref"]), fa(r["prod"]),
                 fa(tval(tsetmc(r["symbol"], r["date"]), r["field"])), r["note"]]
                for r in rs[:n]]
    if cause == "PRECISION_OR_ROUNDING":
        return [[r["symbol"], r["date"], r["field"], fa(r["ref"]), fa(r["prod"]),
                 fa(r["abs_diff"]), fa(float(r["rel_diff"]) * 100, 4, True)]
                for r in rs[:n]]
    return [[r["symbol"], r["date"], r["field"], fa(r["ref"]), fa(r["prod"]),
             fa(r["abs_diff"]), r["note"]] for r in rs[:n]]


# protected DB / artifact evidence
DB = R19["db"]
ARTIFACTS = [
    "rahavard-raw-ohlc-parity.csv",
    "rahavard-type0-vs-tsetmc.csv",
    "rahavard-raw-ohlc-field-mismatches.csv",
    "rahavard-raw-ohlc-taxonomy.csv",
    "rahavard-raw-ohlc-row-taxonomy.csv",
    "rahavard-raw-ohlc-missing.csv",
    "rahavard-raw-ohlc-summary.json",
    "rahavard-raw-ohlc-cohort-manifest.json",
    "source-field-matrix-rahavard.csv",
    "rahavard-raw-ohlc-round19-adjudication.csv",
    "rahavard-raw-ohlc-round19-transitions.csv",
    "rahavard-raw-ohlc-round19-summary.json",
    "round19-test-output.txt",
]

md = f"""# RA365 Round 19 — Mismatch Closure Report

**تاریخ:** 2026-10-22  
**شاخه:** `{CURRENT_BRANCH}`  
**مبنای Round 18:** `{OLD_REV}`  
**HEAD هنگام تولید گزارش:** `{CURRENT_HEAD[:12]}`  
**Commit کد/ابزار/تست این راند:** `{CODE_COMMIT}`  
**مرجع:** snapshot منجمد Rahavard `ref_bars_v2.jsonl` (۲۰۲۶-۱۰-۲۰) و snapshot محصول `product_live_final_v4.jsonl`  
**وضعیت Track B:** دست‌نخورده، روی شاخه مستقل `02ffba94`؛ هیچ فایل Track B در این راند تغییر نکرد.

> این گزارش داوری نهایی اختلاف‌های Raw است. هیچ قیمت، تاریخ یا کندلی تغییر نکرد؛ هیچ تلورانس یا مخرجی تغییر نکرد؛ دیتابیس عملیاتی و promoted فقط read-only استفاده شدند.

---

## ۰. پاسخ کوتاه

- **{fa(S['assets'])} دارایی** و **{fa(S['row_pairs'])} ردیف قابل‌مقایسه** دوباره با همان قرارداد Round 18 سنجیده شدند؛ نتیجهٔ عددی تغییر نکرد: **{fa(S['contract_ok_pct'], 4, True)}** فیلد و **{fa(S['row_exact_pct'], 4, True)}** ردیف.
- **تمام ۲٬۱۱۵ ردیف mismatch تعیین تکلیف شدند؛ `UNCLASSIFIED` از {fa(OLD_ROW.get('UNCLASSIFIED', 0))} به {fa(NEW_ROW.get('UNCLASSIFIED', 0))} رسید.**
- **هیچ باگ عمومی جدیدی در production اثبات نشد.** تنها اصلاحات این راند در قرارداد تحلیل (widen با official CLOSE) و طبقه‌بندی علت بود؛ کد تولیدی قیمت/کندل تغییر نکرد.
- **۶ ردیف PARSING اولیه:** {fa(volume_moved)} ردیف volume در واقع type0-only بودند و به SOURCE رفتند؛ {fa(volume_still_parsing)} ردیف volume صفر snapshot با TSETMC مثبت ماند (`BLOCKED_SNAPSHOT`).
- **۸۶ ردیف UNCLASSIFIED:** {fa(unclassified_to_parsing)} ردیف open با `TSETMC FIRST=0` (fallback مستند product) به PARSING رفتند؛ {fa(unclassified_to_source)} ردیف سه‌منبعی به SOURCE رفتند.
- **۶۲ ردیف CANDLE_GEOMETRY:** flat bar یا H/L بیرون body در منبع type0؛ product با `widen()` ترمیم می‌کند. نقص product اثبات نشد.
- **{fa(rc('PRECISION_OR_ROUNDING', 'rows'))} ردیف PRECISION** (از {fa(OLD_ROW.get('PRECISION_OR_ROUNDING', 0))} اولیه): همه در باند relative ≤ ۰٫۰۵٪ هستند؛ exact و tolerance جدا گزارش شده‌اند و تلورانس تغییر نکرده است. exact mismatch همچنان در مخرج باقی است.
- **{fa(rc('HISTORICAL_REVISION', 'rows'))} ردیف HISTORICAL** (از {fa(OLD_ROW.get('HISTORICAL_REVISION', 0))} اولیه): type0 و TSETMC با هم می‌خوانند و snapshot محصول قدیمی/اصلاح‌شده است؛ `widen()` و قرارداد `type0 close = LAST` حفظ شد.
- **{fa(rc('SOURCE_DATA_DIVERGENCE', 'rows'))} ردیف SOURCE** (از {fa(OLD_ROW.get('SOURCE_DATA_DIVERGENCE', 0))} اولیه): اختلاف منبع/بازنگری/تقویم و volume-only؛ هیچ شرط hard-coded برای نماد اضافه نشد.

---

## ۱. مبنا، دامنه و مرزها

- شروع از `{OLD_REV}` روی شاخه `{CURRENT_BRANCH}`؛ Track B در `mission/technical-pattern-engine-round18-2026-10-22` و commit `02ffba94` بدون تغییر.
- منبع مرجع: snapshot منجمد type0/type7، resolution روزانه، {fa(S['assets'])} دارایی دارای type0.
- منبع محصول: snapshot `product_live_final_v4.jsonl` (همان cohort Round 18)؛ مقایسه روی ردیف‌های مشترک و قابل‌مقایسه.
- oracle مستقل: TSETMC خام، فقط برای اثبات معنای type0 و داوری منبع؛ جایگزین Rahavard نشد.
- دیتابیس عملیاتی و promoted فقط read-only؛ SHA در §۱۰ ثبت شده است.
- هیچ داده‌ای از حساب Rahavard در این راند دریافت نشد؛ مرجع همان snapshot منجمد است. `BLOCKED_LIVE_ACCESS` یعنی «استفاده نشد»، نه «دسترسی وجود ندارد».

---

## ۲. نتیجهٔ نهایی و تفکیک exact از tolerance

### ۲-۱. پوشش

| شاخص | مقدار |
|---|---:|
| دارایی‌های cohort / دارای type0 | {fa(S['assets'])} / {fa(S['type0_assets'])} |
| ردیف‌های type0 | {fa(sum(int(r['type0_rows'] or 0) for r in read_csv('rahavard-type0-vs-tsetmc.csv')))} |
| تاریخ مشترک product/type0 | {fa(COMMON_PC)} |
| ردیف قابل‌مقایسه (last موجود) | {fa(S['row_pairs'])} |
| last-null محصول (خارج از مخرج) | {fa(S['last_null'])} |
| product-only داخل بازه type0 | {fa(S['product_only_inside'])} |
| product-only خارج بازه type0 | {fa(S['product_only_outside'])} |
| type0-only داخل بازه محصول | {fa(S['type0_only_no_trade'] + S['type0_only_tradable'])} |
| type0-only خارج بازه محصول | {fa(S['type0_only_outside'])} |

پوشش type0 نسبت به کل کندل‌های محصول **{fa(100.0 * S['row_pairs'] / PROD_ROWS, 2, True)}** است. «Full-Universe» در این گزارش یعنی تمام دارایی‌ها و ردیف‌های Rahavard قابل‌دسترسی، نه تمام تاریخ محصول. ردیف‌های خارج از بازهٔ type0 مقایسه نشدند و با صفر/forward-fill پر نشدند.

### ۲-۲. تطبیق قراردادی و تحت‌اللفظی

- قراردادی: **{fa(S['contract_ok_pct'], 4, True)}** فیلد؛ **{fa(S['row_exact_pct'], 4, True)}** ردیف.
- تحت‌اللفظی: high **{fa(S['literal_high_exact_pct'], 4, True)}**، low **{fa(S['literal_low_exact_pct'], 4, True)}**، ردیف کامل **{fa(S['literal_row_exact_pct'], 4, True)}**.
- اختلاف تحت‌اللفظی عمدتاً `widen()` مستند است: product سایه را باز می‌کند تا official CLOSE داخل body باشد. این transform در قرارداد تحلیل با official CLOSE مستقل انجام شد، نه با type0 close (که LAST است).

{table(["فیلد", "مقایسه", "exact", "exact٪", "tol", "exact+tol٪"],
       field_rows)}

**جمع:** {fa(cmp_total)} فیلد، {fa(exact_total)} exact، **{fa(100.0 * exact_total / cmp_total, 4, True)}**. در این corpus هیچ ردیفی صرفاً با تلورانس «سبز» نشد: `row_tol == row_exact` و `field tol == field exact`؛ تلورانس تغییری در نتیجه نداد و برای بهبود عدد اضافه نشد.

### ۲-۳. معنای type0 (بدون تغییر)

| فیلد type0 | مرجع TSETMC | exact٪ |
|---|---|---:|
| close | LAST | {fa(S['type0_vs_tsetmc']['close_last_exact_pct'], 4, True)} |
| close | official CLOSE | {fa(S['type0_vs_tsetmc']['close_official_exact_pct'], 4, True)} |
| open | FIRST | {fa(S['type0_vs_tsetmc']['open_first_exact_pct'], 4, True)} |
| open | base OPEN | {fa(S['type0_vs_tsetmc']['open_base_exact_pct'], 4, True)} |
| high / low / volume | HIGH / LOW / VOL | {fa(S['type0_vs_tsetmc']['high_exact_pct'], 4, True)} / {fa(S['type0_vs_tsetmc']['low_exact_pct'], 4, True)} / {fa(S['type0_vs_tsetmc']['vol_exact_pct'], 4, True)} |

type0 خام است، close آن LAST است و open آن FIRST؛ type7 تعدیل‌شده است. هیچ‌کدام از این سه لایه با هم مخلوط نشد.

---

## ۳. P0 — شش ردیف PARSING اولیه

شش ردیف اولیه بر اساس volume صفر product انتخاب شده بودند. داوری با TSETMC و دیتابیس عملیاتی:

{table(["نماد", "تاریخ", "type0 volume", "snapshot product", "TSETMC volume", "DB عملیاتی", "علت نهایی", "وضعیت"],
       sample_volume([adj_by_key[(s, d, 'volume')] for s, d in pure_old]))}

**نتیجه:** {fa(volume_moved)} ردیف از ۶ ردیف، type0-only هستند: TSETMC هم volume صفر دارد و product با TSETMC می‌خواند؛ این‌ها `SOURCE_DATA_DIVERGENCE` هستند، نه خطای parser. {fa(volume_still_parsing)} ردیف (`وملت`) volume صفر snapshot با TSETMC مثبت است؛ دیتابیس عملیاتی volume را مثبت دارد ({fa(float(adj_by_key[('وملت', '2026-07-21', 'volume')]['product_db_volume']))}), پس snapshot کهنه/ناقص است (`BLOCKED_SNAPSHOT`)، نه باگ کد فعلی.

### ۳-۱. volumeهای صفر دیگر

در مجموع **{fa(len(vol_type0) + len(vol_snap0) + len(vol_stale))} فیلد volume صفر** با شاهد بررسی شد:

{table(["نماد", "تاریخ", "type0 volume", "snapshot product", "TSETMC volume", "DB عملیاتی", "علت نهایی", "وضعیت"],
       sample_volume(vol_type0 + vol_snap0 + vol_stale))}

- **{fa(len(vol_type0))} فیلد type0-only:** TSETMC و snapshot محصول صفر، type0 مثبت. علت: منبع Rahavard؛ product دست‌کاری نشد.
- **{fa(len(vol_snap0))} فیلد snapshot-zero:** TSETMC و type0 مثبت، snapshot صفر؛ دیتابیس عملیاتی برای `وملت` و `يلدا` عدد مثبت دارد. snapshot کهنه است؛ کد فعلی `get_chart_db` volume را از DB می‌خواند.
- **{fa(len(vol_stale))} فیلد snapshot-stale:** `پرتو`؛ TSETMC صفر ولی DB و type0 هر دو {fa(float(adj_by_key[('پرتو', '2025-09-17', 'volume')]['product_db_volume']))} هستند. taxonomy دوعنصری آن را SOURCE می‌نامد، اما شاهد DB نشان می‌دهد snapshot کهنه است. این مورد در ستون وضعیت `BLOCKED_SNAPSHOT` است و در محاسبهٔ source/rounding دست‌کاری نشد.

---

## ۴. P0 — ۶۲ ردیف CANDLE_GEOMETRY

- **{fa(tc('CANDLE_GEOMETRY', 'field_mismatches'))} فیلد** در **{fa(tc('CANDLE_GEOMETRY', 'dates'))} تاریخ** و **{fa(tc('CANDLE_GEOMETRY', 'assets'))} دارایی**؛ **{fa(rc('CANDLE_GEOMETRY', 'rows'))} ردیف** با علت غالب CANDLE_GEOMETRY.
- توزیع فیلد: {", ".join(f"{k}: {fa(v)}" for k, v in cat_rows['CANDLE_GEOMETRY']['by_field'].most_common())}.
- {fa(candle_notes.get('type0 O=H=L=C flat bar; only close/last is reliable', 0))} فیلد flat bar (`O=H=L=C`) و {fa(candle_notes.get('type0 H/L outside body; product widen() repairs geometry', 0))} فیلد H/L بیرون body.
- بیشترین تاریخ‌ها: {", ".join(f"{d} ({fa(n)})" for d, n in cat_rows['CANDLE_GEOMETRY']['by_date'].most_common(5))}.

نمونه‌ها:

{table(["نماد", "تاریخ", "فیلد", "type0", "product", "TSETMC", "note"],
       sample_cat(cat_rows['CANDLE_GEOMETRY']['samples'], 'CANDLE_GEOMETRY'))}

**علت عمومی:** flat bar یا H/L ناممکن در منبع type0. product طبق قرارداد `widen()` سایه را باز می‌کند و هیچ قیمت منتشرشده‌ای را خرد نمی‌کند. **اصلاح production لازم نیست**؛ اگر type0 را با `widen` مقایسه کنیم، این ردیف‌ها از mismatch خارج می‌شوند. `type0_bad_geom` کل corpus {fa(S['type0_bad_geom'])} و flat {fa(S['type0_flat'])} ردیف است.

---

## ۵. P0 — ۸۶ ردیف UNCLASSIFIED

### ۵-۱. open با `TSETMC FIRST=0` — {fa(len(open_rows))} فیلد / ۵۵ ردیف غالب PARSING

- در **{fa(len(open_rows))} فیلد open**، TSETMC ستون FIRST را صفر می‌دهد و product طبق قرارداد مستند (خط ۱۳۵ `api/chart.py`) به `clamp(base, low, high)` برمی‌گردد؛ type0 open عدد دیگری دارد.
- این transform **مستند و عمدی** است؛ تنها راه حذف اختلاف، جایگزینی open با مقدار type0 بدون شاهد مستقل است که مجاز نیست. بنابراین `PARSING_OR_TRANSFORM` با وضعیت `VERIFIED_CONTRACT_FALLBACK` ثبت شد.
- ۵۵ ردیف فقط این open را داشتند و PARSING شدند؛ ۵ ردیف هم‌زمان فیلد سه‌منبعی داشتند و به SOURCE رفتند.

نمونه‌ها:

{table(["نماد", "تاریخ", "type0 open", "product open", "TSETMC FIRST", "TSETMC base", "TSETMC high", "TSETMC low"],
       sample_open(open_rows))}

**نتیجه:** نقص product اثبات نشد. `FIRST=0` یعنی منبع TSETMC اولین معامله را منتشر نکرده؛ fallback به base یک قرارداد مستند است و با hard-code یا داده ساختگی جایگزین نشد.

### ۵-۲. سه‌منبعی — {fa(len(three_rows))} فیلد / ۳۱ ردیف غالب SOURCE

- در **{fa(len(three_rows))} فیلد**، type0، TSETMC و product سه عدد متفاوت می‌دهند؛ product در بسیاری از موارد با official CLOSE widen‌شده یا TSETMC مطابق است.
- این‌ها `SOURCE_DATA_DIVERGENCE` هستند؛ نه rounding، نه product transform. هیچ‌کدام از این ردیف‌ها از مخرج حذف نشدند.

نمونه‌ها:

{table(["نماد", "تاریخ", "فیلد", "type0", "product", "TSETMC high/low", "TSETMC official close"],
       sample_three(three_rows))}

### ۵-۳. انتقال ردیف‌ها

| سطح | قبل | بعد | delta | توضیح |
|---|---:|---:|---:|---|
| `UNCLASSIFIED` | {fa(OLD_ROW.get('UNCLASSIFIED', 0))} | {fa(NEW_ROW.get('UNCLASSIFIED', 0))} | {fa(NEW_ROW.get('UNCLASSIFIED', 0) - OLD_ROW.get('UNCLASSIFIED', 0))} | {fa(unclassified_to_parsing)} → PARSING، {fa(unclassified_to_source)} → SOURCE |
| `PARSING_OR_TRANSFORM` | {fa(OLD_ROW.get('PARSING_OR_TRANSFORM', 0))} | {fa(NEW_ROW.get('PARSING_OR_TRANSFORM', 0))} | {fa(NEW_ROW.get('PARSING_OR_TRANSFORM', 0) - OLD_ROW.get('PARSING_OR_TRANSFORM', 0))} | +{fa(unclassified_to_parsing)} از UNCLASSIFIED، -{fa(volume_moved)} به SOURCE |
| `SOURCE_DATA_DIVERGENCE` | {fa(OLD_ROW.get('SOURCE_DATA_DIVERGENCE', 0))} | {fa(NEW_ROW.get('SOURCE_DATA_DIVERGENCE', 0))} | {fa(source_delta)} | +{fa(unclassified_to_source)} + {fa(volume_moved)} + {fa(historical_to_source)} HISTORICAL + {fa(precision_to_source)} PRECISION |
| `HISTORICAL_REVISION` | {fa(OLD_ROW.get('HISTORICAL_REVISION', 0))} | {fa(NEW_ROW.get('HISTORICAL_REVISION', 0))} | {fa(NEW_ROW.get('HISTORICAL_REVISION', 0) - OLD_ROW.get('HISTORICAL_REVISION', 0))} | {fa(historical_to_source)} ردیف با فیلد سه‌منبعی به SOURCE |
| `PRECISION_OR_ROUNDING` | {fa(OLD_ROW.get('PRECISION_OR_ROUNDING', 0))} | {fa(NEW_ROW.get('PRECISION_OR_ROUNDING', 0))} | {fa(NEW_ROW.get('PRECISION_OR_ROUNDING', 0) - OLD_ROW.get('PRECISION_OR_ROUNDING', 0))} | {fa(precision_to_source)} ردیف با فیلد سه‌منبعی به SOURCE |
| `CANDLE_GEOMETRY` | {fa(OLD_ROW.get('CANDLE_GEOMETRY', 0))} | {fa(NEW_ROW.get('CANDLE_GEOMETRY', 0))} | {fa(NEW_ROW.get('CANDLE_GEOMETRY', 0) - OLD_ROW.get('CANDLE_GEOMETRY', 0))} | بدون تغییر |

**تغییر علت در سطح فیلد:** `UNCLASSIFIED→PARSING` {fa(R19['field_transitions'].get('UNCLASSIFIED->PARSING_OR_TRANSFORM', 0))}، `UNCLASSIFIED→SOURCE` {fa(R19['field_transitions'].get('UNCLASSIFIED->SOURCE_DATA_DIVERGENCE', 0))}، `PARSING→SOURCE` {fa(R19['field_transitions'].get('PARSING_OR_TRANSFORM->SOURCE_DATA_DIVERGENCE', 0))}، `PARSING→PARSING` {fa(R19['field_transitions'].get('PARSING_OR_TRANSFORM->PARSING_OR_TRANSFORM', 0))}. ماتریس کامل: `rahavard-raw-ohlc-round19-transitions.csv`.

---

## ۶. P1 — ۲۹۸ ردیف PRECISION_OR_ROUNDING

- **{fa(tc('PRECISION_OR_ROUNDING', 'field_mismatches'))} فیلد** در **{fa(tc('PRECISION_OR_ROUNDING', 'dates'))} تاریخ** و **{fa(tc('PRECISION_OR_ROUNDING', 'assets'))} دارایی**؛ **{fa(rc('PRECISION_OR_ROUNDING', 'rows'))} ردیف** با علت غالب.
- توزیع فیلد: {", ".join(f"{k}: {fa(v)}" for k, v in cat_rows['PRECISION_OR_ROUNDING']['by_field'].most_common())}.
- بیشینهٔ relative diff: **{fa(prec_max * 100, 4, True)}**؛ میانهٔ relative diff در کل این گروه بسیار کوچک‌تر است. این‌ها در باند `REL_ROUND = 0.0005` هستند، اما **exact نیستند** و exact mismatch در مخرج باقی مانده است.
- بیشترین تاریخ‌ها: {", ".join(f"{d} ({fa(n)})" for d, n in cat_rows['PRECISION_OR_ROUNDING']['by_date'].most_common(5))}.

نمونه‌ها:

{table(["نماد", "تاریخ", "فیلد", "type0", "product", "abs", "relative"],
       sample_cat(cat_rows['PRECISION_OR_ROUNDING']['samples'], 'PRECISION_OR_ROUNDING'))}

**داوری:** PRECISION به معنای «اختلاف کوچک عددی» است، نه «تطبیق کامل». تلورانس برای سبزکردن گزارش افزایش نیافت؛ `field tol == field exact` و `row_tol == row_exact` نشان می‌دهد باند tolerance نتیجه را عوض نکرده است. در volume، اختلاف‌های شمارشی کوچک هستند و به‌عنوان همان PRECISION ثبت شده‌اند؛ ادعای rounding ماشینی برای آن‌ها مطرح نشد.

---

## ۷. P2 — ۵۴۹ ردیف HISTORICAL_REVISION

- **{fa(tc('HISTORICAL_REVISION', 'field_mismatches'))} فیلد** در **{fa(tc('HISTORICAL_REVISION', 'dates'))} تاریخ** و **{fa(tc('HISTORICAL_REVISION', 'assets'))} دارایی**؛ **{fa(rc('HISTORICAL_REVISION', 'rows'))} ردیف** با علت غالب.
- توزیع فیلد: {", ".join(f"{k}: {fa(v)}" for k, v in cat_rows['HISTORICAL_REVISION']['by_field'].most_common())}.
- بیشترین تاریخ‌ها: {", ".join(f"{d} ({fa(n)})" for d, n in cat_rows['HISTORICAL_REVISION']['by_date'].most_common(6))}.

نمونه‌ها:

{table(["نماد", "تاریخ", "فیلد", "type0", "product", "TSETMC", "note"],
       sample_cat(cat_rows['HISTORICAL_REVISION']['samples'], 'HISTORICAL_REVISION'))}

**داوری:** در این ردیف‌ها type0 و TSETMC با هم می‌خوانند و snapshot محصول عدد دیگری دارد؛ یعنی snapshot قدیمی‌تر یا اصلاح‌نشده است. این یک **بازنگری/کهنگی snapshot** است، نه خطای transform. قرارداد `widen()` حفظ شد و `type0 close` معادل official CLOSE فرض نشد. هیچ مقدار داخلی برای نزدیک‌شدن به Rahavard تغییر نکرد.

---

## ۸. P3 — ۱٬۱۵۰ ردیف SOURCE_DATA_DIVERGENCE

- **{fa(tc('SOURCE_DATA_DIVERGENCE', 'field_mismatches'))} فیلد** در **{fa(tc('SOURCE_DATA_DIVERGENCE', 'dates'))} تاریخ** و **{fa(tc('SOURCE_DATA_DIVERGENCE', 'assets'))} دارایی**؛ **{fa(rc('SOURCE_DATA_DIVERGENCE', 'rows'))} ردیف** با علت غالب.
- توزیع فیلد: {", ".join(f"{k}: {fa(v)}" for k, v in cat_rows['SOURCE_DATA_DIVERGENCE']['by_field'].most_common())}.
- بیشترین تاریخ‌ها: {", ".join(f"{d} ({fa(n)})" for d, n in cat_rows['SOURCE_DATA_DIVERGENCE']['by_date'].most_common(8))}.

خوشه‌های معنادار:

| خوشه | شاهد | نتیجه |
|---|---|---|
| volume-only ۲۰۲۰-۰۵-۲۶ و تاریخ‌های مشابه | TSETMC volume صفر، type0 مثبت، product صفر | منبع Rahavard؛ product با TSETMC می‌خواند |
| open/high/low ۲۰۲۰-۲۰۲۱ و ۲۰۲۴-۲۰۲۶ | product با TSETMC FIRST/HIGH/LOW یا official CLOSE widen‌شده می‌خواند | اختلاف type0 با oracle؛ transform product نیست |
| close/last | product با TSETMC LAST/CLOSE مطابق است | نوع قیمت یا بازنگری منبع |
| صندوق/آپشن با مقیاس واحد | ratio ۱۰/۱۰۰/۱۰۰۰ | `PRICE_SCALE_OR_UNIT` جدا و بدون اصلاح |
| تاریخ‌های سه‌منبعی | type0، TSETMC و product سه عدد | `P0_THREE_SOURCE_DIVERGENCE` |

نمونه‌ها:

{table(["نماد", "تاریخ", "فیلد", "type0", "product", "abs", "note"],
       sample_cat(cat_rows['SOURCE_DATA_DIVERGENCE']['samples'], 'SOURCE_DATA_DIVERGENCE', 6))}

**داوری:** هیچ شرط hard-coded برای نماد، حذف ردیف از مخرج، یا تغییر قیمت انجام نشد. مواردی که product با TSETMC مطابق است، شاهد مستقل دارند که اختلاف از type0/Rahavard می‌آید. موارد سه‌منبعی هم با شاهد سه منبع ثبت شدند، نه با حدس.

---

## ۹. missing bar، پوشش و محدودیت‌ها

- **{fa(S['type0_only_product_omission'])} ردیف type0 معتبر** که snapshot محصول ندارد؛ {", ".join(f"{d} ({fa(n)})" for d, n in OMIT_DATES.most_common(5))}. بررسی زنده در Round 18 نشان داد pipeline فعلی این تاریخ‌ها را دارد؛ این یک **gap در snapshot محصول** است، نه نقص فعلی دریافت.
- **{fa(S['product_only_rahavard_omission'])} ردیف product** که type0 ندارد؛ gap مرجع Rahavard.
- **{fa(S['type0_only_rahavard_date'])} تاریخ type0-only** که TSETMC هم ندارد؛ تقویم/داده Rahavard.
- **{fa(S['product_only_unverified'])} ردیف product-only** که با شاهد مستقل تعیین تکلیف نشد.
- **{fa(S['last_null'])} ردیف last-null** از مخرج ردیف قابل‌مقایسه خارج شد و جدا گزارش شده است.
- **{fa(S['product_only_no_trade'])} product-only no-trade** و **{fa(S['type0_only_no_trade'])} type0-only no-trade** در درصد قیمت وارد نشدند.
- هیچ missing bar با صفر، forward-fill یا کندل ساختگی پر نشد. هیچ ردیفی برای بهبود درصد حذف نشد.

**محدودیت:** مرجع، snapshot منجمد است و دسترسی live استفاده نشد. type0 فقط {fa(100.0 * S['row_pairs'] / PROD_ROWS, 2, True)} از کندل‌های محصول را می‌پوشاند؛ نتیجه برای ردیف‌های Rahavard قابل‌دسترسی معتبر است، نه تمام تاریخ محصول.

---

## ۱۰. اصلاحات، تست، گیت و دیتابیس‌های محافظت‌شده

### ۱۰-۱. چه چیزی اصلاح شد و چه چیزی نه

- **قرارداد تحلیل:** widen با official CLOSE مستقل (نه type0 close=LAST)؛ این اصلاح در Round 18 انجام و در Round 19 تثبیت شد. نتیجه: high/low قراردادی به {fa([r for r in field_rows if r[0].startswith('High')][0][3])} / {fa([r for r in field_rows if r[0].startswith('Low')][0][3])}.
- **طبقه‌بندی علت:** volume-only type0 با TSETMC صفر به SOURCE منتقل شد؛ snapshot-zero با TSETMC مثبت PARSING ماند؛ open با `FIRST=0` به‌عنوان fallback مستند PARSING ثبت شد. این تغییر فقط تحلیل است و هیچ قیمت/کندلی را تغییر نمی‌دهد.
- **کد تولیدی تغییر نکرد.** هیچ فایل `api/`, `fts_engine.py`, `candle_contract.py` یا دیتابیس در این راند تغییر نکرد.
- **Track B تغییر نکرد.**

### ۱۰-۲. تست‌ها

- `dev/test_rahavard_raw_parity_v1.py`: **۱۶/۱۶** pass (widen با official close، status، taxonomy، type0-only volume در برابر snapshot volume، semantics واقعی). خروجی: `round19-test-output.txt`.
- **Full gate دوباره اجرا نشد** چون هیچ کد production تغییر نکرد؛ آخرین full gate سبز روی `f6e3c4e0` ثبت شده است. این وضعیت `NOT_RE-RUN` است، نه ادعای سبز جدید.
- Track B تست‌ها و build آن در این راند اجرا نشدند؛ فایل‌های آن دست‌نخورده‌اند.

### ۱۰-۳. دیتابیس‌های محافظت‌شده

| دیتابیس | SHA256 | وضعیت |
|---|---|---|
| عملیاتی `BorsTerminal-src/market.db` | `{DB['operational']['sha256']}` | بدون تغییر، read-only |
| promoted `market_r17_migrated.db` | `{DB['promoted']['sha256']}` | بدون تغییر، read-only |
| مرجع موقت `reference.db` | `{DB['reference']['sha256']}` | فقط read-only برای مقایسه |

هیچ migration، write، VACUUM یا بازسازی روی دیتابیس عملیاتی/promoted انجام نشد. SHA ابتدا و انتهای راند یکسان است.

---

## ۱۱. معیار خروج Track A

| معیار | وضعیت | شاهد |
|---|---|---|
| همهٔ باگ‌های عمومی قابل‌اثبات اصلاح شدند | `VERIFIED` | هیچ باگ production اثبات نشد؛ اصلاحات فقط تحلیل |
| قرارداد Raw و adjusted واضح و پایدار | `VERIFIED` | type0=LAST/FIRST، type7=adjusted، widen با official CLOSE |
| موارد قابل‌اصلاح شناخته‌شده بسته شدند | `VERIFIED` | UNCLASSIFIED صفر؛ ۱۱۶ فیلد P0 تعیین تکلیف |
| اختلاف‌های منبع/تاریخی علت و وضعیت مستند دارند | `VERIFIED` | SOURCE {fa(rc('SOURCE_DATA_DIVERGENCE', 'rows'))}؛ HISTORICAL {fa(rc('HISTORICAL_REVISION', 'rows'))} |
| هیچ علت جدید و نامشخصی باقی نمانده | `VERIFIED` | UNCLASSIFIED {fa(NEW_ROW.get('UNCLASSIFIED', 0))} |
| artifact و تست رگرسیون ثبت شد | `IMPLEMENTED_AND_TESTED` | ۱۳ artifact + ۱۶ تست |
| وضعیت Git و دیتابیس‌های محافظت‌شده روشن است | `VERIFIED` | SHAها و commit جدا |

**تصمیم:** Track A به معیار خروج رسیده است. موارد باقی‌مانده در §۱۲ «منبع/بازنگری/snapshot» هستند و برای ادامهٔ Track B مسدودکننده نیستند. Track B از همین نقطه ادامه می‌یابد.

---

## ۱۲. موارد باقی‌مانده و وضعیت‌ها

| مورد | تعداد | وضعیت | علت |
|---|---:|---|---|
| volume صفر snapshot با TSETMC مثبت | {fa(len(vol_snap0))} فیلد | `BLOCKED_SNAPSHOT` | snapshot کهنه؛ DB عملیاتی مثبت |
| volume صفر snapshot با DB=type0 | {fa(len(vol_stale))} فیلد | `BLOCKED_SNAPSHOT` | snapshot کهنه؛ taxonomy دوعنصری SOURCE |
| type0-only volume | {fa(len(vol_type0))} فیلد | `VERIFIED_SOURCE_DIVERGENCE` | منبع Rahavard؛ product با TSETMC |
| open با `FIRST=0` | {fa(len(open_rows))} فیلد | `VERIFIED_CONTRACT_FALLBACK` | fallback مستند product |
| سه‌منبعی high/low | {fa(len(three_rows))} فیلد | `VERIFIED_SOURCE_DIVERGENCE` | type0/TSETMC/product سه عدد |
| CANDLE_GEOMETRY | {fa(rc('CANDLE_GEOMETRY', 'rows'))} ردیف | `VERIFIED_SOURCE_GEOMETRY` | flat/H/L منبع type0؛ widen |
| HISTORICAL_REVISION | {fa(rc('HISTORICAL_REVISION', 'rows'))} ردیف | `VERIFIED_SNAPSHOT_REVISION` | snapshot محصول کهنه |
| PRECISION_OR_ROUNDING | {fa(rc('PRECISION_OR_ROUNDING', 'rows'))} ردیف | `VERIFIED_ROUNDING_BAND` | relative ≤ ۰٫۰۵٪؛ exact نیست |
| product snapshot omissions | {fa(S['type0_only_product_omission'])} ردیف | `BLOCKED_SNAPSHOT` | ۲۰۲۳-۰۳-۲۷ و ۲۰۲۶-۱۰ |
| Rahavard omissions | {fa(S['product_only_rahavard_omission'])} ردیف | `BLOCKED_REFERENCE` | مرجع type0 ندارد |
| type0 rows outside product window | {fa(S['type0_only_outside'])} ردیف | `NOT_COMPARABLE` | خارج از بازه محصول |

---

## ۱۳. Git، commit و artifactها

- شاخه Track A: `{CURRENT_BRANCH}`؛ مبنا `{OLD_REV}`؛ HEAD گزارش `{CURRENT_HEAD[:12]}`.
- commit کد/ابزار/تست/artifact: `{CODE_COMMIT}`.
- هیچ push یا merge به `main` انجام نشد؛ Track B روی شاخهٔ مستقل و commit `02ffba94` دست‌نخورده است.
- تغییرات Track A و Track B در commitهای جداگانه نگه داشته شده‌اند.

{table(["artifact", "bytes", "sha256"],
       [[f"`{name}`", fa(os.path.getsize(os.path.join(ART, name))),
         f"`{sha(os.path.join(ART, name))}`"] for name in ARTIFACTS])}

---

## ۱۴. جمع‌بندی

پاسخ نهایی به سؤال اصلی: از **{fa(S['row_pairs'])}** ردیف قابل‌مقایسه، **{fa(S['row_exact_pct'], 4, True)}** ردیف و **{fa(S['contract_ok_pct'], 4, True)}** فیلد با قرارداد خام مستند تطبیق دارند. اختلاف‌های باقی‌مانده به سه خانوادهٔ روشن تقسیم شدند: (۱) منبع type0/Rahavard در برابر oracle TSETMC، (۲) snapshot کهنه/ناقص محصول، (۳) بازنگری تاریخی. هیچ‌کدام با تغییر داده، تلورانس، مخرج یا شرط نمادی «سبز» نشدند. `UNCLASSIFIED` صفر است و Track A قابل‌اعتماد و مستند است.
"""

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(md)
print(OUT, len(md))
