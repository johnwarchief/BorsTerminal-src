// shared/lib/useFlip.ts -- FLIP با Web Animations API برای فهرست‌هایِ مرحلۀ‌بدر‌مرحله
//
// چرا این روش و نه «fade بی‌معنی»: ردیفِ قیف با هر تیک جابه‌جا می‌شود و اگر
// فقط محو/ظاهر شود، چشمِ کاربر نمی‌فهمد *کدام* نماد از کدام مرحلۀ بیرون افتاد.
// FLIP یعنی: قبل از رندرِ تازه، مستطیلِ هر گره را با کلیدِ پایدارش (نماد)
// اندازه می‌گیریم؛ بعد از رندر، اختلاف را با transform جابه‌جا می‌کنیم و به
// صفر برمی‌گردانیم. کاری که خودش GPU-composited است، هیچ layout دیگری را
// بو نمی‌کند، و با `element.animate` قابلِ لغو است (تیکِ ۵ ثانیه‌ای وسطِ
// انیمیشن، صفِ انیمیشن نمی‌سازد).
//
// three things this guards: «یک نماد، یک حرکت» (کلیدِ گره نه ایندکس)،
// بی‌‌انیمیشنِ ردیف‌هایِ تازه (cross-fade نمی‌کنیم، فقط می‌نشینند)، و احترامِ
// به two escape hatches: prefers-reduced-motion و html[data-perf=low].
//
// چرا data-idle اینجا نیست (ریشۀِ رگرسیونِ حرکتِ زنده در v1.0.81):
// قیاس با فلاش و جریانِ درخت. آن‌ها CSS بودند و با `:not([data-hidden])` از
// دروازۀ بی‌کاری مستثنی شدند (#198)، چون تماشای زندۀ قیف ذاتاً بی‌تعامل است و
// بی‌حرکتیِ موس نباید حرکت را بکُشد. FLIP یک انیمیشنِ یک‌بارمصرفِ ۴۲۰ms است که
// خودش لغو می‌شود و هر vsync را بیدار نگه نمی‌دارد — مصرفِ GPUی که دروازۀ بی‌کاری
// برایش ساخته شد را ندارد. پس اینجا فقط پنهان‌بودنِ واقعیِ پنجره (data-hidden)
// حرکت را می‌خواباند، نه بی‌کاریِ ناشی از دست‌روی‌موس-نبودن.
import { useLayoutEffect, useRef } from 'react';

export type FlipOptions = {
  /** دامنهٔ جست‌وجویِ گره‌ها (معمولاً بدنهٔ یک مرحلۀ قیف) */
  root: React.RefObject<HTMLElement | null>;
  /** هر چیزی که تغییرش باید حرکت بسازد — معمولاً ردیفِ خروجیِ مرحلۀ مربوطه */
  deps: unknown[];
  /** آستانهٔ حرکت: زیرِ این جابه‌جایی انیمیشن نمی‌سازد (ردیفِ بی‌جابه‌جایی) */
  minMovePx?: number;
  /** گامِ تأخیرِ هر ردیف به میلی‌ثانیه — صفِ پلکانی از بالا به پایین */
  staggerMs?: number;
};

const MOVE_MS = 420;
const ENTER_MS = 260;
const EASE = 'cubic-bezier(0.22, 0.61, 0.36, 1)';

function motionAllowed(): boolean {
  if (typeof window === 'undefined') return false;
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return false;
  const root = document.documentElement;
  if (root.dataset.perf === 'low') return false;
  // پنهان‌بودنِ واقعیِ پنجره (مینیمایز/تبِ مخفی) حرکت را می‌خواباند؛
  // بی‌حرکتیِ موس (data-idle) نه — تماشای زندۀ قیف همان حالتِ بی‌دست است.
  if (root.dataset.hidden === '1') return false;
  return typeof Element.prototype.animate === 'function';
}

/** کلیدِ پایدارِ هر ردیف از data-fkey می‌آید؛ بی‌آن ردیف بی‌حرکت می‌ماند. */
function keyedNodes(root: HTMLElement): Map<string, HTMLElement> {
  const out = new Map<string, HTMLElement>();
  for (const el of Array.from(root.querySelectorAll<HTMLElement>('[data-fkey]'))) {
    const k = el.dataset.fkey;
    if (k) out.set(k, el);
  }
  return out;
}

export function useFlip({ root, deps, minMovePx = 2, staggerMs = 24 }: FlipOptions): void {
  const before = useRef<Map<string, DOMRect>>(new Map());
  const first = useRef(true);

  useLayoutEffect(() => {
    const el = root.current;
    if (!el) return;
    const snapshot = before.current;

    // FIRST: اندازه‌گیریِ دورِ قبل، فقط برایِ دورۀ اول و دورۀ بعد از هر تغییر
    const run = () => {
      const now = keyedNodes(el);
      if (!motionAllowed()) {
        before.current = now.size ? new Map(Array.from(now, ([k, n]) => [k, n.getBoundingClientRect()])) : snapshot;
        first.current = false;
        return;
      }
      let i = 0;
      for (const [key, node] of now) {
        const old = snapshot.get(key);
        const rect = node.getBoundingClientRect();
        if (!old) {
          if (!first.current) {
            node.animate(
              [{ opacity: 0, transform: 'translateY(-6px)' }, { opacity: 1, transform: 'none' }],
              { duration: ENTER_MS, easing: EASE, fill: 'none' },
            );
          }
          continue;
        }
        const dx = old.left - rect.left;
        const dy = old.top - rect.top;
        if (Math.abs(dx) < minMovePx && Math.abs(dy) < minMovePx) continue;
        // LAST → INVERT → PLAY: یک transform، بی‌دست‌زدن به layoutِ بقیه
        node.animate(
          [{ transform: `translate(${dx}px, ${dy}px)` }, { transform: 'translate(0px, 0px)' }],
          { duration: MOVE_MS, delay: i * staggerMs, easing: EASE, fill: 'none' },
        );
        i += 1;
      }
      first.current = false;
      before.current = new Map(Array.from(now, ([k, n]) => [k, n.getBoundingClientRect()]));
    };

    run();
    // deps فقط «چه وقت» را تعیین می‌کنند؛ خودشان در بدنه خوانده نمی‌شوند
  }, deps);
}
