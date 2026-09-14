// تست badge «مجمع نزدیک» — از رویدادهای تقویم واقعی بک‌اند (events در /api/ma).
// دو حالت خواستهٔ کاربر: مجمع نزدیک (≤۱۴ روز) و تغییر مجمع (لغو/تعویق/انتقال)
// که باید صادقانه نشان داده شود، نه تاریخ قدیمی. بدون رویداد ⇒ بدون badge.
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AssemblyBadge } from '@features/fundamental/components/AssemblyBadge';
import {
  ASSEMBLY_NEAR_DAYS,
  assemblyChangeLabel,
  dayDiff,
  jalaliOf,
  pickAssemblyBadge,
  todayIsoInTehran,
} from '@features/fundamental/lib/assemblyEvent';

/** زمان ثابت: ۲۰۲۶-۰۹-۱۴ ( Tehran ۱۴۰۵/۰۶/۲۳ ) */
const NOW = new Date('2026-09-14T09:00:00Z');

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

function renderBadge(symbol = 'پست بازار', now: Date = NOW) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AssemblyBadge symbol={symbol} now={now} />
    </QueryClientProvider>,
  );
}

function mockEvents(events: unknown[]) {
  fetchMock.mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ status: 'ok', symbol: 'x', events, ma: {}, bars: 0 }),
  } as unknown as Response);
}

describe('lib/assemblyEvent — منطق خالص', () => {
  it('امروز تهران و تبدیل جلالی', () => {
    expect(todayIsoInTehran(NOW)).toBe('2026-09-14');
    expect(jalaliOf('2026-09-14')).toBe('۱۴۰۵/۰۶/۲۳');
    expect(dayDiff('2026-09-14', '2026-09-17')).toBe(3);
    expect(dayDiff('2026-09-14', '2026-09-14')).toBe(0);
    expect(dayDiff('2026-09-17', '2026-09-14')).toBe(-3);
  });

  it('مجمع نزدیک: ۳ روز دیگر با تاریخ جلالی', () => {
    const b = pickAssemblyBadge(
      [{ date: '2026-09-17', cat: 'assembly', title: 'آگهی دعوت به مجمع عمومی عادی سالیانه' }],
      NOW,
    );
    expect(b?.kind).toBe('near');
    expect(b?.days).toBe(3);
    expect(b?.label).toBe('مجمع نزدیک — ۳ روز دیگر (۱۴۰۵/۰۶/۲۶)');
    expect(b?.testId).toBe('assembly-near-badge');
  });

  it('امروز و فردا: برچسب صادقانه، بدون عدد گنگ', () => {
    const t = pickAssemblyBadge([{ date: '2026-09-14', cat: 'assembly', title: 'x' }], NOW);
    expect(t?.label).toBe('مجمع نزدیک — امروز (۱۴۰۵/۰۶/۲۳)');
    const tm = pickAssemblyBadge([{ date: '2026-09-15', cat: 'assembly', title: 'x' }], NOW);
    expect(tm?.label).toBe('مجمع نزدیک — فردا (۱۴۰۵/۰۶/۲۴)');
  });

  it('مجمع فوقالعاده: هدر متفاوت', () => {
    const b = pickAssemblyBadge([{ date: '2026-09-20', cat: 'assemblyExtra', title: 'دعوت به مجمع فوق العاده' }], NOW);
    expect(b?.label).toContain('مجمع فوق‌العاده نزدیک — ۶ روز دیگر');
  });

  it('دورتر از آستانه ⇒ بدون badge', () => {
    const b = pickAssemblyBadge(
      [{ date: '2026-10-30', cat: 'assembly', title: 'x' }],
      NOW,
      ASSEMBLY_NEAR_DAYS,
    );
    expect(b).toBeNull();
  });

  it('تغییر مجمع پیش‌رو: برچسب صادقانهٔ تغییر — نه تاریخ قدیمی', () => {
    const b = pickAssemblyBadge(
      [
        { date: '2026-09-20', cat: 'assembly', title: 'دعوت به مجمع' },
        { date: '2026-09-15', cat: 'assemblyChange', title: 'تصمیمات مجمع — به تعویق افتاد' },
      ],
      NOW,
    );
    expect(b?.kind).toBe('change');
    expect(b?.label).toBe('مجمع به تعویق افتاد');
    expect(b?.testId).toBe('assembly-change-badge');
  });

  it('لغو/انتقال: برچسب از روی عنوان اطلاعیه', () => {
    expect(assemblyChangeLabel('لغو زمان تشکیل جلسه هیات مدیره')).toBe('مجمع لغو شد');
    expect(assemblyChangeLabel('انتقال مجمع عمومی به زمان دیگر')).toBe('زمان مجمع تغییر کرد');
    expect(assemblyChangeLabel('عدم برگزاری مجمع')).toBe('مجمع لغو شد');
    expect(assemblyChangeLabel('تصمیمات مجمع')).toBe('مجمع به تعویق افتاد');
  });

  it('رویداد مجمع پیش‌رو نیست ولی آخرین رویداد گذشته تغییر بود ⇒ برچسب تغییر', () => {
    const b = pickAssemblyBadge(
      [
        { date: '2026-09-01', cat: 'assembly', title: 'دعوت به مجمع' },
        { date: '2026-09-10', cat: 'assemblyChange', title: 'لغو مجمع عمومی' },
      ],
      NOW,
    );
    expect(b?.kind).toBe('change');
    expect(b?.label).toBe('مجمع لغو شد');
  });

  it('بدون رویداد مجمع / رویدادهای نامرتبط ⇒ null (بدون دادهٔ ساختگی)', () => {
    expect(pickAssemblyBadge([], NOW)).toBeNull();
    expect(pickAssemblyBadge(undefined, NOW)).toBeNull();
    expect(
      pickAssemblyBadge([{ date: '2026-09-20', cat: 'dividend', title: 'تقسیم سود' }], NOW),
    ).toBeNull();
    // تاریخ نامعتبر هم فیلتر می‌شود
    expect(pickAssemblyBadge([{ date: 'نه-تاریخ', cat: 'assembly', title: 'x' }], NOW)).toBeNull();
  });

  it('رویدادهای غیرمجمع با هم‌دسته اشتباه گرفته نمی‌شوند', () => {
    const b = pickAssemblyBadge(
      [
        { date: '2026-09-15', cat: 'capitalIncrease', title: 'افزایش سرمایه' },
        { date: '2026-09-16', cat: 'assembly', title: 'دعوت به مجمع' },
      ],
      NOW,
    );
    expect(b?.kind).toBe('near');
    expect(b?.label).toContain('مجمع نزدیک');
  });
});

describe('AssemblyBadge — رندر با دادهٔ واقعی /api/ma', () => {
  beforeEach(() => {
    fetchMock.mockReset();
  });

  it('مجمع نزدیک: badge کنار نماد با تاریخ جلالی و tooltip عنوان اطلاعیه', async () => {
    mockEvents([
      { date: '2026-09-14', ts: 1, title: 'آگهی دعوت به مجمع صندوق سرمایه گذاری در تاریخ ۱۴۰۵/۰۶/۲۳', cat: 'assembly' },
    ]);
    renderBadge('پست بازار');
    const el = await screen.findByTestId('assembly-near-badge');
    expect(el.textContent).toBe('مجمع نزدیک — امروز (۱۴۰۵/۰۶/۲۳)');
    expect(el.getAttribute('title')).toContain('آگهی دعوت به مجمع');
    // درخواست به اندپوینت رویدادها زده شده باشد
    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain('/api/ma/');
    expect(url).toContain(encodeURIComponent('پست بازار'));
  });

  it('تغییر مجمع: برچسب صادقانهٔ تغییر — نه تاریخ قدیمی', async () => {
    mockEvents([
      { date: '2026-09-20', ts: 1, title: 'دعوت به مجمع عمومی', cat: 'assembly' },
      { date: '2026-09-14', ts: 2, title: 'تصمیمات مجمع عمومی — به تعویق افتاد', cat: 'assemblyChange' },
    ]);
    renderBadge('البرز');
    const el = await screen.findByTestId('assembly-change-badge');
    expect(el.textContent).toBe('مجمع به تعویق افتاد');
    expect(screen.queryByTestId('assembly-near-badge')).not.toBeInTheDocument();
    expect(el.getAttribute('title')).toContain('به تعویق افتاد');
  });

  it('بدون رویداد مجمع: هیچ badge رندر نمیشود', async () => {
    mockEvents([{ date: '2026-09-20', ts: 1, title: 'تقسیم سود نقدی', cat: 'dividend' }]);
    renderBadge('شفارس');
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(screen.queryByTestId('assembly-near-badge')).not.toBeInTheDocument();
    expect(screen.queryByTestId('assembly-change-badge')).not.toBeInTheDocument();
  });

  it('خطای شبکه: بدون badge و بدون کرش', async () => {
    fetchMock.mockRejectedValue(new Error('down'));
    renderBadge('شفارس');
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(screen.queryByTestId('assembly-near-badge')).not.toBeInTheDocument();
  });
});
