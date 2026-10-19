// src/__tests__/nav-history.spec.tsx — بندِ A مأموریتِ UI/UX (ده آزمونِ اجباری)
//
// ده آزمونِ «دو کنترلِ بازگشت/بعدی» شماره‌گذاریِ خودِ مأموریت را دنبال می‌کند؛
// هر کدام یکِ ادعایِ جدا را می‌سنجد و هیچ‌کدام ازِ `window.history.length` یا
// جزئیاتِ خصوصیِ router نمی‌خواند. شاهدِ کاشته‌شده درِ آزمونِ نخست ثابت می‌کند
// سنسورِ دروازه‌ها کور نیست: عددِ جعلیِ مرورگر اگر منبعِ حقیقت بود، دکمه‌ها را
// روشن می‌کرد.
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  MemoryRouter, Navigate, Route, Routes,
  useLocation, useNavigate, type NavigateFunction,
} from 'react-router';
import { NavHistoryControls } from '@app/components/NavHistoryControls';
import { Topbar } from '@app/components/Topbar';
import { WorkspaceTabs } from '@app/components/WorkspaceTabs';
import { AppShell } from '@app/layouts/AppShell';
import { useNavHistorySync } from '@shared/lib/useNavHistorySync';
import {
  NAV_HISTORY_MAX, canGoBack, canGoForward, useNavHistoryStore,
  type NavHistoryState,
} from '@shared/stores/navHistoryStore';
import { useAuthStore } from '@shared/stores/authStore';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useWorkspaceStore, type WorkspaceTab } from '@shared/stores/workspaceStore';
import { mainRoutes } from '../routes';

const cold = () => useNavHistoryStore.setState({ entries: [], index: -1 });
const view = (): Pick<NavHistoryState, 'entries' | 'index'> => {
  const { entries, index } = useNavHistoryStore.getState();
  return { entries, index };
};

/** رانندۀِ ناوبری درِ خودِ درختِ router — بی‌اینِ پل، تست مجبور بود تاریخچه را
 *  دستی درِ store بنویسد و دیگر مسیرِ واقعیِ router آزموده نمی‌شد. */
let nav: NavigateFunction;
function Driver() {
  nav = useNavigate();
  return null;
}

function Here() {
  const l = useLocation();
  return <div data-testid="here">{`${l.pathname}${l.search}`}</div>;
}

function Shell({ withTabs = false }: { withTabs?: boolean }) {
  useNavHistorySync();
  return (
    <>
      <NavHistoryControls />
      <Here />
      {withTabs ? <WorkspaceTabs /> : null}
      <Routes>
        <Route path="/" element={<Navigate to="/master" replace />} />
        <Route path="/market" element={<div />} />
        <Route path="/market-status" element={<div />} />
        <Route path="/watch" element={<div />} />
        <Route path="/notifications" element={<div />} />
        <Route path="/master" element={<div />} />
        <Route path="/master/:symbol" element={<div />} />
        <Route path="/technical/:symbol" element={<div />} />
        <Route path="*" element={<div />} />
      </Routes>
    </>
  );
}

function ui(initialEntries: string[], withTabs = false) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Driver />
      <Shell withTabs={withTabs} />
    </MemoryRouter>,
  );
}

const go = (to: string) => act(() => { nav(to); });
const backBtn = () => screen.getByTestId('nav-back');
const fwdBtn = () => screen.getByTestId('nav-forward');
const here = () => screen.getByTestId('here').textContent;

describe('مدلِ تاریخچۀِ ناوبری (تابع‌هایِ خالص)', () => {
  beforeEach(cold);

  it('PUSHِ تکراری حلقه نمی‌سازد وِ دمِ forward را می‌بُرد', () => {
    const r = useNavHistoryStore.getState().record;
    r('/market', 'PUSH');
    r('/watch', 'PUSH');
    r('/watch', 'PUSH');                        // همان صفحۀِ دوباره: بی‌سطرِ تازه
    expect(view().entries).toEqual(['/market', '/watch']);
    r('/notifications', 'PUSH');
    expect(view().entries).toEqual(['/market', '/watch', '/notifications']);
    expect(canGoForward(view())).toBe(false);
  });

  it('REPLACE همانِ خانه را بازنویسی می‌کند، نه صفحۀِ تازه', () => {
    const r = useNavHistoryStore.getState().record;
    r('/x', 'PUSH');
    r('/master', 'REPLACE');
    expect(view()).toEqual({ entries: ['/master'], index: 0 });
  });

  it('POPِ همسایه نشانگر را جابه‌جا می‌کند وِ POPِ بیرونِ مدل صفحه می‌شود وِ دمِ forward بی‌اعتبار', () => {
    const r = useNavHistoryStore.getState().record;
    r('/market', 'PUSH');
    r('/watch', 'PUSH');
    r('/market', 'POP');
    expect(view().entries).toEqual(['/market', '/watch']);
    expect(view().index).toBe(0);
    r('/sarkhati', 'POP');                       // ناوبری ازِ بیرونِ مدل
    // گذشته می‌ماند وِ دمِ forward بی‌اعتبار می‌شود — همان قاعدۀِ PUSH، پسِ دو
    // مسیر درِ مدل یکِ رفتارِ متفاوت ندارند.
    expect(view().entries).toEqual(['/market', '/sarkhati']);
    expect(view().index).toBe(1);
  });

  it('نشانیِ بی«/» وِ خالی اصلاً ثبت نمی‌شوند', () => {
    const r = useNavHistoryStore.getState().record;
    r('market', 'PUSH');
    r('', 'PUSH');
    expect(view()).toEqual({ entries: [], index: -1 });
  });

  it('سقفِ تاریخچه ازِ دمِ قدیمی می‌کاهد وِ نشانگر را گم نمی‌کند', () => {
    const r = useNavHistoryStore.getState().record;
    for (let i = 0; i < NAV_HISTORY_MAX + 12; i++) r(`/watch?i=${i}`, 'PUSH');
    const { entries, index } = view();
    expect(entries.length).toBe(NAV_HISTORY_MAX);
    expect(index).toBe(NAV_HISTORY_MAX - 1);
    expect(entries[entries.length - 1]).toBe(`/watch?i=${NAV_HISTORY_MAX + 11}`);
    expect(canGoBack(view())).toBe(true);
  });
});

describe('دو کنترلِ بازگشت/بعدی درِ نوارِ بالا', () => {
  beforeEach(() => {
    cold();
    localStorage.clear();
    useSymbolStore.getState().clearSymbol();
    const tab: WorkspaceTab = { id: 't1', path: '/market', symbol: '' };
    useWorkspaceStore.setState({ tabs: [tab], activeId: 't1' });
  });
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    delete (window.history as unknown as Record<string, unknown>).length;
  });

  // ۱
  it('آغازِ سرد: هر دو دکمه غیرفعال است، بی‌آنکه طولِ تاریخچۀِ مرورگر اهمیتی داشته باشد', () => {
    Object.defineProperty(window.history, 'length', { value: 9, configurable: true });
    ui(['/market']);
    expect(window.history.length).toBe(9);        // شاهدِ کاشته‌شده زنده است
    expect(backBtn()).toBeDisabled();
    expect(fwdBtn()).toBeDisabled();
    expect(view().entries).toEqual(['/market']);
  });

  // ۲
  it('زنجیرۀِ PUSH: بازگشت روشن می‌شود وِ همانِ مسیرِ پیشین را پس می‌دهد', () => {
    ui(['/market']);
    go('/technical/فولاد');
    expect(here()).toBe('/technical/فولاد');
    expect(backBtn()).toBeEnabled();
    expect(backBtn().getAttribute('title')).toContain('/market');
    fireEvent.click(backBtn());
    expect(here()).toBe('/market');
    expect(fwdBtn()).toBeEnabled();
  });

  // ۳
  it('query گم نمی‌شود: برگشت به /master?stage=3 همانِ پرسش را بازمی‌گرداند', () => {
    ui(['/market']);
    go('/master?stage=3');
    go('/watch');
    fireEvent.click(backBtn());
    expect(here()).toBe('/master?stage=3');
    expect(view().entries[1]).toBe('/master?stage=3');
  });

  // ۴
  it('PUSH پس ازِ بازگشت، دمِ forward را می‌بُرد', () => {
    ui(['/market']);
    go('/watch');
    go('/notifications');
    fireEvent.click(backBtn());
    expect(here()).toBe('/watch');
    expect(fwdBtn()).toBeEnabled();
    go('/market-status');
    expect(view().entries).toEqual(['/market', '/watch', '/market-status']);
    expect(fwdBtn()).toBeDisabled();
  });

  // ۵
  it('بازگردانِ جایِ خالیِ برنامه (REPLACE) خانه‌ای که به «/» برمی‌گردد نمی‌سازد', () => {
    ui(['/']);
    expect(here()).toBe('/master');              // <Navigate replace> درِ همانِ رندر
    expect(view().entries).toEqual(['/master']);
    expect(backBtn()).toBeDisabled();
  });

  // ۶
  it('POPِ بومیِ router: دروازه‌ها جابه‌جا می‌شوند، صفحۀِ تازه ساخته نمی‌شود', () => {
    ui(['/market']);
    go('/watch');
    const before = view().entries;
    act(() => { nav(-1); });                      // همان کاری که کلیدِ Backِ مرورگر می‌کند
    expect(here()).toBe('/market');
    expect(view().entries).toEqual(before);        // بی‌سطرِ تازه
    expect(view().index).toBe(0);
    expect(backBtn()).toBeDisabled();
    expect(fwdBtn()).toBeEnabled();
  });

  // ۷
  it('تب‌هایِ فضایِ کاری: جابه‌جایی، بستن و تبِ تازه مدل را نمی‌شکنند', () => {
    ui(['/market'], true);
    expect(here()).toBe('/market');
    fireEvent.click(screen.getByTestId('ws-tab-new'));    // تبِ تازه ⇒ /master
    expect(here()).toBe('/master');
    expect(backBtn()).toBeEnabled();
    expect(useWorkspaceStore.getState().tabs.length).toBe(2);
    fireEvent.click(backBtn());
    expect(here()).toBe('/market');
    expect(useWorkspaceStore.getState().tabs.length).toBe(2);   // بی‌تبِ گم‌شده
    // رفتارِ ازِ پیشِ همینِ نوارِ تب (بندِ ۱ effect درِ WorkspaceTabs): نشانیِ
    // تازه تبِ فعال را بازنویسی می‌کند، پس بازگشت «تب عوض نمی‌کند» — هر دو تب
    // حالا رویِ /market نشسته‌اند. اینِ فاز آن را تغییر نمی‌دهد؛ اینجا پین
    // می‌شود تاِ ادعایِ «ناشکنی‌بودن» بی‌شاهد نباشد.
    const activeId = useWorkspaceStore.getState().activeId;
    expect(useWorkspaceStore.getState().tabs.find((t) => t.id === activeId)?.path)
      .toBe('/market');
    fireEvent.click(screen.getByTestId(`ws-tab-close-${activeId}`));
    expect(useWorkspaceStore.getState().tabs.length).toBe(1);
    expect(here()).toBe('/market');                       // همسایه جایش می‌آید
    expect(view().entries.every((p) => p.startsWith('/'))).toBe(true);
  });

  // ۸
  it('بازگشتِ قیف درِ MasterPage دست‌نخورده است: navigate(-1) درِ مدل POP می‌شود، نه صفحۀِ تازه', async () => {
    await import('@features/master/routes/MasterPage');
    useAuthStore.setState({ isAuthenticated: true });
    useSymbolStore.setState({ symbol: 'فولاد' });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={['/market']}>
          <Driver />
          <Here />
          <Routes>
            <Route path="/" element={<AppShell />}>
              {mainRoutes.map((r) => (
                <Route key={r.path} path={r.path || undefined} index={!r.path} element={r.element} />
              ))}
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    go('/master/فولاد');
    const btn = await screen.findByTestId('master-back', {}, { timeout: 6000 });
    const before = view().entries;
    fireEvent.click(btn);
    await waitFor(() => expect(here()).toBe('/market'));
    expect(view().entries).toEqual(before);            // بی‌سطرِ جعلیِ «/master»
    expect(view().index).toBe(0);
    expect(fwdBtn()).toBeEnabled();                     // «بعدی» حالا معنا دارد
  });

  // ۹
  it('کلیک رویِ کنترلِ غیرفعال هیچ مسیری نمی‌سازد', () => {
    ui(['/market']);
    fireEvent.click(backBtn());
    fireEvent.click(fwdBtn());
    expect(here()).toBe('/market');
    expect(view().entries).toEqual(['/market']);
  });

  // ۱۰
  it('ردیفِ تازه‌ای ساخته نمی‌شود وِ هیچ خطایِ کنسولی افزوده نمی‌شود', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 200 })));
    useSymbolStore.setState({ pinned: ['فولاد'] });      // گروهِ میانیِ نوارِ بالا
    const { unmount } = render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={['/market']}>
          <Driver />
          <Topbar />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const header = screen.getByTestId('nav-back').closest('header');
    expect(header).not.toBeNull();
    // همانِ کلاسِ ارتفاعِ پیشین (h-11 وِ md:h-9): هیچِ خطی به نوارِ بالا نیفزوده نشده
    expect(header!.className).toContain('h-11');
    expect(header!.className).toContain('md:h-9');
    // همانِ سه گروه: وضعیت+ناوبری، نشان‌شده‌ها، کنترل‌هایِ سمتِ چپ
    expect(header!.querySelectorAll(':scope > div')).toHaveLength(3);
    // کنترل‌ها داخلِ همانِ گروهِ ناوبری وِ کنارِ «موقعیت در برنامه» نشسته‌اند
    const navGroup = header!.querySelector('nav[aria-label="موقعیت در برنامه"]')?.parentElement;
    expect(navGroup?.querySelector('[data-testid="nav-back"]')).not.toBeNull();
    expect(navGroup?.querySelector('[data-testid="nav-forward"]')).not.toBeNull();
    unmount();

    // نیمۀِ دوم: یکِ نشستِ کاملِ ناوبری درِ harnessِ بی‌اجزاءِ جانبی — اینجا
    // هیچ console.error قابلِ قبول نیست (نه ازِ نوعِ «not wrapped in act»، که
    // درِ نوارِ بالا ازِ polling خودِ FreshnessBadge می‌آید و بهِ اینِ فاز ربطی ندارد).
    const errors = vi.spyOn(console, 'error');
    ui(['/market']);
    go('/watch');
    fireEvent.click(backBtn());
    go('/notifications');
    fireEvent.click(fwdBtn());                            // غیرفعال
    expect(errors).not.toHaveBeenCalled();
  });
});
