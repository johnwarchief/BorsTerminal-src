// features/technical/components/ChartSettingsDialog.tsx -- دیالوگ تنظیمات چارت (تب‌دار، سبک TV)
// تب‌ها: مقیاس‌ها و خطوط · ظاهر · خط وضعیت · نماد · رویدادها.
// همهٔ کنترل‌ها به استایل/آپشن واقعی klinecharts v10 نگاشت می‌شوند (بدون شبیه‌سازی)؛
// موارد ناموجود صادقانه به‌صورت «در دسترس نیست» با دلیل نمایش داده می‌شوند.
import { useState } from 'react';
import { useFtsConfigStore, type ChartEngine, type ChartType, type PriceScale, type Timeframe } from '../stores/ftsConfigStore';

const ENGINES: { key: ChartEngine; label: string; hint: string }[] = [
  { key: 'klinecharts', label: 'klinecharts (فعلی)', hint: 'موتور قدیمی؛ ابزارهای ترسیم FTS فعال' },
  { key: 'lightweight', label: 'Lightweight Charts', hint: 'موتور متن‌باز تریدینگ‌ویو؛ فاز مهاجرت' },
];

const TYPES: { key: ChartType; label: string }[] = [
  { key: 'candle_solid', label: 'کندل' },
  { key: 'candle_stroke', label: 'کندل توخالی' },
  { key: 'ohlc', label: 'بار' },
  { key: 'line', label: 'خط' },
  { key: 'area', label: 'اریا' },
  { key: 'heikin_ashi', label: 'Heikin-Ashi' },
  { key: 'renko', label: 'Renko' },
  { key: 'kagi', label: 'Kagi' },
  { key: 'pnf', label: 'Point & Figure' },
];

const TIMEFRAMES: { key: Timeframe; label: string }[] = [
  { key: 'day', label: 'روزانه' },
  { key: 'week', label: 'هفتگی' },
  { key: 'month', label: 'ماهانه' },
];

const SCALES: { key: PriceScale; label: string; hint: string }[] = [
  { key: 'normal', label: 'خطی', hint: 'yAxis.type = normal' },
  { key: 'logarithm', label: 'لگاریتمی', hint: 'yAxis.type = logarithm' },
  { key: 'percentage', label: 'درصدی', hint: 'yAxis.type = percentage' },
];

const POSITIONS: { key: 'right' | 'left'; label: string }[] = [
  { key: 'right', label: 'راست' },
  { key: 'left', label: 'چپ' },
];

const BACKGROUNDS: { key: 'theme' | 'classic'; label: string }[] = [
  { key: 'theme', label: 'همراه تم' },
  { key: 'classic', label: 'کلاسیک تیره' },
];

const UP_COLORS = ['#10b981', '#26a69a', '#089981', '#4ade80'];
const DOWN_COLORS = ['#f43f5e', '#ef5350', '#f23645', '#fb7185'];

type Tab = 'scales' | 'appearance' | 'status' | 'symbol' | 'events';

const TABS: { id: Tab; label: string }[] = [
  { id: 'scales', label: 'مقیاس‌ها و خطوط' },
  { id: 'appearance', label: 'ظاهر' },
  { id: 'status', label: 'خط وضعیت' },
  { id: 'symbol', label: 'نماد' },
  { id: 'events', label: 'رویدادها' },
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

function Toggle({ on, label, onClick }: { on: boolean; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={on}
      className={`rounded-full border px-3 py-1 text-xs font-semibold transition-colors ${
        on ? 'border-border-accent bg-accent-blue/15 text-accent-blue' : 'border-border-c bg-bg-card text-text-muted'
      }`}
    >
      {label}: {on ? 'روشن' : 'خاموش'}
    </button>
  );
}

export function ChartSettingsDialog({ open, onClose, symbol }: { open: boolean; onClose: () => void; symbol?: string }) {
  const [tab, setTab] = useState<Tab>('scales');
  const priceScale = useFtsConfigStore((s) => s.priceScale);
  const chartType = useFtsConfigStore((s) => s.chartType);
  const chartEngine = useFtsConfigStore((s) => s.chartEngine);
  const timeframe = useFtsConfigStore((s) => s.timeframe);
  const view = useFtsConfigStore((s) => s.view);
  const showGrid = useFtsConfigStore((s) => s.showGrid);
  const showCrosshair = useFtsConfigStore((s) => s.showCrosshair);
  const showRsi = useFtsConfigStore((s) => s.showRsi);
  const showVolMa = useFtsConfigStore((s) => s.showVolMa);
  const setPriceScale = useFtsConfigStore((s) => s.setPriceScale);
  const setChartType = useFtsConfigStore((s) => s.setChartType);
  const setChartEngine = useFtsConfigStore((s) => s.setChartEngine);
  const setTimeframe = useFtsConfigStore((s) => s.setTimeframe);
  const setView = useFtsConfigStore((s) => s.setView);
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
      <div className="glass-panel max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-2xl p-4" onClick={(e) => e.stopPropagation()}>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-black text-text-primary">تنظیمات چارت</h3>
          <button type="button" onClick={onClose} aria-label="بستن" data-testid="chart-settings-close" className="rounded px-2 text-text-muted hover:text-accent-red">
            ✕
          </button>
        </div>

        <div className="mb-2 flex flex-wrap gap-1" role="tablist">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              data-testid={`settings-tab-${t.id}`}
              onClick={() => setTab(t.id)}
              className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${
                tab === t.id ? 'border-border-accent bg-accent-blue/15 text-accent-blue' : 'border-border-c bg-bg-card text-text-muted'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === 'scales' ? (
          <>
            <Row label="موتور چارت" hint="پیش‌فرض klinecharts است تا رگرسیون نشود">
              <Choice options={ENGINES} value={chartEngine} onPick={setChartEngine} />
            </Row>
            <Row label="نوع چارت" hint="نگاشت به candle.type؛ انواع HA/Renko/Kagi/PnF در لایهٔ داده تبدیل می‌شوند">
              <Choice options={TYPES} value={chartType} onPick={setChartType} />
            </Row>
            <Row label="تایم‌فریم" hint="بازنمونه‌گیری سمت کلاینت از کندل روزانه">
              <Choice options={TIMEFRAMES} value={timeframe} onPick={setTimeframe} />
            </Row>
            <Row label="مقیاس محور قیمت" hint="yAxis.type در klinecharts">
              <Choice options={SCALES} value={priceScale} onPick={setPriceScale} />
            </Row>
            <Row label="جای محور قیمت">
              <Choice options={POSITIONS} value={view.priceScalePos} onPick={(v) => setView({ priceScalePos: v })} />
            </Row>
            <Row label="مقیاس و محور">
              <Toggle on={view.yAxisReverse} label="معکوس‌سازی" onClick={() => setView({ yAxisReverse: !view.yAxisReverse })} />
              <Toggle on={view.yAxisInside} label="برچسب داخل چارت" onClick={() => setView({ yAxisInside: !view.yAxisInside })} />
              <Toggle on={view.axisDragLock} label="قفل درگ محور" onClick={() => setView({ axisDragLock: !view.axisDragLock })} />
            </Row>
            <Row label="حاشیهٔ برچسب محورها" hint="tickText.marginStart/End">
              {[0, 3, 6, 10].map((m) => (
                <button
                  key={m}
                  type="button"
                  aria-pressed={view.axisTickMargin === m}
                  onClick={() => setView({ axisTickMargin: m })}
                  className={`num rounded-full border px-3 py-1 text-xs font-semibold ${
                    view.axisTickMargin === m ? 'border-border-accent bg-accent-blue/15 text-accent-blue' : 'border-border-c bg-bg-card text-text-muted'
                  }`}
                >
                  {m}
                </button>
              ))}
            </Row>
            <Row label="خطوط و نشانگرها">
              <Toggle on={showGrid} label="شبکه" onClick={() => toggleDisplay('grid')} />
              <Toggle on={showCrosshair} label="کراس‌هیر" onClick={() => toggleDisplay('crosshair')} />
              <Toggle on={view.showXAxis} label="محور زمان" onClick={() => setView({ showXAxis: !view.showXAxis })} />
              <Toggle on={view.showYAxis} label="محور قیمت" onClick={() => setView({ showYAxis: !view.showYAxis })} />
            </Row>
            <Row label="اندیکاتورها" hint="MA(14)/MA(100) روی قیمت همیشه فعال؛ حجم ۲۱ و RSI۱۴ اختیاری">
              <Toggle on={showVolMa} label="MA حجم ۲۱" onClick={() => toggleIndicator('volMa')} />
              <Toggle on={showRsi} label="RSI(14)" onClick={() => toggleIndicator('rsi')} />
            </Row>
          </>
        ) : null}

        {tab === 'appearance' ? (
          <>
            <Row label="پس‌زمینهٔ چارت" hint="layout.background (بازسازی چارت)">
              <Choice options={BACKGROUNDS} value={view.background} onPick={(v) => setView({ background: v })} />
            </Row>
            <Row label="رنگ کندل صعودی" hint="candle.bar.upColor/upWickColor">
              {UP_COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  aria-label={`صعودی ${c}`}
                  data-testid={`up-${c}`}
                  aria-pressed={view.candleUp === c}
                  onClick={() => setView({ candleUp: c })}
                  className={`h-6 w-6 rounded-full border ${view.candleUp === c ? 'border-border-accent' : 'border-border-c'}`}
                  style={{ background: c }}
                />
              ))}
              <button type="button" data-testid="reset-up" onClick={() => setView({ candleUp: null })} className="rounded-full border border-border-c px-2 py-0.5 text-[11px] text-text-muted">
                بازنشانی
              </button>
            </Row>
            <Row label="رنگ کندل نزولی">
              {DOWN_COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  aria-label={`نزولی ${c}`}
                  data-testid={`down-${c}`}
                  aria-pressed={view.candleDown === c}
                  onClick={() => setView({ candleDown: c })}
                  className={`h-6 w-6 rounded-full border ${view.candleDown === c ? 'border-border-accent' : 'border-border-c'}`}
                  style={{ background: c }}
                />
              ))}
              <button type="button" data-testid="reset-down" onClick={() => setView({ candleDown: null })} className="rounded-full border border-border-c px-2 py-0.5 text-[11px] text-text-muted">
                بازنشانی
              </button>
            </Row>
            <Row label="بدنه و سایه" hint="candle.bar.upWickColor/downWickColor">
              <Toggle on={view.wickGray} label="سایهٔ خاکستری" onClick={() => setView({ wickGray: !view.wickGray })} />
            </Row>
            <p className="text-[10px] leading-4 text-text-muted">
              تب «ظاهر» فقط رنگ‌های واقعیِ موتور را عوض می‌کند (پس‌زمینه/کندل/سایه)؛ رنگ‌های معنایی صعود/نزول پیش‌فرض دست‌نخورده می‌مانند.
            </p>
          </>
        ) : null}

        {tab === 'status' ? (
          <>
            <Row label="خط وضعیت (افسانه)" hint="OHLCV و مقادیر MA روی گوشهٔ چارت">
              <Toggle on={view.showLegend} label="افسانهٔ شیشه‌ای" onClick={() => setView({ showLegend: !view.showLegend })} />
            </Row>
            <p className="text-[10px] leading-4 text-text-muted">
              مقادیر باز / بیشترین / کمترین / پایانی / حجم و MA ها در افسانه نمایش داده می‌شوند. سایر فیلدهای خط وضعیت
              تریدینگ‌ویو (تغییر روز، مقدار اندیکاتورها به‌صورت جدا) در این موتور پشتیبانی نمی‌شوند.
            </p>
          </>
        ) : null}

        {tab === 'symbol' ? (
          <>
            <Row label="نماد فعال" hint="از آدرس/دیده‌بان انتخاب می‌شود">
              <span className="num text-xs font-bold text-text-primary">{symbol || 'نمادی انتخاب نشده'}</span>
            </Row>
            <p className="text-[10px] leading-4 text-text-muted">
              کنترل دقت اعشار/حداقل-حداکثر قیمت در klinecharts 10 از طریق API عمومی در دسترس نیست (setPriceVolumePrecision حذف شده)؛
              بنابراین این تب فقط اطلاعات نمایش می‌دهد و کنترل ساختگی ندارد.
            </p>
          </>
        ) : null}

        {tab === 'events' ? (
          <p className="py-2 text-[10px] leading-5 text-text-muted" data-testid="settings-events-note">
            رویدادهای سود نقدی/تجزیه سهام در داده‌های بک‌اند موجود نیست؛ بنابراین این تب صادقانه خالی است و هیچ عدد ساختگی نمایش داده نمی‌شود.
          </p>
        ) : null}
      </div>
    </div>
  );
}
