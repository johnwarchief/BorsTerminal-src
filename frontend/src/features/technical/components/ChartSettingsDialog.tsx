// features/technical/components/ChartSettingsDialog.tsx -- دیالوگ تنظیمات چارت (تب‌های مقیاس/ظاهر/ابزار)
// همهٔ فیلدها واقعی و متصل به ftsConfigStore هستند (بدون شبیه‌سازی).
// طبق docs/CHART-PARITY-REFERENCE.md §۳ (زیرمجموعهٔ قابل‌نگاشت روی klinecharts v10).
import { useFtsConfigStore, type ChartEngine, type ChartType, type PriceScale, type Timeframe } from '../stores/ftsConfigStore';

const ENGINES: { key: ChartEngine; label: string; hint: string }[] = [
  { key: 'klinecharts', label: 'klinecharts (فعلی)', hint: 'موتور قدیمی؛ ابزارهای ترسیم FTS فعال' },
  { key: 'lightweight', label: 'Lightweight Charts', hint: 'موتور متن‌باز تریدینگ‌ویو؛ فاز مهاجرت' },
];

const SCALES: { key: PriceScale; label: string; hint: string }[] = [
  { key: 'normal', label: 'خطی', hint: 'yAxis.type = normal' },
  { key: 'logarithm', label: 'لگاریتمی', hint: 'yAxis.type = logarithm' },
  { key: 'percentage', label: 'درصدی', hint: 'yAxis.type = percentage' },
];

const TYPES: { key: ChartType; label: string }[] = [
  { key: 'candle_solid', label: 'کندل' },
  { key: 'candle_stroke', label: 'کندل توخالی' },
  { key: 'ohlc', label: 'بار' },
  { key: 'line', label: 'خط' },
  { key: 'area', label: 'اریا' },
];

const TIMEFRAMES: { key: Timeframe; label: string }[] = [
  { key: 'day', label: 'روزانه' },
  { key: 'week', label: 'هفتگی' },
  { key: 'month', label: 'ماهانه' },
];

function Row({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1 border-b border-[var(--hairline)] py-2 last:border-b-0">
      <span className="text-[11px] font-bold text-text-secondary">{label}</span>
      {hint ? <span className="text-[10px] text-text-muted">{hint}</span> : null}
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  );
}

function Choice<T extends string>({
  options,
  value,
  onPick,
}: {
  options: { key: T; label: string; hint?: string }[];
  value: T;
  onPick: (v: T) => void;
}) {
  return (
    <>
      {options.map((o) => (
        <button
          key={o.key}
          type="button"
          title={o.hint}
          aria-pressed={value === o.key}
          onClick={() => onPick(o.key)}
          className={`rounded-full border px-3 py-1 text-xs font-semibold transition-colors ${
            value === o.key ? 'border-border-accent bg-accent-blue/15 text-accent-blue' : 'border-border-c bg-bg-card text-text-muted hover:text-text-secondary'
          }`}
        >
          {o.label}
        </button>
      ))}
    </>
  );
}

export function ChartSettingsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const priceScale = useFtsConfigStore((s) => s.priceScale);
  const chartType = useFtsConfigStore((s) => s.chartType);
  const chartEngine = useFtsConfigStore((s) => s.chartEngine);
  const timeframe = useFtsConfigStore((s) => s.timeframe);
  const showGrid = useFtsConfigStore((s) => s.showGrid);
  const showCrosshair = useFtsConfigStore((s) => s.showCrosshair);
  const showRsi = useFtsConfigStore((s) => s.showRsi);
  const showVolMa = useFtsConfigStore((s) => s.showVolMa);
  const setPriceScale = useFtsConfigStore((s) => s.setPriceScale);
  const setChartType = useFtsConfigStore((s) => s.setChartType);
  const setChartEngine = useFtsConfigStore((s) => s.setChartEngine);
  const setTimeframe = useFtsConfigStore((s) => s.setTimeframe);
  const toggleDisplay = useFtsConfigStore((s) => s.toggleDisplay);
  const toggleIndicator = useFtsConfigStore((s) => s.toggleIndicator);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="تنظیمات چارت"
      data-testid="chart-settings"
      onClick={onClose}
    >
      <div className="glass-panel max-h-[85vh] w-full max-w-md overflow-y-auto rounded-2xl p-4" onClick={(e) => e.stopPropagation()}>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-black text-text-primary">تنظیمات چارت</h3>
          <button type="button" onClick={onClose} aria-label="بستن" data-testid="chart-settings-close" className="rounded px-2 text-text-muted hover:text-accent-red">
            ✕
          </button>
        </div>

        <Row label="موتور چارت" hint="پیش‌فرض klinecharts است تا رگرسیون نشود">
          <Choice options={ENGINES} value={chartEngine} onPick={setChartEngine} />
        </Row>

        <Row label="مقیاس محور قیمت" hint="نگاشت به yAxis.type در klinecharts">
          <Choice options={SCALES} value={priceScale} onPick={setPriceScale} />
        </Row>

        <Row label="نوع چارت" hint="نگاشت به candle.type در klinecharts">
          <Choice options={TYPES} value={chartType} onPick={setChartType} />
        </Row>

        <Row label="تایم‌فریم" hint="بازنمونه‌گیری سمت کلاینت از کندل روزانه">
          <Choice options={TIMEFRAMES} value={timeframe} onPick={setTimeframe} />
        </Row>

        <Row label="خطوط و نشانگرها">
          <button
            type="button"
            onClick={() => toggleDisplay('grid')}
            aria-pressed={showGrid}
            className={`rounded-full border px-3 py-1 text-xs font-semibold ${showGrid ? 'border-border-accent bg-accent-blue/15 text-accent-blue' : 'border-border-c bg-bg-card text-text-muted'}`}
          >
            شبکه: {showGrid ? 'روشن' : 'خاموش'}
          </button>
          <button
            type="button"
            onClick={() => toggleDisplay('crosshair')}
            aria-pressed={showCrosshair}
            className={`rounded-full border px-3 py-1 text-xs font-semibold ${showCrosshair ? 'border-border-accent bg-accent-blue/15 text-accent-blue' : 'border-border-c bg-bg-card text-text-muted'}`}
          >
            کراس‌هیر: {showCrosshair ? 'روشن' : 'خاموش'}
          </button>
        </Row>

        <Row label="اندیکاتورها" hint="MA(14)/MA(100) روی قیمت همیشه فعال؛ حجم ۲۱ و RSI۱۴ اختیاری">
          <button
            type="button"
            onClick={() => toggleIndicator('volMa')}
            aria-pressed={showVolMa}
            className={`rounded-full border px-3 py-1 text-xs font-semibold ${showVolMa ? 'border-border-accent bg-accent-blue/15 text-accent-blue' : 'border-border-c bg-bg-card text-text-muted'}`}
          >
            MA حجم ۲۱: {showVolMa ? 'روشن' : 'خاموش'}
          </button>
          <button
            type="button"
            onClick={() => toggleIndicator('rsi')}
            aria-pressed={showRsi}
            className={`rounded-full border px-3 py-1 text-xs font-semibold ${showRsi ? 'border-border-accent bg-accent-blue/15 text-accent-blue' : 'border-border-c bg-bg-card text-text-muted'}`}
          >
            RSI(14): {showRsi ? 'روشن' : 'خاموش'}
          </button>
        </Row>

        <p className="mt-2 text-[10px] leading-4 text-text-muted">
          تب‌های «رویدادها/هشدارها/معاملات/میانبرها» در این نسخه نیستند (نیازمند داده/بک‌اند سمت سرور). این دیالوگ فقط فیلدهای دارای اثر واقعی روی چارت را نشان می‌دهد.
        </p>
      </div>
    </div>
  );
}
