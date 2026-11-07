# RA365 Round 18 — Raw OHLC Parity & Causal Attribution

**تاریخ:** 2026-10-22  
**شاخه:** `mission/ra365-round18-raw-ohlc-parity-2026-10-22`  
**مبنای Round 17:** `c35b6eb7`  
**Commit کد این راند:** `531aa2b1 + 596d1523`  
**دیتابیس عملیاتی:** SHA `7b933b05d03b8a2f9383f901faf6b2c34f1500e70619d6cc5c8039f171b1848c` (mtime: 2026-10-15 03:31)

---

## ۰. خلاصهٔ اجرایی

این راند پیش از هر اصلاح تعدیل، سه لایه را از هم جدا کرد: **Raw OHLC**، **Factor** و **Adjusted OHLC**. نتیجهٔ اصلی این است که دادهٔ خام مسیر زنده تقریباً سالم است و اختلاف تعدیل‌شدهٔ Round 17 عمدتاً از لایهٔ Factor می‌آید، نه از دریافت/نگاشت/پارس دادهٔ خام.

| موضوع | نتایج اندازه‌گیری‌شده | وضعیت |
|---|---|---|
| قرارداد Raw با payload واقعی TSETMC | CSV و JSON در ۱۰٬۵۳۹ ردیف مشترک، ۱۰۰٪ یکسان | `VERIFIED` |
| تطبیق فیلدهای قراردادی Raw | ۱۴٬۸۷۰٬۸۷۲ فیلد مقایسه‌شده، ۹۹٫۹۸۲۴٪ exact | `VERIFIED` |
| تطبیق ردیفی Raw | ۲٬۱۲۴٬۲۵۱ از ۲٬۱۲۴٬۹۳۶ ردیف، ۹۹٫۹۶۷۸٪ | `VERIFIED` |
| مسیر زنده (basis=last) | ۹۹٫۹۷۵۵٪ تطبیق ردیفی | `VERIFIED` |
| مسیر fallback (basis=closing) | ۹۶٫۰۴۴۱٪ تطبیق ردیفی (قبل از اصلاح) | `VERIFIED` |
| علت غالب اختلاف خام | واگرایی/عقب‌ماندگی منبع: ۸۲۰ ردیف؛ fallback محلی: ۲۲۰ ردیف | `VERIFIED` |
| خطای پارس/نگاشت/تاریخ/مقیاس در Raw | صفر ردیف قراردادی باقی‌مانده | `VERIFIED` |
| Factor exact (R17 promoted) | ۶۹٫۰۲۴۳٪ | `VERIFIED` |
| Adjusted OHLC (R17 promoted) | ۶۸٫۳۰۴۵٪ | `VERIFIED` |
| رگرسیون‌های R17 که Raw آن‌ها سالم است | ۶۸ از ۸۵ ردیف | `VERIFIED` |
| اصلاح عمومی fallback | fallback display از ۹۵٫۱۳۰۱٪ به ۹۹٫۹۳۸۴٪ | `IMPLEMENTED_AND_TESTED` (روی کپی) |
| انتشار به دیتابیس عملیاتی | انجام نشد؛ نسخهٔ آماده روی کپی | `BLOCKED` (پیش‌شرط عملیاتی) |
| دیتابیس عملیاتی | SHA پیش/پس یکسان؛ بدون نوشتن | `VERIFIED` |
| Full gate | ALL SUITES PASSED — 145 سوئیت، 44 silent، 2 skip، failure: 0 | `VERIFIED` |

**نتیجهٔ تشخیصی:** اگر Raw سالم باشد ولی Factor فرق کند، مسئله در رویدادها/الگوریتم تعدیل است. اندازه‌گیری نشان می‌دهد Raw مسیر زنده ۹۹٫۹۷۵۵٪ و Factor ۶۹٫۰۲۴۳٪ است؛ بنابراین شکاف اصلی Adjusted OHLC **Factor** است، نه دادهٔ خام. تنها بخش قابل‌اصلاح در Raw، مسیر fallback محلی بود که با یک اصلاح عمومی و ایدمپوتنت به ۹۹٫۹۳۸۴٪ رسید.

---

## ۱. Git، مبنا و وضعیت دیتابیس

- Worktree مستقل: `.worktrees/ra365-round18`، شاخهٔ `mission/ra365-round18-raw-ohlc-parity-2026-10-22`، ساخته‌شده از `c35b6eb7` (HEAD پایانی Round 17).
- `main` تغییر نکرد؛ هیچ push/merge انجام نشد.
- Working tree شروع پاک بود؛ artifacts این راند در `artifacts/ra365/r18/` ساخته شد.
- اعداد گزارش Round 17 از artifact واقعی بازمحاسبه شد: مجموع `parity-symbols-promoted-final.csv` دقیقاً
  ۱٬۱۸۷٬۹۴۵ تاریخ Factor، ۸۱۹٬۹۷۱ exact، ۱٬۰۴۶٬۳۶۹ near، ۴٬۷۵۱٬۷۸۰ فیلد OHLC، ۳٬۲۴۵٬۶۷۸ ok، و ۲٬۵۹۵ دارایی. این با `۶۹٫۰۲۴۳ / ۸۸٫۰۸۲۳ / ۶۸٫۳۰۴۵` گزارش R17 می‌خواند.

**نکتهٔ مهم دربارهٔ SHA عملیاتی:** گزارش Round 17 مقدار `fff358a78be74e8d21961251a727116e102df84cea70f87b4dcb7da198667004` را ثبت کرده بود. این مقدار امروز از هیچ‌یک از کاندیدهای دیتابیس (دیتابیس سورس، worktree Round 15، یا کپی promoted) بازتولید نشد. SHA واقعی دیتابیس سورس در شروع و پایان این راند `7b933b05d03b8a2f9383f901faf6b2c34f1500e70619d6cc5c8039f171b1848c` است؛ mtime فایل اصلی 2026-10-15 03:31 و `market.db-wal` صفر بایت است. فایل `market.db` داخل worktree یک fixture تست است و با دیتابیس عملیاتی یکی نیست؛ SHA گزارش قبلی (`17e93…`) به همان fixture اشاره داشت و اکنون تصحیح شده است. این راند **هیچ نوشتنی** روی آن انجام نداد. اختلاف SHA گزارش R17 به‌عنوان یک ناسازگاری مستند ثبت می‌شود، نه به‌عنوان تغییر این راند.

**دیتابیس‌های اندازه‌گیری:** کپی promoted با SHA `8fb85f381317634430cae429bd9775eba0a364b692e0868b4d9b17dbbcc6c17f` فقط‌خواندنی استفاده شد؛ کپی repaired با SHA `8644d30bfb3c493c5f6c9fad1b857c9277d9a05306f79a712d576bcedf8f6164` فقط برای سنجش اصلاح fallback ساخته شد. هیچ migration عملیاتی انجام نشد.

---

## ۲. تعریف لایه‌ها و معیارها

### لایه‌ها
- **A — BorsTerminal Raw:** کندل‌های خام خروجی pipeline، پیش از هر ضریب. `open` از `<FIRST>` (یا fallback مستند)، `high/low` از `widen()`، `close` انتخاب‌شده با basis، `closing` پایانی رسمی، `last` آخرین معامله، `volume` از `<VOL>`.
- **B — TSETMC Raw Reference:** payload روزانهٔ TSETMC با فیلدهای `<FIRST>`, `<HIGH>`, `<LOW>`, `<CLOSE>`, `<LAST>`, `<OPEN>` (پایه), `<VOL>`؛ مسیر CSV و مسیر JSON و در نمونه‌ای webgw.
- **C — Rahavard type0:** فقط به‌عنوان مرجع مستقل/کنترلی؛ معنای آن با داده سنجیده شد، نه از نام آن فرض شد. `type7` فقط در لایهٔ Adjusted استفاده شد.

### معیارها
- **exact:** برابری عددی؛ **tolerance:** اختلاف ≤ ۰٫۵ ریال؛ **rounding:** اختلاف نسبی ≤ ۰٫۰۵٪ (جدا از exact گزارش می‌شود).
- **row exact:** هر چهار فیلد OHLC قراردادی exact. **full-contract row:** شامل OHLC + last + display close + volume.
- **missing bar** هرگز اختلاف عددی محسوب نشد؛ **no-trade** و **coverage range** جدا ثبت شدند.
- هیچ مقدار missing با صفر، کندل قبلی یا مقدار ساختگی پر نشد.
- کلید ابزار `ins_code` است، نه نماد؛ ۶۳۰ دارایی در manifest بیش از یک `ins_code` دارد و این موضوع در تفسیر fallback/نسخه‌ها لحاظ شد.

---

## ۳. تحقیق بیرونی و قرارداد واقعی داده‌ها

ماتریس کامل: `artifacts/ra365/r18/source-field-matrix.csv` (۲۵ ردیف). منابع بررسی‌شده و سطح اطمینان:

| منبع | یافتهٔ کلیدی | اطمینان |
|---|---|---|
| TSETMC CDN `ClosingPrice/GetClosingPriceDailyListCSV/{insCode}/19900101` | `<FIRST>` اولین معامله، `<CLOSE>` پایانی رسمی، `<LAST>` آخرین معامله، `<OPEN>` قیمت پایه (نه open معاملاتی)، `<VOL>` حجم | `HIGH` (payload زنده + JSON) |
| TSETMC CDN `ClosingPrice/GetClosingPriceDailyList/{insCode}/{top}` | `priceFirst/pClosing/pDrCotVal/priceYesterday` همان معانی CSV؛ `top` سقف دارد و `top=0` کل تاریخچه | `HIGH` |
| TSE webgw `History/Archive/fa?InstrumentId={ISIN}` | مسیر مستقل رسمی با `firstPrice/highvalue/lowvalue/lastprice/closingprice/yesterdayPrice/tradevolume`؛ نمونهٔ ۳٬۲۷۶ ردیف | `HIGH` برای فیلد، `MEDIUM` برای پوشش |
| `GetPriceAdjustList/{insCode}` | `pClosing` و `pClosingNotAdjusted` دو طرف نسبت تعدیل؛ لیست کامل نیست (طبق مرجع، ۵۲٫۳٪ رویدادها در پنجرهٔ ۷ روزه پوشش داده نشد) | `HIGH` برای معنا، `MEDIUM` برای کامل‌بودن |
| `GetInstrumentShareChange/{insCode}` | `numberOfShareOld/New` و `dEven`؛ برای ETF/آپشن ممکن است خالی باشد | `HIGH` برای schema |
| `GetInstrumentCalendar/{insCode}` | مسیر `ClosingPrice/...` پاسخ ۲۰۰ می‌دهد ولی فقط `pClosing` و حجم دارد؛ OHLC ندارد؛ مسیر `Instrument/...` در probe ۴۰۴ بود | `HIGH` برای محدودیت |
| Rahavard type0 (D) | close با product last در ۹۹٫۹۵۵٪ روز یکسان است، با closing رسمی فقط ۱۴٫۰۹۰٪؛ ۱۹۰٬۲۸۷ کندل تخت (O=H=L=C) | `HIGH` برای close=last، `MEDIUM` برای OHLC |
| Instrument versioning | InsCodeهای جدید با پسوند ۲/۳/۴ در تغییر سرمایه ساخته می‌شوند؛ هر دو معتبرند و باید با suffix/dedupe مدیریت شوند | `HIGH` |
| CODAL | منبع رسمی رویدادهای شرکتی است، نه OHLC روزانه | `HIGH` برای رویداد، `N/A` برای OHLC |

**منابع بررسی‌شده:** [tsetmc-skill](https://github.com/amirziveh/tsetmc-skill) (فرهنگ فیلد، نسخه‌بندی InsCode، ناقص‌بودن GetPriceAdjustList)، [tse-market-data](https://github.com/BabakEslami/tse-market-data) (ENDPOINTS.md و `top=0`/History Archive)، [exref urls](https://github.com/m-ahmadi/exref/blob/master/tse/urls.txt)، [fis-agent tsetmc-api](https://github.com/mazaheriMahdi/fis-agent/blob/main/docs/domain/tsetmc-api.md)، [tsetmc-mcp endpoints](https://github.com/solitraderbusiness/tsetmc-mcp/blob/main/docs/endpoints.md) و [CODAL](https://codal.ir/). تاریخچهٔ مخازن بررسی شد: tsetmc-skill در v1.2.0 workflowهای تعدیل را اضافه کرد و tse-market-data چند بار ENDPOINTS.md را حذف/بازنویسی کرد؛ بنابراین نسخه/تاریخ شاهد در ماتریس ثبت شده است.

**شواهد کلیدی قرارداد:** CSV و JSON در ۱۰٬۵۳۹ ردیف مشترک برای هفت فیلد ۱۰۰٪ یکسان بودند؛ `.../0` و `.../19900101` برای یک نماد ۳٬۶۹۵ ردیف با ارزش یکسان برگرداندند. webgw در ۳٬۲۷۶ ردیف مشترک، first/base را ۱۰۰٪ و high/low/close/volume/last را با چند اختلاف لبه‌ای (۱ تا ۷ ردیف) مطابق داشت. منابع TSETMC غیررسمی و مستندنشده‌اند؛ این محدودیت در ماتریس ثبت شده است.

**هشدار مهم دربارهٔ type0:** نوع `type0` یک آینهٔ بایت‌به‌بایت TSETMC نیست. close آن به‌طور تجربی آخرین معامله است، ولی high/low در ۱۹۰٬۲۸۷ کندل تخت شده‌اند (۱۵٫۹۶٪ از تاریخ‌های مشترک). بنابراین type0 برای کنترل close مفید است، برای OHLC مرجع کامل نیست. این همان دلیلی است که «تطبیق خام حدود ۹۷٪» گزارش‌های قبلی را نمی‌توان به‌عنوان خطای pipeline تفسیر کرد.

---

## ۴. Cohort، پوشش و snapshot

- Universe Measured: **۲٬۵۹۵ دارایی** از manifest; ۳۷۰ دارایی manifest محصول نداشتند و اندازه‌گیری نشدند.
- Product snapshot: `_scratch/ra_round3/product_live_final_v4.jsonl` با SHA `893b6d6aa1059d51a83bb7a44fd239d4c381695806562dd3dcdd3ed5d8ad9f27`؛ ۳٬۳۴۴ رکورد success.
- کندل‌های محصول: **۲٬۱۲۵٬۳۳۰** کندل؛ تاریخ‌های مشترک ۲٬۱۲۵٬۰۳۸؛ ردیف‌های قابل‌مقایسه ۲٬۱۲۴٬۹۳۶.
- ردیف‌های TSETMC: **۲٬۸۳۶٬۱۶۱** (شامل روزهای no-trade)؛ type0 D: ۱٬۲۳۳٬۲۱۳ ردیف.
- بازه: ۲۰۰۱ تا ۲۰۲۶؛ دارایی‌های چند InsCode: ۶۳۰.
- ترکیب نوع ابزار: options ۱٬۰۶۲، stocks ۷۹۴، bonds ۳۷۳، etf_funds ۳۴۶، futures ۱۴، warrants ۶.
- پوشش دوره‌ای (دارایی دارای حداقل یک کندل): پیش از ۲۰۲۰: ۵۷۸؛ ۲۰۲۰–۲۰۲۳: ۹۲۲؛ ۲۰۲۴ به بعد: ۲٬۵۹۵.
- Duplicate candle dates در snapshot: ۰؛ duplicate dates در CSVهای TSETMC: ۰.
- بیشترین پوشش سالانه در ۲۰۲۶ (۲٬۵۹۳ دارایی) و کمترین در ۲۰۰۱ (۱۴۴ دارایی) است؛ سال‌های میانی در artifact `report-stats.json` ثبت‌اند.

**پوشش مفقود (جدا از اختلاف عددی):**

| دسته | تعداد | توضیح |
|---|---:|---|
| NO_TRADE (مرجع دارد، کندل محصول ندارد) | ۵۶۳٬۸۰۰ | ردیف‌های H=L=0/VOL=0؛ طبق قرارداد کندل نمی‌شوند |
| PRODUCT_OMISSION (مرجع معامله‌دار، محصول ندارد) | ۴۹۹ | ۲۹۶ دارایی؛ نیازمند بررسی جداگانه |
| REFERENCE_OMISSION (محصول دارد، TSETMC ندارد) | ۲۶۴ | ۲۳۱ دارایی؛ عمدتاً تاریخ/نسخهٔ ابزار |
| PRODUCT_AFTER_REFERENCE_RANGE | ۲۸ | ۲ دارایی؛ snapshot جلوتر از مرجع |

این اعداد **هیچ‌کدام** در درصد تطبیق عددی وارد نشدند.

---

## ۵. نتیجهٔ Raw Parity

### ۵-۱. فیلدهای قراردادی (کل universe)

| فیلد | مقایسه | exact | exact٪ | ≤۰٫۵ | diff | rounding | null |
|---|---|---|---|---|---|---|---|
| Open (FIRST/effective) | ۲٬۱۲۴٬۹۳۶ | ۲٬۱۲۴٬۵۵۵ | ۹۹٫۹۸۲۱٪ | ۰ | ۳۷۰ | ۱۱ | ۰ |
| High (widen contract) | ۲٬۱۲۴٬۹۳۶ | ۲٬۱۲۴٬۵۵۴ | ۹۹٫۹۸۲۰٪ | ۰ | ۳۴۲ | ۴۰ | ۰ |
| Low (widen contract) | ۲٬۱۲۴٬۹۳۶ | ۲٬۱۲۴٬۶۲۹ | ۹۹٫۹۸۵۶٪ | ۰ | ۲۸۴ | ۲۳ | ۰ |
| Close official (پایانی) | ۲٬۱۲۴٬۹۳۶ | ۲٬۱۲۴٬۶۵۸ | ۹۹٫۹۸۶۹٪ | ۰ | ۲۳۸ | ۴۰ | ۰ |
| Close last trade | ۲٬۱۲۱٬۲۵۶ | ۲٬۱۲۰٬۹۷۶ | ۹۹٫۹۸۶۸٪ | ۰ | ۲۳۳ | ۴۷ | ۳٬۶۸۰ |
| Close display (basis) | ۲٬۱۲۴٬۹۳۶ | ۲٬۱۲۴٬۵۷۸ | ۹۹٫۹۸۳۲٪ | ۰ | ۳۱۲ | ۴۶ | ۰ |
| Volume | ۲٬۱۲۴٬۹۳۶ | ۲٬۱۲۴٬۳۰۳ | ۹۹٫۹۷۰۲٪ | ۰ | ۴۹۵ | ۱۳۸ | ۰ |

**جمع:** ۱۴٬۸۷۰٬۸۷۲ فیلد مقایسه‌شده، ۱۴٬۸۶۸٬۲۵۳ exact، **۹۹٫۹۸۲۴٪**. اختلاف‌های عددی باقی‌مانده: ۲٬۲۷۴ diff + ۳۴۵ rounding. no tolerance-only contract row وجود ندارد؛ exact و rounding جدا گزارش شده‌اند.

### ۵-۲. ردیف‌ها

- **Row exact (OHLC قراردادی):** ۲٬۱۲۴٬۲۵۱ از ۲٬۱۲۴٬۹۳۶ = **۹۹٫۹۶۷۸٪**.
- **Full-contract row** (OHLC+last+display+volume): ۱٬۰۴۰ ردیف mismatch از ۲٬۱۲۴٬۹۳۶ ردیف.
- **OHLC-only mismatch:** ۶۸۵ ردیف.
- **All-field composite:** ۹۸٫۸۲۷۷٪ — این عدد عمداً headline نیست، چون high/low literal و parser-stage را هم شامل می‌شود.

**تفکیک مسیر:**

| مسیر | دارایی | ردیف | exact | exact٪ |
|---|---:|---:|---:|---:|
| زنده (basis=last) | ۲٬۵۱۷ | ۲٬۱۲۰٬۷۶۵ | ۲٬۱۲۰٬۲۴۵ | ۹۹٫۹۷۵۵٪ |
| fallback (basis=closing) | ۷۸ | ۴٬۱۷۱ | ۴٬۰۰۶ | ۹۶٫۰۴۴۱٪ |
| local-db-fallback | ۸۴ | ۴٬۲۰۰ | ۴٬۰۳۰ | ۹۵٫۹۵۲۴٪ |
| local-db-unseen | ۶۴ | ۲۵۱ | ۲۰۲ | ۸۰٫۴۷۸۱٪ |

**high/low literal:** high ۹۱٫۰۰۴۲٪ و low ۹۵٫۱۰۴۹٪ — این تفاوت‌ها عمدتاً اثر مستند `widen()` هستند، نه خطای داده. با قرارداد widen، high ۹۹٫۹۸۲۰٪ و low ۹۹٫۹۸۵۶٪ است.

### ۵-۳. کنترل type0 (مرجع مستقل)

- ۱٬۱۹۲٬۰۷۱ تاریخ مشترک؛ close=last: **۹۹٫۹۵۵٪**؛ close=official closing: **۱۴٫۰۹۰٪**.
- open ۹۹٫۹۰۲٪، high ۹۱٫۴۶۲٪، low ۹۶٫۱۷۲٪، volume ۹۹٫۹۱۶٪؛ row exact فقط ۱۴٫۰۲٪ به‌دلیل کندل‌های تخت.
- نتیجه: type0 برای **close** مرجع مستقل خوبی است و تطبیق بالای آن با محصول نشان می‌دهد raw close محصول از یک منبع/زمان مشترک می‌آید؛ برای high/low مرجع کامل نیست.

---

## ۶. طبقه‌بندی علّی اختلاف‌های Raw

مبنای طبقه‌بندی: ۱٬۰۴۰ ردیف full-contract mismatch در ۵۴۳ دارایی. هر ردیف حداکثر یک علت اصلی گرفت؛ شواهد چندعلتی به‌عنوان نمونه حفظ شد.

| علت | دارایی | ردیف | فیلد | سهم از mismatch | Adjusted همچنان بد | اطمینان | شاهد |
|---|---|---|---|---|---|---|---|
| `SOURCE_DATA_DIVERGENCE` (شامل snapshot/عقب‌ماندگی منبع) | ۴۴۲ | ۸۲۰ | ۱٬۲۰۱ | ۷۸٫۸۵٪ | ۵۷۱ | MEDIUM/HIGH | محصول با type0 هم‌مقدار است؛ TSETMC فعلی فرق می‌کند |
| `FALLBACK_DB_SOURCE` (price_history محلی/board) | ۱۰۱ | ۲۲۰ | ۱٬۴۱۸ | ۲۱٫۱۵٪ | ۲۱۹ | HIGH | ردیف محصول با همان ردیف price_history برابر است، نه با TSETMC منتشرشده |

**علت‌هایی که در لایهٔ قراردادی صفر ماندند:** `INSTRUMENT_MAPPING`, `DATE_MAPPING`, `FIELD_MAPPING`, `PRICE_SCALE_OR_UNIT`, `RAW_ADJUSTED_MISMATCH`, `PARSING_OR_TRANSFORM`. یعنی خطای parser/نگاشت/تاریخ/مقیاس روی دادهٔ قراردادی مشاهده نشد. ۳ ردیف باقی‌ماندهٔ اصلاح fallback به ابهام `ins_code` مربوط است و در §۸ جدا آمده است.

**نمونه‌ها:**
- `SOURCE_DATA_DIVERGENCE`: `شرنگي 2025-11-16` volume ۲۷۹٬۳۹۵ در برابر ۲۸۰٬۳۰۶؛ `ددام 2024-06-18` high ۱۲٬۱۷۰ در برابر ۱۲٬۱۰۰؛ `دجابر 2026-09-09` open ۴۷٬۰۰۰ در برابر ۴۶٬۰۰۰.
- `FALLBACK_DB_SOURCE`: `فبيرا 2026-09-01` چهار فیلد OHLC با DB محلی برابر و با TSETMC متفاوت؛ `ضهرم8030 2026-09-01` کل OHLCV متفاوت؛ `اوان 2026-08-24` open/low برابر base (نه FIRST).

**تفکیک حجم:** از ۸۲۰ ردیف واگرایی منبع، ۲۴۹ ردیف فقط volume است؛ بقیه OHLC/open/high/low/close. بنابراین نمی‌توان کل واگرایی را «اختلاف قیمت» نامید.

**اثر بر Adjusted:** ۷۹۰ ردیف از ۱٬۰۴۰ ردیف، در لایهٔ Adjusted هم بد می‌مانند؛ بقیه با factor جبران می‌شوند یا فقط volume‌اند.

---

## ۷. جداسازی Raw / Factor / Adjusted و پیوند با Round 17

همان cohort، همان تعریف‌ها، اما هر لایه از اجرای معتبر خودش:

| لایه | مقایسه | موفق | درصد |
|---|---|---|---|
| Raw OHLC row exact (R18) | ۲٬۱۲۴٬۹۳۶ | ۲٬۱۲۴٬۲۵۱ | ۹۹٫۹۶۷۸٪ |
| Factor exact (R17 promoted) | ۱٬۱۸۷٬۹۴۵ | ۸۱۹٬۹۷۱ | ۶۹٫۰۲۴۳٪ |
| Adjusted OHLC (R17 promoted) | ۴٬۷۵۱٬۷۸۰ | ۳٬۲۴۵٬۶۷۸ | ۶۸٫۳۰۴۵٪ |

**گروه‌بندی دارایی‌ها:**

| گروه | دارایی | Factor exact٪ | Adjusted OHLC٪ | Raw row exact٪ |
|---|---|---|---|---|
| BOTH_HEALTHY | ۲٬۰۷۰ | ۹۱٫۲۳٪ | ۸۹٫۳۶٪ | ۹۹٫۹۹٪ |
| RAW_HEALTHY_FACTOR_WEAK | ۲۷۶ | ۱۷٫۸۱٪ | ۱۹٫۴۷٪ | ۹۹٫۹۹٪ |
| RAW_WEAK_FACTOR_HEALTHY | ۲۲۸ | ۹۶٫۰۵٪ | ۹۴٫۰۴٪ | ۹۹٫۴۶٪ |
| BOTH_WEAK | ۲۱ | ۱۸٫۸۶٪ | ۲۴٫۵۰٪ | ۹۹٫۸۴٪ |

**تفسیر:** ۲۷۶ دارایی با Raw سالم (۹۹٫۹۹٪) اما Factor ضعیف (۱۷٫۸۱٪)، بیشترین سهم تاریخ‌های Factor را دارند. ۲٬۰۷۰ دارایی «هر دو سالم» Factor ۹۱٫۲۳٪ دارند. بنابراین شکاف Adjusted عمدتاً Factor است.

**رگرسیون‌های R17:** ۸۵ ردیف متریک در `regression-layer-link.csv`:
- `RAW_HEALTHY_FACTOR_WEAK`: ۶۸
- `BOTH_HEALTHY`: ۱۲
- `BOTH_WEAK`: ۴
- `RAW_WEAK_FACTOR_HEALTHY`: ۱

| نماد | Raw row exact٪ | Raw contract٪ | Factor exact٪ | Adjusted OHLC٪ | گروه |
|---|---|---|---|---|---|
| حخزر | ۱۰۰٫۰۰۰۰ | ۱۰۰٫۰۰۰۰ | ۳٫۹۳۶۰ | ۴٫۰۶۹۴ | RAW_HEALTHY_FACTOR_WEAK |
| فروي | ۱۰۰٫۰۰۰۰ | ۱۰۰٫۰۰۰۰ | ۳٫۷۲۶۳ | ۳٫۷۴۳۲ | RAW_HEALTHY_FACTOR_WEAK |
| كماسه | ۱۰۰٫۰۰۰۰ | ۱۰۰٫۰۰۰۰ | ۷۷٫۱۰۲۵ | ۸۷٫۳۸۵۲ | BOTH_HEALTHY |
| ميدكو | ۱۰۰٫۰۰۰۰ | ۹۹٫۹۸۷۵ | ۴۱٫۷۸۳۲ | ۴۰٫۱۰۰۵ | RAW_HEALTHY_FACTOR_WEAK |
| نمرينو | ۹۹٫۹۷۲۲ | ۹۹٫۹۹۶۰ | ۲۱٫۴۴۳۲ | ۲۰٫۱۶۶۸ | RAW_HEALTHY_FACTOR_WEAK |

**نتیجه برای سه رگرسیون مستقیم R17:** میدكو، كماسه و نمرينو Raw تقریباً ۱۰۰٪ سالم دارند؛ اختلاف آن‌ها Factor/رویداد است. **فروي** و **حخزر** نیز Raw ۱۰۰٪ دارند اما Factor حدود ۳٫۷٪–۳٫۹٪ است؛ این دو blocker مستقل از Raw و مربوط به تعریف `P`/DPS خالص‌اند. هیچ‌کدام از این موارد با تغییر دادهٔ خام حل نمی‌شود.

**بلوکرهای R17:** ۱۸۴ گام no-cash، ۶۳ گام فاقد منبع و ۵۹ مورد far در لایهٔ رویداد/Factor باقی می‌مانند. Raw parity این دارایی‌ها اندازه‌گیری شد و به‌عنوان `RAW_HEALTHY` یا `RAW_ATTENTION` در `regression-layer-link.csv` ثبت است؛ هیچ مقدار حدسی برای باز کردن آن‌ها وارد نشد.

---

## ۸. اصلاح عمومی: بازسازی price_history از دادهٔ منتشرشده

### علت اثبات‌شده
- `price_history` قبل از اصلاح: **۳۶۹٬۳۵۹** ردیف `src=NULL`، **۷۴٬۳۵۶** ردیف `src=board`، فقط **۳۷** ردیف `published`.
- **۱۰٬۴۴۸** ردیف در **۲۷۱** دارایی، `open` را از `<OPEN>` پایه گرفته‌اند (نه `<FIRST>`).
- در همان پروفایل، اختلاف عددی با TSETMC: open ۱۶٬۵۰۳، close ۶٬۶۳۸، high ۲۷٬۲۵۸، low ۲۰٬۶۵۳، volume ۶٬۶۳۷ ردیف. (last-null به‌صورت جدا و نه به‌عنوان اختلاف عددی ثبت شد.)
- محصول برای ۱۰۱ دارایی fallback، همین ردیف‌های محلی را به‌عنوان Raw سرو می‌کرد؛ ۲۲۰ ردیف full-contract mismatch از همین منبع بود.

### پیاده‌سازی
`tools/ra365_round18_repair_history.py`:
- فقط روی **کپی** دیتابیس کار می‌کند و مسیر عملیاتی را رد می‌کند.
- برای هر ۲٬۵۹۵ دارایی، CSV کش‌شدهٔ همان `ins_code` را با `candle_contract.from_csv_row` پارس می‌کند: `open=FIRST`, `close=CLOSE`, `last=LAST`, `volume=VOL`.
- فقط داخل بازهٔ موجود هر نماد upsert می‌کند؛ پوشش را بازتر نمی‌کند و ردیف حذف نمی‌کند.
- `src=published` می‌نویسد که طبق قرارداد `UPSERT_SQL` بر `board`/`NULL` اولویت دارد.
- کلید `(symbol,date)` است؛ اجرای دوم چیزی اضافه نمی‌کند.

### نتیجهٔ قبل/بعد (fallback display، همان cohort)

| شاخص | قبل | بعد |
|---|---|---|
| ردیف‌های مقایسه‌شده | ۴٬۴۹۷ | ۴٬۸۶۸ |
| row exact | ۴٬۲۷۸ | ۴٬۸۶۵ |
| row exact٪ | ۹۵٫۱۳۰۱٪ | ۹۹٫۹۳۸۴٪ |
| last-null | ۳٬۶۸۰ | ۰ |
| دارایی با basis=closing | ۷۸ | ۵۰ |

- نوشتن اول: ۳۵۴٬۸۷۴ ردیف published؛ ۶٬۴۹۰ ردیف افزوده، ۳۴۸٬۳۸۴ ردیف جایگزین؛ `integrity_check=ok`.
- اجرای دوم: ۳۵۴٬۸۷۴ upsert، **۰** افزوده؛ logical sums و SHA دیتابیس یکسان (`8644d30bfb3c493c5f6c9fad1b857c9277d9a05306f79a712d576bcedf8f6164`). یعنی ایدمپوتنت.
- اثر روی مسیر زنده: **صفر**؛ `get_chart_tsetmc`/CDN تغییر نکرد. این اصلاح فقط مسیر fallback/degraded را هدف می‌گیرد.
- ۳ ردیف باقی‌مانده به ابهام `ins_code` (نسخهٔ قدیم/جدید ابزار) مربوط است؛ برای آن‌ها مقدار حدسی نوشته نشد.
- انتشار به دیتابیس عملیاتی: `BLOCKED`. کپی repaired و manifest آماده است؛ نیازمند snapshot/rollback و تأیید عملیاتی مطابق Round 17.

---

## ۹. تست‌ها، Full gate و Build

- `dev/test_round18_raw_parity_v1.py`: ۳۵ بررسی، ۰ شکست (mapping FIRST/OPEN، no-trade، widen، basis، exact/tolerance/rounding، cause taxonomy، عدم اعمال factor).
- `dev/test_round18_taxonomy_v1.py`: ۵ بررسی، ۰ شکست (source divergence، fallback، field mapping، date mapping، healthy row).
- `dev/test_round18_history_repair_v1.py`: ۱۴ بررسی، ۰ شکست (FIRST mapping، published priority، idempotency، from_db_row).
- سوئیت‌های R15/R16/R17 و official-ledger در اجرای gate دوباره اجرا شدند.
- **Full gate:** `ALL SUITES PASSED`؛ 145 سوئیت شمارش‌شده، 44 silent، 2 skip، failure: 0؛ `PROTECTED_DB_UNCHANGED`.
- Build فرانت: بدون تغییر فرانت؛ وضعیت `VERIFIED`.
- دیتابیس عملیاتی: SHA `7b933b05d03b8a2f9383f901faf6b2c34f1500e70619d6cc5c8039f171b1848c` پیش/پس یکسان. دیتابیس promoted با fingerprint گیت محافظت شد.

---

## ۱۰. Artifactها و checksumها

| فایل | حجم | SHA256 |
|---|---:|---|
| `raw_ohlc_reference.csv` (registry) | ۴۳۵٬۰۵۴ | `e0252304ed509474096d8371f5b6b10819c56e39d6a53b80257d4a3364cca70b` |
| `raw_ohlc_reference.csv.gz` (full rows) | ۵۷٬۸۴۹٬۰۷۱ | `d8b77584c57e2dc81f9d85f403b7b03e3cbe1ba15b91ad400919a4a47dee998f` |
| `raw-ohlc-parity.csv` | ۱٬۲۸۲٬۹۲۵ | `af197d3629a247192ab2822762c6961e548fba282541f885b2d5351fc76a1354` |
| `raw-ohlc-row-mismatches.csv` | ۲۸۷٬۹۳۳ | `cb349f2cc6edd9db06ed21d2f8710c395abeb80fd2bb324d1ddc5a6a15931212` |
| `raw-ohlc-mismatch-taxonomy.csv` | ۱٬۱۲۷ | `83def8b94947da91d48123e709cbdd998f6d360be6e7793faf15245d6d55665d` |
| `source-field-matrix.csv` | ۱۱٬۴۶۲ | `66044c62249e81e44fea93a1cb741c10667a35655a07c6b3d0494df288f1e422` |
| `raw-ohlc-cohort-manifest.json` | ۹٬۱۹۷ | `d9dd4701fef70da5336813fdd8dc59607c1b0835986ff485d5106d0fa2db00cb` |
| `layer-decomposition.csv` | ۲۸۵٬۳۰۴ | `dab81bb036f525ef6590c0e16399da84d8f124182a040bf755c2e1092599bf09` |
| `fallback-display-parity-before.csv` | ۱۰٬۵۸۵ | `25f6780f5d24faad68f6630d2b0fa3f8c72ba8602dd1a534df6e8e0d1784aeb4` |
| `fallback-display-parity-after.csv` | ۹٬۸۴۲ | `de7e7c23660baa15a4b4e40e151ca7d31264974c63324eb5e27975ae2cb63dc4` |
| `raw-ohlc-reference-manifest.json` | ۱٬۴۹۳ | `81367461762fd7b48acc6996676e54fb0e6edbcb4585277491b33a106b7dc689` |
| `layer-joint-summary.json` | ۱٬۴۸۷ | `2a5076feac8629dc87f43c70cd06ec22e59dab053eebac92c3d27cefbcaff845` |
| `regression-layer-link.csv` | ۱۱٬۶۱۶ | `679fa7ea67763b1d2c98930b838a2afe0f2c9c59f84d44d336232d4f26d12fc7` |
| `price-history-repair-manifest-first.json` | ۳۷۶ | `9f7da818450a4ea97dc5801e825100b639316fef19e253c2bcc7f4fed0f39d06` |
| `fallback-adjusted-parity-before.csv` | ۴٬۰۷۰ | `183b16f2465854d5aa58f9b47ffd6af62d92e172293501b5c7a85302adcebd58` |
| `fallback-adjusted-parity-after.csv` | ۴٬۰۹۵ | `c8e7a524cfe737d0105ab833d54f8c17be60588bb8f128c501120380aa08d63b` |

مرجع کامل: ۲٬۸۳۶٬۱۶۱ ردیف TSETMC برای ۲٬۵۹۵ دارایی، gzip ۵۷٬۸۴۹٬۰۷۱ بایت. schema و معنای فیلدها در `raw-ohlc-reference-manifest.json` و `source-field-matrix.csv` است.

---

## ۱۱. وضعیت نهایی

| مورد | وضعیت |
|---|---|
| قرارداد Raw با payload واقعی | `VERIFIED` |
| Raw parity کل universe | `VERIFIED` (۹۹٫۹۶۷۸٪ ردیفی) |
| جداسازی Raw/Factor/Adjusted | `VERIFIED` |
| علت‌شناسی mismatch خام | `VERIFIED` |
| اصلاح fallback روی کپی | `IMPLEMENTED_AND_TESTED` |
| انتشار عملیاتی اصلاح | `BLOCKED` (snapshot/rollback/تأیید بیرونی) |
| ۱۸۴ no-cash / ۶۳ missing / ۵۹ far | `BLOCKED` در لایهٔ Factor؛ مستقل از Raw |
| فروي `BLOCKED_P_DEFINITION` | `BLOCKED`؛ Raw ۱۰۰٪ |
| حخزر `UNVERIFIED_NET_DPS` | `BLOCKED`؛ Raw ۱۰۰٪ |
| Full gate | `VERIFIED` |
| Build فرانت | `VERIFIED` (بدون تغییر فرانت) |
| webgw برای کل universe | `NOT_MEASURED` (نمونهٔ ۳٬۲۷۶ ردیفی) |
| Operational DB | `VERIFIED` بدون تغییر |

---

## ۱۲. Commitها و باقی‌مانده‌ها

- Commit کد/ابزار/تست این راند: `531aa2b1 + 596d1523`.
- گزارش و artifactها در commit جداگانه ثبت می‌شوند.
- هیچ push/merge انجام نشد؛ `main` تغییر نکرد.
- باقی‌ماندهٔ اصلی: Factor exact ۶۹٫۰۲۴۳٪ و Adjusted OHLC ۶۸٫۳۰۴۵٪. Raw دیگر گلوگاه اصلی نیست.
- پیشنهاد Round 19: تمرکز روی رویدادهای Factor (no-cash/far/فروي/حخزر) با همان cohort و همان تعریف‌ها؛ Raw به‌عنوان baseline ثابت نگه داشته شود. اصلاح fallback ابتدا باید از مسیر migration/rollback تأییدشده به محیط عملیاتی منتقل شود.

**دستور پایانی:** هیچ درصدی با تغییر مخرج، حذف موارد دشوار یا مقایسهٔ خام با تعدیل‌شده بهتر نشد. تفکیک Raw/Factor/Adjusted نشان داد مسیر زندهٔ Raw از منبع وفادار است؛ شکاف اصلی Adjusted یک مسئلهٔ Factor/رویداد است و اصلاح fallback نیز فقط دادهٔ محلی کهنه را با دادهٔ منتشرشده جایگزین کرد.


---


---


---


---

## ۱۳. ضمیمه — ممیزی کامل Rahavard type0

این بخش، سؤال «آیا OHLC خام BorsTerminal با Rahavard یکسان است؟» را در سطح ردیف و فیلد پاسخ می‌دهد. گزارش تفصیلی: `docs/RA365-ROUND18-RAHAVARD-RAW-OHLC-PARITY-REPORT.md`؛ داوری نهایی اختلاف‌ها: `docs/RA365-ROUND19-MISMATCH-CLOSURE-REPORT.md`.

- **تمام ۲٬۵۹۵ دارایی** نوع `type0` در snapshot منجمد بررسی شدند؛ **۱٬۱۸۸٬۹۲۱** ردیف قابل‌مقایسه از **۱٬۱۹۲٬۰۷۱** تاریخ مشترک.
- **تطبیق قراردادی Raw:** **۹۹٫۸۹۰۷٪** فیلد و **۹۹٫۸۲۲۱٪** ردیف.
- **تطبیق تحت‌اللفظی OHLC:** high ۹۱٫۷۰۴۳٪، low ۹۶٫۴۲۷۳٪، ردیف کامل ۸۷٫۶۱۰۱٪؛ اختلاف عمدتاً `widen()` مستند است.
- **معنای type0:** close = LAST (۹۹٫۹۱۰۲٪) نه official CLOSE (۱۴٫۰۷۶۰٪)؛ open = FIRST (۹۹٫۸۶۴۱٪) نه base OPEN (۳٫۴۸۴۶٪).
- **علت‌های نهایی (Round 19):** SOURCE_DATA_DIVERGENCE ۱٬۱۵۰ ردیف؛ HISTORICAL_REVISION ۵۴۹؛ PRECISION ۲۹۸؛ CANDLE_GEOMETRY ۶۲؛ PARSING ۵۶؛ UNCLASSIFIED ۰.
- **تعیین تکلیف P0:** از ۶ ردیف PARSING اولیه، ۵ ردیف volume در واقع type0-only بودند و به SOURCE منتقل شدند؛ ۱ ردیف volume صفر snapshot با TSETMC مثبت ماند. ۵۵ ردیف UNCLASSIFIED قبلی، open با `FIRST=0` و fallback مستند product بودند و PARSING شدند؛ ۳۱ ردیف دیگر به سه‌منبعی SOURCE رفتند. UNCLASSIFIED صفر شد.
- **هیچ اصلاح production** موجه اثبات نشد؛ gapهای ۴۹۹تایی snapshot در pipeline زنده وجود دارند و flat/geometry از منبع Rahavard است. تنها قرارداد مقایسه (widen با official CLOSE) اصلاح شد.
- **پوشش:** type0 فقط حدود **۵۵٫۹۴٪** از کندل‌های محصول را می‌پوشاند؛ Full-Universe برای ردیف‌های Rahavard قابل‌دسترسی است، نه تمام تاریخ محصول.
