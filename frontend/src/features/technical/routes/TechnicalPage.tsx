// features/technical/routes/TechnicalPage.tsx -- صفحه تکنیکال FTS (ایجنت 2)
import { useCallback, useEffect, useMemo, useState, lazy, Suspense } from 'react';
import { useNavigate, useParams } from 'react-router';
import { Badge } from '@shared/components/Badge';
import { EmptyState } from '@shared/components/EmptyState';
import { toFaDigits } from '@shared/lib/fmt';
import { publishSignal } from '@shared/lib/signalBus';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useUiStore } from '@shared/stores/uiStore';
import { detectChoch, ftsMAs, lastValid, majorResistance, maStack } from '../lib/indicators';
import { technicalSignal } from '../signals/technicalSignals';
import { useCandleFeed } from '../api/useCandleFeed';
import { useFundGate } from '../api/useFundGate';
import { useFtsAnalysis } from '../api/useFtsAnalysis';
import { useFtsConfigStore } from '../stores/ftsConfigStore';
import { KLineChartWrapper, type ChartDrawApi, type ChartMarker, type FtsChartLayers, type LastDraw } from '../components/KLineChartWrapper';
import { DrawingToolbar } from '../components/DrawingToolbar';
import { ToolPropertiesPanel } from '../components/ToolPropertiesPanel';
import { ChartSettingsDialog } from '../components/ChartSettingsDialog';

/** موتور Lightweight Charts فقط زمانی بارگذاری می‌شود که کاربر آن را انتخاب کند
    (مسیر قدیم klinecharts دست‌نخورده و ایزوله از خطای احتمالی LW می‌ماند). */
const LwChartWrapper = lazy(() =>
  import('../components/LwChartWrapper').then((m) => ({ default: m.LwChartWrapper })),
);
import { paletteFor } from '../lib/chartPalette';
import { FtsToolbar } from '../components/FtsToolbar';
import { FtsStatusCard } from '../components/FtsStatusCard';
import { FtsBadgeStrip } from '../components/FtsBadgeStrip';
import { FtsBottomStrip } from '../components/FtsBottomStrip';
import { FtsTrendPanel } from '../components/FtsTrendPanel';
import { MarketOverview } from '../components/MarketOverview';
import { TechnicalSidebar } from '../components/TechnicalSidebar';
import type { ActiveLevelsView } from '../components/SidebarActiveLevels';
import { computeTradeLevels } from '../lib/levels';
import { resample } from '../lib/resample';

const MA_PERIODS = [14, 21, 52, 100];

const DIR_TONE = { bullish: 'green', bearish: 'red', neutral: 'gray' } as const;
const DIR_LABEL = { bullish: 'صعودی', bearish: 'نزولی', neutral: 'خنثی' } as const;
const STACK_LABEL = { bull: 'سالم صعودی', bear: 'سالم نزولی', mixed: 'درهم', unknown: 'نامشخص' } as const;

export default function TechnicalPage() {
  const params = useParams();
  const navigate = useNavigate();
  const stored = useSymbolStore((s) => s.symbol);
  const setStored = useSymbolStore((s) => s.setSymbol);
  const symbol = params.symbol ?? stored;
  const theme = useUiStore((s) => s.theme);

  const showMAs = useFtsConfigStore((s) => s.showMAs);
  const showJetTrigger = useFtsConfigStore((s) => s.showJetTrigger);
  const showChoch = useFtsConfigStore((s) => s.showChoch);
  const showFibZones = useFtsConfigStore((s) => s.showFibZones);
  const showSetupMarkers = useFtsConfigStore((s) => s.showSetupMarkers);
  const enforceRiskGates = useFtsConfigStore((s) => s.enforceRiskGates);
  const showFtsCard = useFtsConfigStore((s) => s.showFtsCard);
  const chartType = useFtsConfigStore((s) => s.chartType);
  const chartEngine = useFtsConfigStore((s) => s.chartEngine);
  const timeframe = useFtsConfigStore((s) => s.timeframe);
  const showRsi = useFtsConfigStore((s) => s.showRsi);
  const showVolMa = useFtsConfigStore((s) => s.showVolMa);
  const priceScale = useFtsConfigStore((s) => s.priceScale);
  const showGrid = useFtsConfigStore((s) => s.showGrid);
  const showCrosshair = useFtsConfigStore((s) => s.showCrosshair);
  const [chartApi, setChartApi] = useState<ChartDrawApi | null>(null);
  const [lastDraw, setLastDraw] = useState<LastDraw>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const feed = useCandleFeed(symbol);
  const candles = feed.candles;
  const gate = useFundGate(enforceRiskGates ? symbol : '');
  const analysis = useFtsAnalysis(symbol);

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

  // تایم‌فریم نمایشی: بازنمونه‌گیری کلاینتی از کندل روزانه (روزانه/هفتگی/ماهانه)
  const displayed = useMemo(() => resample(candles, timeframe), [candles, timeframe]);

  const signal = useMemo(
    () =>
      symbol && candles.length > 0
        ? technicalSignal({ symbol, ...series, riskGatePass: gate.pass, enforceRiskGates })
        : null,
    [symbol, candles, series, gate.pass, enforceRiskGates],
  );

  useEffect(() => {
    if (signal) publishSignal(signal);
  }, [signal]);

  const gateBlocked = enforceRiskGates && gate.pass === false;

  const maPanel = useMemo(() => {
    const mas = ftsMAs(series.closes);
    const last = { m14: lastValid(mas[14]), m21: lastValid(mas[21]), m52: lastValid(mas[52]), m100: lastValid(mas[100]) };
    return { ...last, stack: maStack(last.m14, last.m21, last.m52, last.m100) };
  }, [series]);

  const jetPrice = useMemo(() => majorResistance(series.highs.slice(0, -1), 120)?.price ?? null, [series]);
  const chochInfo = useMemo(() => detectChoch(series.highs, series.lows, series.closes, 3), [series]);
  const lastTs = candles.length > 0 ? candles[candles.length - 1].timestamp : 0;

  // مارکر ستاپ جت: فقط وقتی تریگر ثبت شده (شکست + بدنه صعودی + حجم) — از سیگنال محاسبه شده
  const jetTriggered = signal?.payload.setups.includes('breakout') ?? false;
  const lastCandle = candles.length > 0 ? candles[candles.length - 1] : null;
  const ftsJet = analysis.data?.fts?.jet ?? null;
  const pointHunt = analysis.data?.fts?.point_hunt ?? null;
  const doubleBottom = analysis.data?.fts?.double_bottom ?? null;

  // مارکرهای ستاپ از فیلدهای پاسخ چارت: جت (شکست سقف) + شکار نقطه/کف دوقلو (پولبک کم‌ریسک)
  const markers = useMemo<ChartMarker[]>(() => {
    const out: ChartMarker[] = [];
    if (!lastCandle) return out;
    if (jetTriggered || ftsJet?.active) {
      out.push({ kind: 'jet', label: ftsJet?.ath ? 'جت ATH' : 'جت', timestamp: lastCandle.timestamp, price: lastCandle.high, dir: 'up' });
    }
    if (doubleBottom?.active && doubleBottom.neckline != null) {
      out.push({ kind: 'pullback', label: 'کف دوقلو', timestamp: lastCandle.timestamp, price: lastCandle.low, dir: 'down' });
    } else if (pointHunt?.active && pointHunt.floor_price != null) {
      out.push({ kind: 'pullback', label: 'شکار نقطه', timestamp: lastCandle.timestamp, price: pointHunt.floor_price, dir: 'down' });
    }
    return out;
  }, [lastCandle, jetTriggered, ftsJet, pointHunt, doubleBottom]);

  const layers = useMemo<FtsChartLayers>(
    () => ({
      maPeriods: showMAs ? MA_PERIODS : null,
      jet: showJetTrigger && jetPrice != null && lastTs > 0 ? { price: jetPrice, timestamp: lastTs } : null,
      choch:
        showChoch && chochInfo.type && chochInfo.level != null && lastTs > 0
          ? { price: chochInfo.level, timestamp: lastTs, bearish: chochInfo.type === 'bearish' }
          : null,
      fib: showFibZones ? (analysis.data?.fts?.fib ?? null) : null,
      markers: showSetupMarkers ? markers : [],
    }),
    [showMAs, showJetTrigger, showChoch, showFibZones, showSetupMarkers, jetPrice, chochInfo, lastTs, analysis.data, markers],
  );

  // داده ندارد: سرور صریح empty گفته یا تاریخچه خالی است — ماسک نمی شود
  const noData = feed.data?.status === 'empty' || (!feed.isLoading && !feed.isError && candles.length === 0);

  /** انتخاب نماد از سایدبار: همان نماد روی چارت + پرش به روت نماد */
  const selectSymbol = useCallback(
    (s: string) => {
      if (!s) return;
      setStored(s);
      navigate(`/technical/${encodeURIComponent(s)}`);
    },
    [navigate, setStored],
  );

  /** نمای «ترازها و حد ضرر» سایدبار برای نماد فعال */
  const activeLevels = useMemo<ActiveLevelsView>(() => {
    const fib = analysis.data?.fts?.fib ?? null;
    const { swingLow, stop5pct } = computeTradeLevels(series.lows);
    return {
      symbol,
      zone3340: fib?.zone_33_40 ? { lo: fib.zone_33_40.lo ?? null, hi: fib.zone_33_40.hi ?? null } : null,
      zone61870: fib?.zone_618_70 ? { lo: fib.zone_618_70.lo ?? null, hi: fib.zone_618_70.hi ?? null } : null,
      baseLevel: fib?.retrace_base_low ?? null,
      ma100: maPanel.m100,
      swingLow,
      stop5pct,
      keyLevels: signal?.payload.keyLevels ?? [],
      stopLoss: signal?.payload.stopLossPrice ?? null,
      lastClose: lastCandle?.close ?? null,
      setups: signal?.payload.setups ?? [],
      direction: signal?.direction ?? null,
    };
  }, [analysis.data, series.lows, maPanel.m100, signal, symbol, lastCandle]);

  return (
    <div className="flex flex-col gap-4 xl:flex-row">
      <TechnicalSidebar active={activeLevels} onSelect={selectSymbol} />

      <main className="flex min-w-0 flex-1 flex-col gap-4">
        {!symbol ? (
          // بدون نماد: چارت کل بورس (نمای کلان بازار)، نه صفحهٔ خالی/بن‌بست
          <MarketOverview onSelect={selectSymbol} />
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-black text-text-primary">{symbol}</h2>
              <Badge tone="blue">{toFaDigits(candles.length)} کندل روزانه</Badge>
              {feed.source ? (
                <Badge tone="gray">{feed.source === 'chart' ? 'کندل تعدیل‌شدهٔ TSETMC' : 'تاریخچهٔ محلی'}</Badge>
              ) : null}
              {signal ? (
                <>
                  <Badge tone={DIR_TONE[signal.direction]}>{DIR_LABEL[signal.direction]}</Badge>
                  {signal.score != null ? <Badge tone="blue">امتیاز {toFaDigits(signal.score)}</Badge> : null}
                  {signal.payload.dataQuality === 'partial' ? <Badge tone="yellow">داده جزئی</Badge> : null}
                </>
              ) : null}
              {feed.isLoading ? <span className="text-xs text-text-secondary">در حال دریافت...</span> : null}
              {feed.isError ? <span className="text-xs text-accent-red">خطا در دریافت تاریخچه</span> : null}
            </div>

            <FtsBadgeStrip data={analysis.data?.fts ?? null} empty={analysis.data?.status === 'empty' || noData} />

            <FtsToolbar onOpenSettings={() => setSettingsOpen(true)} />

            {noData ? (
              <EmptyState
                title="تاریخچه قیمتی برای این نماد نیست"
                hint="سرور برای این نماد کندلی برنگرداند؛ ممکن است نماد جدید باشد یا هنوز همگام سازی نشده"
              />
            ) : (
              <>
                <ToolPropertiesPanel api={chartApi} last={lastDraw} />

                <div className="flex items-start gap-2">
                <DrawingToolbar api={chartApi} />
                <div className="flex min-w-0 flex-1 flex-col gap-4">
                  {chartEngine === 'lightweight' ? (
                    <Suspense
                      fallback={
                        <div
                          className="glass-panel flex items-center justify-center rounded-2xl p-10 text-xs text-text-muted"
                          style={{ height: 600 }}
                          data-testid="lw-loading"
                        >
                          در حال بارگذاری موتور Lightweight Charts...
                        </div>
                      }
                    >
                      <LwChartWrapper
                        data={displayed}
                        palette={paletteFor(theme)}
                        height={600}
                        showRsi={showRsi}
                        showVolMa={showVolMa}
                      />
                    </Suspense>
                  ) : (
                    <KLineChartWrapper
                      data={displayed}
                      palette={paletteFor(theme)}
                      layers={layers}
                      height={600}
                      chartType={chartType}
                      showRsi={showRsi}
                      showVolMa={showVolMa}
                      priceScale={priceScale}
                      showGrid={showGrid}
                      showCrosshair={showCrosshair}
                      onApi={setChartApi}
                      onDrawChange={setLastDraw}
                    />
                  )}
                  <FtsBottomStrip
                    data={{
                      mas: { 14: maPanel.m14, 21: maPanel.m21, 52: maPanel.m52, 100: maPanel.m100 },
                      stackLabel: STACK_LABEL[maPanel.stack],
                      stackTone: maPanel.stack === 'bull' ? 'green' : maPanel.stack === 'bear' ? 'red' : 'gray',
                      setups: signal?.payload.setups ?? [],
                      resistance: jetPrice,
                      support: signal?.payload.keyLevels.find((k) => k.type === 'support')?.price ?? null,
                      stopLoss: signal?.payload.stopLossPrice ?? null,
                    }}
                  />
                </div>
              </div>
              </>
            )}

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
              <FtsTrendPanel data={analysis.data?.fts ?? null} />

              {showFtsCard ? (
                <FtsStatusCard signal={signal} gateBlocked={gateBlocked} jetPrice={jetPrice} />
              ) : (
                <div className="glass-panel p-4">
                  <h3 className="mb-2 text-sm font-black text-text-primary">داوری ایجنت</h3>
                  <p className="text-xs leading-6 text-text-secondary">{signal?.rationale ?? 'در انتظار داده کافی...'}</p>
                </div>
              )}
            </div>
          </>
        )}
      </main>

      <ChartSettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}
