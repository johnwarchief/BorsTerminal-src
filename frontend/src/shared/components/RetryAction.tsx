// shared/components/RetryAction.tsx -- دکمهٔ «تلاش دوباره» برای حالت‌های خطا
// الگو از TapeTable گرفته شده؛ onClick باید همان refetch واقعیِ کوئری باشد،
// نه دکمهٔ تزئینی (قانون: دکمهٔ بی‌اثر ممنوع).
export function RetryAction({
  onRetry,
  testId,
}: {
  onRetry: () => void;
  testId: string;
}) {
  return (
    <button
      type="button"
      onClick={onRetry}
      data-testid={testId}
      className="rounded-lg border border-accent-blue bg-accent-blue/10 px-3 py-1 text-xs font-bold text-accent-blue"
    >
      تلاش دوباره
    </button>
  );
}
