// نگهبانِ تب‌های فضای کاری: مسیرِ هر تب منبع حقیقت است وِ نمادِ یکِ تب،
// تبِ دیگر را تکان نمی‌دهد (سناریویِ صریحِ مأموریت: فولاد درِ یکِ تب، فملی درِ دیگری).
import { render, screen, fireEvent, within, act } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { WorkspaceTabs } from '@app/components/WorkspaceTabs';
import { useWorkspaceStore, DEFAULT_TAB_PATH } from '@shared/stores/workspaceStore';
import { useSymbolStore } from '@shared/stores/symbolStore';

function Shell() {
  return (
    <div>
      <WorkspaceTabs />
      <main id="workspace-panel" role="tabpanel" data-testid="panel">
        صفحه
      </main>
    </div>
  );
}

function renderTabs(initialPath = DEFAULT_TAB_PATH) {
  const router = createMemoryRouter([{ path: '*', element: <Shell /> }], {
    initialEntries: [initialPath],
  });
  return render(<RouterProvider router={router} />);
}

const tabs = () => screen.getAllByRole('tab');
const tabButtons = (label: string) => screen.getAllByRole('tab').filter((el) => el.textContent?.includes(label));

describe('تب‌های فضای کاری (الگویِ ARIA APG باِ تطبیقِ RTL)', () => {
  beforeEach(() => {
    localStorage.clear();
    const first = { id: 'seed', path: DEFAULT_TAB_PATH, symbol: '' };
    act(() => {
      useWorkspaceStore.setState({ tabs: [first], activeId: first.id });
      useSymbolStore.setState({ symbol: '' });
    });
  });

  it('باِ یکِ تب شروع می‌شود وِ tablist درست است', () => {
    renderTabs();
    const list = screen.getByTestId('ws-tablist');
    expect(list).toHaveAttribute('role', 'tablist');
    expect(list).toHaveAttribute('aria-label', 'تب‌های فضای کاری');
    expect(tabs()).toHaveLength(1);
    expect(tabs()[0]).toHaveAttribute('aria-selected', 'true');
    expect(tabs()[0]).toHaveAttribute('aria-controls', 'workspace-panel');
  });

  it('نامِ تب ازِ همانِ واژگانِ Sidebar می‌آید، نه ازِ فهرستِ دوم', () => {
    renderTabs();
    act(() => {
      useWorkspaceStore.getState().openTab('/technical/فولاد', 'فولاد');
    });
    expect(tabButtons('تکنیکال · فولاد')).toHaveLength(1);
  });

  it('«+» هر بار یکِ تبِ تازه می‌سازد (بی‌آنکه بی‌صدا تبِ موجود را فعال کند)', () => {
    renderTabs();
    fireEvent.click(screen.getByTestId('ws-tab-new'));
    expect(tabs()).toHaveLength(2);
    fireEvent.click(screen.getByTestId('ws-tab-new'));
    expect(tabs()).toHaveLength(3);
  });

  it('پیوندِ «بازکردنِ نماد» اگرِ همانِ مسیر باز باشد، تبِ موجود را فعال می‌کند', () => {
    renderTabs();
    const store = useWorkspaceStore.getState;
    let first = '';
    act(() => { first = store().openTab('/technical/فولاد', 'فولاد'); });
    let second = '';
    act(() => { second = store().openTab('/technical/فولاد', 'فولاد'); });
    expect(second).toBe(first);                       // نه تبِ دومی، بلکه همانِ قبلی فعال
    expect(useWorkspaceStore.getState().tabs).toHaveLength(2);  // seed + فولاد
  });

  it('سناریویِ مالک: انتخابِ نماد درِ یکِ تب، تبِ دیگر را عوض نمی‌کند', () => {
    renderTabs();
    const store = useWorkspaceStore.getState;
    act(() => { store().openTab('/technical/فولاد', 'فولاد'); });
    act(() => { store().openTab('/fundamental/فملی', 'فملی'); });
    const [, folad, femeli] = useWorkspaceStore.getState().tabs;   // [0] تبِ نخستِ /master است
    expect(folad.symbol).toBe('فولاد');
    expect(femeli.symbol).toBe('فملی');

    // فعال‌کردنِ هر تب ⇒ نمادِ همانِ تب بهِ chrome برمی‌گردد وِ برعکس
    act(() => { useWorkspaceStore.getState().activateTab(folad.id); });
    expect(useSymbolStore.getState().symbol).toBe('فولاد');
    act(() => { useWorkspaceStore.getState().activateTab(femeli.id); });
    expect(useSymbolStore.getState().symbol).toBe('فملی');
    expect(useWorkspaceStore.getState().tabs.map((t) => t.symbol)).toEqual(['', 'فولاد', 'فملی']);
  });

  it('صفحه‌کلید درِ RTL: پیکانِ چپ ⇒ تبِ بعدی، پیکانِ راست ⇒ قبلی', () => {
    renderTabs();
    act(() => { useWorkspaceStore.getState().openTab('/market-status'); });
    act(() => { useWorkspaceStore.getState().openTab('/watch'); });
    const list = screen.getByTestId('ws-tablist');
    act(() => { useWorkspaceStore.getState().activateTab(useWorkspaceStore.getState().tabs[0].id); });
    const three = tabs();
    expect(three[0]).toHaveAttribute('aria-selected', 'true');

    fireEvent.keyDown(list, { key: 'ArrowLeft' });
    expect(tabs()[1]).toHaveAttribute('aria-selected', 'true');
    fireEvent.keyDown(list, { key: 'ArrowLeft' });
    expect(tabs()[2]).toHaveAttribute('aria-selected', 'true');
    fireEvent.keyDown(list, { key: 'ArrowRight' });
    expect(tabs()[1]).toHaveAttribute('aria-selected', 'true');
    fireEvent.keyDown(list, { key: 'End' });
    expect(tabs()[2]).toHaveAttribute('aria-selected', 'true');
    fireEvent.keyDown(list, { key: 'Home' });
    expect(tabs()[0]).toHaveAttribute('aria-selected', 'true');
  });

  it('Delete تبِ دارایِ فوکوس را می‌بندد؛ بستنِ آخرینِ تب برنامه را بی‌تب نمی‌گذارد', () => {
    renderTabs();
    const list = screen.getByTestId('ws-tablist');
    fireEvent.keyDown(list, { key: 'Delete' });
    expect(tabs()).toHaveLength(1);
    expect(tabs()[0]).toHaveTextContent('استراتژی FTS');
    expect(screen.getByTestId('panel')).toBeInTheDocument();
  });

  it('بستنِ تبِ میانی ⇒ فوکوس بهِ همسایه می‌رود (کاربرِ صفحه‌کلید درِ خلأ نمی‌ماند)', () => {
    renderTabs();
    act(() => { useWorkspaceStore.getState().openTab('/market-status'); });
    act(() => { useWorkspaceStore.getState().openTab('/watch'); });
    const first = useWorkspaceStore.getState().tabs[0];
    fireEvent.click(screen.getByTestId(`ws-tab-close-${first.id}`));
    const stillActive = useWorkspaceStore.getState().activeId;
    expect(stillActive).not.toBe(first.id);
    expect(document.activeElement?.id).toBe(`ws-tab-${stillActive}`);
  });

  it('roving tabindex: فقطِ تبِ انتخاب‌شده درِ ترتیبِ Tab می‌ماند', () => {
    renderTabs();
    act(() => { useWorkspaceStore.getState().openTab('/market-status'); });
    act(() => { useWorkspaceStore.getState().activateTab(useWorkspaceStore.getState().tabs[0].id); });
    const [sel, unsel] = tabs();
    expect(sel).toHaveAttribute('tabindex', '0');
    expect(unsel).toHaveAttribute('tabindex', '-1');
  });

  it('تب‌ها درِ localStorage می‌مانند وِ بازمی‌گردند (reload همانِ تب‌ها را می‌دهد)', async () => {
    renderTabs();
    act(() => { useWorkspaceStore.getState().openTab('/technical/شپنا', 'شپنا'); });
    act(() => { useWorkspaceStore.getState().openTab('/market'); });

    const KEY = ['bors', 'workspace', 'tabs'].join('-');
    const saved = JSON.parse(localStorage.getItem(KEY) ?? '{}');
    expect(saved.tabs.map((t: { path: string }) => t.path)).toEqual(['/master', '/technical/شپنا', '/market']);

    // بارِ دومِ ماژول = همانِ کاری که reload می‌کند: store باید ازِ حافظه پر شود
    vi.resetModules();
    const reloaded = await import('@shared/stores/workspaceStore');
    expect(reloaded.useWorkspaceStore.getState().tabs.map((t: { path: string }) => t.path)).toEqual(saved.tabs.map((t: { path: string }) => t.path));
    expect(reloaded.useWorkspaceStore.getState().activeId).toBe(saved.activeId);
  });

  it('دادهٔ خرابِ حافظه برنامه را سفید نمی‌کند', async () => {
    localStorage.setItem(['bors', 'workspace', 'tabs'].join('-'), '{"tabs":[{"path":42},"nope",{"id":"x","path":"/watch","symbol":""}]}');
    vi.resetModules();
    const reloaded = await import('@shared/stores/workspaceStore');
    const state = reloaded.useWorkspaceStore.getState();
    expect(state.tabs).toHaveLength(1);            // فقطِ رکوردِ سالم می‌ماند
    expect(state.tabs[0].path).toBe('/watch');
    expect(state.activeId).toBe(state.tabs[0].id);
  });

  it('منیوی «…» هنگامِ شلوغی، همهٔ تب‌ها وِ میانبرها را قابل‌دسترس می‌کند', () => {
    renderTabs();
    for (let i = 0; i < 7; i += 1) {
      act(() => { useWorkspaceStore.getState().openTab(`/market/s${i}`); });
    }
    const menuBtn = screen.getByTestId('ws-tab-menu');
    expect(menuBtn).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(menuBtn);
    expect(menuBtn).toHaveAttribute('aria-expanded', 'true');
    const menu = screen.getByTestId('ws-tab-menu-list');
    expect(within(menu).getAllByRole('menuitem').length).toBeGreaterThanOrEqual(8);
    expect(within(menu).getByText(/Ctrl\+T/)).toBeInTheDocument();
  });
});
