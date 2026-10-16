// __tests__/funnel-row-symbol-visible.spec.tsx — نامِ نماد قربانیِ برچسب نمی‌شود
//
// باگِ گزارش‌شده (بندِ ۱ مأموریتِ رابط): درِ ردیفِ قیف (تب استراتژی) نامِ نماد و
// برچسب‌های «عبور با ملاحظات» / «وتوی مجمع» درِ یک `flex … truncate` با
// `max-w-[15ch]` بودند و هر دو برچسب `shrink-0` — پس با روشن‌شدنِ برچسب، نامِ
// نماد به «…» تبدیل می‌شد. jsdom چیدمان را اندازه نمی‌گیرد، پس این پرونده
// **ساختار** را می‌سنجد (نام بی‌truncate، برچسب‌ها بیرونِ دکمۀ نام و رویِ خطِ
// دوم) و بریدگیِ واقعی درِ مرورگر زنده با scrollWidth/offsetWidth سنجیده می‌شود.
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import { StageRow } from '@features/master/ui/FtsFunnelAllStages';
import { funnelFromApi } from '@features/master/lib/funnelView';
import { FUNNEL_FIXTURE } from './fixtures/funnelApi';

const LONG = 'پتروپایش۲';
const base = funnelFromApi(FUNNEL_FIXTURE as never).stages.fundamental.entries[0];

function renderRow(over: Record<string, unknown> = {}) {
  const entry = {
    ...base,
    symbol: LONG,
    name: 'پتروشیمی پارس (دوم)',
    why: { ...base.why, fundamental: 'دو شاخص سنجیده نشد' },
    ...over,
  };
  return render(
    <MemoryRouter>
      <table>
        <tbody>
          <StageRow
            entry={entry as never}
            cols={['symbol', 'score', 'why']}
            showMark="fund"
            stageKey="fundamental"
            onPick={() => {}}
          />
        </tbody>
      </table>
    </MemoryRouter>,
  );
}

describe('ردیفِ قیف با برچسبِ بلند', () => {
  it('نامِ کاملِ نماد درِ DOM است و کلاسِ بریدگی ندارد', () => {
    renderRow({ fundCaveat: true, assemblyVeto: true });
    const name = screen.getByText(LONG);
    expect(name.textContent).toBe(LONG);
    expect(name.className).not.toMatch(/truncate/);
    // هیچ جداسازیِ عرضی هم نباید رویِ خودِ نام نشسته باشد
    expect(name.className).not.toMatch(/max-w-\[/);
  });

  it('برچسب‌ها بیرونِ دکمۀ نام و رویِ خطِ دوم می‌نشینند (نه هم‌خطِ نام)', () => {
    renderRow({ fundCaveat: true, assemblyVeto: true });
    const caveat = screen.getByTestId(`funnel-fund-caveat-${LONG}`);
    const veto = screen.getByTestId(`funnel-assembly-veto-${LONG}`);
    // closest('button')ِ نامِ خودِ نماد است؛ برچسب نباید فرزندِ آن باشد
    expect(caveat.closest('button')).toBeNull();
    expect(veto.closest('button')).toBeNull();
    // هر دو درِ کانتینرِ خطِ دوم‌اند
    const marks = screen.getByTestId(`funnel-row-marks-${LONG}`);
    expect(marks.contains(caveat)).toBe(true);
    expect(marks.contains(veto)).toBe(true);
    // خطِ دوم خواهرِ خطِ نام است، نه فرزندش
    const name = screen.getByText(LONG);
    expect(marks.contains(name)).toBe(false);
  });

  it('بی‌برچسب، خطِ دوم ساخته نمی‌شود (فضای بی‌داده درِ ردیف نمی‌ماند)', () => {
    renderRow({ fundCaveat: false, assemblyVeto: false });
    expect(screen.getByText(LONG)).toBeTruthy();
    expect(screen.queryByTestId(`funnel-row-marks-${LONG}`)).toBeNull();
  });

  it('کلیک رویِ نام همان onPickِ پیشین را می‌دهد (رفتارِ انتخابِ نماد نمرده)', () => {
    let picked: string | null = null;
    const entry = { ...base, symbol: LONG, fundCaveat: true } as never;
    render(
      <MemoryRouter>
        <table>
          <tbody>
            <StageRow
              entry={entry}
              cols={['symbol']}
              showMark="fund"
              stageKey="fundamental"
              onPick={(s: string) => { picked = s; }}
            />
          </tbody>
        </table>
      </MemoryRouter>,
    );
    screen.getByText(LONG).closest('button')!.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(picked).toBe(LONG);
  });
});
