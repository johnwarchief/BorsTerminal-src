// features/fundamental/routes/FundamentalPage.tsx -- صفحه تحلیل بنیادی (ایجنت 1)
// حالت بدون نماد = دیده‌بان کلان بازار (ماتریس ۵ شاخص FTS)؛ با انتخاب نماد
// از جدول، نمای کالبدشکافی تک‌سهم باز میشود.
// کارت FTS تعاملی است: کلیک روی هر سلول، پنل Drill-Down همان شاخص را
// با نمودار و فرمول شفاف باز می‌کند. هلدینگ‌ها به‌جای P/E با P/NAV
// محاسبه می‌شوند (آخرین EPS ۱۲ماهه به‌عنوان جانشین NAV تا وقتی بک‌اند
// ستون NAV منتشر کند) و از مقایسه با گروه نامربوط «سایر» پرهیز می‌شود.
import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router';
import { Badge } from '@shared/components/Badge';
import { EmptyState } from '@shared/components/EmptyState';
import { http, HttpError } from '@shared/api/http';
import { toFaDigits } from '@shared/lib/fmt';
import { statementAgeDays } from '@shared/lib/jalaali';
import { publishSignal } from '@shared/lib/signalBus';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useFtsCard } from '../api/useFtsCard';
import { useQuarters } from '../api/useQuarters';
import { useSectorBoard } from '../api/useSectorBoard';
import { useFtsScreen } from '../api/useFtsScreen';
import { groupBySymbol, useCalendarUpcoming } from '../api/useCalendarUpcoming';
import { deCumulateQuarters, profitYoY, sectorMedianPE } from '../lib/fundMath';
import { isFinancialOrHolding, isPhysicalGrowthApplicable } from '../lib/assetScope';
import { fundamentalSignal } from '../signals/fundamentalSignals';
import { FtsCard } from '../components/FtsCard';
import { cardAuditEvidence } from '../lib/auditEvidence';
import { rejectReasons, rejectLineText } from '../lib/rejectReasons';
import { FtsDrillDown, type DrillDownKey } from '../components/FtsDrillDown';
import { DataGapBanner } from '../components/DataGapBanner';

import { QuarterlyTrend } from '../components/QuarterlyTrend';
import { FtsScreenTable } from '../ui/FtsScreenTable';
import { FtsSettingsTrigger } from '../ui/FtsSettingsDrawer';

const DIR_TONE = { bullish: 'green', bearish: 'red', neutral: 'gray' } as const;
const DIR_LABEL = { bullish: 'بنیاد روبه‌رشد', bearish: 'بنیاد روبه‌افت', neutral: 'بنیاد معادل' } as const;

/** گروه صنعتی نامرتبط برای مقایسه (هلدینگ‌ها با آن سنجیده نمی‌شوند) */
const OTHER_GROUP = 'سایر';


export default function FundamentalPage() {
  const params = useParams();
  const stored = useSymbolStore((s) => s.symbol);
  const setSymbol = useSymbolStore((s) => s.setSymbol);
  const symbol = params.symbol ?? stored;
  const [drawerOpen, setDrawerOpen] = useState(false);
  /** شاخص فعال در Drill-Down — null یعنی پنل بسته */
  const [drillKey, setDrillKey] = useState<DrillDownKey | null>(null);

  const screen = useFtsScreen();
  /** تقویم مجمعِ کل بازار در یک درخواست — برای برچسبِ ردیف‌ها */
  const upcoming = useCalendarUpcoming();
  const assemblyMap = useMemo(() => groupBySymbol(upcoming.data?.items), [upcoming.data]);

  /** بروزرسانی دیتابیس کدال از snapshot گیت‌هاب: POST + polling وضعیت تا پایان */
  type DbStatus = { running: boolean; stage: string; percent?: number; detail?: string; error?: string };
  const [dbUpd, setDbUpd] = useState<DbStatus | null>(null);
  const { refetch: refetchScreen } = screen;
  const handleDbUpdate = async () => {
    setDbUpd({ running: true, stage: 'starting' });
    try {
      await http('/api/sync/codal/db-download', { method: 'POST' });
    } catch { /* وضعیت واقعی از polling می‌آید */ }
  };
  useEffect(() => {
    if (!dbUpd?.running) return;
    const id = setInterval(async () => {
      try {
        const r = await http<{ db: DbStatus }>('/api/sync/codal/db-status');
        setDbUpd(r.db);
        if (!r.db.running && r.db.stage === 'done') void refetchScreen();
      } catch { /* سرور مشغول است — تیک بعدی */ }
    }, 2000);
    return () => clearInterval(id);
  }, [dbUpd?.running, refetchScreen]);
  // اگر دانلود از قبل در جریان است (مثلاً کاربر وسط آن صفحه را عوض کرده)،
  // وضعیت را یک‌بار بخوان تا دکمه و polling از همان ابتدا زنده باشند.
  useEffect(() => {
    let alive = true;
    http<{ db: DbStatus }>('/api/sync/codal/db-status')
      .then((r) => { if (alive && r.db.running) setDbUpd(r.db); })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  const card = useFtsCard(symbol);
  const quarters = useQuarters(symbol);
  const board = useSectorBoard();

  const qRows = useMemo(() => quarters.data?.quarters ?? [], [quarters.data]);
  const fiscal = useMemo(() => deCumulateQuarters(qRows), [qRows]);
  const yoy = useMemo(() => profitYoY(fiscal), [fiscal]);

  const history = useMemo(() => card.data?.history ?? [], [card.data]);
  const latestPeriod = qRows[0]?.period_end ?? history[0]?.period_end ?? null;
  const age = useMemo(() => statementAgeDays(latestPeriod), [latestPeriod]);
  const hasStatements = (card.data?.fs_count ?? 0) > 0 || qRows.length > 0 || history.length > 0;

  const boardRows = useMemo(() => board.data ?? [], [board.data]);
  const peRow = useMemo(() => boardRows.find((r) => r.symbol === symbol), [boardRows, symbol]);
  const companyName = useMemo(
    () => screen.data?.data.find((r) => r.symbol === symbol)?.name ?? null,
    [screen.data, symbol],
  );
  const rawSector = card.data?.sector ?? peRow?.sector_name ?? '';
  /** هلدینگ‌ها با گروه «سایر» مقایسه صنعتی نمی‌شوند — گروه نامربوط است */
  const isHolding = useMemo(
    () => isFinancialOrHolding({ name: companyName, sector_name: rawSector }),
    [companyName, rawSector],
  );
  /** پنلِ P/NAV باید همان‌جا بیاید که موتورِ FTS شاخص ۴ را معاف کرده، نه همان‌جا
   *  که یک طبقه‌بندِ نام/گروه در UI چنین حدس می‌زند (رأیِ مالک ۱۴۰۵-۰۷-۰۳).
   *  صندوق‌ها خارج‌اند: برای آن‌ها «FTS ندارد» نشان داده می‌شود، نه P/NAV. */
  const axis4Exempt =
    card.data?.applicable !== false &&
    (card.data?.indicators?.['4']?.exempt === true || card.data?.indicators?.['4']?.na === true);
  const sector = isHolding && rawSector.trim() === OTHER_GROUP ? '' : rawSector;
  const median = useMemo(() => (sector ? sectorMedianPE(boardRows, sector) : null), [boardRows, sector]);
  const pe = isHolding ? null : peRow?.pe ?? null;
  /** رشد فیزیکی صرفاً برای تولیدی — profile بک‌اند یا طبقه‌بندی نام/گروه */
  const physicalApplicable = useMemo(() => {
    /** مالی/بانکی/هلدینگ/سرمایه‌گذاری: رشد فیزیکی هرگز فعال نمی‌شود (مخفی کامل) */
    if (isFinancialOrHolding({ name: companyName, sector_name: rawSector })) return false;
    const prof = card.data?.profile;
    if (prof?.volume_applicable != null) return prof.volume_applicable;
    return isPhysicalGrowthApplicable({ name: companyName, sector_name: rawSector });
  }, [card.data, companyName, rawSector]);

  /** شاهد ممیزی هر محور — برای کارت «چرا این وضعیت؟» در سلول‌های FtsCard */
  const audit = useMemo(() => (card.data ? cardAuditEvidence(card.data) : null), [card.data]);

  const signal = useMemo(
    () =>
      symbol
        ? fundamentalSignal({
            symbol,
            ftsScore: card.data?.score ?? null,
            passes: card.data?.passes ?? {},
            epsSeries: card.data?.metrics?.eps_series ?? [],
            pe,
            sectorMedianPE: median,
            profitYoY: yoy,
            statementAgeDays: age,
            hasStatements,
            epsPartial: card.data?.metrics?.eps_partial ?? false,
            applicable: card.data?.applicable !== false,
          })
        : null,
    [symbol, card.data, pe, median, yoy, age, hasStatements],
  );

  useEffect(() => {
    if (signal) publishSignal(signal);
  }, [signal]);

  if (!symbol) {
    // دیده‌بان کلان: ماتریس ۵ شاخص FTS روی کل بازار + کشوی تنظیمات
    // min-w-0: زنجیرهٔ flex تا جدول ادامه دارد؛ بدون این، min-w-[1240px]ِ
    // جدول کلِ صفحه را در دیدگاه‌های کوچک از کادر بیرون می‌زند.
    return (
      <div className="flex flex-col gap-2 min-w-0">
        {screen.isLoading ? (
          /* پیش از این در حینِ بارگذاری، rows=[] بود و جدول پیامِ
           * «ردیفی از غربالگری FTS نیامد» نشان می‌داد — اولین اسکنِ بازار
           * ده‌ها ثانیه طول می‌کشد، پس کاربر پیامِ خطا را واقعی می‌خواند. */
          <EmptyState title="در حال بارگذاری غربالگری FTS…" hint="اولین اسکنِ کل بازار ممکن است تا یک دقیقه طول بکشد؛ جدول همین‌جا ظاهر می‌شود" />
        ) : screen.isError ? (
          <EmptyState title="غربالگری FTS در دسترس نیست" hint="سرور غربالگری پاسخ نداد — کمی بعد دوباره امتحان کنید" />
        ) : (
          <FtsScreenTable
            rows={screen.data?.data ?? []}
            thresholds={screen.data?.thresholds ?? null}
            onDbUpdate={handleDbUpdate}
            dbUpdate={dbUpd}
            assemblyEvents={assemblyMap}
            settingsSlot={<FtsSettingsTrigger open={drawerOpen} onToggle={() => setDrawerOpen((v) => !v)} />}
            onSelect={(s) => {
              setSymbol(s);
              setDrawerOpen(false);
            }}
          />
        )}
      </div>
    );
  }

  if (card.isLoading) {
    return <EmptyState title={`در حال دریافت کارت ${symbol}...`} />;
  }

  if (card.isError || !card.data) {
    /** Circuit Breaker: علت واقعیِ نبودِ داده را صادقانه بگو، نه رندر خالی بی‌پیام */
    const status = card.error instanceof HttpError ? card.error.status : null;
    const hint =
      status === 0
        ? 'اتصال برقرار نشد یا پاسخ خوانده نشد — دوباره امتحان کنید'
        : status === 404
          ? `نماد ${symbol} در کدال صورت مالی ندارد`
          : 'سرور بنیادی پاسخ نداد یا خطای شبکه رخ داد';
    return (
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-base font-black text-text-primary">{symbol}</h2>
          <FtsSettingsTrigger open={drawerOpen} onToggle={() => setDrawerOpen((v) => !v)} />
        </div>
        <EmptyState title={`دادهٔ کارت بنیادی ${symbol} نیامد`} hint={hint} />
      </div>
    );
  }

  const metrics = card.data.metrics;
  const passes = card.data.passes ?? {};
  // #205: علتِ رد را همان پرچم‌های موتور می‌گوید، با عدد و آستانۀ خودشان
  const rejectLines = rejectReasons(passes, card.data.indicators ?? null);
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-base font-black text-text-primary">{symbol}</h2>
        {sector ? <span className="text-xs text-text-secondary">{sector}</span> : null}
        {isHolding ? <Badge tone="blue">هلدینگ / سرمایه‌گذاری</Badge> : null}
        {signal ? (
          <>
            <Badge tone={DIR_TONE[signal.direction]}>{DIR_LABEL[signal.direction]}</Badge>
            {signal.score != null ? <Badge tone="blue">امتیاز {toFaDigits(signal.score)}</Badge> : null}
            {signal.payload.staleness ? <Badge tone="yellow">داده کهنه</Badge> : null}
            {signal.payload.dataQuality === 'incomplete' ? <Badge tone="red">داده ناقص</Badge> : null}
          </>
        ) : null}
        <span className="ms-auto flex items-center gap-2">
          <FtsSettingsTrigger open={drawerOpen} onToggle={() => setDrawerOpen((v) => !v)} />
        </span>
      </div>

      {/* تصمیم استراتژیک FTS یا ارزیابی هلدینگ در بالا به‌صورت بنر عریض، خوانا و مدرن */}
      {/* صندوق «FTS ندارد» می‌گیرد نه پنلِ P/NAV (رأی ۱۵)؛ پنلِ هلدینگ فقط برای
          معافِ شاخص ۴ است که ارزیابیِ عملیاتی دارد. */}
      {card.data?.applicable !== false && (isHolding || axis4Exempt) ? (
        <div className="glass-panel panel-in p-4" data-testid="holding-pnav-panel">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-black text-text-primary">ارزش‌گذاری هلدینگ</h3>
            <Badge tone="yellow">N/A</Badge>
          </div>
          <p className="text-2xs leading-relaxed text-text-secondary" data-testid="holding-nav-na">
            این نماد سرمایه‌گذاری/هلدینگ است و در کدال ارزش خالص دارایی (NAV) منتشر نشده؛
            بنابراین P/NAV محاسبه نمی‌شود و جای آن عددی گذاشته نمی‌شود.
          </p>
          <div className="mt-2.5 pt-2.5 border-t border-border-c/50 text-2xs text-text-muted">
            هلدینگ‌ها از شرط «نسبت فروش به ارزش بازار» (شاخص ۴) معاف‌اند.
          </div>
        </div>
      ) : (
        <div className="glass-panel panel-in p-3.5 sm:p-4" data-testid="fts-strategy-summary">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-start sm:items-center gap-3">
              <span className="text-2xl shrink-0 p-1.5 rounded-xl bg-bg-card border border-border-c/60 shadow-xs">
                {card.data.applicable === false ? '➖' : card.data.score == null ? '❓' : card.data.score >= 4 ? '🎯' : card.data.score === 3 ? '⏳' : '🚫'}
              </span>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-xs sm:text-sm font-black text-text-primary">تصمیم استراتژیک FTS:</h3>
                  <span className={`text-xs sm:text-sm font-black ${
                    card.data.applicable === false || card.data.score == null
                      ? 'text-text-muted'
                      : card.data.score >= 4
                      ? 'text-accent-green'
                      : card.data.score === 3
                      ? 'text-amber-400'
                      : 'text-accent-red'
                  }`}>
                    {card.data.applicable === false
                      ? 'FTS ندارد'
                      : card.data.score == null
                      ? 'اطلاعات کافی نیست'
                      : card.data.score >= 4
                      ? 'گزینه عالی برای سبد سرمایه‌گذاری'
                      : card.data.score === 3
                      ? 'مناسب برای زیر نظر گرفتن (واچ‌لیست)'
                      : 'رد شده در بررسی بنیادی'}
                  </span>
                </div>
                <p className="text-2xs text-text-secondary leading-relaxed mt-1">
                  {card.data.applicable === false
                    ? 'ارزیابی پنج‌شاخصهٔ FTS برای شرکت‌های عملیاتی نوشته شده؛ این یک صندوق است، پس داوری برایش صادر نمی‌شود (نه تأیید، نه رد).'
                    : card.data.score == null
                    ? 'چون اطلاعات همه ۵ شاخص کامل نیست، فعلا نمی‌توان تصمیم قطعی در مورد این سهم گرفت.'
                    : card.data.score >= 4
                    ? 'این سهم از فیلترهای مهم سودسازی، رشد فروش و عدم قیمت‌گذاری دستوری عبور کرده و یک گزینه بسیار مستعد است.'
                    : card.data.score === 3
                    ? 'این سهم پتانسیل خوبی دارد اما در یک یا دو شاخص ضعیف عمل کرده. بهتر است گزارش‌های ماهانه بعدی آن را رصد کنیم.'
                    : ''}
                </p>
                {/* #205: در حالتِ رد، علت را موتور می‌نویسد — همان شاخص(ها)ی
                    مردود با عدد و آستانۀ خودش، نه «ضعف در سودسازی یا حاشیۀ
                    پایین یا قیمت‌گذاری دستوری»ی حدسی. */}
                {card.data.applicable !== false && card.data.score != null && card.data.score < 3 ? (
                  <div className="mt-1 text-2xs leading-relaxed" data-testid="fts-reject-reasons">
                    <span className="font-black text-text-primary">علتِ دقیقِ رد: </span>
                    {rejectLines.length === 0 ? (
                      <span className="text-text-secondary">
                        هیچ‌یک از پنج شاخص پرچمِ رد ندارد؛ حکم از وتوی استراتژی یا
                        امتیازِ ترکیبی است — به خطِ «حذف از غربالگری» همین بنر نگاه کنید.
                      </span>
                    ) : (
                      <ul className="mt-1 list-disc space-y-0.5 ps-4">
                        {rejectLines.map((l, i) => (
                          <li key={i} className={l.missing ? 'text-text-muted' : 'text-accent-red'}>
                            {rejectLineText(l)}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ) : null}
              </div>
            </div>

            <div className="shrink-0 flex items-center gap-2 self-start sm:self-center">
              <Badge tone={card.data.applicable === false ? 'gray' : card.data.score == null ? 'gray' : card.data.score >= 4 ? 'green' : card.data.score === 3 ? 'yellow' : 'red'}>
                {card.data.applicable === false
                  ? 'FTS ندارد'
                  : card.data.score == null
                  ? 'بدون داده'
                  : card.data.score >= 4
                  ? 'واجد شرایط سبد FTS'
                  : card.data.score === 3
                  ? 'واچ‌لیست رصد FTS'
                  : 'فاقد شرایط FTS'}
              </Badge>
            </div>
          </div>

          {/* علتِ حذف از غربالگری داخلِ همان جعبهٔ تصمیم — پنلِ جدا ندارد،
              ولی امتیازِ ۴ و ۵ بدونِ ذکرِ وتو «گزینه عالی» خوانده می‌شد */}
          {card.data.excluded ? (
            <div className="mt-3 rounded-xl border border-accent-red/40 bg-accent-red/10 p-3 text-2xs leading-relaxed text-text-primary"
                 data-testid="fts-exclusion-line">
              <span className="font-black">حذف از غربالگری: </span>
              {(card.data.exclusion_reasons ?? []).join(' · ') || 'وتوی استراتژی FTS'}
              {metrics?.mcap_stale ? ' · ارزش بازار کهنه' : ''}
            </div>
          ) : null}

          <div className="mt-3 pt-3 border-t border-border-c/60 text-2xs text-text-muted">
            <span className="font-mono text-text-secondary">
              {age != null ? `سن صورت مالی: ${toFaDigits(age)} روز` : 'صورت مالی معتبر'}
            </span>
          </div>
        </div>
      )}

      {/* ۵ کارت بنیادی FTS — اکنون تمام‌عرض و گشوده به سمت چپ با چیدمان واکنش‌گرا */}
      <FtsCard
        score={card.data.score ?? null}
        passes={passes}
        verdict={card.data.verdict ?? null}
        industryMode={card.data.pricing_mode ?? null}
        indicators={card.data.indicators ?? null}
        thresholds={card.data.thresholds ?? null}
        audit={audit}
        physicalApplicable={physicalApplicable}
        activeDrill={drillKey}
        onDrill={(k) => setDrillKey((cur) => (cur === k ? null : k))}
        quarters={fiscal}
      />

      <FtsDrillDown card={card.data} active={drillKey} quarters={fiscal} physicalApplicable={physicalApplicable} />


      <DataGapBanner gaps={card.data.data_gaps ?? []} eps={card.data.indicators?.['2']} />


      <QuarterlyTrend quarters={fiscal} />
    </div>
  );
}
