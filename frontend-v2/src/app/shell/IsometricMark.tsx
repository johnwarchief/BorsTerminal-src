/** نشانِ ایزومتریکِ حالتِ خالی — کندلی که از سکوی تابلو بالا می‌آید. تزئینی است و نامِ دسترس‌پذیری ندارد. */
export function IsometricMark({ size = 56 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" focusable="false">
      <path d="M32 26 58 39 32 52 6 39Z" fill="var(--panel-3)" stroke="var(--line-strong)" strokeWidth="1.1" />
      <path d="M6 39v10l26 13V52" fill="none" stroke="var(--line-strong)" strokeWidth="1.1" />
      <path d="M58 39v10L32 62" fill="none" stroke="var(--line-strong)" strokeWidth="1.1" />
      <path d="M6 39 32 52 58 39" fill="none" stroke="var(--line)" strokeWidth="0.9" />
      <path d="M32 20 40 24 32 28 24 24Z" fill="var(--accent-soft)" stroke="var(--accent)" strokeWidth="1" />
      <path d="M24 24v10M40 24v10M32 28v10M24 34l8 4 8-4" fill="none" stroke="var(--line-strong)" strokeWidth="1.1" />
    </svg>
  );
}
