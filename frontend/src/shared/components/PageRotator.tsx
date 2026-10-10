// shared/components/PageRotator.tsx -- صفحۀ محلیِ چرخشی، یک الگو برای همه
//
// چرا این فایل هست: الگوی «دو صفحۀ محلی» از قبل درِ `widgets/SymbolInspector.tsx`
// (رأیِ مالک 1405-07-17) ساخته شده بود: جابه‌جاییِ صفحّه فقط «دیدن» است -- نه
// درخواستِ تازه می‌زند نه refetchِ صفحۀ دیگر -- و هر دو صفحّه mount می‌مانند تا
// حالتِ بازشویِ صفحۀ دوم گم نشود. صفحۀ «وضعیت بازار» همان الگو را می‌خواهد به‌اضافۀ
// چرخشِ خودکار. نسخهٔ دومِ ناسازگار نساختن: این پریمیتیو درِ `shared` است چون
// ماتریسِ import (eslint.config.js) به feature اجازهٔ import از widgets نمی‌دهد،
// پس هر دو مصرف‌کننده باید بالاسَر بایستند.
//
// چرخشِ خودکار سه چیز را رعایت می‌کند که رأیِ صریحِ مأموریت است:
//   1) با hover یا focusِ صفحه‌کلید یا هر تعاملِ دستی مکث می‌کند؛
//   2) بعدِ تعامل به ابتدا نمی‌پرد -- از همان صفحّه ادامه می‌دهد؛
//   3) دسترسیِ دستی به همهٔ صفحّه‌ها همیشه هست (تب‌ها هیچ‌وقت پنهان نمی‌شوند).
//
// ترجیعِ سیستمِ کاهشِ حرکت تنها راهنما نیست: درِ همین برنامه (WebView2) تنظیمِ
// ویندوز به صفحه تحمیل می‌شود و تجربهٔ «درخت استراتژی» نشان داد که تکیهٔ صرفِ
// رویِ آن، رویِ ماشینِ هدف یعنی «هیچ‌وقت تکان نخورد». پس یک کلیدِ درون‌برنامه
// (storageKey) بر آن اولویت دارد.
import { useCallback, useEffect, useRef, useState } from 'react';

export type RotatorPage = { id: string; label: string; hint?: string };

/** تنظیمِ درون‌برنامه اگر ست شده باشد حاکم است؛ وگرنه ترجیعِ سیستم. */
export function readMotionSetting(key: string): boolean | null {
  try {
    const v = typeof window !== 'undefined' ? window.localStorage.getItem(key) : null;
    return v === 'rotate' ? true : v === 'still' ? false : null;
  } catch {
    return null;
  }
}

export function writeMotionSetting(key: string, rotate: boolean): void {
  try {
    window.localStorage.setItem(key, rotate ? 'rotate' : 'still');
  } catch {
    /* حالتِ بی‌localStorage (jsdomِ سخت‌گیر یا private mode) فقط یعنی «یادش نمی‌ماند» */
  }
}

export function prefersReducedMotion(): boolean {
  try {
    return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true;
  } catch {
    return false;
  }
}

export type RotatorState = {
  page: string;
  index: number;
  /** چرخش واقعاً در حال اجراست (نه فقط «روشن») */
  rotating: boolean;
  /** کاربر خودش چرخش را خاموش کرده؟ */
  userPaused: boolean;
  setPage: (id: string) => void;
  next: () => void;
  toggle: () => void;
  /** رویِ ظرفِ چرخان بگذارید: hover/focus مکث می‌سازد */
  pauseProps: {
    onMouseEnter: () => void;
    onMouseLeave: () => void;
    onFocus: () => void;
    onBlur: () => void;
  };
};

export function usePageRotator(opts: {
  pages: readonly RotatorPage[];
  intervalMs?: number;
  storageKey?: string;
  /** پیش‌فرضِ چرخش وقتی نه تنظیمِ کاربر هست نه ترجیعِ سیستم */
  defaultRotate?: boolean;
  start?: string;
}): RotatorState {
  const { pages, intervalMs = 6000, storageKey, defaultRotate = true, start } = opts;
  const first = start ?? pages[0]?.id ?? '';
  const [page, setPageState] = useState(first);
  // تنظیمِ درون‌برنامه اگر ست شده حاکم است؛ وگرنه ترجیعِ سیستم، وگرنه خواستۀ مصرف‌کننده
  const [userPaused, setUserPaused] = useState(() => {
    const stored = storageKey ? readMotionSetting(storageKey) : null;
    const wanted = stored ?? (!prefersReducedMotion() && defaultRotate);
    return !wanted;
  });
  const [hovered, setHovered] = useState(false);

  const rotating = !userPaused && !hovered && pages.length > 1;

  // index درِ ref می‌نشیند تا تایمر هر بار بازسازی نشود و پرش به ابتدا رخ ندهد
  const idxRef = useRef(Math.max(0, pages.findIndex((p) => p.id === page)));
  idxRef.current = Math.max(0, pages.findIndex((p) => p.id === page));

  const setPage = useCallback((id: string) => setPageState(id), []);
  const next = useCallback(() => {
    const i = idxRef.current;
    const n = pages.length;
    if (!n) return;
    setPageState(pages[(i + 1) % n].id);
  }, [pages]);

  useEffect(() => {
    if (!rotating) return;
    const t = window.setInterval(next, intervalMs);
    return () => window.clearInterval(t);
  }, [rotating, intervalMs, next]);

  const toggle = useCallback(() => {
    setUserPaused((prev) => {
      const nowPaused = !prev;
      if (storageKey) writeMotionSetting(storageKey, !nowPaused);
      return nowPaused;
    });
  }, [storageKey]);

  return {
    page,
    index: Math.max(0, pages.findIndex((p) => p.id === page)),
    rotating,
    userPaused,
    setPage,
    next,
    toggle,
    pauseProps: {
      onMouseEnter: () => setHovered(true),
      onMouseLeave: () => setHovered(false),
      // focus (صفحه‌کلید) هم باید مکث بسازد؛ blurِ داخلِ ظرف نه -- بنابراین
      // onFocus/onBlur با captureِ رویدادِ کاپچرِ خودِ ظرف کار می‌کند
      onFocus: () => setHovered(true),
      onBlur: () => setHovered(false),
    },
  };
}

/** تب‌هایِ صفحّه -- همان شکلِ بازرسی نماد: grid، aria-current="page"، بی‌refetch */
export function PageTabs({
  pages,
  page,
  onSelect,
  testId,
  ariaLabel,
  className = 'grid-cols-2',
}: {
  pages: readonly RotatorPage[];
  page: string;
  onSelect: (id: string) => void;
  testId: string;
  ariaLabel: string;
  className?: string;
}) {
  return (
    <nav
      aria-label={ariaLabel}
      data-testid={testId}
      className={`grid gap-1 ${className}`}
    >
      {pages.map((p) => (
        <button
          key={p.id}
          type="button"
          aria-current={page === p.id ? 'page' : undefined}
          data-testid={`${testId}-${p.id}`}
          title={p.hint}
          onClick={() => onSelect(p.id)}
          className={`truncate rounded-md border px-2 py-1 text-[10px] font-bold transition-colors ${
            page === p.id
              ? 'border-accent-blue/60 bg-accent-blue/15 text-accent-blue'
              : 'border-border-c/60 bg-bg-primary text-text-muted hover:text-text-primary'
          }`}
        >
          {p.label}
        </button>
      ))}
    </nav>
  );
}

/** کلیدِ توقف/ادامه -- با متنِ روشن که چه اتفاقی دارد می‌افتد */
export function RotateToggle({
  rotator,
  testId,
}: {
  rotator: RotatorState;
  testId: string;
}) {
  return (
    <button
      type="button"
      onClick={rotator.toggle}
      aria-pressed={!rotator.userPaused}
      data-testid={testId}
      title={
        rotator.userPaused
          ? 'چرخشِ خودکار خاموش است -- روشنش کنید'
          : 'چرخشِ خودکار روشن است؛ نشانگر را رویش ببرید تا مکث کند'
      }
      className={`shrink-0 rounded-md border px-1.5 py-0.5 text-3xs font-bold transition-colors ${
        rotator.userPaused
          ? 'border-border-c/60 text-text-muted hover:text-text-primary'
          : 'border-accent-blue/50 bg-accent-blue/10 text-accent-blue'
      }`}
    >
      {rotator.userPaused ? 'چرخش: خاموش' : 'چرخش: روشن'}
    </button>
  );
}

/** نقطه‌هایِ موقعیت -- «کجایِ گردشیم» بی‌بازکردنِ هیچ پنلی */
export function PageDots({
  pages,
  index,
  testId,
}: {
  pages: readonly RotatorPage[];
  index: number;
  testId: string;
}) {
  return (
    <span className="flex items-center gap-1" data-testid={testId} aria-hidden="true">
      {pages.map((p, i) => (
        <span
          key={p.id}
          className={`inline-block size-1 rounded-full ${
            i === index ? 'bg-accent-blue' : 'bg-border-c'
          }`}
        />
      ))}
    </span>
  );
}
