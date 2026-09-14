// features/technical/components/FtsToolbar.tsx -- تولبار ابزارهای چارت به سبک تریدینگ‌ویو
// گروه‌ها: تایم‌فریم · نوع چارت · اندیکاتورها · لایه‌های FTS. ابزارهای رسم روی رپر چارت‌اند.
import { useFtsConfigStore, type ChartType, type IndicatorKey, type Timeframe, type FtsLayerKey } from '../stores/ftsConfigStore';

const LAYERS: { key: FtsLayerKey; label: string }[] = [
  { key: 'showMAs', label: 'مووینگ ها' },
  { key: 'showJetTrigger', label: 'خط آبی' },
  { key: 'showChoch', label: 'خط چین قرمز' },
  { key: 'showFibZones', label: 'کمربند فیبو' },
  { key: 'showSetupMarkers', label: 'مارکر ستاپ' },
  { key: 'enforceRiskGates', label: 'گیت ریسک' },
  { key: 'showFtsCard', label: 'کارت وضعیت' },
];

const TIMEFRAMES: { key: Timeframe; label: string }[] = [
  { key: 'day', label: 'روزانه' },
  { key: 'week', label: 'هفتگی' },
  { key: 'month', label: 'ماهانه' },
];

const CHART_TYPES: { key: ChartType; label: string }[] = [
  { key: 'candle', label: 'کندل' },
  { key: 'ohlc', label: 'بار' },
  { key: 'line', label: 'خط' },
  { key: 'area', label: 'اریا' },
];

const INDICATORS: { key: IndicatorKey; label: string }[] = [
  { key: 'rsi', label: 'RSI(14)' },
  { key: 'volMa', label: 'MA حجم ۲۱' },
];

function Chip({
  active,
  label,
  onClick,
  title,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
  title?: string;
}) {
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

function Divider() {
  return <span aria-hidden className="mx-1 h-5 w-px shrink-0 bg-border-c" />;
}

export function FtsToolbar() {
  const showMAs = useFtsConfigStore((s) => s.showMAs);
  const showJetTrigger = useFtsConfigStore((s) => s.showJetTrigger);
  const showChoch = useFtsConfigStore((s) => s.showChoch);
  const showFibZones = useFtsConfigStore((s) => s.showFibZones);
  const showSetupMarkers = useFtsConfigStore((s) => s.showSetupMarkers);
  const enforceRiskGates = useFtsConfigStore((s) => s.enforceRiskGates);
  const showFtsCard = useFtsConfigStore((s) => s.showFtsCard);
  const chartType = useFtsConfigStore((s) => s.chartType);
  const timeframe = useFtsConfigStore((s) => s.timeframe);
  const showRsi = useFtsConfigStore((s) => s.showRsi);
  const showVolMa = useFtsConfigStore((s) => s.showVolMa);
  const toggle = useFtsConfigStore((s) => s.toggle);
  const setChartType = useFtsConfigStore((s) => s.setChartType);
  const setTimeframe = useFtsConfigStore((s) => s.setTimeframe);
  const toggleIndicator = useFtsConfigStore((s) => s.toggleIndicator);

  const layerStates: Record<FtsLayerKey, boolean> = {
    showMAs,
    showJetTrigger,
    showChoch,
    showFibZones,
    showSetupMarkers,
    enforceRiskGates,
    showFtsCard,
  };

  return (
    <div className="glass-panel flex flex-wrap items-center gap-1.5 rounded-2xl p-3" role="toolbar" aria-label="ابزارهای چارت تکنیکال">
      <span className="px-1 text-[10px] font-bold text-text-muted">تایم‌فریم</span>
      {TIMEFRAMES.map((t) => (
        <Chip key={t.key} active={timeframe === t.key} label={t.label} onClick={() => setTimeframe(t.key)} title="بازنمونه‌گیری از کندل روزانه" />
      ))}

      <Divider />

      <span className="px-1 text-[10px] font-bold text-text-muted">نوع چارت</span>
      {CHART_TYPES.map((c) => (
        <Chip key={c.key} active={chartType === c.key} label={c.label} onClick={() => setChartType(c.key)} />
      ))}

      <Divider />

      <span className="px-1 text-[10px] font-bold text-text-muted">اندیکاتورها</span>
      {INDICATORS.map((ind) => (
        <Chip
          key={ind.key}
          active={ind.key === 'rsi' ? showRsi : showVolMa}
          label={ind.label}
          onClick={() => toggleIndicator(ind.key)}
          title={ind.key === 'rsi' ? 'RSI وایلدر دورهٔ ۱۴ در پنل جدا' : 'میانگین متحرک حجم دورهٔ ۲۱ روی پنل حجم'}
        />
      ))}

      <Divider />

      <span className="px-1 text-[10px] font-bold text-text-muted">لایه‌های FTS</span>
      {LAYERS.map((it) => (
        <Chip
          key={it.key}
          active={layerStates[it.key]}
          label={`${it.label}: ${layerStates[it.key] ? 'روشن' : 'خاموش'}`}
          onClick={() => toggle(it.key)}
        />
      ))}
    </div>
  );
}
