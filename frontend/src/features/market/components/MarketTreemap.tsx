// features/market/components/MarketTreemap.tsx -- نقشۀ بازار (صفحۀ ۲ و ۱۲)
//
// مرجع دو جا این را می‌خواهد: صفحۀ ۲ (کل تابلو با کرکره‌ها) و صفحۀ ۱۲ (فقط
// صندوق‌های طلا). یک کامپوننت با ورودیِ `fixedGroup` هر دو را می‌سازد، ولی هر
// دو مرجع درِ ماتریسِ تحویل جدا ردیابی می‌مانند — شباهت، اجازهٔ حذف نیست.
//
// سه تصمیمی که «عدد ساختگی» را غیرممکن می‌کند:
// ۱) سطحِ هر مستطیل از `size` خودِ ردیف می‌آید و `size` از معیارِ انتخابی درِ
//    سرور مشتق شده. پس «انتخابِ معیار ⇒ سطح‌هایِ متفاوت» واقعی است، نه انیمیشن.
// ۲) رنگ از `tone` سرور است (مثبت/منفی/خنثی/بی‌داده) — همان کلیدِ سراسریِ
//    `lib/tones`، پس نقشه و پنل‌هایِ رتبه‌ای یک نماد را یکی سبز و دیگری قرمز
//    نمی‌کنند.
// ۳) بی‌معامله‌ها درِ چیدمان نمی‌نشینند و شمارشان نوشته می‌شود (`skipped_nodata`).
//    خانهٔ صفر هیچ پیکسلی ندارد و کاربر آن را «حذف‌شدۀ مشکوک» می‌خواند.
//
// چیدمان درِ SVG با viewBoxِ ۰..۱ و مقیاسِ پیکسلی خودِ کادر است؛ اندازه از
// ResizeObserver می‌آید تا ۳۹۰ پیکسلِ موبایل همان داده را بی‌سرریزِ افقی
// دوباره بچیند (مرحلۀ ۵: «هیچ متنی بریده نشود و صفحه سرریز افقی نگیرد»).
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { toFaDigits, fmtInt, fmtPct } from '@shared/lib/fmt';
import { squarify, TREEMAP_LABEL_MIN_H, TREEMAP_LABEL_MIN_W } from '../lib/treemapLayout';
import { TONE_CLASS, TONE_LEGEND, toneOf } from '../lib/tones';
import { SourceNotice, StatusError, StatusLoading, StatusNoData, StatusSection } from './StatusShell';
import type { TreemapMetric, TreemapNode } from '../api/useMarketPanels';
import { useMstatTreemap } from '../api/useMarketPanels';
import { serverStamp } from '@shared/lib/time';
import { WidgetFreshness } from './WidgetFreshness';

const METRICS: { key: TreemapMetric; label: string }[] = [
  { key: 'value', label: 'ارزش معاملات' },
  { key: 'volume', label: 'حجم معاملات' },
  { key: 'cap', label: 'ارزش بازار' },
  { key: 'trades', label: 'تعداد معاملات' },
];

/** همان دامنه‌هایی که `mstat_engine.CATEGORY_ROWS` می‌شمارد — فهرستِ دستی نساخته‌ایم */
const GROUPS: { key: string; label: string }[] = [
  { key: 'all', label: 'کل بازار' },
  { key: 'eq_all', label: 'سهام، حق تقدم و ص.سهامی' },
  { key: 'stock_right', label: 'سهام و حق تقدم' },
  { key: 'eq_fund', label: 'صندوق‌های سهامی و مختلط' },
  { key: 'gold_fund', label: 'صندوق‌های طلا' },
  { key: 'silver_fund', label: 'صندوق‌های نقره' },
  { key: 'lev_fund', label: 'صندوق‌های اهرمی' },
  { key: 'fixed_fund', label: 'صندوق درآمد ثابت' },
  { key: 'top50', label: '۵۰ نماد بزرگ' },
];

const SELECT =
  'min-w-0 max-w-full rounded-lg border border-border-c bg-bg-card px-1.5 py-1 text-2xs text-text-primary';

/** ارتفاعِ ثابتِ کادر: مرجع هم همین نسبت را دارد و در ۷۶۸ پیکسلِ ارتفاعِ صفحه
 *  جدول‌ها باید زیرِ نقشه جا بمانند. */
const CANVAS_H: Record<string, number> = { xs: 240, md: 320, xl: 420 };

function useSize<T extends HTMLElement>() {
  // refِ callback-ای نه useEffectِ بی‌وابستگی: کادرِ نقشه بعدِ رسیدنِ داده
  // مشروط mount می‌شود و با `[]`، effect پیش از وجودِ عنصر اجرا و بی‌observe
  // تمام می‌شد — یعنی width تا ابد صفر و نقشۀ کاملاً سفید درِ مرورگر.
  const [el, setEl] = useState<T | null>(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    if (!el) return;
    // Offset-width به‌جای getBoundingClientRect: درِ این صفحه resize با تغییرِ
    // کلاسِ grid می‌آید و rect هر بارِ تازه‌ای read-only layout را force می‌کند.
    const ro = new ResizeObserver((entries) => {
      const next = Math.round(entries[0]?.contentRect.width ?? el.clientWidth);
      setW((prev) => (Math.abs(prev - next) < 2 ? prev : next));
    });
    ro.observe(el);
    setW(el.clientWidth);
    return () => ro.disconnect();
  }, [el]);
  return [setEl, w] as const;
}

export function MarketTreemap({
  testId = 'ms-treemap',
  title = 'نقشۀ بازار',
  fixedGroup,
  industries,
}: {
  testId?: string;
  title?: string;
  /** صفحۀ ۱۲ همان کامپوننت است با دامنهٔ قفل‌شده رویِ صندوق‌های طلا */
  fixedGroup?: string;
  /** گزینه‌هایِ کرکرۀ صنعت — از `useIndustries` می‌آید، نه از فهرستِ دستی */
  industries?: string[];
}) {
  const navigate = useNavigate();
  const [draftGroup, setDraftGroup] = useState(fixedGroup ?? 'eq_all');
  const [draftIndustry, setDraftIndustry] = useState('');
  const [draftMetric, setDraftMetric] = useState<TreemapMetric>('value');
  // «اعمال فیلتر» درِ مرجع دکمه دارد و باید واقعاً اعمال شود: applied != draft
  // یعنی انتخاب‌هایِ هنوز‌اعمال‌نشده عددِ رویِ نقشه را عوض نمی‌کنند.
  const [applied, setApplied] = useState({ group: fixedGroup ?? 'eq_all', industry: '', metric: 'value' as TreemapMetric });
  const [hover, setHover] = useState<TreemapNode | null>(null);

  const dirty =
    !fixedGroup &&
    (draftGroup !== applied.group || draftIndustry !== applied.industry || draftMetric !== applied.metric);

  const {
    data,
    isLoading,
    isError,
    refetch,
    status: treeStatus,
    dataUpdatedAt: treeUpdatedAt,
  } = useMstatTreemap(
    fixedGroup ?? applied.group,
    fixedGroup ? '' : applied.industry,
    applied.metric,
  );

  const rows = useMemo(() => (data?.rows ?? []) as TreemapNode[], [data]);
  const [wrapRef, wrapW] = useSize<HTMLDivElement>();
  const width = Math.max(0, wrapW);
  const height = CANVAS_H[xlKey(width)] ?? 320;

  const layout = useMemo(() => {
    if (!width || !rows.length) return [];
    const { rects } = squarify(rows.map((r) => ({ key: r.ins_code ?? r.symbol, value: r.size })));
    const byKey = new Map(rows.map((r) => [r.ins_code ?? r.symbol, r]));
    return rects
      .map((rc) => ({ rc, node: byKey.get(rc.key) }))
      .filter((x): x is { rc: (typeof x.rc & object); node: TreemapNode } => !!x.node);
  }, [rows, width]);

  const open = useCallback(
    (n: TreemapNode) => navigate(`/technical/${encodeURIComponent(n.symbol)}`),
    [navigate],
  );

  const metricLabel = data?.metric_label ?? METRICS.find((m) => m.key === applied.metric)?.label;

  return (
    <StatusSection
      testId={testId}
      title={title}
      hint="سطحِ هر خانه از معیارِ انتخابی می‌آید؛ رنگ از تغییرِ پایانی نسبت به دیروز"
      asof={data?.asof}
      badge={
        data
          ? `معیار: ${data.metric_label} (${data.metric_unit}) · مبنای رنگ: ${data.formula?.pct ?? 'pct'}`
          : undefined
      }
      toolbar={
        <div className="flex flex-wrap items-center gap-1.5" data-testid={`${testId}-filters`}>
          {!fixedGroup ? (
            <>
              <label className="flex items-center gap-1 text-3xs text-text-muted">
                دامنه
                <select
                  className={SELECT}
                  data-testid={`${testId}-group`}
                  value={draftGroup}
                  onChange={(e) => setDraftGroup(e.target.value)}
                >
                  {GROUPS.map((g) => (
                    <option key={g.key} value={g.key}>
                      {g.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex items-center gap-1 text-3xs text-text-muted">
                صنعت
                <select
                  className={SELECT}
                  data-testid={`${testId}-industry`}
                  value={draftIndustry}
                  onChange={(e) => setDraftIndustry(e.target.value)}
                >
                  <option value="">همه صنایع</option>
                  {(industries ?? (data?.groups ?? []).map((g) => g.industry)).map((i) => (
                    <option key={i} value={i}>
                      {i}
                    </option>
                  ))}
                </select>
              </label>
            </>
          ) : null}
          <label className="flex items-center gap-1 text-3xs text-text-muted">
            معیارِ سطح
            <select
              className={SELECT}
              data-testid={`${testId}-metric`}
              value={draftMetric}
              onChange={(e) => setDraftMetric(e.target.value as TreemapMetric)}
            >
              {METRICS.map((m) => (
                <option key={m.key} value={m.key}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            data-testid={`${testId}-apply`}
            disabled={!dirty}
            onClick={() =>
              setApplied({ group: draftGroup, industry: draftIndustry, metric: draftMetric })
            }
            className={`rounded-lg border px-2 py-1 text-2xs font-black transition-colors ${
              dirty
                ? 'border-accent-blue bg-accent-blue/15 text-accent-blue'
                : 'border-border-c bg-bg-card text-text-muted'
            }`}
          >
            اعمال فیلتر
          </button>
          {dirty ? (
            <span data-testid={`${testId}-dirty`} className="text-3xs text-accent-yellow">
              انتخاب تغییر کرده — هنوز اعمال نشده
            </span>
          ) : null}
          {/* فاز D: سنِ همینِ ویجت، نه ساعتِ سراسریِ صفحه. `/api/mstat/treemap`
              زمانِ خودِ عدد را گزارش نمی‌کند، پس برچسب همان را صریح می‌گوید. */}
          <WidgetFreshness
            label="نقشۀ بازار"
            input={{
              status: treeStatus,
              dataUpdatedAt: treeUpdatedAt,
              sourceAsOf: serverStamp(data?.computed_at),
            }}
          />
        </div>
      }
    >
      {isError && !data ? (
        <StatusError testId={testId} onRetry={() => void refetch()} />
      ) : isLoading && !data ? (
        <StatusLoading testId={testId} />
      ) : !rows.length ? (
        <>
          <StatusNoData
            testId={testId}
            text={`با این دامنه/صنعت/معیار خانه‌ای نماند — «بی‌داده» یعنی در این نشست ${
              metricLabel ?? 'معیار'
            }ی ثبت نشده، نه صفر.`}
          />
          <SourceNotice testId={testId} items={data?.no_source} />
        </>
      ) : (
        <>
          <div
            ref={wrapRef}
            className="relative min-w-0 w-full overflow-hidden rounded-lg border border-border-c bg-bg-secondary"
            data-testid={`${testId}-canvas`}
            style={{ height }}
          >
            <svg
              width={width || '100%'}
              height={height}
              viewBox={`0 0 ${width || 1} ${height}`}
              role="img"
              aria-label={`نقشۀ بازار بر حسبِ ${metricLabel ?? 'معیار'}`}
              data-testid={`${testId}-svg`}
            >
              {layout.map(({ rc, node }) => {
                const pxW = rc.w * width;
                const pxH = rc.h * height;
                const tone = toneOf(node.tone);
                const showName = pxW >= TREEMAP_LABEL_MIN_W && pxH >= TREEMAP_LABEL_MIN_H;
                const showPct = pxW >= 26 && pxH >= 30;
                return (
                  <g
                    key={rc.key}
                    data-testid={`treemap-cell-${node.symbol}`}
                    data-tone={tone}
                    onClick={() => open(node)}
                    onMouseEnter={() => setHover(node)}
                    onMouseLeave={() => setHover((h) => (h?.symbol === node.symbol ? null : h))}
                    className="cursor-pointer"
                  >
                    <title>{`${node.symbol} — ${node.name ?? ''}\n${
                      data?.metric_label ?? ''
                    }: ${toFaDigits(node.size)} ${node.unit}\nتغییر: ${fmtPct(node.pct ?? null)}`}</title>
                    <rect
                      x={rc.x * width}
                      y={rc.y * height}
                      width={Math.max(0, pxW - 1)}
                      height={Math.max(0, pxH - 1)}
                      rx={2}
                      className={TONE_CLASS[tone].fill}
                      stroke="var(--border-color)"
                      strokeWidth={0.6}
                    />
                    {showName ? (
                      <text
                        x={rc.x * width + pxW / 2}
                        y={rc.y * height + (showPct ? pxH / 2 - 4 : pxH / 2 + 3)}
                        textAnchor="middle"
                        className={`pointer-events-none select-none ${TONE_CLASS[tone].fillText}`}
                        style={{ fontSize: 11, fontWeight: 800 }}
                      >
                        {node.symbol}
                      </text>
                    ) : null}
                    {showPct ? (
                      <text
                        x={rc.x * width + pxW / 2}
                        y={rc.y * height + pxH / 2 + 9}
                        textAnchor="middle"
                        className={`pointer-events-none select-none ${TONE_CLASS[tone].fillText}`}
                        style={{ fontSize: 10, fontWeight: 700 }}
                      >
                        {fmtPct(node.pct ?? null)}
                      </text>
                    ) : null}
                  </g>
                );
              })}
            </svg>
            {hover ? (
              <div
                data-testid={`${testId}-tooltip`}
                className="pointer-events-none absolute bottom-1 left-1 max-w-[92%] rounded-lg border border-border-c bg-bg-card/95 px-2 py-1 text-3xs text-text-primary shadow"
              >
                <span className="font-black">{hover.symbol}</span>
                <span className="mx-1 text-text-muted">{hover.name}</span>
                <span className="num-text">{`${data?.metric_label}: ${toFaDigits(
                  hover.size,
                )} ${hover.unit}`}</span>
                <span className="num-text mx-1">{fmtPct(hover.pct ?? null)}</span>
                <span className="num-text text-text-muted">
                  پایانی {fmtInt(hover.p_closing ?? null)} · {hover.industry ?? 'بی‌صنعت'}
                </span>
              </div>
            ) : null}
          </div>

          <div className="flex flex-wrap items-center gap-x-3 gap-y-1" data-testid={`${testId}-legend`}>
            {TONE_LEGEND.map((l) => (
              <span key={l.tone} className="flex items-center gap-1 text-3xs text-text-secondary">
                <span className={`inline-block size-2 rounded-sm ${TONE_CLASS[l.tone].dot}`} />
                {l.label}
              </span>
            ))}
          </div>

          <p className="num-text text-3xs text-text-muted" data-testid={`${testId}-count`}>
            {toFaDigits(data?.shown ?? rows.length)} خانه از{' '}
            {toFaDigits(data?.total_nodes ?? rows.length)} نمادِ دارایِ {metricLabel?.toLowerCase() ?? 'معیار'} ·
            دامنه: {data?.group_label ?? applied.group}
            {applied.industry ? ` · صنعت: ${applied.industry}` : ''} · مجموع:{' '}
            {toFaDigits(data?.total_size?.toFixed(0) ?? '0')} {data?.metric_unit} ·{' '}
            {toFaDigits(data?.skipped_nodata ?? 0)} نمادِ بی‌{metricLabel?.toLowerCase() ?? 'داده'} در
            چیدمان نیست.
          </p>
          <SourceNotice testId={testId} items={data?.no_source} />
        </>
      )}
    </StatusSection>
  );
}

function xlKey(width: number) {
  if (width >= 1100) return 'xl';
  if (width >= 640) return 'md';
  return 'xs';
}
