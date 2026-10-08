// تست سایدبار چپ (#48 نشانگر مرحلۀ تبِ فعال، #49 پنج مظنه در سایدبار،
// #67 «مرحلۀ خودِ نماد» — همان قیف، نه قاعدۀ دوم)
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { SymbolInspector } from '@widgets/SymbolInspector';
import { INSPECTOR_STAGES, stageHref, stageIndexForPath } from '@widgets/inspectorStage';
import { funnelQueryKey } from '@features/master/api/useFtsFunnel';
import type { ApiPayload } from '@features/master/lib/funnelView';

vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('شبکه در تست خاموش است'))));

function renderAt(path: string, symbol = 'شپنا', seed?: (qc: QueryClient) => void) {
  useSymbolStore.setState({ symbol });
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  seed?.(qc);
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <SymbolInspector />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('نقشۀ تب ⇒ مرحلۀ قیف', () => {
  it('هر تبِ قیف یک مرحلۀ own دارد و تبهایِ بیرونِ قیف null', () => {
    expect(stageIndexForPath('/market')).toBe(0);
    expect(stageIndexForPath('/technical/شپنا')).toBe(1);
    expect(stageIndexForPath('/fundamental/شپنا')).toBe(2);
    expect(stageIndexForPath('/master/شپنا')).toBe(3);
    expect(stageIndexForPath('/portfolio')).toBe(INSPECTOR_STAGES.length - 1);
    expect(stageIndexForPath('/settings')).toBeNull();
  });

  it('تابلوخوانی بی‌نماد است و سه مرحلۀ بعدی نماد را در مسیر می‌برند', () => {
    expect(stageHref(0, 'شپنا')).toBe('/market');
    expect(stageHref(1, 'شپنا')).toBe('/technical/%D8%B4%D9%BE%D9%86%D8%A7');
    expect(stageHref(1, '')).toBe('/technical');
  });
});

describe('نشانگر مرحله در سایدبار چپ', () => {
  it('در تب تابلوخوانی: فعلی=تابلوخوانی، بعدی=تکنیکال', () => {
    renderAt('/market');
    const strip = screen.getByTestId('inspector-stage');
    expect(strip).toBeInTheDocument();
    expect(screen.getByTestId('inspector-stage-tape')).toHaveAttribute('aria-current', 'step');
    expect(screen.getByTestId('inspector-stage-handover')).not.toHaveAttribute('aria-current');
    expect(strip.textContent).toContain('مرحلۀ فعلی: تابلوخوانی · بعدی: تکنیکال');
  });

  it('در پایۀ قیف پیامِ «پایِ قیف» می‌آید و هر سه مرحلۀ قبل گذشته‌اند', () => {
    renderAt('/master/شپنا');
    expect(screen.getByTestId('inspector-stage-handover')).toHaveAttribute('aria-current', 'step');
    expect(screen.getByTestId('inspector-stage-next').textContent).toContain('پایِ قیف');
  });

  it('در تب بیرونِ قیف نشانگر مرحله نمی‌آید (چیزی را حدس نمی‌زند)', () => {
    renderAt('/settings');
    expect(screen.queryByTestId('inspector-stage')).not.toBeInTheDocument();
  });

  it('پنج مظنه در سایدبار چپ نشسته است', () => {
    renderAt('/market');
    expect(screen.getByTestId('sidebar-orderbook')).toBeInTheDocument();
  });
});

describe('جایِ خودِ نماد در قیف (#67)', () => {
  // سایدبار دیگر قواعدِ قیف را رویِ تک‌ناماد اجرا نمی‌کند؛ همان پاسخِ
  // /api/funnel را می‌خواند که جدول می‌خواند. پس seed هم پاسخِ قیف است،
  // نه ردیفِ خامِ تابلو + اسکرینر (آن دو ورودیِ داورِ دوم بودند).
  const seedFunnel = (payload: ApiPayload) => (qc: QueryClient) => {
    qc.setQueryData(
      funnelQueryKey({ preset: 'custom', chain: [], fundMode: 'standard', exceptions: {} }),
      payload,
    );
  };
  const row = (over: Record<string, unknown>) => ({
    symbol: 'شپنا', name: 'شبکه برق', sector: 'برق', status: {}, why: {}, ...over,
  });
  const payload = (entries: Record<string, unknown[]>) => ({
    status: 'success', engine_version: '1', ruleset_version: 'x', as_of: Math.floor(Date.now() / 1000),
    preset: 'custom', chain: [], fund_mode: 'standard',
    universe: { board: 1, screened: 1, joined: 1 },
    stages: {}, entries, timeline: {}, handover: [],
  } as unknown as ApiPayload);

  it('بی‌علامت ⇒ چراغِ تابلو قرمز و خطِ «ایستاده در تابلوخوانی»', () => {
    renderAt('/market', 'شپنا', seedFunnel(payload({
      tape: [row({ status: { tape: 'reject' },
                   why: { tape: [{ code: 'TAPE_F_SUSP_NO_MATCH', text: 'حجم مشکوک — نشانه نیست' }] } })],
    })));
    expect(screen.getByTestId('inspector-stage-tape')).toHaveAttribute('data-stage-state', 'blocked');
    expect(screen.getByTestId('inspector-stage-next').textContent).toContain('ایستاده در «تابلوخوانی»');
    // بالادستِ بسته: سه مرحلۀ بعدی رأی ندارند، پس «سنجیده نشده» جایش را می‌گیرد
    expect(screen.getByTestId('inspector-stage-technical')).toHaveAttribute('data-stage-state', 'unknown');
  });

  it('تابلو سبز + وتوی هفتگی ⇒ چراغِ تکنیکال قرمز و همان‌جا ایستاده', () => {
    renderAt('/technical/شپنا', 'شپنا', seedFunnel(payload({
      tape: [row({ status: { tape: 'pass' } })],
      technical: [row({ status: { tape: 'pass', technical: 'reject' }, weekly: 'down',
                        why: { technical: [{ code: 'WEEKLY_TREND_DOWN', text: 'روند هفتگی نزولی — وتوی قطعی' }] } })],
    })));
    expect(screen.getByTestId('inspector-stage-tape')).toHaveAttribute('data-stage-state', 'passed');
    expect(screen.getByTestId('inspector-stage-technical')).toHaveAttribute('data-stage-state', 'blocked');
    expect(screen.getByTestId('inspector-stage-next').textContent).toContain('ایستاده در «تکنیکال»');
    expect(INSPECTOR_STAGES.map((s) => s.key)).toEqual(['tape', 'technical', 'fundamental', 'handover']);
  });

  it('نماد در پاسخِ قیف نیست ⇒ هیچ مرحله‌ای قرمز نمی‌شود (بی‌داده وتو نیست)', () => {
    renderAt('/market', 'شپنا', seedFunnel(payload({
      tape: [row({ symbol: 'فولاد', status: { tape: 'pass' } })],
    })));
    for (const s of INSPECTOR_STAGES) {
      expect(screen.getByTestId(`inspector-stage-${s.key}`)).toHaveAttribute('data-stage-state', 'unknown');
    }
    expect(screen.getByTestId('inspector-stage-next').textContent).not.toContain('ایستاده');
  });
});
