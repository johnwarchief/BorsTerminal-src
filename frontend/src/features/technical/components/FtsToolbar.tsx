// features/technical/components/FtsToolbar.tsx -- تولبار ابزارهای چارت به سبک تریدینگ‌ویو
// گروه‌ها: تایم‌فریم · نوع چارت · مقیاس و نمایش · اندیکاتورها · لایه‌های FTS.
// آیتم‌ها/فیلدها بر مبنای docs/CHART-PARITY-REFERENCE.md؛ بدون ایموجی.
import {
  useFtsConfigStore,
  type ChartType,
  type DisplayKey,
  type IndicatorKey,
  type PriceScale,
  type Timeframe,
  type FtsLayerKey,
} from '../stores/ftsConfigStore';

const LAYERS: { key: FtsLayerKey; label: string }[] = [
  { key: 'showMAs', label: 'مووینگ ها' },
  { key: 'showJetTrigger', label: 'خط آبی' },
  { key: 'showChoch', label: 'خط چین قرمز' },
  { key: 'showFibZones', label: 'کمربند فیبو' },
  { key: 'showSetupMarkers', label: 'مارکر ستاپ' },
  { key: 'enforceRiskGates', label: 'گیت ریسک' },
  { key: 'showFtsCard', label: 'کارت وضعیت' },
];

const TIMEFRAMES: { key: Timeframe; label: string; title: string }[] = [
  { key: 'day', label: 'روزانه', title: 'D' },
  { key: 'week', label: 'هفتگی', title: 'W' },
  { key: 'month', label: 'ماهانه', title: 'M' },
];

const CHART_TYPES: { key: ChartType; label: string }[] = [
  { key: 'candle_solid', label: 'کندل' },
  { key: 'candle_stroke', label: 'کندل توخالی' },
  { key: 'ohlc', label: 'بار' },
  { key: 'line', label: 'خط' },
  { key: 'area', label: 'اریا' },
];

const PRICE_SCALES: { key: PriceScale; label: string }[] = [
  { key: 'normal', label: 'خطی' },
  { key: 'logarithm', label: 'لگاریتمی' },
  { key: 'percentage', label: 'درصدی' },
];

const DISPLAY: { key: DisplayKey; label: string }[] = [
  { key: 'grid', label: 'شبکه' },
  { key: 'crosshair', label: 'کراس‌هیر' },
];

const INDICATORS: { key: IndicatorKey; label: string; title: string }[] = [
  { key: 'rsi', label: 'RSI(14)', title: 'RSI وایلدر دورهٔ ۱۴ در پنل جدا' },
  { key: 'volMa', label: 'MA حجم ۲۱', title: 'میانگین متحرک حجم دورهٔ ۲۱ روی پنل حجم' },
];

function Chip({ active, label, onClick, title }: { active: boolean; label: string; onClick: () => void; title?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      title={title}
      className={`rounded-full border px-3 py-1 text-xs font-semibold transition-colors ${
        active
          ? 'border-border-accent bg-accent-blue/15 text-accent-blue'
          : 'border-border-c bg-bg-card text-text-muted hover:text-text-secondary'
      }`}
    >
      {label}
    </button>
  );
}

function GroupLabel({ children }: { children: React.ReactNode }) {
  return <span className="px-1 text-[10px] font-bold text-text-muted">{children}</span>;
}

function Divider() {
  return <span aria-hidden className="mx-1 h-5 w-px shrink-0 bg-border-c" />;
}

export function FtsToolbar({ onOpenSettings }: { onOpenSettings?: () => void }) {
  const chartType = useFtsConfigStore((s) => s.chartType);
  const timeframe = useFtsConfigStore((s) => s.timeframe);
  const priceScale = useFtsConfigStore((s) => s.priceScale);
  const showGrid = useFtsConfigStore((s) => s.showGrid);
  const showCrosshair = useFtsConfigStore((s) => s.showCrosshair);
  const showRsi = useFtsConfigStore((s) => s.showRsi);
  const showVolMa = useFtsConfigStore((s) => s.showVolMa);
  const showFtsCard = useFtsConfigStore((s) => s.showFtsCard);
  const showMAs = useFtsConfigStore((s) => s.showMAs);
  const showJetTrigger = useFtsConfigStore((s) => s.showJetTrigger);
  const showChoch = useFtsConfigStore((s) => s.showChoch);
  const showFibZones = useFtsConfigStore((s) => s.showFibZones);
  const showSetupMarkers = useFtsConfigStore((s) => s.showSetupMarkers);
  const enforceRiskGates = useFtsConfigStore((s) => s.enforceRiskGates);
  const setChartType = useFtsConfigStore((s) => s.setChartType);
  const setTimeframe = useFtsConfigStore((s) => s.setTimeframe);
  const setPriceScale = useFtsConfigStore((s) => s.setPriceScale);
  const toggleDisplay = useFtsConfigStore((s) => s.toggleDisplay);
  const toggleIndicator = useFtsConfigStore((s) => s.toggleIndicator);
  const toggle = useFtsConfigStore((s) => s.toggle);

  const layerStates: Record<FtsLayerKey, boolean> = {
    showMAs,
    showJetTrigger,
    showChoch,
    showFibZones,
    showSetupMarkers,
    enforceRiskGates,
    showFtsCard,
  };
  const displayStates: Record<DisplayKey, boolean> = { grid: showGrid, crosshair: showCrosshair };

  return (
    <div className="glass-panel flex flex-wrap items-center gap-1.5 rounded-2xl p-3" role="toolbar" aria-label="ابزارهای چارت تکنیکال">
      <GroupLabel>تایم‌فریم</GroupLabel>
      {TIMEFRAMES.map((t) => (
        <Chip key={t.key} active={timeframe === t.key} label={t.label} onClick={() => setTimeframe(t.key)} title={`${t.title} — بازنمونه‌گیری از کندل روزانه`} />
      ))}

      <Divider />

      <GroupLabel>نوع چارت</GroupLabel>
      {CHART_TYPES.map((c) => (
        <Chip key={c.key} active={chartType === c.key} label={c.label} onClick={() => setChartType(c.key)} />
      ))}

      <Divider />

      <GroupLabel>مقیاس قیمت</GroupLabel>
      {PRICE_SCALES.map((p) => (
        <Chip key={p.key} active={priceScale === p.key} label={p.label} onClick={() => setPriceScale(p.key)} />
      ))}

      <Divider />

      <GroupLabel>نمایش</GroupLabel>
      {DISPLAY.map((d) => (
        <Chip key={d.key} active={displayStates[d.key]} label={`${d.label}: ${displayStates[d.key] ? 'روشن' : 'خاموش'}`} onClick={() => toggleDisplay(d.key)} />
      ))}

      <Divider />

      <GroupLabel>اندیکاتورها</GroupLabel>
      {INDICATORS.map((ind) => (
        <Chip
          key={ind.key}
          active={ind.key === 'rsi' ? showRsi : showVolMa}
          label={ind.label}
          onClick={() => toggleIndicator(ind.key)}
          title={ind.title}
        />
      ))}

      <Divider />

      <GroupLabel>لایه‌های FTS</GroupLabel>
      {LAYERS.map((it) => (
        <Chip
          key={it.key}
          active={layerStates[it.key]}
          label={`${it.label}: ${layerStates[it.key] ? 'روشن' : 'خاموش'}`}
          onClick={() => toggle(it.key)}
        />
      ))}

      {onOpenSettings ? (
        <>
          <Divider />
          <button
            type="button"
            onClick={onOpenSettings}
            data-testid="open-chart-settings"
            className="rounded-full border border-border-accent bg-bg-card px-3 py-1 text-xs font-bold text-accent-blue transition-colors hover:bg-accent-blue/15"
          >
            تنظیمات چارت
          </button>
        </>
      ) : null}
    </div>
  );
}
