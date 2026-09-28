// shared/lib/idleGate.ts — خاموش‌کردن انیمیشن‌های بی‌پایان وقتی کسی نگاه نمی‌کند
// اندازه‌گیری روی v1.0.26: با پنجرهٔ بازِ دست‌نخورده و بازار بسته، پروسهٔ
// gpu-process ~۱۲٪ یک هسته و موتور سه‌بعدی ~۲٪ پیوسته می‌خورد در حالی که
// هیچ درخواستی به بک‌اند نمی‌رفت. مصرف از خودِ رندر بود: یک animate-pulse
// بی‌پایان هر vsync یک فریم کامپوزیت می‌سازد. تا پیش از این فقط با
// document.hidden (مینیمایز) قطع می‌شد.
//
// این ماژول دو پرچم می‌گذارد: html[data-idle] و html[data-hidden]. بقیهٔ کار در
// index.css است که انیمیشن‌ها را pause می‌کند. پولینگِ بازار به این گارد وصل نیست —
// صفحهٔ بی‌حرکت می‌تواند زنده باشد.
//
// data-hidden فقط مخفی‌بودنِ واقعیِ پنجره را می‌گوید. گاردِ بی‌حرکتیِ موس نباید
// با «کلاً پنجره نیست» یکسان فرض شود: تبِ درخت همان‌جاست که مالک بی‌حرکت نگاه
// می‌کند، و استثنایِ جریان (pilot: گزینهٔ c) باید رویِ پنجرهٔ پنهان کار نکند.
const DEFAULT_IDLE_MS = 15_000;
const DEFAULT_CHECK_MS = 2_000;
const ACTIVITY_EVENTS = ['pointerdown', 'pointermove', 'keydown', 'wheel', 'touchstart'] as const;

export function startIdleGate(
  opts: { idleMs?: number; checkMs?: number } = {},
): () => void {
  const idleMs = opts.idleMs ?? DEFAULT_IDLE_MS;
  const checkMs = opts.checkMs ?? DEFAULT_CHECK_MS;
  const root = document.documentElement;

  let lastActivity = Date.now();
  let idle = false;
  root.dataset.idle = '0';

  const setHidden = () => {
    root.dataset.hidden = document.hidden ? '1' : '0';
  };
  setHidden();

  const setIdle = (next: boolean) => {
    if (next === idle) return;
    idle = next;
    root.dataset.idle = idle ? '1' : '0';
  };

  const markActivity = () => {
    lastActivity = Date.now();
    if (idle && !document.hidden) setIdle(false);
  };

  const onVisibility = () => {
    lastActivity = Date.now();
    setHidden();
    // برگشت از مینیمایز باید فوراً انیمیشن‌ها را زنده کند، وگرنه کاربر
    // صفحهٔ یخ‌زده می‌بیند.
    setIdle(document.hidden);
  };

  const timer = window.setInterval(() => {
    setHidden();
    if (document.hidden) {
      setIdle(true);
      return;
    }
    setIdle(Date.now() - lastActivity > idleMs);
  }, checkMs);

  ACTIVITY_EVENTS.forEach((e) => window.addEventListener(e, markActivity, { passive: true }));
  document.addEventListener('visibilitychange', onVisibility);
  onVisibility();

  return () => {
    window.clearInterval(timer);
    ACTIVITY_EVENTS.forEach((e) => window.removeEventListener(e, markActivity));
    document.removeEventListener('visibilitychange', onVisibility);
    setIdle(false);
    root.dataset.hidden = '0';
  };
}
