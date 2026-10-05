// features/market/components/RegulatoryState.tsx -- وضعیتِ ناظرِ نماد درِ Inspector
// سه چیز را از همان ردیفِ تابلو می‌خواند (canonicalِ TSETMC؛ نه اندپوینتِ دوم،
// نه تطبیقِ درِ رابط): وضعیتِ معاملاتی، علتِ توقف، و نظارت.
// چهار حالت را جدا می‌گوید و حق ندارد یکی را جای دیگری بگذارد:
//   رکوردِ وضعیت هست        → همان عنوانِ مبدأ
//   رکوردی ثبت نشده          → «موردی ثبت نشده»  (نه «سالم»، نه «متوقف»)
//   ردیفِ تابلو نمی‌رسد       → «اطلاعات در دسترس نیست»
//   فید خطا داده            → همان بنرِ inspector-feed-error (اینجا تکرار نمی‌شود)
import { toFaDigits } from '@shared/lib/fmt';
import { isoToJalali } from '@shared/lib/jalaali';
import type { MarketRow } from '@shared/types/marketRow';

const NOT_RECORDED = 'موردی ثبت نشده';
const UNAVAILABLE = 'اطلاعات در دسترس نیست';

/** 20261005 → «۱۴۰۵/۰۷/۱۳»؛ بی‌اعتبار را «-» می‌دهد نه صفر */
function dEvenToJalali(d: number | null | undefined): string | null {
  if (d == null || d <= 0) return null;
  const s = String(d);
  if (s.length !== 8) return null;
  return isoToJalali(`${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`);
}

function hEvenToTime(h: number | null | undefined): string | null {
  if (h == null || h <= 0) return null;
  const s = String(h).padStart(6, '0');
  return `${s.slice(0, 2)}:${s.slice(2, 4)}:${s.slice(4, 6)}`;
}

const KIND_FA: Record<string, string> = {
  native: 'از مبدأ (TSETMC)',
  mixed: 'بخشی از مبدأ، بخشی بازسازی',
  reconstructed: 'بازسازی: حجم × میانگینِ وزنی',
};

export function RegulatoryState({
  row,
  feedFailed = false,
}: {
  row: MarketRow | null | undefined;
  feedFailed?: boolean;
}) {
  if (feedFailed || row == null) {
    return (
      <div
        data-testid="inspector-regulatory"
        data-regulatory-state="unavailable"
        className="rounded-lg border border-dashed border-[var(--hairline)] px-2 py-1 text-3xs text-text-muted"
      >
        وضعیتِ ناظر: {UNAVAILABLE}
      </div>
    );
  }

  const stopped = typeof row.stop_state === 'string' && row.stop_state.length > 0;
  const supervised = row.sup_flag != null && row.sup_flag >= 1;
  const titled = typeof row.st_title === 'string' && row.st_title.length > 0;
  const stateDate = dEvenToJalali(row.st_d);
  const stateTime = hEvenToTime(row.st_h);

  if (!stopped && !supervised && !titled) {
    return (
      <div
        data-testid="inspector-regulatory"
        data-regulatory-state="none"
        className="rounded-lg border border-dashed border-[var(--hairline)] px-2 py-1 text-3xs text-text-muted"
        title="هیچ رکوردِ وضعیتی برایِ این نماد از TSETMC نرسیده — این «سالم بودن» نیست"
      >
        وضعیتِ ناظر: {NOT_RECORDED}
      </div>
    );
  }

  const tone = stopped
    ? 'border-accent-red/40 bg-accent-red/10 text-accent-red'
    : supervised
      ? 'border-accent-amber/40 bg-accent-amber/10 text-accent-amber'
      : 'border-[var(--hairline)] bg-bg-card/40 text-text-secondary';
  const whyLines = (row.stop_reasons || '').split('\n').map((s) => s.trim()).filter(Boolean);
  const supLines = (row.sup_reasons || '').split('\n').map((s) => s.trim()).filter(Boolean);

  return (
    <div
      data-testid="inspector-regulatory"
      data-regulatory-state={stopped ? 'stopped' : supervised ? 'supervised' : 'state'}
      className={`rounded-lg border px-2 py-1 text-3xs ${tone}`}
    >
      <div className="flex flex-wrap items-baseline gap-x-1.5" data-testid="inspector-regulatory-head">
        {stopped ? (
          <span className="font-bold">متوقف — {row.stop_state}</span>
        ) : supervised ? (
          <span className="font-bold">زیرِ نظرِ سازمان</span>
        ) : (
          <span className="font-bold">{row.st_title}</span>
        )}
        {stopped && row.stop_since ? (
          <span className="text-text-muted">از {toFaDigits(row.stop_since)}</span>
        ) : null}
        {supervised && row.sup_reason_count ? (
          <span className="text-text-muted">{toFaDigits(row.sup_reason_count)} علتِ نظارت</span>
        ) : null}
        {titled ? (
          <span className="text-text-muted">
            {stateDate ? toFaDigits(stateDate) : 'بدونِ تاریخ'}
            {stateTime ? ` · ${toFaDigits(stateTime)}` : ''}
          </span>
        ) : null}
      </div>

      <details className="mt-0.5">
        <summary className="cursor-pointer select-none text-[9.5px] text-text-muted">جزئیات</summary>
        <ul className="mt-0.5 flex flex-col gap-0.5 pl-3 text-[9.5px] text-text-secondary">
          {titled ? (
            <li>
              وضعیتِ معاملاتی: {row.st_title}
              {row.st_code ? ` (کدِ مبدأ ${row.st_code})` : ''}
            </li>
          ) : (
            <li>وضعیتِ معاملاتی: {NOT_RECORDED}</li>
          )}
          {whyLines.length > 0 ? (
            <li className="text-text-muted">
              علتِ توقف:{' '}
              {whyLines.map((w, i) => (
                <span key={i}>{i > 0 ? '؛ ' : ''}{w}</span>
              ))}
            </li>
          ) : stopped ? (
            <li className="text-text-muted">علتِ توقف: {NOT_RECORDED}</li>
          ) : null}
          {supLines.length > 0 ? (
            <li className="text-text-muted">
              علتِ نظارت:{' '}
              {supLines.map((w, i) => (
                <span key={i}>{i > 0 ? '؛ ' : ''}{w}</span>
              ))}
            </li>
          ) : null}
          {/* مبدأِ عددِ ریالیِ حقیقی/حقوقی — فقط اینجا خوانده می‌شود، نه درِ ستونِ تابلو،
              و هرگز واردِ داوری نمی‌شود. */}
          <li title="پیش‌آمدِ ریالی از خودِ TSETMC می‌آید یا از حجم × میانگینِ وزنی ساخته شده">
            مبدأِ ارزشِ معامله: {KIND_FA[row.ctv_kind ?? 'reconstructed'] ?? UNAVAILABLE}
          </li>
        </ul>
      </details>
    </div>
  );
}
