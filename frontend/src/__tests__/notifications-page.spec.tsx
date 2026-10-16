// __tests__/notifications-page.spec.tsx — بند ۶: مرکزِ اعلان درِ رابط
// چهار چیز باید جدا بماند: منبعِ سالم با شمارش، منبعِ خالی («خبری نیست») با
// منبعِ نرسیده («نرسیده»), ادغامِ تکراری که شمرده می‌شود، و خوانده‌شده که درِ
// همین دستگاه می‌ماند. هیچ تیترِ ساختگی درِ این آزمون سرو نمی‌شود: همه از
// پاسخِ ماکِ خودِ `/api/notifications/feed` می‌آیند.
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import NotificationsPage from '@features/market/routes/NotificationsPage';
import { useNoticePrefsStore } from '@features/market/stores/noticePrefsStore';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

const json = (body: unknown) =>
  ({ ok: true, status: 200, json: async () => body }) as unknown as Response;

const ITEMS = [
  { id: 1, symbol: 'شپنا', company: 'پالایش نفت اصفهان', title: 'اطلاعات و صورت‌های مالی سالانه',
    kind: 'statements', level: 'high', letter_code: 'ن-۱۰',
    reason: 'صورتهایِ مالیِ دوره (ورودیِ EPS/حاشیه/رشدِ پنج‌شاخصه)',
    publish_date: '۱۴۰۵-۰۷-۰۹ ۱۰:۰۰:۰۰', sent_date: null, received_at: '2026-10-09 10:02:00',
    url: 'https://codal.ir/Reports/Decision.aspx?hs=1', source: 'codal', occurrences: 1 },
  { id: 2, symbol: 'فولاد', company: 'فولاد مبارکه', title: 'گزارش فعالیت ماهانه دوره ۱ ماهه',
    kind: 'monthly', level: 'medium', reason: 'مبنایِ رشدِ فروش', letter_code: 'ن-۳۰',
    publish_date: '۱۴۰-۰۷-۰۸ ۱۰:۰۰:۰۰', sent_date: null, received_at: '2026-10-08 10:02:00',
    url: 'https://codal.ir/Reports/Decision.aspx?hs=2', source: 'codal', occurrences: 3 },
];

function mockFeed(over: Record<string, unknown> = {}, sources: unknown = {
  status: 'ok', note: 'تک‌منبع: کدال', sources: [{ source: 'codal', label: 'کدال (سازمانِ بورس)',
    rows: 36350, newest_publish: '۱۴۵-۰۷-۰۹ ۱۰:۰۰:۰۰', last_fetch: '2026-10-10 02:00:00', state: 'ok' }],
}) {
  fetchMock.mockImplementation((url: string) => {
    if (String(url).includes('/sources')) return Promise.resolve(json(sources));
    return Promise.resolve(json({ status: 'ok', source: 'codal', count: ITEMS.length,
                                  scanned: 600, merged_duplicates: 4, items: ITEMS, ...over }));
  });
}

const page = () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={qc}>
        <NotificationsPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
};

beforeEach(() => {
  fetchMock.mockReset();
  localStorage.clear();
  useNoticePrefsStore.setState({ read: [], levels: [], kinds: [], native: false });
});

describe('مرکزِ اعلان', () => {
  it('نوارِ منبع: تعدادِ ردیف و تازه‌ترینِ انتشار/واکشی از خودِ پاسخ', async () => {
    mockFeed();
    page();
    await waitFor(() => expect(screen.getAllByTestId('notice-row').length).toBe(2));
    const strip = screen.getByTestId('notice-source-fresh').textContent ?? '';
    expect(strip).toContain('۳۶۳۵۰ اطلاعیه');
    expect(screen.getByTestId('notice-sources').getAttribute('data-state')).toBe('ok');
  });

  it('هر ردیف لینکِ اصلیِ کدال، زمانِ انتشار و زمانِ دریافتِ جدا دارد', async () => {
    mockFeed();
    page();
    await waitFor(() => expect(screen.getAllByTestId('notice-row').length).toBe(2));
    const a = screen.getAllByTestId('notice-open')[0] as HTMLAnchorElement;
    expect(a.href).toContain('codal.ir');
    expect(a.target).toBe('_blank');
    expect(screen.getAllByTestId('notice-row')[0].textContent).toContain('دریافتِ برنامه: 2026-10-09');
  });

  it('تکراری ادغام می‌شود و «چند بار آمد» رویِ ردیف است (حذفِ بی‌صدا نه)', async () => {
    mockFeed();
    page();
    await waitFor(() => expect(screen.getAllByTestId('notice-row').length).toBe(2));
    expect(screen.getByTestId('notice-occurrences').textContent).toContain('+۲');
    expect(screen.getByTestId('notice-note').textContent).toContain('ادغام شد');
  });

  it('دلیلِ اهمیت درِ همان برچسب است و سطحِ بی‌طبقه با پایین یکی نیست', async () => {
    mockFeed({ items: [...ITEMS, { ...ITEMS[0], id: 9, kind: 'other', level: 'unclassified',
                                   title: 'بازخرید سهام' }] });
    page();
    await waitFor(() => expect(screen.getAllByTestId('notice-row').length).toBe(3));
    // شاخصِ تخت، ترتیبِ DOM را بهِ ترتیبِ آزمونِ بی‌مرتب گره می‌زد؛ گروه‌بندیِ روز
    // آنِ را جابه‌جا می‌کند. هرِ برچسب ازِ ردیفِ خودش خوانده می‌شود — ادعا همان، وِ
    // بستگیِ کم‌تر.
    const rowOf = (t: string) =>
      screen.getAllByTestId('notice-row').find((li) => (li.textContent ?? '').includes(t)) as HTMLElement;
    const chip = (t: string) => rowOf(t).querySelector('[data-testid="notice-level"]') as HTMLElement;
    expect(rowOf('بازخرید سهام').getAttribute('data-level')).toBe('unclassified');
    expect(chip('بازخرید سهام').textContent).toBe('بی‌طبقه');
    expect(chip('سالانه').getAttribute('title')).toContain('EPS');
    // بی‌طبقه باِ پایین یکی نیست: مرزِ خط‌چین مخصوصِ بی‌طبقه است وِ برچسبِ سطحِ دیگر خط‌چین ندارد
    expect(chip('بازخرید سهام').className).toContain('border-dashed');
    expect(chip('ماهانه')).not.toHaveClass('border-dashed');
  });

  it('«خوانده شد» درِ همین دستگاه می‌ماند و شمارۀِ ناخوانده کم می‌شود', async () => {
    mockFeed();
    page();
    await waitFor(() => expect(screen.getAllByTestId('notice-row').length).toBe(2));
    fireEvent.click(screen.getAllByTestId('notice-mark')[0]);
    expect(useNoticePrefsStore.getState().read).toEqual(['1']);
    expect(localStorage.getItem('bors-notice-prefs')).toContain('"1"');
    await waitFor(() => expect(screen.getAllByTestId('notice-read-mark').length).toBe(1));
  });

  it('فیلترِ سطح از خودِ بک‌اند می‌پرسد، نه از برشِ رابط', async () => {
    mockFeed();
    page();
    await waitFor(() => expect(screen.getAllByTestId('notice-row').length).toBe(2));
    fetchMock.mockClear();
    fireEvent.click(screen.getByTestId('notice-level-high'));
    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((c) => String(c[0]));
      expect(urls.some((u) => u.includes('levels=high'))).toBe(true);
    });
  });

  it('منبعِ خالی ⇒ «نرسیده/خالی» با متنِ خودش، نه فهرستِ سفیدِ بی‌دلیل', async () => {
    mockFeed({ items: [], count: 0 }, { status: 'ok', note: '', sources: [
      { source: 'codal', label: 'کدال', rows: 0, newest_publish: null, last_fetch: null, state: 'empty' }] });
    page();
    await waitFor(() => expect(screen.getByTestId('notice-source-empty')).toBeInTheDocument());
    expect(screen.getByTestId('notice-source-empty').textContent).toContain('واکشی نشده');
  });

  it('خطایِ فید صفحه را نمی‌خواباند و هیچ خبری جایگزین ساخته نمی‌شود', async () => {
    fetchMock.mockImplementation(() => Promise.resolve(json({ status: 'error', source: 'codal',
      items: [], message: 'جدول نیست' })));
    page();
    await waitFor(() => expect(screen.getByTestId('notice-error')).toBeInTheDocument());
    expect(screen.queryAllByTestId('notice-row')).toHaveLength(0);
  });

  it('اعلانِ ویندوز پیش‌فرض خاموش است و کلیدش رویِ همان نوار می‌ماند', async () => {
    mockFeed();
    page();
    const box = screen.getByTestId('notice-native') as HTMLInputElement;
    expect(box.checked).toBe(false);
    fireEvent.click(box);
    expect(useNoticePrefsStore.getState().native).toBe(true);
  });
});
