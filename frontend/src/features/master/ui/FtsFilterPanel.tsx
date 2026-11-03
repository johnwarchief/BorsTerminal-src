// features/master/ui/FtsFilterPanel.tsx — قابِ منظمِ فیلترها، بی‌حذفِ هیچ فیلتری
//
// چیپ‌ها و پیچ‌ها همان کامپوننت‌هایِ قبلی‌اند و همان handlerها را دارند؛ این فایل
// فقط سربرگِ دسته، شمارِ فیلترِ فعال، منبعِ زنجیره، کلیدِ پاک‌کردنِ همه و
// بازشوندۀ «جزئیات» را اضافه می‌کند. هیچ فیلتر، آستانه یا presetی اینجا حذف یا
// تغییر نمی‌کند — رأیِ مالک: «رفتارِ استراتژی‌ها و presetهایِ موجود تغییر نکند».
//
// «پاک‌کردنِ همه» هم چیزِ تازه‌ای به بک‌اند نمی‌فرستد: همان `toggle` موجود را برایِ
// هر فیلترِ روشن صدا می‌زند (ترکیبِ UI، نه منطقِ تازه).
import { useState, type ReactNode } from 'react';
import { toFaDigits } from '@shared/lib/fmt';

export type FilterGroup = { key: string; label: string; hint?: string; node: ReactNode };

export function FtsFilterPanel({
  groups,
  activeCount,
  sourceLabel,
  logicLabel,
  onClearAll,
  advanced,
}: {
  groups: FilterGroup[];
  activeCount: number;
  sourceLabel: string;
  logicLabel?: string;
  onClearAll?: () => void;
  /** جزئیاتِ پیشرفته (پیچ‌ها، تنظیماتِ استراتژی) زیرِ همین بازشونده می‌ماند */
  advanced?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const live = groups.filter((g) => g.node);
  return (
    <section className="rounded-xl border border-border-c bg-bg-card/50 px-2.5 py-2"
             data-testid="fts-filter-panel" aria-label="فیلترها"
             title={[sourceLabel ? `زنجیره: ${sourceLabel}` : '', logicLabel ?? '']
               .filter(Boolean).join(' · ') || undefined}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h2 className="text-sm font-black text-text-primary">فیلترها</h2>
        <span className="num rounded-md border border-border-c bg-bg-primary/70 px-1.5 py-0.5 text-2xs font-bold text-text-secondary"
              data-testid="fts-filter-active-count"
              title="هر چیپِ روشن یکِ شرطِ اضافه بر جامعۀ غربالگری است">
          {toFaDigits(activeCount)} فیلتر فعال
        </span>
        {onClearAll && activeCount > 0 ? (
          <button type="button" onClick={onClearAll} data-testid="fts-filter-clear"
                  className="rounded-lg border border-border-c bg-bg-card px-2 py-0.5 text-2xs font-bold
                             text-text-secondary transition-colors hover:border-accent-red/60 hover:text-accent-red">
            پاک‌کردنِ انتخاب‌ها
          </button>
        ) : null}
        {advanced ? (
          <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
                  data-testid="fts-filter-advanced-toggle"
                  className="ms-auto rounded-lg border border-border-c bg-bg-card px-2 py-0.5 text-2xs font-bold
                             text-text-secondary transition-colors hover:border-accent-blue/60 hover:text-accent-blue">
            {open ? 'بستنِ جزئیات' : 'جزئیات و تنظیمات'}
          </button>
        ) : null}
      </div>

      <div className="mt-1.5 flex flex-col gap-1.5">
        {live.map((g) => (
          <div key={g.key} className="min-w-0" data-testid={`fts-filter-group-${g.key}`}>
            <p className="mb-0.5 text-2xs font-bold text-text-secondary" title={g.hint}>
              {g.label}
            </p>
            <div className="min-w-0">{g.node}</div>
          </div>
        ))}
      </div>

      {advanced && open ? (
        <div className="mt-1.5 border-t border-border-c/60 pt-1.5" data-testid="fts-filter-advanced">
          {advanced}
        </div>
      ) : null}
    </section>
  );
}

export default FtsFilterPanel;
