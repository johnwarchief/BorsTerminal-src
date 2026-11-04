import { useState } from 'react';
import { toFaDigits } from '@shared/lib/fa';
import { jalaliFromYmd } from '@shared/lib/jalali';
import { useCodalHealth } from '../api/useCodalHealth';
import { useFtsCard, type FtsCard } from '../api/useFtsCard';
import { useSectorPe } from '../api/useSectorPe';
import { isBankCard, isHoldingCard } from '../lib/assetScope';
import { statusFa, verdictFa, type AxisKey, type AxisStatus } from '../lib/axisMeta';
import { cardStatus } from '../lib/cardStatus';
import { useFundamentalPrefs } from '../stores/prefs';
import { CodalHealthStrip } from './CodalHealthStrip';
import { CorporateCalendar } from './CorporateCalendar';
import { FtsSettingsTrigger } from './FtsSettingsDrawer';
import { HoldingNavPanel } from './HoldingNavPanel';
import { Quintet } from './Quintet';
import { EpsPanel } from './panels/EpsPanel';
import { EvidencePanel } from './panels/EvidencePanel';
import { GrowthPanel } from './panels/GrowthPanel';
import { HistoryPanel } from './panels/HistoryPanel';
import { IndustryPanel } from './panels/IndustryPanel';
import { MarginPanel } from './panels/MarginPanel';
import { SalesPanel } from './panels/SalesPanel';

interface Props {
  symbol: string;
  onBack: () => void;
}

const AXIS_ORDER: AxisKey[] = ['growth', 'eps', 'margin', 'sales', 'industry'];

const STATUS_COLOR: Record<AxisStatus, string> = {
  pass: 'var(--fd-up)',
  fail: 'var(--fd-down)',
  na: 'var(--fd-flat)',
  unknown: 'var(--fd-warn)',
};

const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;

/** R48: as_of تاریخ‌تنها شمسی می‌شود؛ هر رشتهٔ دیگر عیناً می‌ماند. */
function freshnessLabel(asOf: string | null | undefined): string {
  if (!asOf) return 'تازگی نامشخص';
  const parts = DATE_ONLY.exec(asOf);
  if (parts) return `دادهٔ بنیادی تا ${jalaliFromYmd(Number(`${parts[1]}${parts[2]}${parts[3]}`))}`;
  return `دادهٔ بنیادی تا ${asOf}`;
}

function scoreLabel(score: number | null | undefined): string {
  return score == null ? '—' : toFaDigits(score);
}

/**
 * روبانِ امتیاز: شمارشِ همان پنج وضعیتِ `cardStatus`، بدونِ منطقِ دوم.
 * R57: هیچ برچسبِ «قوی‌ترین/ضعیف‌ترین» ساخته نمی‌شود؛ فقط شمارش‌ها، حکم و امتیاز.
 */
function ScoreRibbon({ card }: { card: FtsCard }) {
  const statuses = AXIS_ORDER.map((axis) => cardStatus(card, axis));
  const passed = statuses.filter((status) => status === 'pass').length;
  const failed = statuses.filter((status) => status === 'fail').length;
  const abstained = statuses.filter((status) => status === 'na' || status === 'unknown').length;
  return (
    <div
      data-testid="fundamental-score-ribbon"
      className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--fd-line)] bg-[var(--fd-panel-2)] px-2.5 py-1.5 text-[10px] text-[var(--fd-text-3)]"
    >
      <strong className="text-[var(--fd-text)]">{toFaDigits(passed)} از ۵ محور {statusFa('pass')}</strong>
      <span className="flex gap-1" aria-hidden="true">
        {statuses.map((status, index) => (
          <span
            key={AXIS_ORDER[index]}
            className={`h-1.5 w-6 rounded-full fd-status--${status}`}
            style={{ background: STATUS_COLOR[status] }}
            title={statusFa(status)}
          />
        ))}
      </span>
      {failed ? <span className="text-[var(--fd-down)]">{toFaDigits(failed)} {statusFa('fail')}</span> : null}
      {abstained ? <span>{toFaDigits(abstained)} {statusFa('na')}/{statusFa('unknown')}</span> : null}
      <span className="ms-auto">{verdictFa(card.verdict)} · امتیاز {scoreLabel(card.score)}/۵</span>
    </div>
  );
}

export function FundamentalDetail({ symbol, onBack }: Props) {
  const query = useFtsCard(symbol);
  const sectorPe = useSectorPe(symbol);
  const health = useCodalHealth();
  const surface = useFundamentalPrefs((state) => state.surface);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const card = query.data;

  if (query.isLoading) {
    return (
      <section
        data-testid="fundamental-detail-loading"
        data-fund-surface={surface}
        className="fundamental-surface p-3 text-[11px] text-[var(--fd-text-3)]"
      >
        کارت پنج‌محور در حال خواندن…
      </section>
    );
  }
  if (query.isError || !card) {
    return (
      <section
        data-testid="fundamental-detail-error"
        data-fund-surface={surface}
        className="fundamental-surface p-3 text-[11px] text-[var(--fd-text-3)]"
      >
        کارت بنیادی در دسترس نیست.{' '}
        <button type="button" onClick={() => void query.refetch()} className="tape-btn">تلاش دوباره</button>
      </section>
    );
  }

  const holding = isHoldingCard(card);
  const bank = isBankCard(card);
  const notApplicable = card.applicable === false;
  const focusAxis = (axis: string) => {
    const panel = document.getElementById(`panel-${axis}`);
    panel?.scrollIntoView?.({ block: 'start', behavior: 'smooth' });
  };

  return (
    <section
      data-testid="fundamental-detail"
      data-fund-surface={surface}
      className="fundamental-surface flex min-h-0 flex-1 flex-col bg-[var(--fd-bg)] text-[var(--fd-text)]"
    >
      <header className="flex flex-none flex-wrap items-baseline gap-2 border-b border-[var(--fd-line)] px-3 py-2">
        <button type="button" data-testid="fundamental-back" onClick={onBack} className="tape-btn">
          ← جدول بنیادی
        </button>
        <b data-testid="fundamental-title" className="t-125 font-extrabold">{symbol}</b>
        {card.sector ? <span className="t-9 text-[var(--fd-text-3)]">{card.sector}</span> : null}
        {holding ? (
          <span
            data-testid="holding-class-badge"
            className="rounded border border-[var(--fd-accent)] px-1 text-[9px] text-[var(--fd-accent)]"
          >
            {bank ? 'بانک / مؤسسهٔ اعتباری' : 'هلدینگ / سرمایه‌گذاری'}
          </span>
        ) : null}
        <span data-testid="fundamental-verdict" className="rounded border border-[var(--fd-line-strong)] px-1 text-[9px]">
          {verdictFa(card.verdict)}
        </span>
        <span className="num t-9">امتیاز {scoreLabel(card.score)}/۵</span>
        <span data-testid="fundamental-freshness" className="ms-auto text-[10px] text-[var(--fd-text-3)]">
          {freshnessLabel(card.freshness?.as_of)}
        </span>
        <FtsSettingsTrigger open={settingsOpen} onToggle={() => setSettingsOpen((value) => !value)} />
      </header>

      {notApplicable ? (
        <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-2">
          <section
            data-testid="fundamental-not-applicable"
            className="rounded-lg border border-[var(--fd-line)] bg-[var(--fd-panel)] p-2.5 text-[10px] leading-relaxed text-[var(--fd-text-2)]"
          >
            FTS ندارد — این نماد صندوق/ابزار است و غربالگری پنج‌شاخص برای آن تعریف نشده است.
          </section>
          <CorporateCalendar symbol={symbol} />
          <CodalHealthStrip health={health.data} loading={health.isLoading} />
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-2">
          <Quintet card={card} onFocus={focusAxis} />
          <ScoreRibbon card={card} />
          <div className="grid grid-cols-12 gap-2">
            <div className="col-span-7 max-[1050px]:col-span-12"><GrowthPanel card={card} /></div>
            <div className="col-span-5 max-[1050px]:col-span-12"><EpsPanel card={card} /></div>
            <div className="col-span-5 max-[1050px]:col-span-12"><MarginPanel card={card} /></div>
            <div className="col-span-7 max-[1050px]:col-span-12"><SalesPanel card={card} /></div>
            <div className="col-span-7 max-[1050px]:col-span-12">
              {holding ? <HoldingNavPanel bankLike={bank} /> : <IndustryPanel card={card} sectorPe={sectorPe.data} />}
            </div>
            <div className="col-span-5 max-[1050px]:col-span-12"><HistoryPanel card={card} /></div>
            <div className="col-span-12"><EvidencePanel card={card} /></div>
            <div className="col-span-12"><CorporateCalendar symbol={symbol} /></div>
            <div className="col-span-12"><CodalHealthStrip health={health.data} loading={health.isLoading} /></div>
          </div>
        </div>
      )}
    </section>
  );
}
