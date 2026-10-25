// components/CandleEdgePatternPanel.tsx -- میزِ الگوهای CandleEdge:
// ریلِ خانواده‌ها + فهرست فشرده + تحلیل جمع‌شونده. چارت اول می‌ماند؛ متن فقط
// برای انتخاب/هاور می‌آید و فهرست کامل پشت «نمایش بیشتر» حفظ می‌شود.
import { useEffect, useMemo, useRef, useState } from 'react';
import { fmtInt } from '@shared/lib/fmt';
import type { PatternEvent } from '../signals/candleedge';
import {
  CANDLEEDGE_ALL_FAMILIES,
  CANDLEEDGE_CHART_NOTE,
  CANDLEEDGE_EXPERIMENTAL_NOTE,
  CANDLEEDGE_FAMILIES,
  CANDLEEDGE_FAMILY_LABELS,
  CANDLEEDGE_FAMILY_TITLES,
  CANDLEEDGE_MVP_METHOD_NOTE,
  buildCandleEdgeAnalysis,
  buildCandleEdgeGroups,
  candleEdgeCounts,
  candleEdgeDate,
  candleEdgeFamilyCounts,
  candleEdgeFamilyOf,
  candleEdgeLabel,
  eventIntersectsViewport,
  type CandleEdgeChartData,
  type CandleEdgeFamily,
  type CandleEdgeFamilyFilter,
  type CandleEdgeViewport,
} from '../lib/candleEdgeMvp';

export interface CandleEdgePatternPanelProps {
  enabled: boolean;
  onEnabledChange: (enabled: boolean) => void;
  data: CandleEdgeChartData | null;
  onSelect: (eventKey: string | null) => void;
  engineId: 'klinecharts' | 'ffc';
  families?: CandleEdgeFamilyFilter;
  onFamiliesChange?: (families: CandleEdgeFamilyFilter) => void;
  hoveredKey?: string | null;
  onHover?: (eventKey: string | null) => void;
  visibleRange?: CandleEdgeViewport | null;
}

const NOOP = () => {};

/** برچسبِ کوتاهِ ریل؛ عنوانِ کامل در جزئیات می‌آید. */
const SHORT_LABELS: Record<string, string> = {
  bullish_engulfing: 'پوشای صعودی',
  bearish_engulfing: 'پوشای نزولی',
  bos_bullish: 'BOS صعودی',
  bos_bearish: 'BOS نزولی',
  liquidity_sweep_high: 'جاروی بالا',
  liquidity_sweep_low: 'جاروی پایین',
  double_top: 'سقف دوقلو',
  double_bottom: 'کف دوقلو',
};

const INITIAL_ROWS = 14;
const MORE_ROWS = 24;

function shortLabel(event: PatternEvent): string {
  return SHORT_LABELS[event.detector] ?? candleEdgeLabel(event.detector);
}

function biasDotClass(bias: string): string {
  return bias === 'bullish' ? 'bg-accent-green' : bias === 'bearish' ? 'bg-accent-red' : 'bg-text-muted';
}

function biasTextClass(bias: string): string {
  return bias === 'bullish'
    ? 'text-accent-green'
    : bias === 'bearish'
      ? 'text-accent-red'
      : 'text-text-muted';
}

function FamilyMark({ family }: { family: CandleEdgeFamily }) {
  if (family === 'engulfing') {
    return <span aria-hidden className="inline-block h-2.5 w-3.5 rounded-[2px] border border-current" />;
  }
  if (family === 'bos') {
    return (
      <span aria-hidden className="inline-flex items-end gap-0.5">
        <span className="relative inline-block h-3 w-4">
          <span className="absolute bottom-1 left-0 h-px w-3 bg-current" />
          <span className="absolute bottom-1 right-0 text-3xs leading-none">↗</span>
        </span>
      </span>
    );
  }
  if (family === 'sweep') {
    return (
      <span aria-hidden className="relative inline-block h-3 w-3">
        <span className="absolute left-1/2 top-0 h-3 w-px -translate-x-1/2 bg-current" />
        <span className="absolute left-0 top-1/2 h-px w-3 bg-current" />
      </span>
    );
  }
  return (
    <span aria-hidden className="inline-flex items-end gap-0.5">
      <span className="block h-2.5 w-px bg-current" />
      <span className="block h-1.5 w-2 border-t border-current" />
      <span className="block h-2.5 w-px bg-current" />
    </span>
  );
}

export function CandleEdgePatternPanel({
  enabled,
  onEnabledChange,
  data,
  onSelect,
  engineId,
  families = CANDLEEDGE_ALL_FAMILIES,
  onFamiliesChange = NOOP,
  hoveredKey = null,
  onHover = NOOP,
  visibleRange = null,
}: CandleEdgePatternPanelProps) {
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [limits, setLimits] = useState<Record<CandleEdgeFamily, number>>({
    engulfing: INITIAL_ROWS,
    bos: INITIAL_ROWS,
    sweep: INITIAL_ROWS,
    double: INITIAL_ROWS,
  });
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

  const selectedEvent = useMemo(
    () => data?.events.find((event) => event.key === selectedKey) ?? null,
    [data?.events, selectedKey],
  );

  // خانوادهٔ خاموش نباید انتخابِ پنهان داشته باشد.
  useEffect(() => {
    if (!selectedEvent) return;
    if (families[candleEdgeFamilyOf(selectedEvent.detector)]) return;
    setSelectedKey(null);
    onSelect(null);
  }, [families, selectedEvent, onSelect]);

  const counts = useMemo(() => candleEdgeCounts(data?.events ?? []), [data?.events]);
  const familyCounts = useMemo(
    () => candleEdgeFamilyCounts(data?.events ?? []),
    [data?.events],
  );

  const groupSizes = useMemo(() => {
    const sizes = new Map<string, number>();
    if (!data || data.events.length === 0) return sizes;
    const groups = buildCandleEdgeGroups(`${data.symbol}|${data.timeframe}`, data.events);
    for (const group of groups.groups) {
      for (const event of group.events) sizes.set(event.key, group.events.length);
    }
    return sizes;
  }, [data]);

  const familyEvents = useMemo(() => {
    const map: Record<CandleEdgeFamily, PatternEvent[]> = {
      engulfing: [],
      bos: [],
      sweep: [],
      double: [],
    };
    for (const event of data?.events ?? []) {
      if (!families[candleEdgeFamilyOf(event.detector)]) continue;
      map[candleEdgeFamilyOf(event.detector)].push(event);
    }
    for (const family of CANDLEEDGE_FAMILIES) {
      map[family].sort(
        (a, b) => b.confirmedAtIndex - a.confirmedAtIndex || a.key.localeCompare(b.key),
      );
    }
    return map;
  }, [data?.events, families]);

  const visibleKeys = useMemo(() => {
    if (!visibleRange) return null;
    const set = new Set<string>();
    for (const event of data?.events ?? []) {
      if (families[candleEdgeFamilyOf(event.detector)] && eventIntersectsViewport(event, visibleRange)) {
        set.add(event.key);
      }
    }
    return set;
  }, [data?.events, families, visibleRange]);

  const visibleCount = visibleKeys?.size ?? 0;
  const analysis = useMemo(
    () => (selectedEvent && data ? buildCandleEdgeAnalysis(selectedEvent, data) : null),
    [selectedEvent, data],
  );
  const hoveredEvent = useMemo(
    () => data?.events.find((event) => event.key === hoveredKey) ?? null,
    [data?.events, hoveredKey],
  );
  const pivotConfirmedDate = useMemo(() => {
    if (!selectedEvent || !data) return null;
    const pivot = selectedEvent.anchors.find(
      (anchor) =>
        anchor.role === 'high' ||
        anchor.role === 'low' ||
        anchor.role === 'peak' ||
        anchor.role === 'trough',
    );
    return pivot?.confirmedAtIndex != null && data.bars[pivot.confirmedAtIndex]
      ? candleEdgeDate(data.bars[pivot.confirmedAtIndex].timestamp)
      : null;
  }, [selectedEvent, data]);

  const clearSelection = () => {
    setSelectedKey(null);
    onSelect(null);
  };

  const selectEvent = (event: PatternEvent) => {
    if (selectedKey === event.key) {
      clearSelection();
      return;
    }
    setSelectedKey(event.key);
    onSelect(event.key);
  };

  const toggleFamily = (family: CandleEdgeFamily) => {
    onFamiliesChange({ ...families, [family]: !families[family] });
  };

  const hoverHint = hoveredEvent
    ? `${shortLabel(hoveredEvent)} · ${candleEdgeDate(hoveredEvent.confirmedAt)}${
        hoveredEvent.level != null ? ` · سطح ${fmtInt(hoveredEvent.level)}` : ''
      }`
    : 'برای پیش‌نمایش روی رویداد بایستید.';

  return (
    <section data-testid="candleedge-panel" className="flex h-full min-h-0 flex-col text-2xs">
      <header className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border-c/60 pb-1">
        <label className="inline-flex cursor-pointer items-center gap-2 text-xs font-semibold text-text-secondary">
          <span className="relative inline-flex h-4 w-7 items-center">
            <input
              type="checkbox"
              data-testid="ce-toggle"
              checked={enabled}
              disabled={engineId === 'ffc'}
              onChange={(event) => onEnabledChange(event.target.checked)}
              className="peer sr-only"
            />
            <span className="h-4 w-7 rounded-full bg-bg-card ring-1 ring-border-c transition-colors peer-checked:bg-accent-blue/70 peer-disabled:opacity-40 peer-focus-visible:ring-accent-blue" />
            <span className="pointer-events-none absolute start-0.5 h-3 w-3 rounded-full bg-text-muted transition-transform peer-checked:translate-x-3 peer-checked:bg-white" />
          </span>
          نمایش الگوهای تکنیکال
        </label>
        <span className="rounded-full border border-border-c bg-bg-card px-1.5 py-px text-3xs font-bold text-accent-yellow">
          آزمایشی
        </span>
        {enabled && data && !data.error ? (
          <span data-testid="ce-counts" className="font-mono text-3xs tabular-nums text-text-muted">
            {fmtInt(counts.total)} تأییدشده · {fmtInt(counts.bullish)} صعودی ·{' '}
            {fmtInt(counts.bearish)} نزولی
          </span>
        ) : null}
        {enabled && data && !data.error ? (
          <span className="text-3xs text-text-muted">
            {data.symbol} · {data.timeframe} · {fmtInt(data.bars.length)} کندل
          </span>
        ) : null}
        {enabled && data && !data.error ? (
          <span data-testid="ce-inview" className="text-3xs text-text-muted">
            در دید: {visibleRange ? fmtInt(visibleCount) : '—'}
          </span>
        ) : null}
        {selectedEvent ? (
          <button
            type="button"
            onClick={clearSelection}
            className="ms-auto rounded border border-border-c px-1.5 py-px text-3xs text-text-muted transition-colors hover:border-border-accent hover:text-text-secondary focus-visible:ring-1 focus-visible:ring-accent-blue"
          >
            بستن انتخاب
          </button>
        ) : null}
      </header>

      {engineId === 'ffc' ? (
        <p data-testid="ce-engine-note" className="text-2xs leading-5 text-accent-yellow">
          این لایه فعلاً فقط روی موتور klinecharts رسم می‌شود؛ Fast Financial Charts افزونهٔ
          overlay آن را ندارد. با برگشت به klinecharts دوباره در دسترس است.
        </p>
      ) : null}

      {!enabled && engineId !== 'ffc' ? (
        <p className="max-w-[75ch] text-2xs leading-5 text-text-muted">
          لایه خاموش است. روشن‌کردن، هشت الگوریتم آزمایشی را روی همین سریِ چارت می‌آورد؛ متن
          فقط برای رویدادِ انتخاب/هاور. {CANDLEEDGE_EXPERIMENTAL_NOTE}
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
          در {fmtInt(data.bars.length)} کندل این بازه هیچ الگوی تأییدشده‌ای پیدا نشد؛ این «نبودِ
          رویداد» است، نه تأییدِ نبودِ حرکت.
        </p>
      ) : null}

      {enabled && data && !data.error && data.events.length > 0 ? (
        <>
          <div className="flex flex-wrap items-center gap-1.5 py-1">
            {CANDLEEDGE_FAMILIES.map((family) => {
              const active = families[family];
              return (
                <button
                  key={family}
                  type="button"
                  data-testid={`ce-family-${family}`}
                  aria-pressed={active}
                  onClick={() => toggleFamily(family)}
                  className={`inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 text-3xs transition-colors focus-visible:ring-1 focus-visible:ring-accent-blue ${
                    active
                      ? 'border-accent-blue/45 bg-accent-blue/10 text-text-secondary'
                      : 'border-border-c/70 text-text-muted opacity-60 hover:opacity-100'
                  }`}
                >
                  <FamilyMark family={family} />
                  <span>{CANDLEEDGE_FAMILY_LABELS[family]}</span>
                  <span className="font-mono tabular-nums text-text-muted">
                    {fmtInt(familyCounts[family])}
                  </span>
                </button>
              );
            })}
            <span data-testid="ce-legend" className="ms-auto flex flex-wrap items-center gap-x-2 gap-y-0.5 text-3xs text-text-muted">
              <span className="inline-flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-accent-green" /> صعودی
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-accent-red" /> نزولی
              </span>
              <span className="text-border-c">|</span>
              <span className="inline-flex items-center gap-1 text-text-secondary">
                <FamilyMark family="engulfing" /> پوشا
              </span>
              <span className="inline-flex items-center gap-1 text-text-secondary">
                <FamilyMark family="bos" /> BOS
              </span>
              <span className="inline-flex items-center gap-1 text-text-secondary">
                <FamilyMark family="sweep" /> جارو
              </span>
              <span className="inline-flex items-center gap-1 text-text-secondary">
                <FamilyMark family="double" /> دوقلو
              </span>
            </span>
          </div>

          <p className="text-3xs leading-4 text-text-muted" title={CANDLEEDGE_MVP_METHOD_NOTE}>
            {CANDLEEDGE_CHART_NOTE}
          </p>

          <div className="grid min-h-0 flex-1 gap-2 pt-1 md:grid-cols-[minmax(0,1.08fr)_minmax(270px,0.92fr)]">
            <div className="flex min-h-0 flex-col">
              <div className="flex items-center justify-between gap-2 pb-1">
                <span className="text-3xs font-bold text-text-secondary">
                  رویدادها <span className="font-normal text-text-muted">(تازه‌ترین تأیید)</span>
                </span>
                <span
                  data-testid="ce-hover-hint"
                  aria-live="polite"
                  className="truncate text-3xs text-text-muted"
                >
                  {hoverHint}
                </span>
              </div>
              <div className="min-h-0 overflow-y-auto pe-1" data-testid="ce-groups">
                {CANDLEEDGE_FAMILIES.filter((family) => families[family]).map((family) => {
                  const rows = familyEvents[family];
                  const shown = rows.slice(0, limits[family]);
                  return (
                    <section key={family} data-testid={`ce-section-${family}`} className="pb-1">
                      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-border-c/40 bg-[var(--bg-secondary)] py-0.5 text-3xs">
                        <span className="inline-flex items-center gap-1 font-bold text-text-secondary">
                          <FamilyMark family={family} />
                          {CANDLEEDGE_FAMILY_TITLES[family]}
                        </span>
                        <span className="font-mono tabular-nums text-text-muted">
                          {fmtInt(familyCounts[family])}
                        </span>
                      </header>
                      {shown.length === 0 ? (
                        <p className="px-1 py-1 text-3xs text-text-muted">در این خانواده رویدادی نیست.</p>
                      ) : (
                        shown.map((event) => {
                          const active = event.key === selectedKey;
                          const hovered = event.key === hoveredKey;
                          const groupSize = groupSizes.get(event.key) ?? 1;
                          const inView = visibleKeys?.has(event.key) ?? false;
                          return (
                            <button
                              key={event.key}
                              type="button"
                              data-testid={`ce-event-${event.key}`}
                              aria-pressed={active}
                              title={`${candleEdgeLabel(event.detector)} · ${candleEdgeDate(event.confirmedAt)}`}
                              onMouseEnter={() => onHover(event.key)}
                              onMouseLeave={() => onHover(null)}
                              onFocus={() => onHover(event.key)}
                              onBlur={() => onHover(null)}
                              onClick={() => selectEvent(event)}
                              className={`flex w-full items-center gap-1.5 border-s-2 px-1.5 py-0.5 text-start transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-accent-blue ${
                                active
                                  ? 'border-accent-blue bg-accent-blue/10'
                                  : hovered
                                    ? 'border-border-accent bg-bg-card/70'
                                    : 'border-transparent hover:bg-bg-card/50'
                              }`}
                            >
                              <span
                                className={`h-1.5 w-1.5 shrink-0 rounded-full ${biasDotClass(event.bias)}`}
                                aria-hidden
                              />
                              <span className="min-w-0 flex-1 truncate text-3xs font-semibold text-text-secondary">
                                {shortLabel(event)}
                              </span>
                              <span className="shrink-0 font-mono text-3xs tabular-nums text-text-muted">
                                {candleEdgeDate(event.confirmedAt)}
                              </span>
                              {groupSize > 1 ? (
                                <span
                                  className="shrink-0 rounded-sm border border-border-c/60 px-1 text-3xs tabular-nums text-text-muted"
                                  title={`هم‌گروه با ${fmtInt(groupSize)} رویداد`}
                                >
                                  {fmtInt(groupSize)}
                                </span>
                              ) : null}
                              {inView ? (
                                <span
                                  className="h-1 w-1 shrink-0 rounded-full bg-accent-blue"
                                  title="در محدودهٔ دید"
                                />
                              ) : null}
                            </button>
                          );
                        })
                      )}
                      {rows.length > limits[family] ? (
                        <button
                          type="button"
                          data-testid={`ce-more-${family}`}
                          onClick={() =>
                            setLimits((current) => ({
                              ...current,
                              [family]: current[family] + MORE_ROWS,
                            }))
                          }
                          className="mt-0.5 w-full rounded-sm border border-dashed border-border-c/70 py-0.5 text-3xs text-text-muted transition-colors hover:border-border-accent hover:text-text-secondary focus-visible:ring-1 focus-visible:ring-accent-blue"
                        >
                          نمایش بیشتر ({fmtInt(rows.length - limits[family])})
                        </button>
                      ) : null}
                    </section>
                  );
                })}
              </div>
            </div>

            <aside
              className="min-h-0 overflow-y-auto border-s border-border-c/50 ps-2"
              data-testid="ce-detail-host"
            >
              {analysis && selectedEvent ? (
                <div data-testid="ce-detail" className="flex flex-col gap-1.5 pe-1 text-2xs">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-3xs font-bold tracking-widest text-text-muted">
                        جزئیات رویداد
                      </p>
                      <h3 className="truncate text-xs font-bold text-text-primary">
                        {analysis.title}
                      </h3>
                      <p className="flex items-center gap-1.5 text-3xs text-text-muted">
                        <span className={`font-bold ${biasTextClass(analysis.bias)}`}>
                          {analysis.biasLabel}
                        </span>
                        <span>·</span>
                        <span>{analysis.timeframeLabel}</span>
                        <span>·</span>
                        <span className="text-accent-green">تأییدشده</span>
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={clearSelection}
                      aria-label="بستن جزئیات"
                      className="shrink-0 rounded border border-border-c px-1 text-3xs text-text-muted hover:text-text-secondary focus-visible:ring-1 focus-visible:ring-accent-blue"
                    >
                      ×
                    </button>
                  </div>

                  <dl className="grid grid-cols-[auto_1fr_auto_1fr] gap-x-2 gap-y-0.5 border-y border-border-c/40 py-1 text-3xs">
                    <dt className="text-text-muted">شکل‌گیری</dt>
                    <dd className="font-mono tabular-nums text-text-secondary">
                      {analysis.formationDate || '—'}
                    </dd>
                    <dt className="text-text-muted">تأیید</dt>
                    <dd className="font-mono tabular-nums text-text-secondary">
                      {analysis.confirmationDate || '—'}
                    </dd>
                    <dt className="text-text-muted">سطح</dt>
                    <dd className="font-mono tabular-nums text-text-secondary">
                      {analysis.level != null ? fmtInt(analysis.level) : 'بدون سطح'}
                    </dd>
                    <dt className="text-text-muted">تأیید پیوت</dt>
                    <dd className="font-mono tabular-nums text-text-secondary">
                      {pivotConfirmedDate || '—'}
                    </dd>
                  </dl>

                  <p className="line-clamp-2 text-3xs leading-4 text-text-secondary">
                    {analysis.significance}
                  </p>

                  <details className="group rounded-sm border border-border-c/50 bg-bg-card/30">
                    <summary className="cursor-pointer list-none px-1.5 py-1 text-3xs font-bold text-text-secondary marker:hidden hover:text-text-primary">
                      <span className="inline-block transition-transform group-open:rotate-90">›</span>{' '}
                      تحلیل کامل: لنگرها، کندل‌ها، محدودیت‌ها و ابطال
                    </summary>
                    <div className="flex flex-col gap-1.5 border-t border-border-c/40 p-1.5">
                      <div>
                        <p className="mb-0.5 text-3xs font-bold text-text-muted">لنگرها و تأیید پیوت</p>
                        <table className="w-full border-collapse text-3xs">
                          <thead>
                            <tr className="text-text-muted">
                              <th className="border-b border-border-c px-1 py-0.5 text-start font-normal">نقش</th>
                              <th className="border-b border-border-c px-1 py-0.5 text-start font-normal">تاریخ</th>
                              <th className="border-b border-border-c px-1 py-0.5 text-start font-normal">قیمت</th>
                              <th className="border-b border-border-c px-1 py-0.5 text-start font-normal">تأیید پیوت</th>
                            </tr>
                          </thead>
                          <tbody>
                            {analysis.anchors.map((anchor, index) => (
                              <tr key={`${anchor.roleLabel}-${index}`} className="text-text-secondary">
                                <td className="border-b border-border-c/60 px-1 py-0.5">{anchor.roleLabel}</td>
                                <td className="border-b border-border-c/60 px-1 py-0.5 font-mono tabular-nums">{anchor.date || '—'}</td>
                                <td className="border-b border-border-c/60 px-1 py-0.5 font-mono tabular-nums">{fmtInt(anchor.price)}</td>
                                <td className="border-b border-border-c/60 px-1 py-0.5 font-mono tabular-nums">{anchor.pivotConfirmedDate || '—'}</td>
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
                                <td className="border-b border-border-c/60 px-1 py-0.5 font-mono tabular-nums">{candle.date || '—'}</td>
                                <td className="border-b border-border-c/60 px-1 py-0.5 font-mono tabular-nums">{fmtInt(candle.open)}</td>
                                <td className="border-b border-border-c/60 px-1 py-0.5 font-mono tabular-nums">{fmtInt(candle.high)}</td>
                                <td className="border-b border-border-c/60 px-1 py-0.5 font-mono tabular-nums">{fmtInt(candle.low)}</td>
                                <td className="border-b border-border-c/60 px-1 py-0.5 font-mono tabular-nums">{fmtInt(candle.close)}</td>
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
                  </details>
                </div>
              ) : (
                <div className="flex h-full flex-col justify-center gap-1 p-2 text-text-muted">
                  <p className="text-2xs font-semibold text-text-secondary">یک رویداد را انتخاب کنید.</p>
                  <p className="text-3xs leading-4">
                    هاور روی ردیف، پیش‌نمایش را روی چارت نشان می‌دهد؛ کلیک، چارت را به همان
                    بازه می‌برد و تحلیل فشرده باز می‌شود.
                  </p>
                  {hoverHint !== 'برای پیش‌نمایش روی رویداد بایستید.' ? (
                    <p className="font-mono text-3xs tabular-nums text-text-secondary">{hoverHint}</p>
                  ) : null}
                  <p className="text-3xs leading-4 text-text-muted">{CANDLEEDGE_EXPERIMENTAL_NOTE}</p>
                </div>
              )}
            </aside>
          </div>
        </>
      ) : null}
    </section>
  );
}
