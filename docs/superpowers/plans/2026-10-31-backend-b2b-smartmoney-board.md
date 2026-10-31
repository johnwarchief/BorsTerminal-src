# B2-2 — smart-money، board و گیتِ ۱۳ مسیر

**Spec:** `docs/superpowers/specs/2026-10-29-backend-go-rewrite-design.md` (§۸، مرحلۀ B2، نیمۀ دوم)
**پیش‌نیاز:** B2-1 کامل و سبز (`docs/superpowers/reports/2026-10-30-b2a-mstat-parity.md`، ۳۴ کیس، Δ=۰)
**Branch:** `mission/4-axes-2026-10-10`

## دامنه

دو مسیرِ باقی‌ماندۀ `/api/mstat`:

| مسیر | ترکیب | منبعِ پایتون |
| --- | --- | --- |
| `GET /api/mstat/smart-money` | macro + watch_entry + flow + trio + verdict | `mstat_engine.smart_money`، `day_verdict`، `_market_state` |
| `GET /api/mstat/board` | ده پنلِ B2-1 با `source` حذف‌شده | `api/market_status._board_all` / `mstat_board` |

و گیتِ برابری که هر ۱۳ مسیرِ `routes.json` را رویِ دو کپیِ یخ‌زده می‌سنجد.

`POST /api/mstat/snapshot` بیرون از دامنه است: Go همان `501 NOT_PORTED` را می‌دهد (مالکیت تا B6 در پایتون).

## تصمیم‌های پیش از اجرا

- **R1 — حافظۀ حکم درون‌سرویس است، نه سراسری.** `_ASSESS` و `_STATE_MEMO` در پایتون dictِ ماژول‌اند. در Go همین دو در `Service` می‌نشینند (با mutex) و فقط رویِ cache-miss به‌روز می‌شوند؛ پس رفتارِ «سه ارزیابیِ متوالیِ تازه» و «تغییر نسبت به ارزیابیِ پیش» با همان ترتیبِ درخواست‌ها بازتولید می‌شود. تست‌ها نمونهٔ تازه می‌سازند.
- **R2 — ساعت فقط برای `market_phase` تزریق می‌شود.** `hm`، پنجرۀ ساعت، دورۀ شکل‌گیری و تازگیِ داده از خودِ `h_even`/`asof` خوانده می‌شوند؛ ساعتِ دیوار فقط `Phase.clock_now` را می‌سازد که در بدنۀ smart-money نیست.
- **R3 — board کشِ سطحِ خودش را ندارد.** هر ده پنل از همان `Service.Call` و همان کلیدِ مسیرهایِ تک‌پنلی می‌گذرند (پایتون هم `_mstat_call` هر پنل را صدا می‌زند)، و `source` از هر پنل حذف می‌شود؛ `source` فقط در سطحِ board می‌نشیند.
- **R4 — خطای یک پنل، board را نمی‌اندازد.** بدنهٔ `{status:error,message}`ِ همان پنل (بی‌`source`) داخلِ board می‌نشیند، عینِ `_panel`.
- **R5 — `partial_session` با صحنۀ s5 سنجیده می‌شود.** فیکسچرِ s1 (پایانِ نشست) شاخۀ «جمعِ تا-لحظه» را نمی‌گیرد؛ صحنۀ continuous با `mstat_snap`ِ سه‌نقطه‌ای همان شاخه، `pace_note`، `session_start_clock` و `flow_trend` را می‌پوشاند.
- **R6 — گیت شل نمی‌شود.** `tools/parity/gate_b2a.py` با همان ۱۳ بررسی می‌ماند؛ فقط `routes.json`/کیس‌ها به ۱۳ مسیر می‌رسند. هیچ assertion حذف نمی‌شود.

## Task 11 — اوراکل و طلایی‌ها

- `tools/parity/gen_mstat_golden.py`: افزودن `smart_money` و `board` به پنل‌های s1، و صحنۀ `s5` (continuous):
  - سه نقطۀ `mstat_snap` به روزِ ۲۰۲۶۱۰۲۸ + دو روزِ قبل (کپیِ شیفت‌داده) برای `_same_clock_ref`،
  - `market_index` → `d_even=20261028`, `market_state='A'`, `title='باز'`, `activity_h_even=103000`.
  - فقط `smart_money` در s5.
- `dev/test_mstat_fixture_v1121.py`: `ROUTES` + smart_money/board، `SCENARIOS` + s5، `panel_content` برای این دو، و به‌روزرسانیِ شمارشِ سناریوها (s1..s5).
- فیکسچر دست نمی‌خورد؛ گارد با دو اجرایِ تازه سبز می‌شود.

## Task 12 — موتورِ حکم و smart-money

- `internal/mstat/verdict.go`: `verdictMemo` (assess/state)، `gate`، `flowTrio`، `liqSide`، `liquidityHistory` + `eqAllCodes` + `liquidityFromPriceHistory`، `sessionStartHM`، `negStreak`، `flowTrend`، `sameClockRef`، `clockWindow`، `faNum`/`faSigned`/`hmToClock`/`hmFromHEven`، `dayVerdict`، `marketState`.
- `internal/mstat/smartmoney.go`: `smartMoneyPanel(db, now, memo)` — macro از `macroHealthFrom` (با conn، R2ِ B2-1)، watch_entry، flow، trio، verdict.
- تست: طلاییِ s1 و s5 + وکتورهایِ شاخه (avoid/تأییدِ سه‌گانه/forming/nodata)، تاریخچۀ نقدینگی با آستانۀ تزریقی، فرمتِ فارسی (نیم‌فاصلۀ ارقام، U+2212).

## Task 13 — board و مسیرها

- `internal/mstat/board.go`: `Service.Board(group, limit)`، حذفِ `source` از هر پنل، ترتیبِ همان `_board_all`.
- `handlers.go`: `SmartMoney` و `Board` (Query: `group=eq_all`, `limit=60`؛ `limit` غیرعدد ⇒ 422 مثلِ FastAPI).
- `httpapi`: دو GET و به‌روزرسانیِ تستِ ۵۰۱ (۱۱ → ۱۳).
- تست: طلاییِ board؛ برابریِ هر پنل با طلاییِ تک‌پنلی؛ اشتراکِ کش (board سپس مسیرِ تنها ⇒ بدون بازسازیِ دوباره).

## Task 14 — گیتِ ۱۳ مسیر و گزارش

- `tools/parity/cases_b2a.json`: ۳۶+ کیس با دو مسیرِ تازه (board پیش‌فرض + board با group/limit؛ smart-money).
- گیت با همان ۱۳ بررسی؛ اجرا رویِ دو کپیِ یخ‌زده، Δ=۰، POST همچنان ۵۰۱.
- گزارش فارسی + شاهدِ `_audit/parity/B2b.json` + لجر + پوش.

## چه چیزی در B2-2 نیست

- POST snapshot (B6)، متدِ نادرست (۴۰۴/۴۰۵)، limitهایِ بزرگ‌تر از int64 — همان اختلاف‌هایِ اعلام‌شدۀ B2-1.
- هیچ کاربرِ ریلیز/نصب در این مرحله دیده نمی‌شود؛ برنامهٔ نصب‌شده هنوز پایتون اجرا می‌کند.
