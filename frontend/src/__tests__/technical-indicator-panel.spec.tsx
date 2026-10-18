// تستِ مرحلۀ ۶ — پنلِ کاتالوگِ لایه‌ها، افسانۀ چارت و شواهدِ کلیک
// قانونِ اصلیِ همین تست‌ها «بی‌داده رأی نیست» است: هیچ state‌ای («فعال»،
// «دادهٔ ناکافی»، «در حال تشکیل») بی‌پرچم یا بی‌عددِ خودِ سرور صادر نمی‌شود،
// و زمانِ تأیید از زمانِ وقوع جدا می‌ماند (ضدِ repaint، مرحلۀ ۱۰).
import { fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';

import { FtsIndicatorPanel } from '@features/technical/components/FtsIndicatorPanel';
import { FtsLayerLegend } from '@features/technical/components/FtsLayerLegend';
import { catalogEntry, FTS_INDICATOR_CATALOG } from '@features/technical/lib/ftsIndicatorCatalog';
import { layerEvidence, sourceExists } from '@features/technical/lib/ftsLayerEvidence';
import { PATTERN_PREFS_DEFAULT } from '@features/technical/lib/patternOverlays';
import type { FtsAnalysisData } from '@features/technical/api/useFtsAnalysis';
import { useFtsConfigStore, VIEW_DEFAULTS } from '@features/technical/stores/ftsConfigStore';
import { usePatternPrefsStore } from '@features/technical/stores/patternPrefsStore';

const jetOn = {
  jet: { active: true, resistance: 2758, resistance_date: '2026-02-10', tier: 'standing-ceiling' },
  fib: {
    zone_33_40: { lo: 2100, hi: 2250, in_zone: false },
    leg: { direction: 'down', end: '2026-02-01', provisional: true },
    levels: [{ ratio: 0.33, price: 2200 }],
  },
  structure_points: {
    D: [
      { idx: 4, time: '2026-01-20', confirm_idx: 6, confirm_time: '2026-01-22', price: 1900, kind: 'low', label: 'HL' },
      { idx: 9, time: '2026-02-05', confirm_idx: 12, confirm_time: '2026-02-08', price: 2600, kind: 'high', label: 'HH' },
    ],
  },
} as unknown as FtsAnalysisData;

const jetShort = {
  jet: { active: false, resistance: null, bars_available: 40, bars_required: 120, reason: 'تاریخچهٔ جت ناکافی است' },
} as unknown as FtsAnalysisData;

beforeEach(() => {
  localStorage.clear();
  usePatternPrefsStore.setState({ prefs: { ...PATTERN_PREFS_DEFAULT } });
  useFtsConfigStore.setState({ view: { ...VIEW_DEFAULTS } });
});

describe('لایۀ شواهد (lib/ftsLayerEvidence)', () => {
  it('بی‌payload هیچ لایه‌ای «فعال» نیست و هیچ عددی ساخته نمی‌شود', () => {
    const e = layerEvidence(catalogEntry('jet')!, null);
    expect(e.state).toBe('not-published');
    expect(e.facts).toEqual([]);
  });

  it('جتِ فعال: عددِ سرور، تاریخِ سرور — بدونِ زمانِ تأییدِ ساختگی', () => {
    const e = layerEvidence(catalogEntry('jet')!, jetOn);
    expect(e.state).toBe('active');
    expect(e.occurredAt).toBe('2026-02-10');
    expect(e.confirmedAt).toBeNull();
    expect(e.facts.find((f) => f.label === 'مقاومت')?.value).toBe('۲٬۷۵۸');
  });

  it('ناکافی فقط با دو عددِ خودِ سرور ادعا می‌شود، و علتِ سرور عیناً می‌آید', () => {
    const e = layerEvidence(catalogEntry('jet')!, jetShort);
    expect(e.state).toBe('insufficient');
    expect(e.note).toBe('تاریخچهٔ جت ناکافی است');
    expect(e.facts.map((f) => f.label)).toContain('حداقلِ لازم');
  });

  it('کمربندِ فیبو رویِ موجِ پیش‌نویس «در حال تشکیل» است نه «فعال» (P0#4)', () => {
    const e = layerEvidence(catalogEntry('fib-belt-33-40')!, jetOn);
    expect(e.state).toBe('forming');
    expect(e.note).toContain('پیش‌نویس');
  });

  it('نقاطِ ساختار: «کِی رخ داد» و «کِی فهمیدیم» دو زمانِ جدا هستند', () => {
    const e = layerEvidence(catalogEntry('structure-points')!, jetOn);
    expect(e.state).toBe('active');
    expect(e.occurredAt).toBe('2026-02-05');
    expect(e.confirmedAt).toBe('2026-02-08');
  });

  it('ساختارِ هفتگی: شمارشِ خودِ سرور با ارقامِ فارسی، بی‌پیوتِ W «غیرفعال» است نه حدس (ب-۱)', () => {
    const weekly = {
      structure_points: {
        D: jetOn.structure_points?.D ?? [],
        W: [
          { idx: 2, time: '2026-01-17', confirm_idx: 4, confirm_time: '2026-01-23', price: 1750, kind: 'low', label: 'LL' },
          { idx: 8, time: '2026-02-01', confirm_idx: 11, confirm_time: '2026-02-06', price: 2480, kind: 'high', label: 'HH' },
        ],
      },
    } as unknown as FtsAnalysisData;
    const e = layerEvidence(catalogEntry('structure-points-weekly')!, weekly);
    expect(e.state).toBe('active');
    expect(e.occurredAt).toBe('2026-02-01');
    expect(e.confirmedAt).toBe('2026-02-06');
    expect(e.facts.find((f) => f.label === 'پیوت‌هایِ هفتگی')?.value).toBe('۲ نقطه');
    expect(e.facts.find((f) => f.label === 'آخرین برچسب')?.value).toBe('HH');
    expect(layerEvidence(catalogEntry('structure-points-weekly')!, jetOn).state).toBe('inactive');
    expect(layerEvidence(catalogEntry('structure-points-weekly')!, null).state).toBe('inactive');
    expect(layerEvidence(catalogEntry('structure-points-weekly')!, null).note).toContain('پیوتِ هفتگی');
  });

  it('جعبۀ رنج: سقف/کف/درصد از سرور + کرانۀ زمانیِ باکس؛ بی‌عدد «ناکافی» (ب-۳)', () => {
    const box = {
      range_box: {
        active: true, top: 2750, bottom: 2410, pct_above_top: 1.2,
        start_date: '2026-01-06', end_date: '2026-01-26', reason: null,
      },
    } as unknown as FtsAnalysisData;
    const e = layerEvidence(catalogEntry('range-box')!, box);
    expect(e.state).toBe('active');
    expect(e.occurredAt).toBe('2026-01-26');
    expect(e.facts.find((f) => f.label === 'سقفِ باکس')?.value).toBe('۲٬۷۵۰');
    expect(e.facts.find((f) => f.label === 'کفِ باکس')?.value).toBe('۲٬۴۱۰');
    expect(e.note).toContain('۲۰۲۶-۰۱-۰۶');
    const quiet = {
      range_box: { active: false, top: 2750, bottom: 2410, pct_above_top: null, end_date: '2026-01-26', reason: 'بستهٔ سقف' },
    } as unknown as FtsAnalysisData;
    expect(layerEvidence(catalogEntry('range-box')!, quiet).state).toBe('inactive');
    const empty = { range_box: { active: false, top: null, bottom: null, reason: '۲۱ کندل سابقه بسته نیست' } } as unknown as FtsAnalysisData;
    const n = layerEvidence(catalogEntry('range-box')!, empty);
    expect(n.state).toBe('insufficient');
    expect(n.facts).toEqual([]);
    expect(n.note).toBe('۲۱ کندل سابقه بسته نیست');
    expect(layerEvidence(catalogEntry('range-box')!, jetOn).state).toBe('not-published');
  });

  it('لایۀ غیرِ payload (رویدادهای شرکتی) از feed خوانده می‌شود، نه از `/api/fts`', () => {
    const entry = catalogEntry('corp-actions')!;
    expect(layerEvidence(entry, jetOn).state).toBe('not-published');
    expect(layerEvidence(entry, jetOn, { adjustmentEvents: 3 }).state).toBe('active');
    expect(sourceExists(jetOn, entry.source)).toBe(false);
    expect(sourceExists(jetOn, 'jet.resistance')).toBe(true);
  });
});

describe('پنلِ کاتالوگِ لایه‌ها', () => {
  function mountPanel(fts: FtsAnalysisData | null = jetOn, adjustmentEvents: number | null = 2) {
    render(
      <FtsIndicatorPanel
        fts={fts}
        basis="tsetmc-adjusted"
        bars={320}
        lastBarDate="۱۴۰۴/۱۱/۲۱"
        fetchedAtMs={Date.parse('2026-05-12T09:30:00Z')}
        adjustmentEvents={adjustmentEvents}
      />,
    );
  }

  it('ششِ گروه با نامِ فارسی می‌آید و هر سوییچ مستقل است', () => {
    mountPanel();
    for (const g of ['trend', 'structure', 'fibonacci', 'entry-setup', 'exit-risk', 'history-events']) {
      expect(screen.getByTestId(`fts-layer-group-${g}`)).toBeInTheDocument();
    }
    fireEvent.click(screen.getByTestId('fts-layer-toggle-structure-points'));
    expect(usePatternPrefsStore.getState().prefs.structure.enabled).toBe(false);
    fireEvent.click(screen.getByTestId('fts-layer-toggle-fib-levels'));
    expect(useFtsConfigStore.getState().view.showFibLevels).toBe(true);
  });

  it('لایۀ بی‌توسلِ جدا سوییچِ مرده ندارد (کمربندِ فیبو)', () => {
    mountPanel();
    expect(screen.getByTestId('fts-layer-toggle-fib-belt-33-40')).toBeDisabled();
  });

  it('صداقتِ رجیستری: حدِ ضرر درِ FFC رسم می‌شود، درِ KLineCharts نه', () => {
    mountPanel();
    const row = screen.getByTestId('fts-layer-row-hard-stop');
    expect(within(row).getByText(/K ✗/)).toBeInTheDocument();
    expect(within(row).getByText(/F ✓/)).toBeInTheDocument();
  });

  it('کلیکِ شواهد: قاعده → خروجیِ الگوریتم → انوتیشن با زمانِ تأیید', () => {
    mountPanel();
    fireEvent.click(screen.getByTestId('fts-layer-evidence-btn-structure-points'));
    const card = screen.getByTestId('fts-layer-evidence');
    expect(within(card).getByTestId('fts-evidence-rule').textContent).toContain('روند ساختاری صعودی/نزولی/خنثی');
    expect(within(card).getByTestId('fts-evidence-source').textContent).toContain('structure_points.D');
    const times = within(card).getByTestId('fts-evidence-times').textContent ?? '';
    expect(times).toContain('2026-02-05');
    expect(times).toContain('2026-02-08');
  });

  it('بی‌payload برچسبِ «فعال» صادر نمی‌شود؛ خطِ تازگی مبنا و کندلِ تحلیل را می‌گوید', () => {
    // بی‌رویدادِ مبدأ هم: لایۀ خارجِ جزوه («رویدادهای شرکتی») از feed خوانده
    // می‌شود، پس feed تهی ⇒ آن سطر هم «منتشر نشده» است.
    mountPanel(null, null);
    for (const e of FTS_INDICATOR_CATALOG) {
      expect(screen.getByTestId(`fts-layer-state-${e.id}`).textContent, e.id).not.toBe('فعال');
    }
    expect(screen.getByTestId('fts-layer-freshness').textContent).toContain('tsetmc-adjusted');
    expect(screen.getByTestId('fts-layer-freshness').textContent).toContain('۳۲۰');
  });
});

describe('افسانۀ لایه‌های رسم‌شده', () => {
  it('فقط لایه‌هایِ فعالِ همین موتور؛ خاموش‌کردن از همین‌جا کار می‌کند', () => {
    render(<FtsLayerLegend fts={jetOn} engineId="klinecharts" adjustmentEvents={2} />);
    const legend = screen.getByTestId('fts-layer-legend');
    expect(within(legend).getByTestId('fts-legend-item-jet')).toBeInTheDocument();
    // درِ klinecharts حدِ ضرر رسم نمی‌شود ⇒ درِ افسانه هم نیست
    expect(within(legend).queryByTestId('fts-legend-item-hard-stop')).toBeNull();
    fireEvent.click(within(legend).getByTestId('fts-legend-item-jet'));
    expect(usePatternPrefsStore.getState().prefs.jet.enabled).toBe(false);
  });

  it('بی‌داده هیچ نشانگری تضمین نمی‌شود («لایۀ فعالی رویِ چارت نیست»)', () => {
    render(<FtsLayerLegend fts={null} engineId="ffc" adjustmentEvents={null} />);
    expect(screen.getByTestId('fts-layer-legend').textContent).toContain('لایۀ فعالی');
  });
});
