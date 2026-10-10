// features/master/ui/FunnelErrorBanner.tsx — خطایِ قیف ≠ بازارِ خالی
// تا پیش از این `error` درِ useFtsFunnel برگردانده می‌شد ولی هیچ مصرف‌کننده‌اش آن را
// نمی‌خواند؛ شکستِ درخواست با `EMPTY` به «هیچ نمادی نبود» تبدیل می‌شد. این بنر همان
// خطا را صریح می‌گوید و Retryِ واقعی (همان query) را می‌دهد. با `hasData` فرق می‌کند:
// خطا رویِ دادهٔ قبلی ⇒ هشداریِ نوارِ بالا و جدولِ کهنه؛ خطایِ بی‌داده ⇒ جایِ خالی.
import { RetryAction } from '@shared/components/RetryAction';

export function FunnelErrorBanner({
  onRetry,
  blocking,
}: {
  onRetry: () => void;
  /** true ⇒ هیچ داده‌ای رویِ صفحه نیست و خطا جانشینِ محتوا شده است. */
  blocking?: boolean;
}) {
  return (
    <div
      role="alert"
      data-testid="funnel-error"
      className={`flex flex-wrap items-center justify-between gap-2 rounded-lg border border-dashed px-2.5 py-1.5 text-3xs ${
        blocking
          ? 'border-accent-red/50 bg-accent-red/10 text-accent-red'
          : 'border-accent-yellow/50 bg-accent-yellow/10 text-accent-yellow'
      }`}
    >
      <span>
        {blocking
          ? 'قیف FTS نمی‌رسد — این «بازارِ خالی» نیست، درخواست شکست خورده است.'
          : 'تازه‌سازیِ قیف ناموفق بود؛ عددهایِ رویِ صفحه از آخرینِ پاسخِ موفق‌اند.'}
      </span>
      <RetryAction onRetry={onRetry} testId="funnel-error-retry" />
    </div>
  );
}
