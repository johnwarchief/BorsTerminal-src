// features/market/components/BuySellCell.tsx — ستونِ «خرید/فروشِ» تابلو، یک نسخه
//
// از درونِ `TapeTable.tsx` بی‌کم‌وکاست منتقل شد (§۲۵ِ task: سایدبار و تابلو دو
// implementation از یک چیز نمی‌سازند). همان دو سرانه، همان نوارِ دوسُره و همان
// نسبت، حالا هم درِ ردیفِ تابلو و هم درِ «در یک نظرة»یِ سایدبار خوانده می‌شود.
// رنگِ نسبت از همان آستانه‌هایِ ۱.۵/۰.۸ِ نبض بازار می‌آید — این‌جا داوری نمی‌شود.
import { fmtInt, toFaDigits } from '@shared/lib/fmt';
import { FlashNum } from '@shared/components/FlashNum';
import { buySellShare } from '../lib/tapeFts';
import { powerTone } from '../api/useMarketPulse';

/** رنگِ عددِ نسبت از همان آستانه‌های ۱.۵/۰.۸ِ نبض بازار — این‌جا داوری نمی‌شود */
function powerClass(tone: 'good' | 'mid' | 'bad' | null): string {
  if (tone === 'good') return 'text-accent-green font-bold';
  if (tone === 'bad') return 'text-accent-red font-bold';
  if (tone === 'mid') return 'text-accent-yellow';
  return 'text-text-secondary';
}

const mt = (v: number | null): string => (v == null ? '—' : `${toFaDigits(v.toFixed(1))} م.ت`);

/** سرانه به میلیون تومان: عددِ tabular + واحدِ جدا. واحد در spanِ خودش است چون
 *  `.num` جهت را ltr می‌کند و «۵.۰ م.ت» را در آن «م.ت ۵.۰» می‌خواند. داده نیست ⇒
 *  فقط «—»؛ صفرِ جعلی نه. بالای ۱۰۰ اعشار نمی‌ماند (همان قاعدهٔ ستونِ ارزش):
 *  سرانۀِ صدها میلیونی با یک رقم اعشار در ستونِ ۱۱۸ پیکسلی جا نمی‌شد. */
function pcText(v: number): string {
  return v >= 100 ? fmtInt(v) : toFaDigits(v.toFixed(1));
}

function PcNum({ v, className, testId }: { v: number | null; className: string; testId: string }) {
  return (
    <span data-testid={testId} className={`flex shrink-0 items-baseline gap-px ${className}`}>
      {/* سرانه‌ها هم مثلِ بقیۀِ ستون‌هایِ عددی فلاش می‌گیرند (#12): تا پیش از این
          تنها «نسبتِ خرید/فروش» رنگ می‌دید و دو عددِ بالایِ همان خانه بی‌خبر عوض
          می‌شدند. */}
      <FlashNum
        value={v}
        className="num font-bold"
        render={(x) => (x == null ? '—' : pcText(x))}
      />
      {v != null && <span className="text-3xs opacity-80">م.ت</span>}
    </span>
  );
}

/**
 * خانهٔ خرید/فروش (#146 و #172): دو خط. بالا خودِ دو سرانه (میلیون تومان) — سبز
 * خرید در راست، قرمز فروش در چپ؛ پایین نوارِ سهم و نسبتِ خرید به فروش. تا پیش از
 * #172 دو سرانه فقط در title بود و «با دیدنِ ستون جزئیات زیادی نمی‌داد».
 * یک طرف غایب ⇒ «—» و بی‌نوار: نبودِ داده «فروش صفر» یا «خرید صددرصد» نیست.
 */
export function BuySellCell({
  buyPc,
  sellPc,
  power,
  testId = 'tape-buy-sell',
}: {
  buyPc: number | null;
  sellPc: number | null;
  power: number | null | undefined;
  testId?: string;
}) {
  const share = buySellShare(buyPc, sellPc);
  return (
    <span
      data-testid={testId}
      className="flex min-w-0 flex-col gap-0.5"
      title={`سرانۀ خرید ${mt(buyPc)} · سرانۀ فروش ${mt(sellPc)} — نسبتِ خرید به فروش ${
        power == null ? '—' : `${toFaDigits(power.toFixed(2))}×`
      }`}
    >
      <span className="flex min-w-0 items-baseline justify-between gap-1 text-3xs leading-none">
        <PcNum v={buyPc} className="text-accent-green" testId="tape-buy-pc" />
        <PcNum v={sellPc} className="text-accent-red" testId="tape-sell-pc" />
      </span>
      <span className="flex min-w-0 items-center gap-1">
        <span dir="rtl" aria-hidden className="flex h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-bg-card/80">
          {share == null ? null : (
            <>
              <span className="bg-accent-green transition-[width] duration-300 ease-out" style={{ width: `${share * 100}%` }} />
              <span className="bg-accent-red transition-[width] duration-300 ease-out" style={{ width: `${(1 - share) * 100}%` }} />
            </>
          )}
        </span>
        <span className={`num shrink-0 text-2xs ${powerClass(powerTone(power))}`}>
          <FlashNum value={power} render={(v) => (v == null ? '-' : toFaDigits(v.toFixed(2)))} />
        </span>
      </span>
    </span>
  );
}
