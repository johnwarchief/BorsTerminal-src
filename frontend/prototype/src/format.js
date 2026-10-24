const nf0 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 });
const nf2 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });

export function num(v, digits = 0) {
  if (v === null || v === undefined || !Number.isFinite(Number(v))) return '—';
  const n = Number(v);
  return digits === 0 ? nf0.format(n) : digits === 1 ? nf1.format(n) : nf2.format(n);
}

const UNITS = [
  [1e12, 'هزار میلیارد'],
  [1e9, 'میلیارد'],
  [1e6, 'میلیون'],
  [1e3, 'هزار'],
];

export function compact(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return '—';
  const abs = Math.abs(n);
  for (const [size, label] of UNITS) {
    if (abs >= size) {
      const scaled = n / size;
      const digits = Math.abs(scaled) >= 100 ? 0 : Math.abs(scaled) >= 10 ? 1 : 2;
      return `${num(scaled, digits)} ${label}`;
    }
  }
  return num(n);
}

export function compactPrice(v) {
  return compact(v);
}

/** /api/market z_tot_tran is in million Rial (TSETMC board column). */
export function marketValue(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return '—';
  return compact(n * 1e6);
}

export function pct(v, withSign = true) {
  const n = Number(v);
  if (!Number.isFinite(n)) return '—';
  const sign = withSign && n > 0 ? '+' : '';
  return `${sign}${nf2.format(n)}%`;
}

export function changeClass(v) {
  const n = Number(v);
  if (!Number.isFinite(n) || n === 0) return '';
  return n > 0 ? 'up' : 'down';
}

export function faDateFromDEven(dEven) {
  const raw = String(dEven ?? '');
  if (!/^\d{8}$/.test(raw)) return { iso: raw || '—', fa: '—' };
  const iso = `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`;
  try {
    const fa = new Intl.DateTimeFormat('fa-IR-u-ca-persian', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(new Date(`${iso}T00:00:00Z`));
    return { iso, fa };
  } catch {
    return { iso, fa: iso };
  }
}

export function timeAgo(ts) {
  if (!ts) return '—';
  const s = Math.max(0, Math.round((Date.now() - ts) / 1000));
  if (s < 5) return 'همین حالا';
  if (s < 60) return `${s} ثانیه پیش`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m} دقیقه پیش`;
  const h = Math.round(m / 60);
  return `${h} ساعت پیش`;
}

export function queueState(row) {
  const buy = Number(row?.buy_q1_vol ?? 0);
  const sell = Number(row?.sell_q1_vol ?? 0);
  if (buy > 0 && sell <= 0) return { key: 'buy', label: 'صف خرید', cls: 'green' };
  if (sell > 0 && buy <= 0) return { key: 'sell', label: 'صف فروش', cls: 'red' };
  if (buy > 0 && sell > 0) return { key: 'both', label: 'دو طرف', cls: 'amber' };
  return { key: 'none', label: '—', cls: '' };
}

export function stockFlags(row) {
  const out = [];
  if (row?.f_susp) out.push({ label: 'متوقف', cls: 'amber' });
  if (row?.f_clock) out.push({ label: 'ساعت', cls: 'blue' });
  if (row?.f_smart) out.push({ label: 'هوشمند', cls: 'green' });
  if (row?.f_legal) out.push({ label: 'حقوقی', cls: 'blue' });
  if (row?.is_live === false) out.push({ label: 'کهنه', cls: '' });
  return out.slice(0, 2);
}
