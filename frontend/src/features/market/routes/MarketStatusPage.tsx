// features/market/routes/MarketStatusPage.tsx -- صفحۀ مستقل «وضعیت بازار»
//
// چرا صفحه و نه کارتِ توی تابلو: مالک رأی داد که وضعیتِ بازار باید از ناوبری
// باز شود. نوارِ «وضعیت بازار» بالایِ تابلو می‌ماند (پاسِ سریعِ همان نشست)، و
// اینجا همان داده در نقشِ پخش‌شده می‌نشیند.
//
// معماریِ مرحلۀ ۱: هشت بخش با سرِصفحۀ شماره‌دار (ناوبریِ چسبان با
// IntersectionObserver). صفحۀ ۴ (گزارش‌های بنیادی) به دستورِ صریحِ مالک از دامنه
// بیرون است — درِ ماتریسِ تحویل ثبت شده، نه اینکه بی‌سروصدا حذف شده باشد.
// هیچ بلوکی عددِ ساختگی نمی‌سازد: هر کدام loading / error / بی‌داده دارد، و
// «منبع نرسیده» علتش را از خودِ پاسخ می‌خواند.
//
// چرا بخش‌ها در این فایل props می‌گیرند و خودشان کوئری نمی‌زنند: همان قاعدۀ
// #161ِ تب تکنیکال — کامپوننتِ نمایشی داده را از بالا می‌گیرد تا درِ تست،
// چشمی و با دادهٔ ثابت قابلِ رندر باشد. بخش‌هایِ بزرگ (طلا، مقایسه، چارت،
// نمایِ کلی) خودگردان‌اند چون حالتِ داخلیِ زیادی دارند.
import { useMemo } from 'react';
import { serverStamp } from '@shared/lib/time';
import { MarketStatusPanel } from '../components/MarketStatusPanel';
import { MarketStatusTicker } from '../components/MarketStatusTicker';
import { MarketPulseBar } from '../components/MarketPulseBar';
import { TimelineCharts } from '../components/MicroChartsDrawer';
import {
  BreadthHistogram,
  ClientSplitPanel,
  SessionPhasesPanel,
} from '../components/MarketStatusPanels';
import { IndustriesTable, MainWatchTable } from '../components/MarketStatusTables';
import { IndexCards } from '../components/IndexCards';
import { MarketChartSection } from '../components/MarketChartSection';
import { MarketCompareSection } from '../components/MarketCompareSection';
import { MarketGlanceCards } from '../components/MarketGlanceCards';
import { MarketTreemap } from '../components/MarketTreemap';
import { TopListsGrid } from '../components/RankedPanels';
import { OrdersPanel, OwnershipPanel } from '../components/OrderOwnershipSection';
import { GoldMarketSection } from '../components/GoldMarketSection';
import { MarketSectionNav, SectionHeading, type MarketSection } from '../components/MarketSectionNav';
import { useIndustries } from '../api/useIndustries';
import { useMarketPulse } from '../api/useMarketPulse';
import {
  useMstatClientSplit,
  useMstatHistogram,
  useMstatPhases,
} from '../api/useMarketStatusFeed';
import { useMstatIndexCards, useMstatOrderFlows, useMstatOwnership, useMstatTops } from '../api/useMarketPanels';
import type { WidgetFreshInput } from '../components/WidgetFreshness';

const fresh = (
  label: string,
  q: { status: string; dataUpdatedAt: number },
  computedAt?: string | null,
): WidgetFreshInput & { label: string } => ({
  label,
  status: q.status,
  dataUpdatedAt: q.dataUpdatedAt,
  sourceAsOf: serverStamp(computedAt),
});

const SECTIONS: MarketSection[] = [
  { id: 'ms-sec-overview', label: 'نمای کلی', pages: [6, 7] },
  { id: 'ms-sec-treemap', label: 'نقشۀ بازار', pages: [2] },
  { id: 'ms-sec-tops', label: 'برترین‌ها و تأثیرگذاران', pages: [8] },
  { id: 'ms-sec-orders', label: 'سفارش‌ها و مالکیت', pages: [9] },
  { id: 'ms-sec-gold', label: 'طلا، سکه و صندوق طلا', pages: [1, 3, 10, 11, 12] },
  { id: 'ms-sec-compare', label: 'نمودار مقایسه‌ای', pages: [13] },
  { id: 'ms-sec-chart', label: 'نمودار پیشرفته', pages: [5] },
  { id: 'ms-sec-tables', label: 'جدول‌های تابلو', pages: [2, 8] },
];

export default function MarketStatusPage() {
  const { data: pulse, isLoading: pulseLoading } = useMarketPulse();
  const histo = useMstatHistogram();
  const split = useMstatClientSplit();
  const phases = useMstatPhases();
  const cards = useMstatIndexCards();
  const tops = useMstatTops();
  const flows = useMstatOrderFlows();
  const owner = useMstatOwnership();
  const industries = useIndustries();

  // گزینه‌های کرکرۀ صنعت از خودِ پاسخِ `/api/mstat/industries` — فهرستِ دستی
  // درِ رابط یعنی صنعتی که حذف/تغییر نام می‌کند بی‌خبر غیب شود.
  const industryOptions = useMemo(
    () => (industries.data?.rows ?? []).map((r) => r.industry).filter(Boolean).sort(),
    [industries.data],
  );

  return (
    <div className="flex w-full max-w-none flex-col gap-2" data-testid="market-status-page">
      <MarketStatusPanel />
      <MarketStatusTicker pulse={pulse} split={split.data} />
      <MarketPulseBar pulse={pulse ?? null} isLoading={pulseLoading} />

      <MarketSectionNav sections={SECTIONS} />

      <section className="flex min-w-0 flex-col gap-2">
        <SectionHeading
          id="ms-sec-overview"
          title="نمای کلیِ بازار"
          pages={[6, 7]}
          freshness={[
            // `null` برایِ چهارِ پنلِ بی‌`computed_at` — سنجشِ زندهٔ ۱۴۰۵-۰۷-۲۴ رویِ
            // `/api/mstat/{histogram,clientsplit,industries,phases}`: اینِ پاسخ‌ها
            // ساعتِ ساختِ خودشان را ندارند. برچسب همان را صریح می‌گوید وِ ساعتِ
            // پنلِ همسایه را بهِ آن‌ها نسبت نمی‌دهد (قاعدۀ «بی‌داده ≠ صفر»).
            fresh('کارت‌های شاخص', cards, cards.data?.computed_at),
            fresh('توزیعِ درصد', histo, null),
            fresh('تفکیکِ مشتری', split, null),
            fresh('فازهای نشست', phases, null),
          ]}
          desc="کارت‌های شاخص، توزیعِ درصد، تفکیکِ مشتری و فازهایِ همین نشست — همۀ اعداد از یک اسکنِ market.db"
        />
        <MarketGlanceCards />
        <IndexCards
          data={cards.data}
          isLoading={cards.isLoading}
          isError={cards.isError}
          onRetry={() => void cards.refetch()}
        />
        <div className="grid grid-cols-1 gap-2 xl:grid-cols-3">
          <BreadthHistogram
            data={histo.data}
            isLoading={histo.isLoading}
            isError={histo.isError}
            onRetry={() => void histo.refetch()}
          />
          <ClientSplitPanel
            data={split.data}
            isLoading={split.isLoading}
            isError={split.isError}
            onRetry={() => void split.refetch()}
          />
          <SessionPhasesPanel
            data={phases.data}
            isLoading={phases.isLoading}
            isError={phases.isError}
            onRetry={() => void phases.refetch()}
          />
        </div>
        <div className="glass-panel flex min-w-0 flex-col gap-2 rounded-xl border border-border-c p-2.5">
          <h3 className="text-2xs font-black text-text-primary">نمودارهای درون‌روزِ همین نشست</h3>
          <TimelineCharts />
        </div>
      </section>

      <section className="flex min-w-0 flex-col gap-2">
        <SectionHeading
          id="ms-sec-treemap"
          title="نقشۀ بازار"
          pages={[2]}
          desc="سطح هر بلوک = sizeِ همان معیار؛ رنگ = مثبت/منفی/صفر/بی‌داده. کلیک، نماد را درِ چارتِ پایین باز می‌کند."
        />
        <MarketTreemap industries={industryOptions} />
      </section>

      <section className="flex min-w-0 flex-col gap-2">
        <SectionHeading
          id="ms-sec-tops"
          title="برترین‌ها و تأثیرگذاران"
          pages={[8]}
          freshness={[fresh('برترین‌ها', tops, tops.data?.computed_at)]}
          desc="چهار پنلِ جدا: اثرِ مثبت و منفی بر شاخص، بیشترین ارزش و بیشترین حجم — «اثر بر شاخص» با «٪ رشد قیمت» یکی نیست"
        />
        <TopListsGrid
          panels={tops.data?.panels}
          isLoading={tops.isLoading}
          isError={tops.isError}
          onRetry={() => void tops.refetch()}
          reconciliation={tops.data?.reconciliation}
          blockers={tops.data?.blockers}
        />
      </section>

      <section className="flex min-w-0 flex-col gap-2">
        <SectionHeading
          id="ms-sec-orders"
          title="سفارش‌ها و تغییرِ مالکیت"
          pages={[9]}
          freshness={[fresh('ماندۀ سفارش', flows, flows.data?.computed_at), fresh('جابه‌جاییِ سهم', owner, owner.data?.computed_at)]}
          desc="ماندۀ دفترِ سفارش از حجمِ انجام‌شده، و جابه‌جاییِ سهم از خالصِ ورودِ پول جدا نگه داشته شده"
        />
        <div className="grid grid-cols-1 gap-2 2xl:grid-cols-2">
          <OrdersPanel
            data={flows.data}
            isLoading={flows.isLoading}
            isError={flows.isError}
            onRetry={() => void flows.refetch()}
          />
          <OwnershipPanel
            data={owner.data}
            isLoading={owner.isLoading}
            isError={owner.isError}
            onRetry={() => void owner.refetch()}
          />
        </div>
      </section>

      <section className="flex min-w-0 flex-col gap-2">
        <SectionHeading
          id="ms-sec-gold"
          title="طلا، سکه و صندوق‌های طلا"
          pages={[1, 3, 10, 11, 12]}
          desc="سه جدولِ جدا برایِ سه ماهیتِ متفاوت (صندوق / کاغذی / سایر)، نقشۀ صندوق‌های طلا و روندِ تجمعیِ سبدِ طلا"
        />
        <GoldMarketSection />
      </section>

      <section className="flex min-w-0 flex-col gap-2">
        <SectionHeading
          id="ms-sec-compare"
          title="نمودارِ مقایسه‌ای"
          pages={[13]}
          desc="چند نماد روی یک محور، نرمال‌شده به پایۀ ۱۰۰ فقط رویِ زمان‌هایِ مشترک — قیمتِ خامِ با واحدهای نامرتبط روی یک مقیاس نمی‌آید"
        />
        <MarketCompareSection />
      </section>

      <section className="flex min-w-0 flex-col gap-2">
        <SectionHeading
          id="ms-sec-chart"
          title="نمودارِ پیشرفته"
          pages={[5]}
          desc="همان موتورِ چارتِ برنامه (klinecharts/nahayatnegar) با تایم‌فریم، مبنایِ تعدیل و ابزارهای واقعی"
        />
        <MarketChartSection />
      </section>

      <section className="flex min-w-0 flex-col gap-2">
        <SectionHeading
          id="ms-sec-tables"
          title="جدول‌های تابلو"
          pages={[2, 8]}
          freshness={[fresh('صنایع', industries, null)]}
          desc="صنایع و نمادهای زیرِ نظر — همان دو جدولِ قبلی، بی‌کاهشِ ستون"
        />
        {/* دو جدول نه‌تایی‌ستون در ۱۳۶ پیکسل کنارِ هم فشرده می‌شوند؛ فقط روی
            نمایشگرِ عریض دو ستونه‌اند. */}
        <div className="grid grid-cols-1 gap-2 2xl:grid-cols-2">
          <IndustriesTable />
          <MainWatchTable />
        </div>
      </section>
    </div>
  );
}
