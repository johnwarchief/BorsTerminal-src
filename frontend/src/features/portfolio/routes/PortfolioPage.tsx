// features/portfolio/routes/PortfolioPage.tsx -- مدیریت پرتفوی (بازطراحی کامل)
// دوگانهٔ «پرتفوی هدف / پرتفوی فعلی» + چارت دونات SVG + نوار دلتا + جدول سه‌تبه.
// تمام‌عرض فقط داخل صفحه خودش (w-full max-w-none).
import { useEffect, useMemo, useState } from 'react';
import { Badge } from '@shared/components/Badge';
import { EmptyState } from '@shared/components/EmptyState';
import { RetryAction } from '@shared/components/RetryAction';
import { fmtInt, toFaDigits } from '@shared/lib/fmt';
import { FlashNum } from '@shared/components/FlashNum';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { publishSignal } from '@shared/lib/signalBus';
import { useMarketCloses, usePortfolio } from '../api/usePortfolio';
import { portfolioSignal, stopAsNumber } from '../model/portfolioSignals';
import {
  buildDelta,
  useTargetAllocation,
} from '../stores/targetAllocation';
import { TargetBanner } from '../components/TargetBanner';
import { TargetEditModal } from '../components/TargetEditModal';
import { DeltaBar } from '../components/DeltaBar';
import { useAssetValues } from '../stores/assetValues';
import { useStopLossBoard } from '../api/useStopLossBoard';
import { SymbolBasketAction, weightSourceLabel } from '../components/SymbolBasketAction';
import { SectorMatrix } from '../components/SectorMatrix';
import WatchlistSection from '../components/WatchlistSection';
import { TwinDonuts, ActualPortfolioCard } from '../components/TwinDonuts';

const STATUS_TONE = { accept: 'green', reject: 'red', monitor: 'yellow', pending: 'gray' } as const;
const STATUS_LABEL: Record<string, string> = { accept: 'نگهداری', reject: 'حذف شده', monitor: 'زیر نظر', pending: 'در انتظار' };

type BoardTab = 'portfolio' | 'monitor' | 'rejects';

/** فاصله قیمت تا حد ضرر به درصد؛ null یعنی داده ناقص */
export function distanceToStopPct(price: number | null, stop: number | null): number | null {
  if (price == null || stop == null || stop <= 0) return null;
  return ((price - stop) / stop) * 100;
}

/** برچسب وضعیت حد ضرر بر اساس فاصله قیمت */
export function stopStatusTone(dist: number | null): 'red' | 'yellow' | 'green' | 'gray' {
  if (dist == null) return 'gray';
  if (dist < 0) return 'red';
  if (dist < 5) return 'yellow';
  return 'green';
}

function faNum(x: number, digits = 1): string {
  return toFaDigits(x.toFixed(digits));
}

/** رندر پله‌های DCA — فیبو ۳۳-۴۰ و ۶۱-۷۰ + ستاپ جت؛ غیب داده ⇒ «بدون داده» */
function dcaLabel(fib1: { lo: number | null; hi: number | null } | null, fib2: { lo: number | null; hi: number | null } | null, jet: boolean | null): string {
  const parts: string[] = [];
  parts.push(fib1 != null && (fib1.lo != null || fib1.hi != null) ? `پله۱ ${faNum(fib1.lo ?? fib1.hi ?? 0, 0)}` : 'پله۱ بدون داده');
  parts.push(fib2 != null && (fib2.lo != null || fib2.hi != null) ? `پله۲ ${faNum(fib2.lo ?? fib2.hi ?? 0, 0)}` : 'پله۲ بدون داده');
  parts.push(jet === true ? 'جت ✓' : jet === false ? 'جت ✕' : 'جت بدون داده');
  return parts.join(' · ');
}

export default function PortfolioPage() {
  const symbol = useSymbolStore((s) => s.symbol);
  const setSymbol = useSymbolStore((s) => s.setSymbol);
  const portfolio = usePortfolio();
  const closes = useMarketCloses();
  const [tab, setTab] = useState<BoardTab>('portfolio');
  const [editOpen, setEditOpen] = useState(false);

  const view = useTargetAllocation((s) => s.view);
  const setView = useTargetAllocation((s) => s.setView);
  const classes = useTargetAllocation((s) => s.classes);
  const assetTotal = useAssetValues((s) => s.totalToman);
  const assetValues = useAssetValues((s) => s.values);

  const holdings = useMemo(() => portfolio.data?.portfolio ?? [], [portfolio.data]);
  const monitor = useMemo(() => portfolio.data?.monitor ?? [], [portfolio.data]);
  const rejects = useMemo(() => (portfolio.data?.decisions ?? []).filter((d) => (d.status ?? '').toLowerCase() === 'reject'), [portfolio.data]);
  const counts = portfolio.data?.counts ?? {};
  const limits = portfolio.data?.limits;

  // حد ضررها برای ردیف‌های نماد فعلی (سبد + زیر نظر)
  const boardSymbols = useMemo(() => [...holdings, ...monitor].map((h) => h.symbol), [holdings, monitor]);
  const stops = useStopLossBoard(boardSymbols);

  // سیگنال پرتفوی برای نماد انتخابی — با ظرفیت‌سنجی صنعت
  const sectorUsedPct = useMemo(() => {
    if (!symbol) return null;
    const sector = holdings.find((h) => h.symbol === symbol)?.sector ?? null;
    if (!sector) return null;
    return holdings
      .filter((h) => h.symbol !== symbol && (h.sector ?? '') === sector)
      .reduce((s, h) => s + (h.weight_eff_pct ?? 0), 0);
  }, [holdings, symbol]);

  const signal = useMemo(() => {
    if (!symbol) return null;
    const all = [...holdings, ...monitor];
    const decision = all.find((d) => d.symbol === symbol) ?? null;
    return portfolioSignal({
      symbol,
      decision,
      currentPrice: closes.data?.get(symbol) ?? null,
      sector: decision?.sector ?? null,
      sectorUsedPct,
    });
  }, [symbol, holdings, monitor, closes.data, sectorUsedPct]);

  useEffect(() => {
    if (signal) publishSignal(signal);
  }, [signal]);

  const deltaRows = useMemo(
    () =>
      buildDelta(classes, holdings, {
        classMixPct: limits?.class_mix_pct ?? null,
        basketValueToman: limits?.portfolio_value_toman ?? null,
        totalToman: assetTotal,
        valuesByClass: assetValues,
      }),
    [classes, holdings, limits?.class_mix_pct, limits?.portfolio_value_toman, assetTotal, assetValues],
  );

  if (portfolio.isLoading) return <EmptyState title="در حال دریافت سبد..." />;
  if (portfolio.isError)
    return (
      <EmptyState
        title="خطا در دریافت سبد"
        hint="اتصال بک اند را بررسی کن"
        action={<RetryAction onRetry={() => void portfolio.refetch()} testId="portfolio-retry" />}
      />
    );

  const rows = tab === 'portfolio' ? holdings : tab === 'monitor' ? monitor : rejects;
  const rowLabel = tab === 'portfolio' ? 'سبد' : tab === 'monitor' ? 'رادار زیر نظر' : 'حذف شده ها';
  const sumWeight = limits?.sum_weight_pct;
  const weightCap = limits?.weight_cap_pct;

  const tabs: { id: BoardTab; label: string; count: number }[] = [
    { id: 'portfolio', label: 'سبد', count: holdings.length },
    { id: 'monitor', label: 'زیر نظر', count: monitor.length },
    { id: 'rejects', label: 'حذف شده', count: rejects.length },
  ];

  return (
    <div className="relative flex w-full max-w-none flex-col gap-4 overflow-clip">
      {/* سوییچر دوگانه */}
      <div className="flex flex-wrap items-center gap-2" role="tablist" aria-label="انتخاب نمای پرتفوی">
        <button
          type="button"
          role="tab"
          aria-selected={view === 'target'}
          onClick={() => setView('target')}
          className={`rounded-full border px-4 py-1.5 text-xs font-bold transition-colors duration-200 ${
            view === 'target'
              ? 'border-neon-cyan/50 bg-neon-cyan/15 text-neon-cyan'
              : 'border-border-c bg-bg-card text-text-secondary hover:bg-bg-secondary hover:text-text-primary'
          }`}
        >
          پرتفوی هدف
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={view === 'current'}
          onClick={() => setView('current')}
          className={`rounded-full border px-4 py-1.5 text-xs font-bold transition-colors duration-200 ${
            view === 'current'
              ? 'border-neon-cyan/50 bg-neon-cyan/15 text-neon-cyan'
              : 'border-border-c bg-bg-card text-text-secondary hover:bg-bg-secondary hover:text-text-primary'
          }`}
        >
          پرتفوی فعلی
        </button>
      </div>

      {view === 'target' ? (
        /* ─── بخش اول: پرتفوی هدف — بدون کارت‌های عریض تکراری، جدول صنایع بالا می‌آید ─── */
        <>
          {/* پنل بالای تب: دونات هدف + سنجهٔ هم‌ترازی (دونات واقعی منحصراً در تب فعلی است) */}
          <TwinDonuts onEdit={() => setEditOpen(true)} showActual={false} />

          {/* ماتریس تخصیص صنایع سهام (state مشتق از پوزیشن‌های سبد) */}
          <SectorMatrix />

          <TargetBanner />

          <TargetEditModal open={editOpen} onClose={() => setEditOpen(false)} />
        </>
      ) : (
        /* ─── بخش دوم: پرتفوی فعلی ─── */
        <>
          {/* چارت دونات پرتفوی واقعی و درصد پر شده از کل سرمایه */}
          <ActualPortfolioCard />

          <DeltaBar rows={deltaRows} />

          <div className="flex flex-wrap items-center gap-2 text-xs">
            {/* افزودن دارایی با جستجوی نماد — نام و قیمت از سرور، وزن از تعداد (#106)
                «افزودن به سبد» حذف شد: همین کار را می‌کرد و دو تا لازم نبود (#191).
                تصمیمِ سبد در تب FTS و قیف نخبگان زده می‌شود. */}
            <SymbolBasketAction symbol="" addMode />
            <Badge tone="green">نگهداری {toFaDigits(counts.accept ?? 0)}</Badge>
            <Badge tone="yellow">زیر نظر {toFaDigits(counts.monitor ?? 0)}</Badge>
            <Badge tone="red">حذف شده {toFaDigits(counts.reject ?? 0)}</Badge>
            {sumWeight != null ? (
              <Badge tone={weightCap != null && sumWeight > weightCap ? 'orange' : 'blue'}>
                جمع وزن {toFaDigits(sumWeight)} درصد
                {limits?.weight_source ? ` · ${weightSourceLabel(limits.weight_source)}` : ''}
              </Badge>
            ) : null}
            {limits?.portfolio_value_toman ? (
              <Badge tone="blue">
                ارزش سبد <span className="num">{fmtInt(limits.portfolio_value_toman)}</span> تومان
              </Badge>
            ) : null}
            {limits?.value_missing_count ? (
              <Badge tone="gray">
                {toFaDigits(limits.value_missing_count)} ردیف تعداد ندارد — وزن خودکار حساب نمی‌شود
              </Badge>
            ) : null}
            {weightCap != null ? <Badge tone="gray">سقف وزن هر نماد {toFaDigits(weightCap)} درصد</Badge> : null}
          </div>

          {signal ? (
            <div className="glass-panel panel-in p-4">
              <div className="mb-1 flex items-center gap-2">
                <h3 className="text-sm font-black text-text-primary">سیگنال پرتفوی {symbol}</h3>
                <Badge tone="gray">{STATUS_LABEL[signal.payload.decision] ?? signal.payload.decision}</Badge>
                {signal.payload.weightPct != null ? <Badge tone="blue">وزن {toFaDigits(signal.payload.weightPct)} درصد</Badge> : null}
                {signal.payload.stopLoss != null ? <Badge tone="gray">حد ضرر {toFaDigits(signal.payload.stopLoss)}</Badge> : null}
              </div>
              <p className="text-xs leading-6 text-text-secondary">{signal.rationale}</p>
              {signal.payload.alerts.length > 0 ? (
                <ul className="mt-1.5 flex list-inside list-disc flex-col gap-0.5">
                  {signal.payload.alerts.map((a, i) => (
                    <li key={i} className="text-2xs font-bold text-accent-susp">{a}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}

          <div className="flex flex-wrap gap-2">
            {tabs.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                className={`rounded-full border px-3.5 py-1.5 text-xs font-bold transition-colors duration-200 ${
                  tab === t.id
                    ? 'border-neon-cyan/50 bg-neon-cyan/15 text-neon-cyan'
                    : 'border-border-c bg-bg-card text-text-secondary hover:bg-bg-secondary hover:text-text-primary'
                }`}
              >
                {t.label} <span className="num">({toFaDigits(t.count)})</span>
              </button>
            ))}
          </div>

          <div className="glass-panel overflow-hidden rounded-2xl">
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="bg-bg-card/70 text-start text-2xs uppercase tracking-wider text-text-secondary">
                    <th className="px-3 py-2.5 font-bold">نماد</th>
                    <th className="px-3 py-2.5 font-bold">وضعیت</th>
                    <th className="px-3 py-2.5 font-bold">وزن در سبد</th>
                    <th className="px-3 py-2.5 font-bold">تعداد</th>
                    <th className="px-3 py-2.5 font-bold">ارزش (تومان)</th>
                    <th className="px-3 py-2.5 font-bold">سود/زیان</th>
                    <th className="px-3 py-2.5 font-bold">حد ضرر تکنیکال</th>
                    <th className="px-3 py-2.5 font-bold">حد ضرر بنیادی</th>
                    <th className="px-3 py-2.5 font-bold">فاصله تا حد ضرر</th>
                    <th className="px-3 py-2.5 font-bold">پله‌های DCA</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.length === 0 ? (
                    <tr>
                      <td colSpan={10} className="px-3 py-6 text-center text-xs text-text-muted">
                        {rowLabel} خالی است
                      </td>
                    </tr>
                  ) : (
                    rows.map((h) => {
                      const stopCell = stops.map.get(h.symbol) ?? {
                        techStop: null,
                        techBasis: 'بدون داده',
                        fib1: null,
                        fib2: null,
                        jetActive: null,
                        fundStop: { margin: null, growth: null, hit: null },
                      };
                      const stop = stopAsNumber(h.stop_loss) ?? stopCell.techStop;
                      const price = closes.data?.get(h.symbol) ?? null;
                      const dist = distanceToStopPct(price, stop);
                      const distTone = stopStatusTone(dist);
                      const fundHit = stopCell.fundStop.hit;
                      const pnl = price != null && typeof h.price === 'number' && h.price > 0 ? ((price - h.price) / h.price) * 100 : null;
                      return (
                        <tr
                          key={h.symbol}
                          className={`cursor-pointer border-b border-[var(--hairline)] transition-colors duration-200 odd:bg-bg-secondary/40 hover:bg-bg-card/60 ${h.symbol === symbol ? 'bg-accent-blue/12 outline outline-1 outline-border-accent' : ''}`}
                          tabIndex={0}
                          aria-label={`انتخاب ${h.symbol} در پرتفوی`}
                          onClick={() => setSymbol(h.symbol)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault();
                              setSymbol(h.symbol);
                            }
                          }}
                        >
                          <td className="px-3 py-2.5 font-bold text-text-primary">{h.symbol}</td>
                          <td className="px-3 py-2.5">
                            <Badge tone={STATUS_TONE[(h.status ?? 'pending').toLowerCase() as keyof typeof STATUS_TONE] ?? 'gray'}>
                              {STATUS_LABEL[(h.status ?? 'pending').toLowerCase()] ?? h.status ?? 'در انتظار'}
                            </Badge>
                          </td>
                          <td className="px-3 py-2.5 text-text-primary" title={weightSourceLabel(h.weight_source) ?? undefined}>
                            <FlashNum value={h.weight_eff_pct ?? null} render={(v) => (v == null ? '-' : toFaDigits(v))} />
                            {h.weight_eff_pct != null ? <span className="text-2xs text-text-muted"> درصد</span> : null}
                            {h.weight_source && h.weight_source !== 'value' ? (
                              <span className="text-2xs text-text-muted"> ({weightSourceLabel(h.weight_source)})</span>
                            ) : null}
                          </td>
                          <td className="px-3 py-2.5">
                            {h.qty != null && h.qty > 0 ? (
                              <span className="num text-xs text-text-primary">{fmtInt(h.qty)}</span>
                            ) : (
                              <span className="text-xs text-text-muted" title="تعداد ثبت نشده؛ وزن خودکار حساب نمی‌شود">
                                بدون تعداد
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-2.5">
                            {h.value_toman != null && h.value_toman > 0 ? (
                              <FlashNum value={h.value_toman} render={(v) => (v == null ? '-' : fmtInt(v))} />
                            ) : (
                              <span className="text-xs text-text-muted">-</span>
                            )}
                          </td>
                          <td className="px-3 py-2.5">
                            {pnl == null ? (
                              <span className="text-xs text-text-muted">-</span>
                            ) : (
                              <span className={`num text-xs font-bold ${pnl >= 0 ? 'text-accent-green' : 'text-accent-red'}`}>
                                {pnl >= 0 ? '+' : ''}{toFaDigits(Math.round(pnl * 10) / 10)}٪
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-2.5">
                            {stop != null ? (
                              <span className="text-xs text-text-secondary" title={stopCell.techBasis}>
                                <span className="num">{toFaDigits(stop)}</span> <span className="text-2xs text-text-muted">({stopCell.techBasis})</span>
                              </span>
                            ) : (
                              <span className="text-xs text-text-muted">بدون داده</span>
                            )}
                          </td>
                          <td className="px-3 py-2.5">
                            {fundHit == null ? (
                              <span className="text-xs text-text-muted">بدون داده</span>
                            ) : (
                              <Badge tone={fundHit ? 'red' : 'green'}>
                                {fundHit ? 'فعال' : 'سالم'}
                                {stopCell.fundStop.margin != null ? <span> · حاشیه <span className="num">{toFaDigits(stopCell.fundStop.margin)}٪</span></span> : null}
                              </Badge>
                            )}
                          </td>
                          <td className="px-3 py-2.5">
                            {dist == null ? (
                              <span className="text-xs text-text-muted">-</span>
                            ) : (
                              <span
                                className={`text-xs font-bold ${
                                  distTone === 'red' ? 'text-accent-red' : distTone === 'yellow' ? 'text-accent-yellow' : 'text-accent-green'
                                }`}
                              >
                                {dist < 0 ? 'شکسته' : <span className="num">{toFaDigits(Math.round(dist * 10) / 10)}٪</span>}
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-2.5">
                            <span className="text-2xs text-text-secondary" title={dcaLabel(stopCell.fib1, stopCell.fib2, stopCell.jetActive)}>
                              {dcaLabel(stopCell.fib1, stopCell.fib2, stopCell.jetActive)}
                            </span>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* واچ‌لیست داخلِ همین workspace است (§۱): نه تبِ ناوبری، نه صفحۀ دیگر */}
          <WatchlistSection />
        </>
      )}
    </div>
  );
}
