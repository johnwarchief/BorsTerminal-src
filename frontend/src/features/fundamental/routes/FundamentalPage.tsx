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
import { deCumulateQuarters, profitYoY, sectorMedianPE } from '../lib/fundMath';
import { isFinancialOrHolding, isPhysicalGrowthApplicable } from '../lib/assetScope';
import { fundamentalSignal } from '../signals/fundamentalSignals';
import { FtsCard } from '../components/FtsCard';
import { cardAuditEvidence } from '../lib/auditEvidence';
import { FtsDrillDown, type DrillDownKey } from '../components/FtsDrillDown';
import { DataGapBanner } from '../components/DataGapBanner';

import { QuarterlyTrend } from '../components/QuarterlyTrend';
import { RiskGatesPanel } from '../components/RiskGatesPanel';
import { FtsScreenTable } from '../ui/FtsScreenTable';
import { FtsSettingsTrigger } from '../ui/FtsSettingsDrawer';

const DIR_TONE = { bullish: 'green', bearish: 'red', neutral: 'gray' } as const;
const DIR_LABEL = { bullish: 'صعودی', bearish: 'نزولی', neutral: 'خنثی' } as const;

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
  /** دکمهٔ بروزرسانی بالای جدول: تازه‌سازیِ ۵ شاخص از کدال + بازخوانیِ غربالگر */
  const [refreshing, setRefreshing] = useState(false);
  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await http('/api/sync/codal/fts-refresh?mode=monthly', { method: 'POST' });
    } catch { /* سرور ممکن است فوراً پاسخ ندهد؛ بازخوانی را ادامه می‌دهیم */ }
    try { await screen.refetch(); } finally { setRefreshing(false); }
  };

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
      <div className="flex flex-col gap-4 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-base font-black text-text-primary">دیده‌بان کلان بنیادی بازار</h2>
          <span className="text-xs text-text-secondary">ماتریس ۵ شاخص جزوهٔ FTS</span>
          <FtsSettingsTrigger open={drawerOpen} onToggle={() => setDrawerOpen((v) => !v)} />
        </div>
        {screen.isError ? (
          <EmptyState title="غربالگری FTS در دسترس نیست" hint="سرور اسکرینر پاسخ نداد — بعداً تلاش کن" />
        ) : (
          <FtsScreenTable
            rows={screen.data?.data ?? []}
            thresholds={screen.data?.thresholds ?? null}
            onRefresh={handleRefresh}
            refreshing={refreshing}
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
        ? 'پاسخ بک‌اند با قرارداد دادهٔ فرانت ناسازگار است — قرارداد را بررسی کن'
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
        <span className="mr-auto flex items-center gap-2">
          <span className="text-2xs text-text-muted">{signal?.rationale ?? ''}</span>
          <FtsSettingsTrigger open={drawerOpen} onToggle={() => setDrawerOpen((v) => !v)} />
        </span>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <FtsCard
          score={card.data.score ?? null}
          passes={passes}
          verdict={card.data.verdict ?? null}
          industryMode={card.data.pricing_mode ?? null}
          audit={audit}
          physicalApplicable={physicalApplicable}
          activeDrill={drillKey}
          onDrill={(k) => setDrillKey((cur) => (cur === k ? null : k))}
        />
        {isHolding ? (
          <div className="glass-panel panel-in p-4" data-testid="holding-pnav-panel">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-black text-text-primary">ارزش‌گذاری هلدینگ — نیازمند ارزیابی پرتفوی هلدینگ (N/A)</h3>
              <Badge tone="yellow">N/A</Badge>
            </div>
            <p className="text-2xs leading-relaxed text-text-secondary" data-testid="holding-nav-na">
              نیازمند ارزیابی پرتفوی هلدینگ (N/A) — این شرکت سرمایه‌گذاری/هلدینگ است و مقایسهٔ P/E با گروه‌های تولیدی
              نامعناست. تا انتشار دادهٔ NAV (ارزش خالص دارایی‌های پرتفوی) از بک‌اند، هیچ نسبتِ جایگزینی مثل
              «EPS به‌عنوان جانشین NAV» محاسبه یا نمایش داده نمی‌شود — عدد ساختگی ممنوع.
            </p>
            <div className="mt-3 pt-3 border-t border-border-c text-2xs text-text-muted">
              بر اساس استراتژی FTS: هلدینگ‌ها از شرط نسبت فروش به ارزش بازار معاف هستند و با P/NAV سنجیده می‌شوند.
            </div>
          </div>
        ) : (
          <div className="glass-panel panel-in p-4 flex flex-col justify-between" data-testid="fts-strategy-summary">
            <div>
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-black text-text-primary">تصمیم استراتژیک FTS</h3>
                </div>
                <Badge tone={card.data.score == null ? 'gray' : card.data.score >= 4 ? 'green' : card.data.score === 3 ? 'yellow' : 'red'}>
                  {card.data.score == null ? 'بدون داده' : card.data.score >= 4 ? 'واجد شرایط سبد FTS' : card.data.score === 3 ? 'واچ‌لیست رصد FTS' : 'فاقد شرایط FTS'}
                </Badge>
              </div>

              <div className="space-y-2.5">
                <div className={`rounded-xl border p-3 ${
                  card.data.score == null
                    ? 'border-border-c/70 bg-bg-card/50 text-text-primary'
                    : card.data.score >= 4
                    ? 'border-accent-green/40 bg-accent-green/10 text-text-primary'
                    : card.data.score === 3
                    ? 'border-accent-yellow/40 bg-accent-yellow/10 text-text-primary'
                    : 'border-accent-red/40 bg-accent-red/10 text-text-primary'
                }`}>
                  <div className="flex items-center gap-2 font-bold text-xs mb-1">
                    <span>{card.data.score == null ? '❓' : card.data.score >= 4 ? '🎯' : card.data.score === 3 ? '⏳' : '🚫'}</span>
                    <span>
                      {card.data.score == null
                        ? 'اطلاعات کافی نیست'
                        : card.data.score >= 4
                        ? 'گزینه عالی برای سبد سرمایه‌گذاری'
                        : card.data.score === 3
                        ? 'مناسب برای زیر نظر گرفتن'
                        : 'رد شده در بررسی بنیادی'}
                    </span>
                  </div>
                  <p className="text-2xs text-text-secondary leading-relaxed mt-1">
                    {card.data.score == null
                      ? 'چون اطلاعات همه ۵ شاخص کامل نیست، فعلا نمی‌توان تصمیم قطعی در مورد این سهم گرفت.'
                      : card.data.score >= 4
                      ? 'این سهم از فیلترهای مهم سودسازی، رشد فروش و عدم قیمت‌گذاری دستوری عبور کرده و یک گزینه بسیار مستعد است.'
                      : card.data.score === 3
                      ? 'این سهم پتانسیل خوبی دارد اما در یک یا دو شاخص ضعیف عمل کرده. بهتر است گزارش‌های ماهانه بعدی آن را رصد کنیم.'
                      : 'به دلیل ضعف در سودسازی، حاشیه سود پایین یا قیمت‌گذاری دستوری، این سهم برای سرمایه‌گذاری تایید نمی‌شود.'}
                  </p>
                </div>

                <div className="rounded-xl border border-border-c/70 bg-bg-card/50 p-3">
                  <div className="text-xs font-bold text-text-primary mb-1 flex items-center gap-1.5">
                    <span className="text-accent-blue">⚡</span>
                    <span>گام بعدی چیست؟</span>
                  </div>
                  <p className="text-2xs text-text-secondary leading-relaxed">
                    {card.data.score != null && card.data.score >= 4
                      ? 'بنیاد سهم عالی است. حالا در تب بازار بررسی کنید که آیا خریداران قدرت کافی دارند؟ سپس در تب تکنیکال منتظر یک نقطه ورود مناسب (مثل پولبک) بمانید.'
                      : 'با این شرایط بنیادی، نگهداری این سهم پیشنهاد نمی‌شود. اگر هم قصد خرید دارید فقط با دید نوسان‌گیری کوتاه و با رعایت سفت و سخت حد ضرر عمل کنید.'}
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-3 pt-3 border-t border-border-c/60 flex items-center justify-between text-2xs text-text-muted">
              <span>منطق غربالگری: کاهش ۸۰۰ نماد به ۱۰ واچ‌لیست و ۵ سبد</span>
              <span className="font-mono text-text-secondary">{age != null ? `سن صورت مالی: ${toFaDigits(age)} روز` : 'صورت مالی معتبر'}</span>
            </div>
          </div>
        )}
      </div>

      <FtsDrillDown card={card.data} active={drillKey} quarters={fiscal} physicalApplicable={physicalApplicable} />

      <RiskGatesPanel
        excluded={card.data.excluded ?? false}
        reasons={card.data.exclusion_reasons ?? []}
        pricingMode={card.data.pricing_mode ?? null}
        mcapStale={metrics?.mcap_stale ?? false}
      />

      <DataGapBanner gaps={card.data.data_gaps ?? []} eps={card.data.indicators?.['2']} />


      <QuarterlyTrend quarters={fiscal} />
    </div>
  );
}
