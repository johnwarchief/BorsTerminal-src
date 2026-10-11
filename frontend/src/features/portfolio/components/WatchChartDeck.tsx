// features/portfolio/components/WatchChartDeck.tsx — کارتِ نمودارِ چندصفحۀِ دیده‌بان
//
// چرا: زیرِ جدولِ «دیده‌بان بازار» فقط یک کارتِ نمودار بود و آن یک کارت، نمودارِ
// یک نماد را نشان می‌داد — برایِ رصدِ ده‌ها نماد باید بالا و پایین می‌رفتید و هیچ
// شاخصِ بنیادی‌ای کنارِ نمودار نبود. رأیِ مالک: کارتِ نمودار چندصفحهایِ
// قابلِ اسکرول شود و درِ هر صفحه دو شاخصِ بنیادی جا بگیرد؛ شاخصِ ۵ درِ کارتِ
// تنها نمی‌نشیند، بلکه کنارِ ۳ و ۴ درِ ورقۀِ دومِ همان نماد می‌آید.
//
// هر نماد دو ورقه دارد: ۱) نمودار + رشد فروش + EPSِ سه‌ساله  ۲) نمودار + حاشیه
// ناخالص + فروش÷ارزش + نرخ‌گذاری. بی‌این تقسیم، پنج کاشی درِ یک کارت یا یک
// کاشی درِ کارتِ تنها می‌افتاد — هر دو را خودِ رأی رد کرده است.
//
// داده: نمودار از همان `useWatchCandles`ِ پیشین (`/api/chart/{symbol}`) و پنج
// شاخص از همان `useFtsCard`ِ کارتِ بنیادی (`/api/fundamental/{symbol}`) — نه
// فرمولِ دوم درِ فرانت. فقط ورقۀِ دیدنی mount می‌شود، پس فهرستِ شصت‌نمادی
// شصت درخواستِ بنیادی نمی‌سازد؛ هر نماد یک‌بار درِ ده دقیقه کش می‌ماند.
import { useEffect, useMemo, useState } from 'react';
import { toFaDigits } from '@shared/lib/fmt';
import { FTS_LABEL } from '@shared/lib/ftsLabels';
import { useFtsCard } from '@features/fundamental/api/useFtsCard';
import { WatchMiniChart } from './WatchMiniChart';

/** دو ورقهٔ هر نماد — شمارهٔ شاخص‌ها عینِ کلیدهایِ `indicators` درِ پاسخ است */
const PARTS: readonly (readonly string[])[] = [['1', '2'], ['3', '4', '5']];

const LABEL_KEY: Record<string, string> = {
  '1': '1_growth', '2': '2_eps_trend', '3': '3_gross_margin',
  '4': '4_sales_to_mcap', '5': '5_industry',
};

/** حکمِ یک شاخص از خودِ کارت: `pass` سه‌حالته است (true/false/null) و null
 *  «بی‌حکم» است، نه رد — همان قراردادی که کارتِ بنیادی رعایت می‌کند. */
function IndTile({ symbol, ind }: { symbol: string; ind: string }) {
  const q = useFtsCard(symbol);
  const rec = q.data?.indicators?.[ind as '1'];
  const verdict = q.isPending ? '…'
    : q.isError ? 'بی‌داده'
    : rec?.pass === true ? 'تأیید'
      : rec?.pass === false ? 'رد'
        : 'بی‌حکم';
  const tone = verdict === 'تأیید' ? 'border-accent-green/40 text-accent-green'
    : verdict === 'رد' ? 'border-accent-red/40 text-accent-red'
      : 'border-border-c text-text-muted';
  return (
    <span
      data-testid={`watch-ind-${symbol}-${ind}`}
      className={`inline-flex items-center gap-1.5 rounded-lg border bg-bg-card/60 px-2 py-1 text-2xs font-bold ${tone}`}
      title={`${FTS_LABEL[LABEL_KEY[ind]]} — حکم از کارتِ بنیادیِ همین نماد`}
    >
      <span className="text-text-secondary">{FTS_LABEL[LABEL_KEY[ind]]}</span>
      <span>{verdict}</span>
    </span>
  );
}

export function WatchChartDeck({ symbols, selected, onSelect }: {
  symbols: string[];
  selected: string;
  onSelect: (s: string) => void;
}) {
  // ورقه‌ها: [نماد ۰/ورقه ۰]، [نماد ۰/ورقه ۱]، [نماد ۱/ورقه ۰] …
  const pages = useMemo(
    () => symbols.flatMap((symbol) => PARTS.map((inds, part) => ({ symbol, part, inds }))),
    [symbols],
  );
  const [idx, setIdx] = useState(0);
  // نماد عوض شود (کلیک درِ جدول، گذر از قیف) — ورقه به همان نماد می‌پرد.
  useEffect(() => {
    const at = pages.findIndex((p) => p.symbol === selected);
    if (at >= 0) setIdx(at);
  }, [selected, pages]);
  const safe = pages.length ? Math.min(idx, pages.length - 1) : 0;
  const page = pages[safe];
  const go = (n: number) => {
    if (!pages.length) return;
    const next = (n + pages.length) % pages.length;
    setIdx(next);
    onSelect(pages[next].symbol);
  };

  if (!page) return null;
  return (
    <div
      className="glass-panel flex min-w-0 flex-col gap-1.5 rounded-2xl p-2.5"
      data-testid="watch-chart-deck"
      tabIndex={0}
      onKeyDown={(e) => {
        // RTL: فلشِ چپ «بعدی» است و فلشِ راست «قبلی» — همان چیزی که دستِ کاربر
        // رویِ صفحهٔ راست‌به‌چپ انتظار دارد.
        if (e.key === 'ArrowLeft') { e.preventDefault(); go(safe + 1); }
        if (e.key === 'ArrowRight') { e.preventDefault(); go(safe - 1); }
      }}
      onWheel={(e) => {
        // سوایپِ افقیِ ترک‌پد ورقه عوض می‌کند؛ اسکرولِ عمودی دست‌نخورده می‌ماند
        // تا صفحهٔ دیده‌بان همچنان با چرخ ماوس پایین برود.
        if (Math.abs(e.deltaX) < 8) return;
        go(safe + (e.deltaX < 0 ? 1 : -1));
      }}
    >
      <div className="flex flex-wrap items-center gap-1.5 text-2xs">
        <button
          type="button"
          data-testid="watch-deck-prev"
          onClick={() => go(safe - 1)}
          title="رقصۀِ قبل"
          className="rounded-md border border-border-c bg-bg-card px-1.5 py-0.5 font-bold text-text-secondary hover:text-text-primary"
        >
          ›
        </button>
        <button
          type="button"
          data-testid="watch-deck-next"
          onClick={() => go(safe + 1)}
          title="رقصۀِ بعد"
          className="rounded-md border border-border-c bg-bg-card px-1.5 py-0.5 font-bold text-text-secondary hover:text-text-primary"
        >
          ‹
        </button>
        <span className="num font-bold text-text-secondary" data-testid="watch-deck-page">
          {toFaDigits(safe + 1)} / {toFaDigits(pages.length)}
        </span>
        <span className="text-text-muted">
          ورقۀِ {toFaDigits(page.part + 1)}ِ {page.symbol || '—'}
        </span>
        <span className="ms-auto flex flex-wrap items-center gap-1">
          {symbols.map((s) => (
            <button
              key={s}
              type="button"
              data-testid={`watch-deck-jump-${s}`}
              aria-pressed={s === page.symbol}
              onClick={() => {
                const at = pages.findIndex((p) => p.symbol === s);
                if (at >= 0) { setIdx(at); onSelect(s); }
              }}
              className={`rounded-md border px-1.5 py-0.5 font-bold transition-colors ${
                s === page.symbol
                  ? 'border-accent-blue bg-accent-blue/15 text-accent-blue'
                  : 'border-border-c bg-bg-card/60 text-text-muted hover:text-text-primary'
              }`}
            >
              {s}
            </button>
          ))}
        </span>
      </div>

      <WatchMiniChart key={page.symbol} symbol={page.symbol} />

      <div className="flex flex-wrap items-center gap-1.5" data-testid="watch-deck-inds">
        {page.inds.map((ind) => <IndTile key={`${page.symbol}-${ind}`} symbol={page.symbol} ind={ind} />)}
      </div>
    </div>
  );
}

export default WatchChartDeck;
