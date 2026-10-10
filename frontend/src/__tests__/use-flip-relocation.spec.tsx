// __tests__/use-flip-relocation.spec.ts — گاردِ رگرسیونِ «حرکتِ زندهٔ قیف»
//
// خواستۀ مالک (P0-1): نماد باید با هویتِ پایدارش (symbol، نه index) از محلِ
// قبلی به محلِ جدید حرکت کند، و بی‌حرکتیِ موس (تماشای زنده) این حرکت را
// خاموش نکند. این فایل دقیقاً «جابجایی» را می‌سنجد، نه فلاش ردیف یا تغییر count.
//
// jsdom Web Animations API را ندارد؛ getBoundingClientRect را هم همه‌چیز صفر
// برمی‌گرداند. پس سنسور را خودمان می‌سازیم: موقعیتِ هر ردیف از یک نقشۀ
// symbol→top خوانده می‌شود، و `animate` رکورد می‌کند چه حرکتی ساخته شد.
// کنترلِ منفی هم کاشته شده: اگر گاردِ حرکت کور باشد، تستِ «حرکت ساخته می‌شود»
// نمی‌تواند سبز شود.
import { render, cleanup } from '@testing-library/react';
import { useRef } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useFlip } from '@shared/lib/useFlip';

// موقعیتِ فعلیِ هر ردیف (کلیدِ پایدار = symbol). تست با جابه‌جا کردن این مقادیر
// «جابجایی بین رتبه‌ها» را شبیه‌سازی می‌کند.
const POS = new Map<string, number>();

type AnimateCall = { key: string; keyframes: Array<Record<string, string>> };
let animateCalls: AnimateCall[] = [];

function FlipList({ symbols }: { symbols: string[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useFlip({ root: ref, deps: [symbols.join(' ')] });
  return (
    <div ref={ref}>
      {symbols.map((s) => (
        <div key={s} data-fkey={s} />
      ))}
    </div>
  );
}

function patchSensors() {
  const origRect = Element.prototype.getBoundingClientRect;
  Element.prototype.getBoundingClientRect = function (this: Element) {
    const k = (this as HTMLElement).dataset?.fkey;
    const top = k ? POS.get(k) ?? 0 : 0;
    return { top, left: 0, bottom: top + 29, right: 200, width: 200, height: 29,
             x: 0, y: top, toJSON: () => ({}) } as DOMRect;
  };
  HTMLElement.prototype.animate = function (
    this: HTMLElement,
    keyframes: Array<Record<string, string>>,
  ) {
    animateCalls.push({ key: this.dataset.fkey ?? '', keyframes });
    return { cancel() {}, finished: Promise.resolve(), currentTime: 0 } as unknown as Animation;
  } as typeof HTMLElement.prototype.animate;
  // motionAllowed وجود animate را روی Element.prototype می‌سنجد (در مرورگر
  // واقعی همان‌جاست)؛ پس سنسور هم باید همان‌جا بنشیند وگرنه گارد کور می‌شود.
  Element.prototype.animate = HTMLElement.prototype.animate;
  return () => {
    Element.prototype.getBoundingClientRect = origRect;
    delete (Element.prototype as { animate?: unknown }).animate;
    delete (HTMLElement.prototype as { animate?: unknown }).animate;
  };
}

const motion = (c: AnimateCall) => c.keyframes[0]?.transform ?? '';
const moved = () => animateCalls.filter((c) => /translate\(.*\)/.test(motion(c)));

function setFlag(name: string, value: string | null) {
  if (value === null) delete document.documentElement.dataset[name];
  else document.documentElement.dataset[name] = value;
}

let restore: () => void;

beforeEach(() => {
  animateCalls = [];
  POS.clear();
  restore = patchSensors();
  setFlag('idle', null);
  setFlag('hidden', null);
  setFlag('perf', null);
  const mq = vi.spyOn(window, 'matchMedia').mockImplementation((q) => {
    return {
      matches: false, media: q, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(),
      removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    } as unknown as MediaQueryList;
  });
  return () => mq.mockRestore();
});

afterEach(() => {
  restore();
  cleanup();
});

describe('جابجاییِ نماد با هویتِ پایدارش (نقشۀ رگرسیونِ حرکتِ زنده)', () => {
  it('با عوض‌شدنِ رتبه، ردیفِ موجود «حرکت» می‌گیرد نه «ورودِ تازه»', () => {
    POS.set('A', 0); POS.set('B', 29);
    const { rerender } = render(<FlipList symbols={['A', 'B']} />);
    expect(animateCalls.length).toBe(0); // دورِ اول: بی‌حرکتِ خودساز

    // حکم عوض شده و رتبه‌ها جابه‌جا شده‌اند: B بالا، A پایین.
    POS.set('A', 29); POS.set('B', 0);
    rerender(<FlipList symbols={['B', 'A']} />);

    expect(moved().map((c) => c.key).sort()).toEqual(['A', 'B']);
    // کنترلِ منفی: جهتِ حرکتِ A برعکسِ جابه‌جاییِ واقعی‌اش است (0 → 29 ⇒ invert -29)
    expect(motion(moved().find((c) => c.key === 'A')!)).toContain('-29');
  });

  it('ردیفِ بدونِ جابه‌جایی انیمیشن نمی‌سازد', () => {
    POS.set('A', 0); POS.set('B', 29);
    const { rerender } = render(<FlipList symbols={['A', 'B']} />);
    POS.set('A', 0); POS.set('B', 29); // جای هیچ‌کدام عوض نشده، فقط ترتیبِ یکسان
    rerender(<FlipList symbols={['A', 'B']} />);
    expect(moved().length).toBe(0);
  });

  it('تماشای زنده (بی‌حرکتیِ موس) حرکت را نمی‌خواباند — علتِ رگرسیونِ v1.0.81', () => {
    POS.set('A', 0); POS.set('B', 29);
    setFlag('idle', '1'); // دست روی موس نیست، پنجره دیده می‌شود
    const { rerender } = render(<FlipList symbols={['A', 'B']} />);
    POS.set('A', 29); POS.set('B', 0);
    rerender(<FlipList symbols={['B', 'A']} />);
    expect(moved().map((c) => c.key).sort()).toEqual(['A', 'B']);
  });

  it('پنجرۀ پنه/مینیمایز حرکت را می‌خواباند (صرفه‌جوییِ GPU حفظ شود)', () => {
    POS.set('A', 0); POS.set('B', 29);
    setFlag('idle', '1');
    setFlag('hidden', '1');
    const { rerender } = render(<FlipList symbols={['A', 'B']} />);
    POS.set('A', 29); POS.set('B', 0);
    rerender(<FlipList symbols={['B', 'A']} />);
    expect(moved().length).toBe(0);
  });

  it('حالتِ کم‌مصرف (data-perf=low) حرکت را می‌خواباند', () => {
    POS.set('A', 0); POS.set('B', 29);
    setFlag('perf', 'low');
    const { rerender } = render(<FlipList symbols={['A', 'B']} />);
    POS.set('A', 29); POS.set('B', 0);
    rerender(<FlipList symbols={['B', 'A']} />);
    expect(moved().length).toBe(0);
  });

  it('prefers-reduced-motion حرکت را می‌خواباند (دسترس‌پذیری فروخته نمی‌شود)', () => {
    vi.restoreAllMocks();
    vi.spyOn(window, 'matchMedia').mockImplementation((q) => ({
      matches: q.includes('prefers-reduced-motion'), media: q, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(),
      removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    }) as unknown as MediaQueryList);
    POS.set('A', 0); POS.set('B', 29);
    const { rerender } = render(<FlipList symbols={['A', 'B']} />);
    POS.set('A', 29); POS.set('B', 0);
    rerender(<FlipList symbols={['B', 'A']} />);
    expect(moved().length).toBe(0);
  });
});
