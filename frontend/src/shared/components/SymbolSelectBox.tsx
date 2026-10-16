// shared/components/SymbolSelectBox.tsx — جعبۀ انتخابِ کنارِ نامِ نماد
//
// مالک این را «بسیار کوچک، مزاحمِ نام، touch-friendly، واضح» خواسته (§۲). دو نکته
// که درِ این repo قبلاً آوار ساخته:
//  ۱) ردیفِ تابلو خودش `role="button"` است و Space/Enter را هم می‌گیرد
//     (`TapeTable.tsx:294-301`)؛ بی‌`stopPropagation` درِ هر دو رخداد، یک کلیکِ
//     جعبه هم انتخاب زد و هم کاربر را به صفحۀ نماد برد.
//  ۲) ستون‌هایِ تابلو با `grid-cols-[…]` دست‌چین شده‌اند و هر عنصرِ جدید درِ
//     `div` ردیف آن‌ها را جابه‌جا می‌کند («fixِ تراز ستون» درِ `TapeTable.tsx:311-313`
//     دقیقاً همین را می‌گوید). پس این جعبه **داخلِ همان سلولِ نماد** می‌نشیند،
//     نه به‌عنوانِ ستونِ تازه.
//
// هدفِ لمسیِ ۲۸px با paddingِ منفی ساخته شده: کادرِ دیدنی ۱۶px است ولی نقطۀ
// کلیک بزرگ‌تر — کوچک درِ چشم، بزرگ درِ انگشت.
import { useIsSelected } from '@shared/stores/selectedSymbolsStore';
import { useSelectedSymbolsStore } from '@shared/stores/selectedSymbolsStore';

export default function SymbolSelectBox({
  symbol,
  name = '',
  insCode = null,
  className = '',
}: {
  symbol: string;
  name?: string;
  insCode?: string | null;
  className?: string;
}) {
  const on = useIsSelected(symbol);
  const toggle = useSelectedSymbolsStore((s) => s.toggle);
  const act = (e: React.MouseEvent | React.KeyboardEvent) => {
    e.stopPropagation();
    e.preventDefault();
    toggle({ symbol, name, insCode });
  };
  const label = on
    ? `برداشتنِ انتخابِ «${symbol}» از فهرستِ رصد`
    : `انتخابِ «${symbol}» برایِ رصد`;
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={on}
      aria-label={label}
      title={label}
      data-testid={`select-box-${symbol}`}
      onClick={act}
      onKeyDown={(e) => {
        if (e.key === ' ' || e.key === 'Enter') act(e);
      }}
      // رأیِ مالک ۱۴۰۵-۰۷-۱۷: جدول تمیز بماند — جعبه فقط با hoverِ **ردیف**
      // (§29ِ مأموریت: اندروید hover ندارد ⇒ با `hover:none` همیشه دیده می‌شود)
      // یا با focus صفحه‌کلید؛ و وقتی روشن است پنهان نمی‌شود، وگرنه «کدام را
      // انتخاب کردم؟» دوباره بی‌جواب می‌ماند.
      className={`-m-1 grid shrink-0 cursor-pointer place-items-center rounded-full p-1 opacity-0 transition-opacity duration-150 group-hover:opacity-100 focus-visible:opacity-100 aria-[checked=true]:opacity-100 [@media(hover:none)]:opacity-100 motion-reduce:transition-none ${className}`}
    >
      <span
        aria-hidden
        className={`grid h-4 w-4 place-items-center rounded-[3px] border text-[10px] font-black leading-none ${
          on
            ? 'border-accent-blue bg-accent-blue/20 text-accent-blue'
            : 'border-border-c bg-bg-card/70 text-transparent hover:border-accent-blue/60'
        }`}
      >
        ✓
      </span>
    </button>
  );
}
