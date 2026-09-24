// features/technical/components/ChartSettingsDialog.tsx -- دیالوگ جامع تنظیمات چارت (سبک TradingView)
// ۴ تب اصلی استاندارد: نماد (Symbol) · خط وضعیت (Status Line) · مقیاس‌ها (Scales) · ظاهر (Appearance)
// + تب رویدادها (Events). تمام گزینه‌ها بلافاصله در localStorage ماندگار می‌شوند.
import { useState } from 'react';
import { useUiStore } from '@shared/stores/uiStore';
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
  { key: 'solid', label: 'ممتد' },
  { key: 'dashed', label: 'خط‌چین' },
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
  const isLight = useUiStore((s) => s.theme) === 'light';
  return (
    <div
      className={`flex flex-col gap-2 rounded-xl border p-3.5 transition-colors ${
        isLight
          ? 'border-[#e0e3eb] bg-[#f8f9fa] hover:border-[#d1d4dc]'
          : 'border-[#2a2e39] bg-[#141722] hover:border-[#3d4251]'
      }`}
    >
      <div className="flex items-center justify-between">
        <span className={`text-xs font-bold tracking-wide ${isLight ? 'text-[#131722]' : 'text-white'}`}>
          {label}
        </span>
        {hint ? (
          <span className={`text-[10.5px] font-medium ${isLight ? 'text-[#5f6368]' : 'text-[#b2b5be]'}`}>
            {hint}
          </span>
        ) : null}
      </div>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
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
  const isLight = useUiStore((s) => s.theme) === 'light';
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {options.map((o) => {
        const isActive = value === o.key;
        return (
          <button
            key={o.key}
            type="button"
            title={o.hint}
            aria-pressed={isActive}
            onClick={() => onPick(o.key)}
            className={`rounded-lg border px-3 py-1.5 text-xs font-bold transition-all ${
              isActive
                ? 'border-[#2962ff] bg-[#2962ff] text-white shadow-sm ring-1 ring-[#2962ff]/50'
                : isLight
                ? 'border-[#d1d4dc] bg-[#f0f3fa] text-[#131722] hover:border-[#b2b5be] hover:bg-[#e0e3eb]'
                : 'border-[#2a2e39] bg-[#1a1e29] text-[#e0e3eb] hover:border-[#434857] hover:bg-[#262b3d] hover:text-white'
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

function Toggle({ on, label, onClick }: { on: boolean; label: string; onClick: () => void }) {
  const isLight = useUiStore((s) => s.theme) === 'light';
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={on}
      className={`group inline-flex items-center gap-2.5 rounded-lg border px-3 py-1.5 text-xs font-semibold transition-all ${
        on
          ? isLight
            ? 'border-[#089981]/50 bg-[#089981]/15 text-[#089981] shadow-sm ring-1 ring-[#089981]/30'
            : 'border-[#089981]/60 bg-[#089981]/20 text-white shadow-sm ring-1 ring-[#089981]/40'
          : isLight
          ? 'border-[#d1d4dc] bg-[#f0f3fa] text-[#131722] hover:border-[#b2b5be] hover:bg-[#e0e3eb]'
          : 'border-[#2a2e39] bg-[#1a1e29] text-[#e0e3eb] hover:border-[#434857] hover:bg-[#262b3d] hover:text-white'
      }`}
    >
      <span
        className={`relative inline-flex h-3.5 w-6 shrink-0 items-center rounded-full transition-colors ${
          on ? 'bg-[#089981]' : isLight ? 'bg-[#cbd5e1]' : 'bg-[#363a45]'
        }`}
      >
        <span
          className={`inline-block h-2.5 w-2.5 rounded-full bg-white transition-transform ${
            on ? '-translate-x-3' : '-translate-x-0.5'
          }`}
        />
      </span>
      <span className={isLight ? (on ? 'text-[#089981] font-semibold' : 'text-[#131722] font-semibold') : 'text-white font-medium'}>
        {label}
      </span>
      <span className={`text-[10px] font-bold ${on ? (isLight ? 'text-[#089981]' : 'text-[#34d399]') : (isLight ? 'text-[#5f6368]' : 'text-[#b2b5be]')}`}>
        ({on ? 'روشن' : 'خاموش'})
      </span>
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
  const isLight = useUiStore((s) => s.theme) === 'light';
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
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="تنظیمات چارت"
      data-testid="chart-settings"
      onClick={onClose}
    >
      <div
        className={`flex max-h-[85vh] w-full max-w-xl flex-col overflow-hidden rounded-2xl border shadow-2xl transition-colors ${
          isLight
            ? 'border-[#e0e3eb] bg-[#ffffff] shadow-black/20'
            : 'border-[#2a2e39] bg-[#1e222d] shadow-black/80'
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* هدر پنجره */}
        <div
          className={`flex items-center justify-between border-b px-5 py-3.5 transition-colors ${
            isLight ? 'border-[#e0e3eb] bg-[#f8f9fa]' : 'border-[#2a2e39] bg-[#1a1e29]'
          }`}
        >
          <div className="flex items-center gap-2.5">
            <span className={`text-sm font-black ${isLight ? 'text-[#131722]' : 'text-white'}`}>
              تنظیمات چارت
            </span>
            {symbol && (
              <span className="rounded-md border border-[#2962ff]/30 bg-[#2962ff]/15 px-2.5 py-0.5 text-xs font-bold text-[#2962ff]">
                {symbol}
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="بستن"
            data-testid="chart-settings-close"
            className={`flex h-7 w-7 items-center justify-center rounded-lg transition-colors ${
              isLight
                ? 'text-[#5f6368] hover:bg-[#e0e3eb] hover:text-[#131722]'
                : 'text-[#9aa0a6] hover:bg-[#2a2e39] hover:text-white'
            }`}
          >
            ✕
          </button>
        </div>

        {/* نوار تب‌های استاندارد */}
        <div
          className={`flex flex-wrap gap-1.5 border-b px-4 py-2.5 transition-colors ${
            isLight ? 'border-[#e0e3eb] bg-[#f0f3fa]' : 'border-[#2a2e39] bg-[#141720]'
          }`}
          role="tablist"
        >
          {TABS.map((t) => {
            const isActive = tab === t.id;
            return (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={isActive}
                data-testid={`settings-tab-${t.id}`}
                onClick={() => setTab(t.id)}
                className={`relative rounded-lg px-3.5 py-1.5 text-xs font-bold transition-all ${
                  isActive
                    ? 'bg-[#2962ff] text-white shadow-md shadow-[#2962ff]/30 ring-1 ring-[#2962ff]'
                    : isLight
                    ? 'text-[#434651] hover:bg-[#e0e3eb] hover:text-[#131722]'
                    : 'text-[#c2c7d0] hover:bg-[#2a2e39] hover:text-white'
                }`}
              >
                {t.label}
              </button>
            );
          })}
        </div>

        {/* محتوای تب فعال */}
        <div className={`flex-1 overflow-y-auto p-5 ${isLight ? 'text-[#131722]' : 'text-[#e0e3eb]'}`}>

          {/* ۱. تب نماد (Symbol) */}
          {tab === 'symbol' && (
            <div className="flex flex-col gap-2.5">
              <Row label="رنگ بدنه کندل صعودی" hint="رنگ رشد قیمت (سبز)">
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
                  className={`rounded-lg border px-3 py-1 text-xs font-semibold transition-colors ${
                    isLight
                      ? 'border-[#d1d4dc] bg-[#f0f3fa] text-[#131722] hover:border-[#b2b5be] hover:bg-[#e0e3eb]'
                      : 'border-[#2a2e39] bg-[#1a1e29] text-[#e0e3eb] hover:border-[#434857] hover:bg-[#262b3d] hover:text-white'
                  }`}
                >
                  بازنشانی
                </button>
              </Row>

              <Row label="رنگ بدنه کندل نزولی" hint="رنگ افت قیمت (قرمز)">
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
                  className={`rounded-lg border px-3 py-1 text-xs font-semibold transition-colors ${
                    isLight
                      ? 'border-[#d1d4dc] bg-[#f0f3fa] text-[#131722] hover:border-[#b2b5be] hover:bg-[#e0e3eb]'
                      : 'border-[#2a2e39] bg-[#1a1e29] text-[#e0e3eb] hover:border-[#434857] hover:bg-[#262b3d] hover:text-white'
                  }`}
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

              <Row label="نشانگر رویدادهای تعدیل (Corporate Actions)">
                <Toggle
                  on={view.showCorporateActions !== false}
                  label="نشانگرهای تعدیل قیمت پایه"
                  onClick={() => setView({ showCorporateActions: view.showCorporateActions === false })}
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
            <div className="flex flex-col gap-3">
              <div
                className={`flex flex-col gap-2 rounded-xl border p-3.5 transition-colors ${
                  isLight
                    ? 'border-[#e0e3eb] bg-[#f8f9fa]'
                    : 'border-[#2a2e39]/80 bg-[#161922]/70'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-xs font-bold tracking-wide ${isLight ? 'text-[#131722]' : 'text-white'}`}>
                    اطلاعات نماد و ارقام زنده
                  </span>
                  <span className={`text-[10.5px] font-medium ${isLight ? 'text-[#5f6368]' : 'text-[#9aa0a6]'}`}>
                    Symbol, OHLC & Volume
                  </span>
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-2">
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
                </div>
              </div>

              <div
                className={`flex flex-col gap-2 rounded-xl border p-3.5 transition-colors ${
                  isLight
                    ? 'border-[#e0e3eb] bg-[#f8f9fa]'
                    : 'border-[#2a2e39]/80 bg-[#161922]/70'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-xs font-bold tracking-wide ${isLight ? 'text-[#131722]' : 'text-white'}`}>
                    اندیکاتورها و افسانه چارت
                  </span>
                  <span className={`text-[10.5px] font-medium ${isLight ? 'text-[#5f6368]' : 'text-[#9aa0a6]'}`}>
                    Indicator Values & Legend
                  </span>
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-2">
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
                </div>
              </div>

              <p
                className={`rounded-xl border p-3.5 text-xs leading-6 transition-colors ${
                  isLight
                    ? 'border-[#e0e3eb] bg-[#f8f9fa] text-[#434651]'
                    : 'border-[#2a2e39]/60 bg-[#161922]/50 text-[#9aa0a6]'
                }`}
              >
                با فعال‌بودن خط وضعیت، هنگام حرکت نشانگر موس روی کندل‌ها مقادیر باز، بالاترین، پایین‌ترین، پایانی و حجم به
                صورت تبولار و بدون پرش به‌روزرسانی می‌شوند.
              </p>
            </div>
          )}

          {/* ۳. تب مقیاس‌ها (Scales) */}
          {tab === 'scales' && (
            <div className="flex flex-col gap-2.5">
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
                    className={`rounded-lg border px-3 py-1.5 text-xs font-bold transition-all ${
                      view.axisTickMargin === m
                        ? 'border-[#2962ff] bg-[#2962ff]/25 text-white ring-1 ring-[#2962ff]/40 shadow-sm'
                        : isLight
                        ? 'border-[#d1d4dc] bg-[#f0f3fa] text-[#131722] hover:border-[#b2b5be] hover:bg-[#e0e3eb]'
                        : 'border-[#2a2e39] bg-[#1e222d] text-[#d1d4dc] hover:border-[#363a45] hover:bg-[#262b3d] hover:text-white'
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
            <div className="flex flex-col gap-2.5">
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
                      className={`h-7 w-7 cursor-pointer rounded border bg-transparent ${
                        isLight ? 'border-[#d1d4dc]' : 'border-[#2a2e39]'
                      }`}
                    />
                    <span className={`font-mono text-xs ${isLight ? 'text-[#5f6368]' : 'text-[#9aa0a6]'}`}>
                      {view.customBgColor || '#131722'}
                    </span>
                  </div>
                )}
              </Row>

              <Row label="رنگ کندل صعودی" hint="رنگ رشد قیمت (سبز)">
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
                  className={`rounded-lg border px-3 py-1 text-xs font-semibold transition-colors ${
                    isLight
                      ? 'border-[#d1d4dc] bg-[#f0f3fa] text-[#131722] hover:border-[#b2b5be] hover:bg-[#e0e3eb]'
                      : 'border-[#2a2e39] bg-[#1a1e29] text-[#e0e3eb] hover:border-[#434857] hover:bg-[#262b3d] hover:text-white'
                  }`}
                >
                  بازنشانی
                </button>
              </Row>

              <Row label="رنگ کندل نزولی" hint="رنگ افت قیمت (قرمز)">
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
                  className={`rounded-lg border px-3 py-1 text-xs font-semibold transition-colors ${
                    isLight
                      ? 'border-[#d1d4dc] bg-[#f0f3fa] text-[#131722] hover:border-[#b2b5be] hover:bg-[#e0e3eb]'
                      : 'border-[#2a2e39] bg-[#1a1e29] text-[#e0e3eb] hover:border-[#434857] hover:bg-[#262b3d] hover:text-white'
                  }`}
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
                  <span className={`text-xs font-semibold ${isLight ? 'text-[#5f6368]' : 'text-[#9aa0a6]'}`}>شفافیت:</span>
                  {[5, 10, 20, 50].map((op) => (
                    <button
                      key={op}
                      type="button"
                      aria-pressed={view.watermarkOpacity === op}
                      onClick={() => setView({ watermarkOpacity: op })}
                      className={`rounded-lg border px-2.5 py-1 text-xs font-bold transition-all ${
                        view.watermarkOpacity === op
                          ? 'border-[#2962ff] bg-[#2962ff] text-white shadow-sm'
                          : isLight
                          ? 'border-[#d1d4dc] bg-[#f0f3fa] text-[#131722] hover:border-[#b2b5be] hover:bg-[#e0e3eb]'
                          : 'border-[#2a2e39] bg-[#1e222d] text-[#d1d4dc] hover:border-[#363a45] hover:text-white'
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
            <div className="flex flex-col gap-3 py-1">
              <Row label="رویدادهای شرکتی و مجامع روی چارت" hint="Corporate Actions">
                <Toggle
                  on={view.showCorporateActions !== false}
                  label="نمایش کلیه نشانگرهای رویداد شرکتی روی کندل‌ها"
                  onClick={() => setView({ showCorporateActions: view.showCorporateActions === false })}
                />
              </Row>

              <div
                className={`rounded-xl border p-4 text-xs leading-6 space-y-2 transition-colors ${
                  isLight
                    ? 'border-[#e0e3eb] bg-[#f8f9fa] text-[#131722]'
                    : 'border-[#2a2e39] bg-[#141722] text-[#e0e3eb]'
                }`}
              >
                <div className={`flex items-center gap-2 font-bold ${isLight ? 'text-[#131722]' : 'text-white'}`}>
                  <span className="inline-block h-2 w-2 rounded-full bg-[#2962ff]" />
                  <span>راهنمای نشانگرهای رویداد:</span>
                </div>
                <ul className={`list-inside list-disc space-y-1 pr-2 ${isLight ? 'text-[#434651]' : 'text-[#b2b5be]'}`}>
                  <li><strong className="text-[#2962ff]">نشانگر آبی D:</strong> سود نقدی تصویب‌شده در مجمع سالیانه به همراه مقدار ریالی هر سهم.</li>
                  <li><strong className="text-[#f59e0b]">نشانگر کهربایی S:</strong> درصد افزایش سرمایه از محل سود انباشته، آورده نقدی یا تجدید ارزیابی.</li>
                </ul>
                <p
                  className={`border-t pt-2 ${isLight ? 'border-[#e0e3eb] text-[#5f6368]' : 'border-[#2a2e39]/80 text-[#b2b5be]'}`}
                  data-testid="settings-events-note"
                >
                  رویدادهای سود نقدی، مجامع و افزایش سرمایه به صورت زنده از سامانه کدال در سرور ثبت می‌شوند؛
                  این تب فاقد هرگونه داده ساختگی یا شبیه‌سازی‌شده است.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* فوتر پنجره */}
        <div
          className={`flex items-center justify-between border-t px-5 py-3.5 transition-colors ${
            isLight ? 'border-[#e0e3eb] bg-[#f8f9fa]' : 'border-[#2a2e39] bg-[#1a1e29]'
          }`}
        >
          <span className={`text-xs font-medium ${isLight ? 'text-[#5f6368]' : 'text-[#b2b5be]'}`}>
            کلیه تنظیمات به صورت خودکار در حافظه مرورگر ذخیره می‌شوند.
          </span>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg bg-[#2962ff] px-4 py-1.5 text-xs font-bold text-white shadow-md shadow-[#2962ff]/30 transition-all hover:bg-[#1e53e5] active:scale-95"
          >
            بستن و اعمال
          </button>
        </div>
      </div>
    </div>
  );
}

