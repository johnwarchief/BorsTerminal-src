// __tests__/master-fts-details.spec.tsx — جزئیاتِ چهار صفحه (§۱–۵ Round M)
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MasterFtsDetails } from '@features/master/ui/MasterFtsDetails';
import { supportResistance } from '@features/master/api/useKeyLevels';
import { buildDossier, type MasterDossier } from '@features/master/lib/masterDossier';
import { IND_COLUMNS, type Candidate } from '@features/master/lib/ftsFunnel';

const t = (s: string) => new Date(s).toISOString().slice(0, 10);

const FEED = {
  status: 'success',
  analysis_basis: 'tsetmc-adjusted',
  fts: {
    status: { code: 'entry_trigger', text: 'جت: شکست مقاومت', trigger: { label: 'جت', price: 13740, date: '2026-10-04' }, vetoed: false },
    trend: { D: { trend: 'up' }, W: { trend: 'up' }, matrix: { decision: 'PERMITTED', setup: 'JET', desc: 'هفتگی صعودی + روزانه صعودی' } },
    jet: { active: true, resistance: 13720, close: 13740, ath: false },
    exit_engine: { verdict: 'hold', l1: { hard_stop: 11134, ma14: 12936, stop_basis: 'swing_low' } },
    hourglass: { active: null, action: 'UNKNOWN', ma52: null, weekly_rsi5: null, desc: 'سابقه هفتگی کمتر از حد نصاب' },
  },
} as never;

function cand(over: Partial<Candidate> = {}): Candidate {
  const status = { tape: 'pass', technical: 'pass', fundamental: 'pending', handover: 'pending' };
  return {
    symbol: 'شکاش', name: 'شکاش', sector: 'خودرو',
    status, why: { tape: 'نشانهٔ ساعت روشن', technical: 'هفتگی صعودی', fundamental: 'سه شاخص سنجیده نشده', handover: 'صبر' },
    score: 3, trendW: 'up', trendD: 'up', setups: 'جت', inds: ['pass', 'pending', 'unavailable', 'pass', 'reject'],
    patterns: ['ساعت'], techSource: 'live', kind: 'stock',
    row: { symbol: 'شکاش', p_last: 13700, percent_change: 1.1 } as Candidate['row'],
    screen: { score: 3, verdict: 'WATCH', eps_last: 812, gross_margin: null, sales_to_mcap: null,
              excluded: false, applicable: true, exclusion_reasons: null } as Candidate['screen'],
    jetEvidence: null, assemblyVeto: false, assemblyWhy: '', screenRank: 4, ...over,
  } as Candidate;
}

const dossierOf = (c: Candidate | null): MasterDossier => buildDossier(c, FEED as never, 'شکاش');

describe('supportResistance — فقط مقایسه، بی‌آستانه', () => {
  const levels = [
    { price: 12000, kind: 'low' }, { price: 13200, kind: 'low' },
    { price: 14000, kind: 'high' }, { price: 15500, kind: 'high' },
  ];
  it('نزدیک‌ترین کفِ زیرِ قیمت و نزدیک‌ترین سقفِ بالایِ قیمت', () => {
    expect(supportResistance(levels, 13500)).toEqual({ support: 13200, resistance: 14000 });
  });
  it('بی‌قیمت یا بی‌سطح ⇒ null، نه صفر', () => {
    expect(supportResistance(levels, null)).toEqual({ support: null, resistance: null });
    expect(supportResistance([], 13500)).toEqual({ support: null, resistance: null });
    expect(supportResistance(undefined, 13500).support).toBeNull();
  });
});

describe('MasterFtsDetails — S/T/F/Strategy', () => {
  const renderD = (c: Candidate | null) =>
    render(
      <MasterFtsDetails candidate={c} dossier={dossierOf(c)} badges={[]} support={13200} srResistance={14000} />,
    );

  it('هر پنج شاخصِ بنیادی با برچسبِ جزوه می‌آیند', () => {
    renderD(cand());
    for (const col of IND_COLUMNS) {
      expect(screen.getByText(col.label, { exact: false })).toBeInTheDocument();
    }
  });

  it('حکمِ مرحله با حکمِ شاخص قاطی نمی‌شود: درِ بنیادی ⏳ است و شاخصِ ردشده ❌ خودش', () => {
    renderD(cand());
    const f = screen.getByTestId('details-fundamental');
    const head = f.querySelector('summary')?.textContent ?? '';
    expect(head).toContain('⏳');            // خودِ درِ بنیادی pending است
    expect(head).not.toContain('❌');
    expect(f.textContent).toContain('❌');   // شاخص ۵ واقعاً رد شده — پنهانش نمی‌کنیم
    expect(f.textContent).toContain('○');    // شاخصِ سنجیده‌نشده ≠ رد
    expect(f.textContent).toContain('داده نیست');
  });

  it('تاریخِ تریگر جلالی نمایش داده می‌شود، نه میلادی', () => {
    renderD(cand());
    const tech = screen.getByTestId('details-technical').textContent ?? '';
    expect(tech).toContain('۱۴۰۵/۰۷/۱۲');
    expect(t).toBeDefined();
  });

  it('حمایت از key-levels می‌آید و با مقاومت قاطی نمی‌شود', () => {
    renderD(cand());
    const tech = screen.getByTestId('details-technical').textContent ?? '';
    expect(tech).toContain('حمایت');
    expect(tech).toContain('۱۳٬۲۰۰');
  });

  it('بی‌کاندید: چهار بخش رندر می‌شوند و هیچ‌کدام «رد» جا نمی‌زنند', () => {
    renderD(null);
    for (const id of ['details-selection', 'details-technical', 'details-fundamental', 'details-strategy']) {
      expect(screen.getByTestId(id)).toBeInTheDocument();
    }
    expect(screen.getByTestId('master-fts-details').textContent).toContain('○');
  });
});
