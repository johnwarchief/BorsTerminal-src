import { useFtsCard } from '../api/useFtsCard';
import { AXES, statusFa } from '../lib/axisMeta';
import { cardStatus } from '../lib/cardStatus';

// R69: پیام‌های بارگذاری/خطا متنِ fd دارند، پس باید پس‌زمینهٔ fd هم داشته باشند.
const MESSAGE = 'bg-[var(--fd-bg)] p-2 text-[10px] leading-relaxed text-[var(--fd-text-3)]';

/**
 * واریانتِ فشردهٔ داک: پنج کارتِ کوچک فقط شماره/نامِ محور و واژهٔ وضعیت را
 * نشان می‌دهند؛ نه چارت، نه فرمول و نه ضعیف‌ترین/رتبهٔ ساختگی.
 */
export function FundamentalCards({ symbol }: { symbol: string }) {
  const query = useFtsCard(symbol);

  if (query.isLoading) {
    return (
      <p data-testid="fundamental-cards-loading"
        className={`fundamental-surface ${MESSAGE}`}>
        پنج محورِ بنیادی در حال خواندن…
      </p>
    );
  }
  if (query.isError || !query.data) {
    return (
      <p data-testid="fundamental-cards-error"
        className={`fundamental-surface ${MESSAGE}`}>
        کارت بنیادی این نماد در دسترس نیست؛ چارت و تابلو دست‌نخورده‌اند.
      </p>
    );
  }

  const card = query.data;
  return (
    <div data-testid="fundamental-cards"
      className="fundamental-surface grid grid-cols-5 gap-1 p-1 max-[900px]:grid-cols-2">
      {AXES.map((meta) => {
        const status = cardStatus(card, meta.key);
        return (
          <div key={meta.key} data-axis={meta.key}
            className="min-w-0 rounded border border-[var(--fd-line)] bg-[var(--fd-panel)] p-1.5">
            <span className="block truncate text-[9px] text-[var(--fd-text-3)]">
              {meta.num} {meta.short}
            </span>
            <b className={`block text-[11px] fd-status--${status}`}>{statusFa(status)}</b>
          </div>
        );
      })}
    </div>
  );
}
