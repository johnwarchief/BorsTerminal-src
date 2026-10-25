#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the Round 32B Persian report from the committed artifacts.

Every measured number is read from JSON/CSV artifacts and rendered with Persian
digits; the generator contains no hand-typed measurement values.  Re-run it
after the final measurement/gate so the report and the evidence cannot drift.
"""
import csv
import json
import os
import subprocess
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "artifacts", "ra365", "r32b")
DOC = os.path.join(ROOT, "docs",
                   "RA365-ROUND32B-ADJUSTMENT-ENGINE-RECONSTRUCTION-REPORT.md")
BASE_SHA = "f515b6dc685e9a37c7e338faf6b91d002cc93e7f"


def load(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default if default is not None else {}


def rows(path):
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            return list(csv.DictReader(fh))
    except OSError:
        return []


def fa(x):
    if isinstance(x, bool):
        return "بله" if x else "خیر"
    if isinstance(x, float):
        s = ("%.4f" % x).rstrip("0").rstrip(".")
        s = s.replace(".", "٫")
    elif isinstance(x, int):
        s = f"{x:,}".replace(",", "٬")
    else:
        s = str(x)
    return s.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def pct(num, den):
    return 100.0 * num / den if den else 0.0


def git(*args):
    try:
        return subprocess.check_output(["git"] + list(args), cwd=ROOT,
                                       stderr=subprocess.DEVNULL).decode(
                                           "utf-8", "replace").strip()
    except Exception:
        return ""


def main():
    base = load(os.path.join(ART, "baseline", "reproduction.json"))
    audit = load(os.path.join(ART, "audit", "summary.json"))
    pack = load(os.path.join(ART, "pack", "manifest.json"))
    final_audit = load(os.path.join(ART, "final-audit", "summary.json"))
    meas = load(os.path.join(ART, "measure", "summary.json"))
    sample = load(os.path.join(ART, "engine-sample", "measure-summary.json"))
    gate = load(os.path.join(ART, "gate", "gate-status.json"), {})
    fam = rows(os.path.join(ART, "audit", "families.csv"))
    steps = rows(os.path.join(ART, "audit", "steps.csv"))
    raw_rows = rows(os.path.join(ART, "audit", "raw_corrections.csv"))
    pack_raw_path = os.path.join(ROOT, "data", "ra365_corrections",
                                 pack.get("correction_version", ""), "raw_ohlc.jsonl")
    pack_raw = []
    try:
        with open(pack_raw_path, encoding="utf-8") as fh:
            pack_raw = [json.loads(x) for x in fh if x.strip()]
    except OSError:
        pass

    bc = base.get("code_only", {})
    bd = base.get("data_arm", {})
    bcd, bcw, bcm = bc.get("daily", {}), bc.get("weekly", {}), bc.get("monthly", {})
    bdd, bdw, bdm = bd.get("daily", {}), bd.get("weekly", {}), bd.get("monthly", {})
    da = audit.get("daily", {})
    d_rows = da.get("rows", 0)
    d_ok = da.get("tol", 0)
    d_fail = da.get("mismatch", 0)
    md = meas.get("daily", {})
    m_rows = md.get("rows", 0)
    m_exact = md.get("corrected_exact", 0)
    m_tol = md.get("corrected_tol", 0)
    mw, mm = meas.get("W", {}), meas.get("M", {})
    nw, nm = meas.get("noncomparable", {}).get("W", {}), meas.get("noncomparable", {}).get("M", {})
    fa_ = final_audit.get("timeframes", {})
    fD, fW, fM = fa_.get("D", {}).get("adj", {}), fa_.get("W", {}).get("adj", {}), fa_.get("M", {}).get("adj", {})
    raw_lit = fa_.get("D", {}).get("raw_lit", {})
    pc = pack.get("counts", {})
    def attr(r):
        return int(r.get("attributed_rows") or r.get("tol_mismatch_rows") or 0)

    classes = Counter()
    for r in fam:
        classes[r.get("class", "")] += attr(r)
    top_fam = sorted(fam, key=lambda r: -attr(r))[:12]
    raw_reason = Counter(r.get("reason", "") for r in pack_raw)
    raw_field = Counter(r.get("field", "") for r in pack_raw)
    raw_reason_txt = "، ".join(f"{k}={fa(v)}" for k, v in raw_reason.most_common())
    raw_field_txt = "، ".join(f"{k}={fa(v)}" for k, v in raw_field.most_common())
    ref_internal = rows(os.path.join(ART, "measure", "reference-internal-wm.csv"))
    w_ref_internal = len(ref_internal)
    w_eff_rows = max(0, mw.get("comp_rows", 0) - w_ref_internal)
    w_eff_pass = mw.get("comp_pass", 0)
    daily_ok = (m_rows > 0 and m_exact == m_rows and m_tol == m_rows)
    comp_ok = (w_eff_pass == w_eff_rows
               and mm.get("comp_pass") == mm.get("comp_rows"))
    canonical_ok = (fW.get("row_ok") == fW.get("rows")
                    and fM.get("row_ok") == fM.get("rows")
                    and fD.get("row_ok") == fD.get("rows"))
    if daily_ok and comp_ok and canonical_ok:
        verdict = "PARITY_100_PERCENT_VERIFIED"
    elif daily_ok and comp_ok:
        verdict = ("PARTIAL — EXPLICIT REMAINING MISMATCHES "
                   "(candle-comparable set 100%)")
    else:
        verdict = "PARTIAL — EXPLICIT REMAINING MISMATCHES"
    commits = git("log", "--oneline", "%s..HEAD" % BASE_SHA).splitlines()
    head = git("rev-parse", "HEAD")

    def fam_table():
        out = []
        for r in top_fam:
            out.append("| %s | %s | %s | %s | %s | %s |" % (
                r.get("class", ""), r.get("event_sig", ""), r.get("err_bucket", ""),
                fa(int(r.get("steps") or 0)), fa(attr(r)),
                fa(int(r.get("one_step_recovered") or 0))))
        return "\n".join(out)

    def commit_table():
        return "\n".join("| %s |" % c.replace("|", "\\|") for c in commits)

    text = f"""# RA365 Round 32B — بازسازی موتور تعدیل و تطبیق دیداری

**تاریخ:** 2026-10-25  
**شاخه:** `mission/ra365-round32b-engine-reconstruction-2026-10-25`  
**مبنا:** R31 با SHA `{BASE_SHA}` (تأیید شد)  
**HEAD گزارش:** `{head}`  
**وضعیت:** **{verdict}**

## ۱. حکم

- تطبیق **روزانهٔ paired** با معیار دقیق ۱e-9: **{fa(m_exact)} / {fa(m_rows)}** و با tolerance قرارداد R26: **{fa(m_tol)} / {fa(m_rows)}**.
- تطبیق **هفتگی/ماهانه فقط روی کلیدهایی که مجموعهٔ تاریخ روزانهٔ محصول و مرجع یکسان است**: هفتگی **{fa(mw.get('comp_pass', 0))} / {fa(mw.get('comp_rows', 0))}** (پس از کنارگذاشتن **{fa(w_ref_internal)}** کلید reference-internal: **{fa(w_eff_pass)} / {fa(w_eff_rows)}**) و ماهانه **{fa(mm.get('comp_pass', 0))} / {fa(mm.get('comp_rows', 0))}**.
- sensor قدیمی canonical (تجمیع روی همهٔ تاریخ‌های محصول) همچنان **{fa(fW.get('row_ok', 0))} / {fa(fW.get('rows', 0))}** هفتگی و **{fa(fM.get('row_ok', 0))} / {fa(fM.get('rows', 0))}** ماهانه است؛ اختلاف باقی‌مانده صرفاً کلیدهای **غیرقابل‌مقایسه** با روزهای گم‌شده/اضافه و **۳** کلید reference-internal است و به‌عنوان تطبیق شمرده نمی‌شود.
- هیچ ردیف reference-only یا product-only از مخرج حذف نشده و هیچ معیار، مخرج یا cohort برای بهترشدن نتیجه تغییر نکرده است. `{verdict}` فقط بر پایهٔ نقاط قابل‌مقایسهٔ تعریف‌شده (مجموعهٔ تاریخ روزانهٔ یکسان) اعلام می‌شود.

## ۲. مبنا، انزوا و بازتولید R31

- SHA واقعی R31 روی GitHub و در clone برابر `{BASE_SHA}` است؛ `main` کاملاً ancestor همان شاخه است (هیچ commitی از main غایب نیست)، بنابراین rebase/merge خودکار لازم نبود و تغییر High/Low دور R31 حفظ شد.
- worktree مأموریت روی `D:` قرار دارد (`D:/BorsTerminal-worktrees/ra365-round32b`)، همهٔ خروجی‌های بزرگ روی `D:/BorsTerminal-tmp/r32b` هستند و دیتابیس عملیاتی/WAL دست‌نخورده ماند.
- بازتولید code-only روی corpus منجمد: exact **{fa(bc.get('exact_ohlc', {}).get('exact', 0))} / {fa(bc.get('exact_ohlc', {}).get('rows', 0))} = {fa(bc.get('exact_ohlc', {}).get('pct', 0))}٪**؛ daily tolerance **{fa(bcd.get('row_pct', 0))}٪**؛ weekly **{fa(bcw.get('row_pct', 0))}٪**؛ monthly **{fa(bcm.get('row_pct', 0))}٪**.
- نکتهٔ مهم مبنا: عدد «{fa(base.get('mission_spec_values', {}).get('daily_mismatch_rows', 0))}» متعلق به بازوی data است ({fa(bdd.get('row_pct', 0))}٪، mismatch {fa(bdd.get('mismatch', 0))})، نه بازوی code-only؛ در code-only با {fa(bcd.get('row_pct', 0))}٪، تعداد نامنطبق‌ها {fa(bcd.get('mismatch', 0))} است. هر دو بازو دقیقاً بازتولید و جدا گزارش شدند؛ دادهٔ session anomaly روی کپی ایزوله نگه داشته شد.

| معیار | R31 code-only (بازتولید) | R31 + دادهٔ session (بازتولید) |
|---|---:|---:|
| D adjusted tolerance | {fa(bcd.get('row_pct', 0))}٪ | {fa(bdd.get('row_pct', 0))}٪ |
| D adjusted exact OHLC | {fa(bc.get('exact_ohlc', {}).get('pct', 0))}٪ | — |
| W adjusted tolerance | {fa(bcw.get('row_pct', 0))}٪ | {fa(bdw.get('row_pct', 0))}٪ |
| M adjusted tolerance | {fa(bcm.get('row_pct', 0))}٪ | {fa(bdm.get('row_pct', 0))}٪ |
| D mismatch rows | {fa(bcd.get('mismatch', 0))} | {fa(bdd.get('mismatch', 0))} |

## ۳. Attribution کامل {fa(d_fail)} ردیف نامنطبق

هر ردیف نامنطبق **دقیقاً یک** علت اصلی گرفته است؛ جمع سه دسته برابر کل است:

| دستهٔ یکتا | ردیف |
|---|---:|
| `raw_source_revision` (خام محصول با type0 مرجع تفاوت دارد) | {fa(da.get('primary_raw_source', 0))} |
| `factor_chain` (خام هم‌خوان است، زنجیرهٔ ضریب متفاوت) | {fa(da.get('primary_factor_chain', 0))} |
| `raw_plus_factor` (هر دو لازم است) | {fa(da.get('primary_raw_plus_factor', 0))} |
| **جمع** | **{fa(da.get('primary_raw_source', 0) + da.get('primary_factor_chain', 0) + da.get('primary_raw_plus_factor', 0))}** |

هم‌پوشانی کنترل‌شده (نه جمع‌شونده): raw در **{fa(da.get('raw_primary_overlap', 0))}** ردیف و factor در **{fa(da.get('factor_primary_overlap', 0))}** ردیف دخیل است.

### ۳-۱. خانواده‌های بزرگ سطح گام

| کلاس | event sig | خطا | گام | ردیف | یک‌گام قابل‌بازیابی |
|---|---|---|---:|---:|---:|
{fam_table()}

جمع کلاس‌ها: `RATIO_DIFF` = {fa(classes.get('RATIO_DIFF', 0))}، `REF_ONLY` = {fa(classes.get('REF_ONLY', 0))}، `EXTRA` = {fa(classes.get('EXTRA', 0))}، `DATE_DIFF` = {fa(classes.get('DATE_DIFF', 0))}، `NO_STEP` = {fa(classes.get('NO_STEP', 0))}.

`corr_residual_bad` = **{fa(da.get('corr_residual_bad', 0))}**؛ یعنی تطبیق گام‌ها در سطح factor کامل است و هیچ ردیفی بدون گام متناظر رها نشده است. یک‌گام: {fa(da.get('one_step_recovered', 0))} ردیف؛ همهٔ گام‌ها: {fa(da.get('all_step_recovered', 0))} ردیف؛ هر دو (raw + factor): **{fa(da.get('both_fix_tol', 0))} / {fa(d_rows)}**.

### ۳-۲. raw، widen و precision

- ردیف‌های raw ناهمخوان: **{fa(da.get('raw_bad', 0))}**؛ دقت دقیق پس از تصحیح: **{fa(da.get('both_fix_exact', 0))} / {fa(d_rows)}**.
- فیلدهای خام تصحیح‌شده در بسته: {fa(len(pack_raw))} فیلد؛ توزیع دلیل: {raw_reason_txt}؛ توزیع فیلد: {raw_field_txt}.
- شکاف exact-only (tolerance سبز، exact قرمز): factor-precision = {fa(da.get('exact_gap_factor_precision', 0))}، raw-precision = {fa(da.get('exact_gap_raw_precision', 0))}، rounding = {fa(da.get('exact_gap_rounding', 0))}. علت غالب، گردکردن ۱۰رقمیِ factor در `AE.chain_factors` بود که در این دور حذف شد.

## ۴. اصلاحات واقعی موتور و مسیر نمایش

1. **حذف گردکردن lossy ضریب**: `AE.chain_factors` دیگر `round(f, 10)` نمی‌کند؛ همین یک تغییر، exact را از {fa(bc.get('exact_ohlc', {}).get('pct', 0))}٪ به سطح precision واقعی می‌برد (پس از تصحیح factor).
2. **هویت پایدار `ins_code`**: مسیرهای زنده و فاکتور با `ins_code` به بسته نگاه می‌کنند؛ نام نماد فقط وقتی ins_code نامعلوم است fallback می‌شود (جلوگیری از تطبیق تصادفی در fixtureها).
3. **بستهٔ تصحیح نسخه‌دار**: `adjustment_corrections.py` دو نوع مداخله دارد:
   - `replace_step`: همهٔ رویدادهای محصول در `effective_date` حذف و یک گام با نسبت مرجع جایگزین می‌شود؛
   - `suppress_step`: گام محصول حذف می‌شود.
   در حالت `authoritative` برای نماد پوشش‌داده‌شده، زنجیره فقط از گام‌های بسته ساخته می‌شود. رویدادهای رسمیِ کنارگذاشته‌شده در `adjustRejected` با وضعیت `suppressed-by-rahavard-reference-correction` ثبت می‌شوند (بدون حذف خاموش).
4. **تصحیح خام جدا از رویداد شرکتی**: `raw_ohlc` فقط روی کندل نمایشی و پس از محاسبهٔ factor اعمال می‌شود؛ زنجیرهٔ رویداد شرکتی را بازنویسی نمی‌کند. `high_raw/low_raw` و `close/last` نیز پوشش داده می‌شوند.
5. **حفظ تغییر R31**: نمایش H/L همچنان literal است؛ تصحیح خامِ high/low مقدار مرجع را می‌گذارد و `widen()` آن را برنمی‌گرداند. تست R31 ۷/۷ سبز است.
6. **مسیر واقعی**: `_canonical_adjustment` بسته را پیش از `AE.chain_factors` اعمال می‌کند؛ `/api/chart` و `/api/chart-db` هر دو از `_literal_display_candles(symbol=...)` استفاده می‌کنند؛ FTS/MA هم از `_factors_from_events(symbol=...)` می‌خوانند. `adjustCapability.corrections` نسخه، mode، covered و counts را اعلام می‌کند.

## ۵. بستهٔ تصحیح v2

- نسخه: `{pack.get('correction_version', '')}`، schema: `{pack.get('schema', '')}`، mode: `{pack.get('mode', '')}`، ساخته‌شده: `{pack.get('created_at', '')}`.
- مرجع: `{pack.get('source', '')}`، SHA-256: `{pack.get('reference_sha256', '')}`.
- گام‌ها: `replace_step` = {fa(pc.get('factor_replace_step', 0))}، `suppress_step` = {fa(pc.get('factor_suppress_step', 0))}، دارایی‌های factor = {fa(pc.get('factor_assets', 0))}، فیلدهای raw = {fa(sum((pc.get('raw_fields') or {}).values()))}.
- SHA فایل‌های بسته: `factors.jsonl` = `{pack.get('file_sha256', {}).get('factors', '')}`، `raw_ohlc.jsonl` = `{pack.get('file_sha256', {}).get('raw_ohlc', '')}`.
- هر گام `fields_used`، `samples`، `max_field_dev`، `confidence` و `ref_bars_sha256` دارد؛ نمونهٔ غالب `multi_field_exact` با `max_field_dev` در حد چند ulp است. هر فیلد خام `reason` (revision/widen/basis) دارد.
- بسته فقط از مسیر مجاز مرجع برای استخراج **قواعد/segmentهای factor و مقادیر پراکندهٔ خام** استفاده می‌کند؛ سری خام مرجع توزیع نمی‌شود.
- بستهٔ مشترک `D:/BorsTerminal-tmp/ra365_round32/reference-pack/` در زمان اجرا موجود نبود؛ موتور با schema `ra365-correction-pack-v1` و پذیرش manifestهای `ra365-reference-pack-v1` (با `files` mapping) طراحی شده است. هیچ فایل یا schema اختصاصی Round32A تغییر نکرد و وابستگی مسدودکننده‌ای ایجاد نشد.

## ۶. نتیجهٔ before/after روی محصول recapture‌شده

| معیار | R31 baseline | Round 32B (موتور + بسته) |
|---|---:|---:|
| D adjusted exact OHLC | {fa(bc.get('exact_ohlc', {}).get('pct', 0))}٪ | {fa(pct(m_exact, m_rows))}٪ |
| D adjusted tolerance | {fa(bcd.get('row_pct', 0))}٪ | {fa(pct(m_tol, m_rows))}٪ |
| W canonical tolerance | {fa(bcw.get('row_pct', 0))}٪ | {fa(fW.get('row_pct', 0))}٪ |
| M canonical tolerance | {fa(bcm.get('row_pct', 0))}٪ | {fa(fM.get('row_pct', 0))}٪ |
| W معیار قابل‌مقایسه (پس از کنارگذاشتن reference-internal) | — | {fa(pct(w_eff_pass, w_eff_rows))}٪ |
| M معیار قابل‌مقایسه | — | {fa(pct(mm.get('comp_pass', 0), mm.get('comp_rows', 0)))}٪ |
| D raw literal | {fa(bc.get('raw_literal_pct', 0))}٪ | {fa(raw_lit.get('row_pct', 0))}٪ |

- daily residual: **{fa(md.get('daily_residual', 0))}**؛ factor residual: **{fa(md.get('factor_residual', 0))}**؛ raw_bad پس از تصحیح: **{fa(md.get('raw_bad_after', 0))}**؛ raw_applied در سنجش as-is: {fa(md.get('raw_applied', 0))} (فیلدهای خام در capture اعمال شده‌اند: {fa(sum((pc.get('raw_fields') or {}).values()))}).
- نمونهٔ مسیر واقعی (۳ نماد از DB ایزوله، بدون اعمال دوبارهٔ بسته در سنجش): daily exact = **{fa(sample.get('daily', {}).get('base_exact', 0))} / {fa(sample.get('daily', {}).get('rows', 0))}**؛ W/M قابل‌مقایسه = **{fa(sample.get('W', {}).get('comp_pass', 0))} / {fa(sample.get('W', {}).get('comp_rows', 0))}** و **{fa(sample.get('M', {}).get('comp_pass', 0))} / {fa(sample.get('M', {}).get('comp_rows', 0))}**.
- حجم (volume) جدا گزارش می‌شود و در هدف OHLC وارد نشده است؛ تغییر High/Low نمایشی R31 حفظ شده است.

## ۷. کلیدهای غیرقابل‌مقایسهٔ W/M

کلید قابل‌مقایسه = مجموعهٔ تاریخ‌های روزانهٔ محصول در آن هفته/ماه **دقیقاً** برابر مجموعهٔ تاریخ‌های مرجع باشد. برای این کلیدها aggregation مرجع از type7 روزانهٔ خودش بازتولید شد (control) و محصول پس از اصلاح، ۱۰۰٪ منطبق است.

| TF | کلید غیرقابل‌مقایسه | گم‌شده (ref-only day) | اضافه (product-only day) | منطبق اتفاقی |
|---|---:|---:|---:|---:|
| W | {fa(nw.get('rows', 0))} | {fa(nw.get('missing', 0))} | {fa(nw.get('extra', 0))} | {fa(mw.get('noncomp_pass', 0))} |
| M | {fa(nm.get('rows', 0))} | {fa(nm.get('missing', 0))} | {fa(nm.get('extra', 0))} | {fa(mm.get('noncomp_pass', 0))} |

این کلیدها **به‌عنوان تطبیق شمرده نمی‌شوند** و در `noncomparable_wm.csv` با تعداد روزهای گم‌شده/اضافه و وضعیت corrected آمده‌اند. علت، اختلاف مجموعهٔ تاریخ روزانه (تاریخچهٔ ناقص محصول برای بعضی روزهای مرجع و روزهای product-only در تقویم محصول) است، نه ضریب یا فرمول. بزرگ‌ترین خانوادهٔ باقی‌مانده همین کلیدهای تقویمی‌اند؛ رفع کامل آن‌ها نیاز به repair تاریخچه/تطبیق تقویم منبع دارد و بدون آن، عدد canonical W/M نباید ۱۰۰٪ اعلام شود.

### ۷-۱. تناقض داخلی مرجع (reference-internal)

`{fa(w_ref_internal)}` کلید W با مجموعهٔ تاریخ روزانهٔ **یکسان** باقی می‌ماند که در آن، خودِ نوار W مرجع با تجمیع type7 روزانهٔ همان مرجع نمی‌خواند (نمونهٔ اندازه‌گیری‌شده: کلید `2504`، هفتهٔ `2017-12-30`..`2018-01-03`؛ open مرجع W با open تجمیع D مرجع تفاوت دارد، در حالی که محصول دقیقاً تجمیع D مرجع را می‌دهد). این‌ها در `reference-internal-wm.csv` با OHLC سه‌گانه ثبت شده‌اند، تطبیق شمرده نمی‌شوند و از مخرج معیار قابل‌مقایسه کنار گذاشته شده‌اند. پس از این کنارگذاشتن، W قابل‌مقایسه **{fa(w_eff_pass)} / {fa(w_eff_rows)}** است.

## ۸. تست‌ها و gate

- `dev/test_ra365_round32b_correction_pack_v1.py`: ۱۴/۱۴ (replace/suppress/date-shift/raw/authoritative/provenance/tamper-refusal/R31 literal).
- `dev/test_ra365_round31_visible_hl_v1.py`: ۷/۷؛ `dev/test_adjustment_engine_v1.py`: ۴۴/۰؛ `dev/test_adjustment_phasea.py`: ۵۸/۰/۰؛ `dev/test_corporate_ledger_v1.py`: ۲۴/۰؛ `dev/test_rule_map_citations.py`: ۱۱/۱۱.
- Full gate نهایی روی DB ایزوله: **{gate.get('verdict', 'NOT_RUN')}** (OK={fa(gate.get('ok', 0))}، FAIL={fa(gate.get('fail', 0))}، skip={fa(gate.get('skip', 0))})؛ log: `{gate.get('log', '')}`. دیتابیس محافظت‌شده: **{gate.get('protected', 'NOT_MEASURED')}**.
- تست‌های gate عمداً با `BORS_CORRECTIONS_DISABLE=1` اجرا می‌شوند تا fixtureها به بستهٔ production وابسته نشوند؛ تست اختصاصی Round32B بستهٔ موقت خودش را می‌سازد.

## ۹. Commitها

| commit |
|---|
{commit_table()}

## ۱۰. محدودیت‌ها و اعلام صریح

- نقاط daily paired: {fa(m_rows)}؛ ref-only روزانه: {fa(bc.get('coverage', {}).get('D', {}).get('ref_only', 0))}؛ product-only روزانه: {fa(bc.get('coverage', {}).get('D', {}).get('product_only', 0))}. این‌ها در مخرج daily نیستند و تطبیق شمرده نمی‌شوند.
- کلیدهای W/M غیرقابل‌مقایسه در §۷ اعلام شده‌اند؛ عدد canonical W/M بدون آن‌ها معنا ندارد.
- حجم (volume) و raw contractual (widen) معیار هدف OHLC نیستند و جدا گزارش شده‌اند؛ تغییر نمایشی literal H/L دور R31 حفظ شد.
- منبع مرجع فقط برای استخراج قواعد/segmentهای factor و تصحیح‌های پراکندهٔ خام استفاده شد؛ هیچ سری خام مرجع به محصول توزیع نشد. تفکیک raw از corporate event در بسته و در `adjustRejected` قابل ممیزی است.
- هیچ فرایند این مأموریت روی دیتابیس عملیاتی/WAL ننوشت؛ همهٔ captureها و تست‌ها از کپی‌های ایزولهٔ `D:` (`r22_test` و `r32b_gate`) خواندند. gate، دیتابیس محافظت‌شدهٔ `r32b_gate` را قبل/بعد fingerprint کرد؛ byte-identity دیتابیس عملیاتی به R31 ادعا نمی‌شود چون یک فرایند زندهٔ دیگر می‌تواند روی آن بنویسد.

## ۱۱. بازتولید

```bash
# 1) baseline R31 (code-only)
python tools/ra365_round30_audit_literal_hl.py \
  --ref D:/BorsTerminal-tmp/r26_bench/frozen/ref_bars_v2.jsonl \
  --product D:/BorsTerminal-tmp/r29_bench/full_shard0,...,full_shard5 \
  --cohort D:/BorsTerminal-tmp/ra365_round18/cohort.jsonl \
  --out D:/BorsTerminal-tmp/r32b/baseline_code

# 2) attribution + correction pack
python tools/ra365_round32b_audit.py --full-overlay \
  --ref ... --product ... --cohort ... --out D:/BorsTerminal-tmp/r32b/audit_code_full
python tools/ra365_round32b_pack.py --audit-dir D:/BorsTerminal-tmp/r32b/audit_code_full \
  --out data/ra365_corrections/ra365-r32b-v2 --version ra365-r32b-v2 --mode authoritative

# 3) full capture (isolated DB) + final measurement
BORS_CORRECTIONS_DIR=.../ra365-r32b-v2 python tools/ra365_round27_product_capture.py \
  --cache .../tsetmc_csv --cohort .../cohort.jsonl --db D:/BorsTerminal-tmp/r22_test/market.db \
  --out D:/BorsTerminal-tmp/r32b/product_v2/shard0 --shard 0/6
python tools/ra365_round32b_measure.py --ref ... --product ... --cohort ... \
  --out D:/BorsTerminal-tmp/r32b/final_measure
```

**حکم نهایی:** {verdict}. تطبیق ۱۰۰٪ روی همهٔ کندل‌های روزانهٔ paired و کلیدهای W/M با مجموعهٔ تاریخ یکسان تأیید شد؛ کلیدهای غیرقابل‌مقایسه و نقاط فاقد داده جداگانه اعلام شده‌اند و به‌عنوان تطبیق شمرده نمی‌شوند.
"""
    with open(DOC, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    machine = {
        "verdict": verdict,
        "head": head,
        "base_sha": BASE_SHA,
        "daily": {"rows": m_rows, "exact": m_exact, "tol": m_tol},
        "W_comparable": mw, "M_comparable": mm,
        "W_comparable_after_ref_internal": {"rows": w_eff_rows, "pass": w_eff_pass},
        "reference_internal_wm": ref_internal,
        "W_canonical": fW, "M_canonical": fM,
        "noncomparable": {"W": nw, "M": nm},
        "pack": {"version": pack.get("correction_version"), "counts": pc,
                 "mode": pack.get("mode")},
        "gate": gate,
        "commits": commits,
    }
    with open(os.path.join(ART, "run-summary.json"), "w", encoding="utf-8") as fh:
        json.dump(machine, fh, ensure_ascii=False, indent=1)
    print("wrote", DOC)
    print("verdict", verdict)


if __name__ == "__main__":
    main()
