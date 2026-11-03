// shared/components/DefaultSymbolNotice.tsx -- «اینِ نمادِ انتخابِ شما نبود»
//
// چرا اینِ فایل هست (فاز D، بندِ ۵): سه صفحه نمادِ پیش‌فرضِ *عمدی* دارند:
//   · `TechnicalPage.tsx:59`  → `viewSymbol = symbol || 'فولاد'`
//   · `MarketChartSection`     → `initialSymbol = 'فولاد'`
//   · `WatchMarketWorkspace`   → `effective … || symbols[0]`
// هرِ سه باِ کامنتِ درِ خودِ فایل دفاع شده‌اند (تازه‌وارد بی‌چیزِ خالی نبیند، وِ فولبک
// عمداً درِ استورِ سراسری/آدرس نوشته نمی‌شود). پس کارِ درست **حذفشان نیست** — که
// همانِ باگِ رفع‌شدۀِ پیشین را برمی‌گرداند -- کارِ درست **دیدنی‌کردنِ تفاوت** است:
// تاِ امروز رابط بی‌صدا «فولاد» را نشان می‌داد وِ کاربر آن را انتخابِ خودِ می‌خواند.
//
// قاعدۀِ نمایش فقط یکِ چیز است: اگرِ نمادِ دیده‌شدن ازِ *فولبک* آمده باشد، گفته می‌شود.
// نشانیِ آدرس (URL) انتخابِ کاربر است، نه فولبک؛ وِ نمادِ خالی هم چیزی نشان نمی‌دهد.
// هیچِ عدد وِ هیچِ نامِ دیگری اینجا ساخته نمی‌شود.

/** نمادِ رویِ صحنه ازِ *فولبک* آمده، یا ازِ انتخابِ واقعیِ کاربر؟
 *
 *  پرسش باِ «مقایسهٔ دوِ رشته» جواب نمی‌دهد: `/technical/فملی` وقتی استور «فولاد»
 *  است، آدرسِ خودِ کاربر است وِ اگر باِ `shown !== selected` سنجیده شود، برچسبِ
 *  «پیش‌فرض» دروغ می‌گوید. پس اینجا «منبعِ مقدار» خوانده می‌شود: نه آدرس وِ نه استور
 *  چیزی نداشتند ⇒ صفحه فولبکش را نشان می‌دهد. */
export function isDefaultDisplay(src: {
  /** پارامترِ مسیر (`/technical/<symbol>`) */
  url?: string | null;
  /** نمادِ ذخیره‌شدۀِ سراسری */
  stored?: string | null;
  /** چیزی که واقعاً رویِ صحنه است */
  shown: string;
}): boolean {
  if (!src.shown) return false;                 // چیزی رویِ صحنه نیست
  const chosen = normalize(src.url) || normalize(src.stored);
  return !chosen;                               // فقط بی‌منبعِ واقعی، فولبک است
}

/** بی‌حساس بهِ فاصله */
function normalize(s: string | null | undefined): string {
  return (s ?? '').replace(/\s+/g, '').trim();
}

export function DefaultSymbolNotice({ shown, url, stored, testId = 'default-symbol-notice' }: {
  shown: string;
  url?: string | null;
  stored?: string | null;
  testId?: string;
}) {
  if (!isDefaultDisplay({ url, stored, shown })) return null;
  return (
    <span
      data-testid={testId}
      title="اینِ نماد راِ شما انتخاب نکردید؛ صفحۀِ بی‌انتخاب نمی‌خواهد خاموش بماند، وِ فولبک عمداً درِ استورِ سراسری یاِ آدرس نوشته نمی‌شود."
      className="num-text inline-flex max-w-[260px] items-center gap-1 truncate rounded-lg border border-tone-warn/40 bg-tone-warn/10 px-2 py-0.5 text-3xs font-bold text-tone-warn"
    >
      نمایشِ پیش‌فرض: {shown} — انتخابِ شما نبود
    </span>
  );
}
