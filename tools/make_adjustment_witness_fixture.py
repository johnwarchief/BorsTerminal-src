#!/usr/bin/env python3
# ── ۱) چرا این ابزار هست
# `dev/test_adjustment_engine_v1.py` شاخۀ «ج» خود را با نمونۀ واقعیِ تعدیل داوری می‌کند و
# آن نمونه را از `_audit/ra365_ref_bars.json` می‌خواند. آن فایل ~۱۲ مگابایت است و
# `_audit/*.json` درِ `.gitignore` پشتِ الگویِ ثبت‌شده می‌ماند (سیاستِ مخزن: کشیدنیِ خام
# کامیت نمی‌شود؛ جدول‌هایِ نتیجه که کامیت می‌شوند). نتیجه: رویِ یکِ ماشینِ تازه که فقط
# `git clone` کرده، آنِ suite به‌جای داوریِ واقعی به بندِ «ج۰ شاهدِ مرجع موجود نیست»
# می‌افتد و قرمز می‌شود — همان چیزی که درِ ممیزیِ ۲۰۲۶-۱۰-۱۵ (سیستمِ دوم) درِ worktree
# تازه دیده شد.
#
# ── ۲) چه می‌سازد
# یکِ زیرمجموعۀِ کوچکِ مستند از همانِ کشیدنی: فقط سطرهایِ چارتی و رویدادهایی که آنِ
# suite می‌خواند (دو نماد، type0/type7، دانۀ روزانہ) + بلوکِ provenance که lineage را
# ثابت می‌کند. خروجی درِ `dev/fixtures/` می‌نشیند، همانِ جایی که مخزن fixtureهایِ تست را
# نگه می‌دارد (`dev/fixtures/fts_v10_payloads.json`)؛ پس بی‌هیچ استثنایِ `.gitignore`
# درِ گیت ثبت می‌شود وِ بی‌`git add -f` منتشر می‌شود.
#
# ── ۳) نحوهٔ اجرا
#   python tools/make_adjustment_witness_fixture.py \
#       --src _audit/ra365_ref_bars.json --out dev/fixtures/ra365_witness_subset.json
# بی‌`--src` از کشیدنیِ اصلیِ همینِ چک‌اوت استفاده می‌کند؛ اگر آن نیست، هیچِ داده‌ای جعل
# نمی‌شود و ابزار با rc=2 می‌ایستد (بندِ ۵).
#
# ── ۴) تجدیدپذیری
# کشیدنیِ کامل با `ra365_job_fetch.js` دوباره ساخته می‌شود (۲۹ نماد × type0/type7 × D/W)
# — ولی آن نیازمندِ نشستِ احراز هویت‌شدۀ مالک درِ rahavard365 است و همانِ restriction
# درِ `docs/RAHAVARD-CANDLE-ADJUSTMENT-PARITY-1405-07-20.md` (بندِ فایل‌هایِ خام) ثبت
# شده. پس این زیرمجموعه همانِ باریکه‌ای است که «بی‌لاگینِ مالک هم شود داوری را دید» را
# ممکن می‌کند؛ عددِ میانۀِ خطایِ ج۴ از داده‌هایِ واقعی می‌آید، نه از تنظیم.
#
# ── ۵) چه چیزی را نمی‌سازد
# هیچ ردیف، ضریب یا نسبَتی را از پیشِ خودش نمی‌چیند و هیچِ مقدارِ مفقودی را صفر یا ۱
# نمی‌کند. اگر کلیدِ لازمِ یکی از نمادها درِ مبدأ نباشد، همانِ نماد را بی‌داده می‌گذارد
# و درِ گزارشِ stdout روشن می‌گوید کدامِ کلید مفقود است.
import argparse
import hashlib
import json
import os
import sys

WITNESS_SYMBOLS = ("وبصادر", "طلا")
SERIES_SUFFIXES = ("type0", "type7")
GRANULARITY = "D"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(src, out):
    with open(src, encoding="utf-8") as f:
        ref = json.load(f)
    bars = ref.get("bars") or {}
    meta = ref.get("meta") or {}

    subset = {"bars": {}, "meta": {}, "witness": {}}
    missing = []
    for sym in WITNESS_SYMBOLS:
        for suf in SERIES_SUFFIXES:
            key = f"{sym}|{suf}|{GRANULARITY}"
            entry = bars.get(key)
            if entry is None:
                missing.append(key)
                continue
            subset["bars"][key] = {"status": entry.get("status"), "bars": entry.get("bars") or []}
        mark_key = "marks|" + sym
        if mark_key in meta:
            subset["meta"][mark_key] = meta[mark_key]
        else:
            missing.append(mark_key)

    subset["witness"] = {
        "symbols": list(WITNESS_SYMBOLS),
        "series": [f"{s}|{x}|{GRANULARITY}" for s in WITNESS_SYMBOLS for x in SERIES_SUFFIXES],
        "granularity": GRANULARITY,
        "rows": {k: len(v.get("bars") or []) for k, v in subset["bars"].items()},
        "events": {("marks|" + s): len((((meta.get("marks|" + s) or {}).get("json") or {}).get("data") or []))
                   for s in WITNESS_SYMBOLS},
        "source": os.path.relpath(src, ROOT).replace("\\", "/"),
        "source_bytes": os.path.getsize(src),
        "source_sha256": _sha256(src),
        "corpus_size_at_capture": ref.get("corpusSize"),
        "made_by": "tools/make_adjustment_witness_fixture.py",
        "note": ("زیرمجموعۀِ کوچکِ مستند از کشیدنیِ کامل، برایِ بندِ «ج» سوئیتِ تعدیل. "
                 "مبدأ: ra365_job_fetch.js (نیازمندِ نشستِ مالک)."),
    }

    with open(out, "w", encoding="utf-8") as f:
        json.dump(subset, f, ensure_ascii=False, sort_keys=True, indent=1)

    print(f"[witness] wrote {out}  ({os.path.getsize(out):,} bytes from "
          f"{os.path.getsize(src):,} source bytes)")
    for k in sorted(subset["bars"]):
        e = subset["bars"][k]
        print(f"  bars  {k:<22} rows={len(e['bars'])} status={e['status']}")
    for k in sorted(subset["meta"]):
        n = len((((subset["meta"][k].get("json") or {}).get("data")) or []))
        print(f"  marks {k:<22} events={n}")
    if missing:
        print("  [WARN] این کلیدها درِ مبدأ پیدا نشدند (بی‌جعلِ داده): " + ", ".join(missing))
    return 0 if not missing else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(ROOT, "_audit", "ra365_ref_bars.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "dev", "fixtures", "ra365_witness_subset.json"))
    a = ap.parse_args()
    if not os.path.exists(a.src):
        print(f"[FAIL] مبدأِ کشیدنی موجود نیست: {a.src}")
        print("       یا فایل را از چک‌اوتِ اصلی کپی کنید یا با ra365_job_fetch.js بسازید؛"
              " این ابزار هیچ شاهدِ جعلی نمی‌سازد.")
        return 2
    return build(a.src, a.out)


if __name__ == "__main__":
    sys.exit(main())
