// RA-3: هشدارِ قیمتی — داوریِ خالص، استورِ پایدار، و پنل/نگهبانِ زنده
import { fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { crossed, dueAlertIds, firedLabel, tickPrice } from '@features/technical/lib/priceAlerts';
import { usePriceAlertWatch } from '@features/technical/lib/usePriceAlertWatch';
import { usePriceAlertStore, type PriceAlert } from '@features/technical/stores/priceAlertStore';
import { PriceAlertsPanel } from '@features/technical/nahayatnegar/components/PriceAlertsPanel';
import { PriceAlertBanner } from '@features/technical/nahayatnegar/components/PriceAlertBanner';

const alert = (patch: Partial<PriceAlert> = {}): PriceAlert => ({
  id: 'a1',
  symbol: 'فولاد',
  side: 'above',
  price: 125000,
  createdAt: 1,
  firedAt: null,
  active: true,
  seen: true,
  ...patch,
});

beforeEach(() => {
  localStorage.clear();
  usePriceAlertStore.setState({ alerts: [] });
});

describe('داوریِ خالصِ هشدار', () => {
  it('قیمتِ اکنون: آخرین، و اگر نبود پایانی — صفر و NaN قیمت نیستند', () => {
    expect(tickPrice({ p_last: 120000, p_closing: 119000 })).toBe(120000);
    expect(tickPrice({ p_last: null, p_closing: 119000 })).toBe(119000);
    expect(tickPrice({ p_last: 0, p_closing: 119000 })).toBe(119000);
    expect(tickPrice({ p_last: null, p_closing: null })).toBeNull();
    expect(tickPrice(null)).toBeNull();
  });

  it('برابرِ آستانه «بالای» را شلیک می‌کند و «زیر» را نه', () => {
    expect(crossed({ side: 'above', price: 125000 }, 125000)).toBe(true);
    expect(crossed({ side: 'below', price: 125000 }, 125000)).toBe(true);
    expect(crossed({ side: 'above', price: 125000 }, 124999)).toBe(false);
    expect(crossed({ side: 'below', price: 125000 }, 124999)).toBe(true);
  });

  it('بی‌قیمت هیچ شلیکی نیست؛ نمادِ غایب در فید داوری نمی‌شود', () => {
    const rows = [{ symbol: 'فولاد', p_last: null, p_closing: null }];
    expect(dueAlertIds([alert()], rows)).toEqual([]);
    expect(dueAlertIds([alert()], [{ symbol: 'شپنا', p_last: 130000 }])).toEqual([]);
  });

  it('هشدارِ خاموش و شلیک‌شده دوباره شلیک نمی‌شوند', () => {
    const rows = [{ symbol: 'فولاد', p_last: 130000 }];
    expect(dueAlertIds([alert({ active: false })], rows)).toEqual([]);
    expect(dueAlertIds([alert({ firedAt: 5 })], rows)).toEqual([]);
    expect(dueAlertIds([alert()], rows)).toEqual(['a1']);
  });

  it('متنِ بنر از خودِ هشدار و قیمتِ اکنون ساخته می‌شود؛ رقمِ لاتین ندارد', () => {
    const t = firedLabel(alert(), 131000);
    expect(t).toContain('فولاد');
    expect(t).toContain('بالا رفت از');
    expect(t).toContain('۱۲۵');
    expect(t).toContain('۱۳۱');
    expect(/[0-9]/.test(t)).toBe(false);
  });
});

describe('استورِ هشدار', () => {
  it('آستانهٔ نامعتبر و نمادِ خالی هیچ نمی‌سازند', () => {
    const s = () => usePriceAlertStore.getState();
    expect(s().addAlert({ symbol: '  ', side: 'above', price: 125000 })).toBeNull();
    expect(s().addAlert({ symbol: 'فولاد', side: 'above', price: 0 })).toBeNull();
    expect(s().addAlert({ symbol: 'فولاد', side: 'above', price: Number.NaN })).toBeNull();
    expect(s().alerts).toHaveLength(0);
  });

  it('تکرارِ همان شرط همان id را برمی‌گرداند و ردیفِ دوم نمی‌سازد', () => {
    const first = usePriceAlertStore.getState().addAlert({ symbol: 'فولاد', side: 'above', price: 125000 });
    const again = usePriceAlertStore.getState().addAlert({ symbol: 'فولاد', side: 'above', price: 125000 });
    expect(first).toBeTruthy();
    expect(again).toBe(first);
    expect(usePriceAlertStore.getState().alerts).toHaveLength(1);
  });

  it('شلیک ⇒ خاموش، بی‌seen؛ بازنشانی ⇒ دوباره فعال', () => {
    const id = usePriceAlertStore.getState().addAlert({ symbol: 'فولاد', side: 'above', price: 125000 })!;
    usePriceAlertStore.getState().fire([id], 777);
    let a = usePriceAlertStore.getState().alerts[0];
    expect([a.active, a.firedAt, a.seen]).toEqual([false, 777, false]);
    usePriceAlertStore.getState().markSeen([id]);
    a = usePriceAlertStore.getState().alerts[0];
    expect(a.seen).toBe(true);
    usePriceAlertStore.getState().rearm(id);
    a = usePriceAlertStore.getState().alerts[0];
    expect([a.active, a.firedAt]).toEqual([true, null]);
  });

  it('ذخیره و بازیابی:ردیفِ خرابِ ذخیره‌شده بارگذاری نمی‌شود', async () => {
    usePriceAlertStore.getState().addAlert({ symbol: 'فولاد', side: 'below', price: 118000 });
    const raw = JSON.parse(localStorage.getItem('fts.price-alerts.v1') ?? '{}');
    expect(raw.alerts).toHaveLength(1);
    localStorage.setItem(
      'fts.price-alerts.v1',
      JSON.stringify({ alerts: [...raw.alerts, { symbol: 'شپنا', side: 'above', price: 0 }, { symbol: '', side: 'above', price: 5 }] }),
    );
    vi.resetModules();
    const mod = await import('@features/technical/stores/priceAlertStore');
    expect(mod.usePriceAlertStore.getState().alerts).toHaveLength(1);
  });
});

describe('نگهبانِ هشدار روی فید', () => {
  it('هر تازه‌شدنِ فید آستانه‌ها را داوری می‌کند و بنر فقط شلیک‌شده را نشان می‌دهد', async () => {
    const id = usePriceAlertStore.getState().addAlert({ symbol: 'فولاد', side: 'above', price: 125000 })!;
    const rows = [{ symbol: 'فولاد', p_last: 121000, p_closing: 120000 }];
    const up = [{ symbol: 'فولاد', p_last: 126500, p_closing: 125000 }];
    const { rerender } = renderHook(({ r }) => usePriceAlertWatch(r), { initialProps: { r: rows } });
    expect(usePriceAlertStore.getState().alerts[0].firedAt).toBeNull();

    rerender({ r: up });
    await waitFor(() => expect(usePriceAlertStore.getState().alerts[0].active).toBe(false));

    render(<PriceAlertBanner rows={up} />);
    const line = screen.getByTestId(`price-alert-line-${id}`);
    expect(line.textContent).toContain('فولاد');
    expect(line.textContent).toContain('۱۲۶');
    expect(screen.getByTestId('price-alert-banner').textContent).toContain('۱');
    fireEvent.click(screen.getByTestId('price-alert-dismiss'));
    expect(usePriceAlertStore.getState().alerts[0].seen).toBe(true);
  });
});

describe('پنلِ هشدار', () => {
  it('افزودن با عددِ فارسی و Enter، و برچسبِ «همین حالا برقرار است»', () => {
    render(<PriceAlertsPanel symbol="فولاد" boardRow={{ p_last: 130000, p_closing: 129000 }} />);
    fireEvent.click(screen.getByTestId('alert-side-below'));
    fireEvent.change(screen.getByTestId('alert-price'), { target: { value: '۱۳۵٬۰۰۰' } });
    expect(screen.getByTestId('alert-immediate').textContent).toContain('همین حالا');
    fireEvent.keyDown(screen.getByTestId('alert-price'), { key: 'Enter' });
    expect(usePriceAlertStore.getState().alerts).toHaveLength(1);
    expect(usePriceAlertStore.getState().alerts[0]).toMatchObject({
      symbol: 'فولاد',
      side: 'below',
      price: 135000,
    });
  });

  it('ورودیِ بی‌عدد افزودن را جلو می‌گیرد و هیچ هشدارِ ساختگی ساخته نمی‌شود', () => {
    render(<PriceAlertsPanel symbol="فولاد" boardRow={null} />);
    fireEvent.change(screen.getByTestId('alert-price'), { target: { value: 'abc' } });
    expect(screen.getByTestId('alert-error').textContent).toContain('بزرگ‌تر از صفر');
    expect(screen.getByTestId('alert-empty')).toBeInTheDocument();
  });

  it('حذفِ هشدار از لیست، لیست را خالی می‌کند', () => {
    const id = usePriceAlertStore.getState().addAlert({ symbol: 'خودرو', side: 'above', price: 200000 })!;
    render(<PriceAlertsPanel symbol="خودرو" boardRow={{ p_last: 190000 }} />);
    expect(screen.getByTestId(`alert-row-${id}`)).toBeInTheDocument();
    fireEvent.click(screen.getByTestId(`alert-remove-${id}`));
    expect(screen.getByTestId('alert-empty')).toBeInTheDocument();
  });

  it('نگهدارِ شمارشِ فعال در نوارِ بالا با افزودن تازه می‌شود', async () => {
    const { FtsToolbar } = await import('@features/technical/nahayatnegar/components/FtsToolbar');
    const noop = () => {};
    render(
      <FtsToolbar
        symbolName="فولاد"
        companyName="فولاد مبارکه"
        onOpenSymbolSearch={noop}
        activeTimeframe="D"
        onTimeframeChange={noop}
        activeCandleType="candle_solid"
        onCandleTypeChange={noop}
        activeAdjustment="combined"
        onAdjustmentChange={noop}
        onOpenIndicators={noop}
        isFtsActive={false}
        onToggleFts={noop}
        isFullscreen={false}
        onToggleFullscreen={noop}
      />,
    );
    expect(screen.getByTestId('price-alert-bell').textContent).toContain('🔔');
    usePriceAlertStore.getState().addAlert({ symbol: 'فولاد', side: 'above', price: 125000 });
    await waitFor(() => expect(screen.getByTestId('price-alert-bell').textContent).toContain('۱'));
    fireEvent.click(screen.getByTestId('price-alert-bell'));
    expect(screen.getByTestId('price-alerts-panel')).toBeInTheDocument();
    // نمادِ پیش‌فرضِ فرم همان نمادِ بازِ چارت است
    expect((screen.getByTestId('alert-symbol') as HTMLInputElement).value).toBe('فولاد');
    // کرشِ تعاملیِ زنده: پنل داخلِ هدری است که با هر کلیک می‌بندد؛ کلیکِ داخلِ
    // پنل نباید به هدر برسد، وگرنه همان اولین انتخاب پنل را می‌دزدد
    fireEvent.click(screen.getByTestId('alert-side-below'));
    expect(screen.getByTestId('price-alerts-panel')).toBeInTheDocument();
    fireEvent.change(screen.getByTestId('alert-price'), { target: { value: '۱۲۵٬۰۰۰' } });
    expect(screen.getByTestId('price-alerts-panel')).toBeInTheDocument();
  });
});
