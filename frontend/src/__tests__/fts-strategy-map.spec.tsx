// __tests__/fts-strategy-map.spec.tsx -- نقشۀ استراتژی FTS: درختِ چهار صفحه، چیدمانِ محاسبه‌شده و ریل
// سه چیز را می‌پاید که خواستۀ بازطراحی بود: (۱) parent/child هر Zone سطرهایِ خودِ
// چارت است، (۲) چیدمان محاسبه می‌شود و مختصِ دستی ندارد، (۳) پرست و جهتِ جریان فقط
// ریل را روشن می‌کنند و توپولوژی را نمی‌سازند.
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ObsidianStrategyGraph } from '../features/master/components/ObsidianStrategyGraph';
import {
  PRESET_ACTIVE,
  ZONES,
  activeIdsForPreset,
  ancestorsOf,
  buildFtsChartModel,
  getGraphLinks,
  railOrder,
  refEdges,
  zoneRoots,
  type FtsZone,
} from '../features/master/lib/ftsChartModel';
import { INDENT, LEAF_W, PAD_X, ZONE_W, layoutMap } from '../features/master/lib/ftsChartLayout';
import { FTS_DEFAULT_PARAMS, useStrategyParamsStore } from '../features/master/stores/strategyParamsStore';
import { useUiStore } from '../shared/stores/uiStore';

const model = buildFtsChartModel(FTS_DEFAULT_PARAMS);
const kids = (id: string) => (model.childrenOf.get(id) ?? []);

// پرس‌وجو از نقشه با همان نشانه‌هایی که خودِ کامپوننت می‌زند (data-node-id،
// data-zone-frame، data-rail-step، data-ref-edge) — بدونِ testidِ دوگانه.
const allRows = () => Array.from(document.querySelectorAll('[data-node-id]'));
const rowEl = (id: string) => document.querySelector(`[data-node-id="${id}"]`) as Element;
const idsOf = (els: Element[]) => els.map((e) => e.getAttribute('data-node-id') as string);
const railIds = () => idsOf(allRows().filter((e) => e.getAttribute('data-rail') === '1'));
const litIds = () => idsOf(allRows().filter((e) => e.getAttribute('data-lit') === '1'));

describe('درختِ چهار صفحۀ چاپی (مدلِ canonical)', () => {
  it('هیچ هسۀ پرکُنکشنی نیست؛ هر Zone ریشۀ خودش را دارد', () => {
    expect(model.byId.has('fts_core')).toBe(false);
    expect(model.roots).toEqual(zoneRoots());
    for (const n of model.nodes) {
      if (!n.parent) expect([ 'f_root', 't_root', 's_root', 'm_root' ]).toContain(n.id);
      else {
        const p = model.byId.get(n.parent);
        expect(p, 'parentِ گرهٔ «' + n.id + '» موجود است').toBeTruthy();
        // رابطۀ ساختاری فقط درونِ همان صفحۀ چاپی مجاز است
        expect(p?.zone, n.id + ' در همان Zone والد است').toBe(n.zone);
      }
    }
    for (const z of ZONES) expect(model.byId.get(model.roots[z.key])?.zone).toBe(z.key);
  });

  it('سطرهایِ خودِ چارت والد و فرزندند — نه رابطۀ حدسی', () => {
    // صفحۀ ۲: سیگنال خرید ⇒ فروش ⇒ حد ضرر؛ هفتگی صعودی ⇒ سه شاخۀ روزانه
    expect(kids('t_root')).toEqual(['t_buy', 't_sell', 't_stop']);
    expect(kids('tech_weekly_up')).toEqual(['t_daily_up', 't_daily_down', 't_daily_neutral']);
    expect(kids('t_daily_up')).toEqual(['setup_pullback', 'setup_jet']);
    expect(kids('t_daily_down')).toEqual(['setup_fib', 'setup_choch']);
    expect(kids('t_sell')).toEqual(['setup_double_bottom', 'setup_double_top', 'exit_third_peak', 'exit_rsi_div']);
    // صفحۀ ۱: پنج سطرِ شاخص + طبقۀ امتیاز که سطرِ جزوه نیست
    expect(kids('f_root')).toEqual([
      'crit_sales_growth', 'crit_3y_eps', 'crit_gross_margin', 'crit_ps_ratio', 'crit_pricing_regime', 'f_tiers',
    ]);
    expect(model.byId.get('f_tiers')?.origin).toBe('program');
    // صفحۀ ۳: سبک ⇒ نقدینگی ⇒ صنایع ⇒ حجم ⇒ الگوها ⇒ خشک کردن
    expect(kids('s_root')).toEqual([
      's_style', 's_liquidity', 's_industries', 's_volume', 's_patterns', 's_dry',
    ]);
    expect(kids('s_liquidity')).toEqual(['s_arena', 'tape_flow_charts', 'tape_smart_money']);
    expect(kids('s_volume_trend')).toEqual(['tape_volume_trend']);
    // صفحۀ ۴: مهندسی معکوس ⇒ مدیریت سرمایه ⇒ رصد ⇒ تناسب ⇒ استراتژی
    expect(kids('m_root')).toEqual(['m_reverse', 'm_money', 'm_monitor', 'm_fit', 'm_strategy']);
    expect(kids('m_reverse')).toEqual(['m_reverse_tape', 'm_reverse_tech', 'm_reverse_fund']);
    expect(kids('m_stop_kind')).toEqual(['stop_swing', 'stop_trend']);
    expect(kids('m_ladder')).toEqual(['tech_weekly_hourglass', 'stop_hourglass', 'exit_half']);
  });

  it('هسته‌ای که ده‌ها برگ از آن بیرون برود نداریم — بیشترینِ شاخه فهرستِ خودِ چارت است', () => {
    const fan = model.nodes.map((n) => kids(n.id).length);
    expect(Math.max(...fan)).toBeLessThanOrEqual(7);
    expect(kids('m_money')).toHaveLength(7);
    expect(model.nodes.filter((n) => kids(n.id).length >= 6).map((n) => n.id).sort())
      .toEqual(['f_root', 'm_money', 's_root']);
  });

  it('مفهومی که درِ چند صفحه تکرار شده گونۀ دوم نمی‌سازد؛ فقط «هم‌نام» است', () => {
    const ids = new Set(model.nodes.map((n) => n.id));
    expect(ids.size).toBe(model.nodes.length);
    // کف‌روبی/ساعت/حجمِ مشکوک همان سه گرهٔ صفحۀ ۳‌اند؛ صفحۀ ۴ با ref به آن‌ها می‌رود
    const tape = model.byId.get('m_reverse_tape');
    expect(tape?.refs).toEqual(['tape_volume', 'tape_clock', 'tape_floor_sweep']);
    expect(tape?.parent).toBe('m_reverse');
    // دو گره‌ای که برچسبِ صفحۀ خودشان درِ جدولِ پیشین دو صفحه می‌گفت، یک Zone دارند
    for (const id of ['setup_point_hunt', 'tech_weekly_hourglass', 'exit_third_peak', 'exit_rsi_div']) {
      expect(model.byId.get(id)?.zone).toBeTruthy();
    }
    const pairs = refEdges(model);
    expect(pairs.length).toBeGreaterThan(0);
    for (const r of pairs) expect(r.source === r.target).toBe(false);
  });
});

describe('چیدمانِ محاسبه‌شده (بی‌مختصِ دستی)', () => {
  const layout = layoutMap(model);

  it('چهار Zone در جایگاهِ ثابتِ راست‌به‌چپ نشسته‌اند و هم‌قدند', () => {
    expect(layout.zones.map((z) => z.key)).toEqual(['F', 'T', 'S', 'M']);
    expect(layout.zones[0].x).toBeGreaterThan(layout.zones[1].x);
    expect(layout.zones[3].x).toBeLessThan(layout.zones[2].x);
    for (const z of layout.zones) expect(z.w).toBe(ZONE_W);
    const heights = new Set(layout.zones.map((z) => z.h));
    expect(heights.size).toBe(1);
    // هیچ دو Zone روی هم نمی‌افتند
    for (let i = 0; i + 1 < layout.zones.length; i += 1) {
      expect(layout.zones[i].x).toBeGreaterThan(layout.zones[i + 1].x + layout.zones[i + 1].w - 1);
    }
    expect(layout.width).toBe(PAD_X * 2 + 4 * ZONE_W + 3 * 22);
  });

  it('سطرها درونِ ستونِ خودشان‌اند، هم‌پوشانی ندارند و تورفتگی = عمقِ درخت', () => {
    for (const z of layout.zones) {
      const box = z;
      const rows = layout.rows.filter((r) => r.zone === z.key);
      expect(rows.length).toBeGreaterThan(3);
      for (let i = 0; i < rows.length; i += 1) {
        const r = rows[i];
        expect(r.right, 'لبۀ راست درِ ستون').toBeLessThanOrEqual(box.x + box.w - PAD_X + 0.5);
        expect(r.x, 'لبۀ چپ درِ ستون').toBeGreaterThanOrEqual(box.x + PAD_X - 0.5);
        expect(r.x).toBeGreaterThanOrEqual(0);
        if (i > 0) expect(r.y, 'سطر بعدی پایین‌تر است').toBeGreaterThan(rows[i - 1].y);
        if (i > 0) expect(rows[i - 1].y + rows[i - 1].h).toBeLessThanOrEqual(r.y + 0.01);
      }
      // عمقِ هر سطر با تورفتگیِ راست‌به‌چپِ همان سطر می‌خواند
      for (const r of rows) {
        const node = model.byId.get(r.id);
        const d = ancestorsOf(model, r.id).length - 1;
        expect(r.depth, node?.label).toBe(d);
      }
    }
    // آرنجِ رابط از والد به فرزندِ همان Zone می‌رود و نه جای دیگر
    for (const l of layout.links) {
      const a = layout.rowById.get(l.source);
      const b = layout.rowById.get(l.target);
      expect(a, l.source + ' سطر دارد').toBeTruthy();
      expect(b, l.target + ' سطر دارد').toBeTruthy();
      expect(a?.zone).toBe(b?.zone);
      expect(b?.y).toBeGreaterThan(a?.y ?? -1);
    }
    // پهنای کارتِ برگ + تورفتگیِ بیشینه از ستون بیرون نمی‌زند
    const maxDepth = Math.max(...layout.rows.map((r) => r.depth));
    expect(LEAF_W + maxDepth * INDENT + PAD_X * 2).toBeLessThanOrEqual(ZONE_W);
  });

  it('جمع‌کردنِ شاخه فقط سطرهایِ زیرِ همان شاخه را کم می‌کند', () => {
    const open = layoutMap(model);
    const closed = layoutMap(model, new Set(['s_style']));
    const gone = open.rows.map((r) => r.id).filter((id) => !closed.rows.some((r) => r.id === id));
    expect(gone.sort()).toEqual(['s_style_swing', 's_style_trend'].sort());
    expect(closed.rows.some((r) => r.id === 's_style')).toBe(true);
    // بقیۀ ستون‌ها دست‌نخورده‌اند
    for (const z of ['F', 'T', 'M'] as FtsZone[]) {
      expect(closed.rows.filter((r) => r.zone === z).map((r) => r.id))
        .toEqual(open.rows.filter((r) => r.zone === z).map((r) => r.id));
    }
  });
});

describe('ریل: پرست و جهت، روشنگری رویِ نقشۀ ثابت', () => {
  beforeEach(() => {
    useStrategyParamsStore.getState().resetAll();
    useUiStore.getState().setTheme('dark');
  });

  it('جهتِ جریان توپولوژی را نمی‌سازد: همان یال‌ها، همان سطرهایِ درخت', () => {
    const rev = getGraphLinks('reverse').map((l) => [l.source, l.target].sort().join('|')).sort();
    const cls = getGraphLinks('classic').map((l) => [l.source, l.target].sort().join('|')).sort();
    expect(rev).toEqual(cls);
    expect(railOrder('reverse')).toEqual(['S', 'T', 'F', 'M']);
    expect(railOrder('classic')).toEqual(['F', 'T', 'S', 'M']);
    // سه وابستگیِ بین‌صفحه‌ای که خودِ چارت می‌گوید — نه بیشتر
    const cross = new Set(
      getGraphLinks('reverse')
        .filter((l) => {
          const a = model.byId.get(l.source)?.zone;
          const b = model.byId.get(l.target)?.zone;
          return a && b && a !== b;
        })
        .map((l) => [l.source, l.target].sort().join('|')),
    );
    expect(cross.size).toBe(3);
  });

  it('با سوییچِ پرست، گره‌ها جابه‌جا نمی‌شوند؛ فقط ریل عوض می‌کند', () => {
    const { rerender } = render(<ObsidianStrategyGraph selectedPreset="swing" />);
    const swingRows = idsOf(allRows());
    const swingRail = railIds();
    rerender(<ObsidianStrategyGraph selectedPreset="trend" />);
    const trendRows = idsOf(allRows());
    const trendRail = railIds();
    expect(trendRows).toEqual(swingRows);
    expect(trendRail).not.toEqual(swingRail);
    expect(trendRail).toContain('tape_floor_sweep');
    expect(trendRail).toContain('setup_point_hunt');
    expect(trendRail).toContain('stop_trend');
    // رأیِ مالک (حکمِ ۸): روندگیر هیچ گرهٔ «خروج»ی روشن ندارد
    expect(trendRail).not.toContain('exit_half');
    expect(trendRail.every((id) => ancestorsOf(model, id).every((a) => trendRail.includes(a)))).toBe(true);
  });

  it('ساعت شنی ستاپِ مستقل ندارد؛ همان اشباعِ هفتگی روشن می‌شود', () => {
    render(<ObsidianStrategyGraph selectedPreset="hourglass" />);
    const rail = railIds();
    expect(rail).toContain('tech_weekly_hourglass');
    expect(rail).toContain('stop_hourglass');
    for (const s of ['setup_jet', 'setup_pullback', 'setup_choch']) expect(rail).not.toContain(s);
  });

  it('حالتِ سفارشی همان گره‌هایی را روشن می‌کند که کاربر انتخاب کرده', () => {
    render(
      <ObsidianStrategyGraph
        selectedPreset="custom"
        activeCustomNodes={['fund_medium', 'tech_weekly_reject', 'tape_clock']}
      />,
    );
    const rail = railIds();
    expect(rail).toContain('tape_clock');
    expect(rail).toContain('fund_medium');
    expect(rail).not.toContain('tape_floor_sweep');
  });

  it('جست‌وجو کلِ مسیر را روشن می‌کند و بیرونِ مسیر خاموش', () => {
    render(<ObsidianStrategyGraph selectedPreset="swing" />);
    fireEvent.change(screen.getByPlaceholderText(/جستجو در قوانین و نودها/), { target: { value: 'کف‌روبی' } });
    const lit = litIds();
    expect(lit).toContain('tape_floor_sweep');
    expect(lit).toContain('s_patterns_trend');
    expect(lit).toContain('s_root');
    expect(lit).not.toContain('rule_rr');
  });

  it('هاور فقط همسایه و مسیرِ مرتبط را روشن می‌گذارد', () => {
    render(<ObsidianStrategyGraph selectedPreset="swing" />);
    const row = rowEl('stop_trend');
    fireEvent.pointerEnter(row);
    expect(row.getAttribute('data-lit')).toBe('1');
    expect(rowEl('m_stop_kind').getAttribute('data-lit')).toBe('1');
    expect(rowEl('rule_cap').getAttribute('data-lit')).toBe('0');
    fireEvent.pointerLeave(row);
  });

  it('فلشِ ریلِ بینِ Zone فقط رویِ گام‌هایِ روشن نفس می‌کشد', () => {
    render(<ObsidianStrategyGraph selectedPreset="trend" />);
    const steps = Array.from(document.querySelectorAll('[data-rail-step]'));
    expect(steps).toHaveLength(3);
    expect(steps.map((s) => s.getAttribute('data-lit'))).toEqual(['1', '1', '1']);
    // گامِ F➔M از سرِ نقشه برمی‌گردد (کمان) تا خطِ کجِ عبوری نسازد
    const arc = steps.filter((s) => s.getAttribute('data-rail-arc') === '1');
    expect(arc).toHaveLength(1);
  });

  it('پلاکِ نماد، وضعیتِ چهار فاز را رویِ Zoneهایِ خودش می‌نشاند', () => {
    render(
      <ObsidianStrategyGraph
        selectedPreset="trend"
        symbol="فولاد"
        symbolPhaseStatus={[
          { k: 'F', status: 'pass', label: 'بنیادی تایید' },
          { k: 'T', status: 'wait', label: 'در انتظار ستاپ' },
          { k: 'S', status: 'pass', label: 'الگوی ساعت' },
          { k: 'M', status: 'fail', label: 'وتوی سبد' },
        ]}
      />,
    );
    for (const [k, st] of [['F', 'pass'], ['T', 'wait'], ['S', 'pass'], ['M', 'fail']] as const) {
      expect(document.querySelector(`[data-zone-frame="${k}"]`)?.getAttribute('data-phase-status')).toBe(st);
    }
    expect(Number(document.querySelector('[data-zone-frame="T"]')?.getAttribute('data-lit-count'))).toBeGreaterThan(0);
  });

  it('خط‌چینِ هم‌نام فقط برایِ گرهٔ لنگه دیده می‌شود (بوم شلوغ نمی‌شود)', () => {
    render(<ObsidianStrategyGraph selectedPreset="swing" />);
    const refEls = () => Array.from(document.querySelectorAll('[data-ref-edge]'));
    const before = refEls().length;
    expect(before).toBeGreaterThan(0);
    expect(before).toBeLessThanOrEqual(allRows().filter((r) => r.getAttribute('data-node-kind') === 'leaf').length);
    fireEvent.click(rowEl('m_reverse_tape'));
    const after = refEls().map((el) => el.getAttribute('data-ref-edge'));
    expect(after.every((id) => id && id.includes('m_reverse_tape'))).toBe(true);
  });

  it('جدولِ پرست همان فهرستِ برنامه است و نقشه چیزی به آن کم یا زیاد نمی‌کند', () => {
    expect(PRESET_ACTIVE.swing).toContain('tape_clock');
    expect(PRESET_ACTIVE.trend).toEqual([
      'fund_super', 'fund_good', 'tech_weekly_up', 'setup_fib', 'setup_choch', 'setup_jet',
      'setup_point_hunt', 'tape_floor_sweep', 'stop_trend',
    ]);
    const on = activeIdsForPreset('trend', model);
    expect(on.has('m_stop_kind')).toBe(true);
    expect(on.has('t_buy')).toBe(true);
  });
});
