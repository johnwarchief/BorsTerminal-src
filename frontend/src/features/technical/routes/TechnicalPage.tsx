// features/technical/routes/TechnicalPage.tsx -- میزکار تمام‌صفحهٔ تب تکنیکال (T-18)
// چیدمان full-bleed بدون اسکرول عمودی: هدر فشرده + چارت flex-1 + داک کشویی پایین + سایدبار راست.
import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router';
import { Badge } from '@shared/components/Badge';
import { toFaDigits } from '@shared/lib/fmt';
import { publishSignal } from '@shared/lib/signalBus';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useUiStore } from '@shared/stores/uiStore';
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
import { FtsDock } from '../components/FtsDock';
import { TechnicalSidebar } from '../components/TechnicalSidebar';
import { ReplayBar } from '../components/ReplayBar';
import { ComparePanel } from '../components/ComparePanel';
import { MarketOverview } from '../components/MarketOverview';
import { ChartSettingsDialog } from '../components/ChartSettingsDialog';
import type { ActiveLevelsView } from '../components/SidebarActiveLevels';
import { useNnChartData, useNnTedipx } from '../nahayatnegar/lib/useNnData';
import '../styles/tvTheme.css';

/** چارت پورت‌شدهٔ جمینای (v10) با React.lazy تا چانک صفحهٔ تکنیکال سبک بماند */
const NnChart = lazy(() => import('../nahayatnegar/components/KLineChartWrapper'));

const DIR_TONE = { bullish: 'green', bearish: 'red', neutral: 'gray' } as const;
const DIR_LABEL = { bullish: 'صعودی', bearish: 'نزولی', neutral: 'خنثی' } as const;

export default function TechnicalPage() {
  const params = useParams();
  const navigate = useNavigate();
  const stored = useSymbolStore((s) => s.symbol);
  const setStored = useSymbolStore((s) => s.setSymbol);
  const symbol = params.symbol ?? stored;
  const theme = useUiStore((s) => s.theme);

  const enforceRiskGates = useFtsConfigStore((s) => s.enforceRiskGates);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const replayActive = useReplayStore((s) => s.active);
  const replayCursor = useReplayStore((s) => s.cursor);
  const replayPlaying = useReplayStore((s) => s.playing);
  const replaySpeed = useReplayStore((s) => s.speedMs);
  const setReplayCursor = useReplayStore((s) => s.setCursor);
  const setReplayPlaying = useReplayStore((s) => s.setPlaying);

  const nn = useNnChartData(symbol);
  const tedipx = useNnTedipx();
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

  const replayRows = useMemo(
    () => (replayActive ? replaySlice(nn.data, replayCursor) : nn.data),
    [replayActive, nn.data, replayCursor],
  );

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
      ma100: null,
      swingLow,
      stop5pct,
      keyLevels: signal?.payload.keyLevels ?? [],
      stopLoss: signal?.payload.stopLossPrice ?? null,
      lastClose: candles.length > 0 ? candles[candles.length - 1].close : null,
      setups: signal?.payload.setups ?? [],
      direction: signal?.direction ?? null,
    };
  }, [analysis.data, series.lows, signal, symbol, candles]);

  const noData = !symbol ? tedipx.data.length === 0 : nn.status === 'empty' || (!nn.isLoading && !nn.isError && nn.data.length === 0);

  return (
    <div className="tv-workbench flex h-[calc(100vh-3.25rem)] min-h-0 flex-col gap-2 overflow-hidden p-2 xl:flex-row">
      <TechnicalSidebar active={activeLevels} onSelect={selectSymbol} />

      <main className="flex min-h-0 min-w-0 flex-1 flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-black text-text-primary">{symbol || 'کل بورس'}</h2>
          <Badge tone="blue">{toFaDigits(replayRows.length)} کندل</Badge>
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

        <div className="min-h-0 min-w-0 flex-1" data-testid="chart-area">
          {noData ? (
            <div className="glass-panel flex h-full items-center justify-center rounded-2xl text-xs text-text-muted" data-testid="nn-no-data">
              دادهٔ کندلی برای این نماد از سرور برنگشت (بدون داده — نه ساختگی)
            </div>
          ) : (
            <div className="glass-panel h-full overflow-hidden rounded-2xl" data-testid="nn-chart-host">
              <Suspense
                fallback={
                  <div className="flex h-full items-center justify-center text-xs text-text-muted" data-testid="nn-loading">
                    در حال بارگذاری چارت...
                  </div>
                }
              >
                <NnChart
                  initialSymbol={symbol || 'شاخص کل'}
                  initialName={symbol || 'شاخص کل'}
                  initialMarket="بورس"
                  onSymbolChange={(s) => selectSymbol(s.symbol)}
                />
              </Suspense>
            </div>
          )}
        </div>

        {symbol ? (
          <FtsDock
            tabs={[
              { id: 'status', label: 'وضعیت FTS', node: <FtsStatusCard signal={signal} gateBlocked={gateBlocked} jetPrice={null} /> },
              { id: 'trend', label: 'تحلیل ساختاری', node: <FtsTrendPanel data={analysis.data?.fts ?? null} /> },
              { id: 'compare', label: 'مقایسهٔ نمادها', node: <ComparePanel activeSymbol={symbol} /> },
              {
                id: 'verdict',
                label: 'داوری ایجنت',
                node: (
                  <div className="glass-panel p-3">
                    <p className="text-xs leading-6 text-text-secondary">{signal?.rationale ?? 'در انتظار داده کافی...'}</p>
                  </div>
                ),
              },
            ]}
          />
        ) : (
          <div className="shrink-0">
            <MarketOverview onSelect={selectSymbol} />
          </div>
        )}
      </main>

      <ChartSettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} symbol={symbol} />
      {/* theme در پالت چارت استفاده می‌شود */}
      <span className="hidden" data-theme={theme} />
    </div>
  );
}
