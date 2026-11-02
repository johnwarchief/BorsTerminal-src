/**
 * frontend-v2/src/features/technical/model/streamingIndicators.ts
 *
 * موتور محاسباتی استریمینگ اندیکاتورهای تکنیکال با کتابخانه بومی trading-signals:
 * پشتیبانی از پردازش تیک‌به‌تیک و افزایشی (O(1)) بدون نیاز به محاسبه مجدد تاریخچه
 * جهت دستیابی به ۱۸۰ فریم بر ثانیه در زمان اتصال به وب‌سوکت تابلوی بازار.
 */

import { SMA, EMA, RSI, MACD, BollingerBands, ATR } from 'trading-signals';
import type { Candle } from './types';

export interface IndicatorConfig {
  smaPeriod?: number;
  emaPeriod?: number;
  rsiPeriod?: number;
  macdFast?: number;
  macdSlow?: number;
  macdSignal?: number;
  bbPeriod?: number;
  bbStdDev?: number;
  atrPeriod?: number;
}

export interface StreamingIndicatorValues {
  sma: number | null;
  ema: number | null;
  rsi: number | null;
  macd: {
    macd: number;
    signal: number;
    histogram: number;
  } | null;
  bollingerBands: {
    upper: number;
    middle: number;
    lower: number;
  } | null;
  atr: number | null;
}

export class StreamingIndicatorEngine {
  private config: Required<IndicatorConfig>;
  private sma: SMA;
  private ema: EMA;
  private rsi: RSI;
  private macd: MACD;
  private bb: BollingerBands;
  private atr: ATR;
  private latestValues: StreamingIndicatorValues;

  constructor(config?: IndicatorConfig) {
    this.config = {
      smaPeriod: config?.smaPeriod ?? 20,
      emaPeriod: config?.emaPeriod ?? 20,
      rsiPeriod: config?.rsiPeriod ?? 14,
      macdFast: config?.macdFast ?? 12,
      macdSlow: config?.macdSlow ?? 26,
      macdSignal: config?.macdSignal ?? 9,
      bbPeriod: config?.bbPeriod ?? 20,
      bbStdDev: config?.bbStdDev ?? 2,
      atrPeriod: config?.atrPeriod ?? 14,
    };

    this.sma = new SMA(this.config.smaPeriod);
    this.ema = new EMA(this.config.emaPeriod);
    this.rsi = new RSI(this.config.rsiPeriod);
    this.macd = new MACD(
      new EMA(this.config.macdFast),
      new EMA(this.config.macdSlow),
      new EMA(this.config.macdSignal)
    );
    this.bb = new BollingerBands(this.config.bbPeriod, this.config.bbStdDev);
    this.atr = new ATR(this.config.atrPeriod);

    this.latestValues = {
      sma: null,
      ema: null,
      rsi: null,
      macd: null,
      bollingerBands: null,
      atr: null,
    };
  }

  /**
   * اعمال کندل جدید و به‌روزرسانی افزایشی کلیه شاخص‌ها
   */
  public update(candle: Candle, replace = false): StreamingIndicatorValues {
    // بروزرسانی میانگین‌های متحرک و اسیلاتورها با قیمت پایانی
    this.sma.update(candle.close, replace);
    this.ema.update(candle.close, replace);
    this.rsi.update(candle.close, replace);
    this.macd.update(candle.close, replace);
    this.bb.update(candle.close, replace);

    // شاخص دامنه واقعی میانگین (ATR) نیازمند High, Low, Close است
    this.atr.update(
      {
        high: candle.high,
        low: candle.low,
        close: candle.close,
      },
      replace
    );

    let smaVal: number | null = null;
    if (this.sma.isStable) {
      try {
        const res = this.sma.getResult();
        smaVal = res !== null ? Number(res) : null;
      } catch {
        smaVal = null;
      }
    }

    let emaVal: number | null = null;
    if (this.ema.isStable) {
      try {
        const res = this.ema.getResult();
        emaVal = res !== null ? Number(res) : null;
      } catch {
        emaVal = null;
      }
    }

    let rsiVal: number | null = null;
    if (this.rsi.isStable) {
      try {
        const res = this.rsi.getResult();
        rsiVal = res !== null ? Number(res) : null;
      } catch {
        rsiVal = null;
      }
    }

    let macdVal: { macd: number; signal: number; histogram: number } | null = null;
    if (this.macd.isStable) {
      try {
        const res = this.macd.getResult();
        if (res) {
          macdVal = {
            macd: Number(res.macd),
            signal: Number(res.signal),
            histogram: Number(res.histogram),
          };
        }
      } catch {
        macdVal = null;
      }
    }

    let bbVal: { upper: number; middle: number; lower: number } | null = null;
    if (this.bb.isStable) {
      try {
        const res = this.bb.getResult();
        if (res) {
          bbVal = {
            upper: Number(res.upper),
            middle: Number(res.middle),
            lower: Number(res.lower),
          };
        }
      } catch {
        bbVal = null;
      }
    }

    let atrVal: number | null = null;
    if (this.atr.isStable) {
      try {
        const res = this.atr.getResult();
        atrVal = res !== null ? Number(res) : null;
      } catch {
        atrVal = null;
      }
    }

    this.latestValues = {
      sma: smaVal,
      ema: emaVal,
      rsi: rsiVal,
      macd: macdVal,
      bollingerBands: bbVal,
      atr: atrVal,
    };

    return this.latestValues;
  }

  /**
   * بارگذاری دسته‌ای کندل‌های تاریخی برای مقداردهی اولیه استریم
   */
  public updateBatch(candles: Candle[]): StreamingIndicatorValues[] {
    const results: StreamingIndicatorValues[] = [];
    for (const candle of candles) {
      results.push(this.update(candle));
    }
    return results;
  }

  /**
   * بازگرداندن آخرین مقادیر محاسبه‌شده
   */
  public getLatestValues(): StreamingIndicatorValues {
    return this.latestValues;
  }

  /**
   * بررسی پایداری و آمادگی تمام اندیکاتورها (پایان دوره وارم‌آپ)
   */
  public isStable(): boolean {
    return (
      this.sma.isStable &&
      this.ema.isStable &&
      this.rsi.isStable &&
      this.macd.isStable &&
      this.bb.isStable &&
      this.atr.isStable
    );
  }

  /**
   * بازنشانی کامل وضعیت اندیکاتورها
   */
  public reset(): void {
    this.sma = new SMA(this.config.smaPeriod);
    this.ema = new EMA(this.config.emaPeriod);
    this.rsi = new RSI(this.config.rsiPeriod);
    this.macd = new MACD(
      new EMA(this.config.macdFast),
      new EMA(this.config.macdSlow),
      new EMA(this.config.macdSignal)
    );
    this.bb = new BollingerBands(this.config.bbPeriod, this.config.bbStdDev);
    this.atr = new ATR(this.config.atrPeriod);

    this.latestValues = {
      sma: null,
      ema: null,
      rsi: null,
      macd: null,
      bollingerBands: null,
      atr: null,
    };
  }
}
