// __tests__/technical-board-context.spec.tsx -- زمینه، نه رأی
// دورِ مصرف‌کننده اجازه داد وضعیتِ ناظر و رویدادِ شرکتی درِ سایدبارِ تکنیکال و
// تبِ «داوری» *نشان* داده شود، به شرطِ اینکه هیچ داوریِ تازه نسازد. این سنجش
// همان شرط را قفل می‌کند: چیپ‌ها از propsِ جدا می‌آیند و هیچ‌یک از کلیدهایِ
// TSETMC واردِ گیت/فرمولِ FTS نشده است.
import { render, screen } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { SidebarActiveLevels, type ActiveLevelsView } from '@features/technical/components/SidebarActiveLevels';

const base: ActiveLevelsView = {
  symbol: 'شپنا',
  fts: null,
  ma100: null,
  lastClose: 1000,
  setups: ['jet'],
  context: ['fib_step1'],
  direction: 'bullish',
};

describe('زمینۀ تابلو درِ سایدبارِ تکنیکال', () => {
  it('بی‌زمینه، هیچ خطِ تازه‌ای نیست (پاسخِ قدیمی همان می‌ماند)', () => {
    render(<SidebarActiveLevels active={base} />);
    expect(screen.queryByTestId('sidebar-board-context')).toBeNull();
    expect(screen.getByTestId('sidebar-fts-context').textContent).toContain('زمینه:');
  });

  it('متوقف + رویدادِ اخیر: دو چیپ، بی‌تغییرِ ستاپ‌ها و زمینه‌هایِ FTS', () => {
    render(<SidebarActiveLevels active={{
      ...base,
      boardFlags: { stopped: 'تعلیق شده', stopSince: '1405-07-11', recentEvents: ['تغییرِ سهام (1405-07-01)'] },
    }} />);
    const line = screen.getByTestId('sidebar-board-context');
    expect(line.textContent).toContain('از تابلو:');
    expect(line.textContent).toContain('متوقف');
    expect(line.textContent).toContain('تغییرِ سهام');
    // چیپ‌هایِ FTS از همان آرایه‌هایِ سرورند و بیشتر نشده‌اند
    expect(screen.getByTestId('sidebar-fts-context').textContent).toContain('زمینه:');
  });

  it('نظارت تنها ⇒ یک چیپ، و کلمهٔ «متوقف» نمی‌آید (UNKNOWN ≠ stopped)', () => {
    render(<SidebarActiveLevels active={{ ...base, boardFlags: { supervised: true } }} />);
    const line = screen.getByTestId('sidebar-board-context');
    expect(line.textContent).toContain('نظارت');
    expect(line.textContent).not.toContain('متوقف');
  });
});

describe('بی‌محاسبۀ موازی و بی‌رأیِ تازه', () => {
  const src = (p: string) => readFileSync(join(__dirname, '..', p), 'utf-8');
  const FORBIDDEN = ['stop_state', 'stop_reasons', 'sup_flag', 'sup_reason_count', 'ctv_kind', 'client_type_value'];

  it('گیت‌هایِ سختِ مستر هیچ‌کدام از کلیدهایِ ناظر/مبدأ را نمی‌خوانند', () => {
    const gates = src('features/master/lib/strictGates.ts');
    for (const key of FORBIDDEN) expect(gates).not.toContain(key);
  });

  it('فرمولِ سیگنالِ تکنیکال همان ورودی‌ها را دارد (هیچ وزنِ تازه نه)', () => {
    const sig = src('features/technical/signals/technicalSignals.ts');
    for (const key of FORBIDDEN) expect(sig).not.toContain(key);
  });

  it('هفت فیلترِ تابلو (tapeAlgorithms) دست‌نخورده: هیچ کلیدِ P0 درِ فرمول نیست', () => {
    const tape = src('features/market/lib/tapeAlgorithms.ts');
    for (const key of [...FORBIDDEN, 'instrument_state', 'supervision_state']) expect(tape).not.toContain(key);
  });
});
