# تب تقویم بازار — BorsTerminal Calendar Module

ماژول مستقل تقویم رویدادهای بازار سرمایه (مهندسی‌معکوس‌شده از `rahavard365.com/calendar`). هسته پروژه دست نخورده — تنها اتصال‌ها: یک دکمه ناوبری + یک `<section id="calView">` + ۳ تگ include در `index.html`.

## فایل‌ها
| فایل | نقش |
|---|---|
| `calendarService.js` | لایه دیتا: واکشی → نرمال‌سازی → کش (memory + localStorage با TTL ۶ ساعت) → فیلتر/کوئری |
| `calendar.js` | UI: تقویم جلالی ماهانه/هفتگی، فیلترها، پاپ‌آور جزئیات (`calTabOpen` نقطه ورود) |
| `calendar.css` | استایل هم‌راستا با تم دارک/لایت پروژه (`--bg-card`, `--border-color`, `data-chart-theme`) |
| `cache.json` | کش استاتیک رویدادها — خروجی فچر (همین فایل توسط فرانت خوانده می‌شود) |
| `../../dev/calendar_fetcher.py` | اسکریپت واکشی دوره‌ای (cron/Task Scheduler) |

## منبع داده (v2 — کدال، رایگان)
```
GET https://search.codal.ir/api/search/v2/q?PageNumber=1&PageSize=20&search=true
    &Category=6&FromDate=1405/06/01&ToDate=1405/06/31        → مجامع (دعوت/تصمیمات)
GET .../q?...&Subject=پرداخت سود&FromDate=...&ToDate=...      → سود نقدی
GET .../q?...&Subject=افزایش سرمایه / عرضه اولیه / سررسید      → بقیه دسته‌ها
```
- بدون احراز هویت — پاسخ: `{"Total": N, "Page": p, "Letters": [{TracingNo, Symbol, CompanyName, Title, PublishDateTime(jalali, ارقام فارسی), ...}]}`
- **PageSize سمت کدال حداکثر ۲۰** → فچر صفحه‌بندی می‌کند (`--max-pages`، پیشفرض ۱۵ صفحه × ۲۰ = ۳۰۰ نامه در هر کوئری کلان)
- فقط **۵ کوئری کلان در ماه** (کم‌ترافیک) + تاخیر تصادفی ۱-۲ ثانیه + هدر UA مرورگر
- 429/WAF → **Exponential Backoff** (2/4/8/16s)؛ با `--adb-rotate` بعد از دو بک‌آف ناموفق (یا هر ۱۰ رکوئست) حالت پرواز via adb روشن/خاموش می‌شود (تغییر IP سیم‌کارت)
- نگاشت به فرمت فرانت: `event_type_id`: مجامع از عنوان (فوق‌العاده→2، عادی→1)، سود→3، بقیه→0 (فرانت با کلیدواژه دسته‌بندی می‌کند)

## ساختار خام Letters (کدال)
```json
{"TracingNo": 1594880, "Symbol": "شیران", "CompanyName": "...", "Title": "...",
 "PublishDateTime": "۱۴۰۵/۰۶/۰۷ ۱۴:۳۸:۵۴", "SentDateTime": "...", "PdfUrl": "...", "HasAttachment": true}
```

## واکشی دوره‌ای
```bat
:: هر ۶ ساعت (Windows Task Scheduler):
schtasks /Create /SC HOURLY /MO 6 /TN "BorsCalendarFetch" ^
  /TR "C:\path\BorsTerminal_TechV2\run_calendar_fetch.bat"
```
```bash
# cron:
0 */6 * * * cd /path/BorsTerminal_TechV2 && venv/Scripts/python dev/calendar_fetcher.py
```
اجرای دستی:
```bash
venv/Scripts/python.exe dev/calendar_fetcher.py                       # امروز تا +۱۹۰ روز
venv/Scripts/python.exe dev/calendar_fetcher.py --from 2026-08-20 --to 2027-03-20 --db market.db
```

## ساختار کش (`cache.json`)
```json
{
  "meta": { "source": "...", "fetchedAt": "...", "from": "...", "to": "...", "count": 524, "industries": {} },
  "token": "<access_token آخرین واکشی>",
  "events": [ { ...همان ساختار خام بالا... } ]
}
```
- `meta.industries`: نقشه اختیاری `نماد → صنعت` برای فیلتر صنعت (در صورت تزریق، UI خودکار پر می‌شود).
- `token`: برای «به‌روزرسانی زنده» سمت کلاینت در صورت افزودن پروکسی داخلی (`/api/calendar/events`).

## دیتابیس لوکال (اختیاری — `--db market.db`)
```sql
CREATE TABLE calendar_events (
  report_id TEXT PRIMARY KEY, asset_id TEXT, symbol TEXT,
  event_type_id INTEGER, category TEXT, event_time TEXT,
  title TEXT, description TEXT, fetched_at TEXT);
```

## مدل دیتای نرمال‌شده سمت فرانت (خروجی CalService.query)
```js
{ id: "r717970", typeId: 2, cat: "assemblyExtra",
  title: "آگهی دعوت به مجمع عمومی فوق العاده (نوبت دوم)",
  desc: "...", symbol: "وسقزوین", symbolId: "15702",
  ms: 1789452600000, date: "2026-09-26", time: "10:00", reportId: "717970" }
```
`cat` ∈ `assembly | assemblyExtra | dividend | capitalIncrease | ipo | bondMaturity | other`

## استفاده
تب «📅 تقویم» در سایدبار → نمای ماه/هفته جلالی، ناوبری ماه، فیلتر نوع/نماد/صنعت/متن، کلیک روی رویداد = جزئیات کامل.

## نکته نسخه v2
فچر v2 از **کدال** (رایگان، بدون احراز) استفاده می‌کند؛ نسخه قبلی (رهاورد) به session-cookie نیاز داشت و حذف شد.
دستورات: `--jmonth 1405/06 --months 3 --db market.db --adb-rotate --max-pages 15`
