# شواهدِ تطبیقِ تبِ «وضعیت بازار» — Qoder 3 (۲۰۲۶-۱۰-۲۰)

همهٔ فایل‌ها snapshotِ زمان‌دار یا خروجیِ اجرایِ واقعی‌اند. هیچ دادهٔ حساب، کوکی،
توکن، پروفایل یا هویتِ نشست در این پوشه نیست. فایل‌های `*.json` بزرگ‌تر از حدِ
متعارف (`bors-board-...`) فقط projectionِ فیلدهای لازم‌اند، نه dumpِ کامل.

## snapshotهای اصلی

| فایل | زمان | معنا |
|---|---|---|
| `snapshot-20261020-145936.json` | ۱۴:۵۹:۳۶ | قبل از اصلاح `p_last` |
| `snapshot-20261020-151546.json` | ۱۵:۱۵:۴۶ | بعد از اصلاح `p_last` |
| `snapshot-20261020-152056.json` | ۱۵:۲۰:۵۶ | بعد از اصلاح صفر/گمشده؛ `total_field_diffs=0` |

## round-1-firefox

`asset-453.json` — مقادیرِ صفحهٔ نمادِ فولاد در Rahavard365 از پنجرهٔ Firefox،
با روشِ UI/کپیِ متن؛ بدون CDP/Marionette و بدون استخراجِ نشست. عمقِ ۱۴:۱۹:۳۳
«آخرین نشست» است، نه عمقِ جاری.

## round-2

پاسخ‌های API در لحظهٔ خواندن: `api-mstat_indexcards.json`،
`api-mstat_clientsplit.json`، `api-mstat_phase.json`. فایلِ خامِ `/api/market`
به‌دلیلِ حجم حذف شد؛ projectionِ آن در round-4 است.

## round-4

| فایل | معنا |
|---|---|
| `bors-board-20261020-sync151951.json` | ۶۱۴۲ ردیفِ Bors، sync ۱۵:۱۹:۵۱ |
| `tsetmc-postclose.json` | ۳۲۸۷ ردیفِ TSETMC، fetch ۱۷:۱۳:۳۶ |
| `universe-summary.json` | شمارشِ وضعیت‌ها (۳۲۸۱ هم‌نیاز، ۲۲ زندهٔ اضافی، ۶ کهنه، ۲۸۳۳ تاریخی) |
| `postclose-field-parity.json` | ۰ اختلاف در ۱۱ فیلد روی ۳۰۹۳ ردیفِ same-tick |

`universe-summary.json` و `postclose-field-parity.json` با اسکریپت‌های
`dev/market_universe_closure_v1.py` و `dev/market_postclose_parity_v1.py`
بدون شبکه بازتولید می‌شوند.

## round-7

اسکرین‌شات‌های ۱۳۶۶×۷۶۸ و ۱۶۰۰×۹۰۰ از «وضعیت بازار» و «تابلو» + probeهای
`ui-probe.json` / `ui-board-probe.json` (overflow، خطای کنسول، برچسب‌ها).
این‌ها UIِ محلی با دادهٔ DBِ ایزوله‌اند، نه نشستِ Rahavard.

## round-8

`vitest-full.log` (کلِ Frontend) و `backend-gate.log` (`dev/run_all_tests.py`).
لاگِ backend با `PYTHONIOENCODING=utf-8` اجرا شده؛ اجرای بدون آن روی cp1252
شکستِ محیطی داشت، نه شکستِ تست.

## تفکیکِ live و mock

- **live:** snapshotهای TSETMC/Bors، asset 453، پاسخ‌های APIِ سرورِ محلی روی DBِ ایزوله.
- **mock/pure:** `dev/market_last_trade_semantics_v1.py`،
  `dev/mstat_industry_depth_semantics_v1.py` (monkeypatch) و تست‌های Vitest.
- **صفر/`None`:** هیچ صفرسازی یا مقدارِ جایگزینی برای بالا بردنِ درصد انجام نشده است.
