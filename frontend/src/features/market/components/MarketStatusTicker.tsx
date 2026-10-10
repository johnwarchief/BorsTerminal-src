// features/market/components/MarketStatusTicker.tsx -- خلاصۀ چرخشیِ وضعیت بازار
//
// رأیِ مأموریت: کاربر باید خلاصۀ وضعیت را بی‌بازکردنِ تک‌تکِ پنل‌ها سریع ببیند،
// ولی چرخشِ خودکار نباید او را مجبور به دنبال‌کردنِ متنِ متحرک کند و دسترسیِ دستی
// به همه‌چیز باید بماند. پس: یک نوارِ کوتاه که میانِ پنج صفحۀ «واقعیتِ کلیدی»
// می‌گردد، تب‌هایش همیشه دیدنی‌اند، با hover/focus/کلیدِ توقف مکث می‌کند، و بعدِ
// هر تعامل از همان‌جا ادامه می‌دهد (نه از ابتدا).
//
// هیچ درخواستِ تازه‌ای نمی‌زند: هر چهار صفحّه از همان کوئری‌هایی خوانده می‌شود که
// صفحۀ وضعیت بالفعل باز کرده (market-pulse / clientsplit).
// TanStack Query کلیدِ مشترک را یکی می‌شمارد، پس افزودنِ این نوار مصرفِ شبکه را
// بالا نمی‌برد -- و این خودش شرطِ هفتمِ پذیرش است.
import { useEffect, useMemo, useState } from 'react';
import { toFaDigits, fmtInt, fmtPct, fmtHemmat } from '@shared/lib/fmt';
import { MarqueeTrack } from '@shared/components/MarqueeTrack';
import { PageDots, PageTabs, RotateToggle, prefersReducedMotion, usePageRotator, type RotatorPage } from '@shared/components/PageRotator';
import { pulseDepth, pulseEqAll, pulseHemat, pulseIndex, pulseTradeValueAllMarketHemat, type MarketPulseData } from '../api/useMarketPulse';
import type { ClientSplitFeed } from '../api/useMarketStatusFeed';

const PAGES: readonly RotatorPage[] = [
  { id: 'breadth', label: 'پهنای بازار', hint: 'چند نماد مثبت، چند منفی، چند سنجیده نشد' },
  { id: 'flow', label: 'جریان پول', hint: 'سرانهٔ خرید و فروشِ حقیقی و قدرت خریدار' },
  { id: 'value', label: 'شاخص و ارزش', hint: 'شاخص کل، گردش امروز و همتِ بازار' },
  { id: 'queues', label: 'صف‌ها', hint: 'تعادل ارزش صف خرید و فروش' },
];

/** یک سطرِ «عنوان: مقدار» -- نبودِ مقدار خط تیره است، نه صفر */
function Fact({ label, value, tone }: { label: string; value: string; tone?: 'pos' | 'neg' | 'muted' }) {
  const toneCls = tone === 'pos' ? 'text-accent-green' : tone === 'neg' ? 'text-accent-red' : 'text-text-primary';
  return (
    <span className="flex min-w-0 items-baseline gap-1 text-2xs">
      <span className="shrink-0 text-text-muted">{label}</span>
      <span className={`num truncate font-black ${toneCls}`} data-testid={`ticker-fact-${label}`}>
        {value}
      </span>
    </span>
  );
}

function orDash(v: number | null | undefined, fmt: (n: number) => string = fmtInt): string {
  return typeof v === 'number' && Number.isFinite(v) ? fmt(v) : '—';
}

type TickerMode = 'continuous' | 'paged';
const MODE_KEY = 'market.status.ticker.mode.v1';

function readMode(): TickerMode {
  try {
    const v = window.localStorage.getItem(MODE_KEY);
    if (v === 'paged' || v === 'continuous') return v;
  } catch {
    /* بی‌localStorage یعنی یادش نمی‌ماند؛ پیش‌فرض پایین می‌نشیند */
  }
  // پیش‌فرض: پیوسته، مگر اینکه سیستم کاهشِ حرکت بخواهد
  return prefersReducedMotion() ? 'paged' : 'continuous';
}

export function MarketStatusTicker({
  pulse,
  split,
}: {
  pulse: MarketPulseData | null | undefined;
  split: ClientSplitFeed | null | undefined;
}) {
  const [mode, setMode] = useState<TickerMode>(readMode);
  useEffect(() => {
    try {
      window.localStorage.setItem(MODE_KEY, mode);
    } catch {
      /* بی‌localStorage فقط یعنی یادش نمی‌ماند */
    }
  }, [mode]);

  const rotator = usePageRotator({
    pages: PAGES,
    intervalMs: 6000,
    storageKey: 'market.status.ticker.rotate.v1',
  });

  const thermo = pulse?.thermometer ?? null;
  const eq = pulseEqAll(pulse);
  const depth = pulseDepth(pulse);
  const idx = pulseIndex(pulse);
  const hemat = pulseHemat(pulse);
  const tradeHemat = pulseTradeValueAllMarketHemat(pulse);

  /** هر چهار صفحّه یک گروهِ «برچسب + واقعیت‌ها» است؛ حالتِ پیوسته همان گروه‌ها
   *  را درِ یک نوارِ روان می‌چیند، پس عددِ دوم یا محاسبۀِ دومی ساخته نمی‌شود. */
  const groups = useMemo(() => {
    const g: Record<string, React.ReactNode> = {
      breadth: (
        <>
          <Fact label="مثبت" value={orDash(thermo?.positive)} tone="pos" />
          <Fact label="منفی" value={orDash(thermo?.negative)} tone="neg" />
          <Fact label="خنثی" value={orDash(thermo?.zero)} />
          <Fact label="بی‌درصد" value={orDash(thermo?.nodata)} tone="muted" />
        </>
      ),
      flow: (
        <>
          <Fact label="خرید حقیقی" value={orDash(eq?.pcBuy, (v) => `${fmtInt(v)} م.ت`)} />
          <Fact label="فروش حقیقی" value={orDash(eq?.pcSell, (v) => `${fmtInt(v)} م.ت`)} />
          <Fact
            label="قدرت خریدار"
            value={orDash(eq?.power, (v) => `${toFaDigits(v.toFixed(2))}×`)}
            tone={eq?.power != null && eq.power >= 1.5 ? 'pos' : eq?.power != null && eq.power < 1 ? 'neg' : undefined}
          />
          <Fact
            label="جریانِ کل"
            value={orDash(split?.money_flow_b_toman, (v) => `${fmtInt(v)} میلیارد`)}
            tone={split?.money_flow_b_toman != null && split.money_flow_b_toman < 0 ? 'neg' : 'pos'}
          />
        </>
      ),
      value: (
        <>
          <Fact label="شاخص کل" value={orDash(idx?.last, (v) => fmtInt(Math.round(v)))} />
          <Fact
            label="تغییر"
            value={idx?.pct != null ? fmtPct(idx.pct) : '—'}
            tone={idx?.pct != null && idx.pct < 0 ? 'neg' : 'pos'}
          />
          <Fact label="گردش امروز" value={tradeHemat != null ? `${toFaDigits(tradeHemat.toFixed(2))} همت` : '—'} />
          <Fact label="ارزش بازار" value={hemat?.value != null ? fmtHemmat(hemat.value * 1e10) : '—'} />
        </>
      ),
      queues: depth ? (
        <>
          <Fact label="ارزش صف خرید" value={orDash(depth.buyBt, (v) => `${fmtInt(v)} م.ت`)} tone="pos" />
          <Fact label="ارزش صف فروش" value={orDash(depth.sellBt, (v) => `${fmtInt(v)} م.ت`)} tone="neg" />
          <Fact label="نسبت" value={orDash(depth.ratio, (v) => `${toFaDigits(v.toFixed(2))}×`)} />
          <Fact label="نماد در صف" value={`${orDash(depth.buyCount)} / ${orDash(depth.sellCount)}`} />
        </>
      ) : (
        <span className="text-2xs text-text-muted" data-testid="ticker-no-depth">
          عمقِ صف برایِ این نشست نرسید — «بی‌داده» یعنی اندازه‌گیری ممکن نبود، نه صفِ خالی.
        </span>
      ),
    };
    return g;
  }, [thermo, eq, idx, tradeHemat, hemat, depth, split]);

  const body = groups[rotator.page] ?? groups.breadth;

  const active = PAGES.find((p) => p.id === rotator.page) ?? PAGES[0];

  return (
    <section
      data-testid="status-ticker"
      className="glass-panel flex min-w-0 flex-col gap-1.5 rounded-xl border border-border-c p-2.5"
      {...rotator.pauseProps}
    >
      <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
        <PageTabs
          pages={PAGES}
          page={rotator.page}
          onSelect={(id) => { rotator.setPage(id); setMode('paged'); }}
          testId="ticker-tabs"
          ariaLabel="صفحّه‌هایِ خلاصۀ وضعیت بازار"
          className="grid-cols-2 sm:grid-cols-4"
        />
        <div className="flex items-center gap-2">
          <ModeToggle mode={mode} onMode={setMode} />
          {mode === 'paged' ? <PageDots pages={PAGES} index={rotator.index} testId="ticker-dots" /> : null}
          <RotateToggle rotator={rotator} testId="ticker-rotate-toggle" />
        </div>
      </div>

      {mode === 'continuous' ? (
        <div className="min-h-[22px]" data-testid="ticker-continuous">
          <MarqueeTrack
            paused={!rotator.rotating}
            speedPxPerS={42}
            testId="ticker-marquee"
          >
            {PAGES.map((pg) => (
              <span key={pg.id} className="flex shrink-0 items-baseline gap-x-4"
                    data-testid={`ticker-group-${pg.id}`}>
                <span className="shrink-0 text-2xs font-black text-text-primary">{pg.label}</span>
                {groups[pg.id]}
              </span>
            ))}
          </MarqueeTrack>
        </div>
      ) : (
        <div className="flex min-h-[22px] flex-wrap items-baseline gap-x-4 gap-y-1" data-testid="ticker-body">
          <span className="shrink-0 text-2xs font-black text-text-primary">{active.label}</span>
          {body}
        </div>
      )}
    </section>
  );
}

/** «پیوسته / صفحه‌ای» — انتخابِ خودِ کاربر بر تنظیمِ چرخش حاکم نیست، مکمل آن
 *  است: درِ حالتِ پیوسته همان `rotating` نوار را متوقف می‌کند (hover، focus،
 *  دکمۀ توقف و کاهشِ حرکتِ سیستم). */
function ModeToggle({ mode, onMode }: { mode: TickerMode; onMode: (m: TickerMode) => void }) {
  return (
    <button
      type="button"
      data-testid="ticker-mode-toggle"
      aria-pressed={mode === 'continuous'}
      onClick={() => onMode(mode === 'continuous' ? 'paged' : 'continuous')}
      className="rounded-md border border-border-c/60 bg-bg-primary px-1.5 py-0.5 text-3xs font-bold text-text-muted transition-colors hover:text-text-primary"
      title="پیوسته: نوار آرام می‌گردد و همهٔ گروه‌ها پشتِ هم می‌آیند. صفحه‌ای: یک گروه درِ میانِ صفحه‌ها."
    >
      {mode === 'continuous' ? 'پیوسته' : 'صفحه‌ای'}
    </button>
  );
}
