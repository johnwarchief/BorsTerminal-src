// Round 21 live Rahavard365 capture (read-only).
// Run inside the owner's authenticated rahavard365.com tab via DevTools Console
// (or Qoder Browser Connector evaluate_script).  The bearer token is fetched and
// consumed inside the page; no token, cookie or account data leaves the page.
// The script downloads `ra365_r23_ref_ext.json` with type0/type7 x D/W bars for
// the 14-asset pilot (price type: real_close).  Move the download to
// D:/BorsTerminal-tmp/r21_live/ before running tools/ra365_round21_live_parity.py.
(async () => {
  const IDS31 = [595,48315,207,325,291,599,2672,453,149,167,182,696,183,703,462,484,287,384,6274,109,485,7836,16449,17495,569,458,159,252,498,661,302]; const IDS19 = [711,16272,15239,637,490,500,24691,1771,724,60,32,2967,1585,65,273,7831,20817,6273,540];
  const gt = async () => {
    const r = await fetch('/api/v2/accounts/access-token', { credentials: 'include' });
    const j = await r.json().catch(() => null);
    let t = null;
    const cs = [j, j && j.data, j && j.data && j.data.token];
    for (const c of cs) {
      if (typeof c === 'string' && c.length > 20) { t = c; break; }
      if (c && typeof c === 'object') {
        for (const k of ['access_token', 'accessToken', 'token', 'jwt']) {
          if (typeof c[k] === 'string' && c[k].length > 20) { t = c[k]; break; }
        }
      }
      if (t) break;
    }
    return t;
  };
  let token = await gt();
  const out = { generated_at: new Date().toISOString(), source: location.origin,
                price_type: 'real_close', items: [] };
  const q = [];
  for (const id of IDS31) for (const type of ['type0', 'type7']) q.push([id, type, 'M']); for (const id of IDS19) for (const type of ['type0', 'type7']) for (const res of ['D', 'W', 'M']) q.push([id, type, res]);
  let i = 0;
  const worker = async () => {
    while (true) {
      const n = i++;
      if (n >= q.length) break;
      const [id, type, res] = q[n];
      const sym = 'exchange.asset:' + id + ':real_close:' + type;
      const u = '/api/v2/chart/bars?countback=100000&symbol=' + encodeURIComponent(sym) +
        '&resolution=' + res + '&from=2008-01-01T00:00:00Z&to=2026-10-23T23:59:59Z';
      let st = 0, rows = [], er = null;
      for (let a = 0; a < 3; a++) {
        const ctl = new AbortController();
        const to = setTimeout(() => ctl.abort(), 25000);
        try {
          if (!token) token = await gt();
          const r = await fetch(u, { headers: { Authorization: 'Bearer ' + token,
            'application-name': 'rahavard', platform: 'web', Accept: 'application/json' },
            credentials: 'include', signal: ctl.signal });
          st = r.status;
          if (st === 401) { token = await gt(); clearTimeout(to); continue; }
          const j = await r.json().catch(() => null);
          rows = (j && Array.isArray(j.data) ? j.data : []).map(b => ({ utc: b.utc, t: b.time,
            o: b.open, h: b.high, l: b.low, c: b.close, v: b.volume }));
          clearTimeout(to);
          break;
        } catch (e) { er = String(e).slice(0, 100); clearTimeout(to); }
        await new Promise(r => setTimeout(r, 800));
      }
      out.items.push({ asset_id: id, type, res, status: st, n: rows.length, bars: rows, error: er });
      await new Promise(r => setTimeout(r, 250));
    }
  };
  await Promise.all([0, 1, 2].map(worker));
  out.generated_at = new Date().toISOString();
  const blob = new Blob([JSON.stringify(out)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'ra365_r23_ref_ext.json';
  document.body.appendChild(a); a.click(); a.remove();
  console.log('R21_DONE ' + JSON.stringify({ series: out.items.length, bytes: blob.size,
    failed: out.items.filter(x => x.status !== 200 || !x.n).map(x => [x.asset_id, x.type, x.res, x.status, x.n, x.error]) }));
})()
