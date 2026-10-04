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
import { FtsEngineChart } from '../components/FtsEngineChart';
import { aggregateCandles, type Timeframe as ChartTimeframe } from '../nahayatnegar/lib/timeframe';
import type { EngineBar } from '../engine';
import { useCandleFeed } from '../api/useCandleFeed';
import { useFundGate } from '../api/useFundGate';
import { useFtsAnalysis } from '../api/useFtsAnalysis';
import { technicalSignal } from '../signals/technicalSignals';
import { weeklyFromFts } from '../lib/weeklyFromFts';
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
import { applyAdjustmentToCandles, mapBackendAdjustEvents } from '../nahayatnegar/lib/adjustments';
import { useMarketFeed } from '@features/market/api/useMarketFeed';
import { usePriceAlertWatch } from '../lib/usePriceAlertWatch';
import { PriceAlertBanner } from '../nahayatnegar/components/PriceAlertBanner';
import '../styles/tvTheme.css';

/** چارت پورت‌شدهٔ جمینای (v10) با React.lazy تا چانک صفحهٔ تکنیکال سبک بماند */
const NnChart = lazy(() => import('../nahayatnegar/components/KLineChartWrapper'));

/** تایم‌فریمِ استور ('day'|'week'|'month') → واژهٔ لایۀ تجمیع ('D'|'W'|'M') */
const TF_TO_CHART: Record<string, ChartTimeframe> = { day: 'D', week: 'W', month: 'M' };


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

  // هشدارهایِ قیمتی روی همین فید داوری می‌شوند — برای هر نمادی که کاربر
  // آستانه گذاشته، نه فقط نمادِ بازِ چارت.
  usePriceAlertWatch(marketData?.data);

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

  // داکِ پایین و پنل‌های FTS از همین نمادِ نمایشی تغذیه می‌شوند. پیش‌تر روی
  // `symbol` (تهی تا کاربر چیزی انتخاب نکند) قفل بودند، پس پنل‌هایِ پایینِ تب
  // برای کسی که هنوز نمادی انتخاب نکرده اصلاً در DOM نمی‌آمد (#185).
  const nn = useNnChartData(viewSymbol);
  const tedipx = useNnTedipx();
  const feed = useCandleFeed(viewSymbol);
  const analysis = useFtsAnalysis(viewSymbol);
  const gate = useFundGate(enforceRiskGates ? viewSymbol : '');

  // سیگنالِ تکنیکال باید همان سریِ تعدیل‌شده‌ای را ببیند که چارت می‌رسمد و موتورِ
  // FTSِ سرور تحلیل می‌کند. پیش‌تر روی کندلِ خام می‌دوید: دو طرفِ یک افزایشِ سرمایه
  // دو مقیاسِ قیمتی‌اند، پس MA/مقاومت/فیبو قاطی می‌شد (شاهد: کايزد ۵۸۱۰ ← ۲۶۴۲).
  const adjustEvents = feed.data?.adjustEvents;
  const candles = useMemo(
    () => applyAdjustmentToCandles(feed.candles, mapBackendAdjustEvents(adjustEvents ?? []), 'combined'),
    [feed.candles, adjustEvents],
  );

  // موتورِ دوم (FFC): همان کندلِ تعدیل‌شده، همان تجمیع، همان تحلیلِ سرور -- فقط
  // رندرِ دیگر. پیش‌فرضِ تولید klinecharts می‌ماند؛ انتخابِ کاربر در
  // fts.chart.settings.v1 ذخیره می‌شود.
  const chartEngine = useFtsConfigStore((s) => s.chartEngine);
  const setChartEngine = useFtsConfigStore((s) => s.setChartEngine);
  const storeTimeframe = useFtsConfigStore((s) => s.timeframe);
  const storeChartType = useFtsConfigStore((s) => s.chartType);
  const storePriceScale = useFtsConfigStore((s) => s.priceScale);
  const theme = useUiStore((s) => s.theme);
  const engineBars = useMemo<EngineBar[]>(
    () =>
      aggregateCandles(candles, TF_TO_CHART[storeTimeframe] ?? 'D').map((c) => ({
        timestamp: c.timestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        volume: c.volume ?? 0,
      })),
    [candles, storeTimeframe],
  );
  const engineStyle =
    storeChartType === 'line' ? 'line'
      : storeChartType === 'area' ? 'area'
      : storeChartType === 'ohlc' ? 'bars'
      : storeChartType === 'heikin_ashi' ? 'heikin'
      : 'candles';

  // رأیِ هفتگی از همان موتورِ FTSِ سرور می‌آید و داخلِ سیگنال منتشر می‌شود؛ گیتِ
  // وتوی هفتگیِ تبِ مستر و سایدبارِ چپ فقط از همین می‌خوانند. پیش‌تر هیچ‌کس این
  // سه فیلد را تولید نمی‌کرد و گیت برای هر نمادی «در انتظار» می‌ماند ⇒
  // «توقف در فیلتر دوم» (شاهد: کايزد با ۱۵۲٪ صعودِ هفتگی).
  const weekly = useMemo(() => weeklyFromFts(analysis.data?.fts), [analysis.data]);

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
    () =>
      candles.length > 0
        ? technicalSignal({
            symbol: viewSymbol,
            ...series,
            riskGatePass: gate.pass,
            enforceRiskGates,
            weekly,
            // همان شیئی که چارت و پنل «وضعیت FTS» می‌خوانند؛ تنها منبعِ تشخیص
            fts: analysis.data?.fts ?? null,
          })
        : null,
    [viewSymbol, candles, series, gate.pass, enforceRiskGates, weekly, analysis.data],
  );
  useEffect(() => {
    if (signal) publishSignal(signal);
  }, [signal]);
  const gateBlocked = enforceRiskGates && gate.pass === false;

  useEffect(() => {
    if (!replayActive || !replayPlaying) return;
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
    // خط ماژور MA(100): میانگین ۱۰۰ بستهٔ آخر؛ null اگر تاریخچه کمتر از ۱۰۰ کندل است
    const closes = series.closes.filter((x) => Number.isFinite(x));
    const ma100 =
      closes.length >= 100
        ? Math.round(closes.slice(-100).reduce((a, b) => a + b, 0) / 100)
        : null;
    return {
      symbol: viewSymbol,
      fts: analysis.data?.fts ?? null,
      ma100,
      lastClose: candles.length > 0 ? candles[candles.length - 1].close : null,
      setups: signal?.payload.setups ?? [],
      context: signal?.payload.context ?? [],
      direction: signal?.direction ?? null,
    };
  }, [analysis.data, series.closes, signal, viewSymbol, candles]);

  const noData = !symbol ? tedipx.data.length === 0 : nn.status === 'empty' || (!nn.isLoading && !nn.isError && nn.data.length === 0);

  return (
    <div className="tv-workbench flex h-[calc(100dvh-3rem)] min-h-0 min-w-0 w-full flex-col overflow-hidden xl:flex-row">
      <TechnicalSidebar active={activeLevels} symbol={viewSymbol} onSelect={selectSymbol} />

      <main className="flex min-h-0 min-w-0 flex-1 flex-col">
        {/* چارت تمام‌فضا (بدون کادر تودرتو/حاشیهٔ مرده) */}
        <div className="relative min-h-0 min-w-0 flex-1" data-testid="chart-area">
          {chartEngine === 'ffc' ? (
            <div className="h-full w-full overflow-hidden" data-testid="ffc-chart-host">
              <FtsEngineChart
                engineId="ffc"
                bars={engineBars}
                fts={analysis.data?.fts ?? null}
                dark={theme !== 'light'}
                logScale={storePriceScale === 'logarithm'}
                candleStyle={engineStyle}
                onEngineChange={setChartEngine}
              />
            </div>
          ) : noData ? (
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
                  fts={analysis.data?.fts ?? null}
                  replayActive={replayActive}
                  chartEngine={chartEngine}
                  onEngineChange={setChartEngine}
                  onToggleReplay={() => (replayActive ? stopReplay() : startReplay(Math.max(0, nn.data.length - 1)))}
                  onOpenSettings={() => setSettingsOpen(true)}
                  onSymbolChange={(s) => selectSymbol(s.symbol)}
                />
              </Suspense>
            </div>
          )}
          <PriceAlertBanner rows={marketData?.data} />
        </div>

        <FtsDock
          tabs={[
            {
              id: 'status',
              label: 'وضعیت FTS',
              node: (
                <div className="flex flex-col gap-2">
                  <FtsBadgeStrip
                    data={analysis.data?.fts ?? null}
                    empty={analysis.data?.status === 'empty' || noData}
                    error={
                      analysis.data?.status === 'error'
                        ? analysis.data.message || 'موتور تحلیل خطا داد'
                        : analysis.isError
                          ? 'تحلیل از سرور گرفته نشد'
                          : null
                    }
                  />
                  <FtsStatusCard
                    signal={signal}
                    gateBlocked={gateBlocked}
                    jetPrice={analysis.data?.fts?.jet?.resistance ?? null}
                    jetReason={analysis.data?.fts?.jet?.reason ?? null}
                    trigger={analysis.data?.fts?.status?.trigger ?? null}
                  />
                </div>
              ),
            },
            { id: 'trend', label: 'تحلیل ساختاری', node: <FtsTrendPanel data={analysis.data?.fts ?? null} /> },
            { id: 'replay', label: 'بازپخش', node: <ReplayBar total={nn.data.length} /> },
            { id: 'patterns', label: 'الگوهای FTS', node: <PatternToggles /> },

            { id: 'compare', label: 'مقایسهٔ نمادها', node: <ComparePanel activeSymbol={viewSymbol} /> },
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
      </main>

      <ChartSettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} symbol={symbol} />
    </div>
  );
}
