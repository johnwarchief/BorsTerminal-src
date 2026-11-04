import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FTS_BASIC_DEFAULTS, useFtsConfig, useSaveFtsConfig } from '@features/fundamental/api/useFtsConfig';
import { FtsSettingsDrawer } from '@features/fundamental/ui/FtsSettingsDrawer';

vi.mock('@features/fundamental/api/useFtsConfig', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@features/fundamental/api/useFtsConfig')>();
  return { ...actual, useFtsConfig: vi.fn(), useSaveFtsConfig: vi.fn() };
});

const mockedCfg = vi.mocked(useFtsConfig);
const mockedSave = vi.mocked(useSaveFtsConfig);
const mutate = vi.fn();

beforeEach(() => {
  mutate.mockReset();
  mockedCfg.mockReturnValue({
    data: { status: 'success', config: { ...FTS_BASIC_DEFAULTS, growth_min: 40 } },
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useFtsConfig>);
  mockedSave.mockReturnValue({
    mutate,
    isPending: false,
    isSuccess: false,
    isError: false,
    data: undefined,
  } as unknown as ReturnType<typeof useSaveFtsConfig>);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('fts settings drawer', () => {
  it('saves a full payload and keeps hourglass keys', () => {
    render(<FtsSettingsDrawer open onClose={vi.fn()} />);
    fireEvent.change(screen.getByTestId('fts-growth-min'), { target: { value: '60' } });
    fireEvent.click(screen.getByTestId('fts-settings-save'));
    expect(mutate).toHaveBeenCalledTimes(1);
    const payload = mutate.mock.calls[0]![0];
    expect(payload.growth_min).toBe(60);
    expect(payload.hourglass_rsi_period).toBe(7);
    expect(payload.mandatory_sectors).toEqual(['خودرو', 'نیروگاه', 'لاستیک']);
  });

  it('shows server validation errors and no success message', () => {
    mockedSave.mockReturnValue({
      mutate,
      isPending: false,
      isSuccess: true,
      isError: false,
      data: { status: 'error', message: 'برخی مقادیر معتبر نیستند', errors: { growth_min: 'عدد معتبر نیست' } },
    } as unknown as ReturnType<typeof useSaveFtsConfig>);
    render(<FtsSettingsDrawer open onClose={vi.fn()} />);
    expect(screen.getByTestId('fts-settings-error').textContent).toContain('عدد معتبر نیست');
    expect(screen.queryByTestId('fts-settings-success')).toBeNull();
  });

  it('closes on Escape', () => {
    const onClose = vi.fn();
    render(<FtsSettingsDrawer open onClose={onClose} />);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('reset sends fundamental defaults and preserves hourglass', () => {
    render(<FtsSettingsDrawer open onClose={vi.fn()} />);
    fireEvent.click(screen.getByTestId('fts-settings-reset'));
    const payload = mutate.mock.calls[0]![0];
    expect(payload.growth_min).toBe(40);
    expect(payload.hourglass_rsi_period).toBe(7);
  });
});
