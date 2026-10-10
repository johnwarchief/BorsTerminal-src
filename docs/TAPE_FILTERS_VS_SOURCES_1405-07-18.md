# فیلترهایِ تابلوخوانی در برابرِ منابع — سنجشِ ۱۴۰۵-۰۷-۱۸

بازدید: `C:\Users\PCMOD\Desktop\BorsTerminal` (شاخۀ `fix/fts-p0-2-gates-flip`) — فقط‌خواندنی، هیچ کدی تغییر نکرد. پنج فیلترِ اصلیِ رجیستری (`funnel_registry.py:119-263`) плюсِ دو فیلترِ کمکیِ همان لایه (`f_smart`, `f_legal`)؛ هر هفت درِ `tape_flags.apply_tape_flags` (`tape_flags.py:332-353`) ساخته می‌شوند و از همان pathِ تولید (`api/market.py:1031`) به تابلو، بج‌ها و قیف می‌رسند. بانک و API الان end-of-session‌اند (بازار بسته؛ نشستِ `d_even=20261010`).

## ۱) جدولِ پنج + دو فیلتر

ورودی‌ها از کوئریِ تابلو (`api/market.py:841-866`) و پنجرۀ `[ih]` از `tape_history` (`api/market.py:324-369`) می‌آیند. `tvol = q_tot_tran` (`api/market.py:959`)، `plp = plp_raw` (محاسبۀ `api/market.py:1000`، با fallback به `percent_last` — `tape_flags.py:106-116`)، `is_live` (`api/market.py:556`).

| فیلتر | ورودی‌ها (ستونِ واقعی + file:line) | فرمولِ اجرا شده (tape_flags.py) | آستانه‌ها و مبدأ | حالتِ خروجی | مصرف‌کننده‌هایِ UI |
|---|---|---|---|---|---|
| `f_clock` الگوی ساعت | `p_last`,`p_closing` (`api/market.py:843`)، `vol_ratio_file`=`tvol÷(prior30_vol/30)` (`tape_flags.py:174-176`؛ `prior30_vol` `api/market.py:345`)، `z_tot_tran` | `tape_flags.py:211-216` | `CLOCK_DELTA=0.02` (`:62`) از `docs/الگوی ساعت.txt:1`؛ `CLOCK_TRADES=30` (`:72`)؛ `VOL_BASE_SESSIONS=30` (`:47`) | bool؛ NaNِ ورودی → False (`:216`) | `tapeStore.ts:14,18`؛ `tapeBadges.ts:56-66`؛ `tapeAlgorithms.ts:375-376` |
| `f_susp` حجم مشکوک | `vol_ratio_file`، `z_tot_tran` | `tape_flags.py:219-222` | `SUSP_VOL_MULT=3.0` (`:58`) از `حجم مشکوک.txt:1`؛ `SUSP_TRADES=50` (`:73`) | همان | `tapeStore.ts:19`؛ `tapeBadges.ts:90-92`؛ `useInspectorBoard.ts:44` |
| `f_jet` جت | `vol_ratio_file`, `buyer_power`=`buy_i_vol/buy_count_i ÷ sell_i_vol/sell_count_i` (`tape_flags.py:179-189`؛ ستون‌ها `api/market.py:847-852`)، `p_last`,`p_closing`,`plp`، پلکان `h{2,5,9,19,29,39,49,59}_max` (`api/market.py:357-364`) | `tape_flags.py:225-241` | `JET_VOL_MULT=3.0`، `JET_BUYER_POWER=1.5`، `JET_MIN_TRADES=100` (`:57,:60,:76`)؛ پلکان `JET_LADDER` (`:41`) — عین `فیلتر جت.txt:1` | همان؛ پنجرۀ ناقص ⇒ نسنج (`_sessions_ok` `:143-145`) | `tapeStore.ts:20`؛ `tapeBadges.ts:93-102`؛ `SymbolInspector.tsx:628-630` |
| `f_roobi` کف‌روبی | `p_last`، `tmin`=`market_watch.allowed_min` (`api/market.py:861`)، `zd1`=`buy_q1_cnt` (`:858`)، `qd1`=`buy_q1_vol` (`:857`)، `plp` | `tape_flags.py:244-270` | `pl==tmin`، `plp<-1`، `zd1>1`، `qd1>100` (`:68-70`) — عین `کف روبی صف فروش.txt:1` | همان | `tapeStore.ts:21`؛ `tapeBadges.ts:103-105`؛ `SuspiciousPanel.tsx:92`؛ `MarketFilters.tsx:277-281` |
| `f_noqteh` نقطه‌زنی | `p_closing`، `min_low_29` (`api/market.py:354-355`)، `vol_ratio_file`، `z_tot_tran` | `tape_flags.py:273-297` | `NOQTEH_MAX_DIST=3.0`، `LOW_BASE_SESSIONS=29`، `NOQTEH_TRADES=5` (`:54,:64,:74`) — عین `نقطه زنی.txt` (حلقۀ `n<29`، `cfield2<3`) | همان؛ `min_low_29==0` ⇒ رد (`:292`) | `tapeStore.ts:22`؛ `tapeBadges.ts:106-108` |
| `f_smart` (کمکی) | `vol_ratio_file`، `buyer_power`، `p_last≥p_closing`، `plp>0` | `tape_flags.py:300-314` | `SMART_VOL_MULT=1.5`، `SMART_BP_GE=1.0` (`:84-85`) — `ورود پول هوشمند.txt` سطرِ ۱ | همان | `tapeStore.ts:25`؛ `tapeBadges.ts:111-121`؛ UI فقط پرچم را می‌خواند (`MarketFilters.tsx:72` backend-only) |
| `f_legal` (کمکی) | `f_smart` + `buy_i_vol>0.5*tvol` + `sell_n_vol>0.5*tvol` (`api/market.py:847-850`) | `tape_flags.py:317-329` | `LEGAL_SHARE_OF_TVOL=0.5` (`:90`) — فایل «کد به کد…» سطرِ ۱ | همان | `tapeStore.ts:26`؛ `tapeBadges.ts:122-130` |

سه‌حالته: درِ فرمول سه مقدار True/False/NaN وجود دارد، اما `apply_tape_flags` با `.fillna(False)` بیرون را دوحالته می‌کند و بعد `& alive` پرچمِ ردیف‌هایِ بیرونِ تابلویِ امروز را خاموش می‌کند (`tape_flags.py:119-129,346-352`)؛ این همان try/catchِ ExecFilter است. «سنجش‌ناپذیر» درِ UI از ستون‌هایِ nullِ کمکی خوانده می‌شود (`vol_ratio_file`, `hist_sessions`, `min_low_29`, `tmin`… — `_KEEP_NULL` در `api/market.py:1054-1078`).

## ۲) معنا درِ جزوه و پین‌هایِ منبع

رجیستری برایِ هر فیلتر `source_file` + `source_sha256` پین کرده است؛ هر هفت پین را خودم راستی‌آزمایی کردم (`hashlib.sha256` روی `docs/*.txt` — هفت‌از‌هفت OK، مثلاً `الگوی ساعت.txt → 6637192e4d10a73d…`).

- فرمولِ هر پنج+دو فیلتر **عیناً درِ فایل‌هایِ `docs/*.txt` هست** (متنِ کاملِ بالا خوانده شد؛ `funnel_registry.py:130,153,173,197-201,217-225,239,258` سطر:فرمول را ثبت می‌کنند). برایِ هیچ‌یک NOT FOUND نیازی نیست.
- معنایِ جزوه‌ای (از `FTS_CHART3_extracted_text.txt`): حجم مشکوک «سه برابر میانگین ماهانه» (سطرِ ۷۸)؛ الگوی ساعت «اگر قیمت آخرین معامله بیشتر از ۱٪ نسبت به قیمت پایانی بزرگتر بود…» (سطرِ ۸۲)؛ کف‌روبی «سهم صف فروش است ولی اوردرهای قوی در حال خرید…» (سطرِ ۸۶)؛ نقطه‌زنی «ورود در کف سوم یا پنجم» (سطرِ ۹۵)؛ جت «عبور از سقف تاریخی یا مقاومت استاتیک» (سطرِ ۳۶).
- تضادِ ثبت‌شده X-1: چارت ۳ عددِ **۱٪** را می‌گوید و فایل `1.02`؛ رأیِ ۱۸ متنِ فایل را مرجع کرد (`funnel_registry.py:130-132`).
- تنظیم‌پذیری از جزوه: ضریبِ حجمِ ساعت «عدد ۱ را به ۳ یا ۵ تغییر دهیم» (`jozve_FTS_handwritten_pages_1-24.md:608-609` و `FTS_CHART3:90`)، دامنهٔ مشکوک «(tvol)>2.5 یا 5» (`:617`)، تقریبِ کف‌روبی «(tno)>200» (`:612` — درِ کد نیست، `funnel_registry.py:205`).
- **NOT FOUND:** فیلتر «خشک کردن» — نام درِ چارت ۳ هست، فرمول درِ هیچ منبعی نیست (`funnel_registry.py:268-270`).

## ۳) سنجشِ زنده رویِ دادهٔ خودمان

نمونۀ API: `GET http://127.0.0.1:8002/api/market` در **۲۰۲۶-۱۰-۱۰T۰۹:۵۹:۳۰Z** (۱۳:۲۹ تهرانی؛ بازار بسته ⇒ پایانِ نشست). ۸۰۰۱ پاسخ نداد (`http=000` در ۰۹:۵۸:۵۹Z)؛ ۸۰۰۰ هم بسته بود. `meta: d_even=20261010, last_sync=2026-10-10 10:23:55`؛ ۵۸۹۲ ردیف، ۲۹۱۷ ردیفِ `is_live`.

| فیلتر | True | False | null | (نمونۀ True) |
|---|---|---|---|---|
| f_clock | ۲۳ | ۵۸۶۹ | ۰ | سصفها، ضخود8061… |
| f_susp | ۳۵ | ۵۸۵۷ | ۰ | اتكام، دزاگرس، شساخت… |
| f_jet | ۱ | ۵۸۹۱ | ۰ | لبن |
| f_roobi | ۱۶ | ۵۸۷۶ | ۰ | تاپكيش، خشرق، غمارگ… |
| f_noqteh | ۱ | ۵۸۹۱ | ۰ | هماي |
| f_smart | ۲۷ | ۵۸۶۵ | ۰ | تمحركه، جهرم، شساخت… |
| f_legal | ۳ | ۵۸۸۹ | ۰ | شساخت، ضبساما725، غمايه |

«نسنجیده» درِ حالتِ nullِ ورودی‌هاست (رویِ ۲۹۱۷ ردیفِ live): `vol_ratio_file` null ⇒ ۱۱۷۷ (۷۳ ردیف بی‌`tape_history`، ۶۶۵ تایِ دیگر زیرِ ۳۰ نشست)؛ `min_low_29` null ⇒ ۷۳؛ `hist_sessions` null ⇒ ۷۳؛ `buy_q1_cnt` null ⇒ ۱۰۹۰ درِ کلِ payload ولی ۰ درِ live؛ `tvol`/`z_tot_tran`/`tmin` هرگز null نیستند. توزیعِ ورودی‌ها (live): `vol_ratio_file` — ۱۵۰۵ ردیف <۱، ۱۰۳ ردیف ۱–۱٫۵، ۶۴ ردیف ۱٫۵–۳، ۶۸ ردیف ≥۳؛ `z_tot_tran` — >۳۰: ۱۰۷۱، >۵۰: ۹۷۶، >۱۰۰: ۸۳۵، >۵: ۱۳۴۶؛ `buyer_power_raw` سنجیده درِ ۱۸۵۸ که ۴۴۸ تایِ آن ≥۱٫۵؛ `percent_last ≥0` درِ ۱۸۸۱ ازِ ۲۵۷۱ِ سنجیده.

کوئری‌هایِ فقط‌خواندنیِ بانک (`file:market.db?mode=ro`، ۱۰:۰۰:۴۲Z): `market_watch` ۵۸۹۴ ردیف، همۀ `allowed_min>0`؛ `tape_history` — ۴۰۹۲ نماد که ۳۱۵۴ تایِ آن ≥۳۰ نشست دارند؛ `client_type` امروز ۱۵۹۳ ردیف (سقفِ نمادهایِ سنجیدنیِ `f_smart`/`f_legal`).

## ۴) تطبیقِ زنده با TSETMC

`GET https://cdn.tsetmc.com/api/Instrument/GetInstrumentInfo/{insCode}` درِ ۱۰:۰۱:۲۱Z برایِ پنج نماد (خشرق، زاگرس2، سصفها، لبن، هماي): **`psGelStaMin/psGelStaMax` درِ پنج‌از‌پنج عیناً برابرِ `allowed_min/allowed_max`ِ `market_watch`** — همان نگاشتِ درست؛ `h5_max`/`h19_max` سقفِ مجاز نیستند (سقفِ تک‌روزیِ نشستِ kامِ پیش — `api/market.py:357-364`) و مقابله‌شان با psGelSta ساختگی است. `qTotTran5JAvg` عمداً مقابله نمی‌شود: واحدش تأیید نشده (زاگرس2: ۱۰۰٬۰۰۰ در برابرِ tvolِ ۲٬۴۱۵٬۴۶۹) و سنجشِ امروزِ مالک برایِ «آ س پ» هیچ‌یک ازِ دو کاندیدایِ ما را نداد. `dEven=20261010` درِ هر پنج ⇒ هم‌نشست بودنِ مقایسه تأیید شد.

## ۵) اختلاف‌ها و تفسیر

| یافته | طبقه |
|---|---|
| فرمولِ هر هفت فیلتر == فایل‌هایِ `docs/*.txt` (پین‌ها OK) | بدونِ اختلاف |
| چارت ۳ «۱٪» در برابرِ فایل «۱٫۰۲» برایِ ساعت (رأیِ ۱۸: فایل مرجع) | فرمولِ محاسباتی (تعارضِ ثبت‌شده در `funnel_registry.py:132`) |
| «خشک کردن» بدونِ فرمولِ منبع | فیلد ناموجود در منبع (NOT FOUND صریح) |
| ۱۱۷۷ ردیفِ live بی‌مبنایِ Σ/۳۰ (۶۶۶ نمادِ زیرِ ۳۰ نشست) — درِ سایت هم ExecFilter می‌اندازد | نگاشتِ درستِ «نسنج»؛ اختلافِ قبلیِ ردیف‌محور (شش‌برابر) اصلاح شده — `tape_flags.py:43-50` |
| `plp_raw`/`resistance_59`/`dist_min30_pct` درِ payload نیستند (کلیدِ absent) درحالی‌که داوریِ داخلی می‌سازند | رندرِ UI (عمدی، `api/market.py:653`) |
| `f_smart` فقط ≤۱۵۹۳ نماد (پوششِ `client_type`) | فیلد ناموجود در منبع (برایِ بقیه) |
| [is5]/[is6] درِ بانک نیست ⇒ دو variantِ پولِ هوشمند سنجیده نمی‌شوند | فیلد ناموجود در منبع (`funnel_registry.py:244`) |
| ۸۰۰۱ (نصبی) درِ این نشست پاسخ نداد؛ نمونهاش ازِ ۸۰۰۲ (dev) است؛ تطبیقِ «نصبی ⇄ dev» درِ این نشست **راستی‌آزمایی نشده** | UNAVAILABLE |
| ساعتِ ۱۳:۲۹ تهرانی ⇒ end-of-session؛ هیچ اختلافِ زمانِ نشستِ دیگری دیده نشد (`dEven` دو طرف یکی) | — |
| qTotTran5JAvg | واحد/تبدیلِ داده — **راستی‌آزمایی نشده** (بدونِ ادعایِ delta) |

## ۶) TradersArena

درِ این نشست **گرفته نشد و دسترسی اصلاً attempt نشد** ⇒ `UNAVAILABLE`. جزوه مقایسه‌اش را برایِ الگوی ساعت می‌خواهد: «در سایت TRADER ARENA ستون اختلاف آخرین و پایانی را از زیاد به کم فیلتر می‌کنیم» (`FTS_CHART3_extracted_text.txt:83`)؛ خودِ Jobِ ممیزی هم صریحاً همان را `UNAVAILABLE` می‌گذارد (`tools/market_tape_live_audit.py:14-17`). لازمِ کار: دسترسیِ شبکه/احرازِ به tradersarena.com، ستونِ «diff last/closing» برایِ همان `dEven`، و مقابلهٔ فقط‌خواندنیِ `pl−pc`ِ ما — نشستِ جدا یعنی بی‌اعتبار، پس هم‌نشست بودن باید اول ثابت شود.
