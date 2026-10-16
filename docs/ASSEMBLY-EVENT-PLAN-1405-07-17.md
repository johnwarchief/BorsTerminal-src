# AssemblyEvent — آنچه راستی‌آزمایی شد و کاری که مانده (۱۴۰۵-۰۷-۱۷)

این پروندۀ تحویل است، نه گزارشِ انجام‌شده. سه بندِ اول **سنجیده** شده‌اند (با خواندنِ
کد و فایلِ داده)؛ بند ۴ و ۵ **هنوز ساخته نشده‌اند**.

## ۱) زنجیرۀ واقعیِ مجمع (برخلافِ تصورِ «از صفر بساز»)

| حلقه | کجا | چیست |
| --- | --- | --- |
| واکشی | `dev/calendar_fetcher.py` | جستجوی Codal (`Category=6` مجامع + کلیدواژه‌ها) → ساختِ ردیفِ رویداد |
| کش | `static/calendar/cache.json` | ۱۹۰ ردیف؛ میدان‌ها: `date_time, event_time, event_title, description, event_type_id, report_id, link, asset_symbol_trade, asset_id` |
| خواندن | `api/chart.py:969 upcoming_assemblies()` | یک منبع، دو مصرف: `/api/calendar/upcoming` (برچسبِ سطر) و `_apply_assembly_veto` در `api/screener.py:164` |
| رابط | `frontend/src/features/fundamental/lib/assemblyEvent.ts` | مدلِ `CalEvent {date,title,cat}` + برچسبِ «مجمع نزدیک / تغییر مجمع» + برچسبِ «افزایش سرمایه» |

پس یک مدلِ رویداد **از قبل وجود دارد** و قاعدۀ «regex فقط برای طبقه‌بندی/کشف/برچسب»
درِ آن رعایت شده است (`classify_tid` درِ فچر، `CAPITAL_RE` درِ `api/chart.py:981`
و آینهٔ فرانتی‌اش درِ `assemblyEvent.ts:149`).

## ۲) دو نقصِ اثبات‌شده که رأیِ مالک (§۲۳ و §۲۴) مستقیماً منعشان می‌کند

**الف) تاریخِ انتشار جایِ تاریخِ مجمع می‌نشیند، بی‌هیچ علامتِ منشأ.**
`dev/calendar_fetcher.py:558-570`:

```python
iso, ev_time = extract_when(title, pub_iso)   # fallback: تاریخِ انتشار
...  "date_time": iso,                          # هیچ فیلدی نمی‌گوید این از کجاست
```

`extract_when` (`:535-551`) اگر عنوانِ اطلاعیه تاریخِ «مورخ …» نداشته باشد،
**خودِ `pub_iso` را برمی‌گرداند**. اطلاعیه‌هایی مثلِ «تصمیمات مجمع…» یا
«لغو آگهی دعوت به مجمع…» همین شکل‌اند — و `assemblyEvent.ts:124` همان عدد را با
متنِ «مجمع نزدیک — ۳ روز دیگر (…)» نشان می‌دهد و `api/screener.py` از همان برای
**وتوی سبد** استفاده می‌کند. این دقیقاً همان چیزی است که مالک منع کرد: *proxy نباید
به fact بدل شود*.

**ب) تاریخِ انتشار اصلاً حمل نمی‌شود.** `pub_iso` درِ فچر ساخته می‌شود
(`:542-551`) و درِ همان‌جا دور ریخته می‌شود؛ درِ `cache.json` هیچ فیلدِ انتشاری نیست
(اتّحادِ میدان‌های ۱۹۰ ردیف: `asset_id, asset_symbol_trade, date_time, description,
event_time, event_title, event_type_id, link, report_id`). پس برچسبِ
«تاریخ انتشار اطلاعیه» که مالک خواست، **فعلاً قابلِ ساخت نیست** — داده‌اش هست، ولی
درِ لایهٔ ذخیره گم می‌شود.

## ۳) DPS و decision_date: امروز چه وضعیتی دارد

- **DPS:** هیچ‌جایِ زنجیره (نه Codal، نه TSETMC، نه `cache.json`) عددی به نامِ DPS
  نمی‌نشیند ⇒ مطابقِ رأیِ مالک باید **صریحاً `UNAVAILABLE` اعلام شود**، نه اینکه
  سکوت meaning‌دار تلقی شود. (parse کردن DPS از PDF attachmentها **ممنوع** است.)
- **decision_date:** منبعِ ساختاریافته‌ای برای «تاریخِ تصمیمِ مجمع» وجود ندارد —
  آنچه هست *تاریخِ رویدادِ تقویم* است. باید `null` بماند.
- کامنتِ گمراه‌کننده درِ `codal_fetcher.py:3587-3589` می‌گوید «board-assignment /
  assembly notices are **stored as notices** but never deep-extracted». این با
  خودِ فایل در تضاد است: `SAVE_USEFUL_ONLY = True` درِ `codal_fetcher.py:76-79`
  دسته‌های «مجمع»، «توقف/بازگشایی»، «تغییر مدیران»، «پورتفوی صندوق» را **از ذخیره
  درِ `codal_notices` بیرون می‌اندازد** — پس اطلاعیهٔ مجمع «ذخیره» نمی‌شود که
  «deep-extract» نشود. (درِ این کارتر `codal.db` نیست، پس شمارِ ردیفِ مجمع
  راستی‌آزمایی نشد؛ ادّعایِ این بند فقط بر پایۀ همان دو بلوکِ کد است.)

## ۴) کاری که مانده (به همین ترتیب)

1. **فچر:** `published_at` را درِ ردیفِ رویداد بگذار و منشأِ تاریخِ رویداد را علامت
   بزن: `date_source: "title" | "publication_fallback"`. بی‌علامت، هیچ مصرف‌کننده‌ای
   نمی‌تواند صادق باشد.
2. **بک‌اند:** `api/chart.py:_upcoming_by`/`upcoming_assemblies` و
   `api/screener.py:_apply_assembly_veto` فقط رویِ `date_source == "title"` وتو
   کنند؛ ردیفِ `publication_fallback` ⇒ برچسبِ «اطلاعیه»، نه «مجمعِ پیش‌رو».
3. **مدلِ canonical:** `AssemblyEvent` با میدان‌های
   `symbol, tracing_no(=report_id), category, meeting_date, meeting_date_source,
   published_at, decision_date=null, dps=null ("UNAVAILABLE"), title, source,
   fetched_at`. فرانت (`assemblyEvent.ts`) همین را بخواند، نه `date`ِ تنها.
4. **رابط:** «روز مجمع» و «تاریخ انتشار اطلاعیه» دو labelِ جدا؛ برایِ اطلاعیهٔ
   بی‌تاریخِ مجمع، هیچ «X روز دیگر»ی ساخته نشود.
5. **گاردها:** درِ `dev/test_calendar_v92.py` (که پیش‌تر بینِ `assemblyEvent.ts` و
   پیش‌فرضِ `/api/calendar/upcoming` هم‌خوانی می‌گیرد) + یک بندِ تازه:
   «bi‌date_source، وتو روشن نمی‌شود» و «هیچ ردیفی decision_date/DPS جعلی ندارد».
6. **کامنتِ `codal_fetcher.py:3587-3589`** با متنِ دقیقِ رفتارِ `SAVE_USEFUL_ONLY`
   عوض شود. رفتارِ ذخیره‌سازی را بی‌دلیل بزرگ نکن: reingestionِ تاریخی **درِ این
   milestone نکن** (رأیِ مالک §۲۶) و DB را بی‌فایده سنگین نکن.

## ۵) بندِ بازِ دیگری که درِ همین کارتر زمین مانده

- **Sidebar «در یک نگاه»:** رأیِ مالک Quick Scan را به‌عنوان قابلیتِ مستقل حذف کرد؛
  رفتارش «کلیکِ نماد ⇒ داوریِ کاملِ هدفمند ⇒ سایدبار». درِ این کارتر هیچ Quick Scanِ
  مستقلی ساخته نشده بود (جستجو برای `quickScan|پویشِ سریع` ⇒ صفر)، پس چیزی برای حذف
  نیست؛ کاری که مانده خودِ سطرِ «در یک نگاه» است. `stageProgressFor` از قبل حالتِ
  `not_in_universe` را هم می‌دهد.
- **Android parity:** واژگانِ «غربالگری»، ستارۀ واچ‌لیست، و شمارشِ تکمیلِ جامعۀ
  غربالگری درِ `BorsTerminal-android` (کارترِ جدا؛ `scripts/build_mobile_snapshot.py`
  و `shared/api/local/`).

## ۶) فرمانِ شروعِ session بعد

> در `C:\Users\PCMOD\Desktop\BorsTerminal-roadmap` (branch `funnel-api-wip`) ادامه بده.
> پروندۀ `docs/ASSEMBLY-EVENT-PLAN-1405-07-17.md` را کامل بخوان و از بند ۴ شروع کن؛
> بند ۱ و ۲ بدونِ هم تغییر نکنند (علامتِ منشأ پیش از مصرف‌کننده معنا ندارد).
> بک‌اندِ dev را روی ۸۰۰۱ بالا بیاور (`python -m uvicorn app:app --port 8001`) و
> `npx vite --port 5173` — همین روش درِ این session کار کرد؛ `market.db` این کارتر
> هست. هیچ عددِ روندِ دست‌سازی درِ گزارش‌ها نکن؛ گاردِ `dev/funnel_engine_v1.py`
> (۴۲ بند) و `dev/user_watchlist_v1.py` (۱۳ بند) و `dev/persian_glyph_guard.py` باید
> سبز بمانند. Release نساز تا milestone ACCEPTED شود.
