// features/technical/routes/TechnicalPage.tsx -- میزکار چارت‌محور تب تکنیکال (T-19)
// چارت‌محور: هدر تک‌خطی مینیمال + چارت تمام‌فضا + داک استاتوس‌بار باریک (۲۸px) + سایدبار جمع‌شو.
import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router';
import { publishSignal } from '@shared/lib/signalBus';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useUiStore } from '@shared/stores/uiStore';
import { useFtsConfigStore } from '../stores/ftsConfigStore';
import { useReplayStore } from '../stores/replayStore';
import { clampCursor, isAtEnd, stepCursor } from '../lib/replay';
import { computeTradeLevels } from '../lib/levels';
import { useCandleFeed } from '../api/useCandleFeed';
import { useFundGate } from '../api/useFundGate';
import { useFtsAnalysis } from '../api/useFtsAnalysis';
import { technicalSignal } from '../signals/technicalSignals';
import { FtsBadgeStrip } from '../components/FtsBadgeStrip';
import { FtsTrendPanel } from '../components/FtsTrendPanel';
import { FtsStatusCard } from '../components/FtsStatusCard';
import { FtsDock } from '../components/FtsDock';
import { PatternToggles } from '../components/PatternToggles';
import { TechnicalSidebar } from '../components/TechnicalSidebar';
import { ReplayBar } from '../components/ReplayBar';
import { ComparePanel } from '../components/ComparePanel';
import { ChartSettingsDialog } from '../components/ChartSettingsDialog';
import type { ActiveLevelsView } from '../components/SidebarActiveLevels';
import { useNnChartData, useNnTedipx } from '../nahayatnegar/lib/useNnData';
import { useMarketFeed } from '@features/market/api/useMarketFeed';
import '../styles/tvTheme.css';

/** چارت پورت‌شدهٔ جمینای (v10) با React.lazy تا چانک صفحهٔ تکنیکال سبک بماند */
const NnChart = lazy(() => import('../nahayatnegar/components/KLineChartWrapper'));


export default function TechnicalPage() {
  const params = useParams();
  const navigate = useNavigate();
  const stored = useSymbolStore((s) => s.symbol);
  const setStored = useSymbolStore((s) => s.setSymbol);
  const symbol = params.symbol ?? stored;
  // نماد پیش‌فرضِ نمایشی («فولاد») فقط به چارت داده می‌شود؛ هرگز در استورِ سراسری
  // یا آدرس نوشته نمی‌شود — پیش از این اینجا نوشته می‌شد و همان نماد در تب تابلو
  // و سایدبار «انتخاب‌شده» می‌ماند، هرچند کاربر هیچ‌وقت آن را انتخاب نکرده بود.
  const viewSymbol = symbol || 'فولاد';

  const { data: marketData } = useMarketFeed();
  const boardRow = useMemo(() => {
    if (!marketData?.data) return null;
    return marketData.data.find((item) => item.symbol === viewSymbol) ?? null;
  }, [viewSymbol, marketData]);

  // جمع شدن خودکار نوار اصلی سمت راست هنگام ورود به تب تکنیکال جهت بیشینه‌سازی بوم چارت.
  // هنگام خروج از تب، حالت را به «خودکار» برمی‌گردانیم تا سایدبار روی سایر تب‌ها بماند.
  useEffect(() => {
    useUiStore.getState().setSidebarCollapsed(true);
    return () => {
      useUiStore.getState().setSidebarCollapsed(null);
    };
  }, []);

  const enforceRiskGates = useFtsConfigStore((s) => s.enforceRiskGates);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const replayActive = useReplayStore((s) => s.active);
  const replayCursor = useReplayStore((s) => s.cursor);
  const replayPlaying = useReplayStore((s) => s.playing);
  const replaySpeed = useReplayStore((s) => s.speedMs);
  const setReplayCursor = useReplayStore((s) => s.setCursor);
  const setReplayPlaying = useReplayStore((s) => s.setPlaying);
  const startReplay = useReplayStore((s) => s.start);
  const stopReplay = useReplayStore((s) => s.stop);

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
    // MA(100) خط ماژور: میانگین ۱۰۰ بستهٔ آخر؛ null اگر تاریخچه کمتر از ۱۰۰ کندل است
    const closes = series.closes.filter((x) => Number.isFinite(x));
    const ma100 =
      closes.length >= 100
        ? Math.round(closes.slice(-100).reduce((a, b) => a + b, 0) / 100)
        : null;
    return {
      symbol,
      zone3340: fib?.zone_33_40 ? { lo: fib.zone_33_40.lo ?? null, hi: fib.zone_33_40.hi ?? null } : null,
      zone61870: fib?.zone_618_70 ? { lo: fib.zone_618_70.lo ?? null, hi: fib.zone_618_70.hi ?? null } : null,
      baseLevel: fib?.retrace_base_low ?? null,
      ma100,
      swingLow,
      stop5pct,
      keyLevels: signal?.payload.keyLevels ?? [],
      stopLoss: signal?.payload.stopLossPrice ?? null,
      lastClose: candles.length > 0 ? candles[candles.length - 1].close : null,
      setups: signal?.payload.setups ?? [],
      direction: signal?.direction ?? null,
    };
  }, [analysis.data, series.lows, series.closes, signal, symbol, candles]);

  const noData = !symbol ? tedipx.data.length === 0 : nn.status === 'empty' || (!nn.isLoading && !nn.isError && nn.data.length === 0);

  return (
    <div className="tv-workbench flex h-[calc(100dvh-3rem)] min-h-0 min-w-0 w-full flex-col overflow-hidden xl:flex-row">
      <TechnicalSidebar active={activeLevels} onSelect={selectSymbol} />

      <main className="flex min-h-0 min-w-0 flex-1 flex-col">
        {/* چارت تمام‌فضا (بدون کادر تودرتو/حاشیهٔ مرده) */}
        <div className="relative min-h-0 min-w-0 flex-1" data-testid="chart-area">
          {noData ? (
            <div className="flex h-full items-center justify-center text-xs text-text-muted" data-testid="nn-no-data">
              دادهٔ کندلی برای این نماد از سرور برنگشت (بدون داده — نه ساختگی)
            </div>
          ) : (
            <div className="h-full w-full overflow-hidden" data-testid="nn-chart-host">
              <Suspense
                fallback={
                  <div className="flex h-full items-center justify-center text-xs text-text-muted" data-testid="nn-loading">
                    در حال بارگذاری چارت...
                  </div>
                }
              >
                <NnChart
                  initialSymbol={viewSymbol}
                  initialName={boardRow?.name || viewSymbol}
                  boardRow={boardRow}
                  replayActive={replayActive}
                  onToggleReplay={() => (replayActive ? stopReplay() : startReplay(Math.max(0, nn.data.length - 1)))}
                  onOpenSettings={() => setSettingsOpen(true)}
                  onSymbolChange={(s) => selectSymbol(s.symbol)}
                />
              </Suspense>
            </div>
          )}
        </div>

        {symbol ? (
          <FtsDock
            tabs={[
              {
                id: 'status',
                label: 'وضعیت FTS',
                node: (
                  <div className="flex flex-col gap-2">
                    <FtsBadgeStrip data={analysis.data?.fts ?? null} empty={analysis.data?.status === 'empty' || noData} />
                    <FtsStatusCard signal={signal} gateBlocked={gateBlocked} jetPrice={analysis.data?.fts?.jet?.resistance ?? null} />
                  </div>
                ),
              },
              { id: 'trend', label: 'تحلیل ساختاری', node: <FtsTrendPanel data={analysis.data?.fts ?? null} /> },
              { id: 'replay', label: 'بازپخش', node: <ReplayBar total={nn.data.length} /> },
              { id: 'patterns', label: 'الگوهای FTS', node: <PatternToggles /> },

              { id: 'compare', label: 'مقایسهٔ نمادها', node: <ComparePanel activeSymbol={symbol} /> },
              {
                id: 'verdict',
                label: 'داوری',
                node: (
                  <div className="p-1">
                    <p className="text-xs leading-6 text-text-secondary">{signal?.rationale ?? 'در انتظار داده کافی...'}</p>
                  </div>
                ),
              },
            ]}
          />
        ) : null}
      </main>

      <ChartSettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} symbol={symbol} />
    </div>
  );
}
