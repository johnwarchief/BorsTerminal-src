// تست پرتفوی هدف: دونات، نرمال‌سازی، ویرایش/بازنشانی، نوار دلتا
import { describe, expect, it } from 'vitest';
import {
  FTS_DEFAULT_TARGETS,
  buildDelta,
  isValidAllocation,
  mixSentence,
  normalizePct,
  sumPct,
} from '@features/portfolio/stores/targetAllocation';
import { donutSegments } from '@features/portfolio/components/TargetDonut';
import { deltaLabel, deltaTotals, deltaTone } from '@features/portfolio/components/DeltaBar';

describe('طبقات پیش‌فرض FTS', () => {
  it('شش طبقه با جمع دقیق ۱۰۰٪', () => {
    expect(FTS_DEFAULT_TARGETS).toHaveLength(6);
    const total = sumPct(FTS_DEFAULT_TARGETS);
    expect(total).toBeCloseTo(100, 5);
  });

  it('تفکیک استاندارد طلا طبق سند: طلا و سکه ۴۵٪ (فیزیکی ۳۰٪ + صندوق/گواهی ۱۵٪)', () => {
    const gold = FTS_DEFAULT_TARGETS.find((c) => c.id === 'gold');
    const cert = FTS_DEFAULT_TARGETS.find((c) => c.id === 'gold-cert');
    expect(gold).toBeDefined();
    expect(gold!.pct).toBe(30);
    expect(gold!.label).toBe('طلای فیزیکی، سکه و شمش');
    expect(cert).toBeDefined();
    expect(cert!.pct).toBe(15);
    expect(gold!.pct + cert!.pct).toBe(45);
    expect(cert!.label).toBe('صندوق‌ها و گواهی سپردهٔ طلا');
  });

  it('سقف سهام طبق فرمول ریسک سیستماتیک (طبقه equity ۱۵٪)', () => {
    const equity = FTS_DEFAULT_TARGETS.find((c) => c.id === 'equity');
    expect(equity).toBeDefined();
    expect(equity!.pct).toBe(15);
    expect(equity!.hint).toContain('۲۰');
  });

  it('سایر طبقات: ارز ۱۵٪ · نقره ۱۰٪ · درآمد ثابت ۱۵٪', () => {
    expect(FTS_DEFAULT_TARGETS.find((c) => c.id === 'crypto')!.pct).toBe(15);
    expect(FTS_DEFAULT_TARGETS.find((c) => c.id === 'silver')!.pct).toBe(10);
    expect(FTS_DEFAULT_TARGETS.find((c) => c.id === 'fixed')!.pct).toBe(15);
  });
});

describe('نرمال‌سازی و اعتبارسنجی', () => {
  it('جمع بالای ۱۰۰ به ۱۰۰ نرمال می شود', () => {
    const norm = normalizePct([
      { id: 'a', label: 'A', pct: 60, color: '#000' },
      { id: 'b', label: 'B', pct: 60, color: '#111' },
    ]);
    expect(sumPct(norm)).toBeCloseTo(100, 1);
    expect(norm[0].pct).toBeCloseTo(50, 1);
  });

  it('جمع زیر ۱۰۰ به ۱۰۰ نرمال می شود (بازه شروع پیش‌فرض)', () => {
    const norm = normalizePct([
      { id: 'a', label: 'A', pct: 30, color: '#000' },
      { id: 'b', label: 'B', pct: 30, color: '#111' },
    ]);
    expect(sumPct(norm)).toBeCloseTo(100, 1);
    expect(norm[0].pct).toBeCloseTo(50, 1);
  });

  it('جمع ۱۰۰ دست‌نخورده می ماند', () => {
    const input = [
      { id: 'a', label: 'A', pct: 40, color: '#000' },
      { id: 'b', label: 'B', pct: 60, color: '#111' },
    ];
    expect(normalizePct(input).map((c) => c.pct)).toEqual([40, 60]);
  });

  it('جمع صفر ⇒ بازگشت به پیش‌فرض FTS', () => {
    const norm = normalizePct([{ id: 'a', label: 'A', pct: 0, color: '#000' }]);
    expect(norm).toHaveLength(6);
    expect(sumPct(norm)).toBeCloseTo(100, 5);
  });

  it('اعتبارسنجی: جمع ۰ رد، جمع ۱۰۰ قبول، جمع ۱۰۵ رد', () => {
    expect(isValidAllocation([{ id: 'a', label: 'A', pct: 0, color: '#000' }])).toBe(false);
    expect(isValidAllocation(FTS_DEFAULT_TARGETS)).toBe(true);
    expect(isValidAllocation([{ id: 'a', label: 'A', pct: 60, color: '#000' }, { id: 'b', label: 'B', pct: 60, color: '#111' }])).toBe(false);
  });
});

describe('چارت دونات (SVG خالص)', () => {
  it('قطعه‌های مثبت ساخته می شوند و صفرها حذف', () => {
    const segs = donutSegments([
      { id: 'a', label: 'A', pct: 30, color: '#000' },
      { id: 'b', label: 'B', pct: 0, color: '#111' },
      { id: 'c', label: 'C', pct: 15, color: '#222' },
    ]);
    expect(segs).toHaveLength(2);
    expect(segs[0].pct).toBe(30);
  });

  it('درصد نامعتبر (NaN/منفی) حذف می شود', () => {
    const segs = donutSegments([
      { id: 'a', label: 'A', pct: Number.NaN, color: '#000' },
      { id: 'b', label: 'B', pct: -5, color: '#111' },
      { id: 'c', label: 'C', pct: 10, color: '#222' },
    ]);
    expect(segs).toHaveLength(1);
  });
});

describe('نوار شکاف و ری‌بالانس (Delta)', () => {
  it('مازاد مثبت ⇒ فروش سبز', () => {
    expect(deltaTone(5)).toBe('green');
    expect(deltaLabel(5)).toContain('فروش');
    expect(deltaLabel(5)).toContain('۵');
  });

  it('کسری منفی ⇒ خرید قرمز', () => {
    expect(deltaTone(-5)).toBe('red');
    expect(deltaLabel(-5)).toContain('خرید');
  });

  it('نزدیک صفر ⇒ در هدف', () => {
    expect(deltaTone(0)).toBe('gray');
    expect(deltaLabel(0)).toBe('در هدف');
  });

  it('دلتای طبقه سهام از وزن سبد واقعی ساخته می شود', () => {
    const rows = buildDelta(FTS_DEFAULT_TARGETS, [
      { weight_eff_pct: 6 },
      { weight_eff_pct: 4 },
      { weight_eff_pct: 5 },
      { weight_eff_pct: null },
    ]);
    const eq = rows.find((r) => r.id === 'equity');
    expect(eq).toBeDefined();
    expect(eq!.currentPct).toBe(15);
    // هدف سهام ۱۵ ⇒ دلتا صفر
    expect(eq!.delta).toBe(0);
  });

  it('سبدِ خالی ⇒ «داده نداریم»، نه کسریِ ساخته‌شده', () => {
    const rows = buildDelta(FTS_DEFAULT_TARGETS, []);
    const eq = rows.find((r) => r.id === 'equity');
    expect(eq!.currentPct).toBeNull();
    expect(eq!.delta).toBeNull();
    expect(eq!.reason).toContain('سبد خالی');
  });

  // #106: پیش از این هر طبقهٔ غیرسهامی صفر می‌گرفت و «کسریِ کامل» اعلام می‌شد؛
  // یعنی سبدی که ۸۷٪ آن صندوقِ طلاست، طلا را ۰٪ نشان می‌داد.
  it('طبقهٔ بی‌داده ⇒ null با علت، نه صفرِ ساختگی', () => {
    const rows = buildDelta(FTS_DEFAULT_TARGETS, [{ weight_eff_pct: 10 }]);
    const gold = rows.find((r) => r.id === 'gold');
    expect(gold!.currentPct).toBeNull();
    expect(gold!.delta).toBeNull();
    expect(gold!.reason).toBeTruthy();
  });

  it('ترکیبِ طبقاتِ بک‌اند، فعلیِ هر طبقه را می‌سازد («طلا ۸۷٪ از سبد»)', () => {
    const rows = buildDelta(FTS_DEFAULT_TARGETS, [{ weight_eff_pct: 12.8 }], {
      classMixPct: { gold: 87.2, stock: 12.8 },
      basketValueToman: 1_732_500,
    });
    expect(rows.find((r) => r.id === 'gold')!.currentPct).toBe(87.2);
    expect(rows.find((r) => r.id === 'gold')!.basis).toBe('basket');
    // gold و gold-cert هر دو همان طلای سبد را می‌شمارند، پس یکی عدد دارد:
    // تابلو فیزیکی را از گواهیِ سپرده جدا نمی‌کند؛ اگر هر دو ۸۷٫۲ می‌گرفتند،
    // «پوشش» ۱۸۷٪ می‌شد و کارتِ ری‌بالانس دو برابرِ لازم فروش پیشنهاد می‌داد.
    const cert = rows.find((r) => r.id === 'gold-cert')!;
    expect(cert.currentPct).toBeNull();
    expect(cert.delta).toBeNull();
    expect(cert.reason).toContain('طلای فیزیکی، سکه و شمش');
    // هدفِ ردیفِ حمل‌کننده، جمعِ هدفِ طبقه است (۳۰ + ۱۵)، نه هدفِ سطرِ خودش
    expect(rows.find((r) => r.id === 'gold')!.classTargetPct).toBe(45);
    expect(rows.find((r) => r.id === 'gold')!.delta).toBe(42.2);
    expect(cert.classTargetPct).toBe(45);
    expect(cert.classLabel).toContain('صندوق‌ها و گواهی سپردهٔ طلا');
    expect(rows.find((r) => r.id === 'equity')!.currentPct).toBe(12.8);
    // crypto هیچ نمادی در تابلو ندارد ⇒ بدون داده
    expect(rows.find((r) => r.id === 'crypto')!.currentPct).toBeNull();
    expect(rows.find((r) => r.id === 'crypto')!.delta).toBeNull();
  });

  // باگِ واقعیِ همین شماره: «پوشش ۱۸۷٪» — چون یک وزن دو بار جمع می‌شد.
  it('طلا دو بار شمرده نمی‌شود: پوشش و جمعِ فعلی از یک اندازهٔ طبقه می‌آیند', () => {
    const rows = buildDelta(FTS_DEFAULT_TARGETS, [{ weight_eff_pct: 12.8 }], {
      classMixPct: { gold: 87.2, stock: 12.8 },
      basketValueToman: 1_732_500,
    });
    const { target, current } = deltaTotals(rows);
    expect(target).toBe(100);
    expect(current).toBe(100); // ۸۷٫۲ + ۱۲٫۸ — نه ۱۷۴٫۴ + …
    // کارت‌های کسری/مازاد هم نباید یک طبقه را دو بار بیاورند
    const flagged = rows.filter((r) => r.delta != null && Math.abs(r.delta) > 0.05);
    expect(flagged.map((r) => r.id)).toEqual(['gold', 'equity']);
  });

  // همان باگ روی سبدِ تک‌ردیفه: ردیفی که بک‌اند طبقه‌اش را می‌داند در ترکیبِ طبقات
  // شمرده شده؛ جمعش در «جانشینِ سهام» همان وزن را دوباره سهام می‌کرد (طلا ۱۰۰٪
  // ⇒ «سهام ۱۰۰٪» و پوشش ۲۰۰٪).
  it('ردیفِ طبقه‌دار در جانشینِ سهام نمی‌نشیند؛ فقط ردیفِ بی‌طبقه', () => {
    const rows = buildDelta(
      FTS_DEFAULT_TARGETS,
      [
        { weight_eff_pct: 100, asset_class: { cls: 'fund', kind: 'gold' } },
      ],
      { classMixPct: { gold: 100 } },
    );
    expect(rows.find((r) => r.id === 'gold')!.currentPct).toBe(100);
    const eq = rows.find((r) => r.id === 'equity')!;
    expect(eq.currentPct).toBeNull();
    expect(eq.delta).toBeNull();
    expect(deltaTotals(rows).current).toBe(100);
  });

  // حقِ تقدم هم ادعای سهامی است؛ نگاشتِ نبودش یعنی وزنِ آن ردیف بی‌صدا از
  // ترکیبِ فعلی می‌افتد و سهامِ سبد کم‌شمرده می‌شود.
  it('حقِ تقدم در طبقهٔ سهام شمرده می‌شود، نه این‌که بی‌صدا دور ریخته شود', () => {
    const rows = buildDelta(FTS_DEFAULT_TARGETS, [{ weight_eff_pct: 40 }], {
      classMixPct: { gold: 60, right: 20, stock: 20 },
    });
    expect(rows.find((r) => r.id === 'equity')!.currentPct).toBe(40);
    expect(rows.find((r) => r.id === 'gold')!.currentPct).toBe(60);
  });

  it('با سرمایهٔ کلِ ثبت‌شده، درصد به مخرجِ «سرمایه» می‌رود و برچسبش عوض می‌شود', () => {
    const rows = buildDelta(FTS_DEFAULT_TARGETS, [], {
      classMixPct: { gold: 50 },
      basketValueToman: 1_000_000,
      totalToman: 4_000_000,
    });
    const gold = rows.find((r) => r.id === 'gold')!;
    expect(gold.currentPct).toBe(12.5); // ۵۰٪ از سبد = ۱م تومان = ۱۲٫۵٪ از ۴م
    expect(gold.basis).toBe('capital');
    expect(gold.delta).toBe(-32.5); // هدفِ *طبقهٔ* طلا ۴۵٪ (۳۰ فیزیکی + ۱۵ گواهی)
  });

  it('ارزشِ دستیِ تنها منبعِ طبقه‌ای است که تابلو نمی‌شناسد (رمز/arbitrage)', () => {
    const rows = buildDelta(FTS_DEFAULT_TARGETS, [{ weight_eff_pct: 40 }], {
      totalToman: 2_000_000,
      valuesByClass: { crypto: 300_000 },
    });
    const crypto = rows.find((r) => r.id === 'crypto')!;
    expect(crypto.currentPct).toBe(15);
    expect(crypto.basis).toBe('capital');
  });

  it('جملهٔ headline بدترین انحراف را با مخرجش می‌گوید', () => {
    const rows = buildDelta(FTS_DEFAULT_TARGETS, [], {
      classMixPct: { gold: 87.2, stock: 12.8 },
      basketValueToman: 1_732_500,
    });
    const s = mixSentence(rows);
    expect(s).toContain('طلا');
    expect(s).toContain('از سبد');
    expect(s).toContain('هدف');
    // عددِ هدف باید هدفِ جمعِ طبقه باشد؛ با ۳۰٪ِ سطرِ تنها «مازاد ۵۷٫۲٪» اعلام می‌شد
    expect(s).toBe('طلای فیزیکی، سکه و شمش: ۸۷.۲٪ از سبد — هدف ۴۵٪ (مازاد ۴۲.۲٪)');
    expect(mixSentence(buildDelta(FTS_DEFAULT_TARGETS, []))).toBeNull();
  });
});
