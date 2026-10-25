// RA365 Round 32B — read-only live capture for the three reference-internal
// weekly keys (assets 8, 803, 804; week 2017-12-30..2018-01-03).
// Paste/type this whole function into an AUTHENTICATED rahavard365.com tab's
// DevTools console.  The bearer token is fetched and consumed inside the page;
// no token, cookie, email or password is printed, stored or sent to Node.
// It downloads ra365_r32b_week2504_live.json with bars only.
(async () => {
  const IDS = [8, 803, 804];
  const TYPES = ['type0', 'type7'];
  const RES = ['D', 'W'];
  const FROM = '2017-12-20T00:00:00Z';
  const TO = '2018-01-10T23:59:59Z';
  const getToken = async () => {
    const r = await fetch('/api/v2/accounts/access-token', { credentials: 'include' });
    let t = null;
    try {
      const j = await r.json();
      const cs = [j, j && j.data, j && j.data && j.data.token].filter(Boolean);
      for (const c of cs) {
        if (typeof c === 'string' && c.length > 20) { t = c; break; }
        if (c && typeof c === 'object') {
          for (const k of ['access_token', 'accessToken', 'token', 'jwt']) {
            if (typeof c[k] === 'string' && c[k].length > 20) { t = c[k]; break; }
          }
        }
        if (t) break;
      }
    } catch (e) { /* no token */ }
    return { status: r.status, token: t };
  };
  let g = await getToken();
  const out = { captured_at: new Date().toISOString(), source: location.origin,
                token_status: g.status, has_token: !!g.token, items: [] };
  const q = [];
  for (const id of IDS) for (const type of TYPES) for (const res of RES) q.push([id, type, res]);
  let i = 0;
  const worker = async () => {
    while (true) {
      const n = i++;
      if (n >= q.length) break;
      const [id, type, res] = q[n];
      const sym = 'exchange.asset:' + id + ':real_close:' + type;
      const u = '/api/v2/chart/bars?countback=100&symbol=' + encodeURIComponent(sym) +
        '&resolution=' + res + '&from=' + FROM + '&to=' + TO;
      let status = 0, rows = [], error = null;
      for (let a = 0; a < 2; a++) {
        try {
          if (!g.token) g = await getToken();
          const r = await fetch(u, {
            headers: { Authorization: 'Bearer ' + g.token, 'application-name': 'rahavard',
                       platform: 'web', Accept: 'application/json' },
            credentials: 'include' });
          status = r.status;
          if (status === 401 && a === 0) { g = await getToken(); continue; }
          const j = await r.json().catch(() => null);
          const bars = j && Array.isArray(j.data) ? j.data : [];
          rows = bars.map(b => ({ utc: b.utc, o: b.open, h: b.high, l: b.low,
                                  c: b.close, v: b.volume }));
          break;
        } catch (e) { error = String(e).slice(0, 100); }
      }
      out.items.push({ asset_id: id, type, res, status, n: rows.length, bars: rows, error });
      await new Promise(r => setTimeout(r, 200));
    }
  };
  await Promise.all([0, 1, 2].map(worker));
  const blob = new Blob([JSON.stringify(out)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'ra365_r32b_week2504_live.json';
  document.body.appendChild(a); a.click(); a.remove();
  console.log('R32B_WEEK2504_DONE ' + JSON.stringify({
    token_status: out.token_status, has_token: out.has_token,
    items: out.items.map(x => [x.asset_id, x.type, x.res, x.status, x.n]),
    failed: out.items.filter(x => x.status !== 200 || !x.n)
      .map(x => [x.asset_id, x.type, x.res, x.status, x.n, x.error]) }));
})()
