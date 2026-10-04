// __tests__/master-dossier.spec.tsx — برآیندِ تک‌ناماد (Round L)
// دو چیز سنجیده می‌شود: (۱) ترجمه، داوری نیست — هرچه در payload هست همان می‌آید
// و چیزی که نیست ساخته نمی‌شود؛ (۲) گیتِ هفتگی در خلاصه هم همان گیت است و روزانه
// جایگزینِ آن نمایش داده نمی‌شود. کنترلِ منفی هم دارد تا سنجش‌ها بی‌محتوا سبز نشوند.
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import {
  buildDossier,
  deriveVerdict,
  findCandidate,
  type DossierVerdict,
} from '@features/master/lib/masterDossier';
import { MasterDossierPanel } from '@features/master/ui/MasterDossier';
import type { Candidate, FunnelStageKey, StageStatus } from '@features/master/lib/ftsFunnel';
import type { FtsPlanFeed } from '@features/master/api/useFtsPlan';

const KEYS: FunnelStageKey[] = ['tape', 'technical', 'fundamental', 'handover'];

const st = (over: Partial<Record<FunnelStageKey, StageStatus>> = {}):
  Record<FunnelStageKey, StageStatus> => ({
    tape: 'pass', technical: 'pass', fundamental: 'pass', handover: 'pass', ...over,
  });

function candidate(over: Partial<Candidate> = {}): Candidate {
  const status = (over.status ?? st()) as Record<FunnelStageKey, StageStatus>;
  const why = Object.fromEntries(KEYS.map((k) => [k, `دلیلِ ${k}`])) as Record<FunnelStageKey, string>;
  return {
    symbol: 'فولاد', name: 'فولاد مبارکه', sector: 'فلزات',
    status, why, score: 4, trendW: 'up', trendD: 'up', setups: 'جت',
    inds: [], patterns: [], techSource: 'live', kind: 'stock',
    row: { p_last: 3750, percent_change: 1.2 } as Candidate['row'],
    screen: null, jetEvidence: null, assemblyVeto: false, assemblyWhy: '',
    portfolio: null, screenRank: 1, ...over,
  } as Candidate;
}

const FEED = {
  status: 'success',
  analysis_basis: 'tsetmc-adjusted',
  fts: {
    status: {
      code: 'weekly_veto',
      text: 'وتوی تایم هفتگی — فرصت ورود نمی‌دهد',
      trigger: { kind: 'jet', label: 'جت', price: 4210, date: '1405-07-12', role: 'entry' },
      vetoed: true,
    },
    trend: {
      D: { trend: 'up' }, W: { trend: 'down' },
      matrix: { decision: 'REJECT', setup: 'NONE', desc: 'تایم هفتگی نزولی — وتوی کامل' },
    },
    jet: { active: true, resistance: 4210, ceiling: 4500, ath: false, close: 4213, pct_above_res: 0.7 },
    exit_engine: { verdict: 'hold', l1: { hard_stop: 3980, ma14: 4050 } },
    hourglass: { active: false, action: 'NORMAL', ma52: 4400, weekly_rsi5: 58.2 },
  },
} as unknown as FtsPlanFeed;

const EMPTY_FEED = { status: 'success' } as unknown as FtsPlanFeed;

describe('deriveVerdict — واژگانِ خودِ مدلِ قیف', () => {
  it('همۀ درها باز + تحویل باز ⇒ تأیید', () => {
    expect(deriveVerdict(st())).toEqual({ verdict: 'confirmed', stage: 'handover' });
  });

  it('اولین دربند حکم را تعیین می‌کند، نه میانگینِ درها', () => {
    expect(deriveVerdict(st({ tape: 'reject', handover: 'pass' })).verdict).toBe('reject');
    expect(deriveVerdict(st({ tape: 'reject' })).stage).toBe('tape');
    expect(deriveVerdict(st({ technical: 'reject' })).stage).toBe('technical');
  });

  it('«سنجیده نشد» هرگز رد نیست', () => {
    const v = deriveVerdict(st({ fundamental: 'unavailable', handover: 'unavailable' }));
    expect(v.verdict).toBe('insufficient');
    const p = deriveVerdict(st({ fundamental: 'pending', handover: 'pending' }));
    expect(p.verdict).toBe('wait');
    expect((['reject'] as DossierVerdict[]).includes(v.verdict)).toBe(false);
  });

  it('کنترلِ منفی: یک «reject» مخفی در تحویل، حکم را از تأیید به رد می‌برد', () => {
    expect(deriveVerdict(st({ handover: 'reject' })).verdict).toBe('reject');
  });
});

describe('buildDossier — ترجمه، نه داوری', () => {
  it('متنِ موتور دست‌نخورده می‌ماند و عددِ سطوح از همان payload است', () => {
    const d = buildDossier(candidate(), FEED, 'فولاد');
    expect(d.technical.engineText).toBe('وتوی تایم هفتگی — فرصت ورود نمی‌دهد');
    expect(d.levels.resistance).toBe(4210);
    expect(d.levels.hardStop).toBe(3980);
    expect(d.hourglass.ma52).toBe(4400);
    expect(d.hourglass.rsi5).toBe(58.2);
    expect(d.technical.basis).toBe('tsetmc-adjusted');
  });

  it('گیتِ هفتگی بسته ⇒ روزانه به‌عنوان جایگزینِ وتو نمی‌آید', () => {
    const d = buildDossier(candidate({ trendW: 'down', trendD: 'up' }), FEED, 'فولاد');
    expect(d.flow.gated).toBe(true);
    expect(d.flow.weekly).not.toBe(d.flow.daily);
    expect(d.flow.daily).toBe('—');
    expect(d.flow.reason).toContain('هفتگی');
    expect(d.stages.find(s => s.key === 'technical')?.status).toBe('pass');
  });

  it('کنترلِ منفی: همان کاندید با ماتریسِ PERMITTED گیت‌شده نیست و روزانه خوانده می‌شود', () => {
    const ok = JSON.parse(JSON.stringify(FEED));
    ok.fts.status = { code: 'entry_trigger', text: 'جت: شکست مقاومت', trigger: null, vetoed: false };
    ok.fts.trend.matrix = { decision: 'PERMITTED', setup: 'JET_OR_PULLBACK_HOLD', desc: 'هفتگی صعودی' };
    const d = buildDossier(candidate({ trendW: 'up' }), ok as FtsPlanFeed, 'فولاد');
    expect(d.flow.gated).toBe(false);
    expect(d.flow.daily).not.toBe('—');
    expect(d.technical.code).toBe('entry_trigger');
  });

  it('بی‌payload و بی‌کاندید: نه حکمِ جعلی، نه ستاپِ جعلی، نه رد', () => {
    const d = buildDossier(null, EMPTY_FEED, 'نمادِ_بی‌داده');
    expect(d.inFunnel).toBe(false);
    expect(d.verdict).toBe('insufficient');
    expect(d.flow.setup).toBeNull();
    expect(d.technical.engineText).toBeNull();
    expect(d.levels.hardStop).toBeNull();
    expect(d.stages.every(s => s.status === 'unavailable' || s.status === 'reject')).toBe(true);
  });

  it('جزئیاتِ تکنیکال: متن‌هایِ موتور عین‌اند؛ کدهایِ انگلیسیِ خروج به واژگانِ مالک برگردانده می‌شوند', () => {
    const d = buildDossier(candidate(), FEED, 'فولاد');
    expect(d.technical.matrixDesc).toContain('هفتگی نزولی');
    expect(d.technical.exitVerdict).toBe('نگهداری');
    expect(d.technical.jetAth).toBe(false);
    expect(d.levels.ceiling).toBe(4500);
    expect(d.hourglass.desc ?? '—').not.toBe('فعال');
  });

  it('بی‌کاندید و بی‌گیت: «تعیین‌کننده» ادعا نمی‌شود؛ با گیت، مرحلهٔ تکنیکال است', () => {
    const open = JSON.parse(JSON.stringify(FEED));
    open.fts.status.vetoed = false;
    open.fts.trend.matrix = { decision: 'PERMITTED', setup: 'JET_OR_PULLBACK_HOLD', desc: '' };
    expect(buildDossier(null, open as FtsPlanFeed, 'خ').verdictStage).toBeNull();
    expect(buildDossier(null, FEED, 'خ').verdictStage).toBe('technical');
    expect(buildDossier(candidate(), FEED, 'خ').verdictStage).not.toBeNull();
  });

  it('ساعتِ شنیِ سنجیده‌نشده «غیرفعال» خوانده نمی‌شود', () => {
    const noHg = JSON.parse(JSON.stringify(FEED));
    noHg.fts.hourglass = { active: null, action: 'UNKNOWN', ma52: null, weekly_rsi5: null };
    const d = buildDossier(candidate(), noHg as FtsPlanFeed, 'فولاد');
    expect(d.hourglass.active).toBeNull();
  });
});

describe('findCandidate — یک منبع، همان آبجکت', () => {
  const c = candidate();
  it('کاندید را از فهرستِ قیف برمی‌گرداند، نه نسخه‌ای تازه', () => {
    expect(findCandidate([[], [c]], 'فولاد')).toBe(c);
  });
  it('نیابد ⇒ null (نه کاندیدِ ساختگی)', () => {
    expect(findCandidate([[c]], 'خودرو')).toBeNull();
  });
});

describe('MasterDossierPanel — پنج ثانیه اول', () => {
  const renderD = (d: ReturnType<typeof buildDossier>) =>
    render(
      <MemoryRouter>
        <MasterDossierPanel dossier={d} />
      </MemoryRouter>,
    );

  it('حکم، علت، جریانِ هفتگی و چهار در روی صفحه‌اند', () => {
    renderD(buildDossier(candidate(), FEED, 'فولاد'));
    expect(screen.getByTestId('dossier-verdict')).toBeInTheDocument();
    expect(screen.getByTestId('dossier-flow-gated')).toBeInTheDocument();
    expect(screen.getAllByTestId(/^dossier-stage-/)).toHaveLength(4);
    expect(screen.getByText('رد')).toBeInTheDocument();
    expect(screen.queryByText('روند روزانه')).not.toBeInTheDocument();
  });

  it('کنترلِ منفی: در حالتِ بازبودنِ گیت، روند روزانه نمایش داده می‌شود و ردِ دروازۀ تکنیکال نه', () => {
    const ok = JSON.parse(JSON.stringify(FEED));
    ok.fts.status = { code: 'entry_trigger', text: 'جت: شکست مقاومت', trigger: null, vetoed: false };
    ok.fts.trend.matrix = { decision: 'PERMITTED', setup: 'JET_OR_PULLBACK_HOLD', desc: '' };
    renderD(buildDossier(candidate({ trendW: 'up', trendD: 'up',
      status: st({ technical: 'pass' }) }), ok as FtsPlanFeed, 'فولاد'));
    expect(screen.getByText('روند روزانه')).toBeInTheDocument();
    expect(screen.queryByTestId('dossier-flow-gated')).not.toBeInTheDocument();
  });

  it('لینکِ نمودار همان نماد را باز می‌کند', () => {
    renderD(buildDossier(candidate(), FEED, 'فولاد'));
    const a = screen.getByTestId('dossier-open-chart');
    expect(a.getAttribute('href')).toContain('/technical/');
    expect(a.getAttribute('href')).toContain(encodeURIComponent('فولاد'));
  });
});
