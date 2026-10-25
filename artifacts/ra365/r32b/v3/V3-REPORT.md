# RA365 Round 32B — بستهٔ تصحیح v3، قابل بازتولید و مبنادار

**تاریخ:** 2026-10-25  
**شاخه:** `mission/ra365-round32b-engine-reconstruction-2026-10-25`  
**مرجع:** `D:/BorsTerminal-tmp/ra365_round32b_v3/reference/ref_bars_v2.jsonl`  
**SHA-256 مرجع:** `4b1ecb4c1effc4d5770c42521d96a2540a9c9f7b471d7cc710cd034712a8c17c` (verify=بله)  
**ورودی محصول:** ۲٬۵۹۴ فایل، manifest SHA `95875648306ae418a3fbff371bb34fb8a1e3c0eb2323ea0e18c9782505a8d28e`  
**cohort SHA:** `79a3c666c2b49363fd5b7a2684ee776d034a2fc3ef09006f0f16c7af3d5df18f`  
**ساخت:** `created_at=2026-10-25T20:00:00+00:00` (ثابت، برای بازتولید بایت‌به‌بایت)  
**وضعیت بازتولید:** **یکسان** — دو اجرای مستقل با همان ورودی، همان sha256 را دادند.

## فرمان بازتولید

```bash
python tools/ra365_round32b_reproduce_v3.py   --out D:/BorsTerminal-tmp/ra365_round32b_v3/repro-check   --expect-hashes data/ra365_corrections/ra365-r32b-v3/build-hashes.json
```

این فرمان مرجع را hash-verify، ورودی‌های R29 را hash-verify، audit را در حالت full-overlay/pack-only اجرا، pack را با `mode=authoritative` می‌سازد و sha256 همهٔ فایل‌ها را با اجرای اول مقایسه می‌کند.

## شمارش‌ها

- factors: `replace_step` = ۶٬۶۳۱، `suppress_step` = ۱۳۹، دارایی‌ها = ۸۲۷، ردیف‌ها = ۶٬۷۷۰.
- raw_ohlc: ۵٬۴۸۳ فیلد؛ توزیع فیلد در manifest v3.
- v2 برای مقایسه: `ra365-r32b-v2` با ۶٬۶۳۱ replace و ۱۳۹ suppress. محتوای core ردیف‌های v3 همان v2 است؛ `price_basis`/`basis_detail` افزوده شده‌اند.

## price_basis — کدام ردیف با کدام مبنا

| kind | same_basis | reference_close_matches_other_price_basis | unknown_basis |
|---|---:|---:|---:|
| factors | ۱٬۶۲۶ | ۵٬۱۴۴ | ۰ |
| raw_ohlc | ۴٬۳۲۷ | ۱٬۱۵۶ | ۰ |

- `same_basis`: close و last محصول در تاریخ مؤثر یکسان‌اند؛ نسبت close مرجع روی همان مبنای نمایش است.
- `reference_close_matches_other_price_basis`: close و last در تاریخ مؤثر تفاوت دارند؛ نسبت close مرجع به مبنای دیگر محصول می‌خورد؛ این ردیف‌ها جدا شده‌اند.
- `unknown_basis`: کندل محصول در تاریخ مؤثر نیست یا close/last موجود نیست.
- فایل‌های جدا: `factors.same_basis.jsonl`، `factors.reference_close_matches_other_price_basis.jsonl`، `raw_ohlc.same_basis.jsonl`، `raw_ohlc.reference_close_matches_other_price_basis.jsonl` (و unknown در صورت وجود). `basis-summary.json` شمارش و تعریف‌ها را دارد.

## سه کلید reference-internal هفتگی

هفتهٔ `2017-12-30`..`2018-01-03` برای دارایی‌های 8/803/804؛ CSV: `reference-internal-live.csv`.

| asset | symbol | field(s) W↔D | ref W open | live status |
|---|---|---|---:|---|
| 8 | شپارس | open,high | ۶۹٫۴۱۹۵ | NOT_RUN_LOGIN_REQUIRED |
| 803 | تداوم | open,low | ۳۲۵۹٫۵۷۱۲ | NOT_RUN_LOGIN_REQUIRED |
| 804 | اعتماد | low | ۱۸٬۶۴۰ | NOT_RUN_LOGIN_REQUIRED |

- تناقض داخلی مرجع (W در برابر تجمیع type7 D خودش) با دادهٔ منجمد تأیید شد: 8 (`open`,`high`), 803 (`open`,`low`), 804 (`low`).
- **live capture انجام نشد**: connector با token_status=۴۰۱ و پنل ورود، Brave با مودال ورود، Edge CDP/پروفایل probe موجود نبود. هیچ رمز/کوکی/توکنی خوانده، چاپ یا ذخیره نشد. وضعیت در CSV `NOT_RUN_LOGIN_REQUIRED` است و مقدار live ساخته نشد.
- برای تکمیل live پس از لاگین مالک: `tools/ra365_round32b_week2504_capture.js` را در تب لاگین‌شدهٔ Rahavard اجرا کنید و سپس `tools/ra365_round32b_week2504_live.py --live <json>` را اجرا کنید. خروجی، مقدار live و مقایسه با ref W/D را به همان CSV اضافه می‌کند.

## sha256 فایل‌های v3 (اجرای A / B)

| file | run A | run B |
|---|---|---|
| `basis-summary.json` | `8194dc257c31f411` | `8194dc257c31f411` |
| `factors.jsonl` | `811b7e4e6c2ba569` | `811b7e4e6c2ba569` |
| `factors.reference_close_matches_other_price_basis.jsonl` | `5a354df2fb468206` | `5a354df2fb468206` |
| `factors.same_basis.jsonl` | `971b3e2422f5b883` | `971b3e2422f5b883` |
| `factors.unknown_basis.jsonl` | `e3b0c44298fc1c14` | `e3b0c44298fc1c14` |
| `manifest.json` | `5d34a15d2966e5c3` | `5d34a15d2966e5c3` |
| `raw_ohlc.jsonl` | `600b00b8f656c712` | `600b00b8f656c712` |
| `raw_ohlc.reference_close_matches_other_price_basis.jsonl` | `31aa173ccfef5391` | `31aa173ccfef5391` |
| `raw_ohlc.same_basis.jsonl` | `43b3b62459c82d1e` | `43b3b62459c82d1e` |
| `raw_ohlc.unknown_basis.jsonl` | `e3b0c44298fc1c14` | `e3b0c44298fc1c14` |

## مسیرها و محدودیت‌ها

- خروجی روی D: `D:/BorsTerminal-tmp/ra365_round32b_v3/`؛ بستهٔ commitشده: `data/ra365_corrections/ra365-r32b-v3/`.
- فایل خام مرجع (`ref_bars_v2.jsonl`) و payloadهای محصول در Git نیستند؛ فقط hash/manifest و بستهٔ مشتق‌شده commit می‌شود.
- دیتابیس عملیاتی/WAL خوانده یا بازنویسی نشد؛ هیچ commit به `main` زده نشد.
- v3 با هم‌اکنون opt-in است: `BORS_CORRECTIONS_DIR=<repo>/data/ra365_corrections/ra365-r32b-v3`؛ مسیر پیش‌فرض v2 برای جلوگیری از تغییر مسیر بحرانی دست‌نخورده ماند.
