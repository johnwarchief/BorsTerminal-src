// features/technical/routes/TechnicalPage.tsx -- میزکار چارت‌محور تب تکنیکال (T-19)
// چارت‌محور: هدر تک‌خطی مینیمال + چارت تمام‌فضا + داک استاتوس‌بار باریک (۲۸px) + سایدبار جمع‌شو.
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
import { PatternToggles } from '../components/PatternToggles';
import { TechnicalSidebar } from '../components/TechnicalSidebar';
import { ReplayBar } from '../components/ReplayBar';
import { ComparePanel } from '../components/ComparePanel';
import { MarketOverview } from '../components/MarketOverview';
import { ChartSettingsDialog } from '../components/ChartSettingsDialog';
import type { ActiveLevelsView } from '../components/SidebarActiveLevels';
import { useNnChartData, useNnTedipx } from '../nahayatnegar/lib/useNnData';
import { useMarketFeed } from '@features/market/api/useMarketFeed';
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

  const { data: marketData } = useMarketFeed();
  const boardRow = useMemo(() => {
    if (!symbol || !marketData?.data) return null;
    return marketData.data.find((item) => item.symbol === symbol) ?? null;
  }, [symbol, marketData]);

  // اگر هیچ نمادی انتخاب نشده، نماد پیش‌فرض با دیتای کامل ('فولاد') را فعال می‌کنیم
  useEffect(() => {
    if (!symbol) {
      const defaultSym = 'فولاد';
      setStored(defaultSym);
      navigate(`/technical/${encodeURIComponent(defaultSym)}`, { replace: true });
    }
  }, [symbol, navigate, setStored]);

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
    <div className="tv-workbench flex h-[calc(100vh-3rem)] min-h-0 flex-col gap-1 overflow-hidden p-1.5 xl:flex-row">
      <TechnicalSidebar active={activeLevels} onSelect={selectSymbol} />

      <main className="flex min-h-0 min-w-0 flex-1 flex-col gap-1">
        {/* هدر تک‌خطی مینیمال و غنی از اطلاعات نماد */}
        <div className="flex h-9 shrink-0 items-center justify-between border-b border-[var(--hairline)] px-2 bg-bg-secondary/40" data-testid="tech-header">
          <div className="flex items-center gap-2 overflow-hidden">
            <span className="truncate text-sm font-black text-text-primary">{symbol || 'کل بورس'}</span>
            {boardRow?.name && (
              <span className="hidden sm:inline text-xs text-text-muted truncate max-w-[170px]" title={boardRow.name}>
                {boardRow.name}
              </span>
            )}
            {boardRow && (boardRow.p_last != null || boardRow.p_closing != null) && (
              <div className="flex items-center gap-1.5 border-r border-[var(--hairline)] pr-2">
                <span className="num text-xs font-black text-text-primary">
                  {toFaDigits(Math.round(boardRow.p_last ?? boardRow.p_closing ?? 0).toLocaleString('en-US'))}
                </span>
                {boardRow.percent_change != null && (
                  <span
                    className={`num text-2xs font-bold px-1.5 py-0.5 rounded ${
                      boardRow.percent_change >= 0
                        ? 'bg-accent-green/15 text-accent-green'
                        : 'bg-accent-red/15 text-accent-red'
                    }`}
                  >
                    {boardRow.percent_change >= 0 ? '+' : ''}{toFaDigits(boardRow.percent_change.toFixed(2))}%
                  </span>
                )}
              </div>
            )}
            <span className="num text-[11px] text-text-muted hidden md:inline">{toFaDigits(replayRows.length)} کندل</span>
            {signal ? <Badge tone={DIR_TONE[signal.direction]}>{DIR_LABEL[signal.direction]}</Badge> : null}
          </div>

          <div className="mr-auto flex items-center gap-1 shrink-0">
            <button
              type="button"
              data-testid="header-replay"
              aria-pressed={replayActive}
              onClick={() => (replayActive ? stopReplay() : startReplay(Math.max(0, nn.data.length - 1)))}
              className={`rounded border px-2 py-0.5 text-[11px] font-bold transition-colors ${
                replayActive
                  ? 'border-border-accent bg-accent-blue/15 text-accent-blue'
                  : 'border-border-c bg-bg-card text-text-secondary hover:border-border-accent hover:text-accent-blue'
              }`}
            >
              {replayActive ? 'پایان بازپخش' : 'بازپخش'}
            </button>
            <details className="relative" data-testid="header-fts-popover">
              <summary className="cursor-pointer list-none rounded border border-border-c bg-bg-card px-2 py-0.5 text-[11px] font-bold text-text-secondary hover:border-border-accent hover:text-accent-blue">
                FTS
                {signal?.payload.setups.length ? ` · ${toFaDigits(signal.payload.setups.length)}` : ''}
              </summary>
              <div className="absolute left-0 top-full z-50 mt-1 w-[340px] rounded-lg border border-[var(--hairline)] bg-bg-secondary p-2 shadow-xl">
                <FtsBadgeStrip data={analysis.data?.fts ?? null} empty={analysis.data?.status === 'empty' || noData} />
                {signal ? (
                  <p className="mt-1 text-[11px] leading-5 text-text-secondary">
                    {DIR_LABEL[signal.direction]}
                    {signal.score != null ? ` · امتیاز ${toFaDigits(signal.score)}` : ''} — {signal.rationale}
                  </p>
                ) : (
                  <p className="mt-1 text-[11px] text-text-muted">در انتظار دادهٔ کافی...</p>
                )}
              </div>
            </details>
            <button
              type="button"
              onClick={() => setSettingsOpen(true)}
              data-testid="open-chart-settings"
              className="rounded border border-border-c bg-bg-card px-2 py-0.5 text-[11px] font-bold text-text-secondary hover:border-border-accent hover:text-accent-blue"
            >
              تنظیمات
            </button>
          </div>
        </div>

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
                  initialSymbol={symbol || 'فولاد'}
                  initialName={boardRow?.name || symbol || 'فولاد'}
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
              {
                id: 'status',
                label: 'وضعیت FTS',
                node: (
                  <div className="flex flex-col gap-2">
                    <FtsBadgeStrip data={analysis.data?.fts ?? null} empty={analysis.data?.status === 'empty' || noData} />
                    <FtsStatusCard signal={signal} gateBlocked={gateBlocked} jetPrice={null} />
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
        ) : (
          <div className="shrink-0">
            <MarketOverview onSelect={selectSymbol} />
          </div>
        )}
      </main>

      <ChartSettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} symbol={symbol} />
    </div>
  );
}
