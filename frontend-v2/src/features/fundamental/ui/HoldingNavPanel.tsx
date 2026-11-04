export function HoldingNavPanel({ bankLike }: { bankLike: boolean }) {
  return (
    <section data-testid="holding-pnav-panel" className="rounded-[var(--radius-sm)] border border-line bg-panel p-2 t-9">
      <div className="mb-1 flex items-center justify-between gap-2">
        <h3 className="t-10 font-bold text-text-2">
          {bankLike ? 'ارزش‌گذاری بانک' : 'ارزش‌گذاری هلدینگ'}
        </h3>
        <span className="rounded-[3px] border border-warn/40 bg-warn/10 px-1 text-warn">N/A</span>
      </div>
      <p data-testid="holding-nav-na" className="leading-relaxed text-text-2">
        {bankLike
          ? 'N/A — قابل ارزیابی نیست؛ این نماد بانک/مؤسسهٔ اعتباری است و P/NAV برای این طبقه تعریف نشده است.'
          : 'N/A — قابل ارزیابی نیست؛ این نماد سرمایه‌گذاری/هلدینگ است و در کدال ارزش خالص دارایی (NAV) منتشر نشده؛ بنابراین P/NAV محاسبه نمی‌شود و جای آن عددی گذاشته نمی‌شود.'}
      </p>
      <p className="mt-1 text-text-3">
        {bankLike
          ? 'بانک‌ها از شرط «نسبت فروش به ارزش بازار» (شاخص ۴) معاف‌اند.'
          : 'هلدینگ‌ها از شرط «نسبت فروش به ارزش بازار» (شاخص ۴) معاف‌اند.'}
      </p>
    </section>
  );
}
