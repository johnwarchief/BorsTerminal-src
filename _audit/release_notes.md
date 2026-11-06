BorsTerminal v1.0.78 — Technical / FTS Fixes

### Technical
* اصلاح Daily Trend classification در هستۀ `_fts_classify_trend`
* بهبود رفتار الگوی V-Bottom (کف‌های V شکل فوراً صعودی تشخیص داده می‌شوند)
* محافظت از ساختار (جلوگیری از flip شدن Trend روزانه به `down/range` در اثر تشکیلِ یک LH کوچک مادامی که کف ماژور اصلی نشکسته باشد)

### FTS
* تأیید Weekly/Daily branching و سازگاری کامل با Owner Rulings (از جمله حفظ قاعده Jet/Pullback)
* حفظ canonical matrix decision به عنوان تنها مرجع تصمیم‌گیر (هیچ فیلتر مازادی در Frontend اعمال نمی‌شود)
* اصلاح regression مربوط به ارزیابی متغیرهای Tape smart-money (تطبیق با ریفکتور PRESET_ENTRY)

### Candle
* تأیید separation و معماری قراردادِ B2:
  * نمایش چارت (Display) → `LAST`
  * محاسبات پایه/تعدیلات/شکست مقاومت → `CLOSE`

### Validation
* تمام تست‌های `dev/run_all_tests.py` شامل FTS trend fixtures، Candle Fidelity، و Tape Smart Money مجدداً با موفقیت پاس شدند (بدون شکست/دور زدن).
* ارزیابی زنده روی ۲۰ نماد بازار (`_audit/validate_20.py`): به دلیل عدم اتصال به سرور آنلاین در محیط جاری `UNVERIFIED` رها شد، اما نتایج Local Validation کاملاً منطبق و دقیق ارزیابی شده است.

### Build
* frontend: موفقیت‌آمیز
* PyInstaller: موفقیت‌آمیز (بسته Onedir)
* Inno Setup: موفقیت‌آمیز

### Commit
* HEAD: `e23e240`

### Hash
SHA-256: `08FCC9C96FEB8A262DF647B8E783D904155E8BCB06457F4AEE761551707743D8`
