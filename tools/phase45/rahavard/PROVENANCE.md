# PROVENANCE — درایورِ ضبطِ Rahavard در فاز ۴٫۵

| قلم | مقدار |
| --- | --- |
| فایلِ مبدأ | `D:/BorsTerminal-tmp/ra365_round32/wt/tools/ra365/r32-reference/capture_rahavard.mjs` |
| مخزنِ مبدأ | worktreeِ R32A؛ commit `7e0c630dc790d0e857ad4407beb55bbb5c176c42` (2026-10-25) |
| SHA-256 مبدأ | `6fcb9c53f13ff0e29713001c6f5eef8dd683a383385a12341ad74cb412553cd3` |
| SHA-256 نسخهٔ پورت‌شده | همان (کپیِ بایت‌به‌بایت؛ هیچ تغییری ندادم) |
| مجوز | کدِ اصلیِ همین پروژه؛ هیچ کدِ ثالثی وارد نشده. دادهٔ مرجع اشتراکِ مالک است و بازتوزیع نمی‌شود. |

## چه چیزی پورت شد و چه چیزی نه

فقط درایورِ ضبط (`capture_rahavard.mjs`) پورت شد، چون تنها قطعه‌ای است که با
مرورگرِ مالک حرف می‌زند. خطِ لولهٔ R32 (`import_reference.py`،
`infer_factor_segments.py`، `build_mismatch_ledger.py`، `pack.py`) پورت نشد؛
مأموریتِ ۴٫۵ به آن خطِ لوله نیاز ندارد. به‌جای آن `import_capture.py` فقط
خروجیِ همین درایور را به `bars.ndjson.gz` + `coverage.json` نرمال می‌کند.

## قاعدهٔ رمز

درایور توکن را **داخلِ صفحه** از `/api/v2/accounts/access-token` می‌گیرد،
روی `window` همان صفحه کش می‌کند و هرگز به Node برنمی‌گرداند. در گزارش‌ها و
فایل‌هایِ خروجی هیچ کوکی، توکن، شناسهٔ حساب یا رمزی نوشته نمی‌شود. خروجیِ
ضبط فقط OHLCV و متادیتایِ عمومی است. این با قیدِ §3 مأموریت یکی است.

## اجرا

```bash
# ۱) پنجرهٔ ضبط را باز کنید و در همان پنجره واردِ Rahavard شوید
node tools/phase45/rahavard/capture_rahavard.mjs --launch --probe-auth --port 9333
#    exit 3 = هنوز وارد نشده‌اید؛ exit 0 = نشست معتبر است

# ۲) ضبطِ D/W/M برایِ نوعِ خام و تعدیل‌شده
node tools/phase45/rahavard/capture_rahavard.mjs \
  --symbols _audit/phase45/rahavard/symbols.json \
  --out _audit/phase45/rahavard/capture.json \
  --types type0,type7 --res D,W,M --countback 700 \
  --from 2010-01-01T00:00:00Z --to 2026-11-10T00:00:00Z --marks

# ۳) نرمال‌سازی (خروجی و `_audit/phase45/` محلی و gitignored است)
python tools/phase45/rahavard/import_capture.py \
  --in _audit/phase45/rahavard/capture.json \
  --out _audit/phase45/rahavard/normalized
```

`--countback 700` سقفِ کندلِ هر سری است؛ برایِ پوششِ کاملِ ۳۰ نماد کافی است.
`--types type0` خام و `type7` تعدیل‌شده است. ریسکِ ماهانه (تکرارِ هر کندل ~۳ بار)
در `import_capture.py` با `duplicate_rows_dropped` و `conflicting_duplicates`
جدا شمرده می‌شود.
