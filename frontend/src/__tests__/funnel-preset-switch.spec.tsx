// @ts-nocheck
/* P0 regression: تغییر Preset باید منبعِ معتبر (URL) را عوض کند تا جدول تازه شود.
   قبل ازِ اصلاح: دکمه فقط store را عوض می‌کرد و `useActiveFunnelPreset` رویِ
   `?preset=`ِ URL قفل می‌ماند ⇒ جدول با کلیک تغییر نمی‌کرد. */
import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@shared/api/http', () => ({
  http: vi.fn(async () => ({ status: 'no_data' })),
}));

import { FtsFunnelStages } from '@features/master/ui/FtsFunnelStages';
import { useActiveFunnelPreset } from '@features/master/lib/useActiveFunnelPreset';

function renderBar(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <FtsFunnelStages preset="trend" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('P0: preset switch moves the authoritative source', () => {
  it('clicking a different preset updates the active preset even when URL pins it', () => {
    renderBar('/master?preset=trend');
    // شروع: trend فعال است (از URL)
    expect(screen.getByTestId('funnel-mode-trend').getAttribute('aria-pressed')).toBe('true');
    // کلیک روی swing باید presetِ فعال را عوض کند
    fireEvent.click(screen.getByTestId('funnel-mode-swing'));
    expect(screen.getByTestId('funnel-mode-swing').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('funnel-mode-trend').getAttribute('aria-pressed')).toBe('false');
  });

  it('activePreset tracks the URL after the click (single source stays consistent)', () => {
    let seen: string | undefined;
    function Probe() {
      seen = useActiveFunnelPreset('trend');
      return null;
    }
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={['/master?preset=hourglass']}>
          <Probe />
          <FtsFunnelStages preset="trend" />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(seen).toBe('hourglass'); // URL برنده است
    fireEvent.click(screen.getByTestId('funnel-mode-swing'));
    expect(seen).toBe('swing'); // و کلیک، URL را جابه‌جا می‌کند
  });
});
