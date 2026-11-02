/**
 * frontend-v2/src/features/technical/ui/__tests__/CandleEdgeCard.test.tsx
 *
 * آزمون‌های واحد و یکپارچگی کارت لبه آماری (CandleEdgeCard):
 * ۱. رندر ساختار کارت و نمایش عنوان و رژیم بازار
 * ۲. نمایش نرخ برد تاریخی ۱، ۳ و ۵ کندل آینده با ارقام فارسی
 * ۳. نمایش فاکتور سود (PF) و نسبت سود به زیان (R/R)
 * ۴. سوئیچ روشن/خاموش کردن زون‌های SMC و به‌روزرسانی استور
 * ۵. نمایش الگوهای اخیر پرایس‌اکشن و بج‌های صعودی/نزولی
 * ۶. نمایش زون‌های فعال نقدینگی FVG و Order Block
 */

import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { CandleEdgeCard } from '../CandleEdgeCard';
import { useTechnicalStore } from '../../model/technicalStore';
import type { CandleEdgeReport } from '../../model/types';

const MOCK_EDGE_REPORT: CandleEdgeReport = {
  symbol: 'FOOLAD',
  patternName: 'Bullish Engulfing',
  winRate1Bar: 0.65,
  winRate3Bar: 0.72,
  winRate5Bar: 0.68,
  profitFactor: 2.15,
  riskRewardRatio: 2.4,
  sampleCount: 350,
  marketRegime: 'TRENDING_BULL',
  activeZones: [
    {
      id: 'fvg-1',
      type: 'FVG',
      isBullish: true,
      top: 15200,
      bottom: 14800,
      equilibrium: 15000,
      startIndex: 10,
      startTs: 1730000000,
      mitigated: false,
    },
    {
      id: 'ob-1',
      type: 'ORDER_BLOCK',
      isBullish: false,
      top: 16500,
      bottom: 16100,
      equilibrium: 16300,
      startIndex: 22,
      startTs: 1730100000,
      mitigated: false,
    },
  ],
  recentStructures: [
    {
      type: 'BOS',
      isBullish: true,
      price: 15400,
      timestamp: 1730050000,
    },
  ],
};

describe('CandleEdgeCard', () => {
  beforeEach(() => {
    useTechnicalStore.getState().reset();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders card container with symbol and market regime', () => {
    render(<CandleEdgeCard symbol="FOOLAD" data={MOCK_EDGE_REPORT} />);

    expect(screen.getByTestId('candle-edge-card')).toBeDefined();
    expect(screen.getByText(/لبه آماری و SMC/)).toBeDefined();
    expect(screen.getByText('روند صعودی')).toBeDefined();
  });

  it('renders historical win rates for 1, 3, and 5 forward bars', () => {
    render(<CandleEdgeCard data={MOCK_EDGE_REPORT} />);

    expect(screen.getByText('۱ کندل بعد')).toBeDefined();
    expect(screen.getByText('۳ کندل بعد')).toBeDefined();
    expect(screen.getByText('۵ کندل بعد')).toBeDefined();

    // نرخ‌های برد ۶۵٪، ۷۲٪، ۶۸٪ با ارقام فارسی
    expect(screen.getByText('۶۵٪')).toBeDefined();
    expect(screen.getByText('۷۲٪')).toBeDefined();
    expect(screen.getByText('۶۸٪')).toBeDefined();
  });

  it('renders profit factor and risk/reward ratio', () => {
    render(<CandleEdgeCard data={MOCK_EDGE_REPORT} />);

    expect(screen.getByText('فاکتور سود (PF)')).toBeDefined();
    expect(screen.getByText('نسبت سود/زیان (R/R)')).toBeDefined();
    expect(screen.getByText(/۲[٫\.]۱۵/)).toBeDefined();
    expect(screen.getByText(/۲[٫\.]۴/)).toBeDefined();
  });

  it('displays detected pattern with bullish badge', () => {
    render(<CandleEdgeCard data={MOCK_EDGE_REPORT} />);

    expect(screen.getByText('الگوی اخیر:')).toBeDefined();
    expect(screen.getByText('پوشای صعودی')).toBeDefined();
  });

  it('toggles showSMCZones when switch button is clicked', () => {
    render(<CandleEdgeCard data={MOCK_EDGE_REPORT} />);

    const switchBtn = screen.getByRole('switch');
    expect(useTechnicalStore.getState().showSMCZones).toBe(false);

    fireEvent.click(switchBtn);
    expect(useTechnicalStore.getState().showSMCZones).toBe(true);

    fireEvent.click(switchBtn);
    expect(useTechnicalStore.getState().showSMCZones).toBe(false);
  });

  it('displays active liquidity zones (FVG and Order Block)', () => {
    render(<CandleEdgeCard data={MOCK_EDGE_REPORT} />);

    expect(screen.getByText('زون‌های نقدینگی (SMC)')).toBeDefined();
    expect(screen.getByText('FVG')).toBeDefined();
    expect(screen.getByText('ORDER_BLOCK')).toBeDefined();
  });

  it('handles empty active zones with friendly message', () => {
    const emptyZonesReport: CandleEdgeReport = {
      ...MOCK_EDGE_REPORT,
      activeZones: [],
    };

    render(<CandleEdgeCard data={emptyZonesReport} />);
    expect(screen.getByText('هیچ زون فعال مصرف‌نشده‌ای یافت نشد')).toBeDefined();
  });

  it('toggles interactive traders educational guide with clear explanations of win rate and patterns', () => {
    const shootingStarReport: CandleEdgeReport = {
      ...MOCK_EDGE_REPORT,
      patternName: 'Shooting Star',
      marketRegime: 'TRENDING_BEAR',
    };

    render(<CandleEdgeCard data={shootingStarReport} />);

    // پنل ابتدا بسته است
    expect(screen.queryByTestId('traders-guide-panel')).toBeNull();

    // کلیک روی دکمه راهنما (؟)
    const guideBtn = screen.getByTestId('toggle-guide-btn');
    fireEvent.click(guideBtn);

    // پنل آموزشی باز می‌شود
    const guidePanel = screen.getByTestId('traders-guide-panel');
    expect(guidePanel).toBeDefined();

    // تشریح کالبدشکافی شهاب ثاقب
    expect(guidePanel.textContent).toContain('کالبدشکافی الگوی شهاب ثاقب');
    expect(guidePanel.textContent).toContain('فروشندگان');
    expect(guidePanel.textContent).toContain('شناسایی سود');

    // تشریح مفهوم نرخ برد تاریخی ۱، ۳ و ۵ کندل
    expect(guidePanel.textContent).toContain('نرخ برد تاریخی');
    expect(guidePanel.textContent).toContain('کندل آینده');

    // بستن پنل
    fireEvent.click(guideBtn);
    expect(screen.queryByTestId('traders-guide-panel')).toBeNull();
  });

  it('switches to famous symbols watchlist tab and selects a symbol on click', () => {
    render(<CandleEdgeCard symbol="FOOLAD" data={MOCK_EDGE_REPORT} />);

    const symbolsTabBtn = screen.getByTestId('tab-symbols-btn');
    fireEvent.click(symbolsTabBtn);

    const watchlist = screen.getByTestId('famous-symbols-watchlist');
    expect(watchlist).toBeDefined();
    expect(screen.getByText('دیده‌بان ۲۰ نماد شاخص')).toBeDefined();

    // بررسی وجود نمادهای معروف فولاد، فملی، شستا
    expect(screen.getByTestId('symbol-item-فولاد')).toBeDefined();
    expect(screen.getByTestId('symbol-item-فملی')).toBeDefined();
    expect(screen.getByTestId('symbol-item-شستا')).toBeDefined();

    // کلیک روی فملی برای تغییر نماد فعال
    const feliBtn = screen.getByTestId('symbol-item-فملی');
    fireEvent.click(feliBtn);

    expect(useTechnicalStore.getState().selectedSymbol).toBe('فملی');
  });

  it('switches to institutional SMC zones tab and inspects equilibrium and mitigation', () => {
    render(<CandleEdgeCard symbol="FOOLAD" data={MOCK_EDGE_REPORT} />);

    const smcTabBtn = screen.getByTestId('tab-smc-btn');
    fireEvent.click(smcTabBtn);

    const smcPanel = screen.getByTestId('institutional-smc-panel');
    expect(smcPanel).toBeDefined();

    expect(smcPanel.textContent).toContain('تقاضا (Demand)');
    expect(smcPanel.textContent).toContain('عرضه (Supply)');
    expect(smcPanel.textContent).toContain('۵۰٪ EQ');
    expect(smcPanel.textContent).toContain('فعال');
  });
});

