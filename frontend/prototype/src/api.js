const JSON_HEADERS = { Accept: 'application/json' };

async function getJSON(path, { timeout = 60000 } = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeout);
  try {
    const res = await fetch(path, { headers: JSON_HEADERS, signal: ctrl.signal, cache: 'no-store' });
    const text = await res.text();
    let body = null;
    try {
      body = text ? JSON.parse(text) : null;
    } catch {
      body = null;
    }
    if (!res.ok) {
      const msg = body?.message || body?.detail || `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return body;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  version: () => getJSON('/api/update/version', { timeout: 15000 }),
  market: () => getJSON('/api/market', { timeout: 120000 }),
  delta: (rev) => getJSON(`/api/market/delta?since=${encodeURIComponent(rev)}`, { timeout: 30000 }),
  row: (symbol) => getJSON(`/api/market/row?symbol=${encodeURIComponent(symbol)}`, { timeout: 30000 }),
  chart: (symbol) => getJSON(`/api/chart/${encodeURIComponent(symbol)}`, { timeout: 120000 }),
  history: (symbol) => getJSON(`/api/history/${encodeURIComponent(symbol)}`, { timeout: 60000 }),
};

export function mergeDelta(rows, deltaRows) {
  if (!Array.isArray(deltaRows) || deltaRows.length === 0) return rows;
  const byCode = new Map(rows.map((r, i) => [r.ins_code ?? `#${i}`, i]));
  const next = rows.slice();
  for (const r of deltaRows) {
    const key = r.ins_code;
    if (!key) return null;
    const at = byCode.get(key);
    if (at === undefined) {
      byCode.set(key, next.length);
      next.push(r);
    } else {
      next[at] = r;
    }
  }
  return next;
}
