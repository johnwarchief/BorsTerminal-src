// features/market/components/MarketStatusPanel.tsx — «وضعیت بازار»، سه مفهوم جدا
//
// چرا این پنل هست: نشانگرِ تازگی درِ Topbar فقط می‌دانست «درخواستِ آخر موفق بود».
// سنجشِ زندهٔ ۱۴۰۵-۰۷-۱۸ (۱۱:۰۶ تا ۱۱:۲۲، بازارِ باز): `revision` نودوچهار و
// نیم دقیقه اصلاً تکان نخورد و همان‌وقت برچسب «(به‌روزرسانی: لحظاتی پیش)» می‌گفت.
// پس سه چیز باید جدا خوانده شود و جدا دیده شود:
//   ۱) اتصال      — درخواست به بک‌اند می‌رسد؟ (از خودِ Market Feed)
//   ۲) دریافت     — سرور آخرین بار چه وقت از بازار داده گرفت؟ (`last_cycle_at`)
//   ۳) تازگیِ داده — آخرین بار چه وقت *عددی* عوض شد؟ (`rev_at` درِ فید)
// هیچ‌کدام از این سه جای دو تای دیگر را پر نمی‌کند و هیچ عددی اینجا ساخته نمی‌شود:
// همه از `/api/live-stats` (پنجره، تیک، جهان) و از خودِ فیدِ تابلو می‌آیند.
import { useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { MARKET_FEED_KEY } from '@shared/api/marketFeed';
import type { MarketFeed } from '@shared/types/marketRow';
import { computeFeedStatus } from '@shared/lib/feedFreshness';
import { isMarketOpen } from '@shared/lib/marketHours';
import { toFaDigits } from '@shared/lib/fmt';
import { useLiveStats } from '../api/useLiveStats';

function fmtSpan(ms: number | null | undefined): string {
  if (ms == null) return '—';
  const s = Math.round(ms / 1000);
  if (s < 60) return `${toFaDigits(s)} ثانیه`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${toFaDigits(m)} دقیقه`;
  return `${toFaDigits(Math.floor(m / 60))} ساعت و ${toFaDigits(m % 60)} دقیقه`;
}

function fmtSec(s: number | null | undefined): string {
  if (s == null) return '—';
  return s < 90 ? `${toFaDigits(Math.round(s))} ثانیه` : `${toFaDigits(Math.round(s / 60))} دقیقه`;
}

/** «۲۰۲۶-۱۰-۱۰ ۱۱:۰۶:۳۶» (ساعتِ محلیِ همان ماشین که سرور روی آن است) → epoch ms. */
function parseLocalStamp(stamp: string | null | undefined): number | null {
  if (!stamp) return null;
  const t = new Date(stamp.replace(' ', 'T')).getTime();
  return Number.isFinite(t) ? t : null;
}

/** یک تراشۀ برچسب‌دار درِ همان خطِ جمع‌وجور. */
function Chip({ label, value, tone, title, testId }: {
  label: string; value: string; tone: string; title?: string; testId?: string;
}) {
  return (
    <span
      title={title ?? label}
      data-testid={testId}
      className={`inline-flex items-center gap-1 rounded-full border border-border-c px-2 py-0.5 text-3xs font-bold ${tone}`}
    >
      <span className="text-text-muted">{label}</span>
      <span className="num">{value}</span>
    </span>
  );
}

const UNIVERSE_LABEL: Record<string, string> = {
  total: 'کلِ تابلو',
  trading: 'در حالِ معامله',
  quote: 'مظنه بی‌معامله',
  no_trade: 'بدونِ معاملۀ اخیر',
  suspended: 'متوقف',
  stale: 'دادهٔ کهنه',
  unknown: 'نامعلوم',
  market_closed: 'بازار بسته',
  eligible: 'واجدِ غربالگری',
  duplicate_rows: 'ردیفِ تکراری',
  observed_rows: 'نماد دیدۀ‌شده',
};

export function MarketStatusPanel() {
  const qc = useQueryClient();
  const { data: stats, isError, error, refetch } = useLiveStats();
  const [open, setOpen] = useState(false);
  // ساعتِ خودِ پنل: اگر فقط به داده‌یِ کوئری تکیه کنیم، تا `live-stats` عوض نشود
  // رندر نمی‌شود و «سنِ داده» رویِ عددِ همان لحظه می‌ماند (سنجشِ مرورگر: «۵۱ ثانیه»
  // یکِ دقیقه ثابت ماند). ۱۵ ثانیه یک‌بار بی‌هزینه است و همین پنجرۀِ کوئری است.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 15_000);
    return () => clearInterval(id);
  }, []);

  // اتصال/دریافت/تازگی از همان فیدِ مشترک (بدونِ درخواستِ دوم).
  const feed = useMemo(() => {
    const q = qc.getQueryCache().find({ queryKey: MARKET_FEED_KEY });
    const d = q?.state.data as MarketFeed | undefined;
    return {
      status: q?.state.status ?? 'idle',
      dataUpdatedAt: q?.state.dataUpdatedAt ?? 0,
      revAt: d?.rev_at ?? null,
      rev: d?.rev ?? null,
      liveCount: d?.live_count ?? null,
      total: d?.count ?? null,
      fossil: d?.fossil_count ?? null,
      lastSync: d?.meta?.last_sync ?? null,
    };
    // `now` تنها برایِ سن است؛ تیکِ هر رندرِ همین پنل کافی است (۱۵ ثانیه).
  }, [qc, now]);

  const fs = computeFeedStatus({
    status: feed.status, dataUpdatedAt: feed.dataUpdatedAt, dataChangedAt: feed.revAt,
    liveCount: feed.liveCount, totalCount: feed.total, now,
  });
  const d = stats?.data ?? {};
  const win = d.window ?? {};
  const tick = d.tick ?? {};
  const uni = d.universe ?? {};
  const counts = uni.counts ?? {};
  // «آخرین باری که سرور از بازار داده گرفت» — زمانِ خودِ بک‌اند (ضربانِ چرخۀ تیک)،
  // نه زمانِ رسیدنِ پاسخ به این مرورگر. بی‌این، هر دورِ «unchanged» هم «تازه» خوانده
  // می‌شود و همان دروغِ «لحظاتی پیش» رویِ دادهٔ نودوچهار دقیقه یخ‌زده تکرار می‌شود.
  const cycleAtMs = parseLocalStamp(d.last_cycle_at ?? feed.lastSync);
  const cycleAgoMs = cycleAtMs == null ? null : Math.max(0, now - cycleAtMs);
  const marketOpenBackend = win.market_open ?? isMarketOpen(new Date(now));
  const stalledByServer = typeof tick.cooldown_remaining_s === 'number'
    && tick.cooldown_remaining_s > 0;

  const tone = (ok: boolean) => (ok ? 'text-accent-green' : 'text-accent-yellow');

  return (
    <section
      data-testid="market-status-panel"
      className="glass-panel w-full rounded-xl border border-border-c bg-bg-card/45 px-3 py-1.5"
      aria-label="وضعیت بازار"
    >
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          data-testid="msp-toggle"
          title="باز کردنِ جزئیاتِ وضعیتِ تابلو"
          className="text-2xs font-black text-text-primary hover:text-accent-blue"
        >
          وضعیت بازار
        </button>
        <Chip
          label="بازار"
          value={marketOpenBackend ? 'باز' : 'بسته'}
          tone={marketOpenBackend ? 'text-accent-green' : 'text-text-muted'}
          title="پنجرۀ معاملۀ تابلو از خودِ بک‌اند (۰۸:۴۵–۱۲:۳۰ تهران)"
        />
        <Chip
          label="اتصال"
          value={fs.connection === 'ok' ? 'رسید' : fs.connection === 'error' ? 'نمی‌رسد' : 'در راه'}
          tone={fs.connection === 'ok' ? 'text-accent-green'
            : fs.connection === 'error' ? 'text-accent-red' : 'text-accent-yellow'}
          title={`آخرین پاسخِ فید: ${fmtSpan(feed.dataUpdatedAt ? now - feed.dataUpdatedAt : null)} پیش`}
        />
        <Chip
          label="آخرین دادهٔ بازار"
          value={cycleAgoMs == null ? 'گزارش نشده' : fmtSpan(cycleAgoMs)}
          tone={tone(cycleAgoMs == null || cycleAgoMs < 60_000)}
          title={`چرخۀ تیکِ سرور: ${d.last_cycle_at ?? '—'} · ویرایش: ${toFaDigits(d.revision ?? 0)}`}
        />
        <Chip
          label="عوض‌شدنِ عدد"
          value={feed.revAt ? fmtSpan(now - feed.revAt) : 'نامعلوم'}
          tone={tone(fs.freshness === 'live' || fs.freshness === 'closed')}
          testId="msp-data-age"
          title="سنِ آخرینِ revisionِ دیده‌شده در همین مرورگر — «تازگی» یعنی همین، نه رسیدنِ پاسخ"
        />
        <Chip
          label="ویرایش"
          value={toFaDigits(feed.rev ?? 0)}
          tone="text-text-secondary"
          title={`ردیفِ نشستِ جاری: ${toFaDigits(feed.liveCount ?? 0)} از ${toFaDigits(feed.total ?? 0)}`}
        />
        {stalledByServer ? (
          <Chip
            label="خنک"
            value={fmtSec(tick.cooldown_remaining_s ?? null)}
            tone="text-accent-red"
            testId="msp-cooldown"
            title="بازارِ TSETMC پاسخِ ۴۲۹ داده؛ حلقۀ تیکِ سرور موقتاً توقف می‌کند"
          />
        ) : null}
        {isError ? (
          <button
            type="button"
            data-testid="msp-retry"
            onClick={() => void refetch()}
            className="rounded-full border border-accent-red/50 bg-accent-red/10 px-2 py-0.5 text-3xs font-bold text-accent-red"
            title={String((error as Error | null)?.message ?? error)}
          >
            وضعیتِ نامعلوم — دوباره
          </button>
        ) : null}
      </div>

      {open ? (
        <div className="mt-1.5 grid grid-cols-1 gap-x-6 gap-y-1 border-t border-border-c/60 pt-1.5 text-2xs text-text-secondary md:grid-cols-3">
          <div className="flex flex-col gap-0.5">
            <span className="font-black text-text-primary">پنجره‌ها (از بک‌اند)</span>
            <span>معاملۀ تابلو: {win.market_open == null ? 'نامعلوم' : win.market_open ? 'باز' : 'بسته'}</span>
            <span>پنجرۀ سینکِ نبض: {win.sync_window == null ? 'نامعلوم' : win.sync_window ? 'باز' : 'بسته'}</span>
            <span>نوشتنِ تیک: {win.tick_writes == null ? 'نامعلوم' : win.tick_writes ? 'فعال' : 'خاموش'}</span>
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="font-black text-text-primary">حلقۀ تیک</span>
            <span>چرخه‌ها: {toFaDigits(d.cycles ?? 0)} · بدونِ تغییر: {toFaDigits(d.nochange_cycles ?? 0)}</span>
            <span>مدتِ آخرین چرخه: {tick ? fmtSec(d.last_cycle_s ?? null) : '—'}</span>
            <span className="num">گوش‌دادن: {tick.listening ? 'بله' : 'نه'} ·
              بی‌تغییری: {fmtSec(tick.since_change_s ?? null)}</span>
            <span className="num">درخواست‌های خنک‌شده: {toFaDigits(tick.cooldown_level ?? 0)} ·
              آویزان بیش از ۱۰s: {toFaDigits(tick.cycle?.slow_over_10s ?? 0)}</span>
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="font-black text-text-primary">جهانِ نمادها</span>
            {Object.keys(UNIVERSE_LABEL).filter((k) => counts[k] != null).map((k) => (
              <span key={k} className="num flex justify-between gap-2">
                <span>{UNIVERSE_LABEL[k]}</span>
                <span className="font-bold text-text-primary">{toFaDigits(counts[k])}</span>
              </span>
            ))}
            {uni.observed_rows ? (
              <span className="text-3xs text-text-muted">
                مشاهده در ویرایشِ {toFaDigits(uni.revision ?? 0)}
              </span>
            ) : (
              <span className="text-3xs text-accent-yellow">جهان هنوز در این اجرا مشاهده نشده</span>
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}

export default MarketStatusPanel;
