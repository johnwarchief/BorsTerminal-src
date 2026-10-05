// __tests__/inspector-regulatory.spec.tsx -- وضعیتِ ناظر درِ Inspector
// چهار حالت باید از هم جدا بمانند (دورِ مصرف‌کننده، بخشِ Inspector):
//   رکوردِ توقف / رکوردِ نظارت / فقط عنوانِ وضعیت / هیچ رکوردی ثبت‌نشده
// و «ردیف نمی‌رسد» با «رکورد نیست» یکی نیست. هیچ‌کدام رأیِ تازه‌ای نمی‌سازند و
// هیچ درخواستِ تازه‌ای نمی‌زنند — همه از همان ردیفِ تابلو خوانده می‌شود.
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import type { MarketRow } from '@shared/types/marketRow';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { RegulatoryState } from '@features/market/components/RegulatoryState';
import { SymbolInspector } from '@widgets/SymbolInspector';

const fetchMock = vi.fn(() => Promise.reject(new Error('شبکه در تست خاموش است')));
vi.stubGlobal('fetch', fetchMock);

const row = (over: Partial<MarketRow>): MarketRow =>
  ({ symbol: 'شپنا', name: 'شبکه برق', p_last: 1000, ...over }) as unknown as MarketRow;

const state = () => screen.getByTestId('inspector-regulatory').getAttribute('data-regulatory-state');

describe('RegulatoryState', () => {
  it('متوقف: عنوانِ مبدأ + تاریخِ آغاز + علت‌ها درِ جزئیات', () => {
    render(<RegulatoryState row={row({
      stop_state: 'مشمول فرایند تعلیق',
      stop_since: '1405-07-13',
      stop_reasons: 'عدم ارائه صورتهای مالی\nعدم رعایت الزامات پذیرش',
      st_code: 'IS', st_title: 'ممنوع-متوقف', st_d: 20261005, st_h: 175816,
      ctv_kind: 'native',
    })} />);
    expect(state()).toBe('stopped');
    expect(screen.getByTestId('inspector-regulatory-head').textContent).toContain('متوقف — مشمول فرایند تعلیق');
    expect(screen.getByText('جزئیات')).toBeInTheDocument();
    expect(screen.getAllByText(/عدم ارائه صورتهای مالی/).length).toBeGreaterThan(0);
    // مبدأِ ریالی هم فقط درِ بازشو است، نه بجِ دائمی
    expect(screen.getAllByText(/از مبدأ \(TSETMC\)/).length).toBeGreaterThan(0);
  });

  it('نظارت بی‌توقف: «زیرِ نظرِ سازمان» و تعدادِ علت‌ها', () => {
    render(<RegulatoryState row={row({
      sup_flag: 1, sup_reason_count: 2,
      sup_reasons: 'عدم رعایت الزامات افشا\nعدم ارسال صورتجلسه',
    })} />);
    expect(state()).toBe('supervised');
    expect(screen.getByTestId('inspector-regulatory-head').textContent).toContain('زیرِ نظرِ سازمان');
    expect(screen.getByTestId('inspector-regulatory-head').textContent).toContain('۲ علتِ نظارت');
  });

  it('فقط عنوانِ وضعیت: همان عنوانِ مبدأ، نه «متوقف» و نه «سالم»', () => {
    render(<RegulatoryState row={row({ st_code: 'I', st_title: 'ممنوع', st_d: 20261003, st_h: 120000 })} />);
    expect(state()).toBe('state');
    expect(screen.getByTestId('inspector-regulatory-head').textContent).toContain('ممنوع');
  });

  it('هیچ رکوردی ⇒ «موردی ثبت نشده» — و این با «سالم» یکی نیست', () => {
    render(<RegulatoryState row={row({ ctv_kind: 'reconstructed' })} />);
    expect(state()).toBe('none');
    expect(screen.getByTestId('inspector-regulatory').textContent).toContain('موردی ثبت نشده');
    expect(screen.getByTestId('inspector-regulatory').textContent).not.toContain('متوقف');
  });

  it('ردیفِ تابلو نمی‌رسد ⇒ «اطلاعات در دسترس نیست» (با «رکورد نیست» یکی نیست)', () => {
    render(<RegulatoryState row={null} />);
    expect(state()).toBe('unavailable');
    expect(screen.getByTestId('inspector-regulatory').textContent).toContain('اطلاعات در دسترس نیست');
  });

  it('بی‌درخواستِ تازه (همان ردیفِ تابلو، نه اندپوینتِ دوم)', () => {
    fetchMock.mockClear();
    render(<RegulatoryState row={row({ stop_state: 'تعلیق شده' })} />);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe('نصبِ وضعیتِ ناظر درِ Inspector', () => {
  it('با ردیفِ متوقف، همین پنل درِ سایدبار می‌نشیند', () => {
    useSymbolStore.setState({ symbol: 'شپنا' });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    qc.setQueryData(['market-feed'], {
      data: [row({ stop_state: 'تعلیق شده', stop_since: '1405-07-11', st_title: 'ممنوع-متوقف' })],
    });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={['/market']}>
          <SymbolInspector />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByTestId('inspector-regulatory')).toHaveAttribute('data-regulatory-state', 'stopped');
  });
});
