// features/portfolio/components/TargetBanner.tsx -- بنر راهنمای سناریوی اقتصادی FTS
// کارت اعلان آبی با آیکون هدف + فرمول ریسک سیستماتیک.
export function TargetBanner() {
  return (
    <div className="rounded-2xl border border-accent-blue/35 bg-accent-blue/10 p-4" role="note" aria-label="راهنمای سناریوی اقتصادی FTS">
      <div className="flex items-start gap-3">
        <span
          aria-hidden
          className="neon-edge-cyan mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-neon-cyan to-blue-600 text-base font-black text-black"
        >
          ◎
        </span>
        <div className="min-w-0">
          <h3 className="text-sm font-black text-accent-blue">پیشنهاد اقتصادی و مدیریت سرمایه FTS</h3>
          <p className="mt-1 break-words text-xs leading-6 text-text-secondary">
            سعی کنید ترکیب دارایی‌های خود را با سیگنال‌های دریافتی به این ترکیب دارایی نزدیک کنید.
          </p>
          <p className="mt-1.5 break-words text-2xs leading-5 text-text-muted">
            فرمول ریسک سیستماتیک: حداکثر ۲۰٪ سهام + دو تا سه برابر طلا جهت پوشش ریسک تورمی/جنگی.
          </p>
        </div>
      </div>
    </div>
  );
}
