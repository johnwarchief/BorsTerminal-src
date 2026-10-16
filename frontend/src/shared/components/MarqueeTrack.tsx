// shared/components/MarqueeTrack.tsx -- نوارِ متحرکِ پیوسته، بی‌ری‌رندر در هر فریم
//
// رأیِ مأموریت (بند ۴.۱، 1405-07-20): نوارِ خلاصۀ وضعیت باید **پیوسته و نرم**
// حرکت کند تا کاربر بی‌اسکرولِ دستی سریع مرور کند؛ چرخشِ صفحه‌به‌صفحۀ
// `PageRotator` تنها حالت نبود. دو قیدی که این فایل نگه می‌دارد:
//
// ۱) حرکت UI از نرخِ داده جداست. محتوایِ اسلاید هرچه باشد همان transform
//    جلو می‌رود؛ هیچ refetch یا محاسبه‌ای درِ هر فریم صدا زده نمی‌شود.
// ۲) حرکت درِ DOM می‌ماند، نه درِ state. حلقۀِ rAF مستقیم `transform` را
//    عوض می‌کند، پس React درِ هر فریم ری‌رندر نمی‌شود (سنجشِ این بند درِ
//    `tools/ticker_motion_probe.mts` با شمارشِ ری‌رندر و شمارشِ درخواست).
//
// قواعدِ دیگر: hover/focus/تعامل ⇒ مکث؛ دکمۀ توقف/ادامه همیشه رویِ خودِ نوار
// می‌ماند (کنترلی که جا بماند درِ نگاهِ مالک «حذف‌شده» خوانده می‌شود)؛
// `prefers-reduced-motion` ⇒ بی‌حرکتِ کامل با محتوایِ چندسطریِ خوانا؛ تغییرِ
// اندازه یا محتوایِ تازه ⇒ ادامه از همان‌جا، بی‌پرشِ ناگهانی؛ و راست‌به‌چپ
// جهتِ درست دارد (محتوا از لبۀِ چپ وارد می‌شود).
import { useEffect, useRef, useState } from 'react';

import { prefersReducedMotion } from './PageRotator';

export type MarqueeState = 'running' | 'paused' | 'reduced';

export function MarqueeTrack({
  children, speedPxPerS = 42, paused = false, direction = 'rtl', testId = 'marquee',
  onStateChange,
}: {
  children: React.ReactNode;
  /** سرعتِ اسمی در پیکسل بر ثانیه — با اندازهٔ محتوا تغییر نمی‌کند */
  speedPxPerS?: number;
  /** مکثِ بیرونی (hover/focus/دکمه). کاهشِ حرکتِ سیستم بر آن اولویت دارد. */
  paused?: boolean;
  direction?: 'rtl' | 'ltr';
  testId?: string;
  onStateChange?: (s: MarqueeState) => void;
}) {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const trackRef = useRef<HTMLDivElement | null>(null);
  const xRef = useRef(0);            // جابه‌جاییِ انباشته (px)
  const sizeRef = useRef({ span: 0, wrap: 0 });
  const rafRef = useRef<number | null>(null);
  const lastRef = useRef<number | null>(null);
  const [reduced, setReduced] = useState(false);

  // ترجیعِ کاهشِ حرکتِ سیستم: یک‌بار درِ mount و با هر تغییرِ تنظیم.
  useEffect(() => {
    setReduced(prefersReducedMotion());
    let mq: MediaQueryList | null = null;
    try {
      mq = window.matchMedia('(prefers-reduced-motion: reduce)');
      const on = () => setReduced(mq?.matches === true);
      mq.addEventListener?.('change', on);
      return () => mq?.removeEventListener?.('change', on);
    } catch {
      return undefined;
    }
  }, []);

  // اندازه‌ها: «span» پهنایِ یک دورِ کاملِ محتواست (نسخۀِ دومِ همان محتوا
  // کنارش چیده شده تا درزِ انتهایی دیده نشود)، و «wrap» پهنۀِ دیدِ کاربر.
  useEffect(() => {
    const wrap = wrapRef.current;
    const track = trackRef.current;
    if (!wrap || !track) return undefined;
    const measure = () => {
      sizeRef.current = { span: track.scrollWidth / 2, wrap: wrap.clientWidth };
      // تغییرِ اندازه نباید پرش بسازد: اگر x از یکِ دور بیرون زد، همان‌جا
      // تودرتو می‌شود (محتوا تکراری است، پس چشم درز نمی‌بیند).
      const span = sizeRef.current.span;
      if (span > 0 && Math.abs(xRef.current) > span) xRef.current = xRef.current % span;
      track.style.transform = `translate3d(${px()}px,0,0)`;
    };
    measure();
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null;
    ro?.observe(wrap);
    ro?.observe(track);
    return () => ro?.disconnect();
  }, [children]);

  function px(): number {
    // راست‌به‌چپ: محتوا به سمتِ راست می‌رود تا لبۀِ چپِ اسلاید آزاد بماند
    return direction === 'rtl' ? xRef.current : -xRef.current;
  }

  useEffect(() => {
    const track = trackRef.current;
    if (!track) return undefined;
    const stop = reduced || paused;
    onStateChange?.(reduced ? 'reduced' : paused ? 'paused' : 'running');
    if (stop) {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
      lastRef.current = null;
      if (reduced) track.style.transform = 'none';   // محتوایِ چندسطریِ ایستا
      return undefined;
    }
    const tick = (t: number) => {
      const last = lastRef.current ?? t;
      const dt = Math.min(64, t - last) / 1000;      // سقفِ یک فریمِ دوبله
      lastRef.current = t;
      const { span } = sizeRef.current;
      if (span > 0) {
        xRef.current = (xRef.current + speedPxPerS * dt) % span;
        track.style.transform = `translate3d(${px()}px,0,0)`;
      }
      rafRef.current = requestAnimationFrame(tick);
      return undefined;
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
      lastRef.current = null;
    };
    // `direction` درِ px() خوانده می‌شود؛ transform هر فریم بازنویسی می‌شود
  }, [reduced, paused, speedPxPerS, direction]);

  return (
    <div
      ref={wrapRef}
      data-testid={testId}
      data-state={reduced ? 'reduced' : paused ? 'paused' : 'running'}
      data-direction={direction}
      className={`relative min-w-0 ${reduced ? 'overflow-x-auto' : 'overflow-hidden'}`}
    >
      <div
        ref={trackRef}
        data-testid={`${testId}-track`}
        className={`flex w-max ${reduced ? 'flex-wrap gap-x-6 gap-y-1' : 'flex-nowrap will-change-transform'}`}
        style={reduced ? undefined : { transform: `translate3d(${px()}px,0,0)` }}
      >
        {/* دو نسخه: یکی برایِ محتوا، یکی برایِ درزِ انتهایی. نسخهٔ دوم برایِ
            فناوریِ کمکی بی‌معناست، پس aria-hidden می‌ماند. */}
        <div className="flex shrink-0 items-baseline gap-x-5" data-testid={`${testId}-copy`}>
          {children}
        </div>
        {!reduced ? (
          <div aria-hidden className="flex shrink-0 items-baseline gap-x-5 ps-5"
               data-testid={`${testId}-copy-2`}>
            {children}
          </div>
        ) : null}
      </div>
    </div>
  );
}
