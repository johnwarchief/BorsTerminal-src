# پلنِ ری‌بیلدِ BorsTerminal — اپِ تازه (گزینهٔ B)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan stage-by-stage. هر مرحله باید مستقل سبز شود؛ وضعیت با `- [ ]` پیگیری می‌شود. این سند «پلنِ مادر» است؛ برای هر مرحله هنگامِ شروع، ریزِ تسک‌ها (فایل/تست/کامیت) در همین سند باز می‌شود.

**Goal:** ساختِ اپِ فرانتِ تازه در ریپو (`frontend-v2/`) که همهٔ قابلیت‌های محصول را از اپِ فعلی می‌گیرد و طرحش از پروتوتایپِ v2 (`http://127.0.0.1:5302/v2/`) می‌آید — بدونِ بازنویسیِ موتورهای داده.

**Architecture:** اپِ تازه فقط UI است و از همان FastAPIِ فعلی می‌خواند (`/api/*`)، داخلِ همان پنجرهٔ Tauriِ D1 بار می‌شود. موتورهای FTS/تعدیل/کدال و سه قراردادِ frozen (`price_basis`, `candle_contract`, `codal_periods`) دست‌نخورده می‌مانند. UIِ قدیم تا هم‌ارزیِ هر مسیر، محصول و fallback است و بعد بازنشسته می‌شود (§4: هم‌زیستیِ زمان‌دار، بدونِ دو نسخهٔ دائمی).

**Tech Stack:** React 18.3 + TypeScript 5.9 + Vite 5 + TanStack Query 5 + TanStack Virtual 3 + Zustand 5 + Zod 4 + Tailwind 4؛ فونتِ Vazirmatn (سرویس‌شده از `/vendor/fonts` بک‌اند)؛ نمودار در S2 از همان KLineChartsِ فعلی.

**Spec:** `docs/BorsTerminal-Desktop-Migration-Decisions.md` (§2، §3، §4، §5، §6، §7، §9، §12.28، §12.31، §12.38، §12.39) + `docs/MIGRATION-D-SPEC-2026-10-27.md` + رأیِ مالک در §۱۳ همان فایلِ تصمیمات (B انتخاب شد؛ C باز است).

## Global Constraints

- «کوکی، توکن، رمز یا اطلاعات احراز هویت را استخراج یا در Git ذخیره نکن.»
- «دادهٔ خام اشتراک رهاورد را در مخزن عمومی قرار نده.»
- «هیچ دیتابیس عملیاتی یا WAL را حذف، بازنویسی یا تعمیر نکن.»
- حداکثر **یک** حلقهٔ زندهٔ TSETMC در هر لحظه (§3)؛ آزمونِ UI با `BORS_NO_FETCH_LOOPS=1` + پروکسیِ مرده.
- هیچ سفارشِ واقعی؛ سرخطی فقط شبیه‌سازی (§8).
- `fetch` فقط در `frontend-v2/src/shared/api/http.ts`؛ هیچ کامپوننتی مستقیم fetch نمی‌زند.
- ارقامِ فارسی فقط با `toFaDigits`/`fmt*`؛ رقمِ دست‌نویس در JSX ممنوع.
- متنِ رابط: فارسیِ RTL، واژگانِ جزوه برای چیزهایی که جزوه نام دارد؛ استعاره در متنِ دیدنی نه.
- هیچ آستانه/قاعده‌ای از خودم ساخته نمی‌شود؛ آستانه‌ها یا از جزوه/کدِ فعلی می‌آید یا رأیِ مالک است.
- `numpy==2.0.2` و هر پینِ بک‌اند دست‌نخورده.
- هر مرحله: `tsc` صفر خطا، تست‌ها سبز، شاهد در `_audit/rebuild/S<n>/`، کامیت + پوش فقط روی `mission/4-axes-2026-10-10`.
- PASSِ بصری خوداعلام نمی‌شود؛ اسکرین‌شات + عدد ارائه می‌شود و رأیِ مالک می‌ماند.

## وضعیتِ فعلی (شروعِ پلن)

- D1 (پوستهٔ Tauri) انجام و پوش شد: `docs/MIGRATION-D1-SHELL-SLICE-2026-10-27.md` §11، remote head `819ba313`.
- اسکلتِ `frontend-v2/` شروع شد: `package.json`، `tsconfig.json`، `vite.config.ts`، `index.html`، `src/app/styles.css` (توکن‌های برنجیِ v2)، `src/shared/lib/fa.ts`، `src/shared/api/http.ts`. هنوز `npm install` و صفحهٔ تابلو نیست.

## ترتیبِ مرحله‌ها و درِ پذیرش

| مرحله | قلمرو | درِ پایان (عدد/شاهد) | رأیِ مالک |
|---|---|---|---|
| S0 پایه‌ها | اسکلت، توکن‌ها، درِ شبکه، تست، dev loop | build صفرخطا؛ vitest سبز؛ نمونهٔ توکن‌ها | — |
| S1 تابلو | `/market` کامل: 6018 ردیف، فیلترها، مرتب‌سازی، جستجو | شمارشِ ۷ فیلتر = اپِ فعلی در همان لحظه؛ واحدها یکی؛ 3 اندازه اسکرین‌شات | G1 رأیِ بصری |
| S2 تکنیکال | نمودار + پنل‌های FTS + تعدیل | 395 کندلِ فولاد و رویدادهای تعدیل یکسان؛ پاریتیِ رهاورد (§6) | G1 |
| S3 مستر + وضعیت بازار | مسیرِ پیش‌فرض + ۱۵+ متریک | متریک‌ها با اپِ فعلی همان‌لحظه یکی | — |
| S4 بنیادی/کدال | جدولِ بنیادی، دوره‌ها، DPS | قواعدِ `codal_periods` بدونِ تغییر؛ نمونهٔ ۱۰ نماد یکی | — |
| S5 دیده‌بان + پرتفوی | CRUD، وزن‌ها | همان رفتارِ گاردهای فعلی (77/77 وزن‌ها) | — |
| S6 درخت استراتژی + Lab + اعلان‌ها | ابزارها | خروجیِ Lab قابلِ مقایسه با اپِ فعلی | — |
| S7 سرخطی | فقط شبیه‌سازی | dry-run؛ هیچ درخواستِ سفارشِ واقعی | — |
| S8 اتصال به پوسته | سرو کردنِ اپِ تازه + Tray/آپدیتر | مسیرِ §12.28 روی اپِ تازه | — |
| S9 دروازهٔ پاریتی/عملکرد/نصب | رهاورد + جزوه + سرعت + نصب | اعدادِ پاریتی و سرعت در برابر A؛ نصب/برگشت | G2 آستانه‌ها، G4 ریلیز |
| S10 بازنشستگیِ قدیم | حذفِ UIِ قدیم + مرج | فقط یک UI در محصول | G3 مرج به main |

## S0 — پایه‌ها (در جریان)

**Files:**
- Create: `frontend-v2/src/main.tsx`, `src/app/App.tsx`, `src/app/shell/AppShell.tsx`, `src/shared/ui/` (کمینه)، `src/__tests__/fa.spec.ts`
- Modify: `frontend-v2/package.json` در صورت نیازِ نسخه بعد از نصب
- Test: `frontend-v2/src/__tests__/fa.spec.ts`

**Interfaces:**
- Produces: `getJson<T>(path, schema, signal?)` از `@shared/api/http`؛ `toFaDigits/fmtInt/fmtPct/fmtHemmat/changePct/isOn` از `@shared/lib/fa`؛ شِلِ `AppShell` با سایدبارِ جمع‌شو و تب‌های ماندگار (Zustand + localStorage).

- [ ] Step 1: `npm install` با `env -u npm_config_allow_scripts` (متغیرِ تزریقیِ محیط نصب را می‌شکند)
- [ ] Step 2: تستِ `fa.spec.ts` (ارقام، درصد، همت) → اول قرمز، بعد سبز
- [ ] Step 3: `main.tsx` + `App.tsx` با `HashRouter` (مسیرِ `/` → `/market`)
- [ ] Step 4: `AppShell` — سایدبارِ ۱۱ مسیر (فقط بازار فعال)، تاپ‌بار، تمِ `brass` پیش‌فرض + سوییچِ روشن
- [ ] Step 5: `npm run typecheck && npm test && npm run build` سبز
- [ ] Step 6: گاردِ کوچک `grep -rn "fetch(" frontend-v2/src` که فقط `http.ts` را برگرداند
- [ ] Step 7: Commit + push

**Acceptance:** build بدونِ خطا؛ vitest سبز؛ خروجیِ build < 400KB gzip (بدونِ نمودار)؛ توکن‌های نمونه (`--bg #101215`، `--accent #c9a45c`، فونت Vazirmatn) در DOMِ مرورگر دیده شود.

## S1 — تابلو (`/market`)

**منبعِ پورت از اپِ فعلی:** `frontend/src/features/market/**`، `frontend/src/shared/api/marketFeed.ts`، `frontend/src/shared/types/marketRow.ts`، `frontend/src/features/market/lib/tapeFts.ts`، `frontend/src/shared/lib/fmt.ts`.

**Endpoints:** `/api/market` (بدنهٔ کامل 4.1MB)، `/api/market/delta?since=rev` (پس از اولین بار)، `/api/market/state`، `/api/market/sync-state`.

**Files:**
- Create: `src/shared/types/market.ts` (Zod: `MarketRowSchema` با `z.looseObject`، `MarketFeedSchema`)، `src/features/market/api/useBoard.ts`، `src/features/market/lib/boardSort.ts`، `src/features/market/lib/tapeFilters.ts`، `src/features/market/routes/MarketPage.tsx`، `src/features/market/components/{StatusStrip,TapeBar,BoardTable}.tsx`
- Test: `src/__tests__/board.spec.ts` (پارسِ پیلودِ نمونه، `changePct`، شمارشِ فیلترها)، `src/__tests__/boardSort.spec.ts`

**Interfaces:**
- Consumes: `getJson`، `fa.ts`
- Produces: `useBoard(): UseQueryResult<MarketFeed>`؛ `TapeKey = 'smart'|'legal'|'roobi'|'susp'|'clock'|'noqteh'|'jet'`؛ `applyFilters(rows, {tape, query}): MarketRow[]`؛ `sortRows(rows, key, dir)`

- [ ] Step 1: تستِ پارس با پیلودِ کوچکِ واقعی (۲ ردیف از `آباد`) → قرمز
- [ ] Step 2: `market.ts` + `useBoard` (کلیدِ `['board']`، staleTime 15s، بدونِ polling در S1؛ دلتا در تسکِ بعد)
- [ ] Step 3: `BoardTable` با `useVirtualizer` (ارتفاعِ ردیف 30px، overscan 12، ستون‌ها: نماد، صنعت، آخرین، تغییر٪، ارزش (همت)، حجم، حقیقی خرید٪، نشان‌ها)
- [ ] Step 4: `TapeBar` — ۷ چیپ با شمارشِ زنده + «همه»؛ معنای انتخاب از اپِ فعلی کپی شود (بدونِ اختراع)
- [ ] Step 5: مرتب‌سازی (پیش‌فرض ارزشِ نزولی)، جستجوی نماد، شمارندهٔ «نمایش N از M»
- [ ] Step 6: `StatusStrip` — «آخرین همگام‌سازی» + تعداد + live/fossil (بدونِ ادعای باز/بسته تا `/api/market/state` وصل شود)
- [ ] Step 7: دلتا (`?since=rev` + merge با سه درِ ایمنیِ `marketFeed.ts`) — در صورتِ ناسازگاری، برگشت به بدنهٔ کامل
- [ ] Step 8: شاهد: اسکرین‌شات 1366/1920/2560 + JSONِ شمارشِ فیلترها در `_audit/rebuild/S1/`
- [ ] Step 9: مقایسهٔ همان‌لحظه با اپِ فعلی: شمارشِ ۷ فیلتر، ارزش/حجمِ ۲۰ نمادِ اول، ترتیبِ پیش‌فرض
- [ ] Step 10: Commit + push

**Acceptance:** 6018 ردیف؛ شمارشِ فیلترها = اپِ فعلی در همان لحظه؛ حجم = `q_tot_tran` و ارزش = `q_tot_cap` (رابطهٔ حجم×قیمت اثبات‌شده)؛ بدونِ خطای کنسول؛ TBTِ اسکرول در 2560 < 100ms.

## S2 — تکنیکال

**منبعِ پورت:** `frontend/src/features/technical/**`، `useCandleFeed.ts`، `KLineChartsEngine.ts`، `ftsOverlays.ts`، `shared/api/chartDb*`.
**Endpoints:** `/api/chart/{symbol}`، `/api/chart-db`، `/api/history/{symbol}`، `/api/fts/analysis`.

- [ ] تسک‌ها هنگامِ شروع باز می‌شود: مسیرِ `#/technical/:symbol` (پارامترِ مسیر، نه querystring)، سوارکردنِ همان KLineCharts، پنل‌های FTS، نشانگرهای رویداد، ریپلی.
- **Acceptance:** برای فولاد همان 395 کندل و همان `adjustEvents`؛ پاریتیِ رهاورد طبق §6/§12.39.2 با پکِ مرجع؛ هیچ تعویضِ موتور بدونِ مقایسه.
- **Rollback:** مسیرِ `/technical` در UIِ قدیم باز می‌ماند.

## S3 — مستر (پیش‌فرضِ محصول) + وضعیت بازار

- `/master` پیش‌فرض می‌ماند (رأیِ مالک)؛ «بازار-اول» فقط ترتیبِ ورود است (§12.38.1).
- متریک‌های وضعیت (۱۵+) از `api/market_status.py`؛ نمونهٔ همان‌لحظه با اپِ فعلی.
- **Acceptance:** هر متریک با اپِ فعلی در یک لحظه یکی؛ برچسبِ تازگی صادق.

## S4 — بنیادی/کدال

- جدولِ بنیادی، `codal_periods` بدونِ تغییر، DPS/Codal auto-update؛ نمونهٔ ۱۰ نماد مقایسه‌ای.
- **Acceptance:** «بی‌دوره» و زنجیرهٔ datasource←عنوان یکسان؛ هیچ قاعدهٔ تازه.

## S5 — دیده‌بان + پرتفوی

- CRUDِ دیده‌بان (`/api/watchlist`)، وزن‌های ارزشی (`77/77` فعلی)؛
- **Acceptance:** همان گاردهای وزن و «صفرِ ساختگی» سبز.

## S6 — درخت استراتژی + آزمایشگاه موتور + اعلان‌ها

- **Acceptance:** خروجیِ Lab (mountMs/fps/heap) قابلِ مقایسه؛ اعلان‌ها فقط کدال با سطحِ قابلِ توضیح.

## S7 — سرخطی (فقط شبیه‌سازی)

- هیچ درخواستِ سفارشِ واقعی؛ dry-run پیش‌فرض (§8)؛ **Acceptance:** گاردهای سرخطیِ فعلی سبز.

## S8 — اتصال به پوسته

- سرو کردنِ اپِ تازه از بک‌اند (مسیرِ `/` یا `/next`)، شلِ D1 همان URL را می‌گیرد؛ Tray/close/آپدیترِ D1 بدونِ تغییر.
- **Acceptance:** مسیرِ §12.28 روی اپِ تازه؛ پنجره/بک‌اند/خروج/Tray/watchdog مثلِ D1.

## S9 — دروازهٔ پاریتی، عملکرد، نصب

- پاریتی: رهاورد (تکنیکال/تعدیل) + جزوهٔ FTS؛ عملکرد: در برابر A (cold 9,364ms، warm 4,581ms، idle 683MB) با همان روش؛ نصب/برگشت با §12.31.
- **Acceptance:** جدولِ عددیِ قبل/بعد؛ هیچ NOT_MEASURED به‌عنوان موفقیت.

## S10 — بازنشستگیِ قدیم + مرج

- حذفِ مسیرِ UIِ قدیم، خاموشیِ pywebview، حذفِ کدِ مرده؛ مرج به `main` فقط با رأیِ مالک (G3).
- **Acceptance:** یک UI در محصول؛ همهٔ گاردها سبز؛ ریلیزِ نهایی.

## رأی‌های بازِ مالک (درِ ورود، نه سؤالِ فنی)

| # | پرسش | کجا لازم می‌شود | پیشنهادِ من |
|---|---|---|---|
| G1 | رأیِ بصری روی دو صفحهٔ نمونه (`final-market-*`، `final-technical-*`) | پایانِ S1/S2 | برنجیِ تیرهٔ v2 مبنا؛ تغییرها با توکن |
| G2 | آستانه‌های عددیِ پذیرش (§1) | قبل از S9 | جدولِ پیشنهادی در D-spec؛ عدد را تو می‌دهی |
| G3 | مرج به `main` (§9 بندِ ۲) | S10 | بعد از سبزیِ S9 |
| G4 | بریدنِ ریلیز | S9 | یک ریلیزِ تجمیعی، نه per-fix |
| G5 | فعال‌کردنِ C (بک‌اندِ تازه) | هر زمان که بگویی | فعلاً نه؛ فقط با شاهدِ ماژول‌به‌ماژول |

## ریسک‌ها

| ریسک | کاهش |
|---|---|
| واگراییِ پاریتی در پورت | مقایسهٔ همان‌لحظه؛ همان تست‌های فعلی به‌عنوان درِ پذیرش؛ هیچ قاعدهٔ تازه |
| دو UIِ موازی | هم‌زیستیِ زمان‌دار؛ UIِ قدیم فقط fallback؛ S10 حذف |
| کندیِ رندر 6018 ردیف | مجازی‌سازی + دلتا؛ بودجهٔ TBT در هر مرحله |
| دادهٔ کهنه به‌عنوان زنده | برچسبِ تازگی از `last_sync`/`rev_at`؛ بدونِ ادعای باز/بسته تا `/api/market/state` |
| وابستگیِ جدید/لایسنس | فقط پکیج‌های رایج؛ KLineChartsِ موجود دوباره استفاده می‌شود |
| خطای محیطیِ npm | `env -u npm_config_allow_scripts` |

## تعریفِ «تمام» برای هر مرحله

`tsc` صفر خطا · تست‌های مرحله سبز · اسکرین‌شات ۳ اندازه · شاهدِ عددی در `_audit/rebuild/S<n>/` · بدونِ خطای کنسول · کامیت + پوش روی شاخهٔ مأموریت · به‌روزرسانی حافظه.
