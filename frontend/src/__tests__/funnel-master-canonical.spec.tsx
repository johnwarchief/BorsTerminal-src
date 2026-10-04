// __tests__/funnel-master-canonical.spec.tsx — مسیرِ اصالت: قیف → MasterDossier → /api/fts
// ادعایی که قبل از ریلیز باید میخکوب شود: حکمی که Master نشان می‌دهد *دقیقاً*
// همان canonical FTS result است — نه قضاوتِ دوم، نه fallbackِ محلی. چهار حالتِ
// مالک + انتخابِ نماد از «تحویل‌شده‌ها» + بی‌نیازی از Signal Bus (قرارداد Round L).
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import {
  buildDossier,
  findCandidate,
  VERDICT_LABEL,
} from '@features/master/lib/masterDossier';
import { MasterDossierPanel } from '@features/master/ui/MasterDossier';
import type { Candidate, FunnelStageKey, StageStatus } from '@features/master/lib/ftsFunnel';
import type { FtsPlanFeed } from '@features/master/api/useFtsPlan';
import { useSignalStore } from '@shared/stores/signalStore';

const KEYS: FunnelStageKey[] = ['tape', 'technical', 'fundamental', 'handover'];

const st = (over: Partial<Record<FunnelStageKey, StageStatus>> = {}):
  Record<FunnelStageKey, StageStatus> => ({
    tape: 'pass', technical: 'pass', fundamental: 'pass', handover: 'pass', ...over,
  });

function candidate(status: Record<FunnelStageKey, StageStatus>, symbol = 'خودرو'): Candidate {
  const why = Object.fromEntries(KEYS.map((k) => [k, `دلیلِ ${k}`])) as Record<FunnelStageKey, string>;
  return {
    symbol, name: 'سایپا', sector: 'خودرو', status, why,
    score: 4, trendW: 'up', trendD: 'up', setups: 'جت',
    inds: [], patterns: [], techSource: 'live', kind: 'stock',
    row: { p_last: 131, percent_change: 0.8 } as Candidate['row'],
    screen: null, jetEvidence: null, assemblyVeto: false, assemblyWhy: '',
    portfolio: null, screenRank: 2,
  } as Candidate;
}

const feed = (over: { vetoed?: boolean; code?: string; text?: string; trigger?: unknown; decision?: string; desc?: string } = {}) =>
  ({
    status: 'success',
    analysis_basis: 'tsetmc-adjusted',
    fts: {
      status: {
        code: over.code ?? 'entry_trigger',
        text: over.text ?? 'جت: شکست مقاومت',
        trigger: 'trigger' in over ? over.trigger : { kind: 'jet', label: 'جت', price: 134, date: '1405-07-12', role: 'entry' },
        vetoed: over.vetoed ?? false,
      },
      trend: {
        D: { trend: 'up' },
        W: { trend: over.decision === 'REJECT' ? 'down' : 'up' },
        matrix: { decision: over.decision ?? 'PERMITTED', setup: 'JET_OR_PULLBACK_HOLD', desc: over.desc ?? 'روند هفتگی صعودی' },
      },
      jet: { active: true, resistance: 134, ceiling: 139, ath: false, close: 135, pct_above_res: 0.7 },
      exit_engine: { verdict: 'hold', l1: { hard_stop: 127, ma14: 130 } },
      hourglass: { active: false, action: 'NORMAL', ma52: 128, weekly_rsi5: 61 },
    },
  }) as unknown as FtsPlanFeed;

describe('مسیرِ اصالت قیف→مستر (بدونِ قاضیِ موازی)', () => {
  it('نمادِ «تحویل‌شده‌ها» از قیف، همان canonical را در مستر باز می‌کند: تأیید', () => {
    // همان چیزی که MasterPage می‌کند: candidate از فهرست‌هایِ قیف پیدا می‌شود،
    // نه از محاسبهٔ دوباره — پس هویتِ آبجکت هم باید یکی بماند.
    const tapeEntries = [candidate(st()), candidate(st({ fundamental: 'reject' }), 'فولاد')];
    const found = findCandidate([tapeEntries, []], 'خودرو');
    expect(found).toBe(tapeEntries[0]);
    const d = buildDossier(found, feed(), 'خودرو');
    expect(d.verdict).toBe('confirmed');
    // قرارداد Round L: متنِ نشان، عینِ متنِ موتور است اگر باشد؛ برچسبِ واژگان
    // (VERDICT_LABEL) فال‌بِ same-verdictِ خودِ مدل است — نه قاضیِ دوم.
    expect(d.verdictText).toBe('جت: شکست مقاومت');
    expect(VERDICT_LABEL[d.verdict]).toBe('تأیید شده');
    expect(d.inFunnel).toBe(true);
  });

  it('PERMITTED با تریگرِ فعال ⇒ تأیید؛ بی‌تریگر و تحویل‌نگه‌داشته ⇒ واچ‌لیست/در انتظار', () => {
    const withTrigger = buildDossier(candidate(st({ handover: 'pending' })), feed({ trigger: null }), 'خودرو');
    // سه دریِ بالا pass و تحویلِ نگه‌داشته ⇒ واچ‌لیست (قاعدۀ deriveVerdictِ Round L)
    expect(withTrigger.verdict).toBe('watch');
    const held = buildDossier(candidate(st()), feed(), 'خودرو');
    expect(held.verdict).toBe('confirmed');
    const upstreamWait = buildDossier(candidate(st({ fundamental: 'pending', handover: 'pending' })), feed({ trigger: null }), 'خودرو');
    expect(upstreamWait.verdict).toBe('wait');
  });

  it('REJECT ⇒ رد، و علتِ نشان همان دلیلِ درِ بسته است؛ descِ موتور کنارش عیناً می‌ماند', () => {
    const d = buildDossier(
      candidate(st({ technical: 'reject' })),
      feed({ decision: 'REJECT', vetoed: true, text: 'وتوی تایم هفتگی — فرصت ورود نمی‌دهد', desc: 'تایم هفتگی نزولی — وتوی کامل' }),
      'خودرو',
    );
    expect(d.verdict).toBe('reject');
    expect(VERDICT_LABEL[d.verdict]).toBe('رد شده');
    expect(d.flow.gated).toBe(true);
    expect(d.flow.reason).toBe('تایم هفتگی نزولی — وتوی کامل');
    expect(d.technical.matrixDesc).toBe('تایم هفتگی نزولی — وتوی کامل');
  });

  it('بی‌کاندید/خطای فید ⇒ «سنجیده نشد» — هرگز «رد» نیست و هیچ fallback محلی حکم نمی‌سازد', () => {
    const d = buildDossier(null, undefined, 'ناشناس');
    expect(d.verdict).toBe('insufficient');
    expect(d.verdictText).toBe(VERDICT_LABEL.insufficient);
    expect(d.inFunnel).toBe(false);
  });

  it('نمایشِ پنل بی‌هیچ سیگنالی در Signal Bus کامل است — رأی به باخِ سیگنال وابسته نیست', () => {
    // باخِ سیگنال عمداً خالی می‌ماند (حالتِ نخستِ برنامه در پنج ثانیه اول).
    expect(Object.keys(useSignalStore.getState().bus).length).toBe(0);
    const d = buildDossier(candidate(st()), feed(), 'خودرو');
    render(
      <MemoryRouter>
        <MasterDossierPanel dossier={d} />
      </MemoryRouter>,
    );
    // قرارداد Round L: نشان، متنِ عینیِ موتور را می‌برد؛ «تأیید شده» در t1
    // سنجیده شد. مهمِ این تست: پنل بی‌باخِ سیگنال کامل رسم می‌شود —
    // حکم از قیف+payload است، نه signalStore.
    expect(screen.getByTestId('dossier-verdict')).toHaveTextContent('جت: شکست مقاومت');
    expect(screen.getByText('روند هفتگی')).toBeInTheDocument();
    // پاراگرافِ «متنِ موتور» فقط وقتی نشان با آن فرق دارد دیده می‌شود؛ اینجا
    // نشان عینِ همان متن است ⇒ تکرار نمی‌شود و حکمِ دومی ساخته نمی‌شود.
    expect(screen.queryByTestId('dossier-engine-text')).toBeNull();
  });
});
