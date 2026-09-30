// تست سایدبار چپ (#48 نشانگر مرحلۀ تبِ فعال، #49 پنج مظنه در سایدبار)
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { SymbolInspector } from '@widgets/SymbolInspector';
import { INSPECTOR_STAGES, stageHref, stageIndexForPath } from '@widgets/inspectorStage';

vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('شبکه در تست خاموش است'))));

function renderAt(path: string, symbol = 'شپنا') {
  useSymbolStore.setState({ symbol });
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
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
