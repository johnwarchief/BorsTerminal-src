import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './theme.css';
import { api, mergeDelta } from './api';
import { faDateFromDEven, timeAgo, num } from './format';
import { MarketPage } from './MarketPage';
import { TechnicalPage } from './TechnicalPage';

const DEFAULT_USER = 'admin';
const DEFAULT_PASS = 'bors123';
const SESSION_KEY = 'bors_proto_session';

function parseRoute() {
  const raw = window.location.hash.replace(/^#\/?/, '');
  const [path, query = ''] = raw.split('?');
  const params = new URLSearchParams(query);
  return {
    name: path || 'market',
    symbol: params.get('symbol') || '',
  };
}

function navigate(name, symbol) {
  const q = symbol ? `?symbol=${encodeURIComponent(symbol)}` : '';
  window.location.hash = `#/${name}${q}`;
}

function useMarketFeed(enabled) {
  const [state, setState] = useState({
    status: 'idle',
    rows: [],
    meta: null,
    rev: null,
    count: 0,
    liveCount: 0,
    error: null,
    lastAt: null,
    latencyMs: null,
    polls: 0,
  });
  const revRef = useRef(-1);
  const rowsRef = useRef([]);

  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;
    let timer = null;

    async function full() {
      const t0 = performance.now();
      try {
        const feed = await api.market();
        if (cancelled) return;
        const rows = Array.isArray(feed?.data) ? feed.data : [];
        rowsRef.current = rows;
        revRef.current = typeof feed?.rev === 'number' ? feed.rev : -1;
        setState((s) => ({
          ...s,
          status: 'ready',
          rows,
          meta: feed?.meta ?? null,
          rev: feed?.rev ?? null,
          count: feed?.count ?? rows.length,
          liveCount: feed?.live_count ?? 0,
          error: null,
          lastAt: Date.now(),
          latencyMs: Math.round(performance.now() - t0),
        }));
      } catch (e) {
        if (cancelled) return;
        setState((s) => ({ ...s, status: s.rows.length ? 'degraded' : 'error', error: String(e?.message || e) }));
      }
    }

    async function tick() {
      if (document.visibilityState !== 'visible') return;
      if (revRef.current < 0) return full();
      try {
        const d = await api.delta(revRef.current);
        if (cancelled) return;
        if (d?.status === 'unchanged') {
          setState((s) => ({ ...s, status: 'ready', lastAt: Date.now(), polls: s.polls + 1 }));
          return;
        }
        if (d?.status === 'delta') {
          const merged = mergeDelta(rowsRef.current, d.rows || []);
          if (!merged || (d.count != null && d.count !== merged.length)) {
            await full();
            return;
          }
          rowsRef.current = merged;
          revRef.current = d.rev;
          setState((s) => ({
            ...s,
            status: 'ready',
            rows: merged,
            rev: d.rev,
            meta: d.meta ?? s.meta,
            count: d.count ?? merged.length,
            liveCount: d.live_count ?? s.liveCount,
            lastAt: Date.now(),
            polls: s.polls + 1,
          }));
          return;
        }
        await full();
      } catch {
        if (!cancelled) setState((s) => ({ ...s, status: 'degraded' }));
      }
    }

    full();
    timer = window.setInterval(tick, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [enabled]);

  return { ...state, refresh: () => setState((s) => ({ ...s, status: 'loading' })) };
}

function Login({ onLogin }) {
  const [user, setUser] = useState(DEFAULT_USER);
  const [pass, setPass] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setBusy(true);
    await new Promise((r) => setTimeout(r, 120));
    const savedUser = localStorage.getItem('bors_proto_user') || DEFAULT_USER;
    const savedPass = localStorage.getItem('bors_proto_pass') || DEFAULT_PASS;
    if (user.trim() === savedUser && pass === savedPass) {
      sessionStorage.setItem(SESSION_KEY, '1');
      onLogin();
    } else {
      setError('نام کاربری یا رمز عبور نادرست است.');
      setPass('');
    }
    setBusy(false);
  }

  return (
    <div className="login" dir="rtl">
      <form className="login-card" onSubmit={submit} data-testid="proto-login">
        <div className="login-brand">
          <div className="brand-mark">ب</div>
          <div>
            <b>بورس‌ترمینال</b>
            <span>BorsTerminal · M1 Workstation</span>
          </div>
        </div>
        <h1>ورود به ایستگاه معاملاتی</h1>
        <p className="sub">احراز هویت محلی؛ دادهٔ بازار از همین دستگاه خوانده می‌شود.</p>
        <div className="field">
          <label htmlFor="u">نام کاربری</label>
          <input id="u" value={user} onChange={(e) => setUser(e.target.value)} autoComplete="username" />
        </div>
        <div className="field">
          <label htmlFor="p">رمز عبور</label>
          <input
            id="p"
            type="password"
            value={pass}
            onChange={(e) => setPass(e.target.value)}
            autoComplete="current-password"
            autoFocus
          />
        </div>
        <p className="err">{error}</p>
        <button className="btn-login" type="submit" disabled={busy}>
          {busy ? 'در حال بررسی…' : 'ورود'}
        </button>
        <div className="hint">
          <span>نمونهٔ آزمایشی محلی</span>
          <span className="mono">admin / bors123</span>
        </div>
      </form>
    </div>
  );
}

const ICONS = {
  market: 'M3 3h18v18H3zM7 15l3-4 3 3 4-6',
  technical: 'M4 19V5M4 19h16M7 14l3-5 3 3 4-7',
  fundamental: 'M5 5h14v14H5zM9 9h6M9 13h6M9 17h3',
  status: 'M4 12h4l2-5 4 10 2-5h4',
  portfolio: 'M4 7h16v12H4zM8 7V5h8v2M4 11h16',
  sarkhati: 'M12 3v18M5 8l7-5 7 5M7 12h10M9 16h6',
  watch: 'M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12zM12 9a3 3 0 100 6 3 3 0 000-6z',
  chevron: 'M9 6l6 6-6 6',
  search: 'M11 4a7 7 0 105.3 11.7L21 20M11 4a7 7 0 010 14',
  sun: 'M12 4v2M12 18v2M4 12h2M18 12h2M6 6l1.5 1.5M16.5 16.5L18 18M18 6l-1.5 1.5M7.5 16.5L6 18M12 8a4 4 0 100 8 4 4 0 000-8z',
  moon: 'M20 14.5A8 8 0 119.5 4a6.5 6.5 0 0010.5 10.5z',
  density: 'M4 6h16M4 10h16M4 14h16M4 18h16',
  refresh: 'M20 12a8 8 0 10-2.3 5.7M20 5v5h-5',
  logout: 'M15 12H4M9 7l-5 5 5 5M14 5h5v14h-5',
  alert: 'M12 4l9 16H3zM12 9v5M12 17h.01',
};

function Icon({ name, size = 15 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={ICONS[name] || ICONS.market} />
    </svg>
  );
}

const NAV = [
  { group: 'پایش بازار', items: [
    { key: 'market', label: 'تابلو بازار', icon: 'market' },
    { key: 'technical', label: 'تحلیل تکنیکال', icon: 'technical' },
    { key: 'market-status', label: 'وضعیت بازار', icon: 'status', soon: true },
  ] },
  { group: 'تحلیل و تصمیم', items: [
    { key: 'fundamental', label: 'بنیادی و FTS', icon: 'fundamental', soon: true },
    { key: 'strategy-tree', label: 'درخت استراتژی', icon: 'sarkhati', soon: true },
  ] },
  { group: 'سرمایه', items: [
    { key: 'portfolio', label: 'مدیریت پرتفوی', icon: 'portfolio', soon: true },
    { key: 'sarkhati', label: 'سرخطی', icon: 'sarkhati', soon: true },
    { key: 'watch', label: 'دیده‌بان', icon: 'watch', soon: true },
  ] },
];

function Topbar({ route, feed, theme, onTheme, density, onDensity, onLogout, onOpenSymbol }) {
  const [query, setQuery] = useState('');
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const fresh = faDateFromDEven(feed.meta?.d_even);
  const connection =
    feed.status === 'ready' ? 'ok' : feed.status === 'degraded' ? 'warn' : feed.status === 'error' ? 'bad' : '';
  const connectionLabel =
    feed.status === 'ready' ? 'متصل' : feed.status === 'degraded' ? 'اتصال ناپایدار' : feed.status === 'error' ? 'قطع ارتباط' : 'در حال اتصال';

  function submitSearch(e) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    const hit = feed.rows.find((r) => r.symbol === q || r.symbol?.includes(q) || r.name?.includes(q));
    if (hit) {
      onOpenSymbol(hit.symbol);
      setQuery('');
    }
  }

  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-mark">ب</div>
        <div className="brand-text">
          <b>بورس‌ترمینال</b>
          <span>FTS Workstation · M1</span>
        </div>
      </div>

      <form className="top-search" onSubmit={submitSearch}>
        <Icon name="search" size={14} />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="جستجوی سریع نماد… (Enter برای تحلیل)"
          aria-label="جستجوی نماد"
          data-testid="global-search"
        />
        <span className="kbd">Ctrl K</span>
      </form>

      <div className="top-actions">
        <span className={`chip ${connection}`} title="وضعیت اتصال به موتور محلی">
          <span className="dot" />
          {connectionLabel}
        </span>
        <span className="chip" title="تاریخ آخرین نشست داده">
          نشست <b className="mono">{fresh.iso}</b>
        </span>
        <span className="chip" title="تازگی داده در کلاینت">
          {feed.lastAt ? timeAgo(feed.lastAt) : '—'}
        </span>
        <span className="chip mono" title="زمان پاسخ آخرین دریافت تابلو">
          {feed.latencyMs != null ? `${num(feed.latencyMs)}ms` : '—'}
        </span>
        <span className="chip mono" title="ساعت محلی">
          {now.toLocaleTimeString('fa-IR', { hour12: false })}
        </span>
        <button className="icon-btn" title={theme === 'dark' ? 'تم روشن' : 'تم تاریک'} onClick={onTheme} aria-label="تغییر تم">
          <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
        </button>
        <button
          className="icon-btn"
          title={density === 'compact' ? 'تراکم راحت' : 'تراکم فشرده'}
          onClick={onDensity}
          aria-label="تغییر تراکم"
        >
          <Icon name="density" />
        </button>
        <button className="icon-btn" title="خروج" onClick={onLogout} aria-label="خروج">
          <Icon name="logout" />
        </button>
      </div>
    </header>
  );
}

function Rail({ route, collapsed, onToggle, onSoon }) {
  return (
    <aside className={`rail ${collapsed ? 'collapsed' : ''}`}>
      <button className="icon-btn rail-toggle" onClick={onToggle} title={collapsed ? 'باز کردن نوار' : 'جمع کردن نوار'} aria-label="نوار کناری">
        <span style={{ transform: collapsed ? 'rotate(180deg)' : 'none', display: 'grid' }}>
          <Icon name="chevron" size={13} />
        </span>
      </button>
      <div className="rail-scroll">
        {NAV.map((sec) => (
          <div key={sec.group}>
            <div className="rail-group-title">{sec.group}</div>
            {sec.items.map((item) => (
              <button
                key={item.key}
                className={`nav-item ${route.name === item.key ? 'active' : ''}`}
                title={collapsed ? item.label : undefined}
                onClick={() => (item.soon ? onSoon(item.label) : navigate(item.key))}
                data-testid={`proto-nav-${item.key}`}
              >
                <span className="ico"><Icon name={item.icon} /></span>
                <span className="label">{item.label}</span>
                {item.soon && !collapsed && <span className="badge" style={{ marginInlineStart: 'auto' }}>M1</span>}
              </button>
            ))}
          </div>
        ))}
      </div>
      <div className="rail-foot">
        <span>دادهٔ محلی · بدون ارسال بیرونی</span>
        <span className="mono">API 127.0.0.1</span>
        <span className="mono">{num(6018)} نماد در بانک</span>
      </div>
    </aside>
  );
}

function Placeholder({ label, onBack }) {
  return (
    <div className="state">
      <h2>{label}</h2>
      <p>
        این بخش در نمونهٔ M1 هنوز منتقل نشده است. نمونهٔ فعلی روی دو صفحهٔ پرترافیک «تابلو بازار» و
        «تحلیل تکنیکال» تمرکز دارد تا اثر پوسته جدا از مسیر داده سنجیده شود.
      </p>
      <button className="btn primary" onClick={onBack}>بازگشت به تابلو بازار</button>
    </div>
  );
}

function App() {
  const [authed, setAuthed] = useState(() => sessionStorage.getItem(SESSION_KEY) === '1');
  const [route, setRoute] = useState(parseRoute);
  const [theme, setTheme] = useState(() => localStorage.getItem('bors_proto_theme') || 'dark');
  const [density, setDensity] = useState(() => localStorage.getItem('bors_proto_density') || 'compact');
  const [collapsed, setCollapsed] = useState(false);
  const [toast, setToast] = useState('');
  const feed = useMarketFeed(authed);

  useEffect(() => {
    const onHash = () => setRoute(parseRoute());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('bors_proto_theme', theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.dataset.density = density;
    localStorage.setItem('bors_proto_density', density);
  }, [density]);

  useEffect(() => {
    if (!toast) return undefined;
    const t = setTimeout(() => setToast(''), 2600);
    return () => clearTimeout(t);
  }, [toast]);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        document.querySelector('[data-testid="global-search"]')?.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  if (!authed) {
    return <Login onLogin={() => setAuthed(true)} />;
  }

  const selectedSymbol = route.symbol || '';
  const openSymbol = (symbol) => navigate('technical', symbol);

  return (
    <div className="app" data-testid="proto-shell">
      <Topbar
        route={route}
        feed={feed}
        theme={theme}
        onTheme={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
        density={density}
        onDensity={() => setDensity((d) => (d === 'compact' ? 'comfortable' : 'compact'))}
        onLogout={() => {
          sessionStorage.removeItem(SESSION_KEY);
          setAuthed(false);
        }}
        onOpenSymbol={openSymbol}
      />
      <div className="shell-body">
        <Rail
          route={route}
          collapsed={collapsed}
          onToggle={() => setCollapsed((c) => !c)}
          onSoon={(label) => setToast(`${label}: در M1 منتقل نشده است`)}
        />
        <main className="main">
          {route.name === 'market' && (
            <MarketPage feed={feed} onOpenSymbol={openSymbol} onRefresh={() => feed.refresh()} />
          )}
          {route.name === 'technical' && (
            <TechnicalPage feed={feed} symbol={selectedSymbol} onOpenSymbol={openSymbol} />
          )}
          {!['market', 'technical'].includes(route.name) && (
            <Placeholder label="این بخش در نمونهٔ M1 نیست" onBack={() => navigate('market')} />
          )}
        </main>
      </div>
      {toast && (
        <div
          role="status"
          style={{
            position: 'fixed', bottom: 16, left: 16, zIndex: 50,
            background: 'var(--surface-3)', border: '1px solid var(--border-2)',
            borderRadius: 8, padding: '7px 11px', fontSize: 10.5, color: 'var(--text-2)',
            boxShadow: 'var(--shadow)',
          }}
        >
          {toast}
        </div>
      )}
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
