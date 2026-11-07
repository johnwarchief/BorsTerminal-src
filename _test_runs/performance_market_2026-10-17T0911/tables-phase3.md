### ۳الف) باتریِ کامل — فرمان، شمار، خروج

```
python dev/run_all_tests.py          # بدونِ فیلتر، ۱۶:۲۸:۴۹ → ۱۶:۵۴:۳۵ (≈۲۵ دقیقه ۴۶ ثانیه)
EXIT=1
```

| نتیجه | شمار |
|---|---:|
| سوئیتِ سبز | ۱۲۰ |
| سوئیتِ قرمز | ۳ |
| جمعِ سوئیت‌ها | ۱۲۳ |

سه قرمز (`phase3-run_all_tests.log`):

| سوئیت | rc | شمارشِ درونِ سوئیت |
|---|---:|---|
| `Phase4 engine: per-type factor formulas (hand-checkable), missing/inva…` | ۱ | `38/39` |
| `R1/R2 housekeeping: dedupe + prev-year backfill` | ۱ | `0 pass / 1 fail` |
| `single writer: one backend per market.db` | ۱ | `0 pass / 1 fail` |

### ۳ب) گیت‌هایِ فرانت و گاردِ خودِ تغییر

| گیت | فرمان | خروج | شمارش |
|---|---|---:|---|
| نصبِ قفل | `npm ci` | ۰ | ۳۵۸ بسته |
| تایپ | `npx tsc -b` | ۰ | بی‌خطا |
| تستِ واحد | `npx vitest run` | ۰ | ۱۶۶ فایلِ سبز، ۱ skip (۱۶۷)؛ ۱٬۷۱۰ تست سبز، ۳ skip (۱٬۷۱۳) درِ ۳۷۷٫۴۲s |
| بیلدِ فرانت | `npm run build` | ۰ | `frontend/dist` ساخته شد |
| گاردِ کشِ بدنه | `python dev/funnel_body_cache_v1.py --port 8020` | ۰ | ۱۱ سبز، ۰ قرمز |
| گیتِ برابریِ خروجی | `python dev/perf_output_equal_v1.py` (۲۷ مسیر) | ۰ | ۱۹ IDENTICAL، ۸ VOLATILE-ONLY، ۰ DATA-DIFF → `OUTPUTS_EQUAL` |
| برابریِ قرارداد | `GET /openapi.json` پیش/پس | ۰ | ۹۳ مسیر، سندِ بایت‌به‌بایت یکی |

قرمز‑سبزِ همان گارد رویِ `ff6b2fb` (بی‌کشِ بدنه): **۳ سبز، ۸ قرمز** — پس گارد کور نیست
و تغییر را واقعاً می‌پوشاند (`phase1-before.log`).

### ۳پ) طبقه‌بندیِ سه قرمز — با بازاجرا، نه با حدس

هیچ‌کدام ازِ سه سوئیت درِ سطحِ تغییرِ من نیست: `git diff --quiet ff6b2fb..HEAD` برایِ هر سه
فایلِ سوئیت و برایِ `adjustment_engine.py` تمیز است، و هیچ‌کدام `api/funnel.py` یا
`app.py` را نمی‌لمسد. علتِ هر سه:

| سوئیت | علت | شاهدِ بازاجرا |
|---|---|---|
| `single writer: one backend per market.db` | درِ زمانِ باتری، ریگِ من (:8020) و بک‌اندِ مأموریتِ دیگر (:8010) بالا بودند. خودِ گارد می‌گوید «پیشِ ازِ `run_all_tests.py` باید سرورها بسته باشند» (`dev/single_writer_guard.py:16-19`) ⇒ **انحرافِ روشِ من**، نه نقصِ کد | با کشتنِ ریگِ من: `OK — تک‌نویسنده`، rc=۰ (`phase3-rerun-after-stopping-rig.log`) |
| `R1/R2 housekeeping: dedupe + prev-year backfill` | فیکسچرِ gitignore شدۀ `market.db.lzma` درِ این ورک‌تری نیست (`.gitignore:147 *.lzma`) | با copyِ `.lzma` ازِ ورک‌تریِ `ui-audit-system-2`: `[selftest] PASS` (`phase3-rerun-with-fixtures.log`) |
| `Phase4 engine … 38/39` | شاخۀ `ج۰` بی‌شاهدِ مرجع عمداً قرمز می‌شود (`dev/test_adjustment_engine_v1.py:207`)؛ شاهدِ `_audit/ra365_ref_bars.json` gitignore است (`.gitignore:192 _audit/*.json`) | با copyِ شاهد ازِ `BorsTerminal-src`: **۴۴ سبز، ۰ قرمز** |

پس: **قرمزِ باقی‌مانده درِ برابرِ تغییرِ من = صفر.** سه قرمزِ نخست همگی محیطی/روشی بودند و
همگی با همان دو شرطِ درست (سرورِ بسته + فیکسچرِ موجود) سبز شدند. هیچ تستی حذف، skip یا
تضعیف نشد؛ فیکسچرها copy شدند، نه ساخت.

یک اثرِ جانبیِ خودِ باتری هم ثبت می‌شود: سوئیتِ فیکسچر،
`dev/fixtures/fts_v10_payloads.json` را با خط‌شکنِ CRLF بازنویسی کرد (محتوا پس ازِ
نرمال‌سازی یکسان است). ازِ `HEAD` برگردانده شد تا کامیتِ این مأموریت آلوده به churn نشود.

### ۳ت) هم‌زمانیِ قیف (بندِ ۱پ) — عدد

ششِ POSTِ همزمان رویِ کلیدِ سردِ `/api/funnel`: `MISS` = ۱، `HIT` = ۵،
wall = ۱٬۱۰۴٫۸ms، بیشینهٔ یکِ درخواستِ ۱٬۱۰۰٫۳ms، جمعِ زمانِ سرویس ۶٫۵s.

