// تست سیگنال پرتفوی: حد ضرر، تمرکز، غیبت و ظرفیت‌سنجی صنعت
import { describe, expect, it } from 'vitest';
import { BaseSignal, PortfolioPayload } from '@contracts/index';
import {
  INDUSTRY_RISK_CAP_PCT,
  industryCapacity,
  portfolioSignal,
} from '@features/portfolio/model/portfolioSignals';

describe('سیگنال پرتفوی', () => {
  it('نبود تصمیم ⇒ رأی ظرفیت‌سنجی (نه بدون داده)', () => {
    const s = portfolioSignal({ symbol: 'شپنا', decision: null, currentPrice: 1000, sectorUsedPct: 5 }, 1726000000000);
    expect(s.direction).not.toBe('neutral');
    expect(s.confidence).not.toBe('nodata');
    expect(s.score).not.toBeNull();
    expect(s.score).toBeGreaterThan(0);
    expect(BaseSignal.safeParse(s).success).toBe(true);
    expect(PortfolioPayload.safeParse(s.payload).success).toBe(true);
  });

  it('ظرفیت کامل صنعت ⇒ رأی صعودی میانه', () => {
    const s = portfolioSignal({ symbol: 'شپنا', decision: null, currentPrice: 1000, sectorUsedPct: 0 }, 1726000000000);
    expect(s.direction).toBe('bullish');
    expect(s.confidence).toBe('medium');
    expect(s.rationale).toContain('ظرفیت');
  });

  it('اشباع صنعت (۲۵٪ مصرف شده) ⇒ رأی نزولی با سقف ۲۰٪', () => {
    const s = portfolioSignal({ symbol: 'شپنا', decision: null, currentPrice: 1000, sectorUsedPct: 25 }, 1726000000000);
    expect(s.direction).toBe('bearish');
    expect(s.rationale).toContain('سقف');
    expect(s.rationale).toContain('۲۰');
  });

  it('نگهداری سالم خنثی میانه می دهد', () => {
    const s = portfolioSignal(
      { symbol: 'شپنا', decision: { symbol: 'شپنا', status: 'accept', weight_eff_pct: 10, stop_loss: 900, reason: null }, currentPrice: 1000 },
      1726000000000,
    );
    expect(s.direction).toBe('neutral');
    expect(s.score).toBe(55);
    expect(s.payload.decision).toBe('accept');
  });

  it('شکست حد ضرر نزولی قوی می دهد', () => {
    const s = portfolioSignal(
      { symbol: 'شپنا', decision: { symbol: 'شپنا', status: 'accept', weight_eff_pct: 10, stop_loss: 1100, reason: null }, currentPrice: 1000 },
      1726000000000,
    );
    expect(s.direction).toBe('bearish');
    expect(s.score).toBe(20);
    expect(s.confidence).toBe('high');
  });

  it('تمرکز بالای ۲۵ درصد هشدار می دهد', () => {
    const s = portfolioSignal(
      { symbol: 'شپنا', decision: { symbol: 'شپنا', status: 'accept', weight_eff_pct: 30, stop_loss: null, reason: null }, currentPrice: 1000 },
      1726000000000,
    );
    expect(s.score).toBe(45);
    expect(s.payload.alerts.length).toBeGreaterThan(0);
  });

  it('وزن صنعت با نماد جدید از سقف ۲۰٪ بگذرد ⇒ هشدار', () => {
    const s = portfolioSignal(
      {
        symbol: 'شپنا',
        decision: { symbol: 'شپنا', status: 'accept', weight_eff_pct: 15, stop_loss: null, reason: null },
        currentPrice: 1000,
        sectorUsedPct: 12,
      },
      1726000000000,
    );
    expect(s.payload.alerts.length).toBeGreaterThan(0);
    expect(s.payload.alerts[0]).toContain('۲۰');
  });

  it('حذف شده نزولی ملایم می دهد', () => {
    const s = portfolioSignal(
      { symbol: 'شپنا', decision: { symbol: 'شپنا', status: 'reject', weight_eff_pct: null, stop_loss: null, reason: 'بنیادی ضعیف' }, currentPrice: null },
      1726000000000,
    );
    expect(s.direction).toBe('bearish');
    expect(s.score).toBe(35);
    expect(s.rationale).toContain('بنیادی ضعیف');
  });
});

describe('ظرفیت‌سنجی صنعت (Capacity Score)', () => {
  it('سقف ریسک صنعت ۲۰٪ است', () => {
    expect(INDUSTRY_RISK_CAP_PCT).toBe(20);
  });

  it('صنعت خالی ⇒ ظرفیت کامل ۲۰٪', () => {
    const c = industryCapacity(0);
    expect(c.remainingPct).toBe(20);
    expect(c.score).toBe(100);
  });

  it('مصرف ۱۲٪ ⇒ ظرفیت ۸٪ با نمره ۴۰', () => {
    const c = industryCapacity(12);
    expect(c.remainingPct).toBe(8);
    expect(c.score).toBe(40);
  });

  it('مصرف ۲۵٪ (بیش از سقف) ⇒ ظرفیت صفر', () => {
    const c = industryCapacity(25);
    expect(c.remainingPct).toBe(0);
    expect(c.score).toBe(0);
    expect(c.note).toContain('پر شده');
  });

  it('داده صنعت نامشخص ⇒ ظرفیت کامل با توضیح', () => {
    const c = industryCapacity(null);
    expect(c.remainingPct).toBe(20);
    expect(c.score).toBe(100);
    expect(c.note).toContain('مشخص نیست');
  });
});
