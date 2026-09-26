// __tests__/mabna-indicators.spec.ts
// تستِ نُه مطالعهٔ rahavard365 (mabnaIndicators.ts). عددهایِ انتظاری «با دست» روی
// کاغذ حساب شده‌اند و همان حساب زیرِ هر تست نوشته شده تا اگر روزی فرمول عوض شد،
// عددِ تست مستقل از خروجیِ پیاده‌سازی قابل بازتولید باشد.
// شواهدِ فرمول: برش‌های Temp/rhv/js/study_*.js از باندلِ rahavard
// (آفست: DT 5406410 | Z 5408420 | SQZ 5411620 | HT 5414043 | SR 5418689 |
//  WT 5422874 | FIBB 5425907 | WTC 5429832 | VIX 5433623).

import { describe, expect, it } from 'vitest';

import {
  MABNA_INDICATORS,
  MABNA_INDICATOR_LIST,
  MABNA_TEMPLATES,
  pineStd,
  registerMabnaIndicators,
  type MabnaCandle,
  type MabnaParam,
  type MabnaRow,
} from '@features/technical/lib/mabnaIndicators';
import { MABNA_INDICATORS as CATALOG, TV_INDICATORS } from '@features/technical/lib/tvIndicatorCatalog';

const bar = (open: number, high: number, low: number, close: number, volume = 1000): MabnaCandle => ({
  open,
  high,
  low,
  close,
  volume,
});

const run = (name: string, data: MabnaCandle[], params?: MabnaParam[]): MabnaRow[] => {
  const tpl = MABNA_TEMPLATES[name];
  if (!tpl) throw new Error(`no template ${name}`);
  return tpl.calc(data, { calcParams: params ?? tpl.calcParams });
};

// «مقدارِ داده» در برابر «خطوطِ ثابت/کدِ رنگ»: در بدنهٔ rahavard بعضی plotها
// بی‌قیدوشرط از کندلِ اول مقدار دارند (۰ و ترازهای WT، باندهای Z، sqz=0) و در TV
// هم همان‌طور کشیده می‌شوند؛ تستِ سریِ کوتاه فقط مقدارهای داده را می‌سنجد.
const DATA_KEYS: Record<string, string[]> = {
  MabnaDT: ['k', 'd'],
  MabnaZScore: ['z'],
  MabnaSQZMOM: ['momentum'],
  MabnaHalfTrend: ['atrHigh', 'atrLow'],
  MabnaSRLevels: ['resistance', 'support', 'bullBreak', 'bearBreak'],
  MabnaWaveTrend: ['wt', 'avg', 'hist'],
  MabnaFibBB: ['basis', 'up1', 'dn1'],
  MabnaWaveTrendCross: ['wt', 'avg', 'hist', 'cross'],
  MabnaVixFix: ['vix', 'rangeHigh', 'rangeLow', 'upperBand'],
};

describe('Z Score — آفست 5408420', () => {
  it('z = (src - sma) / stdev با حسابِ دستی روی ۱..۵', () => {
    // پنجرهٔ ۵تاییِ [1,2,3,4,5]:
    //   sma = (1+2+3+4+5)/5 = 3
    //   stdev (مخرجِ N): sqrt(((1-3)²+(2-3)²+0+(4-3)²+(5-3)²)/5) = sqrt(10/5) = sqrt(2)
    //   z(آخرین) = (5-3)/sqrt(2) = sqrt(2)
    const rows = run(
      'MabnaZScore',
      [1, 2, 3, 4, 5].map((v) => bar(v, v, v, v)),
      [5, 2, 1, 'close'],
    );
    expect(rows.slice(0, 4).every((r) => r.z === undefined)).toBe(true);
    expect(rows[4].z).toBeCloseTo(Math.SQRT2, 10);
    // باندها StdDevs=2 و StdDevs_=1 (خطوطِ ثابتِ بدنه، trackPrice)
    expect(rows[4].stdDevsBand).toBe(2);
    expect(rows[4].negStdDevsBand).toBe(-2);
    expect(rows[4].underStdDevsBand).toBe(1);
    expect(rows[4].negUnderStdDevsBand).toBe(-1);
    // سطلِ رنگِ سطر ۱۱۵: z=1.4142 در بازهٔ [1,1.5) → کدِ ۳۰۰
    expect(rows[4].barColor).toBe(300);
  });

  it('سریِ تخت (stdev=0) na می‌دهد نه صفر', () => {
    // مخرجِ صفر در Pine = na → نقطه نباید روی چارت بیفتد
    const rows = run(
      'MabnaZScore',
      Array.from({ length: 6 }, () => bar(10, 10, 10, 10)),
      [5, 2, 1, 'close'],
    );
    expect(rows.every((r) => r.z === undefined)).toBe(true);
  });

  it('منبعِ src واقعاً عوض می‌شود (high به‌جای close)', () => {
    // close = [1,2,4]: mean = 7/3 ، Σd² = 16/9+1/9+25/9 = 42/9 → var = 14/9 →
    //   stdev = sqrt(14)/3 = 1.2472191 ، z = (5/3)/(sqrt(14)/3) = 5/sqrt(14) = 1.3363062
    // high = [3,4,9]: mean = 16/3 ، Σd² = 49/9+16/9+121/9 = 186/9 → var = 62/9 →
    //   z = (11/3)/(sqrt(62)/3) = 11/sqrt(62) = 1.3970014
    const data = [bar(1, 3, 1, 1), bar(2, 4, 2, 2), bar(4, 9, 4, 4)];
    const zClose = run('MabnaZScore', data, [3, 2, 1, 'close'])[2].z;
    const zHigh = run('MabnaZScore', data, [3, 2, 1, 'high'])[2].z;
    expect(zClose).toBeCloseTo(5 / Math.sqrt(14), 10);
    expect(zHigh).toBeCloseTo(11 / Math.sqrt(62), 10);
  });
});

describe('WaveTrend — آفست 5422874', () => {
  // هندسه: high = low = close = x → hlc3 = (x+x+x)/3 = x؛ دوره‌ها n1=2، n2=2
  // (پنجرهٔ میانگین در بدنه hardcode روی ۴ است). ema با بذرِ SMA و k=2/(2+1)=2/3:
  //   esa  = ema(x,2):        _ 1.5 3.1666667 6.3888889 12.7962963 25.5987654 51.1995885 102.3998628
  //   |x-esa|:                _ 0.5 0.8333333 1.6111111  3.2037037  6.4012346 12.8004115  25.6001372
  //   d    = ema(|x-esa|,2):  _ _   0.6666667 1.2962963  2.5679012  5.1234568 10.2414266  20.4805670
  //   ci   = (x-esa)/(0.015·d): _ _ 83.3333333 82.8571429 83.1730769 83.2931727 83.3244040 83.3314728
  //   wt   = ema(ci,2):       _ _ _ 83.0952381 83.1471306 83.2444920 83.2977666 83.3202374
  //   avg  = sma(wt,4):       _ _ _ _ _ _ 83.1961568 83.2524067
  //   hist = wt-avg:          _ _ _ _ _ _  0.1016098  0.0678308
  const x = [1, 2, 4, 8, 16, 32, 64, 128];
  const rows = run(
    'MabnaWaveTrend',
    x.map((v) => bar(v, v, v, v)),
    [2, 2, 60, 53, -60, -53],
  );

  it('wt با بذرِ SMA و k=2/3 پیش می‌رود', () => {
    expect(rows[2].wt).toBeUndefined(); // دو ciِ اول برای بذرِ دورهٔ ۲ کافی نیست
    expect(rows[3].wt).toBeCloseTo((83.3333333 + 82.8571429) / 2, 6);
    expect(rows[7].wt).toBeCloseTo(83.3202374, 6);
  });

  it('میانگینِ ۴تایی و هیستوگرام (عددِ ۴ در بدنه hardcode است)', () => {
    expect(rows[5].avg).toBeUndefined(); // فقط سه wtِ معتبر هست
    expect(rows[6].avg).toBeCloseTo((83.0952381 + 83.1471306 + 83.244492 + 83.2977666) / 4, 6);
    expect(rows[7].avg).toBeCloseTo(83.2524067, 6);
    expect(rows[7].hist).toBeCloseTo(83.3202374 - 83.2524067, 6);
  });

  it('ترازها و خطِ صفر مثلِ بدنه از کندلِ اول هستن', () => {
    expect(rows[0]).toMatchObject({ zero: 0, ob1: 60, os1: -60, ob2: 53, os2: -53 });
  });
});

describe('WaveTrend with Crosses — آفست 5429832', () => {
  // همان هستهٔ WT روی x = [1,2,4,8,16,32,64,128,64,32,16,8,4,2,1] (سریِ بالا و بعد
  // آینه‌وار). wt و avg از جدولِ بالا در کندل‌های ۶ و ۷ معتبرند و بعد از قله
  // (کندل ۷=۱۲۸) wt سقوط می‌کند:
  //   کندل ۷: wt=83.3202 > avg=83.2524 | کندل ۸: wt=-9.2631 < avg=60.1498 → تقاطعِ نزولی
  //   کندل ۱۱: wt=-51.8317 < avg=-40.6061 | کندل ۱۲: wt=-47.6775 > avg=-50.2097 → تقاطعِ صعودی
  // کدِ رنگ در بدنه `b-y>0?0:1` است → نزولی ۰ (قرمز)، صعودی ۱ (سبز).
  const x = [1, 2, 4, 8, 16, 32, 64, 128, 64, 32, 16, 8, 4, 2, 1];
  const rows = run(
    'MabnaWaveTrendCross',
    x.map((v) => bar(v, v, v, v)),
    [2, 2, 60, 53, -60, -53],
  );

  it('تقاطع فقط در کندل‌هایِ ردشدن علامت می‌زند', () => {
    expect(rows.map((r, i) => (r.cross === undefined ? -1 : i)).filter((i) => i >= 0)).toEqual([8, 12]);
  });

  it('مقدارِ shape خودِ avg است و رنگ از جهتِ تقاطع می‌آید', () => {
    for (const i of [8, 12]) {
      expect(rows[i].cross).toBe(rows[i].avg);
    }
    expect(rows[8].crossColor).toBe(0); // avg > wt → نزولی
    expect(rows[12].crossColor).toBe(1); // wt > avg → صعودی
    // بازبینیِ مستقل از همان ردیفها: علامتِ (wt-avg) باید در این دو کندل عوض شده باشد
    expect(Math.sign(rows[7].wt! - rows[7].avg!)).not.toBe(Math.sign(rows[8].wt! - rows[8].avg!));
    expect(Math.sign(rows[11].wt! - rows[11].avg!)).not.toBe(Math.sign(rows[12].wt! - rows[12].avg!));
  });
});

describe('Squeeze Momentum — آفست 5411620 (مبتنی بر True Range)', () => {
  // ۴۰ کندل: high=110، low=90، بسته‌ها یکی‌درمیان ۹۹/۱۰۱ (کندلِ زوج = ۹۹)، open=100.
  //   TR: کندلِ اول = 110-90 = 20؛ بقیه max(20, |110-close[1]|∈{9,11}, |90-close[1]|∈{11,9}) = 20
  //   BB: sma(close,20)=100 (ده تا ۹۹ و ده تا ۱۰۱)، stdev(مخرج N)=1
  //       up = 100+2·1 = 102 ، dn = 100-2 = 98
  //   KC: sma(TR,20)=20 → ku = 100+1.5·20 = 130 ، kl = 100-30 = 70
  //   on = dn>kl && up<ku = (98>70) && (102<130) → true → sqzColor=1
  //   avgHL = (110+90)/2 = 100 ، ji = (100 + sma(close,20))/2 = 100 → mom = close-100 = ±1
  const data = Array.from({ length: 40 }, (_, i) => bar(100, 110, 90, i % 2 === 0 ? 99 : 101));
  const rows = run('MabnaSQZMOM', data);

  it('بندِ KC با True Range ساخته می‌شود و squeeze روشن است', () => {
    expect(rows[19].sqzColor).toBe(1); // پیش از آنکه linreg مقداری داشته باشد
    expect(rows[38].sqzColor).toBe(1);
  });

  it('مومنتوم = endpointِ رگرسیونِ خطی = -1/7', () => {
    // mom در کندل‌های ۱۹..۳۸ = [+1,-1,+1,…,-1] (کندل ۱۹ فرد → +1)
    //   x̄ = 9.5 ، ȳ = 0 ، Σ(x-x̄)² = 665
    //   Σ y·(x-x̄) = (مجموعِ j زوج: -9.5-7.5-…+8.5 = -5) - (مجموعِ j فرد: -8.5-…+9.5 = 5) = -10
    //   endpoint = ȳ + (-10/665)·(19-9.5) = -95/665 = -1/7 = -0.142857142857
    expect(rows[37].momentum).toBeUndefined(); // بیستمیِ mom در کندل ۳۸ کامل می‌شود
    expect(rows[38].momentum).toBeCloseTo(-1 / 7, 10);
    expect(rows[39].momentum).toBeCloseTo(1 / 7, 10); // پنجرهٔ بعد قرینه است
    // رنگ: مقدار منفی و momِ قبل na → nz(prev)=0 → cur<prev → کدِ ۲ (قرمزِ روشن)
    expect(rows[38].momColor).toBe(2);
    expect(rows[39].momColor).toBe(0); // مثبت و بالاتر از قبل → سبزِ روشن
  });

  it('plot_1 در بدنه صفرِ مطلق است (وضعیت فقط با رنگ نشان می‌دهد)', () => {
    expect(rows[0].sqz).toBe(0);
    expect(rows[39].sqz).toBe(0);
  });

  it('useTrueRange=false دامنه را به high-low می‌برد و وضعیت عوض می‌شود', () => {
    // بسته‌ها ۹۶/۱۰۴ (میانگین ۱۰۰، stdevِ روی N = 4)، high=close+1، low=close-1
    //   BB با mult=1: up = 104±… → mid+4 ، dn = mid-4
    //   high-low = 2 → KC باریک: mid ± 1.5·2 = ±3 → BB بیرونِ KC → off (کد ۲)
    //   TR = max(2, |high_i-close_{i-1}|=9, …) = 9 → KC: mid ± 13.5 → BB داخلِ KC → on (کد ۱)
    const wide = Array.from({ length: 25 }, (_, i) => {
      const c = i % 2 === 0 ? 96 : 104;
      return bar(c, c + 1, c - 1, c);
    });
    const withTR = run('MabnaSQZMOM', wide, [20, 1, 20, 1.5, true]);
    const withoutTR = run('MabnaSQZMOM', wide, [20, 1, 20, 1.5, false]);
    expect(withTR[21].sqzColor).toBe(1);
    expect(withoutTR[21].sqzColor).toBe(2);
  });
});

describe('HalfTrend — آفست 5414043 (مبتنی بر ATR)', () => {
  // صعودِ یکنواخت (ramp): low=100+i، high=102+i، close=101.5+i، open=101+i.
  //   TR = max(2, |high-close[1]|=1.5, |low-close[1]|=0.5) = 2 برای همهٔ کندل‌ها
  //   atr(100) = rma(TR,100) → بذر = میانگینِ ۱۰۰ مقدارِ ۲ = ۲ در کندل ۹۹
  //   d = atr/2 = 1 ، p = channelDeviation·d = 2·1 = 2
  //   کندل ۳: sma(low,2)=102.5 > minHighPrice=102 و close=104.5 > high[1]=103
  //           → تعویید: trend=0، nextTrend=1، maxLowPrice=min(low3,low2)=102
  //   بعد از آن up_i = max(maxLowPrice, up_{i-1}) = low_{i-1} → up(119)=low(118)=218
  const ramp = (n: number) => Array.from({ length: n }, (_, i) => bar(101 + i, 102 + i, 100 + i, 101.5 + i));

  it('پیش از ۱۰۰ کندل کانالِ ATR وجود ندارد (na، نه صفر)', () => {
    const rows = run('MabnaHalfTrend', ramp(99));
    expect(rows.every((r) => r.atrHigh === undefined && r.atrLow === undefined)).toBe(true);
    // خطِ روند از کندلِ اول عدد دارد (در TV هم همین‌طور است): up = maxLowPrice = low[0]؛
    // بعد از تعوییدِ کندل ۳، up_i = low_{i-1} = 99+i → کندل ۹۸ → ۱۹۷
    expect(rows[0].halfTrend).toBe(100);
    expect(rows[98].halfTrend).toBe(197);
  });

  it('خط و کانال روی صعودِ یکنواختِ ۱۲۰کندلی', () => {
    const rows = run('MabnaHalfTrend', ramp(120));
    expect(rows[99].atrHigh).toBeCloseTo(200, 6); // up=198 با p=2
    expect(rows[119].halfTrend).toBeCloseTo(218, 6);
    expect(rows[119].trend).toBe(0); // کدِ palette_0: ۰ = آبی (صعودی)
    expect(rows[119].atrHigh).toBeCloseTo(220, 6);
    expect(rows[119].atrLow).toBeCloseTo(216, 6);
    expect(rows[119].arrowUp).toBeUndefined(); // سیگنال فقط لحظهٔ تعویید است
  });

  it('ریزشِ شارپ روند را عوض می‌کند و برچسبِ فروش می‌زند', () => {
    const data = [...ramp(120), bar(50, 52, 50, 51), bar(48, 50, 46, 47)];
    const rows = run('MabnaHalfTrend', data);
    // کندل ۱۲۰: sma(high,2)=136.5 < maxLowPrice=218 و close=51 < low[1]=219 → trend=1
    // down = prevUp = 218 (خط روی آخرین up می‌ماند — همان کویکِ بدنه)
    expect(rows[120].trend).toBe(1);
    expect(rows[120].halfTrend).toBeCloseTo(218, 6);
    // TR(120) = max(2, |52-220.5|=168.5, |50-220.5|=170.5) = 170.5
    // atr = (2·99 + 170.5)/100 = 3.685 → d = 1.8425 → p = 2·1.8425 = 3.685
    expect(rows[120].atrHigh).toBeCloseTo(221.685, 6);
    expect(rows[120].atrLow).toBeCloseTo(214.315, 6);
    expect(rows[120].sellLabel).toBeCloseTo(221.685, 6); // مقدارِ shape = l
    expect(rows[121].trend).toBe(1);
    expect(rows[121].halfTrend).toBeCloseTo(52, 6); // down = min(minHighPrice=52, prevDown=218)
  });

  it('showChannels=false کانال‌ها را حذف می‌کند نه صفر', () => {
    const rows = run('MabnaHalfTrend', ramp(105), [2, 2, true, false, true]);
    expect(rows[104].atrHigh).toBeUndefined();
    expect(rows[104].atrLow).toBeUndefined();
    expect(rows[104].halfTrend).toBeCloseTo(203, 6);
  });
});

describe('سطوح حمایت/مقاومت با شکست — آفست 5418689', () => {
  const peak = [
    bar(10, 10, 8, 9), bar(11, 11, 9, 10), bar(12, 12, 10, 11),
    bar(13, 20, 12, 19), bar(12, 12, 10, 11), bar(11, 11, 9, 10), bar(12, 12, 10, 11),
  ];

  it('پیوتِ سقف با پنجرهٔ چپ/راست تأیید می‌شود (با یک کندل تأخیر، مثلِ بدنه)', () => {
    // leftBars=2، rightBars=2 → x=3؛ پیوتِ کاندید در کندل ۳ (high=20) وقتی
    // بررسی می‌شود که i-rightBars = 3 → i=5. چپ: 12 و 11 ≤ 20 ✓ ؛ راست: 12 و 11 < 20 ✓
    // اما مقدار در کندلِ *بعد* (۶) مصرف می‌شود: S = prevRawPH
    const rows = run('MabnaSRLevels', peak, [true, 2, 2, 20]);
    expect(rows[4].resistance).toBeUndefined();
    expect(rows[5].resistance).toBeUndefined();
    expect(rows[6].resistance).toBe(20);
    // paint-on-pivot: معادلِ offset:-x → روی خودِ کندلِ پیوت (۳) نشان داده می‌شود
    expect(rows[3].pivotHigh).toBe(20);
    // کفِ ۸ در کندل ۰ پیوت نیست (سمتِ چپ ناقص) → حمایتی هنوز نداریم
    expect(rows[6].support).toBeUndefined();
  });

  it('شکستِ صعودی با تأییدِ حجم روی سطح علامت می‌زند', () => {
    // سطح ۲۰ از کندل ۶ در حالِ اعمال است؛ در کندل ۱۱ close[1]=11 ≤ 20 و close=30 > 20 → F
    // بدنه بر سایه: open-low = 1 و close-open = 10 → !(1 > 10) ✓
    // حجم: ده کندلِ ۱۰۰ و یک کندلِ ۱۰۰۰۰۰ → ema(vol,5)=33400.0 و ema(vol,10)=18263.6
    //       k = 100·(33400-18263.6)/18263.6 ≈ 82.9 > آستانهٔ ۲۰ → W (Break با حجم)
    const data = [
      ...peak,
      bar(11, 11, 9, 10, 100), bar(12, 12, 10, 11, 100), bar(11, 11, 9, 10, 100),
      bar(12, 12, 10, 11, 100), bar(20, 31, 19, 30, 100000),
    ];
    const rows = run('MabnaSRLevels', data, [true, 2, 2, 20]);
    expect(rows[6].resistance).toBe(20);
    expect(rows[10].bullBreak).toBeUndefined(); // هنوز close از سطح نگذشته
    expect(rows[11].bullBreak).toBe(20);
    expect(rows[11].resistance).toBe(20);
    expect(rows[11].bearBreak).toBeUndefined();
  });

  it('showBreaks=false فقط سطوح را می‌گذارد', () => {
    const data = [
      ...peak,
      bar(11, 11, 9, 10, 100), bar(12, 12, 10, 11, 100), bar(11, 11, 9, 10, 100),
      bar(12, 12, 10, 11, 100), bar(20, 31, 19, 30, 100000),
    ];
    const rows = run('MabnaSRLevels', data, [false, 2, 2, 20]);
    expect(rows[11].resistance).toBe(20);
    expect(rows[11].bullBreak).toBeUndefined();
  });
});

describe('Fibonacci BB و DT و VixFix', () => {
  it('Fib-BB: basis = VWMA و فاصله‌ها کسرِ فیبو × (mult·stdev)', () => {
    // hlc3 = [1,2,3] با حجمِ برابر → vwma = (1+2+3)/3 = 2
    // stdev (مخرجِ N) = sqrt(((1-2)²+0+(3-2)²)/3) = sqrt(2/3) → dev = 3·sqrt(2/3)
    const ramp = [1, 2, 3].map((v) => bar(v, v, v, v));
    const rows = run('MabnaFibBB', ramp, [3, 'hlc3', 3]);
    const dev = 3 * Math.sqrt(2 / 3);
    expect(rows[1].basis).toBeUndefined(); // پنجرهٔ ۳تایی در کندل ۲ کامل می‌شود
    expect(rows[2].basis).toBeCloseTo(2, 10);
    expect(rows[2].up1).toBeCloseTo(2 + dev, 10);
    expect(rows[2].dn1).toBeCloseTo(2 - dev, 10);
    expect(rows[2]['up0.5']).toBeCloseTo(2 + 0.5 * dev, 10);
    expect(rows[2]['dn0.764']).toBeCloseTo(2 - 0.764 * dev, 10);
    // حجم‌مدار: با حجمِ ۱۰۰/۱۰۰/۸۰۰ و hlc3 = 1,2,3 →
    //   vwma = (1·100 + 2·100 + 3·800)/(100+100+800) = 2700/1000 = 2.7
    const weighted = run(
      'MabnaFibBB',
      [bar(1, 1, 1, 1, 100), bar(2, 2, 2, 2, 100), bar(3, 3, 3, 3, 800)],
      [3, 'hlc3', 3],
    );
    expect(weighted[2].basis).toBeCloseTo(2.7, 10);
  });

  it('DT: سریِ یکنواختِ صعودی RSIِ ثابت می‌دهد → مخرجِ stoch صفر و در نتیجه na', () => {
    // close = 1..20 با lengthRSI=8 → RSI=100 در همهٔ نقاطِ معتبر → highest=lowest →
    // span=0 → تقسیم بر صفر = na → هیچ‌کدام از K/D ساخته نمی‌شوند (نه صفر)
    const data = Array.from({ length: 20 }, (_, i) => bar(i + 1, i + 1, i, i + 1));
    const rows = run('MabnaDT', data, [8, 5, 3, 3]);
    expect(rows.every((r) => r.k === undefined && r.d === undefined)).toBe(true);
  });

  it('DT: روی نوسانِ معمولی K و D در [۰,۱۰۰] و D میانگینِ سه‌تاییِ K است', () => {
    // زنجیره: RSI(8) از کندل ۸ → stoch(5) از کندل ۱۲ → K=sma(3) از کندل ۱۴ →
    // D=sma(K,3) از کندل ۱۶؛ پس ۲۴ کندل لازم است
    const closes = [10, 11, 10, 12, 11, 13, 12, 14, 13, 15, 14, 16, 15, 17, 16, 18, 17, 19, 18, 20, 19, 21, 20, 22];
    const rows = run('MabnaDT', closes.map((v) => bar(v, v, v - 1, v)));
    const k = rows.map((r) => r.k).filter((v): v is number => v !== undefined);
    const d = rows.map((r) => r.d).filter((v): v is number => v !== undefined);
    expect(k.length).toBeGreaterThan(0);
    for (const v of k) {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(100);
    }
    // D = sma(K,3): اولین D میانگینِ سه Kِ آخر است
    const firstD = rows.findIndex((r) => r.d !== undefined);
    expect(firstD).toBe(16);
    expect(rows[firstD].d).toBeCloseTo((rows[firstD - 2].k! + rows[firstD - 1].k! + rows[firstD].k!) / 3, 10);
    expect(d.length).toBeGreaterThan(0);
  });

  it('VixFix: (highest(close,pd)-low)/highest·100 و خطِ کف', () => {
    // close = low = [3,2,1] و pd=2 → hnif(1) = max(3,2) = 3 → vix(1) = (3-2)/3·100 = 33.3333333
    //                        hnif(2) = max(2,1) = 2 → vix(2) = (2-1)/2·100 = 50
    const data = [bar(3, 3, 3, 3), bar(2, 2, 2, 2), bar(1, 1, 1, 1)];
    const rows = run('MabnaVixFix', data, [2, 2, 2, 3, 0.85, 1.01, true, true]);
    expect(rows[0].vix).toBeUndefined(); // پنجرهٔ highest در کندل ۱ کامل می‌شود
    expect(rows[1].vix).toBeCloseTo(100 / 3, 8);
    expect(rows[2].vix).toBeCloseTo(50, 8);
    // باندِ بولینگر روی vix با bbl=2، mult=2:
    //   sma = (100/3+50)/2 = 125/3 = 41.6666667
    //   stdev(مخرج N) = sqrt(((25/3)²+(25/3)²)/2) = 25/3 = 8.3333333
    //   upper = 125/3 + 2·25/3 = 175/3 = 58.3333333
    expect(rows[1].upperBand).toBeUndefined();
    expect(rows[2].upperBand).toBeCloseTo(175 / 3, 8);
    // rhi = highest(vix,3)·0.85 → پنجرهٔ سه‌تاییِ vix هنوز ناقص است
    expect(rows[2].rangeHigh).toBeUndefined();
    expect(rows[2].rangeLow).toBeUndefined();
    // bottom: در بدنه هیچ na-guard ندارد → vix(2)=50 < upper=58.33 → ۱
    expect(rows[2].bottom).toBe(1);
  });
});

describe('قراردادِ na و ثباتِ عددی', () => {
  /** مولّدِ قطعی (LCG) — fuzz بدونِ وابستگیِ جدید */
  const lcg = (seed: number) => () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);

  const randomSeries = (n: number, seed: number): MabnaCandle[] => {
    const rnd = lcg(seed);
    let price = 50 + rnd() * 50;
    const out: MabnaCandle[] = [];
    for (let i = 0; i < n; i++) {
      const drift = (rnd() - 0.5) * 6;
      const open = price;
      const close = Math.max(0.01, price + drift);
      const high = Math.max(open, close) + rnd() * 3;
      const low = Math.max(0.01, Math.min(open, close) - rnd() * 3);
      out.push({ open, high, low, close, volume: rnd() * 1e6 });
      price = close;
    }
    return out;
  };

  it('هیچ مطالعه‌ای روی دادهٔ متناهی هرگز NaN/Infinity برنمی‌گرداند', () => {
    const datasets = [
      randomSeries(300, 7),
      randomSeries(300, 991),
      randomSeries(5, 3),
      // بدنهٔ بیمار: صفرِ مطلق، حجمِ صفر، قیمتِ یکسان (تقسیم بر صفرها)
      Array.from({ length: 60 }, () => bar(0, 0, 0, 0, 0)),
      Array.from({ length: 60 }, () => bar(10, 10, 10, 10, 100)),
      // پرشِ عددیِ بزرگ
      Array.from({ length: 60 }, (_, i) => bar(1, 1e9 * (i + 1), 0.5, 1e9 * (i + 1), 1)),
      // بدونِ حجم (فیلدِ volume تعریف‌نشده)
      Array.from({ length: 40 }, (_, i) => ({ open: 10 + i, high: 12 + i, low: 9 + i, close: 11 + i })),
    ];
    for (const data of datasets) {
      for (const tpl of MABNA_INDICATOR_LIST) {
        const rows = tpl.calc(data, { calcParams: tpl.calcParams });
        expect(rows.length, `${tpl.name} تعدادِ سطر`).toBe(data.length);
        for (const [i, row] of rows.entries()) {
          for (const [key, value] of Object.entries(row)) {
            expect(Number.isFinite(value as number), `${tpl.name}[${i}].${key} = ${String(value)}`).toBe(true);
          }
        }
      }
    }
  });

  it('سریِ کوتاه‌تر از دوره، مقدارِ داده نمی‌سازد (و صفر جانشین نمی‌کند)', () => {
    const data = [bar(10, 11, 9, 10.5), bar(10.5, 12, 10, 11.5), bar(11, 13, 10.5, 12.5)];
    for (const tpl of MABNA_INDICATOR_LIST) {
      const rows = tpl.calc(data, { calcParams: tpl.calcParams });
      for (const key of DATA_KEYS[tpl.name]) {
        for (const [i, row] of rows.entries()) {
          expect(row[key], `${tpl.name} روی ${data.length} کندل نباید ${key}[${i}] داشته باشد`).toBeUndefined();
        }
      }
    }
  });

  it('stdev/rma/linreg/tr همان رفتارِ مستندِ Pine را دارند', () => {
    // stdevِ روی N: [2,4,4,4,5,5,7,9] → mean=5 ، Σ(mq)² = 9+1+1+1+0+0+4+16 = 32 → sqrt(32/8)=2
    expect(pineStd.stdev([2, 4, 4, 4, 5, 5, 7, 9], 8)[7]).toBeCloseTo(2, 10);
    // rma وایلدر با بذرِ SMA: دورهٔ ۲ روی [1,1,1,1] → از سطرِ دوم به بعد ۱
    expect(pineStd.rma([1, 1, 1, 1], 2)).toEqual([undefined, 1, 1, 1]);
    // tr کندلِ دوم (close[1]=10): max(20-10, |20-10|, |10-10|) = 10
    expect(pineStd.trueRange([bar(10, 15, 5, 10), bar(10, 20, 10, 15)])[1]).toBe(10);
    // linreg روی [1,2,3] همان خطِ دقیق است → endpoint = 3
    expect(pineStd.linreg([1, 2, 3], 3)[2]).toBeCloseTo(3, 10);
    // stoch با پنجرهٔ تخت مخرجِ صفر دارد → na
    expect(pineStd.stoch([5, 5, 5], 3)[2]).toBeUndefined();
  });
});

describe('کاتالوگ و ثبت', () => {
  it('هر نُه مطالعهٔ کاتالوگ تعریف دارد (و برعکس)', () => {
    expect(CATALOG).toBe(MABNA_INDICATORS);
    expect(CATALOG.length).toBe(9);
    expect(MABNA_INDICATOR_LIST.length).toBe(9);
    const missing = CATALOG.map((c) => c.name).filter((n) => MABNA_TEMPLATES[n] == null);
    expect(missing).toEqual([]);
    const orphans = Object.keys(MABNA_TEMPLATES).filter((n) => !CATALOG.some((c) => c.name === n));
    expect(orphans).toEqual([]);
  });

  it('هر سطرِ کاتالوگ برچسبِ فارسی با نامِ rahavard در پرانتز دارد', () => {
    for (const c of CATALOG) {
      expect(c.label, c.name).toMatch(/\(/);
      expect(c.label, c.name).not.toBe(c.name);
    }
  });

  it('overlayها همان سه مطالعهٔ قیمتیِ rahavard هستند', () => {
    // is_price_study:!0 فقط در HT، SR و FIBB دیده می‌شود
    expect(CATALOG.filter((c) => c.overlay).map((c) => c.name).sort()).toEqual([
      'MabnaFibBB',
      'MabnaHalfTrend',
      'MabnaSRLevels',
    ]);
    for (const tpl of MABNA_INDICATOR_LIST) {
      const entry = CATALOG.find((c) => c.name === tpl.name)!;
      expect(tpl.series, tpl.name).toBe(entry.overlay ? 'price' : 'normal');
    }
  });

  it('هیچ نامی با اندیکاتورهای درونیِ چارت یا کاتالوگ TV یکی نیست', () => {
    const builtin = ['VOL', 'MA', 'EMA', 'RSI', 'MACD', 'BOLL'];
    const names = CATALOG.map((c) => c.name);
    expect(names.filter((n) => builtin.includes(n))).toEqual([]);
    expect(names.filter((n) => TV_INDICATORS.some((t) => t.name === n))).toEqual([]);
  });

  it('ثبت idempotent است و یک تمپلتِ خراب بقیه را نمی‌خواباند', () => {
    const first: string[] = [];
    expect(
      registerMabnaIndicators({
        registerIndicator: (i) => first.push((i as { name: string }).name),
        getSupportedIndicators: () => [],
      }),
    ).toBe(9);
    expect(first.sort()).toEqual(CATALOG.map((c) => c.name).sort());
    expect(
      registerMabnaIndicators({
        registerIndicator: () => {
          throw new Error('must not re-register');
        },
        getSupportedIndicators: () => CATALOG.map((c) => c.name),
      }),
    ).toBe(0);
    // فقط MabnaVixFix خراب است → هشت تای دیگر ثبت می‌مانند
    const ok: string[] = [];
    const n = registerMabnaIndicators({
      registerIndicator: (i) => {
        const name = (i as { name: string }).name;
        if (name === 'MabnaVixFix') throw new Error('bad study');
        ok.push(name);
      },
      getSupportedIndicators: () => [],
    });
    expect(n).toBe(8);
    expect(ok).toHaveLength(8);
    expect(ok).not.toContain('MabnaVixFix');
  });

  it('calcParamsِ هر تمپلت با defaults.inputs خودِ rahavard یکی است', () => {
    // ترتیب و مقدارِ پیش‌فرض از metainfo هر مطالعه (بخشِ sources بالای فایل)
    expect(MABNA_TEMPLATES.MabnaDT.calcParams).toEqual([8, 5, 3, 3]);
    expect(MABNA_TEMPLATES.MabnaZScore.calcParams).toEqual([20, 2, 1, 'close']);
    expect(MABNA_TEMPLATES.MabnaSQZMOM.calcParams).toEqual([20, 2, 20, 1.5, true]);
    expect(MABNA_TEMPLATES.MabnaHalfTrend.calcParams).toEqual([2, 2, true, true, true]);
    expect(MABNA_TEMPLATES.MabnaSRLevels.calcParams).toEqual([true, 15, 15, 20]);
    expect(MABNA_TEMPLATES.MabnaWaveTrend.calcParams).toEqual([10, 21, 60, 53, -60, -53]);
    expect(MABNA_TEMPLATES.MabnaWaveTrendCross.calcParams).toEqual([10, 21, 60, 53, -60, -53]);
    expect(MABNA_TEMPLATES.MabnaFibBB.calcParams).toEqual([200, 'hlc3', 3]);
    expect(MABNA_TEMPLATES.MabnaVixFix.calcParams).toEqual([22, 20, 2, 50, 0.85, 1.01, false, false]);
  });
});
