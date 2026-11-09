# کیتِ ادامهٔ Phase 4.8 — تاریخچه (S4) و Repair (S5)

این پوشه برای ادامهٔ کار در یک سشنِ دیگر است. گزارشِ نهایی و اعداد در
`FINAL-REPORT.md` است؛ اینجا مسیرها، هش‌ها، وضعیتِ کامیت‌شدن و فرمان‌های بازتولید
آمده است.

## وضعیتِ شاخه

| مورد | مقدار |
| --- | --- |
| شاخه | `mission/phase48-closeout-2026-11-09` |
| Base | `8d291ca2` |
| کدِ نهایی پیش از گزارش | `1c5be5df` |
| گزارشِ نهایی | `3b4edb12` |
| Merge / Tag / Release | انجام نشده |
| Push | فقط همین شاخه روی `johnwarchief/BorsTerminal-src` |

پوشهٔ حاضر در کامیتی بعد از `3b4edb12` اضافه شده است.

## یک نگاهِ سریع

```bash
python tools/phase48/continuation/verify_artifacts.py
```

برای هر ورودیِ `manifest.json` می‌گوید هست/نیست و هش می‌خواند یا نه. ورودی‌های
`committed` باید همیشه باشند؛ ورودی‌های `local` (DBهای بزرگ، بستهٔ مرجع، باینری‌های
آزمایشی) روی یک clone تازه معمولاً نیستند و خطا حساب نمی‌شوند. با `--strict` نبودنِ
آن‌ها هم خطا می‌شود و با `--json` گزارشِ کامل چاپ می‌شود.

## چه چیزی در گیت است

| مسیر | نقش |
| --- | --- |
| `tools/phase48/backfill_reference.py` | S4: Backfillِ فقط-مفقود از بستهٔ مرجع، Provenance و Rollback |
| `tools/phase48/verify_history_api.py` | S4: سنجشِ APIِ تاریخچه و زنجیرهٔ تعدیل (خام/تعدیل‌شده جدا) |
| `tools/phase48/verify_symbol_identity.py` | S4: بررسیِ `ins_code` و هویتِ نماد |
| `tools/phase48/repair/` | S5: هارنسِ Repairِ تعاملی، نسخهٔ مسیر‌پارامتری‌شده |
| `tools/phase48/continuation/evidence/` | شواهدِ JSONِ S4/S5 (خلاصه و آمار، نه سریِ خام) |
| `data/ra365_corrections/ra365-r32b-v2/` | پکِ اصلاحِ مشتق و پراکنده (از قبل در گیت بود) |
| `FINAL-REPORT.md` | گزارشِ نهایی با اعدادِ اندازه‌گیری‌شده |

## چه چیزی در گیت نیست (و چرا)

| مسیر | اندازه | sha256 | دلیل |
| --- | --- | --- | --- |
| `_audit/phase48/parity/ref/bars.ndjson.gz` | 6,710,605 | `68a1c803…` | دادهٔ اشتراکِ مالک؛ متادیتای ضبط: «not redistributable» |
| `_audit/phase48/parity/ref/symbols.json` | 4,447 | `d1b62739…` | فهرستِ ۳۰ نماد؛ همراهِ بستهٔ مرجع |
| `_audit/phase48/parity/ref/coverage.json` | 64,061 | `3333e660…` | پوششِ ۱۸۰ سریِ مرجع |
| `_audit/phase48/lab/market.db` | 267,472,896 | `bb57564b…` | DBِ منبعِ S4 |
| `_audit/phase48closeout/backfill/work/market.db` | 294,793,216 | `2b701ea3…` | DBِ کارِ S4 با ۷۲,۲۲۲ ردیفِ backfill |
| `_audit/phase48closeout/backfill/verify/market.db` | 294,793,216 | `2b701ea3…` | کپیِ بایت‌یکسان برای سنجشِ API |
| `_audit/phase48closeout/backfill/borsd_backfill_test.exe` | 22,161,920 | `aa448e77…` | بک‌اندِ آزمایشیِ S4 |
| `_audit/phase48closeout/installer/bundle/` | ۱۹۱ MB | چند فایل | باندلِ آزمایشیِ Repair |
| `_audit/phase48closeout/repair/out/BorsTerminal_RepairTest_Setup_v1.0.95.exe` | 22,221,082 | `0015050f…` | نصب‌کنندهٔ آزمایشیِ S5 |
| `_audit/phase48closeout/update/keys/test_ed25519.hex` | — | — | کلیدِ خصوصیِ آزمایشی؛ هرگز کامیت نشود |
| `_audit/phase48closeout/backfill/*/api_token.txt` | — | — | توکنِ آزمایشی؛ هرگز کامیت نشود |
| `installer/.setup_password.iss` | — | — | رمزِ نصاب؛ از قبل gitignored |

`bars.ndjson.gz` و ردیف‌هایِ خامِ backfill عمداً کامیت نشده‌اند: پکِ اصلاحِ گیت‌شده
فقط «مشتق و پراکنده» است و سیاستِ پروژه «no bulk raw series redistribution» دارد.
برای بازتولید، همین فایل روی همین ماشین در مسیرِ بالا هست. اگر جابه‌جا شد، با
`tools/phase45/rahavard/capture_rahavard.mjs` و
`tools/phase45/rahavard/import_capture.py` دوباره ضبط می‌شود؛ این کار به نشستِ
مرورگرِ مالک نیاز دارد (رجوع به `tools/phase45/rahavard/PROVENANCE.md`).

## بازتولیدِ S4 (Backfill)

DBِ کارِ فعلی شاهدِ اصلی است و نباید بازنویسی شود. برای اجرای تازه، یک پوشهٔ کارِ
نو بسازید:

```bash
python tools/phase48/backfill_reference.py apply \
  --src _audit/phase48/lab/market.db \
  --work _audit/phase48closeout/backfill/work-resume \
  --ref _audit/phase48/parity/ref/bars.ndjson.gz \
  --symbols _audit/phase48/parity/ref/symbols.json \
  --run-id rahavard-resume-$(date +%Y%m%dT%H%M%S) \
  --out _audit/phase48closeout/backfill/resume.json
```

- `--work` یک پوشه است؛ ابزار داخلش `market.db` می‌سازد. اگر آن فایل از قبل هست،
  بدون `--reuse-work` خطا می‌دهد (محافظِ عمدی).
- فقط تاریخ‌های غایب نوشته می‌شوند (`INSERT OR IGNORE` + بررسیِ صریح)؛ هیچ ردیفِ
  موجودی حذف یا بازنویسی نمی‌شود.
- Rollback فقط ردیف‌هایِ همان `run-id` را برمی‌دارد:

```bash
python tools/phase48/backfill_reference.py rollback \
  --work _audit/phase48closeout/backfill/work-resume \
  --run-id <same-run-id> \
  --out _audit/phase48closeout/backfill/resume-rollback.json
```

## سنجشِ API و زنجیرهٔ تعدیل

پوشهٔ `_audit/phase48closeout/backfill/verify/` از قبل آماده است: `market.db`،
`api_token.txt` و `market_seed.json` با `status=failed` (نشانگرِ عمدی برای جلوگیری
از mergeِ دوبارهٔ seed؛ آن را «تعمیر» نکنید). بک‌اند را روی همان پوشه و پورتِ ۸۱۵۷
بالا بیاورید:

```bash
export BORS_API_TOKEN="$(cat _audit/phase48closeout/backfill/verify/api_token.txt)"
_audit/phase48closeout/backfill/borsd_backfill_test.exe \
  --port 8157 --no-shell --no-loops \
  --db-dir _audit/phase48closeout/backfill/verify
```

اگر باینریِ آزمایشی نبود، از همان کدِ Go بسازید:

```bash
cd backend-go && go build -o ../_audit/phase48closeout/backfill/borsd_backfill_test.exe ./cmd/borsd && cd ..
```

سپس:

```bash
python tools/phase48/verify_history_api.py \
  --api http://127.0.0.1:8157 \
  --token-file _audit/phase48closeout/backfill/verify/api_token.txt \
  --ref _audit/phase48/parity/ref/bars.ndjson.gz \
  --symbols _audit/phase48/parity/ref/symbols.json \
  --db _audit/phase48closeout/backfill/verify/market.db \
  --pack data/ra365_corrections/ra365-r32b-v2/factors.jsonl \
  --out _audit/phase48closeout/backfill/verify-api-resume.json
```

`verify-api.json` و `verify-api.md` در همین پوشه (`evidence/`) شاهدِ اجرایِ ثبت‌شده
هستند. برای DBِ تازه، `--db` و `--db-dir` را به همان DBِ نو بگیرید و یک توکنِ تازه
(حداقل ۱۶ نویسه) بسازید؛ توکن را کامیت نکنید.

## اجرایِ مجددِ S5 (Repair)

پیش‌نیازها: باندلِ آزمایشی در `_audit/phase48closeout/installer/bundle/`، Inno Setup 6
و مهارتِ Computer Use. مسیرها را در صورتِ نیاز با `PHASE48_REPAIR_BASE`،
`PHASE48_REPAIR_BUNDLE` و `PHASE48_REPAIR_SETUP` عوض کنید.

```bash
python tools/phase48/repair/make_repair_iss.py
"/c/Program Files (x86)/Inno Setup 6/ISCC.exe" \
  _audit/phase48closeout/repair/bors_setup_repairtest.iss
python tools/phase48/repair/manual_repair.py init
python tools/phase48/repair/manual_repair.py start healthy
# جادوگر را با Computer Use بگردانید و manual-ui-healthy.json را بنویسید
python tools/phase48/repair/manual_repair.py verify healthy
```

`sandbox`: `%LOCALAPPDATA%\BorsTerminal_Phase48RepairTest\app`؛ پورتِ آزمون: ۸۱۵۸؛
AppIdِ آزمایشی: `{C3D84F60-2A19-4E7B-8C55-6F9A1B2D3E40}`. نصب‌کنندهٔ آزمایشی رمز
ندارد و `EnsureAppNotRunning`/`SweepOrphanLeftovers` قبل از بدنه `Exit` می‌کنند؛
نصب و Registryِ واقعی روی هیچ مسیری نیست.

شکلِ `manual-ui-<label>.json` که `verify` می‌خواند:

```json
{
  "ok": true,
  "source": "computer-use",
  "pages": {
    "maintenance": {"options": [{"name": "…", "selected": true}], "selected_index": 0},
    "directory": {"chosen": "<sandbox path>"},
    "ready": {"destination": "<sandbox path>"}
  }
}
```

سه نمونهٔ کامل در `tools/phase48/continuation/evidence/manual-ui-*.json` هست.
نسخهٔ اصلیِ هارنس (همان که شاهد را ساخت، همراه با تلاشِ ناموفقِ PowerShell-UIA) در
`_audit/phase48closeout/repair/` می‌ماند و در گیت نیست.

## تصمیمِ بازِ مالک

تنها بخشِ BLOCKED، تعدیلِ پیش از ۲۰۲۴ است. اعدادِ ثبت‌شده:

| سنجه | مقدار |
| --- | --- |
| گام‌های زنجیرهٔ `authoritative` | ۲۷۱ |
| گام‌های مرجع | ۵۰۱ |
| گام‌های Product | ۶۵۲ |
| گام‌های Productِ منطبق با مرجع که حذف می‌شوند | ۴۴۳ |
| تطابقِ دقیق OHLC پیش از ۲۰۲۴ | ۵۸.۲٪ (۶,۴۷۲ از ۱۱,۱۲۱) |
| بیشترین خطای نسبیِ ردیف‌هایِ جدید | ۲۴۴۶.۲۹ |

راه‌حل‌ها (نیازمندِ تأییدِ جداگانهٔ مالک): بازسازیِ بستهٔ کامل یا Overlayِ Product.
هیچ آستانه یا معیارِ تازه‌ای در این کیت ابداع نشده است.

## قیدهای ثابت

- Merge به main، Tag و Release انجام نشود.
- فاز ۵ و اندیکاتور/استراتژیِ تازه شروع نشود.
- `/fts-screen`، `approval_enabled=false`، Q1 Deferred، رتبه‌بندیِ Lexicographic و
  نبودِ Composite Score/Weight دست‌نخورده بمانند.
- کلیدِ خصوصی، توکن و رمزِ نصاب در هیچ فایلِ گیت‌شده‌ای نیاید.
- DBِ عملیاتی و نصبِ واقعی فقط با کپی و Backup لمس شوند.
