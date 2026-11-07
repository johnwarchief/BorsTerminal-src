# TECHNICAL HANDOFF — 2026-11-06

**Branch:** `integration/4axes-main-2026-11-03` · **HEAD:** `926f625d` · **Worktree:** `D:/BorsTerminal-worktrees/4axes-main-integration`
**Push:** هیچ (local only). **Tests:** 779/779 across 93 files, `tsc --noEmit` clean, production build OK.
**Servers:** stopped (8110 backend, 7093 dist). Nothing else touched.

## What is done and green
1. **بنیادی (P0/P1 + unslop + وتو)** — commits `1cef981c`, `28b6400d`, `a1da3b00`; evidence `_audit/rebuild/fts-*`, ledger `.superpowers/sdd/2026-11-05-fts-veto-unslop/`.
2. **الگوها (۲۶ نوع + رده‌بندی + ادغام در اسکنر)** — فاز A، commits `d5dbfaa5`..`fdf039b6`; ledger `_audit/rebuild/technical-phase-a/sdd/progress.md`; spec `docs/superpowers/specs/2026-11-05-technical-workspace-and-scanner-design.md`; plan `docs/superpowers/plans/2026-11-05-technical-workspace-phase-a.md`.
3. **میزکار TradingView (فاز B)** — commits `da0f42e1`..`926f625d`; ledger `_audit/rebuild/technical-phase-b/sdd/progress.md`; plan `docs/superpowers/plans/2026-11-05-technical-workspace-phase-b.md`; live evidence `_audit/rebuild/technical-phase-b/2026-11-06/` (chart 61.2% at 1366, 12px census 0 offenders, 25 screenshots).

## Known open items (ranked)
1. **مالکیت W/M باید به اندیکاتور DoubleTap3D برگردد.** `ClassicPatterns` (overlay) دو‌قلوها را از مسیر آداپتر هم می‌کشد → رسم دوباره و شکل ناقص. `DoubleTap3D` پیش‌فرض روشن است و W/M کامل + خط گردن + TP/SL + چیپ کیفیت را می‌کشد (`overlays/doubleTapOverlay.ts`, `model/doubleTapEngine.ts`, پارامترهای منبع تلگرام `DEFAULT_SOURCE_PARAMS`). اقدام: فیلتر `DOUBLE_TOP/BOTTOM` از `selectFeaturedPatterns` در overlay جدید (داده در فید بماند).
2. **انیمیشن W/M (web-animation-design):** canvas قابل انیمیت نیست؛ لایهٔ HTML/SVG روی چارت با `stroke-dashoffset` ~۳۲۰ms، یک‌بار به‌ازای هر anchor، `prefers-reduced-motion` → fade. مختصات از `chart.convertToPixel`.
3. **دقت الگوها:** فهرست پیش‌فرض فقط ردهٔ ۱ شود؛ ردهٔ ۲ پشت سوییچ «کم‌بسامد» تا داوری بصری ۱۵ نماد × ۲ تایم‌فریم با پذیرش «جعلی=۰» (فاز D) پاس شود. ابزار: `critic-capture.js`/`scanner-acceptance.js` در `D:/BorsTerminal-tmp/s4b-browser`.
4. **فاز C با اندیکاتورهای موجود:** کانال/پولبک/شکست از `MultiModeChannel` / `SuperTrendPullback` / `AutoTrendlineCHoCH` (در `overlays/advancedTradingIndicators.ts`, پیش‌فرض روشن) خوانده شود؛ فقط واگرایی RSI پیاده‌سازی مستقل لازم دارد. سپس یک رویداد برجسته در هر خانواده + ورود ۲۰۰ms.
5. **ریل ۲۴۰px در ۱۳۶۶** (۲۸۰ از ۱۴۴۱ به بالا) — تصمیم لازمِ مالک؛ کد در `src/app/styles.css` بخش workspace-grid و کامنتِ محاسبهٔ ۶۱٪.
6. **ForecastControls/DrawingToolbar** هنوز تایپ ۸٫۵–۱۰px دارند (خارج از census فاز B) و اکنون در حالت `compact` فقط ابزارهای یکتا را نشان می‌دهند (دوگانگی نوار حذف شد).

## Next mission suggestion
«اصلاح الگوها بر پایهٔ اندیکاتور ۳بعدی + انیمیشن W/M + داوری بصری» با پلنِ کوتاه: بازگرداندن مالکیت دو‌قلو، لایهٔ SVG انیمیشنی، پیش‌فرض ردهٔ ۱، سپس audit و فاز C.
