export function HoldingNavPanel({ bankLike }: { bankLike: boolean }) {
  return (
    <section data-testid="holding-pnav-panel" className="rounded border border-[var(--fd-line)] bg-[var(--fd-panel)] p-2 fd-meta">
      <div className="mb-1 flex items-center justify-between gap-2">
        <h3 className="fd-meta  text-[var(--fd-text-2)]">
          {bankLike ? 'ارزش‌گذاری بانک' : 'ارزش‌گذاری هلدینگ'}
        </h3>
        <span className="rounded border border-[var(--fd-warn)] px-1 text-[var(--fd-warn)]">N/A</span>
      </div>
      <p data-testid="holding-nav-na" className="leading-relaxed text-[var(--fd-text-2)]">
        {bankLike
          ? 'N/A — قابل ارزیابی نیست؛ این نماد بانک/مؤسسهٔ اعتباری است و P/NAV برای این طبقه تعریف نشده است.'
          : 'N/A — قابل ارزیابی نیست؛ این نماد سرمایه‌گذاری/هلدینگ است و در کدال ارزش خالص دارایی (NAV) منتشر نشده؛ بنابراین P/NAV محاسبه نمی‌شود و جای آن عددی گذاشته نمی‌شود.'}
      </p>
      <p className="mt-1 text-[var(--fd-text-3)]">
        {bankLike
          ? 'بانک‌ها از شرط «نسبت فروش به ارزش بازار» (شاخص ۴) معاف‌اند.'
          : 'هلدینگ‌ها از شرط «نسبت فروش به ارزش بازار» (شاخص ۴) معاف‌اند.'}
      </p>
    </section>
  );
}
