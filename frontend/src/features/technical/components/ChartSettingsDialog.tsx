// features/technical/components/ChartSettingsDialog.tsx -- دیالوگ جامع تنظیمات چارت (سبک TradingView)
// ۴ تب اصلی استاندارد: نماد (Symbol) · خط وضعیت (Status Line) · مقیاس‌ها (Scales) · ظاهر (Appearance)
// + تب رویدادها (Events). تمام گزینه‌ها بلافاصله در localStorage ماندگار می‌شوند.
import { useState } from 'react';
import {
  useFtsConfigStore,
  type ChartEngine,
  type ChartType,
  type PriceScale,
  type Timeframe,
} from '../stores/ftsConfigStore';

const ENGINES: { key: ChartEngine; label: string; hint: string }[] = [
  { key: 'klinecharts', label: 'klinecharts (فعلی)', hint: 'موتور با ابزارهای ترسیم FTS فعال' },
  { key: 'lightweight', label: 'Lightweight Charts', hint: 'موتور متن‌باز رسمی TradingView' },
];

const TYPES: { key: ChartType; label: string }[] = [
  { key: 'candle_solid', label: 'کندل شمعی' },
  { key: 'candle_stroke', label: 'کندل توخالی' },
  { key: 'ohlc', label: 'میله‌ای (OHLC)' },
  { key: 'line', label: 'خط' },
  { key: 'area', label: 'اریا' },
  { key: 'heikin_ashi', label: 'Heikin-Ashi' },
];

const TIMEFRAMES: { key: Timeframe; label: string }[] = [
  { key: 'day', label: 'روزانه' },
  { key: 'week', label: 'هفتگی' },
  { key: 'month', label: 'ماهانه' },
];

const SCALES: { key: PriceScale; label: string; hint: string }[] = [
  { key: 'normal', label: 'خطی', hint: 'مقیاس حسابی عادی' },
  { key: 'logarithm', label: 'لگاریتمی', hint: 'مقیاس لگاریتمی استاندارد' },
  { key: 'percentage', label: 'درصدی', hint: 'مقیاس درصدی نسبت به اولین کندل' },
];

const POSITIONS: { key: 'right' | 'left'; label: string }[] = [
  { key: 'right', label: 'راست' },
  { key: 'left', label: 'چپ' },
];

const BACKGROUNDS: { key: 'dark' | 'theme' | 'classic' | 'light' | 'custom'; label: string }[] = [
  { key: 'dark', label: 'تیره مات (#131722)' },
  { key: 'classic', label: 'کلاسیک تیره' },
  { key: 'theme', label: 'همراه تم' },
  { key: 'light', label: 'روشن' },
  { key: 'custom', label: 'سفارشی' },
];

const TIMEZONES: { key: string; label: string }[] = [
  { key: 'Asia/Tehran', label: 'تهران (UTC+3:30)' },
  { key: 'UTC', label: 'گرینویچ (UTC)' },
  { key: 'Asia/Dubai', label: 'دبی (UTC+4)' },
  { key: 'Europe/London', label: 'لندن (UTC+0/1)' },
  { key: 'America/New_York', label: 'نیویورک (EST)' },
];

const GRID_STYLES: { key: 'dashed' | 'solid' | 'dotted' | 'none'; label: string }[] = [
  { key: 'dashed', label: 'خط‌چین' },
  { key: 'solid', label: 'ممتد' },
  { key: 'dotted', label: 'نقطه‌چین' },
  { key: 'none', label: 'بدون خط' },
];

const CROSSHAIR_STYLES: { key: 'dashed' | 'dotted' | 'solid'; label: string }[] = [
  { key: 'dashed', label: 'خط‌چین' },
  { key: 'dotted', label: 'نقطه‌چین' },
  { key: 'solid', label: 'ممتد' },
];

const UP_COLORS = ['#089981', '#10b981', '#26a69a', '#4ade80', '#00bcd4'];
const DOWN_COLORS = ['#f23645', '#f43f5e', '#ef5350', '#fb7185', '#e91e63'];

type Tab = 'symbol' | 'status' | 'scales' | 'appearance' | 'events';

const TABS: { id: Tab; label: string }[] = [
  { id: 'symbol', label: 'نماد (Symbol)' },
  { id: 'status', label: 'خط وضعیت (Status Line)' },
  { id: 'scales', label: 'مقیاس‌ها (Scales)' },
  { id: 'appearance', label: 'ظاهر (Appearance)' },
  { id: 'events', label: 'رویدادها' },
];

function Row({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5 border-b border-[#2a2e39]/50 py-2.5 last:border-b-0">
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold text-text-primary">{label}</span>
        {hint ? <span className="text-[10px] text-text-muted">{hint}</span> : null}
      </div>
      <div className="flex flex-wrap items-center gap-1.5">{children}</div>
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
            value === o.key
              ? 'border-accent-blue bg-accent-blue/15 text-accent-blue shadow-sm'
              : 'border-[#2a2e39] bg-[#1e222d] text-text-muted hover:text-text-primary'
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
        on
          ? 'border-accent-blue bg-accent-blue/15 text-accent-blue'
          : 'border-[#2a2e39] bg-[#1e222d] text-text-muted hover:text-text-secondary'
      }`}
    >
      {label}: {on ? 'روشن' : 'خاموش'}
    </button>
  );
}

export function ChartSettingsDialog({
  open,
  onClose,
  symbol,
  initialTab = 'scales',
}: {
  open: boolean;
  onClose: () => void;
  symbol?: string;
  initialTab?: Tab;
}) {
  const [tab, setTab] = useState<Tab>(initialTab);

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
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="تنظیمات چارت"
      data-testid="chart-settings"
      onClick={onClose}
    >
      <div
        className="glass-panel flex max-h-[90vh] w-full max-w-xl flex-col overflow-hidden rounded-2xl border border-[#2a2e39] bg-[#131722] shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* هدر پنجره */}
        <div className="flex items-center justify-between border-b border-[#2a2e39] px-5 py-3.5">
          <div className="flex items-center gap-2">
            <span className="text-sm font-black text-text-primary">تنظیمات چارت</span>
            {symbol && (
              <span className="rounded bg-accent-blue/15 px-2 py-0.5 text-xs font-bold text-accent-blue">
                {symbol}
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="بستن"
            data-testid="chart-settings-close"
            className="rounded-lg p-1 text-text-muted transition-colors hover:bg-[#2a2e39] hover:text-accent-red"
          >
            ✕
          </button>
        </div>

        {/* نوار تب‌های استاندارد */}
        <div className="flex flex-wrap gap-1 border-b border-[#2a2e39] bg-[#1a1e29] px-4 py-2" role="tablist">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              data-testid={`settings-tab-${t.id}`}
              onClick={() => setTab(t.id)}
              className={`rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
                tab === t.id
                  ? 'bg-accent-blue text-white shadow'
                  : 'text-text-muted hover:bg-[#2a2e39]/60 hover:text-text-primary'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* محتوای تب فعال */}
        <div className="flex-1 overflow-y-auto p-5 text-text-secondary">
          {/* ۱. تب نماد (Symbol) */}
          {tab === 'symbol' && (
            <div className="flex flex-col gap-2">
              <Row label="رنگ بدنه کندل صعودی" hint="candle.upColor">
                {UP_COLORS.map((c) => (
                  <button
                    key={c}
                    type="button"
                    aria-label={`صعودی ${c}`}
                    data-testid={`up-${c}`}
                    aria-pressed={view.candleUp === c}
                    onClick={() => setView({ candleUp: c, borderUp: c, wickUp: c })}
                    className={`h-6 w-6 rounded-full border-2 transition-transform hover:scale-110 ${
                      view.candleUp === c ? 'border-white scale-110' : 'border-transparent'
                    }`}
                    style={{ background: c }}
                  />
                ))}
                <button
                  type="button"
                  data-testid="reset-up"
                  onClick={() => setView({ candleUp: null, borderUp: null, wickUp: null })}
                  className="rounded-full border border-[#2a2e39] px-2.5 py-0.5 text-[11px] text-text-muted hover:text-text-primary"
                >
                  بازنشانی
                </button>
              </Row>

              <Row label="رنگ بدنه کندل نزولی" hint="candle.downColor">
                {DOWN_COLORS.map((c) => (
                  <button
                    key={c}
                    type="button"
                    aria-label={`نزولی ${c}`}
                    data-testid={`down-${c}`}
                    aria-pressed={view.candleDown === c}
                    onClick={() => setView({ candleDown: c, borderDown: c, wickDown: c })}
                    className={`h-6 w-6 rounded-full border-2 transition-transform hover:scale-110 ${
                      view.candleDown === c ? 'border-white scale-110' : 'border-transparent'
                    }`}
                    style={{ background: c }}
                  />
                ))}
                <button
                  type="button"
                  data-testid="reset-down"
                  onClick={() => setView({ candleDown: null, borderDown: null, wickDown: null })}
                  className="rounded-full border border-[#2a2e39] px-2.5 py-0.5 text-[11px] text-text-muted hover:text-text-primary"
                >
                  بازنشانی
                </button>
              </Row>

              <Row label="بوردر و سایه کندل‌ها">
                <Toggle
                  on={view.showBorders}
                  label="بوردر دور کندل‌ها"
                  onClick={() => setView({ showBorders: !view.showBorders })}
                />
                <Toggle
                  on={view.showWicks}
                  label="سایه کندل‌ها (Wicks)"
                  onClick={() => setView({ showWicks: !view.showWicks })}
                />
                <Toggle
                  on={view.wickGray}
                  label="سایه خاکستری"
                  onClick={() => setView({ wickGray: !view.wickGray })}
                />
              </Row>

              <Row label="رویدادهای شرکتی روی چارت (Corporate Actions)">
                <Toggle
                  on={view.showCorporateActions !== false}
                  label="نشانگرهای مجامع"
                  onClick={() => setView({ showCorporateActions: view.showCorporateActions === false })}
                />
                <Toggle
                  on={view.showDividends !== false}
                  label="سود نقدی (D)"
                  onClick={() => setView({ showDividends: view.showDividends === false })}
                />
                <Toggle
                  on={view.showSplits !== false}
                  label="افزایش سرمایه (S)"
                  onClick={() => setView({ showSplits: view.showSplits === false })}
                />
              </Row>

              <Row label="تایم‌زون چارت (Timezone)">
                <Choice
                  options={TIMEZONES}
                  value={view.timezone || 'Asia/Tehran'}
                  onPick={(tz) => setView({ timezone: tz })}
                />
              </Row>
            </div>
          )}

          {/* ۲. تب خط وضعیت (Status Line) */}
          {tab === 'status' && (
            <div className="flex flex-col gap-2">
              <Row label="کنترل‌های خط وضعیت و افسانه">
                <Toggle
                  on={view.statusShowSymbol}
                  label="نام نماد و قیمت زنده"
                  onClick={() => setView({ statusShowSymbol: !view.statusShowSymbol })}
                />
                <Toggle
                  on={view.statusShowOhlc}
                  label="مقادیر OHLC کندل جاری"
                  onClick={() => setView({ statusShowOhlc: !view.statusShowOhlc })}
                />
                <Toggle
                  on={view.statusShowVolume}
                  label="حجم معاملات"
                  onClick={() => setView({ statusShowVolume: !view.statusShowVolume })}
                />
                <Toggle
                  on={view.statusShowIndicators}
                  label="مقادیر اندیکاتورها"
                  onClick={() => setView({ statusShowIndicators: !view.statusShowIndicators })}
                />
                <Toggle
                  on={view.showLegend}
                  label="افسانه گوشه چارت"
                  onClick={() => setView({ showLegend: !view.showLegend })}
                />
              </Row>
              <p className="mt-2 rounded-lg bg-[#1a1e29] p-3 text-[11px] leading-5 text-text-muted">
                با فعال‌بودن خط وضعیت، هنگام حرکت نشانگر موس روی کندل‌ها مقادیر باز، بالاترین، پایین‌ترین، پایانی و حجم به
                صورت تبولار و بدون پرش به‌روزرسانی می‌شوند.
              </p>
            </div>
          )}

          {/* ۳. تب مقیاس‌ها (Scales) */}
          {tab === 'scales' && (
            <div className="flex flex-col gap-2">
              <Row label="نوع چارت">
                <Choice options={TYPES} value={chartType} onPick={setChartType} />
              </Row>

              <Row label="تایم‌فریم">
                <Choice options={TIMEFRAMES} value={timeframe} onPick={setTimeframe} />
              </Row>

              <Row label="مقیاس محور قیمت" hint="محور عمودی">
                <Choice options={SCALES} value={priceScale} onPick={setPriceScale} />
              </Row>

              <Row label="محاسبه ترازهای فیبوناچی">
                <Toggle
                  on={view.fibLogarithmic === true}
                  label="ترازهای فیبوناچی بر پایه لگاریتمی"
                  onClick={() => setView({ fibLogarithmic: !view.fibLogarithmic })}
                />
              </Row>

              <Row label="جایگاه و جهت محور قیمت">
                <Choice
                  options={POSITIONS}
                  value={view.priceScalePos}
                  onPick={(v) => setView({ priceScalePos: v })}
                />
                <Toggle
                  on={view.yAxisInside}
                  label="برچسب داخل چارت"
                  onClick={() => setView({ yAxisInside: !view.yAxisInside })}
                />
                <Toggle
                  on={view.yAxisReverse}
                  label="معکوس‌سازی"
                  onClick={() => setView({ yAxisReverse: !view.yAxisReverse })}
                />
              </Row>

              <Row label="قفل مقیاس و درگ">
                <Toggle
                  on={view.axisDragLock}
                  label="قفل درگ محور"
                  onClick={() => setView({ axisDragLock: !view.axisDragLock })}
                />
              </Row>

              <Row label="حاشیه برچسب محورها (پیکسل)">
                {[0, 3, 6, 10].map((m) => (
                  <button
                    key={m}
                    type="button"
                    aria-pressed={view.axisTickMargin === m}
                    onClick={() => setView({ axisTickMargin: m })}
                    className={`rounded-full border px-3 py-1 text-xs font-semibold ${
                      view.axisTickMargin === m
                        ? 'border-accent-blue bg-accent-blue/15 text-accent-blue'
                        : 'border-[#2a2e39] bg-[#1e222d] text-text-muted hover:text-text-primary'
                    }`}
                  >
                    {m}px
                  </button>
                ))}
              </Row>

              <Row label="موتور رندرینگ چارت">
                <Choice options={ENGINES} value={chartEngine} onPick={setChartEngine} />
              </Row>
            </div>
          )}

          {/* ۴. تب ظاهر (Appearance) */}
          {tab === 'appearance' && (
            <div className="flex flex-col gap-2">
              <Row label="پس‌زمینه چارت">
                <Choice
                  options={BACKGROUNDS}
                  value={view.background}
                  onPick={(v) => setView({ background: v })}
                />
                {view.background === 'custom' && (
                  <div className="flex items-center gap-2 pr-2">
                    <input
                      type="color"
                      value={view.customBgColor || '#131722'}
                      onChange={(e) => setView({ customBgColor: e.target.value })}
                      className="h-7 w-7 cursor-pointer rounded border border-[#2a2e39] bg-transparent"
                    />
                    <span className="font-mono text-xs text-text-muted">{view.customBgColor || '#131722'}</span>
                  </div>
                )}
              </Row>

              <Row label="رنگ کندل صعودی" hint="candle.upColor">
                {UP_COLORS.map((c) => (
                  <button
                    key={c}
                    type="button"
                    aria-label={`صعودی ${c}`}
                    data-testid={`up-${c}`}
                    aria-pressed={view.candleUp === c}
                    onClick={() => setView({ candleUp: c, borderUp: c, wickUp: c })}
                    className={`h-6 w-6 rounded-full border-2 transition-transform hover:scale-110 ${
                      view.candleUp === c ? 'border-white scale-110' : 'border-transparent'
                    }`}
                    style={{ background: c }}
                  />
                ))}
                <button
                  type="button"
                  data-testid="reset-up"
                  onClick={() => setView({ candleUp: null, borderUp: null, wickUp: null })}
                  className="rounded-full border border-[#2a2e39] px-2.5 py-0.5 text-[11px] text-text-muted hover:text-text-primary"
                >
                  بازنشانی
                </button>
              </Row>

              <Row label="رنگ کندل نزولی" hint="candle.downColor">
                {DOWN_COLORS.map((c) => (
                  <button
                    key={c}
                    type="button"
                    aria-label={`نزولی ${c}`}
                    data-testid={`down-${c}`}
                    aria-pressed={view.candleDown === c}
                    onClick={() => setView({ candleDown: c, borderDown: c, wickDown: c })}
                    className={`h-6 w-6 rounded-full border-2 transition-transform hover:scale-110 ${
                      view.candleDown === c ? 'border-white scale-110' : 'border-transparent'
                    }`}
                    style={{ background: c }}
                  />
                ))}
                <button
                  type="button"
                  data-testid="reset-down"
                  onClick={() => setView({ candleDown: null, borderDown: null, wickDown: null })}
                  className="rounded-full border border-[#2a2e39] px-2.5 py-0.5 text-[11px] text-text-muted hover:text-text-primary"
                >
                  بازنشانی
                </button>
              </Row>

              <Row label="خطوط شبکه گرید (Grid)">
                <Choice
                  options={GRID_STYLES}
                  value={view.gridStyle || 'dashed'}
                  onPick={(s) => setView({ gridStyle: s })}
                />
                <Toggle
                  on={showGrid}
                  label="کلیه خطوط شبکه"
                  onClick={() => toggleDisplay('grid')}
                />
                <Toggle
                  on={view.showGridHorz}
                  label="خطوط افقی"
                  onClick={() => setView({ showGridHorz: !view.showGridHorz })}
                />
                <Toggle
                  on={view.showGridVert}
                  label="خطوط عمودی"
                  onClick={() => setView({ showGridVert: !view.showGridVert })}
                />
              </Row>

              <Row label="استایل کراس‌هیر (Crosshair)">
                <Choice
                  options={CROSSHAIR_STYLES}
                  value={view.crosshairStyle || 'dashed'}
                  onPick={(s) => setView({ crosshairStyle: s })}
                />
                <Toggle
                  on={showCrosshair}
                  label="کراس‌هیر"
                  onClick={() => toggleDisplay('crosshair')}
                />
              </Row>

              <Row label="واترمارک نماد و تایم‌فریم (Watermark)">
                <Toggle
                  on={view.showWatermark}
                  label="نمایش واترمارک"
                  onClick={() => setView({ showWatermark: !view.showWatermark })}
                />
                <div className="flex items-center gap-2 pr-2">
                  <span className="text-xs text-text-muted">شفافیت:</span>
                  {[5, 10, 20, 50].map((op) => (
                    <button
                      key={op}
                      type="button"
                      aria-pressed={view.watermarkOpacity === op}
                      onClick={() => setView({ watermarkOpacity: op })}
                      className={`rounded px-2 py-0.5 text-xs font-bold transition-colors ${
                        view.watermarkOpacity === op
                          ? 'bg-accent-blue text-white'
                          : 'bg-[#1e222d] text-text-muted hover:text-text-primary'
                      }`}
                    >
                      {op}%
                    </button>
                  ))}
                </div>
              </Row>

              <Row label="اندیکاتورهای پایه‌ای">
                <Toggle
                  on={showVolMa}
                  label="MA حجم ۲۱"
                  onClick={() => toggleIndicator('volMa')}
                />
                <Toggle
                  on={showRsi}
                  label="RSI (14)"
                  onClick={() => toggleIndicator('rsi')}
                />
              </Row>
            </div>
          )}

          {/* ۵. تب رویدادها (Events) */}
          {tab === 'events' && (
            <div className="py-2">
              <p
                className="rounded-lg bg-[#1a1e29] p-4 text-xs leading-6 text-text-muted"
                data-testid="settings-events-note"
              >
                رویدادهای سود نقدی، مجامع و افزایش سرمایه به صورت زنده از سامانه کدال در سرور ثبت می‌شوند؛
                این تب فاقد هرگونه داده ساختگی یا شبیه‌سازی‌شده است.
              </p>
            </div>
          )}
        </div>

        {/* فوتر پنجره */}
        <div className="flex items-center justify-between border-t border-[#2a2e39] bg-[#1a1e29] px-5 py-3">
          <span className="text-[11px] text-text-muted">
            کلیه تنظیمات به صورت خودکار در حافظه مرورگر ذخیره می‌شوند.
          </span>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg bg-accent-blue px-4 py-1.5 text-xs font-bold text-white transition-colors hover:bg-accent-blue/80"
          >
            بستن و اعمال
          </button>
        </div>
      </div>
    </div>
  );
}
