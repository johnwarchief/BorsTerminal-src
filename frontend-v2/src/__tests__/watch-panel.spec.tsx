import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { MarketRow } from '@shared/types/market';
import { WatchPanel } from '@features/market/panels/WatchPanel';

vi.mock('@features/market/components/SuspiciousPanel', () => ({
  SuspiciousPanel: ({ onSelect, sections }: { onSelect: (id: string) => void; sections: string[] }) => (
    <button type="button" data-testid="susp-stub" onClick={() => onSelect('10')}>{sections.join(',')}</button>
  ),
}));
vi.mock('@features/market/components/IndustryScreener', () => ({
  IndustryScreener: ({ onPick }: { onPick: (sector: string) => void }) => (
    <button type="button" data-testid="industry-stub" onClick={() => onPick('فلزات')}>صنایع</button>
  ),
}));

const rows = [{ symbol: 'الف', ins_code: '10' }] as MarketRow[];
const filterConfig = {} as never;

afterEach(cleanup);

describe('WatchPanel', () => {
  it('shows the global scope label', () => {
    render(<WatchPanel rows={rows} filterConfig={filterConfig} onSelect={() => {}} />);
    expect(screen.getByTestId('watch-scope-label').textContent).toContain('کل تابلو');
  });

  it('switches the three tabs', () => {
    render(<WatchPanel rows={rows} filterConfig={filterConfig} onSelect={() => {}} />);
    expect(screen.getByTestId('susp-stub').textContent).toBe('clock');
    fireEvent.click(screen.getByTestId('watch-tab-susp'));
    expect(screen.getByTestId('susp-stub').textContent).toBe('susp,roobi');
    fireEvent.click(screen.getByTestId('watch-tab-industries'));
    expect(screen.getByTestId('industry-stub')).toBeTruthy();
  });

  it('reports the selected ins_code without navigating', () => {
    const onSelect = vi.fn();
    render(<WatchPanel rows={rows} filterConfig={filterConfig} onSelect={onSelect} />);
    fireEvent.click(screen.getByTestId('susp-stub'));
    expect(onSelect).toHaveBeenCalledWith('10');
  });

  it('passes the sector pick upward', () => {
    const onPickSector = vi.fn();
    render(<WatchPanel rows={rows} filterConfig={filterConfig} onSelect={() => {}} onPickSector={onPickSector} />);
    fireEvent.click(screen.getByTestId('watch-tab-industries'));
    fireEvent.click(screen.getByTestId('industry-stub'));
    expect(onPickSector).toHaveBeenCalledWith('فلزات');
  });
});
