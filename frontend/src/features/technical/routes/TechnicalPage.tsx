// features/technical/routes/TechnicalPage.tsx -- تب تکنیکال با چارت پورت‌شدهٔ جمینای (NahayatNegar)
// چارت سطح‌نما: KLineChartNahayatNegar (پورت‌شده به klinecharts v10) با دادهٔ واقعی ما.
// سایدبار راست، بازپخش، مقایسه و پنل‌های FTS (تحلیل سمت سرور) ما حفظ شده‌اند.
import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router';
import { Badge } from '@shared/components/Badge';
import { toFaDigits } from '@shared/lib/fmt';
import { publishSignal } from '@shared/lib/signalBus';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useUiStore } from '@shared/stores/uiStore';
import { majorResistance } from '../lib/indicators';
import { paletteFor } from '../lib/chartPalette';
import { SplitChartView } from '../components/SplitChartView';
import type { ChartMarker, FtsChartLayers } from '../components/KLineChartWrapper';
import { useFtsConfigStore } from '../stores/ftsConfigStore';
import { useReplayStore } from '../stores/replayStore';
import { clampCursor, isAtEnd, replaySlice, stepCursor } from '../lib/replay';
import { computeTradeLevels } from '../lib/levels';
import { useCandleFeed } from '../api/useCandleFeed';
import { useFundGate } from '../api/useFundGate';
import { useFtsAnalysis } from '../api/useFtsAnalysis';
import { technicalSignal } from '../signals/technicalSignals';
import { FtsBadgeStrip } from '../components/FtsBadgeStrip';
import { FtsTrendPanel } from '../components/FtsTrendPanel';
import { FtsStatusCard } from '../components/FtsStatusCard';
import { TechnicalSidebar } from '../components/TechnicalSidebar';
import { ReplayBar } from '../components/ReplayBar';
import { ComparePanel } from '../components/ComparePanel';
import { MarketOverview } from '../components/MarketOverview';
import { ChartSettingsDialog } from '../components/ChartSettingsDialog';
import type { ActiveLevelsView } from '../components/SidebarActiveLevels';
import { useNnChartData, useNnTedipx } from '../nahayatnegar/lib/useNnData';

/** چارت پورت‌شدهٔ جمینای با React.lazy تا چانک صفحهٔ تکنیکال سبک بماند */
const NnChart = lazy(() =>
  import('../nahayatnegar/components/KLineChartWrapper').then((m) => ({ default: m.KLineChartNahayatNegar })),
);

const DIR_TONE = { bullish: 'green', bearish: 'red', neutral: 'gray' } as const;
const DIR_LABEL = { bullish: 'صعودی', bearish: 'نزولی', neutral: 'خنثی' } as const;

export default function TechnicalPage() {
  const params = useParams();
  const navigate = useNavigate();
  const stored = useSymbolStore((s) => s.symbol);
  const setStored = useSymbolStore((s) => s.setSymbol);
  const symbol = params.symbol ?? stored;
  const theme = useUiStore((s) => s.theme);
  const view = useFtsConfigStore((s) => s.view);

  const enforceRiskGates = useFtsConfigStore((s) => s.enforceRiskGates);
  const showFtsCard = useFtsConfigStore((s) => s.showFtsCard);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const replayActive = useReplayStore((s) => s.active);
  const replayCursor = useReplayStore((s) => s.cursor);
  const replayPlaying = useReplayStore((s) => s.playing);
  const replaySpeed = useReplayStore((s) => s.speedMs);
  const setReplayCursor = useReplayStore((s) => s.setCursor);
  const setReplayPlaying = useReplayStore((s) => s.setPlaying);

  // دادهٔ چارت جدید (کندل + رویدادهای تعدیل) و نمای کل بورس
  const nn = useNnChartData(symbol);
  const tedipx = useNnTedipx();

  // تحلیل/سیگنال FTS ما روی همان داده (سرور + محاسبات خودمان)
  const feed = useCandleFeed(symbol);
  const candles = feed.candles;
  const analysis = useFtsAnalysis(symbol);
  const gate = useFundGate(enforceRiskGates ? symbol : '');

  const series = useMemo(
    () => ({
      opens: candles.map((c) => c.open),
      closes: candles.map((c) => c.close),
      highs: candles.map((c) => c.high),
      lows: candles.map((c) => c.low),
      volumes: candles.map((c) => c.volume ?? null),
    }),
    [candles],
  );

  const signal = useMemo(
    () => (symbol && candles.length > 0 ? technicalSignal({ symbol, ...series, riskGatePass: gate.pass, enforceRiskGates }) : null),
    [symbol, candles, series, gate.pass, enforceRiskGates],
  );
  useEffect(() => {
    if (signal) publishSignal(signal);
  }, [signal]);
  const gateBlocked = enforceRiskGates && gate.pass === false;

  const maPanel = useMemo(() => {
    const mas: { 14: number | null; 21: number | null; 52: number | null; 100: number | null } = {
      14: null,
      21: null,
      52: null,
      100: null,
    };
    return mas;
  }, []);

  // دادهٔ چارت: کل بورس (بدون نماد) یا نماد فعال + برش بازپخش
  const chartRows = useMemo(() => {
    if (!symbol) return tedipx.data;
    return replayActive ? replaySlice(nn.data, replayCursor) : nn.data;
  }, [symbol, tedipx.data, nn.data, replayActive, replayCursor]);

  useEffect(() => {
    if (!replayActive || !replayPlaying || !symbol) return;
    const t = setInterval(() => {
      const cur = clampCursor(replayCursor, nn.data.length);
      if (isAtEnd(cur, nn.data.length)) {
        setReplayPlaying(false);
        return;
      }
      setReplayCursor(stepCursor(cur, nn.data.length, 1));
    }, Math.max(50, replaySpeed));
    return () => clearInterval(t);
  }, [replayActive, replayPlaying, replayCursor, replaySpeed, nn.data.length, symbol, setReplayCursor, setReplayPlaying]);

  const selectSymbol = useCallback(
    (s: string) => {
      if (!s) return;
      setStored(s);
      navigate(`/technical/${encodeURIComponent(s)}`);
    },
    [navigate, setStored],
  );

  const activeLevels = useMemo<ActiveLevelsView>(() => {
    const fib = analysis.data?.fts?.fib ?? null;
    const { swingLow, stop5pct } = computeTradeLevels(series.lows);
    return {
      symbol,
      zone3340: fib?.zone_33_40 ? { lo: fib.zone_33_40.lo ?? null, hi: fib.zone_33_40.hi ?? null } : null,
      zone61870: fib?.zone_618_70 ? { lo: fib.zone_618_70.lo ?? null, hi: fib.zone_618_70.hi ?? null } : null,
      baseLevel: fib?.retrace_base_low ?? null,
      ma100: maPanel[100],
      swingLow,
      stop5pct,
      keyLevels: signal?.payload.keyLevels ?? [],
      stopLoss: signal?.payload.stopLossPrice ?? null,
      lastClose: candles.length > 0 ? candles[candles.length - 1].close : null,
      setups: signal?.payload.setups ?? [],
      direction: signal?.direction ?? null,
    };
  }, [analysis.data, series.lows, maPanel, signal, symbol, candles]);

  // لایه‌های FTS (فیبو/مارکر/خط جت + MA) برای چارت جدید و پنل‌های اسپلیت
  const layers = useMemo<FtsChartLayers>(() => {
    const jet = majorResistance(series.highs.slice(0, -1), 120)?.price ?? null;
    const fts = analysis.data?.fts ?? null;
    const last = candles.length > 0 ? candles[candles.length - 1] : null;
    const lastTs = last?.timestamp ?? 0;
    const markers: ChartMarker[] = [];
    if (last && signal?.payload.setups.includes('breakout')) {
      markers.push({ kind: 'jet', label: 'جت', timestamp: last.timestamp, price: last.high, dir: 'up' });
    }
    if (last && fts?.double_bottom?.active && fts.double_bottom.neckline != null) {
      markers.push({ kind: 'pullback', label: 'کف دوقلو', timestamp: last.timestamp, price: last.low, dir: 'down' });
    } else if (last && fts?.point_hunt?.active && fts.point_hunt.floor_price != null) {
      markers.push({ kind: 'pullback', label: 'شکار نقطه', timestamp: last.timestamp, price: fts.point_hunt.floor_price, dir: 'down' });
    }
    return {
      maPeriods: [14, 21, 52, 100],
      jet: jet != null && lastTs > 0 ? { price: jet, timestamp: lastTs } : null,
      choch: fts?.choch?.bearish && fts.choch.level != null && lastTs > 0 ? { price: fts.choch.level, timestamp: lastTs, bearish: true } : null,
      fib: fts?.fib ?? null,
      markers,
    };
  }, [series, candles, signal, analysis.data]);

  const noData = !symbol ? tedipx.data.length === 0 : nn.status === 'empty' || (!nn.isLoading && !nn.isError && nn.data.length === 0);

  return (
    <div className="flex flex-col gap-4 xl:flex-row">
      <TechnicalSidebar active={activeLevels} onSelect={selectSymbol} />

      <main className="flex min-w-0 flex-1 flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-base font-black text-text-primary">{symbol || 'کل بورس'}</h2>
          <Badge tone="blue">{toFaDigits(chartRows.length)} کندل</Badge>
          <Badge tone="gray">چارت NahayatNegar (پورت v10)</Badge>
          {signal ? (
            <>
              <Badge tone={DIR_TONE[signal.direction]}>{DIR_LABEL[signal.direction]}</Badge>
              {signal.score != null ? <Badge tone="blue">امتیاز {toFaDigits(signal.score)}</Badge> : null}
            </>
          ) : null}
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            data-testid="open-chart-settings"
            className="mr-auto rounded-full border border-border-accent bg-bg-card px-3 py-1 text-xs font-bold text-accent-blue hover:bg-accent-blue/15"
          >
            تنظیمات چارت
          </button>
        </div>

        {symbol ? <FtsBadgeStrip data={analysis.data?.fts ?? null} empty={analysis.data?.status === 'empty' || noData} /> : null}
        {symbol ? <ReplayBar total={nn.data.length} /> : null}

        {noData ? (
          <div className="glass-panel rounded-2xl p-6 text-center text-xs text-text-muted" data-testid="nn-no-data">
            دادهٔ کندلی برای این نماد از سرور برنگشت (بدون داده — نه ساختگی)
          </div>
        ) : view.splitLayout > 1 ? (
          <SplitChartView
            layout={view.splitLayout}
            data={chartRows}
            palette={paletteFor(theme)}
            layers={layers}
            view={view}
            showRsi
            showVolMa
          />
        ) : (
          <div className="glass-panel overflow-hidden rounded-2xl" data-testid="nn-chart-host">
            <Suspense
              fallback={
                <div className="flex items-center justify-center p-10 text-xs text-text-muted" style={{ height: 420 }} data-testid="nn-loading">
                  در حال بارگذاری چارت...
                </div>
              }
            >
              <NnChart
                initialSymbol={symbol || 'شاخص کل'}
                initialName={symbol || 'شاخص کل'}
                initialMarket="بورس"
                data={chartRows}
                corporateActions={symbol ? nn.actions : []}
                layers={layers}
                onSymbolChange={(s) => selectSymbol(s.symbol)}
              />
            </Suspense>
          </div>
        )}

        {symbol ? <ComparePanel activeSymbol={symbol} /> : <MarketOverview onSelect={selectSymbol} />}

        {symbol ? (
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <FtsTrendPanel data={analysis.data?.fts ?? null} />
            {showFtsCard ? (
              <FtsStatusCard signal={signal} gateBlocked={gateBlocked} jetPrice={null} />
            ) : (
              <div className="glass-panel p-4">
                <h3 className="mb-2 text-sm font-black text-text-primary">داوری ایجنت</h3>
                <p className="text-xs leading-6 text-text-secondary">{signal?.rationale ?? 'در انتظار داده کافی...'}</p>
              </div>
            )}
          </div>
        ) : null}
      </main>

      <ChartSettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} symbol={symbol} />
    </div>
  );
}
