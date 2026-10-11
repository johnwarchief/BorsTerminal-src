// features/portfolio/components/SymbolWatchAction.tsx — «به دیده‌بان اضافه کن»
//
// چرا: نمادی که از چهار گامِ غربالگری رد شده و درِ «تحویل» نشسته، تا پیش از این
// فقط راهِ «سبد» را داشت (تصمیمِ سرمایه‌ای با وزن و حد ضرر). اما بیشترِ وقتِ مالک
// بینِ «همین حالا نمی‌خرم» و «نمی‌خواهم گمش کنم» است — یعنی رصد. این دکمه همان
// را درِ یک کلیک می‌کند و نماد را درِ تبِّ اصلیِ «دیده‌بان بازار» می‌گذارد.
// منبعِ داده همان `watchSymbolsStore`ِ خودِ زیرتب است (localStorageِ همین دستگاه،
// بی‌درخواستِ تازه به سرور) — فهرستِ ستاره‌هایِ سرور (/api/watchlist) جداست و
// این دکمه به آن دست نمی‌زند.
import { toFaDigits } from '@shared/lib/fmt';
import { normalizeFa } from '@shared/lib/normalizeFa';
import { WATCH_MAX, useWatchSymbolsStore } from '../stores/watchSymbolsStore';

export function SymbolWatchAction({ symbol }: { symbol: string }) {
  const symbols = useWatchSymbolsStore((s) => s.symbols);
  const add = useWatchSymbolsStore((s) => s.add);
  const remove = useWatchSymbolsStore((s) => s.remove);
  const norm = normalizeFa(symbol);
  const on = symbols.some((x) => normalizeFa(x) === norm);
  const full = !on && symbols.length >= WATCH_MAX;
  return (
    <button
      type="button"
      data-testid={`watch-action-${symbol}`}
      aria-pressed={on}
      disabled={full}
      title={full
        ? `دیده‌بان پر است (${toFaDigits(symbols.length)} از ${toFaDigits(WATCH_MAX)}) — اول یکی را بردار`
        : on
          ? 'درِ دیده‌بان بازار است؛ کلیک برای بیرون آمدن'
          : 'افزودن به تبِّ اصلیِ دیده‌بان بازار'}
      onClick={() => (on ? remove(symbol) : add(symbol))}
      className={`shrink-0 rounded-full border px-2 py-0.5 text-2xs font-bold transition-colors ${
        full
          ? 'cursor-not-allowed border-border-c bg-bg-card/40 text-text-muted'
          : on
            ? 'border-accent-green/50 bg-accent-green/15 text-accent-green'
            : 'border-border-c bg-bg-card/60 text-text-muted hover:border-accent-green/50 hover:text-accent-green'
      }`}
    >
      {on ? 'درِ دیده‌بان' : 'دیده‌بان+'}
    </button>
  );
}

export default SymbolWatchAction;
