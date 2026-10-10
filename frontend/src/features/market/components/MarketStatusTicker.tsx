// features/market/components/MarketStatusTicker.tsx -- خلاصۀ چرخشیِ وضعیت بازار
//
// رأیِ مأموریت: کاربر باید خلاصۀ وضعیت را بی‌بازکردنِ تک‌تکِ پنل‌ها سریع ببیند،
// ولی چرخشِ خودکار نباید او را مجبور به دنبال‌کردنِ متنِ متحرک کند و دسترسیِ دستی
// به همه‌چیز باید بماند. پس: یک نوارِ کوتاه که میانِ پنج صفحۀ «واقعیتِ کلیدی»
// می‌گردد، تب‌هایش همیشه دیدنی‌اند، با hover/focus/کلیدِ توقف مکث می‌کند، و بعدِ
// هر تعامل از همان‌جا ادامه می‌دهد (نه از ابتدا).
//
// هیچ درخواستِ تازه‌ای نمی‌زند: هر پنج صفحّه از همان کوئری‌هایی خوانده می‌شود که
// صفحۀ وضعیت بالفعل باز کرده (market-pulse / histogram / clientsplit / thermometer).
// TanStack Query کلیدِ مشترک را یکی می‌شمارد، پس افزودنِ این نوار مصرفِ شبکه را
// بالا نمی‌برد -- و این خودش شرطِ هفتمِ پذیرش است.
import { useMemo } from 'react';
import { toFaDigits, fmtInt, fmtPct, fmtHemmat } from '@shared/lib/fmt';
import { PageDots, PageTabs, RotateToggle, usePageRotator, type RotatorPage } from '@shared/components/PageRotator';
import { pulseDepth, pulseEqAll, pulseHemat, pulseIndex, pulseTradeValueAllMarketHemat, type MarketPulseData } from '../api/useMarketPulse';
import type { ClientSplitFeed, HistogramFeed } from '../api/useMarketStatusFeed';

const PAGES: readonly RotatorPage[] = [
  { id: 'breadth', label: 'پهنای بازار', hint: 'چند نماد مثبت، چند منفی، چند سنجیده نشد' },
  { id: 'flow', label: 'جریان پول', hint: 'سرانهٔ خرید و فروشِ حقیقی و قدرت خریدار' },
  { id: 'value', label: 'شاخص و ارزش', hint: 'شاخص کل، گردش امروز و همتِ بازار' },
  { id: 'queues', label: 'صف‌ها', hint: 'تعادل ارزش صف خرید و فروش' },
  { id: 'quality', label: 'کیفیتِ داده', hint: 'چند ردیف سنجیده شد و چند نه' },
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

export function MarketStatusTicker({
  pulse,
  histogram,
  split,
}: {
  pulse: MarketPulseData | null | undefined;
  histogram: HistogramFeed | null | undefined;
  split: ClientSplitFeed | null | undefined;
}) {
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

  const body = useMemo(() => {
    switch (rotator.page) {
      case 'breadth':
        return (
          <>
            <Fact label="مثبت" value={orDash(thermo?.positive)} tone="pos" />
            <Fact label="منفی" value={orDash(thermo?.negative)} tone="neg" />
            <Fact label="خنثی" value={orDash(thermo?.zero)} />
            <Fact label="بی‌درصد" value={orDash(thermo?.nodata)} tone="muted" />
          </>
        );
      case 'flow':
        return (
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
              value={orDash(split?.money_flow_b_toman, (v) => `${fmtInt(v)} میلیارد`) }
              tone={split?.money_flow_b_toman != null && split.money_flow_b_toman < 0 ? 'neg' : 'pos'}
            />
          </>
        );
      case 'value':
        return (
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
        );
      case 'queues':
        return depth ? (
          <>
            <Fact label="ارزش صف خرید" value={orDash(depth.buyBt, (v) => `${fmtInt(v)} م.ت`)} tone="pos" />
            <Fact label="ارزش صف فروش" value={orDash(depth.sellBt, (v) => `${fmtInt(v)} م.ت`)} tone="neg" />
            <Fact label="نسبت" value={orDash(depth.ratio, (v) => `${toFaDigits(v.toFixed(2))}×`)} />
            <Fact
              label="نماد در صف"
              value={`${orDash(depth.buyCount)} / ${orDash(depth.sellCount)}`}
            />
          </>
        ) : (
          <span className="text-2xs text-text-muted" data-testid="ticker-no-depth">
            عمقِ صف برایِ این نشست نرسید — «بی‌داده» یعنی اندازه‌گیری ممکن نبود، نه صفِ خالی.
          </span>
        );
      default:
        return (
          <>
            <Fact label="سنجیده‌شده" value={orDash(histogram?.known)} />
            <Fact label="بی‌درصد" value={orDash(histogram?.nodata)} tone="muted" />
            <Fact label="بی‌معامله" value={orDash(histogram?.not_traded)} tone="muted" />
            <Fact label="جامعۀ نمادها" value={orDash(thermo ? (thermo.positive ?? 0) + (thermo.negative ?? 0) + (thermo.zero ?? 0) + (thermo.nodata ?? 0) + (thermo.not_traded ?? 0) : null)} />
          </>
        );
    }
  }, [rotator.page, thermo, eq, idx, tradeHemat, hemat, depth, split, histogram]);

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
          onSelect={rotator.setPage}
          testId="ticker-tabs"
          ariaLabel="صفحّه‌هایِ خلاصۀ وضعیت بازار"
          className="grid-cols-2 sm:grid-cols-5"
        />
        <div className="flex items-center gap-2">
          <PageDots pages={PAGES} index={rotator.index} testId="ticker-dots" />
          <RotateToggle rotator={rotator} testId="ticker-rotate-toggle" />
        </div>
      </div>
      <div className="flex min-h-[22px] flex-wrap items-baseline gap-x-4 gap-y-1" data-testid="ticker-body">
        <span className="shrink-0 text-2xs font-black text-text-primary">{active.label}</span>
        {body}
      </div>
    </section>
  );
}
