# B4 Task 3b — fan-outِ کارتِ پنج‌محور (برنامۀ موازی)

پلنِ مادر: `2026-10-31-backend-b4-fundamental.md` · لجر: `.superpowers/sdd/2026-11-01-backend-b4-fundamental/progress.md`
داورِ نهایی درِ همهٔ شاخه‌ها یکی است: **طلایی‌هایِ اوراکلِ پایتون** (`internal/fundamental/testdata/golden/s1|s2|s3`)
با `parity.Compare` رویِ همان فیکسچرِ یخ‌زده. هیچ شاخه‌ای با «درست به‌نظر رسیدن» بسته نمی‌شود.

## چرا می‌شود موازی‌کار کرد
پنج‌محور یک درختِ وابستگیِ لایه‌لایه است، نه یک حلقۀ تو‌در‌تو:

```
config (آستانه‌ها) ─┬─ series (ماهانہ) ──────┬─ axes1 (۱الف/۱ب) ─┐
statements (سالانہ)─┤                        ├─ axes2 (EPS)      ├─ evaluate ─ insights ─ card
                    └─ margin (۳) ─ axes4(۴) ┘                  │
sector/industry (۵) ─ risk_gates ───────────────────────────────┘
```

هر لایه فقط خروجیِ لایۀ بالادستِ خود را می‌خواند و هیچ حالتِ تازه‌ای اختراع نمی‌کند
(§۱۵ بند ۲: پاریتِ bug-for-bug؛ رأی‌ها و آستانه‌ها حکمِ مالک است، نه پیشنهادِ من).

## مالکیتِ فایل (تعارضِ نوشتن ممنوع)
| شاخه | فایل‌هایِ تازه در `backend-go/internal/fundamental/` | مرجعِ پایتون |
| --- | --- | --- |
| A config | `config.go`, `config_test.go` | `api/fundamental.py:75-152` · `api/market.py:35-80` · `bors_config.py:779-860` |
| B series | `series.go`, `series_test.go` | `fts_engine.py:1068-1186` · `api/fundamental.py:446-533` |
| C statements | `statements.go`, `statements_test.go` | `fts_engine.py:709-800,801-873,1002-1067,570-600` · `codal_units.py` |
| D axes 1 | `axis1.go`, `axis1_test.go` | `api/fundamental.py:542-752` |
| E axes 2/3 | `axis23.go`, `axis23_test.go` | `fts_engine.py:1285-1568` · `api/fundamental.py:757-960` |
| F axes 4/5 + gates | `axis45.go`, `gates.go`, `axis45_test.go` | `fts_engine.py:1569-1650,1757-2250` · `api/fundamental.py:968-1220` |
| G orchestration | `evaluate.go`, `insights.go`, `card.go`, `card_test.go`, `handlers.go`, `routes.go` | `api/fundamental.py:1226-1860,2003-2215` |

مالکیتِ `reference.go` / `text.go` / `service.go` درِ این دور **قفل** است (دورِ اصلاحِ
بازبینی رویِ همان‌ها در حال کار است). هر شاخه فقط از تابع‌هایِ صادرشدهٔ آن‌ها
استفاده می‌کند و اگر چیزی کم دارد درِ فایلِ خودش تعریف می‌کند، نه درِ فایلِ مشترک.

## داورِ هر شاخه (633 وکتور، شش‌صد‌وسِ‌سی‌و‌سه مورد، از خودِ پایتون)
`tools/parity/gen_fundamental_vectors.py` + `gen_fundamental_layer_vectors.py`
→ `testdata/vectors/*.json` · تازگی‌شان را `dev/test_fundamental_vectors_b4.py`
می‌پاید (تولیدِ دوباره + مقایسهٔ بایتی + کنترلِ منفی).

| فایلِ وکتور | مورد | شاخه‌ای که می‌پاید |
| --- | --- | --- |
| `thresholds.json` | ۲۰ | A (ترتیبِ پراب، صفرِ تورم، رشته‌هایِ بی‌عدد) |
| `config.json` | ۱۸ | A (پاک‌سازیِ نوع، boundها، مهاجرتِ نسل‌قدیم) |
| `series.json` | ۱۳ | B (`_dedupe_ym`، `ytd_denominator`) |
| `profile.json` / `entity.json` | ۱۷ / ۱۴ | B/C (طبقه، دامنۀ شرکت) |
| `sector.json` | ۹ | F (رژیم قیمت‌گذاری + استثنای دارو/بانک) |
| `statements.json` | ۶۵ | C (`annual_statements`، `reference_annual`، `gross_margin`، `quarter_reference_rows` با پنج سقف) |
| `indicators.json` | ۶۵ | D/E (`ind1a`، `ind1b`، `axis1`، `eps_ladder`، `eps_assessment`، `ind2`، `states`) |
| `annualize.json` | ۲۰ | F (`annualized_sales`، `ind4_exempt`) |
| `valuation.json` | ۲۸۰ | F (شبکهٔ `ind4_valuation`: تهی/صفر/معاف/بی‌ارزش‌بازار) |
| `text.json` | ۱۰۰ | G (`_n` هزارگان، `_pct_txt`، `_fa`، `_state`، `_eps_cells/_eps_row`، `_ms_series`) |

هیچ عددی درِ آزمون‌هایِ Go دست‌نویس نمی‌شود؛ آزمون فقط وکتور را می‌خواند. جایی که
فیکسچر شاخه‌ای را نمی‌سازد (مثلِ `months_source="unknown"` یا boundِ ساعت‌شنی)
وکتورِ تازه اضافه می‌شود، نه انتظارِ دستِ انسانی.

## قراردادِ مشترکِ کمک‌تابع‌ها (درِ `helpers.go` و `text.go` تثبیت شده)
`toF` (float امن، NaN⇒0.0) · `numOrNil` (عدد یا nil — «داده نیست» هیچ‌وقت ۰.۰ نمی‌شود) ·
`rialsOrNil` · `falsy` · `pyStr` · `round1..4` (نیم‌به‌زوجِ پایتون) · `faDigits`/`nGroup`
(هزارگان) · `pctText` (`%+.1f` / `%.1f` + ٪) · `stateTri` (سه‌حالۀ pass/fail/na/nodata).
هر شاخه که اینها را لازم دارد **باید** از همین‌ها بخورد؛ تعریفِ دومِ `toF` درِ دو فایل
ممنوع (تعارضِ کامپایل نمی‌دهد ولی دو معنا می‌سازد — همان بلیّت که `codal_periods` را ساخت).

## قاعدۀ سه‌گانۀ هر شاخه
1. **آستانه و رأی دست‌نخورده:** هیچ عددِ تازه‌ای نوشته نمی‌شود؛ هر عدد از فایلِ
   پیکربندی یا از `FTS_V10_DEFAULTS` می‌آید با همان ترتیبِ پراب
   (`v10_<k>` ← کلیدِ پنل ← پیش‌فرض؛ `monetary_growth_min` پرابِ `v10_` ندارد).
2. **null ≠ 0 ≠ false:** سه تبدیلِ متفاوت درِ سه جای متفاوت می‌ماند.
3. **ردیف حذف نمی‌شود:** شاخه‌هایِ انتخابِ مرجع فقط «برنده» را عوض می‌کنند.

## دروازهٔ پذیرشِ هر شاخه
- `go test ./internal/fundamental/ -run <نامِ شاخه> -count=1` سبز با وکتورهایِ نام‌دار
  که **خودِ پایتون** ساخته (اسکریپتِ `tools/parity/gen_fundamental_golden.py` گسترش
  می‌یابد تا هر لایه وکتورِ جدا داشته باشد، نه فقط پیلودِ نهایی).
- یک کنترلِ منفیِ ثبت‌شده: شاخه را خراب کن، آزمون باید قرمز شود.
- چیزی که با فیکسچرِ فعلی قابلِ ساختن نیست صریح «راستی‌آزمایی نشده» می‌خورد.

## ترتیبِ اجرا
۰) دورِ اصلاحِ بازبینیِ B4a بسته و کامیت شود (درخت تمیز).
۱) A+B+C موازی (هیچ‌کدام به دیگری نیاز ندارد).
۲) D+E+F موازی (ورودی‌شان از ۱ می‌آید).
۳) G (هم‌خوانیِ کلِ پیلود با ۱۳ طلایی) + ثبتِ مسیر `{symbol}` و بازگشتِ پنج کیسِ
   `declared` به مقایسه.
۴) گیتِ کاملِ B4 + گزارش + لجر + پوش.
