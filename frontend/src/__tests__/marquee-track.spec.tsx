// __tests__/marquee-track.spec.tsx -- نوارِ روانِ پیوسته (بند ۴.۱ مأموریت)
// چهار چیز باید ثابت بماند: حرکت درِ DOM است نه state (بی‌ری‌رندر هر فریم)،
// توقف با hover/focus/دکمه واقعاً فریم‌ها را می‌بندد، کاهشِ حرکتِ سیستم نوار را
// ایستا و چندسطری می‌کند، و آمدنِ محتوایِ تازه جابه‌جایی را به صفر برنمی‌گرداند.
import { render, screen, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MarqueeTrack } from '@shared/components/MarqueeTrack';

let rafCount = 0;
let frames: FrameRequestCallback[] = [];
let renders = 0;

function installRaf() {
  frames = [];
  rafCount = 0;
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
    frames.push(cb);
    return ++rafCount;
  });
  vi.stubGlobal('cancelAnimationFrame', () => { frames = []; });
}

let clock = 0;
/** ساعتِ ساختگیِ یکنواخت: هر گام dtِ واقعی می‌دهد (با performance.now()ِ ثابتِ jsdom
 *  dt صفر می‌شد و حرکت دیده نمی‌شد — آزمونِ بی‌حرکت چیزی را نمی‌سنجد). */
const step = (ms: number) =>
  act(() => {
    clock += ms;
    const q = frames.splice(0, frames.length);
    q.forEach((cb) => cb(clock));
  });
/** فریمِ نخست فقط مبنا می‌گذارد (dt=0)، پس سنجشِ حرکت به دو گام نیاز دارد */
const advance = (n = 2, ms = 16) => { for (let i = 0; i < n; i++) step(ms); };

function Content({ label }: { label: string }) {
  renders++;
  return <span data-testid="unit">{label}</span>;
}

const reduced = (on: boolean) =>
  vi.stubGlobal('matchMedia', (q: string) => ({
    matches: q.includes('reduced-motion') && on,
    addEventListener: () => {}, removeEventListener: () => {},
  }));

// jsdom اندازه ندارد؛ نوار بی‌پهنایی حرکت نمی‌کند (این عمدی است: بی‌اندازه
// هیچ transform معناداری نمی‌سازیم). برایِ آزمونِ حرکت، پهنایِ ساختگی می‌گذاریم.
function stubSizes() {
  Object.defineProperty(HTMLElement.prototype, 'scrollWidth', { configurable: true, value: 800 });
  Object.defineProperty(HTMLElement.prototype, 'clientWidth', { configurable: true, value: 400 });
}

beforeEach(() => { installRaf(); renders = 0; reduced(false); stubSizes(); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('MarqueeTrack', () => {
  it('درِ حالتِ روان transform درِ DOM عوض می‌شود و React ری‌رندر نمی‌کند', () => {
    render(<MarqueeTrack testId="mq"><Content label="الف" /></MarqueeTrack>);
    const track = screen.getByTestId('mq-track');
    const first = renders;
    expect(track.style.transform).toBe('translate3d(0px,0,0)');
    advance();
    expect(track.style.transform).toMatch(/^translate3d\([0-9.]+px,0,0\)$/);
    expect(track.style.transform).not.toBe('translate3d(0px,0,0)');
    expect(renders).toBe(first);            // هیچ ری‌رندری درِ هر فریم نیست
  });

  it('paused ⇒ فریمی درخواست نمی‌شود و data-state اعلام می‌کند', () => {
    render(<MarqueeTrack testId="mq" paused><Content label="الف" /></MarqueeTrack>);
    expect(screen.getByTestId('mq').getAttribute('data-state')).toBe('paused');
    const before = rafCount;
    advance();
    expect(rafCount).toBe(before);
  });

  it('کاهشِ حرکتِ سیستم ⇒ بی‌حرکت، محتوایِ چندسطریِ خوانا، بی‌نسخۀ دوم', () => {
    reduced(true);
    render(<MarqueeTrack testId="mq"><Content label="الف" /></MarqueeTrack>);
    expect(screen.getByTestId('mq').getAttribute('data-state')).toBe('reduced');
    expect(screen.queryByTestId('mq-copy-2')).toBeNull();
    expect(screen.getByTestId('mq-track').style.transform).toBe('none');
    const before = rafCount;          // فریمِ نخستِ پیش از دیدنِ تنظیم، شمارش نمی‌شود
    advance();
    expect(rafCount).toBe(before);    // حلقه بسته است، نه فقط بی‌محتوا
  });

  it('محتوایِ تازه ⇒ ادامه از همان جابه‌جایی، بی‌پرش به ابتدا', () => {
    const { rerender } = render(
      <MarqueeTrack testId="mq"><Content label="الف" /></MarqueeTrack>);
    const track = screen.getByTestId('mq-track');
    advance();
    const mid = track.style.transform;
    expect(mid).not.toBe('translate3d(0px,0,0)');
    rerender(<MarqueeTrack testId="mq"><Content label="ب" /></MarqueeTrack>);
    expect(track.style.transform).toBe(mid);   // همان‌جا می‌ماند، نه صفر
  });

  it('راست‌به‌چپ جهتِ مثبت و چپ‌به‌راست جهتِ منفی دارد', () => {
    const a = render(<MarqueeTrack testId="mqr" direction="rtl"><Content label="ر" /></MarqueeTrack>);
    advance();
    const rtl = screen.getByTestId('mqr-track').style.transform;
    a.unmount();
    render(<MarqueeTrack testId="mql" direction="ltr"><Content label="ل" /></MarqueeTrack>);
    advance();
    const ltr = screen.getByTestId('mql-track').style.transform;
    expect(rtl).toMatch(/^translate3d\([0-9.]+px,0,0\)$/);      // rtl ⇒ مثبت
    expect(ltr).toMatch(/^translate3d\(-[0-9.]+px,0,0\)$/);     // ltr ⇒ منفی
  });
});
