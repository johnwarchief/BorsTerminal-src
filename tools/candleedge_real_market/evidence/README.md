# شواهد اعتبارسنجی CandleEdge — دور ۲

این پوشه خروجی اجرای واقعی ۲۰ آشکارساز CandleEdge روی دادهٔ BorsTerminal است.
هیچ فایلی در این پوشه سیگنال رسمی یا توصیهٔ معاملاتی نیست.

**شاخه:** `mission/technical-candleedge-real-market-validation-2026-10-25`
**مبنا:** `4a597278f4bf74c29430d2faa2f4ea01de7e37cc`
**گزارش:** `docs/technical-indicators/reviewed/CANDLEEDGE-REAL-MARKET-VALIDATION-2026-10-25.md`

## فایل‌ها

| فایل | چیست |
|---|---|
| `stats.json` | آمار کامل آشکارساز/تایم‌فریم/نقدشوندگی/سال/سالینس/ارزیابی آینده‌نگر |
| `ledger.ndjson.gz` | دفتر کامل رویدادها؛ هر خط: نماد، تایم‌فریم، حالت، آشکارساز، جهت، ایندکس تأیید، سطح، لنگرها |
| `salience-groups.ndjson.gz` | جدول ۱۱۹٬۹۳۷ گروه سالینس با رتبهٔ سه روش نمایش |
| `series.ndjson.gz` | خلاصهٔ هر سری: تعداد کندل، تعداد رویداد، خطا، وضعیت هش |
| `record-manifest.ndjson.gz` | هش ورودی و وضعیت هر رکورد گردآوری |
| `ledger-validation.json` | نتیجهٔ اعتبارسنجی مستقل زمان/لنگر/سطح |
| `salience-validation.json` | تطابق مجموع گروه‌ها/رویدادها با دفتر و نبود گروه بیش از پنجره |
| `margins.json` | توزیع عبور BOS و نفوذ Sweep |
| `captures/` | تصاویر و نتیجهٔ ۲۱ بررسی خودکار نمایشگر |

فایل ورودی خام (`real_market.ndjson`، حدود ۵۰ مگابایت) در Git نیست؛
SHA-256 آن `90901ef87914c87be7213090f7ffc94622e941ea5fe101718793ed928d63c433` است
و با `collect_real_market.py` از یک کپی پایگاه داده بازتولید می‌شود.

## بازتولید

```bash
# 1) اعتبارسنجی دفتر (ledger.ndjson.gz و series.ndjson.gz همین‌جا)
node tools/candleedge_real_market/validate_ledger.cjs --dir=tools/candleedge_real_market/evidence

# 2) حساسیت مرزی (از frontend/)
CANDLEEDGE_NDJSON=<path>/real_market.ndjson \
  ./node_modules/.bin/vite-node ../tools/candleedge_real_market/validate_margins.ts

# 3) بازسازی جدول سالینس (از frontend/)
./node_modules/.bin/vite-node ../tools/candleedge_real_market/build_salience_table.ts

# 4) نمایشگر
cd tools/candleedge_real_market/viewer
python -m http.server 8137
# http://127.0.0.1:8137/
```

## محدودیت‌ها

- ماهانه برای ساختار/سوئیپ/دوقلو `INSUFFICIENT_HISTORY` است.
- فقط ۲۵۶ نماد از ۷۷۲ نماد زنجیرهٔ تعدیل ترکیبی کامل دارند.
- ارزیابی آینده‌نگر بدون هزینه/صف/نقدشوندگی و در یک رژیم صعودی است؛ بک‌تست سوددهی نیست.
- مقایسه با رهاورد `NOT_MEASURED` است.
