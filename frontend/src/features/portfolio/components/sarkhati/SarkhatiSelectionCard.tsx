// features/portfolio/components/sarkhati/SarkhatiSelectionCard.tsx — انتخاب از
// دیده‌بانِ EasyTrader و پرتفوی، در یک فهرست؛ دو منبع جدا و یک نمادِ واحد.
//
// هیچ‌کدام از این دو منبع «سفارش» نیست. هدف و اولویت فقط در فهرستِ سرخطی
// ذخیره می‌شوند؛ ارسال/قیمت/حجم در فرمِ سفارش سنجیده می‌شود و live خاموش است.
import { useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useMarketFeedShared } from '@shared/api/marketFeed';
import { fmtInt, fmtPct, toFaDigits } from '@shared/lib/fmt';
import { matchFa, normalizeFa } from '@shared/lib/normalizeFa';
import { useSymbolStore } from '@shared/stores/symbolStore';
import type { MarketRow } from '@shared/types/marketRow';
import {
  useBuyingPower, useEasyTraderWatchlist, useExecutionPortfolio,
} from '../../lib/orderClient';
import {
  selectionKey, useSarkhatiSelectionStore, type SelectionGoal, type SelectionSource,
  type SelectedSymbol,
} from '../../stores/sarkhatiSelectionStore';
import { Chip, GhostBtn, Line, Note } from './parts';

const SOURCE_LABEL: Record<SelectionSource, string> = {
  watchlist: 'دیده‌بان', portfolio: 'پرتفوی', market: 'تابلو',
};
const GOAL_LABEL: Record<SelectionGoal, string> = {
  buy: 'خرید', sell: 'فروش', unknown: 'نامشخص',
};
const TABS = [
  { id: 'all', label: 'همهٔ نمادها' },
  { id: 'watchlist', label: 'دیده‌بان من' },
  { id: 'portfolio', label: 'پرتفوی من' },
  { id: 'selected', label: 'انتخاب‌شده‌ها' },
] as const;
type Tab = typeof TABS[number]['id'];

type Unified = {
  key: string; symbol: string; name: string; isin: string | null;
  ins_code: string | null; sources: SelectionSource[]; categories: string[];
  market: MarketRow | null; pos: Record<string, unknown> | null;
};

function str(v: unknown): string {
  return typeof v === 'string' ? v : v == null ? '' : String(v);
}
function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}
function addSource(list: SelectionSource[], s: SelectionSource): SelectionSource[] {
  return list.includes(s) ? list : [...list, s];
}
function rawNum(v: unknown): string {
  const n = num(v);
  return n == null ? '—' : fmtInt(n);
}
function clock(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isFinite(d.getTime())
    ? d.toLocaleTimeString('fa-IR', { hour12: false }) : '—';
}
function sumAmounts(items: SelectedSymbol[]): number | null {
  let total = 0;
  let any = false;
  for (const it of items) {
    const raw = it.amount.replace(/[٬,]/g, '').replace(/[^0-9.]/g, '');
    const v = Number(raw);
    if (Number.isFinite(v) && v > 0) { total += v; any = true; }
  }
  return any ? total : null;
}

export function SarkhatiSelectionCard() {
  const qc = useQueryClient();
  const feed = useMarketFeedShared((f) => f.data ?? [], 60_000);
  const watchQ = useEasyTraderWatchlist();
  const portQ = useExecutionPortfolio();
  const bpQ = useBuyingPower();
  const setSymbol = useSymbolStore((s) => s.setSymbol);
  const currentSymbol = useSymbolStore((s) => s.symbol);
  const sel = useSarkhatiSelectionStore();
  const [tab, setTab] = useState<Tab>('watchlist');
  const [q, setQ] = useState('');

  const watch = watchQ.data;
  const port = portQ.data;
  const bp = bpQ.data;
  const feedRows = feed.data ?? [];
  const watchRows = (watch?.rows ?? []) as Record<string, unknown>[];
  const portRows = (port?.positions ?? port?.rows ?? []) as Record<string, unknown>[];
  const watchUnique = new Set(watchRows
    .filter((r) => r.resolved === true && str(r.symbol))
    .map((r) => normalizeFa(str(r.symbol)))).size;
  const portUnique = new Set(portRows
    .filter((r) => r.resolved === true && str(r.symbol))
    .map((r) => normalizeFa(str(r.symbol)))).size;

  const unified = useMemo(() => {
    const map = new Map<string, Unified>();
    const symbolToKey = new Map<string, string>();
    const ensure = (symbol: string, isin: string | null, insCode: string | null,
      name: string): Unified => {
      const key = selectionKey({ symbol, isin });
      const norm = normalizeFa(symbol);
      let u = map.get(key);
      if (!u) {
        const fallback = symbolToKey.get(norm);
        if (fallback?.startsWith('sym:') && map.has(fallback)) {
          u = map.get(fallback)!;
          map.delete(fallback);
          u.key = key;
          map.set(key, u);
        }
      }
      if (!u) {
        u = { key, symbol, name: name || symbol, isin, ins_code: insCode,
          sources: [], categories: [], market: null, pos: null };
        map.set(key, u);
      } else {
        if (!u.name || u.name === u.symbol) u.name = name || u.name;
        if (!u.isin && isin) u.isin = isin;
        if (!u.ins_code && insCode) u.ins_code = insCode;
      }
      symbolToKey.set(norm, u.key);
      return u;
    };
    for (const r of feedRows) {
      if (!r.symbol) continue;
      const u = ensure(r.symbol, null, null, str(r.name));
      u.market = r;
    }
    for (const w of watchRows) {
      if (w.resolved !== true) continue;
      const symbol = str(w.symbol);
      if (!symbol) continue;
      const u = ensure(symbol, str(w.isin) || null, str(w.ins_code) || null, '');
      u.sources = addSource(u.sources, 'watchlist');
      const cat = str(w.category_name);
      if (cat && !u.categories.includes(cat)) u.categories.push(cat);
    }
    for (const p of portRows) {
      if (p.resolved !== true) continue;
      const symbol = str(p.symbol);
      if (!symbol) continue;
      const u = ensure(symbol, str(p.isin) || null, str(p.ins_code) || null,
        str(p.broker_name));
      u.sources = addSource(u.sources, 'portfolio');
      u.pos = p;
    }
    for (const u of map.values()) {
      if (!u.sources.length && u.market) u.sources = ['market'];
    }
    return [...map.values()];
  }, [feedRows, watchRows, portRows]);

  const byKey = useMemo(() => new Map(unified.map((u) => [u.key, u])), [unified]);
  const selectedKeys = useMemo(
    () => new Set(sel.items.map((i) => i.key)), [sel.items]);
  const identityConflicts = useMemo(() => {
    const bySymbol = new Map<string, Set<string>>();
    for (const u of unified) {
      if (!u.sources.some((s) => s !== 'market')) continue;
      const norm = normalizeFa(u.symbol);
      const keys = bySymbol.get(norm) ?? new Set<string>();
      keys.add(u.key);
      bySymbol.set(norm, keys);
    }
    return [...bySymbol.entries()]
      .filter(([, keys]) => keys.size > 1).map(([norm]) => norm);
  }, [unified]);

  const watchUnresolved = watchRows.filter((r) => r.resolved !== true);
  const portUnresolved = portRows.filter((r) => r.resolved !== true);

  const selectedRows = useMemo(() => sel.items.map((it) => {
    const u = byKey.get(it.key);
    return u ?? {
      key: it.key, symbol: it.symbol, name: it.name || it.symbol,
      isin: it.isin, ins_code: it.ins_code, sources: it.sources, categories: [],
      market: null, pos: null,
    } as Unified;
  }), [sel.items, byKey]);

  const visible = useMemo(() => {
    const needle = q.trim();
    const list = tab === 'all' ? unified
      : tab === 'watchlist' ? unified.filter((u) => u.sources.includes('watchlist'))
        : tab === 'portfolio' ? unified.filter((u) => u.sources.includes('portfolio'))
          : selectedRows;
    const filtered = needle
      ? list.filter((u) => matchFa(u.symbol, needle) || matchFa(u.name, needle)
        || matchFa(u.isin ?? '', needle))
      : list;
    if (!needle && tab === 'all') return [];
    return filtered.slice(0, 80);
  }, [q, tab, unified, selectedRows]);

  const toggleRow = (u: Unified) => {
    sel.toggle({ symbol: u.symbol, name: u.name, isin: u.isin,
      ins_code: u.ins_code, sources: u.sources });
  };
  const selectVisible = () => {
    for (const u of visible) {
      if (!u.symbol || selectedKeys.has(u.key)) continue;
      sel.toggle({ symbol: u.symbol, name: u.name, isin: u.isin,
        ins_code: u.ins_code, sources: u.sources });
    }
  };
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['execution-watchlist'] });
    void qc.invalidateQueries({ queryKey: ['execution-portfolio'] });
    void qc.invalidateQueries({ queryKey: ['execution-buying-power'] });
  };

  const watchOk = watch?.state === 'WATCHLIST_VERIFIED';
  const portOk = port?.status === 'success';
  const bpOk = bp?.state === 'BUYING_POWER_VERIFIED';
  const watchTone = watchQ.isPending ? 'idle' : watchOk ? 'ok' : 'bad';
  const portTone = portQ.isPending ? 'idle' : !portOk ? 'bad'
    : port?.state === 'PORTFOLIO_PARTIALLY_VERIFIED' ? 'warn' : 'ok';
  const bpTone = bpQ.isPending ? 'idle' : bpOk ? 'ok' : 'bad';
  const bpValue = num(bp?.value);
  const missing = (port?.missing_fields ?? []) as string[];
  const goals = sel.items.reduce((m, it) => {
    m[it.goal] = (m[it.goal] ?? 0) + 1;
    return m;
  }, {} as Partial<Record<SelectionGoal, number>>);
  const amountTotal = sumAmounts(sel.items);
  const times = {
    watchlist: watch?.fetched_at ?? null,
    portfolio: port?.fetched_at ?? null,
    buyingPower: bp?.fetched_at ?? null,
  };

  return (
    <section className="rounded-xl border border-border-c/70 bg-bg-card/25 px-2.5 py-2"
      data-testid="sarkhati-selection-card">
      <div className="flex flex-wrap items-center gap-1.5" data-testid="sources-summary">
        <h4 className="text-2xs font-black text-text-primary">انتخاب نماد برای سرخطی</h4>
        <Chip tone={watchTone} testId="sources-watchlist"
          title={watch?.error ?? 'دیده‌بانِ شخصی EasyTrader — منبعی جدا از پرتفوی'}>
          دیده‌بان: {watchQ.isPending ? 'در حال دریافت…' : !watchOk
            ? 'در دسترس نیست' : `${toFaDigits(String(watchUnique))} نماد`}
        </Chip>
        <Chip tone={portTone} testId="sources-portfolio"
          title={port?.error ?? (missing.length ? 'تعداد/آزاد/قابل‌فروش در منبع نیست' : 'پرتفوی خواندنی')}>
          پرتفوی: {portQ.isPending ? 'در حال دریافت…' : !portOk
            ? 'در دسترس نیست' : `${toFaDigits(String(portUnique))} دارایی`}
        </Chip>
        <Chip tone={bpTone} testId="sources-buying-power"
          title={bp?.error ?? bp?.formula ?? 'قدرت خرید خواندنی'}>
          قدرت خرید: {bpQ.isPending ? '…' : !bpOk ? 'نامعلوم'
            : bpValue == null ? 'بدون مقدار' : (
              <span data-testid="sources-buying-power-value" className="num">
                {fmtInt(bpValue)} ریال
              </span>
            )}
        </Chip>
        <GhostBtn testId="sources-refresh" onClick={refresh}
          title="خواندن دوبارهٔ همان سه منبع؛ هیچ نوشتنی انجام نمی‌شود">
          به‌روزرسانی
        </GhostBtn>
        <span className="ms-auto text-3xs text-text-muted" data-testid="sources-times">
          دیده‌بان {clock(times.watchlist)} · پرتفوی {clock(times.portfolio)}
          {' · '}قدرت خرید {clock(times.buyingPower)}
        </span>
      </div>

      {!watchOk && !watchQ.isPending ? (
        <Line kind="warn" testId="sources-watchlist-error">
          دیده‌بان خوانده نشد: {watch?.error || 'پاسخی نیامد'} — فهرستِ خالی جعل نمی‌شود.
        </Line>
      ) : null}
      {!portOk && !portQ.isPending ? (
        <Line kind="warn" testId="sources-portfolio-error">
          پرتفوی خوانده نشد: {port?.error || 'پاسخی نیامد'} — مقدار ساختگی نمایش داده نمی‌شود.
        </Line>
      ) : null}
      {!bpOk && !bpQ.isPending ? (
        <Line kind="warn" testId="sources-buying-power-error">
          قدرت خرید نامعلوم است: {bp?.error || 'پاسخی نیامد'} — پیش‌بررسیِ خرید مسدود می‌ماند.
        </Line>
      ) : null}
      {watchOk && (watch?.duplicate_count ?? 0) > 0 ? (
        <Line kind="muted" testId="sources-watch-duplicates">
          دیده‌بان: {toFaDigits(String(watch?.raw_count ?? 0))} ردیف،
          {' '}{toFaDigits(String(watchUnique))} نمادِ یکتا،
          {' '}{toFaDigits(String(watch?.duplicate_count ?? 0))} تکراری — تکراری‌ها یک نماد نمایش داده می‌شوند.
        </Line>
      ) : null}
      {missing.length ? (
        <Line kind="muted" testId="sources-portfolio-missing">
          پرتفوی منبعِ تعدادِ کل/آزاد/قابل‌فروش نیست؛ این سه فیلد نمایش داده نمی‌شوند.
        </Line>
      ) : null}
      {portOk && portRows.length ? (
        <Line kind="muted" testId="sources-portfolio-units">
          واحدِ ارزش و میانگین خرید در منبع تأیید نشد؛ عددِ خام، بدونِ ادعای ریال.
        </Line>
      ) : null}
      {watchUnresolved.length || portUnresolved.length ? (
        <Line kind="warn" testId="sources-unresolved">
          {toFaDigits(String(watchUnresolved.length + portUnresolved.length))} ردیف
          به نمادِ بازار نگاشت نشد (ISIN مبهم/ناشناس) و قابلِ انتخاب نیست.
        </Line>
      ) : null}
      {identityConflicts.length ? (
        <Line kind="warn" testId="sources-identity-conflicts">
          {toFaDigits(String(identityConflicts.length))} نماد با دو ISINِ متفاوت در
          منابع دیده شد؛ به‌جایِ یکی‌کردنِ حدسی، ردیف‌ها جدا نگه داشته شدند.
        </Line>
      ) : null}

      <div className="mt-1.5 flex flex-wrap items-center gap-1" role="tablist"
        aria-label="منبع نمادها" data-testid="sarkhati-source-tabs">
        {TABS.map((t) => {
          const count = t.id === 'watchlist' ? (watchOk ? watchUnique : 0)
            : t.id === 'portfolio' ? (portOk ? portUnique : 0)
              : t.id === 'selected' ? sel.items.length : null;
          return (
            <button key={t.id} type="button" role="tab" aria-selected={tab === t.id}
              data-testid={`sarkhati-source-tab-${t.id}`}
              onClick={() => setTab(t.id)}
              className={`inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-2xs font-bold ${
                tab === t.id ? 'border-accent-blue/60 bg-accent-blue/10 text-accent-blue'
                  : 'border-border-c bg-bg-primary/40 text-text-secondary'}`}>
              {t.label}
              {count != null ? <span className="num text-3xs text-text-muted">
                {toFaDigits(String(count))}</span> : null}
            </button>
          );
        })}
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="جست‌وجوی نماد، نام یا ISIN"
          aria-label="جست‌وجوی نماد در منابع"
          data-testid="sarkhati-source-search"
          className="ms-auto w-[min(18rem,100%)] rounded-lg border border-border-c
            bg-bg-primary px-2 py-1 text-2xs text-text-primary placeholder:text-text-muted" />
      </div>

      <div className="mt-1 flex flex-wrap items-center gap-1">
        <GhostBtn testId="sarkhati-source-select-visible" onClick={selectVisible}
          disabled={!visible.length}>انتخابِ نتایجِ این فهرست</GhostBtn>
        <GhostBtn testId="sarkhati-source-clear" onClick={sel.clear}
          disabled={!sel.items.length}>پاک کردنِ انتخاب</GhostBtn>
        <span className="text-2xs text-text-muted" data-testid="sarkhati-selection-count">
          انتخاب‌شده: {toFaDigits(String(sel.items.length))}
        </span>
      </div>

      {tab === 'all' && !q.trim() ? (
        <Line kind="muted" testId="sarkhati-source-all-hint">
          برای دیدنِ همهٔ نمادهای تابلو، نماد یا نام را جست‌وجو کنید.
        </Line>
      ) : null}

      <ul className="sk-scroll mt-1 max-h-[13rem] overflow-y-auto rounded-lg border
        border-border-c/50" data-testid="sarkhati-source-list">
        {visible.map((u) => {
          const on = selectedKeys.has(u.key);
          const last = num(u.market?.p_last);
          const pct = num(u.market?.percent_change);
          return (
            <li key={u.key} data-testid={`sarkhati-source-row-${u.key}`}
              className="flex flex-wrap items-center gap-x-2 gap-y-0.5 border-b
                border-border-c/25 px-2 py-1 text-2xs last:border-0">
              <input type="checkbox" checked={on} onChange={() => toggleRow(u)}
                aria-label={`انتخاب ${u.symbol}`}
                data-testid={`sarkhati-source-pick-${u.key}`}
                className="size-3.5 accent-accent-blue" />
              <button type="button" onClick={() => setSymbol(u.symbol)}
                title="انتخاب این نماد برای فرمِ سفارش"
                data-testid={`sarkhati-source-use-${u.key}`}
                className="num font-black text-text-primary hover:text-accent-blue">
                {u.symbol}
              </button>
              <span className="min-w-0 max-w-[22ch] truncate text-text-secondary"
                title={u.name}>{u.name}</span>
              {u.sources.map((s) => (
                <Chip key={s} tone={s === 'portfolio' ? 'warn' : 'idle'}>
                  {SOURCE_LABEL[s]}
                </Chip>
              ))}
              {u.categories.length ? (
                <span className="text-3xs text-text-muted" title={u.categories.join(' · ')}>
                  {u.categories.join(' · ')}
                </span>
              ) : null}
              {last != null ? <span className="num text-text-secondary">{fmtInt(last)}</span> : null}
              {pct != null ? <span className={`num text-3xs ${
                pct > 0 ? 'text-accent-green' : pct < 0 ? 'text-accent-red' : 'text-text-muted'}`}>
                {fmtPct(pct)}</span> : null}
              {u.pos ? <span className="text-3xs text-text-muted" data-testid="source-position">
                ارزش (عدد خام): {rawNum(u.pos.asset)} · میانگین خرید (عدد خام): {rawNum(u.pos.avg_buy)}
              </span> : null}
              {currentSymbol && normalizeFa(currentSymbol) === normalizeFa(u.symbol) ? (
                <Chip tone="ok" title="نمادِ فرمِ سفارش">فرم</Chip>
              ) : null}
            </li>
          );
        })}
        {!visible.length ? (
          <li className="px-2 py-2 text-2xs text-text-muted" data-testid="sarkhati-source-empty">
            {tab === 'selected' ? 'هنوز نمادی انتخاب نشده است.'
              : tab === 'all' ? 'نتیجه‌ای در جست‌وجو نیست.'
                : tab === 'watchlist' ? (watchOk ? 'دیده‌بان خالی است.' : 'دیده‌بان در دسترس نیست.')
                  : (portOk ? 'پرتفوی خالی است.' : 'پرتفوی در دسترس نیست.')}
          </li>
        ) : null}
      </ul>

      {watchUnresolved.length && (tab === 'watchlist' || tab === 'all') ? (
        <details className="mt-1 rounded-lg border border-border-c/40 px-2 py-1"
          data-testid="sarkhati-watch-unresolved">
          <summary className="cursor-pointer text-2xs text-accent-yellow">
            ردیف‌هایِ نگاشت‌نشدهٔ دیده‌بان ({toFaDigits(String(watchUnresolved.length))})
          </summary>
          <ul className="mt-1 flex flex-col gap-0.5">
            {watchUnresolved.map((r, i) => (
              <li key={`${str(r.isin)}-${i}`} className="num text-3xs text-text-muted" dir="ltr">
                {str(r.isin)} · {str(r.mapping_error) || 'بدونِ نگاشت'}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      {portUnresolved.length && (tab === 'portfolio' || tab === 'all') ? (
        <details className="mt-1 rounded-lg border border-border-c/40 px-2 py-1"
          data-testid="sarkhati-port-unresolved">
          <summary className="cursor-pointer text-2xs text-accent-yellow">
            ردیف‌هایِ نگاشت‌نشدهٔ پرتفوی ({toFaDigits(String(portUnresolved.length))})
          </summary>
          <ul className="mt-1 flex flex-col gap-0.5">
            {portUnresolved.map((r, i) => (
              <li key={`${str(r.isin)}-${i}`} className="num text-3xs text-text-muted" dir="ltr">
                {str(r.isin)} · {str(r.mapping_error) || 'بدونِ نگاشت'}
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      <details className="mt-1 rounded-lg border border-border-c/50 px-2 py-1"
        data-testid="sarkhati-selection-review">
        <summary className="cursor-pointer text-2xs font-bold text-accent-blue">
          مرور و ذخیرهٔ فهرست سرخطی ({toFaDigits(String(sel.items.length))})
          {sel.dirty ? ' · ذخیره‌نشده' : ''}
        </summary>
        <div className="mt-1.5 flex flex-col gap-1">
          {sel.items.map((it, i) => {
            const u = byKey.get(it.key);
            return (
              <div key={it.key} data-testid={`sarkhati-selected-row-${i}`}
                className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg
                  border border-border-c/40 bg-bg-primary/30 px-2 py-1">
                <span className="num text-3xs font-black text-text-muted">
                  {toFaDigits(String(i + 1))}
                </span>
                <span className="num text-2xs font-black text-text-primary">{it.symbol}</span>
                <span className="min-w-0 max-w-[18ch] truncate text-3xs text-text-secondary"
                  title={it.name}>{it.name}</span>
                {it.sources.map((s) => (
                  <Chip key={s} tone={s === 'portfolio' ? 'warn' : 'idle'}>
                    {SOURCE_LABEL[s]}
                  </Chip>
                ))}
                <div className="flex items-center gap-0.5" role="group" aria-label="هدف">
                  {(['buy', 'sell', 'unknown'] as SelectionGoal[]).map((g) => (
                    <button key={g} type="button" onClick={() => sel.setGoal(it.key, g)}
                      data-testid={`sarkhati-goal-${g}-${i}`}
                      className={`rounded border px-1 text-3xs ${
                        it.goal === g ? 'border-accent-blue text-accent-blue'
                          : 'border-border-c text-text-muted'}`}>
                      {GOAL_LABEL[g]}
                    </button>
                  ))}
                </div>
                <div className="flex items-center gap-0.5">
                  <button type="button" onClick={() => sel.move(it.key, -1)}
                    disabled={i === 0} aria-label="بالا"
                    className="rounded border border-border-c px-1 text-3xs disabled:opacity-30">↑</button>
                  <button type="button" onClick={() => sel.move(it.key, 1)}
                    disabled={i === sel.items.length - 1} aria-label="پایین"
                    className="rounded border border-border-c px-1 text-3xs disabled:opacity-30">↓</button>
                </div>
                <input value={it.amount} onChange={(e) => sel.setAmount(it.key, e.target.value)}
                  inputMode="decimal" placeholder="بودجه (ریال)" aria-label={`بودجه ${it.symbol}`}
                  data-testid={`sarkhati-amount-${i}`}
                  className="w-24 rounded border border-border-c bg-bg-primary px-1 py-0.5
                    text-3xs text-text-primary" />
                <button type="button" onClick={() => sel.remove(it.key)}
                  data-testid={`sarkhati-selected-remove-${i}`}
                  className="text-3xs text-accent-red">حذف</button>
                {u?.pos ? <span className="text-3xs text-text-muted"
                  data-testid="selected-position-values">
                  ارزش (عدد خام): {rawNum(u.pos.asset)} · میانگین (عدد خام): {rawNum(u.pos.avg_buy)}
                </span> : null}
              </div>
            );
          })}
          {!sel.items.length ? (
            <Line kind="muted">هنوز نمادی انتخاب نشده؛ از فهرست بالا انتخاب کنید.</Line>
          ) : null}

          <div className="rounded-lg border border-border-c/40 bg-bg-primary/30 px-2 py-1
            text-2xs text-text-secondary" data-testid="sarkhati-selection-summary">
            <div className="flex flex-wrap gap-x-3 gap-y-0.5">
              <span>منابع: دیده‌بان {toFaDigits(String(sel.items.filter((x) => x.sources.includes('watchlist')).length))}</span>
              <span>پرتفوی {toFaDigits(String(sel.items.filter((x) => x.sources.includes('portfolio')).length))}</span>
              <span>هدف: خرید {toFaDigits(String(goals.buy ?? 0))} · فروش {toFaDigits(String(goals.sell ?? 0))} · نامشخص {toFaDigits(String(goals.unknown ?? 0))}</span>
              <span>جمع بودجهٔ واردشده: {amountTotal == null ? '—' : `${fmtInt(amountTotal)} ریال`}</span>
            </div>
            <div className="mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5 text-3xs text-text-muted">
              <span>دیده‌بان {clock(times.watchlist)}</span>
              <span>پرتفوی {clock(times.portfolio)}</span>
              <span>قدرت خرید {clock(times.buyingPower)}</span>
              {bpOk ? <span>قدرت خرید تأییدشده ({bp?.unit ?? 'IRR'})</span>
                : <span className="text-accent-yellow">قدرت خرید نامعلوم — بررسیِ خرید مسدود</span>}
              {bp?.order_write_state === 'ORDER_WRITE_UNVERIFIED' ? (
                <Chip tone="warn" testId="selection-write-unverified">ارسال سفارش تأییدنشده</Chip>
              ) : null}
            </div>
            <div className="mt-0.5 flex flex-wrap items-center gap-1">
              <GhostBtn testId="sarkhati-selection-save" onClick={() => sel.save(times)}
                disabled={!sel.items.length}>ذخیرهٔ فهرست سرخطی</GhostBtn>
              <GhostBtn testId="sarkhati-selection-clear" onClick={sel.clear}
                disabled={!sel.items.length}>پاک کردن</GhostBtn>
              {sel.savedAt ? <span className="text-3xs text-accent-green"
                data-testid="sarkhati-selection-saved">
                ذخیره شد: {new Date(sel.savedAt).toLocaleString('fa-IR', { hour12: false })}
              </span> : null}
              {sel.dirty ? <span className="text-3xs text-accent-yellow"
                data-testid="sarkhati-selection-dirty">تغییرات ذخیره نشده</span> : null}
            </div>
          </div>

          {bpOk && bp?.raw ? (
            <details className="rounded-lg border border-border-c/40 px-2 py-1"
              data-testid="sarkhati-buying-details">
              <summary className="cursor-pointer text-3xs text-text-muted">
                جزئیاتِ قدرت خرید (منبع و اجزای خام)
              </summary>
              <div className="mt-1 grid gap-x-3 gap-y-0.5 text-3xs sm:grid-cols-2">
                {Object.entries(bp.raw).map(([k, v]) => (
                  <span key={k} className="flex justify-between gap-2">
                    <span className="text-text-muted">{k}</span>
                    <span className="num text-text-secondary">{typeof v === 'number' ? fmtInt(v) : '—'}</span>
                  </span>
                ))}
              </div>
              <p className="mt-1 text-3xs text-text-muted">
                فرمول: {bp.formula ?? '—'} · منبع: {bp.source ?? '—'}
              </p>
            </details>
          ) : null}

          <Note label="این فهرست چه چیزی نیست" testId="selection-nots">
            <ul className="flex flex-col gap-0.5">
              <li>انتخاب یا اولویتِ این فهرست، تضمینِ تقدم در صفِ کارگزاری نیست.</li>
              <li>بودجهٔ واردشده بودجهٔ شماست، نه قدرت خریدِ کارگزاری.</li>
              <li>حضور در پرتفوی به‌خودش هدفِ فروش نمی‌سازد و حضور در دیده‌بان هدفِ خرید نمی‌سازد.</li>
              <li>قیمت، حجم و پیش‌بررسیِ مالی در فرمِ سفارش سنجیده می‌شوند؛ live_ready=false است.</li>
            </ul>
          </Note>
        </div>
      </details>
    </section>
  );
}
