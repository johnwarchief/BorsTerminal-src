# PERF-AUDIT-BASELINE — عددِ پیش از هر optimization (PHASE: Measure only)

> **Baseline تاریخی عملکرد:** این اعداد برای بیلد و محیط سنجش ثبت‌شده در همین سند معتبرند و baseline امروز محسوب نمی‌شوند. هر ادعای بهبود یا رگرسیون را با همان روش، روی کد جاری و محیط یکسان دوباره اندازه‌گیری کنید؛ نتایج Jev ذکرشده نیز وضعیت مهاجرت Laya را تعیین نمی‌کند.


سنجش روی **بیلدِ سورس** (uvicorn 8002، `dist` ساختۀ `npm run build` همین نشست) و
Chromium ایزولهٔ jev-browser، بازارِ بسته (ریتمِ واقعیِ ساعتِ بازار پایین‌تر است
نه بالاتر — اعدادِ بازِ بازار از ریتمِ کد استخراج شده). هیچ کدِ اپلیکیشنی در این
PHASE عوض نشد. ابزارها: `tools/perf_audit_probe.mts` (جدید)،
`tools/tab_cost_probe.mts`، `tools/market_poll_cost.mts`،
`tools/feed_parse_cost.mts`؛ خروجی‌ها `_audit/perf_audit.json`،
`_audit/tab_cost_8002.json`، `_audit/backend_lat_8002.json`.

## Baselineِ صفحه‌به‌صفحه (CDP Performance.getMetrics، پنجرۀ ۱۲s بی‌تعامل)

| تب | Task | Script | Layout | Style | DOM |
|---|---:|---:|---:|---:|---:|
| tape | 22ms | 0 | 0 | 11ms | 1610 |
| technical | 19ms | 1 | 0 | 6 | 578 |
| fundamental | 21ms | 0 | 0 | 8 | 567 |
| masterFunnel | 26ms | 0 | 0 | 14 | 2031 |
| masterVerdict | 15ms | 1 | 0 | 5 | 304 |
| **strategy-tree** | **1023ms** | 2 | **31** | **98** | 821 |
| portfolio | 15ms | 0 | 0 | 5 | 400 |

## سناریوهای پروب

- startup: تا نخستین سطر جدول **482ms**؛ heap سرد **9.2MB**؛ first-poll کامل
  تابلو **629KB فشرده / 1414ms** (اولین بار، شاملِ boot روت لاگی).
- idle بازار (۶۰s): Task **2757ms** (۴٫۶٪ یک هسته؛ Script تنها 367 — بقیه
  paint/render تسک‌ها)، long-task ۲×~۶۰ms، heap 9.5→9.7، ریزِ rAF ۳۰ms.
- اسکرول ۲۴گامِ جدول: Task 281ms — بی‌مشکل.
- tab-loop ×۳ چرخۀ کامل: heap **22.9 → 25.4 → 29.7MB** (+~4MB در هر پاس؛
  در ۳ پاس به سقف نرسید — یا کشِ gcTime دیرآزادشونده است یا نشت؛ ۱۰‌پاس
  لازم — UNKNOWN باز).
- ۲۰ سوییچ نماد درِ تکنیکال: heap +2.7MB، Task 1823ms (≈۹۱ms/سوییچ —
  rebuild کاملِ سری در klinecharts)، **JSEventListeners Δ=−26** (تخلیه سالم)،
  ۱۰ canvas زنده در پایان (باید ۵-۶ باشد —UNKNOWN).
- دراور ۱۰× open/close: heap +1.2MB و بعد flat؛ intervalsLive ثابت.
- درخت mount/unmount ×۵: heap 35.2→35.4 (flat)، listeners **1025 ثابت**،
  nodes 9489 ثابت → lifecycle تمیز؛ Task 1.2–1.8s هر چرخه (رسمِ نخستِ ~۵۰۰-۸۰۰
  عنصرِ SVG).
- Heavy master (داossier+بازرس، ۲۰s): Task 985ms، long-task 17×∑1266ms،
  worst-rAF 14ms.
- **Heavy tree با جریانِ روشن (۲۰s): Task 7861ms = ۳۹٪ هسته** — در حالی که
  Script تنها 80ms است؛ یعنی هزینه در **renderer/compositingِ SMIL
  (cometها)/SVG** است نه JS. حالت پیش‌فرضِ جریان `system` است (با
  prefers-reduced-motion خاموش می‌شود).

## Market realtime (كلِ چرخه)

- بدنهٔ کامل 4.52MB / 5598 ردیف / ۴۸ فیلد؛ JSON.parse 21ms، zod 30ms،
  کلون 38ms (node؛ درِ مرورگر هم‌رتبه). با etag: ۳۰۴ صفر‌بایت/3ms؛ deltaِ
  بی‌تغییری: ۱۵۸ بایت. zod سهمِ ۵s-tick ≈ ۰٫۶٪ — گلو نیست.
- **هر پولینگ یک wrapper آبجکتِ تازه می‌سازد حتی درِ `unchanged`**
  (`shared/api/marketFeed.ts:44-46`) → همهٔ observerها (تا **۸** در
  /technical و /master) re-render می‌شوند؛ درِ master اضافه بر آن
  `buildFunnel` + صفِ tech + دو `useMarketCloses` Map-سازِ-۵۵۹۸ردیفی و
  سه اسکنِ خطیِ inspector می‌چرخد.
- دو observer هم‌زمانِ `useFtsFunnel` درِ /master (MasterPage + FtsFunnelStages).

## Backend (uvicorn 8002، تک‌workerno)

- بی‌بارداری: CPU 0٪، RSS 540MB (بانک در RAM). ۲۱ thread، 265 handle.
- /api/market: ۲۵ms میانه (۴٫۵MB) — SWR ۶۰s + etag سالم.
- **خانوادۀ mstat بی‌کشِ سطح-API، هر درخواست محاسبۀ زنده روی ۵۵۹۸ ردیف**:
  summary ≈300ms، smart-money ۴۰۶–۸۳۵ms، depth 254ms، thermometer 250ms،
  histogram 355ms → هر نفسِ نبض (۴ اندپوینت) ≈ **۱٫۲–۱٫۷ ثانیهٔ هسته**؛
  در ساعتِ بازار هر ۳۰s ≈ ۴–۶٪ duty؛ تداخلِ اندازه‌گیری‌شده بر تأخیر
  market در همان لحظه: 25→58-62ms (×2.3 — فاجعه نه، ولی قابل‌حذف).
- /api/fts کشِ ۹۰۰sِ نتیجه (87ms میانه، cold 1.7s)؛ screener کشِ ۱۲h و
  build تا ۶۰ آنالیز FTS در هر sync. تایمرهای سرور: tick 5s (فقط با
  تغییر revision بازسازی)، full-sync 90s، snapshot نبض 300s.
- first-poll اپ 1414ms: sampleِ نخستِ سرد است (تک‌نمونه)؛ تکرارِ صف درِ
  burstِ نبض فقط ×2.3 — پس 1414ms را گلوِ سرور ندانست؛ باید تفکیک شد
  (دانلود+پارس+chunk) — UNKNOWN باز.

## Timer/listener — ممیزی ایستا

همۀ `setInterval`ها پاک‌سازی‌شده‌اند؛ churnهای ثبت‌شده: replay interval هر
گامِ cursor (`TechnicalPage.tsx:171-180`)، snapshotِ ترسیم ۲s (تمیز)، timeout
یک‌طرفۀ LoginScreen/UserSettingsModal بدونِ لغو. listener ماژولِ popstate
عمدیِ یک‌بار. WebSocket درِ برنامه هیچ.

## Ranked

- **P0-1** تب درخت: ~۸٪ هسته بی‌تعامل / ۳۹٪ با جریان — هزینهٔ رسمِ SMIL/SVG.
- **P0-2** churn هر پولینگ: wrapper تازه + fan-out ۸-observerه + funnel/Map
  rebuildها — هزینۀِ مداومِ بیکار درِ بازارِ باز.
- **P0-3** mstat بدونِ کش: ~۱٫۵s هسته هر نفسِ نبض + RSS ۶۱۷MBِ پردازش پس
  از burst.
- **P1** rebuild کاملِ سری چارت در هر سوییچ (۹۱ms)؛ دو observer قیف در
  /master؛ growth ۴MB/پاسِ tab-loop (تا اثبات نشت یا سقف).
- **P2** اسکرول/دیالوگ/idle بقیۀ تب‌ها: عددِ خوب — کاری نکنید.

## قیدها

FTS logic، ودوی هفتگی، ساعت شنی، adjustment، معنای داده، UX IA و **انیمیشن‌ها**
دست‌نخورده — هر fix پیشنهادی باید «همان تجربه، تسکِ کمتر» باشد.

## نتایجِ optimization (Steps 1–8 — پس از `5e132dd` + fixِ نشت)

سه وضعیت در یک پروب (`tools/perf_audit_probe.mts`)، همان آدرس و همان پنجره‌ها؛
عددِ دستکاری‌شده نیست: «baseline» = `a4e0454`، «میانی» = پس از Stepهای 1–4 و
پیشِ fixِ نشت (`_audit/perf_audit_after.json`)، «نهایی» = با fixِ نشت
(`_audit/perf_audit_final.json`، ۱۰ پاس).

| سنجش (ms مگر ذکرِ واحد) | baseline | میانی | نهایی |
|---|---:|---:|---:|
| idle-market ۶۰s — Task | 2757 | 731 | **550** |
| scroll-market — Task | 281 | 73 | **59** |
| heavy-tree-flow ۲۰s — Task | 7861 | 2006 | **1346** |
| heavy-tree-flow — DOM nodes | 8100 | 12454 | **5579** |
| heavy-master-dossier ۲۰s — Task | 985 | 280 | **172** |
| symbol-stress ۲۰ — Task / heap پس | 1823 / 32.4MB | 905 / 61.2MB | 933 / **28.0MB** |
| tab-loop ۱۰ پاس — listener زنده | — ( ثبت نمی‌شد ) | 687→1491 (+97/پاس) | **521 ثابت** |
| tab-loop ۱۰ پاس — heap | 22.9→29.7MB/3پاس | 24.6→57.2MB | **17.9→20.6MB (سقفِ صاف)** |
| فراخوانِ تکراریِ mstat در همان revision (بک‌اند) | 295–406 | **5–21 (parity بایت‌به‌بایت)** | 5–21 |
| بدنهٔ پولینگِ بی‌تغییری | 4.1MB کامل | **۱۵۸B دلتا + snapshotِ هم‌هویت** | همان |

هدف‌های Step7 هر سه محقق شدند: بی‌تغییری→fan-outِ نزدیکِ صفر (تستِ `f3===f2`)،
mstatِ تکراری→CPUِ نزدیکِ صفر، درخت→کاهشِ ۸۳٪ از ۷٫۹s.

### نشتِ /technical — اثبات، ریشه، بستن

- اثبات: هر سیکلِ market↔technical دقیقاً `document:keydown/mousedown/touchstart`
  را +۱ می‌کرد (CDP JSEventListeners ۵ سیکل: 247→752).
- ریشه: `dispose(chartContainerRef.current)` در cleanupِ passive — ریف پیش از
  cleanup تهی می‌شد و گاردِ `if` دیسپوز را بی‌صدا رد می‌کرد (klinecharts v10).
- fix: قفلِ میزبان در `hostEl` زمانِ `init` و دیسپوزِ همان (`KLineChartWrapper.tsx`).
- پس از fix: ۱۰ سیکل ⇒ JSEventListeners 247→251، documentها بدونِ رشد، هیپِ
  پسِ GCِ اجباری 14.1→16.3MB و صاف. رفتارِ cache (symbol-stress heap +7MB و
  سپس بی‌رشد) نشت نیست؛ gcTimeِ TanStack است — سند شد، پاک‌سازیِ حدسی نشد.
- KLineCharts دوم (second engine): بی‌فعال که بود؛ سوییچِ فعال‌سازی انجام نشد (Step4-D).

### بازگشتِ انجماد

`dev/test_roundm_freeze.py` = 6 pass / 0 fail / 1 skip با همان توزیعِ پین‌شده
(seen up=35/range=5؛ PERMITTED=35/REJECT=5)؛ `dev/run_all_tests.py` = ALL SUITES
PASSED؛ vitest فرانت 1425 تست در 134 پرونده؛ tsc/eslint/CJK = صفر.

**راستی‌آزمایی‌نشده:** قضاوتِ pilot jev در تمامِ فازِ optimization در دسترس نبود
(timeout مکرر) — نصابِ «دو jev» فقط با نیمۀ browser خوانده شد.
