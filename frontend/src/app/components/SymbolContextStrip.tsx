import { useLocation, useNavigate } from 'react-router';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useInspectorRawRow, useInspectorBoard } from '@widgets/useInspectorBoard';
import { useSymbolVeto } from '@widgets/useSymbolVeto';
import { toFaDigits, fmtPct, fmtInt } from '@shared/lib/fmt';
import { Badge } from '@shared/components/ui/badge';
import { Button } from '@shared/components/ui/button';
import { LiveNumber } from '@shared/components/ui/live-number';
import { ClientShareInline } from '@shared/components/ClientSharePct';

export function SymbolContextStrip() {
  const symbol = useSymbolStore((s) => s.symbol);
  const pinned = useSymbolStore((s) => s.pinned);
  const togglePin = useSymbolStore((s) => s.togglePin);
  const clearSymbol = useSymbolStore((s) => s.clearSymbol);

  const rawRow = useInspectorRawRow();
  const board = useInspectorBoard();
  const veto = useSymbolVeto(symbol);

  const location = useLocation();
  const navigate = useNavigate();

  if (!symbol) return null;

  const isPinned = pinned.includes(symbol);
  const pct = board?.percentChange ?? null;
  const isPos = pct != null && pct > 0;
  const isNeg = pct != null && pct < 0;

  const currentPath = location.pathname;

  const routes = [
    { id: 'technical', label: 'تکنیکال', path: `/technical/${encodeURIComponent(symbol)}` },
    { id: 'fundamental', label: 'بنیادی', path: `/fundamental/${encodeURIComponent(symbol)}` },
    { id: 'master', label: 'مستر FTS', path: `/master/${encodeURIComponent(symbol)}` },
    { id: 'strategy-tree', label: 'درخت FTS', path: `/strategy-tree/${encodeURIComponent(symbol)}` },
    { id: 'market', label: 'تابلو', path: '/market' },
  ];

  return (
    <div
      role="region"
      aria-label={`اطلاعات نماد ${symbol}`}
      /* دیگر چسبان نیست: ارتفاعِ اینِ نوار باِ flex-wrap بهِ محتوا بستگی دارد
         (سنجشِ ۱۳۶۶ باِ داورِ باز: ۶۵px، بی‌داور ۳۸px) و «top-9» ثابت هیچ‌وقت
         پایینِ آن را نمی‌گیرد — ناوبریِ بخش‌ها زیرِ آن می‌ماند. پین‌شدنِ
         فقط رویِ Topbar (۳۶pxِ قطعی) است و نمادِ انتخابی همان‌جا درِ
         breadcrumb دیده می‌شود. */
      className="relative flex min-h-[38px] w-full shrink-0 flex-wrap items-center justify-between gap-2 border-b border-border-c/70 bg-bg-secondary/95 px-3 py-1 text-xs backdrop-blur-md shadow-xs transition-all duration-150"
    >
      {/* سمت راست (شروع): شناسه و مشخصات نماد */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => togglePin(symbol)}
          title={isPinned ? 'حذف از نشان‌شده‌ها' : 'افزودن به نشان‌شده‌ها'}
          aria-label={isPinned ? 'حذف از نشان‌شده‌ها' : 'نشان‌کردن نماد'}
          className={`rounded-md p-1 transition-colors ${
            isPinned
              ? 'text-accent-yellow hover:text-accent-yellow/80'
              : 'text-text-muted hover:text-text-primary'
          }`}
        >
          {isPinned ? '★' : '☆'}
        </button>

        <div className="flex items-baseline gap-1.5">
          <span className="text-sm font-black text-text-primary">{symbol}</span>
          {board?.name ? (
            <span className="hidden truncate text-2xs text-text-muted md:inline max-w-[140px]">
              {board.name}
            </span>
          ) : null}
        </div>

        {board?.sector ? (
          <Badge variant="secondary" size="xs" className="hidden lg:inline-flex">
            {board.sector}
          </Badge>
        ) : null}

        {rawRow?.st_title ? (
          <Badge
            variant={rawRow.f_susp ? 'warning' : rawRow.st_title === 'مجاز' ? 'success' : 'destructive'}
            size="xs"
          >
            {rawRow.st_title}
          </Badge>
        ) : null}

        {/* برچسب وتوی مجمع یا روند */}
        {veto.assembly.veto ? (
          <Badge variant="warning" size="xs">
            {veto.assembly.label || 'وتوی مجمع'}
          </Badge>
        ) : veto.weekly.veto ? (
          <Badge variant="destructive" size="xs">
            وتوی هفتگی
          </Badge>
        ) : null}
      </div>

      {/* بخش میانی: اعداد قیمتی و درصدی زنده با انیمیشن ملایم و فلاش مارکت */}
      <div className="flex items-center gap-3 font-mono text-2xs">
        {board?.pLast != null ? (
          <div className="flex items-baseline gap-1">
            <span className="text-text-muted text-3xs font-sans">آخرین:</span>
            <LiveNumber
              value={board.pLast}
              format={(v) => fmtInt(v)}
              className="font-bold text-text-primary"
            />
          </div>
        ) : null}

        {board?.pClosing != null ? (
          <div className="flex items-baseline gap-1">
            <span className="text-text-muted text-3xs font-sans">پایانی:</span>
            <LiveNumber
              value={board.pClosing}
              format={(v) => fmtInt(v)}
              className="font-semibold text-text-secondary"
            />
          </div>
        ) : null}

        {pct != null ? (
          <Badge
            variant={isPos ? 'success' : isNeg ? 'destructive' : 'secondary'}
            size="sm"
            className="font-bold"
          >
            <LiveNumber
              value={pct}
              format={(v) => fmtPct(v)}
              flash={false}
            />
          </Badge>
        ) : null}

        {board?.buyerPower != null && board.buyerPower > 0 ? (
          <div className="hidden items-baseline gap-1 sm:flex">
            <span className="text-text-muted text-3xs font-sans">قدرت خریدار:</span>
            <LiveNumber
              value={board.buyerPower}
              format={(v) => toFaDigits(v.toFixed(2))}
              className={
                board.buyerPower >= 1.2
                  ? 'text-accent-green font-bold'
                  : board.buyerPower <= 0.8
                    ? 'text-accent-red font-bold'
                    : 'text-text-secondary font-bold'
              }
            />
          </div>
        ) : null}

        {/* بند ۲ مأموریت: سهمِ حقیقی/حقوقی از ارزشِ خرید و فروش، همان عددِ
            بک‌اند (`client_split.py`) از ردیفِ خودِ تابلو — کنارِ نسبتِ
            خریدار/فروشنده، درِ نوارِزمینۀ نماد که روی صفحۀ بنیادی هم می‌آید.
            «ح/حقوقی» نیست: برچسبِ کامل درِ title نشسته است. */}
        {rawRow ? (
          <div className="hidden items-baseline gap-1.5 sm:flex" data-testid="strip-client-share">
            <span className="text-text-muted text-3xs font-sans">سهمِ حقیقی از ارزش:</span>
            <ClientShareInline row={rawRow} side="buy" testId="strip-client-share-buy" />
            <span className="text-text-muted text-3xs">/</span>
            <ClientShareInline row={rawRow} side="sell" testId="strip-client-share-sell" />
          </div>
        ) : null}
      </div>

      {/* سمت چپ (پایان): دکمه‌های ناوبری سریع و بستن نماد */}
      <div className="flex items-center gap-1.5">
        <div className="hidden items-center gap-1 sm:flex">
          {routes.map((r) => {
            const isActive = currentPath.startsWith(`/${r.id}`);
            return (
              <Button
                key={r.id}
                size="xs"
                variant={isActive ? 'default' : 'ghost'}
                onClick={() => navigate(r.path)}
                className={isActive ? 'font-bold' : 'text-text-muted hover:text-text-primary'}
              >
                {r.label}
              </Button>
            );
          })}
        </div>

        <button
          type="button"
          onClick={clearSymbol}
          title="بستن کانتکست نماد"
          aria-label="بستن کانتکست نماد"
          className="rounded-md border border-border-c/60 p-1 text-2xs text-text-muted transition-colors hover:border-accent-red/50 hover:bg-accent-red/10 hover:text-accent-red"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
