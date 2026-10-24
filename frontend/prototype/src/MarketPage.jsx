import React, { useMemo, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import {
  compact,
  marketValue,
  num,
  pct,
  changeClass,
  faDateFromDEven,
  queueState,
  stockFlags,
  timeAgo,
} from './format';

const COLUMNS = [
  { key: 'symbol', label: 'نماد', align: 'start', sortable: true },
  { key: 'p_last', label: 'قیمت', sortable: true },
  { key: 'percent_change', label: 'تغییر', sortable: true },
  { key: 'q_tot_tran', label: 'حجم', sortable: true },
  { key: 'z_tot_tran', label: 'ارزش (ریال)', sortable: true },
  { key: 'buy_q1_vol', label: 'صف خرید', sortable: true },
  { key: 'sell_q1_vol', label: 'صف فروش', sortable: true },
  { key: 'buyer_power', label: 'قدرت خریدار', sortable: true },
  { key: 'state', label: 'وضعیت', sortable: false },
];

const FILTERS = [
  { key: 'all', label: 'همه' },
  { key: 'up', label: 'مثبت' },
  { key: 'down', label: 'منفی' },
  { key: 'queue', label: 'صف خرید' },
];

export function MarketPage({ feed, onOpenSymbol, onRefresh }) {
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [sort, setSort] = useState({ key: 'z_tot_tran', dir: 'desc' });
  const scrollRef = useRef(null);

  const rows = feed.rows || [];
  const fresh = faDateFromDEven(feed.meta?.d_even);

  const stats = useMemo(() => {
    let up = 0;
    let down = 0;
    let queue = 0;
    let value = 0;
    for (const r of rows) {
      const p = Number(r.percent_change);
      if (Number.isFinite(p) && p > 0) up += 1;
      else if (Number.isFinite(p) && p < 0) down += 1;
      if (queueState(r).key === 'buy') queue += 1;
      value += (Number(r.z_tot_tran) || 0) * 1e6;
    }
    return { up, down, queue, value, total: rows.length };
  }, [rows]);

  const visible = useMemo(() => {
    const q = query.trim();
    let out = rows;
    if (q) {
      out = out.filter(
        (r) => r.symbol?.includes(q) || r.name?.includes(q) || String(r.ins_code ?? '').includes(q),
      );
    }
    if (filter === 'up') out = out.filter((r) => Number(r.percent_change) > 0);
    else if (filter === 'down') out = out.filter((r) => Number(r.percent_change) < 0);
    else if (filter === 'queue') out = out.filter((r) => queueState(r).key === 'buy');

    const dir = sort.dir === 'asc' ? 1 : -1;
    out = out.slice().sort((a, b) => {
      if (sort.key === 'symbol') return dir * String(a.symbol || '').localeCompare(String(b.symbol || ''), 'fa');
      const av = Number(a[sort.key]);
      const bv = Number(b[sort.key]);
      const an = Number.isFinite(av) ? av : -Infinity;
      const bn = Number.isFinite(bv) ? bv : -Infinity;
      return dir * (an - bn);
    });
    return out;
  }, [rows, query, filter, sort]);

  const virtualizer = useVirtualizer({
    count: visible.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => (document.documentElement.dataset.density === 'comfortable' ? 38 : 30),
    overscan: 14,
    scrollMargin: 28,
  });

  function toggleSort(key) {
    if (key === 'state') return;
    setSort((s) => ({ key, dir: s.key === key && s.dir === 'desc' ? 'asc' : 'desc' }));
  }

  const loading = feed.status === 'loading' && rows.length === 0;
  const error = feed.status === 'error' && rows.length === 0;

  return (
    <div className="market-page" data-testid="market-page">
      <div className="page-head">
        <div className="page-title">
          <h1>تابلو بازار</h1>
          <p>
            {fresh.fa} · آخرین نشست <b className="mono">{fresh.iso}</b>
            {feed.count ? ` · ${num(feed.count)} ردیف` : ''}
          </p>
        </div>
        <div className="page-tools">
          <input
            className="input"
            style={{ width: 190 }}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="فیلتر نماد / نام…"
            aria-label="فیلتر تابلو"
            data-testid="market-filter"
          />
          <div className="seg" role="tablist" aria-label="فیلتر سریع">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                className={filter === f.key ? 'on' : ''}
                onClick={() => setFilter(f.key)}
                role="tab"
                aria-selected={filter === f.key}
              >
                {f.label}
              </button>
            ))}
          </div>
          <button className="btn" onClick={onRefresh} title="دریافت دوبارهٔ تابلو">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M20 12a8 8 0 10-2.3 5.7M20 5v5h-5" />
            </svg>
            تازه‌سازی
          </button>
        </div>
      </div>

      <div className="kpis">
        <Kpi k="نمادهای مثبت" v={num(stats.up)} s={`${stats.total ? ((stats.up / stats.total) * 100).toFixed(0) : 0}% بازار`} cls="up" />
        <Kpi k="نمادهای منفی" v={num(stats.down)} s={`${stats.total ? ((stats.down / stats.total) * 100).toFixed(0) : 0}% بازار`} cls="down" />
        <Kpi k="صف خرید" v={num(stats.queue)} s="تقاضای بدون عرضه" cls="up" />
        <Kpi k="ارزش معاملات" v={compact(stats.value)} s="ریال · مجموع ردیف‌ها" />
        <Kpi k="ردیف‌های زنده" v={num(feed.liveCount)} s={`از ${num(feed.count || rows.length)} نماد`} />
      </div>

      <div className="table-wrap">
        <div className="table-top">
          <span className="count">
            نمایش <b className="mono">{num(visible.length)}</b> از <b className="mono">{num(rows.length)}</b>
          </span>
          <span className="badge blue">{filter === 'all' ? 'بدون فیلتر' : FILTERS.find((f) => f.key === filter)?.label}</span>
          {feed.status === 'degraded' && <span className="badge amber">پولینگ ناپایدار</span>}
          <span className="spacer" />
          <span className="count">مرتب‌سازی: {COLUMNS.find((c) => c.key === sort.key)?.label} ({sort.dir === 'desc' ? 'نزولی' : 'صعودی'})</span>
        </div>

        {loading && (
          <div className="table-skeleton" data-testid="market-loading">
            {Array.from({ length: 14 }).map((_, i) => (
              <div key={i} className="skeleton line" style={{ opacity: 1 - i * 0.05 }} />
            ))}
          </div>
        )}

        {error && (
          <div className="state">
            <div className="error-box">
              <span>دریافت تابلو ناموفق بود: {feed.error}</span>
              <button className="btn" onClick={onRefresh}>تلاش دوباره</button>
            </div>
            <p>این پیام از مسیر واقعی `/api/market` آمده است؛ دادهٔ جایگزین یا ساختگی نمایش داده نمی‌شود.</p>
          </div>
        )}

        {!loading && !error && (
          <div className="table-scroll" ref={scrollRef} data-testid="market-scroll">
            <div className="grid-head" style={{ position: 'sticky', top: 0 }}>
              {COLUMNS.map((c) => (
                <button
                  key={c.key}
                  className={c.align === 'start' ? 'h-symbol' : ''}
                  onClick={() => c.sortable && toggleSort(c.key)}
                  style={{ cursor: c.sortable ? 'pointer' : 'default' }}
                  aria-label={`مرتب‌سازی ${c.label}`}
                >
                  {c.label}
                  {sort.key === c.key && <span>{sort.dir === 'desc' ? '↓' : '↑'}</span>}
                </button>
              ))}
            </div>
            <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
              {virtualizer.getVirtualItems().map((vi) => {
                const r = visible[vi.index];
                if (!r) return null;
                return (
                  <Row
                    key={r.ins_code || r.symbol}
                    row={r}
                    style={{ transform: `translateY(${vi.start - 28}px)` }}
                    onOpen={() => onOpenSymbol(r.symbol)}
                  />
                );
              })}
            </div>
            {visible.length === 0 && (
              <div className="state" style={{ minHeight: 180 }}>
                <h2>ردیفی با این فیلتر پیدا نشد</h2>
                <p>فیلتر یا عبارت جستجو را تغییر دهید.</p>
              </div>
            )}
          </div>
        )}

        <div className="feed-note">
          <span>منبع: <b>/api/market</b></span>
          <span>meta: <b className="mono">{fresh.iso}</b></span>
          <span>rev: <b className="mono">{feed.rev ?? '—'}</b></span>
          <span>تازگی: <b>{feed.lastAt ? timeAgo(feed.lastAt) : '—'}</b></span>
          <span>پاسخ: <b className="mono">{feed.latencyMs != null ? `${num(feed.latencyMs)}ms` : '—'}</b></span>
          <span>دور پولینگ: <b className="mono">{num(feed.polls)}</b></span>
          {feed.status === 'degraded' && <span style={{ color: 'var(--warn)' }}>آخرین دریافت ناموفق بود؛ آخرین دادهٔ معتبر نمایش داده می‌شود.</span>}
        </div>
      </div>
    </div>
  );
}

function Kpi({ k, v, s, cls = '' }) {
  return (
    <div className="kpi">
      <span className="k">{k}</span>
      <span className={`v num ${cls}`}>{v}</span>
      <span className="s">{s}</span>
    </div>
  );
}

function Row({ row, style, onOpen }) {
  const q = queueState(row);
  const flags = stockFlags(row);
  const chg = Number(row.percent_change);
  const cls = changeClass(chg);
  const buy = Number(row.buy_q1_vol) || 0;
  const sell = Number(row.sell_q1_vol) || 0;
  const total = buy + sell;
  const buyerPct = total > 0 ? Math.round((buy / total) * 100) : null;

  return (
    <div
      className="grid-row"
      style={style}
      onClick={onOpen}
      role="row"
      tabIndex={0}
      onKeyDown={(e) => (e.key === 'Enter' ? onOpen() : null)}
      data-testid="market-row"
      title={`${row.symbol} — ${row.name || ''}`}
    >
      <div className="cell sym">
        <div className="tick">
          <b>{row.symbol}</b>
          <span>{row.name || row.sector_name || '—'}</span>
        </div>
      </div>
      <div className={`cell num ${cls}`}>{num(row.p_last)}</div>
      <div className={`cell num ${cls}`}>{pct(chg)}</div>
      <div className="cell num">{compact(row.q_tot_tran)}</div>
      <div className="cell num">{marketValue(row.z_tot_tran)}</div>
      <div className="cell num up" style={{ opacity: buy > 0 ? 1 : 0.35 }}>
        {buy > 0 ? compact(buy) : '—'}
        <span className="muted" style={{ fontSize: 8.5 }}> · {num(row.buy_q1_px)}</span>
      </div>
      <div className="cell num down" style={{ opacity: sell > 0 ? 1 : 0.35 }}>
        {sell > 0 ? compact(sell) : '—'}
        <span className="muted" style={{ fontSize: 8.5 }}> · {num(row.sell_q1_px)}</span>
      </div>
      <div className="cell num">
        {compact(row.buyer_power)}
        {buyerPct != null && (
          <span className="bar" style={{ color: buyerPct >= 50 ? 'var(--up)' : 'var(--down)' }}>
            <i style={{ width: `${buyerPct}%` }} />
          </span>
        )}
      </div>
      <div className="cell" style={{ display: 'flex', gap: 4, justifyContent: 'center', alignItems: 'center' }}>
        {q.key !== 'none' && <span className={`badge ${q.cls}`}>{q.label}</span>}
        {flags.map((f) => (
          <span key={f.label} className={`badge ${f.cls}`}>{f.label}</span>
        ))}
        {q.key === 'none' && flags.length === 0 && <span className="badge">—</span>}
      </div>
    </div>
  );
}
