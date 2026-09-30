// features/technical/components/ChartSettingsDialog.tsx -- دیالوگ تنظیمات چارت
//
// شش تب، به همان ترتیبِ دیالوگِ استاندارد (بخش ۱۵ از docs/CHART-PARITY-REFERENCE.md):
//   نماد · خط وضعیت · مقیاس‌ها · رنگ‌بندی · دقت و اعشار · رویدادها
//
// دو قانونِ این فایل:
//  ۱) هر گزینه‌ای که اینجا هست، در چارتِ زنده اثر می‌گذارد. دکمهٔ بی‌اثر
//     ممنوع (#40 همان بود که «تیک‌های مرده» را ثبت کرد).
//  ۲) رنگ و اندازه از توکن‌هایِ تم می‌آید (bg-bg-card / border-border-c /
//     text-text-* / accent-*)، نه از هگزِ دست‌ساز — وگرنه دیالوگ در تمِ روشن
//     با خودِ برنامه می‌جنگید.
import { useState } from 'react';
import {
  useFtsConfigStore,
  type ChartType,
  type PriceScale,
  type Timeframe,
} from '../stores/ftsConfigStore';
import { Modal } from '@shared/ui/Modal';

/** هشت نوعِ چارتی که موتورِ زنده واقعاً رندر می‌کند: شش مقدارِ `candle.type`ِ
 *  klinecharts v10، به‌علاوهٔ «خط» (اریای بی‌سطح) و «Heikin-Ashi» (تبدیلِ سریِ
 *  نمایشی). Renko/Kagi/PnF عمداً نیستند: آن‌ها زمانِ کندل را می‌سازند و با
 *  کلیدِ زمانیِ چارتِ زنده و ابزارهای ترسیم می‌جنگند. */
const TYPES: { key: ChartType; label: string }[] = [
  { key: 'candle_solid', label: 'کندل شمعی' },
  { key: 'candle_stroke', label: 'کندل توخالی' },
  { key: 'candle_up_stroke', label: 'توخالیِ صعودی' },
  { key: 'candle_down_stroke', label: 'توخالیِ نزولی' },
  { key: 'ohlc', label: 'میله‌ای (OHLC)' },
  { key: 'line', label: 'خط' },
  { key: 'area', label: 'اریا' },
  { key: 'heikin_ashi', label: 'هیکین-آشی' },
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

/** گزینه‌های اعشارِ محور؛ 'auto' یعنی همان چیزی که تعدیل می‌گوید */
const PRECISIONS: { key: 'auto' | 0 | 1 | 2 | 3 | 4; label: string }[] = [
  { key: 'auto', label: 'خودکار' },
  { key: 0, label: '۰' },
  { key: 1, label: '۱' },
  { key: 2, label: '۲' },
  { key: 3, label: '۳' },
  { key: 4, label: '۴' },
];

type Tab = 'symbol' | 'status' | 'scales' | 'colors' | 'precision' | 'events';

const TABS: { id: Tab; label: string }[] = [
  { id: 'symbol', label: 'نماد' },
  { id: 'status', label: 'خط وضعیت' },
  { id: 'scales', label: 'مقیاس‌ها' },
  { id: 'colors', label: 'رنگ‌بندی' },
  { id: 'precision', label: 'دقت و اعشار' },
  { id: 'events', label: 'رویدادها' },
];

function Row({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-border-c bg-bg-card/60 p-3">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-2xs font-bold text-text-primary">{label}</span>
        {hint ? <span className="text-3xs font-medium text-text-muted">{hint}</span> : null}
      </div>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </div>
  );
}

function Choice<T extends string | number>({
  options,
  value,
  onPick,
}: {
  options: { key: T; label: string; hint?: string }[];
  value: T;
  onPick: (v: T) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {options.map((o) => {
        const isActive = value === o.key;
        return (
          <button
            key={String(o.key)}
            type="button"
            title={o.hint}
            aria-pressed={isActive}
            onClick={() => onPick(o.key)}
            className={`rounded-lg border px-3 py-1.5 text-2xs font-bold transition-colors ${
              isActive
                ? 'border-accent-blue bg-accent-blue/20 text-text-primary ring-1 ring-accent-blue/50'
                : 'border-border-c bg-bg-card/40 text-text-secondary hover:border-border-accent hover:text-text-primary'
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

function Toggle({ on, label, hint, onClick }: { on: boolean; label: string; hint?: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={on}
      title={hint}
      className={`inline-flex items-center gap-2.5 rounded-lg border px-3 py-1.5 text-2xs font-semibold transition-colors ${
        on
          ? 'border-accent-green/60 bg-accent-green/15 text-text-primary'
          : 'border-border-c bg-bg-card/40 text-text-secondary hover:border-border-accent hover:text-text-primary'
      }`}
    >
      <span
        className={`relative inline-flex h-3.5 w-6 shrink-0 items-center rounded-full transition-colors ${
          on ? 'bg-accent-green' : 'bg-border-c'
        }`}
      >
        <span
          className={`inline-block h-2.5 w-2.5 rounded-full bg-bg-primary transition-transform ${
            on ? '-translate-x-3' : '-translate-x-0.5'
          }`}
        />
      </span>
      {label}
    </button>
  );
}

/** ردیفِ انتخابِ رنگ — یک‌جا ساخته می‌شود تا صعودی/نزولی دو نسخهٔ واگرا نشوند */
function SwatchRow({
  label,
  hint,
  colors,
  value,
  testPrefix,
  onPick,
  onReset,
}: {
  label: string;
  hint: string;
  colors: string[];
  value: string | null;
  testPrefix: 'up' | 'down';
  onPick: (c: string) => void;
  onReset: () => void;
}) {
  return (
    <Row label={label} hint={hint}>
      {colors.map((c) => (
        <button
          key={c}
          type="button"
          aria-label={`${label} ${c}`}
          data-testid={`${testPrefix}-${c}`}
          aria-pressed={value === c}
          onClick={() => onPick(c)}
          className={`h-6 w-6 rounded-full border-2 transition-transform hover:scale-110 ${
            value === c ? 'border-text-primary scale-110' : 'border-border-c'
          }`}
          style={{ background: c }}
        />
      ))}
      <button
        type="button"
        data-testid={`reset-${testPrefix}`}
        onClick={onReset}
        className="rounded-lg border border-border-c px-3 py-1 text-2xs font-semibold text-text-secondary transition-colors hover:border-border-accent hover:text-text-primary"
      >
        بازنشانی
      </button>
    </Row>
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
  const timeframe = useFtsConfigStore((s) => s.timeframe);
  const view = useFtsConfigStore((s) => s.view);
  const showGrid = useFtsConfigStore((s) => s.showGrid);
  const showCrosshair = useFtsConfigStore((s) => s.showCrosshair);
  const showRsi = useFtsConfigStore((s) => s.showRsi);
  const showVolMa = useFtsConfigStore((s) => s.showVolMa);

  const setPriceScale = useFtsConfigStore((s) => s.setPriceScale);
  const setChartType = useFtsConfigStore((s) => s.setChartType);
  const setTimeframe = useFtsConfigStore((s) => s.setTimeframe);
  const setView = useFtsConfigStore((s) => s.setView);
  const toggleDisplay = useFtsConfigStore((s) => s.toggleDisplay);
  const toggleIndicator = useFtsConfigStore((s) => s.toggleIndicator);

  if (!open) return null;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="تنظیمات چارت"
      description={symbol ?? undefined}
      className="max-w-2xl"
      testId="chart-settings"
      footer={
        <div className="flex items-center justify-between">
          <span className="text-2xs text-text-muted">هر تغییر بی‌درنگ ذخیره و اعمال می‌شود.</span>
          <button
            type="button"
            onClick={onClose}
            data-testid="chart-settings-done"
            className="rounded-lg bg-accent-blue/25 px-4 py-1.5 text-2xs font-bold text-text-primary ring-1 ring-accent-blue/60 transition-colors hover:bg-accent-blue/35"
          >
            بستن و اعمال
          </button>
        </div>
      }
    >

        <div
          className="flex flex-wrap gap-1.5 border-b border-border-c bg-bg-card/40 px-4 py-2"
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
                className={`rounded-lg px-3 py-1.5 text-2xs font-bold transition-colors ${
                  isActive
                    ? 'bg-accent-blue/25 text-text-primary ring-1 ring-accent-blue/60'
                    : 'text-text-secondary hover:bg-bg-card hover:text-text-primary'
                }`}
              >
                {t.label}
              </button>
            );
          })}
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {tab === 'symbol' && (
            <div className="flex flex-col gap-2.5">
              <Row label="نوع چارت">
                <Choice options={TYPES} value={chartType} onPick={setChartType} />
              </Row>
              <Row label="تایم‌فریم" hint="دقیقه‌ای در بانکِ داده نیست">
                <Choice options={TIMEFRAMES} value={timeframe} onPick={setTimeframe} />
              </Row>
              <Row label="تایم‌زون" hint="ساعتِ محورِ زمانی">
                <Choice options={TIMEZONES} value={view.timezone || 'Asia/Tehran'} onPick={(tz) => setView({ timezone: tz })} />
              </Row>
            </div>
          )}

          {tab === 'status' && (
            <div className="flex flex-col gap-2.5">
              <Row label="خطِ وضعیتِ کندل" hint="همان بلوکِ بالایِ چارت">
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
                  on={view.statusShowSymbol}
                  label="نام نماد"
                  onClick={() => setView({ statusShowSymbol: !view.statusShowSymbol })}
                />
              </Row>
              <Row label="مقادیر اندیکاتورها">
                <Toggle
                  on={view.statusShowIndicators}
                  label="ارزشِ مطالعاتِ فعال"
                  onClick={() => setView({ statusShowIndicators: !view.statusShowIndicators })}
                />
                <Toggle
                  on={view.showLegend}
                  label="افسانهٔ گوشهٔ چارت"
                  onClick={() => setView({ showLegend: !view.showLegend })}
                />
              </Row>
              <Row label="چسبندگیِ متن" hint="جلویِ دیدِ کندل‌ها را نگیرد">
                <Toggle
                  on={view.legendAlways === true}
                  label="همیشه روی بوم بماند"
                  hint="خاموش: فقط وقتی نشانگر روی چارت است خوانده می‌شود"
                  onClick={() => setView({ legendAlways: !(view.legendAlways === true) })}
                />
              </Row>
            </div>
          )}

          {tab === 'scales' && (
            <div className="flex flex-col gap-2.5">
              <Row label="مقیاسِ محورِ قیمت" hint="محورِ عمودی">
                <Choice options={SCALES} value={priceScale} onPick={setPriceScale} />
              </Row>
              <Row label="جایگاهِ محور">
                <Choice options={POSITIONS} value={view.priceScalePos} onPick={(v) => setView({ priceScalePos: v })} />
                <Toggle
                  on={view.yAxisInside}
                  label="برچسب داخلِ چارت"
                  onClick={() => setView({ yAxisInside: !view.yAxisInside })}
                />
                <Toggle
                  on={view.yAxisReverse}
                  label="معکوس‌سازی"
                  onClick={() => setView({ yAxisReverse: !view.yAxisReverse })}
                />
              </Row>
              <Row label="مقیاسِ عمودی هنگامِ جابه‌جایی" hint="درگِ افقی نباید چارت را عمودی بتکاند">
                <Toggle
                  on={view.axisScaleLock === true}
                  label="قفلِ قیمت به نسبتِ کندل"
                  hint="روشن: زوم هم مقیاس را نمی‌شکند. خاموش: فقط درگِ افقی مقیاس را نمی‌پراند."
                  onClick={() => setView({ axisScaleLock: !(view.axisScaleLock === true) })}
                />
              </Row>
              <Row label="قفلِ اسکرول و زومِ محور (موتورِ کهنه)" hint="در موتورِ lightweight اعمال می‌شود">
                <Toggle
                  on={view.axisDragLock}
                  label="قفل درگ محور"
                  onClick={() => setView({ axisDragLock: !view.axisDragLock })}
                />
              </Row>
              <Row label="ترازهای فیبوناچی">
                <Toggle
                  on={view.fibLogarithmic === true}
                  label="بر پایۀ مقیاسِ لگاریتمی"
                  onClick={() => setView({ fibLogarithmic: !(view.fibLogarithmic === true) })}
                />
              </Row>
              <Row label="حاشیۀ برچسبِ محورها">
                <Choice
                  options={[0, 3, 6, 10].map((m) => ({ key: m, label: `${m}px` }))}
                  value={view.axisTickMargin}
                  onPick={(m) => setView({ axisTickMargin: m })}
                />
              </Row>
            </div>
          )}

          {tab === 'colors' && (
            <div className="flex flex-col gap-2.5">
              <Row label="پس‌زمینه">
                <Choice options={BACKGROUNDS} value={view.background} onPick={(v) => setView({ background: v })} />
                {view.background === 'custom' ? (
                  <span className="flex items-center gap-2">
                    <input
                      type="color"
                      aria-label="رنگِ پس‌زمینهٔ سفارشی"
                      value={view.customBgColor || '#131722'}
                      onChange={(e) => setView({ customBgColor: e.target.value })}
                      className="h-7 w-7 cursor-pointer rounded border border-border-c bg-transparent"
                    />
                    <span className="text-2xs text-text-muted">{view.customBgColor || '#131722'}</span>
                  </span>
                ) : null}
              </Row>
              <SwatchRow
                label="رنگ کندل صعودی"
                hint="رشد قیمت"
                colors={UP_COLORS}
                value={view.candleUp}
                testPrefix="up"
                onPick={(c) => setView({ candleUp: c, borderUp: c, wickUp: c })}
                onReset={() => setView({ candleUp: null, borderUp: null, wickUp: null })}
              />
              <SwatchRow
                label="رنگ کندل نزولی"
                hint="افت قیمت"
                colors={DOWN_COLORS}
                value={view.candleDown}
                testPrefix="down"
                onPick={(c) => setView({ candleDown: c, borderDown: c, wickDown: c })}
                onReset={() => setView({ candleDown: null, borderDown: null, wickDown: null })}
              />
              <Row label="بدنه، بوردر و سایه">
                <Toggle
                  on={view.showBorders}
                  label="بوردر دور کندل"
                  onClick={() => setView({ showBorders: !view.showBorders })}
                />
                <Toggle
                  on={view.showWicks}
                  label="سایهٔ کندل"
                  onClick={() => setView({ showWicks: !view.showWicks })}
                />
                <Toggle
                  on={view.wickGray}
                  label="سایهٔ خاکستری"
                  onClick={() => setView({ wickGray: !view.wickGray })}
                />
              </Row>
              <Row label="شبکۀ گرید">
                <Choice
                  options={GRID_STYLES}
                  value={view.gridStyle || 'dashed'}
                  onPick={(s) => setView({ gridStyle: s })}
                />
                <Toggle on={showGrid} label="نمایش گرید" onClick={() => toggleDisplay('grid')} />
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
              <Row label="کراس‌هیر">
                <Choice
                  options={CROSSHAIR_STYLES}
                  value={view.crosshairStyle || 'dashed'}
                  onPick={(s) => setView({ crosshairStyle: s })}
                />
                <Toggle on={showCrosshair} label="نمایش کراس‌هیر" onClick={() => toggleDisplay('crosshair')} />
              </Row>
              <Row label="واترمارک">
                <Toggle
                  on={view.showWatermark}
                  label="نمایش واترمارک"
                  onClick={() => setView({ showWatermark: !view.showWatermark })}
                />
                <Choice
                  options={[5, 10, 20, 50].map((op) => ({ key: op, label: `${op}٪` }))}
                  value={view.watermarkOpacity}
                  onPick={(op) => setView({ watermarkOpacity: op })}
                />
              </Row>
              <Row label="مطالعۀ همیشگی" hint="پنل‌های زیرِ چارت">
                <Toggle on={showVolMa} label="MA حجم ۲۱" onClick={() => toggleIndicator('volMa')} />
                <Toggle on={showRsi} label="RSI ۱۴" onClick={() => toggleIndicator('rsi')} />
              </Row>
            </div>
          )}

          {tab === 'precision' && (
            <div className="flex flex-col gap-2.5">
              <Row label="اعشارِ محورِ قیمت" hint="خودکار = بر پایۀ تعدیلِ انتخابی">
                <Choice
                  options={PRECISIONS}
                  value={view.pricePrecision}
                  onPick={(p) => setView({ pricePrecision: p })}
                />
              </Row>
              <p className="rounded-xl border border-border-c bg-bg-card/40 p-3 text-2xs leading-6 text-text-secondary">
                «خودکار» یعنی همان اعشاری که تعدیلِ انتخابی می‌گوید؛ عددِ صریح بر آن
                اولویت دارد و بی‌درنگ روی محور اعمال می‌شود. این فقط نمایش است — هیچ
                قیمتی گرد نمی‌شود و عددِ خامِ تابلو دست‌نخورده می‌ماند.
              </p>
            </div>
          )}

          {tab === 'events' && (
            <div className="flex flex-col gap-2.5">
              <Row label="نشانگرهای رویداد شرکتی" hint="مجامع، سود نقدی، افزایش سرمایه">
                <Toggle
                  on={view.showCorporateActions !== false}
                  label="نمایش روی کندل‌ها"
                  onClick={() => setView({ showCorporateActions: view.showCorporateActions === false })}
                />
              </Row>
              <div className="rounded-xl border border-border-c bg-bg-card/40 p-3 text-2xs leading-6 text-text-secondary">
                <p data-testid="settings-events-note">
                  رویدادهای سود نقدی، مجامع و افزایش سرمایه از همان تاریخچۀ سرور خوانده
                  می‌شوند؛ این تب هیچ دادهٔ شبیه‌سازی‌شده‌ای ندارد.
                </p>
                <p className="mt-2 text-text-muted">
                  TSETMC برای رویدادهای تاریخی فقط یک نسبتِ تعدیل منتشر می‌کند، پس تفکیکِ
                  «سود نقدی» از «افزایش سرمایه» روی چارت نمایش داده نمی‌شود — عددِ جداگانه
                  ساختگی می‌شد.
                </p>
              </div>
            </div>
          )}
        </div>

    </Modal>
  );
}
