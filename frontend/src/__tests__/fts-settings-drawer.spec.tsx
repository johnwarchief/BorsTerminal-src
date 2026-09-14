// تست پنل تنظیمات پیش‌شرط‌های FTS: باز/بسته، اسلایدرها، دروازه‌ها، Reset
// + پنل Overlay/Portal: رندر در document.body، بدون اشغال layout، Esc/کلیک بیرون
// + رگرسیون کات‌نشدن متون فارسی (break-words/min-w-0) و جهت RTL سوییچ‌ها
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { FtsSettingsDrawer, FtsSettingsTrigger } from '@features/fundamental/ui/FtsSettingsDrawer';
import { FTS_GUIDE_DEFAULTS } from '@features/fundamental/api/useFtsConfig';

// GET/POST واقعی نرود — سرور در تست نیست
const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

function renderDrawer(open = true) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <FtsSettingsDrawer open={open} onClose={() => {}} />
    </QueryClientProvider>,
  );
}

function renderTrigger(open = false) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const toggle = vi.fn();
  const utils = render(
    <QueryClientProvider client={queryClient}>
      {/* جدول ساختگی زیر دکمه — مثل صفحهٔ واقعی؛ پنل نباید آن را مچاله کند */}
      <table data-testid="underlying-table">
        <tbody>
          <tr>
            <td>سلول جدول</td>
          </tr>
        </tbody>
      </table>
      <FtsSettingsTrigger open={open} onToggle={toggle} />
    </QueryClientProvider>,
  );
  return { ...utils, toggle };
}

function configPayload() {
  return { status: 'success', config: { ...FTS_GUIDE_DEFAULTS } };
}

describe('پنل تنظیمات FTS', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(configPayload()),
    } as unknown as Response);
  });

  it('بسته نامرئی/بیرون viewport است و با باز شدن داخل دید می‌آید', () => {
    const { rerender } = renderDrawer(false);
    const aside = screen.getByLabelText('پنل تنظیمات پیش‌شرط‌های FTS');
    expect(aside.className).toContain('invisible');
    expect(aside.className).toContain('translate-x-full');
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    rerender(
      <QueryClientProvider client={qc}>
        <FtsSettingsDrawer open onClose={() => {}} />
      </QueryClientProvider>,
    );
    expect(aside.className).toContain('visible');
    expect(aside.className).toContain('translate-x-0');
  });

  it('پنل Overlay است: portal در document.body با fixed inset-y-0 right-0 سمت راست viewport', () => {
    renderTrigger(true);
    const wrapper = screen.getByTestId('fts-settings-trigger');
    const panel = screen.getByTestId('fts-settings-panel');
    // پنل در portal است — والدش document.body است نه wrapper درون-flow دکمه
    expect(panel.parentElement).toBe(document.body);
    expect(wrapper.contains(panel)).toBe(false);
    // پنل کناری ثابت سمت راست — بدون anchor-math، مستقل از اسکرول کانتینر داخلی
    expect(panel.className).toContain('fixed');
    expect(panel.className).toContain('inset-y-0');
    expect(panel.className).toContain('right-0');
    expect(panel.className).toContain('w-[420px]');
    expect(panel.className).toContain('z-[9999]');
    // backdrop نیمه‌شف زیر پنل روی همه‌چیز
    const backdrop = screen.getByTestId('fts-settings-backdrop');
    expect(backdrop.className).toContain('fixed');
    expect(backdrop.className).toContain('inset-0');
    expect(backdrop.className).toContain('z-[9998]');
  });

  it('باز/بسته شدن پنل ابعاد جدول زیرین را تغییر نمی‌دهد (out of layout)', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    let open = false;
    const { rerender } = render(
      <QueryClientProvider client={qc}>
        <table data-testid="underlying-table">
          <tbody>
            <tr>
              <td>سلول جدول</td>
            </tr>
          </tbody>
        </table>
        <FtsSettingsTrigger open={open} onToggle={() => { open = !open; }} />
      </QueryClientProvider>,
    );
    const table = screen.getByTestId('underlying-table');
    const before = { w: table.offsetWidth, h: table.offsetHeight };
    // باز کردن پنل
    fireEvent.click(screen.getByLabelText('تنظیمات پیش‌شرط‌های FTS'));
    rerender(
      <QueryClientProvider client={qc}>
        <table data-testid="underlying-table">
          <tbody>
            <tr>
              <td>سلول جدول</td>
            </tr>
          </tbody>
        </table>
        <FtsSettingsTrigger open onToggle={() => {}} />
      </QueryClientProvider>,
    );
    const after = { w: table.offsetWidth, h: table.offsetHeight };
    // پنل در portal است — جدول همان عرض/ارتفاع قبلی را دارد
    expect(after.w).toBe(before.w);
    expect(after.h).toBe(before.h);
    // پنل باز شده و در document.body رندر شده
    expect(screen.getByTestId('fts-settings-panel').parentElement).toBe(document.body);
    await waitFor(() => {
      expect(screen.getByText('ذخیرهٔ پیش‌شرط‌ها')).toBeInTheDocument();
    });
  });

  it('Esc پنل باز را می‌بندد', () => {
    const toggle = vi.fn();
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <FtsSettingsTrigger open onToggle={toggle} />
      </QueryClientProvider>,
    );
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(toggle).toHaveBeenCalledTimes(1);
  });

  it('کلیک روی backdrop (بیرون پنل) می‌بندد', () => {
    const toggle = vi.fn();
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <FtsSettingsTrigger open onToggle={toggle} />
      </QueryClientProvider>,
    );
    fireEvent.click(screen.getByTestId('fts-settings-backdrop'));
    expect(toggle).toHaveBeenCalledTimes(1);
  });

  it('کلیک روی دکمهٔ ⚙ پنل را باز می‌کند و aria-expanded را true می‌کند', async () => {
    const { toggle } = renderTrigger(false);
    const btn = screen.getByLabelText('تنظیمات پیش‌شرط‌های FTS');
    expect(btn.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(btn);
    expect(toggle).toHaveBeenCalledTimes(1);
    await waitFor(() => {
      expect(screen.getByText('ذخیرهٔ پیش‌شرط‌ها')).toBeInTheDocument();
    });
  });

  it('اسلایدرها و کلیدها رندر می شوند', async () => {
    renderDrawer();
    expect(screen.getByLabelText('حداقل درصد رشد درآمد کدال')).toBeInTheDocument();
    expect(screen.getByLabelText('کف حاشیه سود ناخالص')).toBeInTheDocument();
    expect(screen.getByLabelText('کف نسبت فروش سالانه‌شده به ارزش بازار')).toBeInTheDocument();
    expect(screen.getByText('الزام رشد مقداری / تناژ فیزیکی')).toBeInTheDocument();
    expect(screen.getByText('الزام سابقه عملکرد سودسازی ۳ ساله')).toBeInTheDocument();
    expect(screen.getByText('صنایع آزاد/صادراتی/بورس کالا')).toBeInTheDocument();
    expect(screen.getByText('صنایع مجاز با جهش نرخ (دارو، غذا)')).toBeInTheDocument();
    expect(screen.getByText('همه صنایع')).toBeInTheDocument();
    expect(screen.getByText('حذف نمادهای مشمول تعلیق')).toBeInTheDocument();
    expect(screen.getByText('Reset to FTS Defaults')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText('ذخیرهٔ پیش‌شرط‌ها')).toBeInTheDocument();
    });
  });

  it('دکمه ذخیره کلیدهای جزوه را POST می کند', async () => {
    renderDrawer();
    await waitFor(() => expect(screen.getByText('ذخیرهٔ پیش‌شرط‌ها')).toBeInTheDocument());
    fireEvent.click(screen.getByText('ذخیرهٔ پیش‌شرط‌ها'));
    await waitFor(() => {
      const post = fetchMock.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === 'POST');
      expect(post).toBeDefined();
      const body = JSON.parse((post![1] as RequestInit).body as string) as Record<string, unknown>;
      expect(body.industry_mode).toBe('Exclude_Mandatory_Pricing');
      expect(body.v10_volume_growth_min).toBe(0);
      expect(body.v10_sales_to_mcap_min).toBe(0.5);
      expect(body.v10_eps_years).toBe(3);
    });
  });

  it('گیت چندگزینه‌ای نرخ‌گذاری دستوری: «همه صنایع» یعنی Rank_Only', async () => {
    renderDrawer();
    await waitFor(() => expect(screen.getByText('همه صنایع')).toBeInTheDocument());
    // صبر تا config از سرور بیاید و state اولیه ست شود
    await waitFor(() => expect(screen.getByText('۵۰٪')).toBeInTheDocument());
    fireEvent.click(screen.getByText('همه صنایع'));
    fireEvent.click(screen.getByText('ذخیرهٔ پیش‌شرط‌ها'));
    await waitFor(() => {
      const posts = fetchMock.mock.calls.filter((c) => (c[1] as RequestInit | undefined)?.method === 'POST');
      const body = JSON.parse((posts[posts.length - 1][1] as RequestInit).body as string) as Record<string, unknown>;
      expect(body.industry_mode).toBe('Rank_Only');
    });
  });

  it('گیت چندگزینه‌ای: «جهش نرخ» دارو و غذا را از صنایع دستوری خارج می‌کند', async () => {
    renderDrawer();
    await waitFor(() => expect(screen.getByText('صنایع مجاز با جهش نرخ (دارو، غذا)')).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText('۵۰٪')).toBeInTheDocument());
    fireEvent.click(screen.getByText('صنایع مجاز با جهش نرخ (دارو، غذا)'));
    fireEvent.click(screen.getByText('ذخیرهٔ پیش‌شرط‌ها'));
    await waitFor(() => {
      const posts = fetchMock.mock.calls.filter((c) => (c[1] as RequestInit | undefined)?.method === 'POST');
      const body = JSON.parse((posts[posts.length - 1][1] as RequestInit).body as string) as Record<string, unknown>;
      expect(body.industry_mode).toBe('Exclude_Mandatory_Pricing');
      expect(body.mandatory_sectors).not.toContain('دارو');
      expect(body.mandatory_sectors).not.toContain('غذا');
      expect(body.mandatory_sectors).toContain('خودرو');
    });
  });

  it('اسلایدر شاخص ۴ کف فروش/ارزش بازار را ۱۰٪ تا ۱۰۰٪ نگاشت می‌کند', async () => {
    renderDrawer();
    await waitFor(() => expect(screen.getByLabelText('کف نسبت فروش سالانه‌شده به ارزش بازار')).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText('۵۰٪')).toBeInTheDocument());
    const slider = screen.getByLabelText('کف نسبت فروش سالانه‌شده به ارزش بازار') as HTMLInputElement;
    expect(slider.min).toBe('10');
    expect(slider.max).toBe('100');
    // مقدار پیش‌فرض جزوه: ۵۰٪
    expect(screen.getByText('۵۰٪')).toBeInTheDocument();
    fireEvent.change(slider, { target: { value: '80' } });
    fireEvent.click(screen.getByText('ذخیرهٔ پیش‌شرط‌ها'));
    await waitFor(() => {
      const posts = fetchMock.mock.calls.filter((c) => (c[1] as RequestInit | undefined)?.method === 'POST');
      const body = JSON.parse((posts[posts.length - 1][1] as RequestInit).body as string) as Record<string, unknown>;
      expect(body.v10_sales_to_mcap_min).toBe(0.8);
    });
  });

  it('تاگل شاخص ۲ خاموش یعنی v10_eps_years=1', async () => {
    renderDrawer();
    await waitFor(() => expect(screen.getByText('الزام سابقه عملکرد سودسازی ۳ ساله')).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText('۵۰٪')).toBeInTheDocument());
    fireEvent.click(screen.getByText('الزام سابقه عملکرد سودسازی ۳ ساله'));
    fireEvent.click(screen.getByText('ذخیرهٔ پیش‌شرط‌ها'));
    await waitFor(() => {
      const posts = fetchMock.mock.calls.filter((c) => (c[1] as RequestInit | undefined)?.method === 'POST');
      const body = JSON.parse((posts[posts.length - 1][1] as RequestInit).body as string) as Record<string, unknown>;
      expect(body.v10_eps_years).toBe(1);
    });
  });

  it('Reset پیش‌فرض‌های جزوه را می فرستد و اسلایدرها را بازنشانی می کند', async () => {
    renderDrawer();
    await waitFor(() => expect(screen.getByText('Reset to FTS Defaults')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Reset to FTS Defaults'));
    await waitFor(() => {
      const post = fetchMock.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === 'POST');
      expect(post).toBeDefined();
      const body = JSON.parse((post![1] as RequestInit).body as string) as Record<string, unknown>;
      expect(body.growth_min).toBe(FTS_GUIDE_DEFAULTS.growth_min);
      expect(body.margin_min).toBe(FTS_GUIDE_DEFAULTS.margin_min);
      expect(body.suspended_max_stale_sessions).toBe(3);
      expect(body.v10_sales_to_mcap_min).toBe(0.5);
      expect(body.v10_eps_years).toBe(3);
    });
  });

  it('خطای اعتبارسنجی سرور بدون کرش نشان داده می شود', async () => {
    fetchMock.mockImplementation((_url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              status: 'error',
              message: 'برخی مقادیر معتبر نیستند',
              errors: { growth_min: 'عددِ معتبر نیست' },
              config: null,
            }),
        } as unknown as Response);
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(configPayload()),
      } as unknown as Response);
    });
    renderDrawer();
    await waitFor(() => expect(screen.getByText('ذخیرهٔ پیش‌شرط‌ها')).toBeInTheDocument());
    fireEvent.click(screen.getByText('ذخیرهٔ پیش‌شرط‌ها'));
    await waitFor(() => {
      expect(screen.getByText('برخی مقادیر معتبر نیستند')).toBeInTheDocument();
    });
  });

  it('رگرسیون کات‌نشدن متن: ToggleRow برچسب و hint را با break-words و min-w-0 رندر می‌کند', async () => {
    renderDrawer();
    await waitFor(() => expect(screen.getByText('ذخیرهٔ پیش‌شرط‌ها')).toBeInTheDocument());
    const toggle = screen.getByText('حذف نمادهای مشمول تعلیق').closest('button');
    expect(toggle).not.toBeNull();
    // متن‌ها باید بتوانند بشکنند تا در عرض ۳۲۰px کشو کات نشوند
    const label = screen.getByText('حذف نمادهای مشمول تعلیق');
    expect(label.className).toContain('break-words');
    const hint = screen.getByText('نماد با ۳ نشست عقب‌مانده از تابلو');
    expect(hint.className).toContain('break-words');
    // ظرف متن flex-1 + min-w-0 دارد تا عرض مؤثر بگیرد
    const textCol = label.parentElement;
    expect(textCol?.className).toContain('min-w-0');
    expect(textCol?.className).toContain('flex-1');
  });

  it('رگرسیون کات‌نشدن متن: hint اسلایدرها break-words دارد و برچسب min-w-0', async () => {
    renderDrawer();
    await waitFor(() => expect(screen.getByText('ذخیرهٔ پیش‌شرط‌ها')).toBeInTheDocument());
    const growthLabel = screen.getByText('حداقل درصد رشد درآمد کدال');
    expect(growthLabel.className).toContain('min-w-0');
    expect(growthLabel.className).toContain('break-words');
    const marginHint = screen.getByText(/استاندارد ۳۰٪/);
    expect(marginHint.className).toContain('break-words');
  });

  it('سوییچ تاگل در جهت LTR ایزوله رندر می‌شود تا در RTL جابه‌جا نشود', async () => {
    renderDrawer();
    await waitFor(() => expect(screen.getByText('ذخیرهٔ پیش‌شرط‌ها')).toBeInTheDocument());
    const toggle = screen.getByText('حذف نمادهای مشمول تعلیق').closest('button');
    expect(toggle).not.toBeNull();
    const knobs = toggle!.querySelectorAll('span[dir="ltr"]');
    // بدنهٔ سوییچ dir="ltr" دارد و گلوله با left positioning می‌چسبد نه right
    expect(knobs.length).toBeGreaterThan(0);
    expect((toggle as HTMLElement) !== null).toBe(true);
  });

  it('رگرسیون RTL/عرض: پنل w-[420px] با پدینگ px-6 است و تاگل‌ها فاصله دارند', async () => {
    renderDrawer();
    await waitFor(() => expect(screen.getByText('ذخیرهٔ پیش‌شرط‌ها')).toBeInTheDocument());
    const aside = screen.getByLabelText('پنل تنظیمات پیش‌شرط‌های FTS');
    expect(aside.className).toContain('w-[420px]');
    const scroll = aside.querySelector('.overflow-y-auto');
    expect(scroll).not.toBeNull();
    expect(scroll!.className).toContain('px-6');
    const toggle = screen.getByText('حذف نمادهای مشمول تعلیق').closest('button');
    expect(toggle!.className).toContain('py-2.5');
  });
});
