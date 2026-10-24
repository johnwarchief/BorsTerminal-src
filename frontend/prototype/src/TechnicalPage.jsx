import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Chart } from './Chart';
import { api } from './api';
import {
  compact,
  marketValue,
  num,
  pct,
  changeClass,
  faDateFromDEven,
  queueState,
  stockFlags,
} from './format';

function round4(v) {
  return Math.round(v * 1e4) / 1e4;
}

function toBars(chart) {
  const volByTime = new Map((chart?.volumes || []).map((v) => [v.time, Number(v.value) || 0]));
  return (chart?.candles || [])
    .map((c) => ({
      time: c.time,
      timestamp: Date.parse(`${c.time}T00:00:00Z`),
      open: Number(c.open),
      high: Number(c.high),
      low: Number(c.low),
      close: Number(c.close),
      volume: volByTime.get(c.time) || 0,
    }))
    .filter((b) => Number.isFinite(b.timestamp) && [b.open, b.high, b.low, b.close].every((v) => Number.isFinite(v) && v > 0))
    .sort((a, b) => a.timestamp - b.timestamp);
}

function applyFactors(bars, factors, mode) {
  if (mode === 'none') return bars;
  const byDate = new Map();
  for (const f of factors || []) {
    const day = String(f?.time ?? '').slice(0, 10);
    const v = Number(f?.factor);
    if (day && Number.isFinite(v) && v > 0) byDate.set(day, v);
  }
  return bars.map((b) => {
    const day = new Date(b.timestamp).toISOString().slice(0, 10);
    const k = byDate.get(day) ?? 1;
    return { ...b, open: round4(b.open * k), high: round4(b.high * k), low: round4(b.low * k), close: round4(b.close * k) };
  });
}

function isoWeekKey(ts) {
  const d = new Date(ts);
  const tmp = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  const day = tmp.getUTCDay() || 7;
  tmp.setUTCDate(tmp.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(tmp.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((tmp - yearStart) / 86400000 + 1) / 7);
  return `${tmp.getUTCFullYear()}-W${String(week).padStart(2, '0')}`;
}

function aggregate(bars, timeframe) {
  if (timeframe === 'day' || bars.length === 0) return bars;
  const out = [];
  let cur = null;
  let key = null;
  for (const b of bars) {
    const d = new Date(b.timestamp);
    const k = timeframe === 'month' ? `${d.getUTCFullYear()}-${d.getUTCMonth()}` : isoWeekKey(b.timestamp);
    if (k !== key) {
      if (cur) out.push(cur);
      key = k;
      cur = { ...b };
    } else {
      cur.high = Math.max(cur.high, b.high);
      cur.low = Math.min(cur.low, b.low);
      cur.close = b.close;
      cur.volume += b.volume;
      cur.timestamp = b.timestamp;
    }
  }
  if (cur) out.push(cur);
  return out;
}

const EMPTY_INDICATORS = { ma: true, boll: false, rsi: false };

export function TechnicalPage({ feed, symbol, onOpenSymbol }) {
  const available = feed.rows || [];
  const initial = symbol || (available.some((r) => r.symbol === 'فولاد') ? 'فولاد' : available[0]?.symbol || 'فولاد');
  const [activeSymbol, setActiveSymbol] = useState(initial);
  const [input, setInput] = useState(initial);
  const [chart, setChart] = useState(null);
  const [row, setRow] = useState(null);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState('');
  const [source, setSource] = useState('');
  const [timeframe, setTimeframe] = useState('day');
  const [adjustMode, setAdjustMode] = useState('combined');
  const [chartType, setChartType] = useState('candle');
  const [indicators, setIndicators] = useState(EMPTY_INDICATORS);
  const [drawTool, setDrawTool] = useState(null);
  const [drawError, setDrawError] = useState('');
  const [nonce, setNonce] = useState(0);
  const reqRef = useRef(0);

  useEffect(() => {
    setInput(activeSymbol);
  }, [activeSymbol]);

  useEffect(() => {
    if (symbol && symbol !== activeSymbol) setActiveSymbol(symbol);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol]);

  useEffect(() => {
    const id = ++reqRef.current;
    let cancelled = false;
    setStatus('loading');
    setError('');
    (async () => {
      let data = null;
      let src = 'chart';
      try {
        data = await api.chart(activeSymbol);
        if (!data || data.status === 'error' || !(data.candles?.length > 0)) {
          throw new Error(data?.message || 'پاسخ چارت داده‌ای ندارد');
        }
      } catch (e) {
        try {
          data = await api.history(activeSymbol);
          src = 'history';
          if (!data || !(data.candles?.length > 0)) throw new Error('تاریخچهٔ محلی هم خالی است');
        } catch (e2) {
          if (cancelled || id !== reqRef.current) return;
          setStatus('error');
          setError(`${e?.message || e} · مسیر جایگزین: ${e2?.message || e2}`);
          return;
        }
      }
      if (cancelled || id !== reqRef.current) return;
      setChart(data);
      setSource(src);
      setStatus('ready');
      if (src === 'history') setAdjustMode('none');
      try {
        const r = await api.row(activeSymbol);
        if (!cancelled && id === reqRef.current) setRow(r?.row || null);
      } catch {
        if (!cancelled && id === reqRef.current) {
          setRow(available.find((x) => x.symbol === activeSymbol) || null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSymbol, nonce]);

  const bars = useMemo(() => {
    const raw = toBars(chart);
    return aggregate(applyFactors(raw, chart?.factors || [], adjustMode), timeframe);
  }, [chart, adjustMode, timeframe]);

  const rowFromFeed = row || available.find((r) => r.symbol === activeSymbol) || null;
  const last = bars[bars.length - 1];
  const prev = bars[bars.length - 2];
  const changePct = last && prev ? ((last.close - prev.close) / prev.close) * 100 : Number(rowFromFeed?.percent_change);
  const pricePrecision = last && last.close < 10 ? 2 : last && last.close < 1000 ? 1 : 0;
  const capability = chart?.adjustCapability || null;
  const combinedAvailable = capability ? capability.combined_available === true : (chart?.factors || []).length > 0;
  const fresh = faDateFromDEven(feed.meta?.d_even);
  const chartLastDate = bars[bars.length - 1]?.time || '—';
  const q = queueState(rowFromFeed || {});
  const flags = stockFlags(rowFromFeed || {});

  function submitSymbol(e) {
    e.preventDefault();
    const s = input.trim();
    if (!s) return;
    setActiveSymbol(s);
    onOpenSymbol(s);
  }

  function pickTool(name) {
    setDrawError('');
    setDrawTool({ name, nonce: Date.now() });
  }

  const retailBuy = Number(rowFromFeed?.retail_buy_pct);
  const legalBuy = Number(rowFromFeed?.legal_buy_pct);
  const retailSell = Number(rowFromFeed?.retail_sell_pct);
  const legalSell = Number(rowFromFeed?.legal_sell_pct);
  const hasSplit = [retailBuy, legalBuy, retailSell, legalSell].every((v) => Number.isFinite(v));

  return (
    <div className="tech-page" data-testid="technical-page">
      <div className="page-head">
        <div className="page-title">
          <h1>تحلیل تکنیکال</h1>
          <p>
            {activeSymbol} · {source === 'history' ? 'تاریخچهٔ محلی' : 'کندل TSETMC'} · نشست{' '}
            <b className="mono">{fresh.iso}</b>
          </p>
        </div>
        <div className="page-tools">
          <form onSubmit={submitSymbol} style={{ display: 'flex', gap: 6 }}>
            <input
              className="input"
              style={{ width: 150 }}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="نماد…"
              list="proto-symbols"
              aria-label="نماد تحلیل"
              data-testid="symbol-input"
            />
            <datalist id="proto-symbols">
              {available.slice(0, 400).map((r) => (
                <option key={r.ins_code || r.symbol} value={r.symbol}>{r.name || ''}</option>
              ))}
            </datalist>
            <button className="btn primary" type="submit">بازکردن</button>
          </form>
          <button className="btn" onClick={() => setNonce((n) => n + 1)} title="دریافت دوبارهٔ دادهٔ چارت">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M20 12a8 8 0 10-2.3 5.7M20 5v5h-5" />
            </svg>
            تازه‌سازی
          </button>
        </div>
      </div>

      <div className="tech-toolbar">
        <div className="seg" role="tablist" aria-label="تایم‌فریم">
          {[['day', 'روزانه'], ['week', 'هفتگی'], ['month', 'ماهانه']].map(([k, l]) => (
            <button key={k} className={timeframe === k ? 'on' : ''} onClick={() => setTimeframe(k)}>{l}</button>
          ))}
        </div>
        <div className="sep" />
        <div className="seg" role="tablist" aria-label="مبنای قیمت">
          <button className={adjustMode === 'combined' ? 'on' : ''} onClick={() => setAdjustMode('combined')} disabled={!combinedAvailable}>
            تعدیل‌شده
          </button>
          <button className={adjustMode === 'none' ? 'on' : ''} onClick={() => setAdjustMode('none')}>خام</button>
        </div>
        <div className="sep" />
        <div className="seg" role="tablist" aria-label="نوع نمایش">
          <button className={chartType === 'candle' ? 'on' : ''} onClick={() => setChartType('candle')}>کندل</button>
          <button className={chartType === 'area' ? 'on' : ''} onClick={() => setChartType('area')}>ناحیه‌ای</button>
        </div>
        <div className="sep" />
        {[['ma', 'MA'], ['boll', 'BOLL'], ['rsi', 'RSI']].map(([k, l]) => (
          <button
            key={k}
            className="btn"
            aria-pressed={indicators[k]}
            onClick={() => setIndicators((s) => ({ ...s, [k]: !s[k] }))}
            style={indicators[k] ? { borderColor: 'var(--accent)', color: 'var(--accent)', background: 'var(--accent-soft)' } : undefined}
          >
            {l}
          </button>
        ))}
        <div className="sep" />
        {[['straightLine', 'خط روند'], ['horizontalStraightLine', 'خط افقی'], ['fibonacciLine', 'فیبوناچی']].map(([name, label]) => (
          <button key={name} className="btn" onClick={() => pickTool(name)}>{label}</button>
        ))}
        {drawTool && <span className="badge blue">ابزار فعال: {drawTool.name}</span>}
        {drawError && <span className="badge red">{drawError}</span>}
        <span style={{ marginInlineStart: 'auto' }} className="muted">
          {combinedAvailable ? 'تعدیل سرور در دسترس است' : 'رویداد تعدیل برای این نماد در دسترس نیست'}
        </span>
      </div>

      <div className="tech-grid">
        <div className="chart-card">
          <div className="chart-head">
            <span className="sym">{activeSymbol}</span>
            <span className="name">{rowFromFeed?.name || ''}</span>
            <span className={`px num ${changeClass(changePct)}`}>{last ? num(last.close, pricePrecision) : '—'}</span>
            <span className={`chg num ${changeClass(changePct)}`}>{pct(changePct)}</span>
            <div className="ohlc">
              <span className={`badge ${chartLastDate !== fresh.iso ? 'amber' : ''}`} title="تاریخ آخرین کندل و تاریخ تابلو">کندل <b className="mono">{chartLastDate}</b> · تابلو <b className="mono">{fresh.iso}</b></span>
              <span>O <b className="num">{last ? num(last.open, pricePrecision) : '—'}</b></span>
              <span>H <b className="num">{last ? num(last.high, pricePrecision) : '—'}</b></span>
              <span>L <b className="num">{last ? num(last.low, pricePrecision) : '—'}</b></span>
              <span>C <b className="num">{last ? num(last.close, pricePrecision) : '—'}</b></span>
              <span>V <b className="num">{last ? compact(last.volume) : '—'}</b></span>
              <span>کندل <b className="num">{num(bars.length)}</b></span>
            </div>
          </div>

          {status === 'loading' && (
            <div className="state" data-testid="chart-loading">
              <div className="spinner" />
              <h2>در حال دریافت کندل‌ها</h2>
              <p>منبع: <span className="mono">/api/chart/{activeSymbol}</span> — دادهٔ چارت از بانک محلی و مسیر رسمی نماد خوانده می‌شود.</p>
            </div>
          )}

          {status === 'error' && (
            <div className="state">
              <div className="error-box">
                <span>چارت بارگذاری نشد: {error}</span>
                <button className="btn" onClick={() => setNonce((n) => n + 1)}>تلاش دوباره</button>
              </div>
              <p>هیچ دادهٔ جایگزین ساختگی رسم نمی‌شود.</p>
            </div>
          )}

          {status === 'ready' && bars.length > 0 && (
            <Chart
              candles={bars}
              theme={document.documentElement.dataset.theme || 'dark'}
              symbol={activeSymbol}
              timeframe={timeframe}
              chartType={chartType}
              indicators={indicators}
              drawTool={drawTool}
              onDrawError={setDrawError}
            />
          )}

          {status === 'ready' && bars.length === 0 && (
            <div className="state">
              <h2>کندلی برای این نماد برنگشت</h2>
              <p>پاسخ سرور معتبر بود اما سری قیمت خالی است؛ این را «بدون داده» می‌خوانیم، نه صفر.</p>
            </div>
          )}
        </div>

        <div className="right-col">
          <section className="panel">
            <h3>وضعیت این نماد</h3>
            <div className="kv"><span className="k">قیمت تابلو ({fresh.iso})</span><span className="v num">{num(rowFromFeed?.p_last)}</span></div>
            <div className="kv"><span className="k">تغییر روز</span><span className={`v num ${changeClass(rowFromFeed?.percent_change)}`}>{pct(rowFromFeed?.percent_change)}</span></div>
            <div className="kv"><span className="k">حجم</span><span className="v num">{compact(rowFromFeed?.q_tot_tran)}</span></div>
            <div className="kv"><span className="k">ارزش</span><span className="v num">{marketValue(rowFromFeed?.z_tot_tran)}</span></div>
            <div className="kv"><span className="k">وضعیت صف</span><span className="v">{q.key === 'none' ? '—' : <span className={`badge ${q.cls}`}>{q.label}</span>}</span></div>
            <div className="kv"><span className="k">قدرت خریدار</span><span className="v num">{compact(rowFromFeed?.buyer_power)}</span></div>
            <div className="kv"><span className="k">سکتور</span><span className="v" style={{ fontSize: 10 }}>{rowFromFeed?.sector_name || '—'}</span></div>
            {flags.length > 0 && (
              <div style={{ display: 'flex', gap: 4, marginTop: 6 }}>
                {flags.map((f) => <span key={f.label} className={`badge ${f.cls}`}>{f.label}</span>)}
              </div>
            )}
          </section>

          <section className="panel">
            <h3>عمق صف</h3>
            <div className="kv"><span className="k">خرید — قیمت</span><span className="v num">{num(rowFromFeed?.buy_q1_px)}</span></div>
            <div className="kv"><span className="k">خرید — حجم</span><span className="v num up">{compact(rowFromFeed?.buy_q1_vol)}</span></div>
            <div className="kv"><span className="k">فروش — قیمت</span><span className="v num">{num(rowFromFeed?.sell_q1_px)}</span></div>
            <div className="kv"><span className="k">فروش — حجم</span><span className="v num down">{compact(rowFromFeed?.sell_q1_vol)}</span></div>
          </section>

          <section className="panel">
            <h3>حقیقی / حقوقی (ارزشی)</h3>
            {hasSplit ? (
              <>
                <div className="legend"><span>خرید حقیقی {num(retailBuy, 1)}%</span><span>خرید حقوقی {num(legalBuy, 1)}%</span></div>
                <div className="split-bar">
                  <i style={{ width: `${Math.max(0, Math.min(100, retailBuy))}%`, background: 'var(--up)' }} />
                  <i style={{ width: `${Math.max(0, Math.min(100, legalBuy))}%`, background: 'var(--accent)' }} />
                </div>
                <div className="legend"><span>فروش حقیقی {num(retailSell, 1)}%</span><span>فروش حقوقی {num(legalSell, 1)}%</span></div>
                <div className="split-bar">
                  <i style={{ width: `${Math.max(0, Math.min(100, retailSell))}%`, background: 'var(--down)' }} />
                  <i style={{ width: `${Math.max(0, Math.min(100, legalSell))}%`, background: 'var(--warn)' }} />
                </div>
                <div className="legend" style={{ marginTop: 4 }}>
                  <span>مبنای: {rowFromFeed?.pct_basis || 'نامشخص'}</span>
                  <span>{rowFromFeed?.pct_is_current === 1 ? 'همین نشست' : 'نشست پیشین'}</span>
                </div>
              </>
            ) : (
              <p className="muted" style={{ margin: 0, fontSize: 10 }}>دادهٔ ارزشی حقیقی/حقوقی برای این نماد در دسترس نیست.</p>
            )}
          </section>

          <section className="panel">
            <h3>مسیر داده</h3>
            <div className="kv"><span className="k">منبع کندل</span><span className="v mono">{source}</span></div>
            <div className="kv"><span className="k">ضرایب تعدیل</span><span className="v num">{num((chart?.factors || []).length)}</span></div>
            <div className="kv"><span className="k">رویداد شرکتی</span><span className="v num">{num((chart?.corporateEvents || []).length)}</span></div>
            <div className="kv"><span className="k">منبع تعدیل</span><span className="v mono" style={{ fontSize: 9 }}>{capability?.source || chart?.adjustSource || '—'}</span></div>
            <div className="kv"><span className="k">آخرین کندل</span><span className="v mono">{chartLastDate}</span></div>
            <div className="kv"><span className="k">تازگی تابلو</span><span className="v">{feed.lastAt ? `${Math.round((Date.now() - feed.lastAt) / 1000)}s` : '—'}</span></div>
            {!combinedAvailable && adjustMode === 'combined' && (
              <p className="muted" style={{ margin: '6px 0 0', fontSize: 9.5, color: 'var(--warn)' }}>
                تعدیل برای این نماد تأیید نشده؛ محور را «خام» بخوانید.
              </p>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
