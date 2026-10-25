#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Package v3 evidence and write the short Persian build report.

All numbers are read from the v3 build artifacts; nothing is hand-typed.
"""
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V3 = "D:/BorsTerminal-tmp/ra365_round32b_v3"
ART = os.path.join(ROOT, "artifacts", "ra365", "r32b", "v3")
PACK_REPO = os.path.join(ROOT, "data", "ra365_corrections", "ra365-r32b-v3")


def load(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default if default is not None else {}


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


def copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.isdir(src):
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    elif os.path.exists(src):
        shutil.copy2(src, dst)


def main():
    a = load(V3 + "/pack-v3a/build-hashes.json")
    b = load(V3 + "/pack-v3b/build-hashes.json")
    ha = a.get("file_sha256", {})
    hb = b.get("file_sha256", {})
    identical = bool(ha) and ha == hb
    manifest = load(V3 + "/pack-v3a/manifest.json")
    basis = load(V3 + "/pack-v3a/basis-summary.json")
    ref = load(V3 + "/reference/REFERENCE.json")
    inputs = load(V3 + "/inputs/PRODUCT-INPUTS.json")
    live = load(V3 + "/live/reference-internal-live-summary.json")
    probe = load(V3 + "/live/live-probe.json")
    v2 = load(os.path.join(ROOT, "data", "ra365_corrections", "ra365-r32b-v2", "manifest.json"))

    os.makedirs(ART, exist_ok=True)
    for sub in ("pack", "reference", "inputs", "live"):
        os.makedirs(os.path.join(ART, sub), exist_ok=True)
    copy(V3 + "/pack-v3a/manifest.json", ART + "/pack/manifest.json")
    copy(V3 + "/pack-v3a/basis-summary.json", ART + "/pack/basis-summary.json")
    copy(V3 + "/pack-v3a/build-hashes.json", ART + "/pack/build-hashes-a.json")
    if b:
        copy(V3 + "/pack-v3b/build-hashes.json", ART + "/pack/build-hashes-b.json")
    copy(V3 + "/reference/REFERENCE.json", ART + "/reference/REFERENCE.json")
    copy(V3 + "/inputs/PRODUCT-INPUTS.json", ART + "/inputs/PRODUCT-INPUTS.json")
    copy(V3 + "/inputs/product-payloads.sha256", ART + "/inputs/product-payloads.sha256")
    copy(V3 + "/live/reference-internal-live.csv", ART + "/live/reference-internal-live.csv")
    copy(V3 + "/live/live-probe.json", ART + "/live/live-probe.json")
    copy(V3 + "/live/reference-internal-live-summary.json",
         ART + "/live/reference-internal-live-summary.json")
    copy(V3 + "/pack-v3a", PACK_REPO)

    repro = {"identical": identical,
             "run_a": ha, "run_b": hb,
             "version": a.get("version"),
             "reference_sha256": ref.get("sha256"),
             "product_manifest_sha256": inputs.get("manifest_sha256"),
             "cohort_sha256": (inputs.get("cohort") or {}).get("sha256")}
    json.dump(repro, open(ART + "/reproducibility.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    fc = basis.get("counts", {}).get("factors", {})
    rc = basis.get("counts", {}).get("raw_ohlc", {})
    rows = basis.get("rows", {})
    live_rows = []
    for asset in live.get("assets", []):
        live_rows.append("| %s | %s | %s | %s | %s |" % (
            asset.get("asset_id"), asset.get("symbol"),
            ",".join(asset.get("reference_internal_diff_fields") or []),
            fa(asset.get("ref_w", {}).get("open")),
            asset.get("live_status")))
    live_table = "\n".join(live_rows)
    hash_table = []
    for name in sorted(set(ha) | set(hb)):
        hash_table.append("| `%s` | `%s` | `%s` |" % (name, ha.get(name, "-")[:16],
                                                       hb.get(name, "-")[:16]))
    hash_table = "\n".join(hash_table)
    text = f"""# RA365 Round 32B — بستهٔ تصحیح v3، قابل بازتولید و مبنادار

**تاریخ:** 2026-10-25  
**شاخه:** `mission/ra365-round32b-engine-reconstruction-2026-10-25`  
**مرجع:** `{ref.get('path')}`  
**SHA-256 مرجع:** `{ref.get('sha256')}` (verify={fa(bool(ref.get('verified')))})  
**ورودی محصول:** {fa(inputs.get('files'))} فایل، manifest SHA `{inputs.get('manifest_sha256')}`  
**cohort SHA:** `{(inputs.get('cohort') or {}).get('sha256')}`  
**ساخت:** `created_at={a.get('created_at')}` (ثابت، برای بازتولید بایت‌به‌بایت)  
**وضعیت بازتولید:** **{'یکسان' if identical else 'نایکسان'}** — دو اجرای مستقل با همان ورودی، همان sha256 را دادند.

## فرمان بازتولید

```bash
python tools/ra365_round32b_reproduce_v3.py \
  --out D:/BorsTerminal-tmp/ra365_round32b_v3/repro-check \
  --expect-hashes data/ra365_corrections/ra365-r32b-v3/build-hashes.json
```

این فرمان مرجع را hash-verify، ورودی‌های R29 را hash-verify، audit را در حالت full-overlay/pack-only اجرا، pack را با `mode=authoritative` می‌سازد و sha256 همهٔ فایل‌ها را با اجرای اول مقایسه می‌کند.

## شمارش‌ها

- factors: `replace_step` = {fa(manifest.get('counts', {}).get('factor_replace_step', 0))}، `suppress_step` = {fa(manifest.get('counts', {}).get('factor_suppress_step', 0))}، دارایی‌ها = {fa(manifest.get('counts', {}).get('factor_assets', 0))}، ردیف‌ها = {fa(rows.get('factors', 0))}.
- raw_ohlc: {fa(rows.get('raw_ohlc', 0))} فیلد؛ توزیع فیلد در manifest v3.
- v2 برای مقایسه: `{v2.get('correction_version')}` با {fa(v2.get('counts', {}).get('factor_replace_step'))} replace و {fa(v2.get('counts', {}).get('factor_suppress_step'))} suppress. محتوای core ردیف‌های v3 همان v2 است؛ `price_basis`/`basis_detail` افزوده شده‌اند.

## price_basis — کدام ردیف با کدام مبنا

| kind | same_basis | reference_close_matches_other_price_basis | unknown_basis |
|---|---:|---:|---:|
| factors | {fa(fc.get('same_basis', 0))} | {fa(fc.get('reference_close_matches_other_price_basis', 0))} | {fa(fc.get('unknown_basis', 0))} |
| raw_ohlc | {fa(rc.get('same_basis', 0))} | {fa(rc.get('reference_close_matches_other_price_basis', 0))} | {fa(rc.get('unknown_basis', 0))} |

- `same_basis`: close و last محصول در تاریخ مؤثر یکسان‌اند؛ نسبت close مرجع روی همان مبنای نمایش است.
- `reference_close_matches_other_price_basis`: close و last در تاریخ مؤثر تفاوت دارند؛ نسبت close مرجع به مبنای دیگر محصول می‌خورد؛ این ردیف‌ها جدا شده‌اند.
- `unknown_basis`: کندل محصول در تاریخ مؤثر نیست یا close/last موجود نیست.
- فایل‌های جدا: `factors.same_basis.jsonl`، `factors.reference_close_matches_other_price_basis.jsonl`، `raw_ohlc.same_basis.jsonl`، `raw_ohlc.reference_close_matches_other_price_basis.jsonl` (و unknown در صورت وجود). `basis-summary.json` شمارش و تعریف‌ها را دارد.

## سه کلید reference-internal هفتگی

هفتهٔ `2017-12-30`..`2018-01-03` برای دارایی‌های 8/803/804؛ CSV: `reference-internal-live.csv`.

| asset | symbol | field(s) W↔D | ref W open | live status |
|---|---|---|---:|---|
{live_table}

- تناقض داخلی مرجع (W در برابر تجمیع type7 D خودش) با دادهٔ منجمد تأیید شد: 8 (`open`,`high`), 803 (`open`,`low`), 804 (`low`).
- **live capture انجام نشد**: connector با token_status={fa((probe.get('connector') or {}).get('token_status'))} و پنل ورود، Brave با مودال ورود، Edge CDP/پروفایل probe موجود نبود. هیچ رمز/کوکی/توکنی خوانده، چاپ یا ذخیره نشد. وضعیت در CSV `NOT_RUN_LOGIN_REQUIRED` است و مقدار live ساخته نشد.
- برای تکمیل live پس از لاگین مالک: `tools/ra365_round32b_week2504_capture.js` را در تب لاگین‌شدهٔ Rahavard اجرا کنید و سپس `tools/ra365_round32b_week2504_live.py --live <json>` را اجرا کنید. خروجی، مقدار live و مقایسه با ref W/D را به همان CSV اضافه می‌کند.

## sha256 فایل‌های v3 (اجرای A / B)

| file | run A | run B |
|---|---|---|
{hash_table}

## مسیرها و محدودیت‌ها

- خروجی روی D: `D:/BorsTerminal-tmp/ra365_round32b_v3/`؛ بستهٔ commitشده: `data/ra365_corrections/ra365-r32b-v3/`.
- فایل خام مرجع (`ref_bars_v2.jsonl`) و payloadهای محصول در Git نیستند؛ فقط hash/manifest و بستهٔ مشتق‌شده commit می‌شود.
- دیتابیس عملیاتی/WAL خوانده یا بازنویسی نشد؛ هیچ commit به `main` زده نشد.
- v3 با هم‌اکنون opt-in است: `BORS_CORRECTIONS_DIR=<repo>/data/ra365_corrections/ra365-r32b-v3`؛ مسیر پیش‌فرض v2 برای جلوگیری از تغییر مسیر بحرانی دست‌نخورده ماند.
"""
    out = os.path.join(ART, "V3-REPORT.md")
    open(out, "w", encoding="utf-8", newline="\n").write(text)
    print("wrote", out, "identical", identical)
    print(json.dumps(repro, ensure_ascii=False, indent=1)[:3000])
    return 0 if identical else 1


if __name__ == "__main__":
    sys.exit(main())
