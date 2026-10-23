// In-page Rahavard365 scanner used by the 2026-10-20 full-universe mission.
// Paste this whole function into the authenticated Browser Connector tab via
// evaluate_script, after starting tools/ra365_ingest_server.py.
// The bearer token is fetched and consumed inside the page; it never leaves the page.
function ra365Scan(maxAssets) {
  if (window.__raScan && window.__raScan.running) {
    return { already: true, progress: window.__raScan };
  }
  const ING = 'http://127.0.0.1:8791';
  (async () => {
    let ids = [];
    let done = new Set();
    try {
      ids = await (await fetch(ING + '/targets')).json();
      done = new Set(await (await fetch(ING + '/done')).json());
    } catch (e) {
      window.__raScan = { running: false, error: 'targets:' + String(e).slice(0, 120) };
      return;
    }
    if (maxAssets) ids = ids.slice(0, maxAssets);
    const keys = [];
    for (const id of ids) {
      for (const type of ['type0', 'type7']) {
        for (const res of ['D', 'W']) {
          const k = id + '|' + type + '|' + res;
          if (!done.has(k)) keys.push(k);
        }
      }
    }
    window.__raScan = { running: true, total: keys.length, done: 0, errors: [], started: Date.now(), idx: 0 };
    const pushErr = (m) => { if (window.__raScan.errors.length < 30) window.__raScan.errors.push(String(m).slice(0, 140)); };
    const post = async (p) => {
      try {
        await fetch(ING + '/ingest', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(p) });
      } catch (e) { pushErr('post:' + e); }
    };
    const getToken = async () => {
      const tr = await fetch('/api/v2/accounts/access-token', { credentials: 'include' });
      const tj = await tr.json().catch(() => null);
      let t = null;
      for (const c of [tj, tj && tj.data, tj && tj.data && tj.data.token].filter(Boolean)) {
        if (typeof c === 'string' && c.length > 20) { t = c; break; }
        if (c && typeof c === 'object') for (const k of ['access_token', 'accessToken', 'token', 'jwt'])
          if (typeof c[k] === 'string' && c[k].length > 20) { t = c[k]; break; }
        if (t) break;
      }
      return t;
    };
    const worker = async () => {
      let token = await getToken();
      let n = 0;
      while (true) {
        if (window.__raScan.stop) break;
        const i = window.__raScan.idx++;
        if (i >= keys.length) break;
        const key = keys[i];
        const [id, type, res] = key.split('|');
        const tk = 'exchange.asset:' + id + ':real_close:' + type;
        const u = '/api/v2/chart/bars?countback=100000&symbol=' + encodeURIComponent(tk) +
          '&resolution=' + res + '&from=2020-01-01T00:00:00Z&to=2026-10-20T23:59:59Z';
        let status = 0, rows = [], err = null;
        for (let attempt = 0; attempt < 2; attempt++) {
          try {
            if (!token) token = await getToken();
            const r = await fetch(u, {
              headers: { Authorization: 'Bearer ' + token, 'application-name': 'rahavard', platform: 'web', Accept: 'application/json' },
              credentials: 'include'
            });
            status = r.status;
            if (status === 401 && attempt === 0) { token = await getToken(); continue; }
            const t = await r.text();
            let j = null; try { j = JSON.parse(t); } catch (e) { /* non-json */ }
            const bars = j && Array.isArray(j.data) ? j.data : [];
            rows = bars.map((b) => [b.utc, b.open, b.high, b.low, b.close, b.volume]);
            if (status !== 200) pushErr(key + ' HTTP ' + status);
            break;
          } catch (e) { err = String(e).slice(0, 120); }
        }
        await post({ key, asset_id: id, type, res, status, bars: rows, error: err });
        window.__raScan.done++;
        window.__raScan.last = key;
        n++;
        if (n % 500 === 0) token = await getToken();
        await new Promise((r) => setTimeout(r, 300));
      }
    };
    await Promise.all([0, 1, 2, 3].map(worker));
    window.__raScan.running = false;
    window.__raScan.finished = true;
    window.__raScan.finishedAt = Date.now();
  })();
  return { started: true, workers: 4 };
}
