// تستِ ساختارِ معناییِ مرکزِ اعلان (بندِ اولویتِ ۳ فاز G)
//
// چهار چیز که آزمونِ قبلیِ اینِ صفحه نمی‌گفت:
//  • گروه‌بندیِ روزانه ازِ خودِ تاریخِ کدال می‌آید، نه ازِ تبدیلِ ساعتِ کلاینت
//  • روزِ بی‌تاریخ «—» می‌ماند (اختراعِ تاریخ ممنوع)
//  • هرِ روز یکِ <section> باِ <h2> است (سرعتِ خالیِ heads=0 سنجشِ زنده بود)
//  • فیلترِ نوع، گروه‌ها را ازِ نو می‌چیند (گروه‌بندی بر `visible`، نه `items`)
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useNoticePrefsStore } from '@features/market/stores/noticePrefsStore';
import NotificationsPage, { groupByDay } from '@features/market/routes/NotificationsPage';
import type { NoticeFeed, NoticeSources } from '@features/market/api/useNotifications';

const feedMock = vi.fn();
const sourcesMock = vi.fn();

vi.mock('@features/market/api/useNotifications', () => ({
  useNoticeFeed: () => feedMock(),
  useNoticeSources: () => sourcesMock(),
}));

function item(id: number, over: Record<string, unknown> = {}) {
  return {
    id,
    symbol: 'شپنا',
    company: 'پالایش',
    title: `اطلاعیه ${id}`,
    kind: 'statements',
    level: 'high',
    reason: 'صورتِ مالی',
    letter_code: null,
    publish_date: '1405-07-22T11:04:00',
    sent_date: null,
    received_at: '1405-07-22T11:05:00',
    url: 'https://codal360.ir/x',
    source: 'codal',
    occurrences: 1,
    ...over,
  };
}

const ITEMS = [
  item(1),
  item(2, { publish_date: '1405-07-22T09:00:00' }),
  item(3, { publish_date: '1405-07-20T18:30:00', kind: 'assembly' }),
];

function okFeed(items = ITEMS): NoticeFeed {
  return {
    status: 'ok', source: 'codal', count: items.length, scanned: items.length,
    merged_duplicates: 0, levels: null, since: null, message: null, items,
  } as unknown as NoticeFeed;
}

function okSources(): NoticeSources {
  return {
    status: 'ok', note: null,
    sources: [{ source: 'codal', label: 'کدال', rows: 3, newest_publish: '1405-07-22T11:04:00',
                last_fetch: '1405-07-22T11:06:00', state: 'ok', message: null }],
  } as unknown as NoticeSources;
}

beforeEach(() => {
  feedMock.mockReset();
  sourcesMock.mockReset();
  feedMock.mockReturnValue({ data: okFeed(), isLoading: false, isError: false, refetch: vi.fn() });
  sourcesMock.mockReturnValue({ data: okSources() });
  useNoticePrefsStore.setState({ read: [], levels: [], kinds: [], native: false });
});

describe('groupByDay — منطقِ خالص', () => {
  it('روزها را ازِ خودِ تاریخِ کدال می‌خواند وِ ترتیبِ فید را نگه می‌دارد', () => {
    const days = groupByDay(ITEMS, () => true);
    expect(days.map((d) => d.day)).toEqual(['1405-07-22', '1405-07-20']);
    expect(days[0].items.map((n) => n.id)).toEqual([1, 2]);
    expect(days[1].items.map((n) => n.id)).toEqual([3]);
  });

  it('ناخوانده را به‌ازایِ روز می‌شمارد (نه فقطِ سراسری)', () => {
    const days = groupByDay(ITEMS, (id) => id === '1');
    expect(days[0]).toMatchObject({ day: '1405-07-22', unread: 1 });
    expect(days[1]).toMatchObject({ day: '1405-07-20', unread: 1 });
  });

  it('تاریخِ بی‌منبع را «—» می‌گذارد وِ روزِ امروز نمی‌سازد', () => {
    const days = groupByDay([item(9, { publish_date: null })], () => false);
    expect(days).toHaveLength(1);
    expect(days[0].day).toBe('—');
    expect(days[0].unread).toBe(1);
  });

  it('هیچِ اطلاعیه‌ای درِ گروه‌بندی گم نمی‌شود', () => {
    const days = groupByDay(ITEMS, () => true);
    expect(days.reduce((n, d) => n + d.items.length, 0)).toBe(ITEMS.length);
  });
});

describe('NotificationsPage — ساختارِ معنایی وِ پیمایش', () => {
  it('هرِ روز یکِ section باِ تیترِ سطحِ ۲ (بی‌تیتر = ستونِ بی‌نقطهٔ اتّصال)', async () => {
    render(<NotificationsPage />);
    const heads = await screen.findAllByRole('heading', { level: 2 });
    expect(heads).toHaveLength(2);
    expect(heads[0].textContent).toContain('1405-07-22');
    expect(heads[0].textContent).toContain('۲ اطلاعیه');
    expect(heads[1].textContent).toContain('1405-07-20');
    const sec = screen.getByTestId('notice-day-1405-07-22');
    expect(sec.tagName).toBe('SECTION');
    expect(sec.querySelectorAll('li[data-testid="notice-row"]')).toHaveLength(2);
    expect(sec.contains(heads[0])).toBe(true);
  });

  it('تیترِ روز چسبان است تاِ «کجایِ تاریخچه» حینِ اسکرول خوانده شود', async () => {
    render(<NotificationsPage />);
    const h = await screen.findByTestId('notice-day-title-1405-07-22');
    expect(h.className).toContain('sticky');
    expect(h.className).toContain('top-0');
  });

  it('برچسبِ ناخوانده درِ همانِ روز دیده می‌شود (نه فقطِ شمارِ سراسری)', async () => {
    useNoticePrefsStore.setState({ read: ['1', '3'] });
    render(<NotificationsPage />);
    const badge = await screen.findByTestId('notice-day-unread-1405-07-22');
    expect(badge.textContent).toContain('۱ ناخوانده');
    expect(screen.queryByTestId('notice-day-unread-1405-07-20')).toBeNull();
  });

  it('فیلترِ نوع، گروه‌ها را ازِ نو می‌چیند (روزی که بیرون می‌رود تیتر نمی‌ماند)', async () => {
    render(<NotificationsPage />);
    fireEvent.click(await screen.findByTestId('notice-kind-assembly'));
    expect(await screen.findByTestId('notice-day-title-1405-07-20')).toBeTruthy();
    expect(screen.queryByTestId('notice-day-title-1405-07-22')).toBeNull();
    expect(screen.getAllByTestId('notice-row')).toHaveLength(1);
  });

  it('فیلترِ بی‌نتیجه فهرستِ خالیِ صادق می‌دهد، نه تیترهایِ بی‌محتوا', async () => {
    render(<NotificationsPage />);
    fireEvent.click(await screen.findByTestId('notice-kind-ipo'));
    expect(screen.queryByTestId('notice-list')).toBeNull();
    expect(await screen.findByText('چیزی درِ این فیلتر نیست')).toBeTruthy();
  });
});
