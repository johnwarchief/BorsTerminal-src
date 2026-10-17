// app/components/MobileNav.tsx -- نوارِ پایینِ گوشی (بندِ ۲.۲/۲.۳ مأموریتِ System ۲)
//
// چرا اصلاً ساخته شد: درِ اینِ منبع (شاخه وِ `main`) هیچِ نوارِ پایینِ ثابتی وجود
// نداشت -- ناوبریِ موبایل همانِ ریلِ آیکونِ چپِ سایدبار بود باِ لینک‌هایِ ۳۸×۴۱px
// وِ پالتِ فرمانِ فقط‌کیبوردی (Ctrl+K). بندِ ۲.۲ «نوارِ پایین را جمع‌وجورتر کن»
// را نمی‌شد رویِ چیزی که نیست اعمال کرد، پسِ اینِ اجزا ساخته شد وِ درِ گزارش باِ
// همانِ صداقت ثبت می‌شود: اینِ یکِ «افزودن» است، نه «کوچک‌کردنِ موجود».
//
// سه قانونِ طراحی که درِ کد نگهبانی می‌مانند:
//  ۱) هیچِ مقصدی حذف نمی‌شود: چهارِ first-class + «بیشتر» که همانِ NAV_SECTIONS
//     خودِ سایدبار را می‌شمارد. یکِ مرجعِ ناوبری، دوِ نما -- اگرِ روزی مقصدی ازِ
//     سایدبار برود، اینجا هم می‌رود (آزمونِ `mobile-nav.spec.tsx` همین را می‌پاید).
//  ۲) کفِ لمسی: هرِ آیتم `min-h-[44px]` وِ متنِ زیرِ آیکون، پسِ «اندازۀِ لمس کافی
//     بماند» باِ «ارتفاعِ کلی کمتر» درِ یکِ تنفسِ ۵۶px جمع می‌شود.
//  ۳) safe area: `env(safe-area-inset-bottom)` رویِ paddingِ پایینِ نوار وِ
//     `viewport-fit=cover` درِ `index.html` -- بی‌این دو، درِ گوشیِ ناچ‌دار
//     آخرینِ سطرِ محتوا زیرِ نوار می‌ماند (همان چیزی که بندِ ۲.۲ منع می‌کند).
import { useEffect, useState } from 'react';
import { NavLink, useLocation } from 'react-router';
import { NAV_SECTIONS } from './Sidebar';
import { AccountControls } from './AccountControls';
import { useMediaQuery } from '@shared/lib/useMediaQuery';
import { MEDIA_MOBILE } from '@shared/lib/breakpoints';
import { ChevronIcon, SearchIcon } from '@shared/components/Icons';
import { PALETTE_OPEN_EVENT } from './CommandPalette';

type NavItem = { to: string; label: string; end?: boolean; sub?: boolean;
  icon?: React.ComponentType<{ size?: number; className?: string }> };

const PRIMARY_LABELS = ['وضعیت بازار', 'تابلوخوانی', 'تکنیکال', 'دیده‌بان بازار'];

/** آیتم‌هایِ ناوبری ازِ خودِ سایدبار خوانده می‌شوند، نه ازِ فهرستِ دومی */
function collect(): { primary: NavItem[]; rest: NavItem[] } {
  const all: NavItem[] = NAV_SECTIONS.flatMap((sec) => sec.items.map((i) => ({
    to: i.to, label: i.label, icon: i.icon, end: i.end, sub: i.sub,
  })));
  const primary = PRIMARY_LABELS
    .map((label) => all.find((i) => i.label === label))
    .filter((i): i is NavItem => !!i);
  return { primary, rest: all.filter((i) => !primary.includes(i)) };
}

export function MobileNav() {
  const isMobile = useMediaQuery(MEDIA_MOBILE);
  const [more, setMore] = useState(false);
  const location = useLocation();
  const { primary, rest } = collect();

  useEffect(() => {
    if (!more) return undefined;
    const off = (e: KeyboardEvent) => { if (e.key === 'Escape') setMore(false); };
    window.addEventListener('keydown', off);
    return () => window.removeEventListener('keydown', off);
  }, [more]);

  // مسیرِ عوض‌شده (حتیِ ازِ پالت/لینکِ درونِ صفحه) کشویِ «بیشتر» را می‌بندد، تاِ
  // نوارِ پایین همیشه همانِ چیزی را نشان دهد که کاربر درِ آنِ لحظه می‌بیند.
  useEffect(() => { setMore(false); }, [location.pathname]);

  if (!isMobile) return null;

  const itemCls = ({ isActive }: { isActive: boolean }) =>
    `flex min-h-[44px] flex-1 flex-col items-center justify-center gap-0.5 rounded-lg px-1 text-3xs leading-tight transition-colors ${
      isActive ? 'text-accent-blue' : 'text-text-secondary'}`;

  return (
    <>
      {more ? (
        <div
          role="presentation"
          data-testid="mobile-nav-scrim"
          onClick={() => setMore(false)}
          className="fixed inset-0 z-40 bg-black/45"
        />
      ) : null}
      <nav
        aria-label="ناوبریِ پایینِ گوشی"
        data-testid="mobile-nav"
        className="fixed inset-x-0 bottom-0 z-50 flex items-stretch gap-0.5 border-t border-border-c bg-bg-card/95 px-1 pt-1 pb-[max(0.25rem,env(safe-area-inset-bottom))] backdrop-blur"
      >
        {primary.map((i) => (
          <NavLink key={i.to} to={i.to} aria-label={i.label} className={itemCls}
                   data-testid={`mobile-nav-${i.to.replace(/\//g, '') || 'root'}`}>
            {i.icon ? <i.icon size={18} /> : <ChevronIcon size={18} />}
            <span className="max-w-[68px] truncate">{i.label}</span>
          </NavLink>
        ))}
        <button
          type="button"
          onClick={() => setMore((v) => !v)}
          aria-expanded={more}
          aria-controls="mobile-nav-sheet"
          data-testid="mobile-nav-more"
          className={`flex min-h-[44px] flex-1 flex-col items-center justify-center gap-0.5 rounded-lg text-3xs leading-tight ${
            more ? 'text-accent-blue' : 'text-text-secondary'}`}
        >
          <ChevronIcon size={18} />
          <span>بیشتر</span>
        </button>
      </nav>

      {more ? (
        <div
          id="mobile-nav-sheet"
          role="dialog"
          aria-modal="true"
          aria-label="همۀِ مسیرها"
          className="fixed inset-x-0 bottom-0 z-50 max-h-[62vh] overflow-y-auto rounded-t-2xl border border-border-c bg-bg-card px-2 pt-2 pb-[max(4.5rem,calc(4rem+env(safe-area-inset-bottom)))]"
        >
          <div className="mb-1 flex items-center justify-between">
            <span className="text-2xs font-black text-text-primary">همۀِ مسیرها</span>
            <button type="button" onClick={() => setMore(false)} data-testid="mobile-nav-close"
                    className="min-h-[44px] rounded-lg px-3 text-2xs font-bold text-text-secondary">
              بستن
            </button>
          </div>
          <div className="grid grid-cols-2 gap-1">
            {rest.map((i) => (
              <NavLink key={i.to} to={i.to} aria-label={i.label} className={itemCls}
                       data-testid={`mobile-nav-more-${i.to.replace(/\//g, '')}`}>
                {i.icon ? <i.icon size={18} /> : <ChevronIcon size={18} />}
                <span className="truncate">{i.label}</span>
              </NavLink>
            ))}
            <button
              type="button"
              data-testid="mobile-nav-palette"
              onClick={() => window.dispatchEvent(new Event(PALETTE_OPEN_EVENT))}
              className="flex min-h-[44px] flex-col items-center justify-center gap-0.5 rounded-lg text-3xs text-text-secondary"
            >
              <SearchIcon size={18} />
              <span>جست‌وجو</span>
            </button>
          </div>
          {/* سایدبار درِ گوشی نشان داده نمی‌شود، پسِ اینِ چهارِ کنترل هم ازِ همانِ
              گره‌ای می‌آیند که دسکتاق استفاده می‌کند (بی‌دومینِ نسخۀِ رفتار). */}
          <AccountControls layout="sheet" />
        </div>
      ) : null}
    </>
  );
}
