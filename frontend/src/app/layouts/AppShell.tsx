import { Outlet, useLocation } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import { Sidebar } from '../components/Sidebar';
import { Topbar } from '../components/Topbar';
import { WorkspaceTabs } from '../components/WorkspaceTabs';
import { MobileNav } from '../components/MobileNav';
import { SymbolContextStrip } from '../components/SymbolContextStrip';
import { CommandPalette } from '../components/CommandPalette';
import { SymbolInspector } from '../../widgets/SymbolInspector';
import { FtsPipelineBar } from '../../widgets/FtsPipelineBar';
import { useEffect, useRef } from 'react';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useActiveTab } from '@shared/stores/workspaceStore';
import { useAuthStore } from '@shared/stores/authStore';
import { useMediaQuery } from '@shared/lib/useMediaQuery';
import { MEDIA_MOBILE } from '@shared/lib/breakpoints';
import { useMarketStore } from '@shared/stores/marketStore';
import { startIdleGate } from '@shared/lib/idleGate';
import { useFlashClock } from '@shared/lib/flashClock';
import { useNavHistorySync } from '@shared/lib/useNavHistorySync';
import { LoginScreen } from '../../widgets/LoginScreen';
import { preloadMarketStatusFirstScreen } from '@features/market/lib/preloadMarketStatusFirstScreen';

/**
 * نوارِ «مشاور تحلیلی FTS» که بعد از انتخابِ نماد در بالای صفحه می‌چسبد، فعلاً
 * نمایش داده نمی‌شود (درخواستِ مالک). خودِ ویجت، مودال و تست‌هایش دست‌نخورده‌اند —
 * برای برگرداندن همین پرچم را true کن. (#148)
 */
const SHOW_FTS_PIPELINE_BAR = false;

export function AppShell() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const symbol = useSymbolStore((s) => s.symbol);
  const inspectorOpen = symbol.length > 0;
  const activeTab = useActiveTab();
  const pathname = useLocation().pathname;
  const qc = useQueryClient();
  // بندِ ۲.۳ مأموریتِ System ۲: درِ گوشی دوِ مرجعِ ناوبری نداریم. ریلِ آیکونِ سایدبار
  // درِ ۳۹۰px هم ۵۶px عرضِ جدولِ کارت را می‌خورد وِ هم ۱۱ کنترلِ ۳۸×۴۱px (زیرِ کفِ
  // لمس) بهِ هرِ صفحّه اضافه می‌کرد -- اندازه‌گیریِ `tools/ui_mobile_probe.mjs`.
  // مقصدها وِ کنترل‌هایِ حساب همگی ازِ `MobileNav` + `AccountControls` می‌رسند.
  const isMobile = useMediaQuery(MEDIA_MOBILE);

  // طولِ فلاشِ اعداد از ریتمِ واقعیِ تازۀِ تابلو می‌آید (رأیِ مالک: ۵s ← ~۳٫۵s)
  useFlashClock();

  // تاریخچۀِ درونِ برنامه (بندِ A مأموریتِ UI/UX): هر تغییرِ نشانی باِ نوعش
  // (`PUSH`/`REPLACE`/`POP`) ثبت می‌شود تاِ دو دکمۀِ «بازگشت/بعدی» درِ `Topbar`
  // دروازه‌شان را ازِ همینِ مدلِ بخوانند، نه ازِ `window.history.length`.
  useNavHistorySync();

  // فاز G بندِ ۵: صفحۀِ اولِ «وضعیت بازار» ازِ همینِ لحظه خوانده می‌شود، نه ازِ بعدِ
  // رسیدنِ chunkِ تنبلِ خودِ صفحه. `prefetchQuery` باِ همانِ کلیدِ isِ hook است، پسِ
  // کامپوننت درِ همانِ پرسشِ در حالِ جریان شرکت می‌کند (درخواستِ دوم ساخته نمی‌شود).
  useEffect(() => {
    if (!isAuthenticated) return;
    if (pathname.startsWith('/market-status')) preloadMarketStatusFirstScreen(qc);
  }, [isAuthenticated, pathname, qc]);

  // پولینگ هنگام مینیمایز متوقف می‌شود (فقط hidden؛ «بی‌فوکوس» کمکی نمی‌کند).
  useEffect(() => {
    const handleVisibility = () => useMarketStore.getState().setPaused(document.hidden);
    handleVisibility();
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, []);

  useEffect(() => {
    const stopIdleGate = startIdleGate();

    // تشخیص سیستم کم‌توان → حالت کم‌مصرف (حذف backdrop-blur و انیمیشن‌های پیوسته).
    // قابل بازنویسی با localStorage('perf-low'='0'|'1').
    try {
      const nav = navigator as Navigator & { deviceMemory?: number };
      const tiny = (nav.hardwareConcurrency ?? 8) <= 4 || (nav.deviceMemory ?? 8) <= 4;
      const override = localStorage.getItem('perf-low');
      const low = override != null ? override === '1' : tiny;
      document.documentElement.dataset.perf = low ? 'low' : 'high';
    } catch {
      /* نادیده بگیر */
    }

    return stopIdleGate;
  }, []);

  // ارتفاعِ نوارهایِ چسبانِ بالایِ محتوا اندازه‌گیری می‌شود، نه حدس:
  // `--pinned-h` ازِ قبل درِ index.css تعریف بود ولی قاعدۀِ
  // `.app-content:has(.symbol-strip-bar)` هرگز نمی‌خورد (هیچ المانی کلاسِ
  // `symbol-strip-bar` نداشت)، پس نوارِ فیلترها رویِ `top: 36px` می‌چسبید وِ
  // زیرِ نوارِ نماد (که خود ۳۶ تا ~۱۰۱px را می‌گیرد) پنهان می‌شد — دو نوارِ
  // چسبان رویِ هم. باِ ResizeObserver ارتفاعِ واقعیِ هر دو نوار جمع می‌شود،
  // پسِ هر چیدمانِ تازه‌ای (تب‌هایِ فضایِ کاری، پیچیدنِ نوارِ نماد درِ عرضِ کم)
  // خودکار درست می‌نشیند.
  const contentRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const root = contentRef.current;
    if (!root) return;
    const sync = () => {
      let topbar = 0; let total = 0;
      for (const el of Array.from(root.querySelectorAll<HTMLElement>('[data-pinned]'))) {
        const h = el.getBoundingClientRect().height;
        total += h;
        if (el.dataset.pinned === 'topbar') topbar = h;
      }
      root.style.setProperty('--pinned-topbar', `${Math.round(topbar)}px`);
      root.style.setProperty('--pinned-h', `${Math.round(total)}px`);
    };
    const observed = new WeakSet<Element>();
    const attach = () => {
      root.querySelectorAll('[data-pinned]').forEach((el) => {
        if (observed.has(el)) return;
        observed.add(el);
        ro.observe(el);
      });

      sync();
    };
    const ro = new ResizeObserver(sync);
    // نوارِ نماد باِ «نماد انتخاب‌شده» می‌آید و می‌رود؛ پسِ فهرستِ نوارهایِ چسبان
    // ثابت نیست. MutationObserver رویِ فرزندانیِ خودِ root همین را می‌گیرد،
    // بی‌آنکه لازم باشد افکت هر بارِ رندر دوباره ساخته شود.
    const mo = new MutationObserver(attach);
    mo.observe(root, { childList: true });
    attach();
    return () => { ro.disconnect(); mo.disconnect(); };
  }, []);

  if (!isAuthenticated) {
    return <LoginScreen />;
  }

  // ریسپانسیو (فاز ۲): فاصله/اورلی سایدبار و داور با CSS و توکنها مدیریت میشود
  // (.app-content / .app-main در index.css) — بدون هک جاوااسکریپت در رندر.
  return (
    <div className="flex h-dvh overflow-hidden bg-bg-primary text-text-primary">
      {/* درِ تکنیکال، سایدبارِ اصلی «رندر نمی‌شود» (نه فقط جمع‌شده): عرضِ ۶۰px ریل
          و کفِ لمسیِ ۳۸px درِ گوشی هم برداشته می‌شود. ناوبری از WorkspaceTabs و
          MobileNav می‌آید؛ ترجیحِ جمع‌شدگیِ ذخیره‌شده دست‌نخورده می‌ماند. */}
      {!isMobile && !/^\/technical(?:\/|$)/.test(pathname) && <Sidebar />}
      <div
        ref={contentRef}
        className="app-content flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto overflow-x-hidden transition-[padding] duration-200 ease-out"
        data-inspector={inspectorOpen ? 'open' : 'closed'}
      >
        <Topbar />
        <WorkspaceTabs />
        <SymbolContextStrip />
        {SHOW_FTS_PIPELINE_BAR ? <FtsPipelineBar /> : null}
        <main
          id="workspace-panel"
          role="tabpanel"
          aria-labelledby={activeTab ? `ws-tab-${activeTab.id}` : undefined}
          tabIndex={0}
          className="app-main flex min-h-0 flex-1 flex-col py-2 outline-none focus-visible:ring-2 focus-visible:ring-accent-blue"
        >
          <div className="panel-in flex min-h-0 w-full flex-1 flex-col gap-4">
            <Outlet />
          </div>
        </main>
      </div>
      <SymbolInspector />
      <MobileNav />
      <CommandPalette />
    </div>
  );
}