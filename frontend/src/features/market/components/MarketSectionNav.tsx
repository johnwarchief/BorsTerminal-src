// features/market/components/MarketSectionNav.tsx -- ناوبریِ بخش‌های «وضعیت بازار»
//
// چرا nav و نه اسکرولِ بی‌سر و ته: مرجع (Binder1) سیزده صفحۀ *مجزا* است و
// BorsTerminal آن‌ها را در یک تبِ چندبخشی جمع می‌کند (رأیِ مرحلۀ ۱). بدونِ
// پرشِ بخش، «همۀ ۱۳ صفحه در این تب‌اند» فقط یک ادعاست؛ با آن، هر صفحه به یک
// لنگرِ قابل آزمون تبدیل می‌شود که تستِ Playwright همان را می‌زند.
//
// نشانی هاش‌روتر است (/#/market-status)، پس بخش‌ها پارامترِ query نمی‌گیرند و
// scroll به element انجام می‌شود — با scroll-margin که سربرگِ چسبان رویِ عنوان
// نیفتد.
import { useEffect, useRef, useState } from 'react';
import { toFaDigits } from '@shared/lib/fmt';

export type MarketSection = {
  id: string;
  label: string;
  /** شمارۀ صفحۀ مرجع — تا ماتریس تحویل با صفحه یکی خوانده شود */
  pages: number[];
};

export function MarketSectionNav({
  sections,
  onActiveChange,
}: {
  sections: MarketSection[];
  onActiveChange?: (id: string) => void;
}) {
  const [active, setActive] = useState(sections[0]?.id ?? '');
  const seen = useRef(new Set<string>());

  useEffect(() => {
    // IntersectionObserver به‌جای listen کردنِ scroll: در ۷۶۸ پیکسلِ ارتفاع،
    // listener هر فریم اجرا می‌شد و همان افتِ فریمی را می‌ساخت که قاعدۀ
    // «رندرِ روان» ردّش می‌کند.
    const els = sections
      .map((s) => document.getElementById(s.id))
      .filter((e): e is HTMLElement => !!e);
    if (!els.length) return;
    const io = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        const id = visible[0]?.target.id;
        if (id && id !== active) {
          setActive(id);
          onActiveChange?.(id);
        }
      },
      { rootMargin: '-96px 0px -55% 0px', threshold: [0.01, 0.25, 0.5] },
    );
    for (const el of els) io.observe(el);
    return () => io.disconnect();
  }, [sections, active, onActiveChange]);

  const jump = (id: string) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.scrollIntoView({ behavior: seen.current.has(id) ? 'smooth' : 'auto', block: 'start' });
    seen.current.add(id);
    setActive(id);
    onActiveChange?.(id);
  };

  return (
    <nav
      data-testid="market-section-nav"
      aria-label="بخش‌های وضعیت بازار"
      className="sticky top-[var(--chrome-h)] z-20 -mx-2 border-b border-border-c bg-bg-primary/95 px-2 py-1.5 backdrop-blur"
    >
      {/* تک‌ردیفه با اسکرول افقی: با flex-wrap روی ۱۳۶۶ (و وقتی داور نماد باز است
          و ستون محتوا ۹۵۸px می‌شود) دو خط می‌شد و ارتفاعِ چسبانِ آن نامعلوم
          می‌شد؛ نامتحرک بودن ارتفاع، شرطِ درست‌کارکردنِ scroll-margin عنوان‌ها
          است. دکمه‌ها پاک نمی‌شوند، فقط افقی جابه‌جا می‌شوند. */}
      <ul className="flex flex-nowrap items-center gap-1 overflow-x-auto overscroll-x-contain scrollbar-none">
        {sections.map((s) => {
          const on = active === s.id;
          return (
            <li key={s.id} className="shrink-0">
              <button
                type="button"
                id={`market-section-btn-${s.id}`}
                data-testid={`market-section-${s.id}`}
                aria-current={on ? 'true' : undefined}
                onClick={() => jump(s.id)}
                className={`rounded-full border px-2.5 py-1 text-2xs font-bold transition-colors ${
                  on
                    ? 'border-accent-blue bg-accent-blue/15 text-accent-blue'
                    : 'border-border-c bg-bg-card text-text-secondary hover:text-accent-blue'
                }`}
              >
                {s.label}
                <span className="num-text ms-1 text-3xs text-text-muted">
                  {s.pages.map((p) => toFaDigits(p)).join('·')}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** تیترِ میانیِ هر بخش: شمارۀ صفحۀ مرجع را کنارِ نام نگه می‌دارد */
export function SectionHeading({
  id,
  title,
  pages,
  desc,
}: {
  id: string;
  title: string;
  pages: number[];
  desc?: string;
}) {
  return (
    <div
      id={id}
      data-testid={`section-heading-${id}`}
      className="flex scroll-mt-[calc(var(--chrome-h)+2.875rem)] flex-wrap items-baseline gap-x-2 gap-y-0.5 pt-1"
    >
      <h2 className="text-sm font-black text-text-primary">{title}</h2>
      <span className="num-text rounded border border-border-c bg-bg-card px-1 text-3xs text-text-muted">
        مرجع: {pages.map((p) => toFaDigits(p)).join('، ')}
      </span>
      {desc ? <p className="text-3xs text-text-muted">{desc}</p> : null}
    </div>
  );
}
