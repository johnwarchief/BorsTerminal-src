// app/components/WorkspaceTabs.tsx -- نوارِ تبِ واقعیِ فضای کاری
//
// الگو: ARIA APG «Tabs» (https://www.w3.org/WAI/ARIA/apg/patterns/tabs/) باِ دو
// تطبیقِ عمدی که بدونِ آن‌ها اینِ نوار یا ناوبری‌ناپذیر می‌شد یا باِ ماوس گم:
// ۱) جهتِ پیکان‌ها درِ RTL برگشته است: کاربرِ `dir=rtl` باِ `ArrowLeft` به
//    تبِ *بعدی* می‌رود (چپ = جلوتر درِ چیدمانِ راست‌به‌چپ)، برعکسِ متنی که
//    الگویِ انگلیسی می‌نویسد.
// ۲) دکمۀِ بستن داخلِ خودِ tab نشسته است (همان کاری که Chrome/Edge می‌کنند)،
//    باِ اینِ فرض که «بستن» باید باِ ماوس دیده شود؛ برایِ همینِ دکمه هم
//    roving tabindex دارد تاِ ترتیبِ Tab درِ پیمایشِ صفحه‌کلید نشکند.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router';
import { NAV_SECTIONS } from './Sidebar';
import { useWorkspaceStore, symbolInPath, DEFAULT_TAB_PATH, type WorkspaceTab } from '@shared/stores/workspaceStore';
import { useSymbolStore } from '@shared/stores/symbolStore';

/** مقصدهایی که درِ Sidebar نیستند ولی مسیرِ ثبت‌شده‌اند (routes.tsx) */
const EXTRA_LABELS: Record<string, string> = {
  notifications: 'مرکز اعلان',
  'engine-lab': 'آزمایشگاه موتور',
};

/** برچسبِ فارسیِ یکِ مسیر — ازِ همانِ NAV_SECTIONS که Sidebar می‌خواند، تاِ یکِ واژگانِ دوم نسازیم */
export function labelForPath(path: string): string {
  const seg = path.replace(/^\//, '').split('/')[0];
  if (!seg) return 'استراتژی FTS';
  for (const section of NAV_SECTIONS) {
    const hit = section.items.find((i) => i.to === `/${seg}`);
    if (hit) return hit.label;
  }
  return EXTRA_LABELS[seg] ?? seg;
}

function tabTitle(tab: WorkspaceTab): string {
  const base = labelForPath(tab.path);
  const sym = symbolInPath(tab.path) || tab.symbol;
  return sym ? `${base} · ${sym}` : base;
}

const isTypingTarget = (el: EventTarget | null): boolean => {
  const node = el as HTMLElement | null;
  if (!node || typeof node.tagName !== 'string') return false;
  if (/^(INPUT|TEXTAREA|SELECT)$/.test(node.tagName)) return true;
  return node.isContentEditable === true;
};

export function WorkspaceTabs() {
  const tabs = useWorkspaceStore((s) => s.tabs);
  const activeId = useWorkspaceStore((s) => s.activeId);
  const openTab = useWorkspaceStore((s) => s.openTab);
  const closeTab = useWorkspaceStore((s) => s.closeTab);
  const activateTab = useWorkspaceStore((s) => s.activateTab);
  const syncActive = useWorkspaceStore((s) => s.syncActive);
  const setActiveSymbol = useWorkspaceStore((s) => s.setActiveSymbol);

  const navigate = useNavigate();
  const location = useLocation();
  const storedSymbol = useSymbolStore((s) => s.symbol);
  const setSymbol = useSymbolStore((s) => s.setSymbol);

  const tabRefs = useRef(new Map<string, HTMLDivElement>());
  const focusNextRef = useRef<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const firstTabNav = useRef(true);

  const active = tabs.find((t) => t.id === activeId);
  const path = useMemo(() => `/${location.pathname.replace(/^\/+/, '')}`, [location.pathname]);

  // ۱) مسیرِ واقعی → تبِ فعال (ناوبریِ درونِ صفحه، کلیدِ backِ مرورگر، reload)
  useEffect(() => {
    if (!active) return;
    if (active.path === path && active.symbol === (symbolInPath(path) || storedSymbol)) return;
    syncActive(path, symbolInPath(path) || storedSymbol);
  }, [path, storedSymbol, active, syncActive]);

  // ۲) فعال‌سازیِ تب ⇒ رفتن بهِ مسیرِ آنِ تب وِ برگرداندنِ نمادِ همانِ تب
  useEffect(() => {
    if (!active) return;
    // رویِ اولینِ رندر اینِ هم‌گام‌سازی باید بخوابد: کاربرِ نشانیِ مستقیم
    // (#/market-status ازِ نشانک یا Back) تبِ پیش‌فرضِ /master را نمی‌خواهد،
    // وِ هم‌گامِ ۱ همین حالا همانِ نشانی را بهِ تبِ فعال داده است. بی‌اینِ نگهبان،
    // سنجشِ زنده نشانداد کاربرِ نشانیِ مستقیم درِ #/master فرود می‌آمد وِ کارِ
    // همانِ صفحه (قیف + تابلو) هم درِ راه می‌ماند.
    if (firstTabNav.current) {
      firstTabNav.current = false;
    } else if (active.path !== path) {
      navigate(active.path);
    }
    if (active.symbol && active.symbol !== storedSymbol) setSymbol(active.symbol);
  }, [activeId]);

  // ۳) انتخابِ نماد درِ صفحه‌ای که :symbol ندارد ⇒ فقطِ تبِ فعال یادش می‌ماند
  useEffect(() => {
    if (!active) return;
    if (symbolInPath(active.path)) return;
    if (active.symbol === storedSymbol) return;
    setActiveSymbol(storedSymbol);
  }, [storedSymbol, active, setActiveSymbol]);

  const move = useCallback(
    (delta: number) => {
      const at = tabs.findIndex((t) => t.id === activeId);
      if (at < 0) return;
      const target = tabs[(at + delta + tabs.length) % tabs.length];
      activateTab(target.id);
      tabRefs.current.get(target.id)?.focus();
    },
    [tabs, activeId, activateTab],
  );

  const doClose = useCallback(
    (id: string) => {
      const landed = closeTab(id);
      if (landed) focusNextRef.current = landed;
    },
    [closeTab],
  );

  // پس ازِ بستن، فوکوس بهِ همسایه می‌رود تاِ کاربرِ صفحه‌کلید-محور درِ خلأ نیفتد
  useEffect(() => {
    const want = focusNextRef.current;
    if (!want) return;
    focusNextRef.current = null;
    tabRefs.current.get(want)?.focus();
  }, [tabs, activeId]);

  const onTabListKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    const key = e.key;
    // RTL: چپ = بعدی، راست = قبلی (بندِ ۱ بالایِ فایل)
    if (key === 'ArrowLeft') { e.preventDefault(); move(1); return; }
    if (key === 'ArrowRight') { e.preventDefault(); move(-1); return; }
    if (key === 'Home') { e.preventDefault(); const t = tabs[0]; if (t) { activateTab(t.id); tabRefs.current.get(t.id)?.focus(); } return; }
    if (key === 'End') { e.preventDefault(); const t = tabs[tabs.length - 1]; if (t) { activateTab(t.id); tabRefs.current.get(t.id)?.focus(); } return; }
    if (key === 'Delete' && active) { e.preventDefault(); doClose(active.id); return; }
    if ((key === 'Enter' || key === ' ') && active) { e.preventDefault(); navigate(path); }
  };

  // میانبرهایِ سراسری — قابل‌کشف ازِ titleِ دکمه‌ها وِ فهرستِ «…»
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTypingTarget(e.target)) return;
      if (!e.ctrlKey || e.altKey || e.metaKey) return;
      const { activeId: cur, tabs: all } = useWorkspaceStore.getState();
      if (e.key.toLowerCase() === 't') { e.preventDefault(); openTab(DEFAULT_TAB_PATH, '', { forceNew: true }); return; }
      if (e.key.toLowerCase() === 'w') { e.preventDefault(); if (cur) doClose(cur); return; }
      if (e.key === 'Tab') { e.preventDefault(); move(e.shiftKey ? -1 : 1); return; }
      const n = Number(e.key);
      if (n >= 1 && n <= 9) {
        const target = n === 9 ? all[all.length - 1] : all[n - 1];
        if (target) { e.preventDefault(); activateTab(target.id); }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [openTab, doClose, move, activateTab]);

  const overflowing = tabs.length > 6;

  return (
    <div
      data-shell="workspace-tabs"
      data-testid="workspace-tabs"
      className="flex h-9 shrink-0 items-stretch gap-1 border-b border-border-c bg-bg-card/40 px-2 backdrop-blur"
    >
      <div
        role="tablist"
        aria-label="تب‌های فضای کاری"
        aria-orientation="horizontal"
        onKeyDown={onTabListKeyDown}
        data-testid="ws-tablist"
        className="flex min-w-0 flex-1 items-stretch gap-1 overflow-x-auto [scrollbar-width:thin]"
      >
        {tabs.map((tab) => {
          const isSelected = tab.id === activeId;
          return (
            <div
              key={tab.id}
              id={`ws-tab-${tab.id}`}
              ref={(el) => {
                if (el) tabRefs.current.set(tab.id, el);
                else tabRefs.current.delete(tab.id);
              }}
              role="tab"
              aria-selected={isSelected}
              aria-controls="workspace-panel"
              title={tabTitle(tab)}
              tabIndex={isSelected ? 0 : -1}
              onClick={() => { if (!isSelected) activateTab(tab.id); navigate(tab.path); }}
              onAuxClick={(e) => { if (e.button === 1) doClose(tab.id); }}
              className={
                `group flex max-w-[16rem] min-w-[6.5rem] shrink-0 cursor-pointer items-center gap-1 border-b-2 px-2 text-2xs font-bold outline-none transition-colors ` +
                (isSelected
                  ? 'border-accent-blue bg-bg-primary/80 text-accent-blue'
                  : 'border-transparent text-text-secondary hover:bg-bg-primary/40 hover:text-text-primary') +
                ' focus-visible:ring-2 focus-visible:ring-accent-blue'
              }
            >
              <span className="min-w-0 flex-1 truncate">{tabTitle(tab)}</span>
              <button
                type="button"
                tabIndex={isSelected ? 0 : -1}
                aria-label={`بستن تب ${tabTitle(tab)}`}
                data-testid={`ws-tab-close-${tab.id}`}
                onClick={(e) => { e.stopPropagation(); doClose(tab.id); }}
                className="shrink-0 rounded p-0.5 text-text-muted opacity-60 transition hover:bg-accent-red/15 hover:text-accent-red hover:opacity-100 focus-visible:ring-2 focus-visible:ring-accent-blue"
              >
                <span aria-hidden="true" className="text-3xs leading-none">×</span>
              </button>
            </div>
          );
        })}
      </div>

      <div role="toolbar" aria-label="کنترل تب‌ها" className="flex shrink-0 items-center gap-1">
        <button
          type="button"
          onClick={() => openTab(DEFAULT_TAB_PATH, '', { forceNew: true })}
          aria-label="تب تازه"
          title="تب تازه (Ctrl+T)"
          data-testid="ws-tab-new"
          className="rounded px-2 text-sm font-black text-text-secondary transition hover:bg-accent-blue/12 hover:text-accent-blue focus-visible:ring-2 focus-visible:ring-accent-blue"
        >
          <span aria-hidden="true">+</span>
        </button>
        {overflowing ? (
          <div className="relative">
            <button
              type="button"
              aria-haspopup="true"
              aria-expanded={menuOpen}
              aria-label="فهرست تب‌ها"
              title="فهرست تب‌ها و میانبرها"
              data-testid="ws-tab-menu"
              onClick={() => setMenuOpen((v) => !v)}
              className="rounded px-2 text-sm font-black text-text-secondary transition hover:bg-accent-blue/12 hover:text-accent-blue focus-visible:ring-2 focus-visible:ring-accent-blue"
            >
              <span aria-hidden="true">…</span>
            </button>
            {menuOpen ? (
              <div
                role="menu"
                aria-label="تب‌های باز"
                data-testid="ws-tab-menu-list"
                className="absolute end-0 top-full z-50 mt-1 max-h-72 w-64 overflow-y-auto rounded-lg border border-border-c bg-bg-primary p-1 shadow-lg"
              >
                {tabs.map((t) => (
                  <div key={t.id} className="flex items-center gap-1">
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => { activateTab(t.id); navigate(t.path); setMenuOpen(false); }}
                      className={`min-w-0 flex-1 truncate rounded px-2 py-1 text-start text-2xs ${t.id === activeId ? 'text-accent-blue font-black' : 'text-text-secondary hover:text-text-primary'}`}
                    >
                      {tabTitle(t)}
                    </button>
                    <button
                      type="button"
                      role="menuitem"
                      aria-label={`بستن ${tabTitle(t)}`}
                      onClick={() => doClose(t.id)}
                      className="shrink-0 rounded px-1 text-2xs text-text-muted hover:text-accent-red"
                    >
                      ×
                    </button>
                  </div>
                ))}
                <div className="mt-1 border-t border-border-c/60 px-2 py-1 text-3xs leading-4 text-text-muted">
                  Ctrl+T تب تازه · Ctrl+W بستن · Ctrl+Tab جابه‌جایی · Ctrl+۱…۹ پرش
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
