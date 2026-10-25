// components/CandleEdgePatternPanel.tsx -- نمایش رویدادهای تأییدشدهٔ هشت الگوریتم
// آزمایشی CandleEdge: فهرست گروه‌بندی‌شده + تحلیل همان رویداد. انتخاب با کلیک
// رویداد به چارت می‌رسد تا نشانگر/سطح همان رویداد برجسته شود.
import { useEffect, useMemo, useRef, useState } from 'react';
import { fmtInt } from '@shared/lib/fmt';
import type { PatternEvent } from '../signals/candleedge';
import {
  CANDLEEDGE_CHART_NOTE,
  CANDLEEDGE_EXPERIMENTAL_NOTE,
  CANDLEEDGE_MVP_METHOD_NOTE,
  buildCandleEdgeAnalysis,
  buildCandleEdgeGroups,
  candleEdgeBiasLabel,
  candleEdgeCounts,
  candleEdgeDate,
  candleEdgeLabel,
  type CandleEdgeChartData,
} from '../lib/candleEdgeMvp';

export interface CandleEdgePatternPanelProps {
  enabled: boolean;
  onEnabledChange: (enabled: boolean) => void;
  data: CandleEdgeChartData | null;
  onSelect: (eventKey: string | null) => void;
  engineId: 'klinecharts' | 'ffc';
}

const biasColor = (bias: string): string =>
  bias === 'bullish'
    ? 'text-accent-green'
    : bias === 'bearish'
      ? 'text-accent-red'
      : 'text-text-muted';

export function CandleEdgePatternPanel({
  enabled,
  onEnabledChange,
  data,
  onSelect,
  engineId,
}: CandleEdgePatternPanelProps) {
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const lastSeries = useRef<string | null>(null);
  const seriesKey = data ? `${data.symbol}|${data.timeframe}` : null;

  // تغییر نماد/تایم‌فریم ⇒ هیچ انتخاب یا جزئیاتی از سری قبلی نمی‌ماند.
  useEffect(() => {
    if (lastSeries.current === seriesKey) return;
    lastSeries.current = seriesKey;
    setSelectedKey(null);
    onSelect(null);
  }, [seriesKey, onSelect]);

  // رفرش همان سری با مجموعهٔ رویدادِ متفاوت ⇒ انتخابِ ناپدیدشده پاک می‌شود.
  useEffect(() => {
    if (selectedKey == null) return;
    if (!data || !data.events.some((event) => event.key === selectedKey)) {
      setSelectedKey(null);
      onSelect(null);
    }
  }, [data, selectedKey, onSelect]);

  useEffect(() => {
    if (enabled) return;
    setSelectedKey(null);
    onSelect(null);
  }, [enabled, onSelect]);

  const counts = useMemo(
    () => candleEdgeCounts(data?.events ?? []),
    [data?.events],
  );
  const groups = useMemo(() => {
    if (!data || data.events.length === 0) return null;
    return buildCandleEdgeGroups(`${data.symbol}|${data.timeframe}`, data.events);
  }, [data]);

  const selectedEvent = useMemo(
    () => data?.events.find((event) => event.key === selectedKey) ?? null,
    [data?.events, selectedKey],
  );
  const analysis = useMemo(
    () => (selectedEvent && data ? buildCandleEdgeAnalysis(selectedEvent, data) : null),
    [selectedEvent, data],
  );

  const selectEvent = (event: PatternEvent) => {
    const next = selectedKey === event.key ? null : event.key;
    setSelectedKey(next);
    onSelect(next);
  };

  return (
    <section data-testid="candleedge-panel" className="flex h-full min-h-0 flex-col gap-1.5">
      <header className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <label className="inline-flex cursor-pointer items-center gap-1.5 text-xs font-semibold text-text-secondary">
          <input
            type="checkbox"
            data-testid="ce-toggle"
            checked={enabled}
            disabled={engineId === 'ffc'}
            onChange={(event) => onEnabledChange(event.target.checked)}
            className="h-3.5 w-3.5 accent-[var(--accent-blue)]"
          />
          نمایش الگوهای تکنیکال
        </label>
        <span className="rounded-full border border-border-c bg-bg-card px-1.5 py-px text-3xs font-bold text-accent-yellow">
          آزمایشی
        </span>
        {enabled && data && !data.error ? (
          <span data-testid="ce-legend" className="text-3xs text-text-muted">
            <span className="text-accent-green">▲</span> صعودی
            <span className="mx-1">·</span>
            <span className="text-accent-red">▼</span> نزولی
          </span>
        ) : null}
        {enabled && data && !data.error ? (
          <span data-testid="ce-counts" className="text-3xs text-text-muted">
            {fmtInt(counts.total)} رویداد تأییدشده · {fmtInt(counts.bullish)} صعودی ·{' '}
            {fmtInt(counts.bearish)} نزولی
            {counts.neutral > 0 ? ` · ${fmtInt(counts.neutral)} بی‌جهت` : ''}
          </span>
        ) : null}
        {enabled && data && !data.error ? (
          <span className="text-3xs text-text-muted">
            {data.symbol} · {data.timeframe} · {fmtInt(data.bars.length)} کندل
          </span>
        ) : null}
        {analysis ? (
          <button
            type="button"
            onClick={() => {
              setSelectedKey(null);
              onSelect(null);
            }}
            className="ms-auto rounded border border-border-c px-1.5 py-px text-3xs text-text-muted hover:text-text-secondary"
          >
            پاک‌کردن انتخاب
          </button>
        ) : null}
      </header>

      {engineId === 'ffc' ? (
        <p data-testid="ce-engine-note" className="text-2xs leading-5 text-accent-yellow">
          لایهٔ الگوها فعلاً فقط روی موتور klinecharts رسم می‌شود؛ چارت Fast Financial Charts این
          افزونه را ندارد. با برگشت به klinecharts دوباره در دسترس است.
        </p>
      ) : null}

      {!enabled && engineId !== 'ffc' ? (
        <p className="text-2xs leading-5 text-text-muted">
          لایه خاموش است. با روشن‌کردن، رویدادهای تأییدشدهٔ هشت الگوریتم آزمایشی روی چارت و در
          همین پنل دیده می‌شوند. {CANDLEEDGE_EXPERIMENTAL_NOTE}
        </p>
      ) : null}

      {enabled && data?.error ? (
        <p data-testid="ce-error" className="text-2xs leading-5 text-accent-red">
          اسکن الگوها انجام نشد: {data.error}
        </p>
      ) : null}

      {enabled && !data && engineId !== 'ffc' ? (
        <p data-testid="ce-loading" className="text-2xs leading-5 text-text-muted">
          در حال خواندن کندل‌های همین چارت…
        </p>
      ) : null}

      {enabled && data && !data.error && data.events.length === 0 ? (
        <p data-testid="ce-empty" className="text-2xs leading-5 text-text-muted">
          در {fmtInt(data.bars.length)} کندل این بازه، هیچ الگوی تأییدشده‌ای از هشت الگوریتم MVP
          پیدا نشد. این «نبودِ رویداد» است، نه تأیید نبودِ حرکت.
        </p>
      ) : null}

      {enabled && data && !data.error && groups ? (
        <div className="grid min-h-0 flex-1 gap-2 md:grid-cols-[minmax(190px,280px)_1fr]">
          <div className="min-h-0 overflow-y-auto pe-1" data-testid="ce-groups">
            <p className="mb-1 text-3xs leading-4 text-text-muted">{CANDLEEDGE_MVP_METHOD_NOTE}</p>
            <p className="mb-1 text-3xs leading-4 text-text-muted">{CANDLEEDGE_CHART_NOTE}</p>
            {groups.groups.map((group) => (
              <div
                key={group.id}
                className="mb-1 rounded border border-border-c bg-bg-card/40 p-1"
              >
                <div className="flex items-center justify-between px-0.5 text-3xs text-text-muted">
                  <span>
                    {group.events.length > 1
                      ? `گروه ${fmtInt(group.events.length)} رویدادی`
                      : 'رویداد'}
                  </span>
                  <span className={biasColor(group.bias)}>{candleEdgeBiasLabel(group.bias)}</span>
                </div>
                <div className="flex flex-wrap gap-1 pt-1">
                  {group.events.map((event) => {
                    const active = event.key === selectedKey;
                    return (
                      <button
                        key={event.key}
                        type="button"
                        data-testid={`ce-event-${event.key}`}
                        aria-pressed={active}
                        onClick={() => selectEvent(event)}
                        className={`rounded border px-1.5 py-0.5 text-start text-3xs leading-4 transition-colors ${
                          active
                            ? 'border-accent-blue bg-accent-blue/15 text-accent-blue'
                            : 'border-border-c text-text-secondary hover:border-border-accent hover:text-text-primary'
                        }`}
                      >
                        <span className={active ? '' : biasColor(event.bias)}>
                          {candleEdgeLabel(event.detector)}
                        </span>
                        <span className="ms-1 text-text-muted">{candleEdgeDate(event.confirmedAt)}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          <div className="min-h-0 overflow-y-auto" data-testid="ce-detail-host">
            {analysis ? (
              <div data-testid="ce-detail" className="flex flex-col gap-2 pe-1 text-2xs leading-5">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-xs font-bold text-text-primary">{analysis.title}</h3>
                  <span className={`text-3xs font-bold ${biasColor(analysis.bias)}`}>
                    {analysis.biasLabel}
                  </span>
                  <span className="text-3xs text-text-muted">{analysis.timeframeLabel}</span>
                </div>

                <p className="text-text-secondary">{analysis.significance}</p>

                <dl className="grid grid-cols-[auto_1fr_auto_1fr] gap-x-2 gap-y-0.5 text-3xs">
                  <dt className="text-text-muted">شکل‌گیری</dt>
                  <dd className="text-text-secondary">{analysis.formationDate || '—'}</dd>
                  <dt className="text-text-muted">تأیید</dt>
                  <dd className="text-text-secondary">{analysis.confirmationDate || '—'}</dd>
                  <dt className="text-text-muted">سطح</dt>
                  <dd className="text-text-secondary">
                    {analysis.level != null ? fmtInt(analysis.level) : 'این الگو سطح ندارد'}
                  </dd>
                  <dt className="text-text-muted">وضعیت</dt>
                  <dd className="text-text-secondary">تأییدشده — provisional نمایش داده نمی‌شود</dd>
                </dl>

                <div>
                  <p className="mb-0.5 text-3xs font-bold text-text-muted">
                    لنگرها و زمان تأیید پیوت
                  </p>
                  <table className="w-full border-collapse text-3xs">
                    <thead>
                      <tr className="text-text-muted">
                        <th className="border-b border-border-c px-1 py-0.5 text-start font-normal">نقش</th>
                        <th className="border-b border-border-c px-1 py-0.5 text-start font-normal">تاریخ</th>
                        <th className="border-b border-border-c px-1 py-0.5 text-start font-normal">قیمت</th>
                        <th className="border-b border-border-c px-1 py-0.5 text-start font-normal">
                          تأیید پیوت
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {analysis.anchors.map((anchor, index) => (
                        <tr key={`${anchor.roleLabel}-${index}`} className="text-text-secondary">
                          <td className="border-b border-border-c/60 px-1 py-0.5">{anchor.roleLabel}</td>
                          <td className="border-b border-border-c/60 px-1 py-0.5">{anchor.date || '—'}</td>
                          <td className="border-b border-border-c/60 px-1 py-0.5">{fmtInt(anchor.price)}</td>
                          <td className="border-b border-border-c/60 px-1 py-0.5">
                            {anchor.pivotConfirmedDate || '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div>
                  <p className="mb-0.5 text-3xs font-bold text-text-muted">کندل‌های تشکیل‌دهنده</p>
                  <table className="w-full border-collapse text-3xs">
                    <thead>
                      <tr className="text-text-muted">
                        <th className="border-b border-border-c px-1 py-0.5 text-start font-normal">تاریخ</th>
                        <th className="border-b border-border-c px-1 py-0.5 text-start font-normal">باز</th>
                        <th className="border-b border-border-c px-1 py-0.5 text-start font-normal">بیشینه</th>
                        <th className="border-b border-border-c px-1 py-0.5 text-start font-normal">کمینه</th>
                        <th className="border-b border-border-c px-1 py-0.5 text-start font-normal">بسته</th>
                      </tr>
                    </thead>
                    <tbody>
                      {analysis.candles.map((candle) => (
                        <tr key={candle.index} className="text-text-secondary">
                          <td className="border-b border-border-c/60 px-1 py-0.5">{candle.date || '—'}</td>
                          <td className="border-b border-border-c/60 px-1 py-0.5">{fmtInt(candle.open)}</td>
                          <td className="border-b border-border-c/60 px-1 py-0.5">{fmtInt(candle.high)}</td>
                          <td className="border-b border-border-c/60 px-1 py-0.5">{fmtInt(candle.low)}</td>
                          <td className="border-b border-border-c/60 px-1 py-0.5">{fmtInt(candle.close)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div>
                  <p className="mb-0.5 text-3xs font-bold text-text-muted">محدودیت‌ها</p>
                  <ul className="list-inside list-disc text-3xs text-text-muted">
                    {analysis.limits.map((limit) => (
                      <li key={limit}>{limit}</li>
                    ))}
                  </ul>
                </div>

                <div>
                  <p className="mb-0.5 text-3xs font-bold text-text-muted">شرط ابطال ساختاری</p>
                  <p className="text-3xs text-text-secondary">
                    {analysis.invalidation ??
                      'خروجی الگوریتم برای این الگو شرط ابطال تعریف نکرده است؛ شرطی از خود نمی‌سازیم.'}
                  </p>
                </div>
              </div>
            ) : (
              <p className="text-2xs leading-5 text-text-muted">
                یک رویداد را از فهرست انتخاب کنید تا زمان تشکیل و تأیید، کندل‌های سازنده، سطح و
                محدودیت‌های همان رویداد دیده شود. انتخاب، چارت را به همان بازه می‌برد.
              </p>
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}
