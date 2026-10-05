// گاردِ دو باگی که سنجشِ زندهٔ موتورِ دوم گرفت (۱۴۰۵-۰۷-۱۳):
//   ۱) `updateProps({drawings})` درِ خودِ بسته بی‌صدا دور ریخته می‌شود مگر
//      `controlled: {drawings: true}` اعلام شده باشد (defaultControlledState
//      درِ chart-engine.js هر سه کلید را false می‌گذارد). بی‌این، هیچ لایهٔ
//      FTS یا نشانگرِ رویدادی درِ موتورِ دوم رسم نمی‌شد و شمارشِ «لایهٔ FTS»
//      درِ نوارِ پایین عددِ درست را می‌گفت ولی بوم خالی بود.
//   ۲) واحدِ `ts` درِ این بسته میلی‌ثانیۀِ UTC است (README: `ts: Date.now()`،
//      `ts: 1739990400000`). پیش‌تر بر ۱۰۰۰ تقسیم می‌شد؛ محورِ زمان به‌جایِ
//      ۱۸۰ روز، چهار ساعت نشان می‌داد و بدنهٔ کندل‌ها روی هم می‌افتاد.
// تست با بدلِ ChartEngine نوشته می‌شود؛ WebGL درِ jsdom نیست و لازم هم نیست.
import { describe, expect, it, vi } from 'vitest';

type Props = Record<string, unknown>;
const ctorProps: Props[] = [];
const patches: Props[] = [];

vi.mock('@pairlens/fast-financial-charts/financial-chart', () => ({
  ChartEngine: class {
    props: Props;
    constructor(opts: { elements: unknown; props: Props }) {
      this.props = opts.props;
      ctorProps.push(opts.props);
    }
    updateProps(next: Props) {
      Object.assign(this.props, next);
      patches.push(next);
    }
    resize() {}
    destroy() {}
  },
}));

const { FastFinancialChartsEngine } = await import('./FastFinancialChartsEngine');
const { paletteFromTheme } = await import('../index');

/** خواندنِ مسیرِ تودرتو از آبجکتِ بی‌شکلِ خودِ بسته */
function at(o: unknown, ...keys: (string | number)[]): unknown {
  let cur: unknown = o;
  for (const k of keys) {
    if (cur === null || typeof cur !== 'object') return undefined;
    cur = (cur as Record<string | number, unknown>)[k];
  }
  return cur;
}

const TS = 1739990400000; // ۳۰ بهمن ۱۴۰۳ -- میلی‌ثانیه

async function mounted() {
  const eng = new FastFinancialChartsEngine();
  await eng.mount(document.createElement('div'), {
    visibleBars: 180,
    palette: paletteFromTheme(false),
    candleStyle: 'candles',
    formatTime: (ts: number) => String(ts),
    formatPrice: (v: number) => String(v),
  });
  return eng;
}

const lastOf = (key: string) => patches.filter((p) => p[key]).pop();

describe('موتورِ دوم: کانالِ لایه‌ها و واحدِ زمان', () => {
  it('کانالِ drawings را اعلام می‌کند، وگرنه خودِ بسته patch را دور می‌ریزد', async () => {
    ctorProps.length = 0;
    await mounted();
    expect(ctorProps.length).toBeGreaterThan(0);
    expect(at(ctorProps[0], 'controlled', 'drawings')).toBe(true);
  });

  it('کندل‌ها با همان میلی‌ثانیۀِ ورودی به بسته می‌روند (بی‌تقسیم بر ۱۰۰۰)', async () => {
    ctorProps.length = 0;
    patches.length = 0;
    const eng = await mounted();
    eng.setBars([{ timestamp: TS, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 }]);
    expect(at(lastOf('series'), 'series', 0, 'bars', 0, 'ts')).toBe(TS);
  });

  it('نشانگرِ رویداد هم با همان میلی‌ثانیه به drawings می‌نشیند', async () => {
    ctorProps.length = 0;
    patches.length = 0;
    const eng = await mounted();
    eng.applyOverlays('fts-corp-events', [
      { id: 'corp-shareChange-2025-02-09', kind: 'marker', group: 'fts-corp-events',
        points: [{ timestamp: TS, value: 105 }], color: '#2dd4bf', label: 'تغییر سهام' },
    ]);
    const d = at(lastOf('drawings'), 'drawings', 0);
    expect(at(d, 'type')).toBe('text');
    expect(at(d, 'point', 'ts')).toBe(TS);
    expect(at(d, 'content')).toBe('تغییر سهام');
  });

  it('هر سه گروه در یک patch می‌آیند (جایگزینیِ کامل، نه انباشت)', async () => {
    ctorProps.length = 0;
    patches.length = 0;
    const eng = await mounted();
    const mk = (g: string, ts: number) => ({
      id: `${g}-lvl`, kind: 'level' as const, group: g,
      points: [{ timestamp: ts, value: 100 }], color: '#ffffff',
    });
    eng.applyOverlays('fts-fib', [mk('fts-fib', TS)]);
    eng.applyOverlays('fts-pattern', [mk('fts-pattern', TS + 1000)]);
    eng.applyOverlays('fts-corp-events', [mk('fts-corp-events', TS + 2000)]);
    const all = at(lastOf('drawings'), 'drawings');
    expect(all).toHaveLength(3);
  });
});
