// تست سایدبار چپ (#48 نشانگر مرحلۀ تبِ فعال، #49 پنج مظنه در سایدبار،
// #67 «مرحلۀ خودِ نماد» — همان قیف، نه قاعدۀ دوم)
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import type { MarketRow } from '@shared/types/marketRow';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { SymbolInspector } from '@widgets/SymbolInspector';
import { INSPECTOR_STAGES, stageHref, stageIndexForPath } from '@widgets/inspectorStage';

vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('شبکه در تست خاموش است'))));

const board = (over: Partial<MarketRow>): MarketRow =>
  ({ symbol: 'شپنا', name: 'شبکه برق', p_last: 1000, p_closing: 990, ...over }) as unknown as MarketRow;

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
  /** ردیفی که هیچ فیلترِ دری روشن ندارد ⇒ درِ تابلو بسته */
  const seedRow = (row: MarketRow) => (qc: QueryClient) => {
    qc.setQueryData(['market-feed'], { data: [row] });
  };

  it('بی‌علامت ⇒ چراغِ تابلو قرمز و خطِ «ایستاده در تابلوخوانی»', () => {
    renderAt('/market', 'شپنا', seedRow(board({})));
    expect(screen.getByTestId('inspector-stage-tape')).toHaveAttribute('data-stage-state', 'blocked');
    expect(screen.getByTestId('inspector-stage-next').textContent).toContain('ایستاده در «تابلوخوانی»');
    // بالادستِ بسته: سه مرحلۀ بعدی رأی ندارند، پس «سنجیده نشده» جایش را می‌گیرد
    expect(screen.getByTestId('inspector-stage-technical')).toHaveAttribute('data-stage-state', 'unknown');
  });

  it('تابلو سبز + وتوی هفتگیِ اسکرینر ⇒ چراغِ تکنیکال قرمز و همان‌جا ایستاده', () => {
    renderAt('/technical/شپنا', 'شپنا', (qc) => {
      qc.setQueryData(['market-feed'], { data: [board({ f_susp: true })] });
      qc.setQueryData(['fts-screen', 120], {
        status: 'success',
        count: 1,
        data: [{ symbol: 'شپنا', name: 'شپنا', score: 3, weekly_veto: true, tech_matrix_decision: 'REJECT', tech_trend_w: 'down' }],
      });
    });
    expect(screen.getByTestId('inspector-stage-tape')).toHaveAttribute('data-stage-state', 'passed');
    expect(screen.getByTestId('inspector-stage-technical')).toHaveAttribute('data-stage-state', 'blocked');
    expect(screen.getByTestId('inspector-stage-next').textContent).toContain('ایستاده در «تکنیکال»');
    expect(INSPECTOR_STAGES.map((s) => s.key)).toEqual(['tape', 'technical', 'fundamental', 'handover']);
  });

  it('ردیفِ تابلو وجود ندارد ⇒ هیچ مرحله‌ای قرمز نمی‌شود (بی‌داده وتو نیست)', () => {
    renderAt('/market', 'شپنا', (qc) => qc.setQueryData(['market-feed'], { data: [board({ symbol: 'فولاد' })] }));
    for (const s of INSPECTOR_STAGES) {
      expect(screen.getByTestId(`inspector-stage-${s.key}`)).toHaveAttribute('data-stage-state', 'unknown');
    }
    expect(screen.getByTestId('inspector-stage-next').textContent).not.toContain('ایستاده');
  });
});
