# مشخصات: به‌روزرسانی رویدادمحور دادهٔ ۵ شاخص بنیادی — تازگی ≤ ۱۵ دقیقه

- **تاریخ:** ۲۰۲۶-۱۱-۰۳
- **شاخه:** `integration/4axes-main-2026-11-03` (ادغام `4-axes` با `main`)
- **وضعیت:** جهت و پارامترها توسط مالک تأیید شد (۲۰۲۶-۱۱-۰۳): رویدادمحور، SLA ≤ ۱۵ دقیقه در پنجرهٔ انتشار، نخ درون‌برنامه‌ای (گزینهٔ A).
- **دامنه:** موتور به‌روزرسانی مرجع پایتون (`codal_pipeline` / `codal_fetcher` / `codal_fts_updater`). پورت Go در فاز مهاجرت `sync` و پس از تثبیت قرارداد.
- **خارج از دامنه:** تغییر فرمول یا آستانهٔ هیچ‌یک از ۵ شاخص، تغییر موتور تعدیل، تغییر خط لولهٔ شبانهٔ staging-first، انتشار snapshot در GitHub، و اولویت‌دهی بر اساس watchlist (فاز ۲).

---

## ۰. خلاصهٔ اجرایی

بیشترِ زیرساختِ لازم **از قبل وجود دارد**: نخِ زمان‌بند در بوت (`codal_pipeline.start_worker`)، کشف افزایشی با watermark محافظه‌کارانه (`codal_fetcher.discover_notices`)، صف با claim/lease/retry، `pipeline_dirty` با نقشهٔ وابستگیِ شاخص‌ها، و `recompute_dirty` که فقط نمادهای dirty را باطل/محاسبه می‌کند.

شکافِ واقعیِ تازگی سه چیز است:

1. **فاصلهٔ ثابتِ ۳ ساعتهٔ پاس شبکه** (`DISCOVERY_MIN_GAP_S = 3 * 3600`) که مستقل از ساعتِ انتشار کدال است.
2. **تعویقِ کاملِ محاسبه در بازارِ باز** (`defer_recalc = market_in_session(...)`): ردیف‌های مادی‌شدهٔ `fts_results` تا پایانِ نشست کهنه می‌مانند و خواننده‌هایِ اسکرینر/قیف می‌توانند همان ردیفِ کهنه را ببینند.
3. **نبودِ قفلِ متقابل میان worker افزایشی و orchestrator شبانه** و **نبودِ تازگیِ per-symbol/per-axis** در API و کارت.

این مشخصات آن سه شکاف را می‌بندد، بدونِ ساختنِ خزنده یا صفِ دوم.

---

## ۱. شواهد وضعیت فعلی

| ادعا | جا |
|---|---|
| نخِ worker در بوتِ اپ شروع می‌شود (به‌ازایِ هر پروسه یکی) | `app.py:227`، `codal_pipeline.start_worker` |
| tick پیش‌فرض ۳۰ ثانیه و تصمیمِ بیدارباش از صف/checkpoint | `codal_pipeline.py:1315` (`start_worker`)، `next_wakeup` |
| حداقل فاصلهٔ دو پاس شبکه = ۳ ساعت | `codal_pipeline.py:1094` (`DISCOVERY_MIN_GAP_S`) |
| كادنسِ صف: تهی ۶ ساعت، backlog ۵ دقیقه، کف ۶۰ ثانیه | `codal_pipeline.py:1090-1092` |
| `worker_once` فقط وقتی پاس شبکه می‌زند که `age_net >= DISCOVERY_MIN_GAP_S` | `codal_pipeline.py:1278` |
| محاسبهٔ dirty در بازارِ باز به چرخهٔ بعد موکول می‌شود | `codal_pipeline.py:1288-1293` |
| `fts_results` ستونِ `updated_at` ندارد؛ فقط ۲۶ ستونِ ارزش | `fts_engine.py:272-279` |
| باطل‌سازیِ مادی‌شده فقط داخلِ `recompute_dirty` انجام می‌شود | `codal_pipeline.py:415-472` |
| کشف افزایشی با `pipeline_cursor` و floorِ محافظه‌کارانه وجود دارد | `codal_fetcher.py:2889`؛ `codal_pipeline.py:557` (`watermarks`) |
| صف با claim/lease/retry و backoff نمایی وجود دارد | `codal_pipeline.py:72-78`، `claim`، `mark_failed` |
| نقشهٔ وابستگیِ شاخص‌ها به منبع | `codal_pipeline.py:355` (`AXES_BY_SOURCE`) |
| علامت‌گذاری dirty به‌ازایِ نماد/شاخص | `codal_pipeline.py:366` (`dirty_mark`) |
| پردازش دسته‌ای و materialize فقط نمادهای dirty | `codal_pipeline.py:965` (`run_cycle`)، `:415` (`recompute_dirty`) |
| خط شبانهٔ staging-first با Task Scheduler ۱۸:۳۰ | `app.py:439`؛ `dev/codal_auto_update.py:312` (`run`) |
| قفلِ خط شبانه = `codal_auto.lock` (۶ ساعت کهنگی) | `api/_sync_codal.py:120-135` |
| worker افزایشی این قفل را نمی‌بیند | در `codal_pipeline.py` ارجاعی به `codal_auto.lock` نیست |
| گیت‌های اعتبارسنجیِ staging وجود دارند | `codal_validation.py:506` (`validate_staging`) |
| دکمهٔ دستیِ FTS با ADB rotate | `api/_sync_codal.py:65` (`/api/sync/codal/fts-refresh`) |
| کارتِ v2 هیچ فیلد تازگی/منشأ ندارد | `frontend-v2/src/features/fundamental/api/useFtsCard.ts` |

نتیجه: «چیزی بهتر» یعنی **کادنسِ تطبیقی + باطل‌سازیِ فوری + قفلِ مشترک + نمایشِ تازگی**، نه بازنویسیِ خزنده.

---

## ۲. هدف و غیرهدف

### هدف

1. **SLA تازگی:** در پنجرهٔ انتشار، p95 فاصلهٔ «انتشار اطلاعیه در کدال» تا «قابل‌خواندن‌شدن مقدار تازه در کارت/اسکرینر» ≤ ۱۵ دقیقه؛ بیرون پنجره ≤ ۳ ساعت.
2. **صفر جاافتادنِ بی‌صدا:** هر اطلاعیهٔ دسته‌های ۱ و ۳ که به فید می‌رسد، در چرخهٔ بعدِ پولر (≤ ۱۰ دقیقه) در صف دیده شود، مگر در حالتِ breaker که `gap_flag` صریحاً اعلام می‌شود و پاسِ عمیق جبران می‌کند.
3. **صفر ردیفِ کهنه در بازارِ باز:** به‌محضِ نوشتنِ ردیفِ تازه، ردیفِ مادی‌شدهٔ همان نماد باطل شود؛ محاسبهٔ سنگین می‌تواند به بعد موکول شود، اما خواندنِ کهنه نه.
4. **شفافیت:** برای هر نماد و هر شاخص، `as_of`، منبع (`tracing_no`/دورهٔ گزارش)، و وضعیت `fresh/stale/missing/quarantined` در API و کارت.
5. **تک‌نویسنده:** worker افزایشی و orchestrator شبانه هرگز هم‌زمان روی `market.db` نمی‌نویسند.

### غیرهدف

- اولویت‌دهیِ صف بر اساس watchlist/پرتفوی (فاز ۲؛ نیازمند اتصال `user.db`).
- تغییرِ بازهٔ snapshot یا انتشار GitHub.
- استفادهٔ پیش‌فرض از ADB در worker (فقط خزندهٔ دستی).
- تازگیِ زیرِ یک دقیقه یا streaming.
- تغییر فرمول/آستانهٔ ۵ شاخص یا قرارداد کارت به‌جز افزودن بلوک `freshness`.

---

## ۳. تعریف‌ها

- **پنجرهٔ انتشار:** بازه(های) ساعتیِ روز که بیشترین اطلاعیه‌های دسته‌های ۱ و ۳ در آن‌ها منتشر می‌شوند؛ از تاریخِ خودِ `codal_notices` یاد گرفته می‌شود، نه حدس.
- **فاصلهٔ شبکه (`network_gap_s`):** حداقل فاصلهٔ دو پاسِ کشفِ فید. داخلِ پنجره ۶۰۰ ثانیه، بیرون ۳ ساعت.
- **نمادِ dirty:** نمادی که دست‌کم یک شاخصش به‌خاطرِ منبعِ تازه باطل شده و باید بازمحاسبه شود (`pipeline_dirty`).
- **quarantined:** ردیفِ استخراج‌شده‌ای که گیتِ اعتبارسنجی را رد کرده، در main نوشته نشده، و از retry خودکار خارج است تا مداخلهٔ انسانی.
- **as_of:** زمانِ انتشار/دورهٔ آخرین منبعِ معتبرِ همان شاخص (نه زمانِ اجرای برنامه).
- **fresh:** منبعِ canonical وجود دارد، در `pipeline_dirty` نیست، و ردیفِ مادی‌شده/خواندنی از آن ساخته شده است.
- **stale:** منبعِ canonical تازه‌تر از ردیفِ مادی است یا نماد در `pipeline_dirty` است.
- **missing:** هیچ منبعِ canonical برای آن شاخص وجود ندارد (نه کهنگی؛ نبودِ داده).
- **overdue (فاز ۲):** دورهٔ موردانتظار طبق کادنسِ تاریخیِ همان نماد نرسیده و از p90 تأخیرِ تاریخی گذشته است. در فاز ۱ ساخته نمی‌شود.

---

## ۴. طراحی

### ۴.۱. کادنسِ تطبیقیِ پنجرهٔ انتشار

**مدلِ پنجره (تابع خالص + I/O جدا):**

```
publication_windows(conn, now, lookback_days=120, min_samples=200)
  → {"windows": [("08:30","13:30"), ("15:00","19:30")],
     "source": "learned"|"default",
     "samples": int}
```

- ورودی: `codal_notices.publish_date` و `sent_date` (پس از نرمال‌سازیِ ارقامِ فارسی/عربی، همان `_norm_date`).
- هیستوگرامِ ساعت به‌تفکیکِ دسته (۱ و ۳) و روزِ هفته؛ میانگین متحرکِ ۳ ساعته برای هموارسازی.
- پنجره = ساعت‌های پیوسته‌ای که سهمشان ≥ ۲۵٪ اوج است؛ حاشیهٔ ±۳۰ دقیقه؛ ادغامِ پنجره‌هایی که فاصله‌شان < ۲ ساعت است.
- اگر نمونهٔ کافی نبود (`< min_samples`): پیش‌فرضِ محافظه‌کارانهٔ `08:00–20:00` با `source="default"`.
- نتیجه در `pipeline_cursor` با کلید `pub_windows_v1` و تاریخِ محاسبه کش می‌شود؛ حداکثر یک‌بار در روز بازمحاسبه.

**تابع فاصله:**

```
network_gap_s(now, windows, enabled=True, fast=600, slow=3*3600)
  → fast داخلِ پنجره، slow بیرون، +jitter یکنواختِ ±۶۰ ثانیه
```

- `worker_once` پارامترِ جدید `network_gap_s=None` می‌گیرد؛ اگر None باشد خودش از مدل می‌سازد.
- `want = age_net is None or age_net >= gap` (همان شرطِ فعلی، با gapِ پویا).
- `next_wakeup` همان gap را می‌گیرد تا خوابِ نخ هم تطبیقی شود؛ `CADENCE_MIN_S=60` دست‌نخورده می‌ماند.
- بودجهٔ هر پاس: حداکثر ۲ صفحه برای هر دسته (`discover_auto(max_pages=2)`؛ پاسِ عمیق پس از پاسِ ناقص ۳ صفحه: `DEEP_PAGES_PER_CAT=3`). تخمین: ۴ صفحه/پاس × ۷۲ پاسِ پنجرهٔ ۱۲ساعته = ۲۸۸ + حاشیهٔ بیرونِ پنجره ≈ ۳۲۰ درخواست/روز. سقف سخت: ۴۰۰ درخواست/روز با شمارندهٔ روزانه در `pipeline_cursor` (حکمِ اجرایی ۲۰۲۶-۱۱-۰۳؛ عددِ قبلی ۲۰۰ کشف را ۲.۵–۴ ساعت پیش از پایانِ پنجره می‌بست).
- محیط: `BORS_CODAL_FAST_WINDOW=1` (پیش‌فرض در بیلد frozen روشن؛ در سورس/تست تابعِ همان `BORS_NO_FETCH_LOOPS` حاکم است). خاموش = رفتار امروز (۳ ساعت).

### ۴.۲. پردازش، اعتبارسنجی و مادی‌سازی

**صف و retry:** بدون تغییرِ ساختار. `budget=8`، `MAX_ATTEMPTS=4`، `BACKOFF_S=(0,120,900,3600,21600)`.

**گیتِ ردیفی (جدید):**

- از `codal_validation.py` یک تابعِ خالصِ `validate_extracted_row(table, row)` استخراج می‌شود که همان چهار بررسیِ ردیفی را دارد: منفی‌نبودنِ درآمد/فروش، `gross_profit ≤ revenue`، دورهٔ آینده، و provenance (حداقل یکی از `url`/`pdf_url`/`excel_url`).
- در `process_claimed` **قبل از commit** صدا زده می‌شود. شکست → هیچ نوشتنی در جدولِ مقصد؛ `codal_extracted.state='quarantined'`، `last_error` با کدِ گیت.
- `counts()` حالتِ `quarantined` را جدا می‌شمارد؛ `claim()` آن را برنمی‌دارد (خارج از retry).
- سطحِ staging و گیت‌های سراسری شبانه دست‌نخورده می‌مانند.

**باطل‌سازیِ فوری (جدید):**

- خروجیِ موجودِ `symbols` در tallyِ `process_claimed` (که امروز هم پر می‌شود) مبنای نمادهای touch‌شده است؛ فیلدِ تازه‌ای به قراردادِ صف اضافه نمی‌شود.
- در `run_cycle`، بلافاصله پس از پردازش و مستقل از بازبودنِ بازار:
  - `_invalidate_materialized(conn, touched_symbols)` (حذفِ ردیفِ همان نمادها از `fts_results`).
  - `invalidate_screener_cache(drop_materialized=False)` یک‌بار در هر چرخه (debounce طبیعیِ چرخه).
- حالتِ `recalc="invalidate"` به `run_cycle` اضافه می‌شود: در بازارِ باز، فقط باطل‌سازی انجام می‌شود و `recompute_dirty` (پیش‌محاسبهٔ سنگین) به چرخهٔ بعد موکول می‌شود. `pipeline_dirty` پاک نمی‌شود تا محاسبه گم نشود.
- بیرونِ بازار، رفتارِ امروز: `recompute_dirty` با سقفِ `RECALC_BATCH=80`.

نتیجه: در بازارِ باز، خواننده به‌جای ردیفِ کهنه، مسیرِ fallback زندهٔ `evaluate_v10` را می‌رود (کندتر ولی تازه)؛ اسکرینر/قیف کشِ کهنه نشان نمی‌دهند.

### ۴.۳. تازگی و منشأ

بدونِ جدولِ جدید (برای جلوگیری از گسترشِ سطحِ parity با Go)، تازگی از canonical مشتق می‌شود:

| شاخص | منبعِ as_of | دوره |
|---|---|---|
| ۱ رشد فروش | `monthly_sales` + join به `codal_notices` برای `publish_date` | `period_end` |
| ۲ روند EPS | `financial_statements` (حسابرسی‌شدهٔ غیرتلفیقی) | `period_end` |
| ۳ حاشیهٔ سود | همان FS | `period_end` |
| ۴ فروش÷ارزش بازار | آخرین `monthly_sales` + `market_watch.d_even` | `period_end` + روزِ تابلو |
| ۵ فیلتر صنعت | `instruments`/سکتور در آخرین همگام‌سازی | روزِ تابلو |

**قرارداد:**

```json
{
  "symbol": "فولاد",
  "as_of": "2026-11-03T12:10:00+03:30",
  "axes": {
    "1_growth":   {"as_of": "2026-10-28", "source": "monthly_sales",
                   "tracing_no": 123456, "period_end": "1405/06/31",
                   "state": "fresh", "reason": ""},
    "2_eps_trend": {"as_of": "2026-09-20", "source": "financial_statements",
                   "tracing_no": 120001, "period_end": "1404/12/29",
                   "state": "fresh", "reason": ""},
    "3_gross_margin": {"as_of": "2026-09-20", "source": "financial_statements",
                   "tracing_no": 120001, "period_end": "1404/12/29",
                   "state": "fresh", "reason": ""},
    "4_sales_to_mcap": {"as_of": "2026-11-03", "source": "monthly_sales+market_watch",
                   "tracing_no": 123456, "period_end": "1405/06/31",
                   "state": "fresh", "reason": ""},
    "5_industry": {"as_of": "2026-11-03", "source": "instruments",
                   "state": "fresh", "reason": ""}
  }
}
```

- `state` در فاز ۱: `fresh` / `stale` (در `pipeline_dirty` یا منبع جدیدتر از مادی) / `missing` / `quarantined` (آخرین تلاش رد شد؛ `reason` کدِ گیت).
- `as_of` تاریخِ میلادیِ نرمال‌شده است: تاریخِ فقط-روز به‌صورت `YYYY-MM-DD` و برچسبِ زمان‌دار به‌صورت ISO-8601 با منطقهٔ تهران `YYYY-MM-DDTHH:MM:SS+03:30` (حکمِ اجرایی ۲۰۲۶-۱۱-۰۳)؛ تاریخِ شمسی فقط در `period_end` می‌آید.
- `as_of` سطحِ کارت (فیلدِ بالایی) = **قدیمی‌ترین** `as_of` محورهای ۱/۲/۳ (سنِ دادهٔ بنیادی، هم‌راستا با حکمِ نشان)؛ محورهای ۴/۵ آن را به سمتِ تابلو جابه‌جا نمی‌کنند.
- `GET /api/fundamental/freshness` (دسته‌ای؛ کش ۶۰ ثانیه) و افزودن بلوک `freshness` به پاسخِ `/api/fundamental/{symbol}`. این route باید **پیش از** مسیرِ پویای `/{symbol}` در `api/fundamental.py` ثبت شود، وگرنه «freshness» به‌عنوان نماد گرفته می‌شود.
- کارت v2: نشانِ «تازه تا HH:MM» با tooltipِ شاخص‌های stale؛ اگر `missing` بود، نشان ساخته نشود (تازگیِ جعلی ممنوع).

### ۴.۴. قفل و هم‌زیستی با خط شبانه

- **قفلِ چرخه:** `pipeline_lock` (heartbeat، TTL=۱۸۰s) مثلِ امروز.
- **قفلِ خط شبانه:** `codal_auto.lock` (۶ ساعت کهنگی) مثلِ امروز.
- **تغییر ۱ — worker:** در `worker_once`، پیش از هر پاسِ شبکه/نوشتن، اگر `codal_auto.lock` تازه است (mtime < ۶ ساعت) یا `codal_auto_status.json` مرحلهٔ غیرِپایانیِ تازه دارد → `skipped="orchestrator-busy"` و بیدارباشِ ۵ دقیقه؛ هیچ نوشتنی نمی‌کند.
- **تغییر ۲ — orchestrator:** پیش از کپیِ staging (نه فقط پیش از merge)، منتظرِ آزادشدنِ `pipeline_lock` می‌ماند (خواندنِ `lock_state` از main؛ انتظار حداکثر ۲ دقیقه، سپس fail-closed با `locked`). بعد از گرفتنِ `codal_auto.lock` این کار انجام می‌شود تا worker تازه دیگر شروع نکند.
- نتیجه: کپیِ staging هرگز با نوشتنِ افزایشی هم‌زمان نیست؛ گیتِ «پس‌رفتِ دوره» در `codal_validation` ردیفِ تازه‌ترِ main را به‌عنوانِ رگرسیونِ staging نمی‌بیند.
- قفلِ سوم ساخته نمی‌شود؛ همان دو قفل با ترتیبِ روشن.

### ۴.۵. شبکه، خطا و circuit breaker

- `discover_notices` امروز `blocked`/`incomplete`/`floors` را برمی‌گرداند و نشانک را فقط برای دستهٔ کامل جلو می‌برد؛ همان حفظ می‌شود.
- **breaker:** اگر `blocked=True` یا سه پاسِ پیاپی `incomplete=True` بود (`notice_incomplete_streak >= 3`): فاصلهٔ **پایه** (بی‌jitter) تشدید می‌شود به `min(3h, max(30m, base × 2^min(streak−2, 6)))`؛ jitter پس از آن می‌نشیند. پاسِ کامل شمارنده و `gap_flag` را صفر می‌کند و کادنس به ۶۰۰ ثانیه برمی‌گردد. رخداد در `pipeline_runs`/status با `gap_flag` ثبت می‌شود.
- **پاسِ عمیق:** پرچمِ `notice_deep_pass` در `pipeline_cursor` رویِ پاسِ `incomplete`/`blocked` روشن می‌شود و پاسِ بعدی با `DEEP_PAGES_PER_CAT=3` (به‌جای ۲) اجرا می‌شود؛ پاسِ کامل پرچم را پاک می‌کند.
- **jitter** و `POLITE` دست‌نخورده؛ ADB در worker استفاده نمی‌شود.
- **سقف روزانه:** شمارندهٔ `daily_requests` در `pipeline_cursor`؛ عبور از ۴۰۰ → توقف پاسِ شبکه تا نیمه‌شبِ بعد، با وضعیتِ `budget-exhausted` (نه شکستِ خاموش).
- **آزادسازیِ قرنطینه:** `release_quarantine(conn, tracing_nos=None, reason="operator")` ردیف‌هایِ `quarantined` را به `queued` با `error_kind='requeued'` برمی‌گرداند؛ دريچهٔ CLI: `python codal_pipeline.py --release-quarantine [--tracing-no N ...]` (بی‌شبکه، فقط UPDATE محلی).

### ۴.۶. مشاهده‌پذیری

`worker_status`/`health` (و در صورت نبودِ route، `GET /api/codal/pipeline/status`) این فیلدها را اضافه می‌کند:

```json
{
  "publication": {"windows": ["08:30-13:30","15:00-19:30"],
                  "source": "learned", "samples": 4210,
                  "network_gap_s": 600, "inside_window": true},
  "last_network_pass_at": "2026-11-03 12:01:11",
  "last_new_notice_at": "2026-11-03 12:07:40",
  "last_discovered_tracing_no": 918273,
  "gap_flag": false,
  "incomplete_streak": 0,
  "queue": {"queued": 3, "running": 1, "failed": 0, "quarantined": 0},
  "freshness": {"fresh": 1420, "stale": 34, "missing": 61, "quarantined": 2},
  "daily_requests": 87
}
```

- شمارشِ freshness با یک کوئریِ تجمیعی (نه ۵ کوئری به‌ازایِ هر نماد) و کشِ کوتاه.
- UI: نشانِ تازگی روی کارت + یک خط در تنظیمات/وضعیت: «پنجرهٔ انتشار امروز: …؛ آخرین کشف: …؛ صف: …».

---

## ۵. تغییرات فایل‌به‌فایل

| فایل | تغییر |
|---|---|
| `codal_pipeline.py` | `PUBLICATION_*` constants؛ `publication_windows()`؛ `network_gap_s()`؛ پارامترِ `network_gap_s` در `worker_once` و `next_wakeup`؛ `recalc="invalidate"` در `run_cycle`؛ مصرفِ `symbols`ِ موجود در tallyِ `process_claimed` برای باطل‌سازیِ فوری؛ `quarantined` در `counts`/`claim`؛ گیتِ `orchestrator-busy`؛ فیلدهای status |
| `codal_fetcher.py` | انتقال/پذیرشِ `max_pages` در `discover_auto` برای پاسِ عمیق؛ بدونِ تغییرِ پارسر |
| `codal_validation.py` | استخراجِ `validate_extracted_row()` خالص از بررسی‌های ردیفیِ موجود |
| `dev/codal_auto_update.py` | انتظار برای آزادشدنِ `pipeline_lock` پیش از کپیِ staging؛ ثبتِ `pipeline_lock_wait` در status |
| `api/fundamental.py` | `freshness_of()` (تک‌نماد) و `freshness_bulk()`؛ افزودن `freshness` به کارت؛ route دسته‌ای |
| `api/_sync_codal.py` | بدونِ تغییرِ رفتار؛ فقط استفاده از همان وضعیتِ مشترک در صورت نیاز |
| `frontend-v2/src/features/fundamental/api/useFtsCard.ts` | افزودنِ `freshness` به schema (loose) |
| `frontend-v2/src/features/fundamental/ui/FundamentalCards.tsx` | نشانِ «تازه تا …» + tooltipِ شاخص‌های stale/missing |
| `dev/test_codal_event_update.py` (جدید) | آزمون‌های واحد و فیکسچریِ زیر |
| `dev/test_codal_auto_update_v11.py` | افزودنِ سناریوی قفلِ متقابل و انتظارِ staging |

---

## ۶. آزمون‌ها

### واحد (آفلاین، `:memory:` یا فیکسچر)

1. `publication_windows`: نمونهٔ مصنوعی با دو قله → دو پنجره؛ نمونهٔ کم → پیش‌فرض؛ ارقامِ فارسی/عربی؛ تعطیلات/آخر هفته؛ حاشیه و ادغام.
2. `network_gap_s`: داخل/بیرون پنجره؛ `enabled=False` → ۳ ساعت؛ jitter در بازه؛ نبودِ `last_network` → فوری.
3. `next_wakeup`: داخل پنجره `seconds ≤ 600`؛ بیرون `~3h`؛ queue/retry بر پنجره مقدم است.
4. `recalc="invalidate"`: ردیفِ `fts_results` همان نماد حذف می‌شود، `pipeline_dirty` باقی می‌ماند، و `evaluate_v10` مسیرِ fallback را می‌دهد.
5. `quarantined`: درآمدِ منفی/`gross>revenue`/دورهٔ آینده/بی‌provenance → صفر نوشتن در جدولِ مقصد، state درست، `claim` برنمی‌دارد.
6. قفلِ متقابل: `codal_auto.lock` تازه → `skipped="orchestrator-busy"`؛ قفلِ کهنهٔ ۷ ساعته → اجرا می‌شود.
7. `freshness_of`: کارتِ کامل/بی‌داده/quarantined؛ ۵ محور با `as_of` درست؛ `missing` هرگز `fresh` نمی‌شود.

### یکپارچه (آفلاین، fetch تزریقی)

- فیدِ ساختگی با یک اطلاعیهٔ تازه → صف → scrape ساختگی → ردیف در canonical → dirty → باطل‌سازیِ فوری → (بیرونِ بازار) بازمحاسبه؛ هیچ درخواستِ واقعی.
- فیدِ تکراری → هیچ صف/نوشتن/باطل‌سازی.
- `incomplete=True` → نشانک جلو نمی‌رود؛ پاسِ بعدی `max_pages=3`؛ `gap_flag` ثبت.
- breaker: سه `blocked` پیاپی → gap افزایشی و سپس بازگشت.

### زنده (opt-in، `BORS_CODAL_LIVE_GATE=1`)

- یک پاسِ واقعی بیرونِ بازار: «هیچ اطلاعیهٔ تازه = صفر نوشتن»؛ شمارش درخواست ≤ بودجه.
- یک اطلاعیهٔ واقعیِ شناخته‌شده end-to-end؛ اندازه‌گیریِ فاصلهٔ `publish_date` تا قابل‌خواندن‌شدن.
- هیچ‌گاه در بازارِ باز و بدونِ هماهنگیِ مالک اجرا نمی‌شود.

### رگرسیون

- `dev/codal_scheduler_v1103.py` (گاردِ زمان‌بندی)
- `dev/test_codal_auto_update_v11.py` (staging-first)
- `dev/test_codal_discovery_v1101.py` (watermark)
- B0–B4 و سوئیت‌های FTS/RA365 سبز بمانند.

---

## ۷. عرضهٔ مرحله‌ای

1. **سایه (۱ روز):** فقط محاسبه و لاگِ `publication_windows`/`network_gap_s` و `incomplete`؛ رفتارِ شبکه تغییر نمی‌کند. صحتِ پنجره و بودجه سنجیده می‌شود.
2. **باطل‌سازیِ فوری:** بدونِ تغییرِ کادنس؛ ردیفِ کهنه در بازارِ باز حذف می‌شود. این کم‌ریسک‌ترین بخش و مستقل از شبکه است.
3. **کادنسِ تطبیقی** پشتِ `BORS_CODAL_FAST_WINDOW=1`؛ پایشِ ۴۲۹/صف/quarantine.
4. **پیش‌فرض روشن** در بیلد frozen؛ سورس با همان دروازه‌های موجود.
5. **freshness API + نشانِ کارت.**
6. **پورت Go** هنگام انتقال `sync`؛ تا آن زمان پایتون مرجع است.

---

## ۸. معیارهای موفقیت

| معیار | هدف | روش سنجش |
|---|---|---|
| p95 تأخیر انتشار→خواندن در پنجره | ≤ ۱۵ دقیقه (صف < ۵۰ و بدون breaker) | `publish_date` تا `pipeline_runs.done` + `fts_results`/fallback |
| p95 بیرونِ پنجره | ≤ ۳ ساعت | همان |
| اطلاعیهٔ جاافتادهٔ بی‌صدا | صفر | هر `tracing_no` تازه در چرخهٔ بعد (≤ ۱۰ دقیقه) در صف؛ شکاف = `gap_flag` |
| ردیفِ کهنهٔ مادی در بازارِ باز | صفر | `pipeline_dirty` ∩ `fts_results` بعد از چرخه |
| درخواست روزانه | ≤ ۴۰۰ | شمارندهٔ `daily_requests` |
| نرخ ۴۲۹ | < ۱٪ | `pipeline_runs`/status |
| نوشتنِ هم‌زمان | صفر | آزمونِ قفل + لاگِ `orchestrator-busy` |

---

## ۹. ریسک‌ها و کاهش

- **WAF/۴۲۹ کدال:** breaker + بودجه + jitter؛ ADB خارج از worker؛ بازگشت خودکار به کادنسِ کند.
- **بیش‌برازشِ پنجره:** حداقلِ نمونه، هموارسازی، پیش‌فرضِ محافظه‌کارانه، بازمحاسبهٔ روزانه.
- **اختلاف ساعت/تاریخ:** نرمال‌سازیِ ارقامِ فارسی/عربی (`_norm_date`)، مقایسهٔ عددی، منطقهٔ زمانیِ تهران؛ فرضِ DST ساخته نمی‌شود.
- **نوشتنِ هم‌زمان:** دو قفل با ترتیبِ روشن + آزمونِ رگرسیون؛ قفلِ سوم ساخته نمی‌شود.
- **محاسبهٔ سنگین در بازار:** فقط باطل‌سازی؛ پیش‌محاسبه به بعد؛ سقفِ ۸۰ نماد در چرخه.
- **کارتِ گمراه‌کننده:** `missing` هرگز `fresh` نمایش داده نمی‌شود؛ `as_of` از منبع، نه از زمانِ اجرا.
- **پورت Go:** افزودنِ هیچ جدولِ تازه‌ای به `market.db` در فاز ۱ (freshness مشتق است) تا سطحِ parity گسترش نیابد.

---

## ۱۰. پرسش‌های باز (غیرِمسدودکننده)

1. `overdue` (کادنسِ تاریخیِ هر نماد) در فاز ۲ بیاید یا همین فاز ۱؟ پیشنهاد: فاز ۲، چون نیازمند مدلِ p90 تأخیر و آزمونِ کافی است.
2. اولویتِ watchlist در فاز ۲ با اتصالِ `user.db`؛ تا آن زمان ترتیبِ canonical صف حفظ می‌شود.
3. آیا `GET /api/fundamental/freshness` باید در قیف/اسکرینر هم مصرف شود یا فعلاً فقط کارت؟ پیشنهاد: کارت + وضعیت؛ مصرف در قیف فاز بعد.

---

## Implementation rulings (2026-11-03)

حکم‌هایِ اجراییِ نهایی که بر متنِ بالا مقدم‌اند (پس از بازبینیِ کلِ شاخه):

- **بودجه/صفحه (C1):** `DAILY_REQUEST_CAP=400`؛ `PAGES_PER_CAT=2` و `DEEP_PAGES_PER_CAT=3` (پرچمِ `notice_deep_pass` در `pipeline_cursor`). ۱۲ساعت × ۷۲ پاس × ۴ صفحه + حاشیه ≤ ۴۰۰.
- **Breaker (I1):** با `notice_incomplete_streak >= 3` فاصلهٔ پایه `min(3h, max(30m, base × 2^min(streak−2, 6)))` می‌شود (jitter پس از آن)؛ پاسِ کامل به ۶۰۰ثانیه برمی‌گردد و پرچمِ پاسِ عمیق را پاک می‌کند.
- **آزادسازیِ قرنطینه (I2):** `release_quarantine()` + CLI `--release-quarantine [--tracing-no N ...]`؛ خروجی `queued` با `error_kind='requeued'`، بی‌شبکه.
- **`as_of` ISO (M1):** زمان‌دار `YYYY-MM-DDTHH:MM:SS+03:30`، فقط-روز `YYYY-MM-DD`. `as_of` کارت = قدیمی‌ترین محورهای ۱/۲/۳.
- **نشانِ تازگی:** سنِ نشان از محورهای ۱/۲/۳ (بنیادی) خوانده می‌شود، نه از بیشینهٔ محورهای تابلو.
- **سلامت read-only:** `health()`/`--status` هیچ کش/checkpoint نمی‌نویسد (شاملِ `pub_windows_v1`).
- **کش‌ها:** freshness دسته‌ای TTL=۶۰ثانیه (process-local، کلید تاپلِ مرتب‌شدهٔ نمادها)؛ dropِ payload اسکرینر debounce=۳۰۰ثانیه در `pipeline_cursor` — باطل‌سازیِ `fts_results` بی‌تأخیر.
