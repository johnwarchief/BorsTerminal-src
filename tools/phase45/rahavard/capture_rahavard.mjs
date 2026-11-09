// tools/ra365/r32-reference/capture_rahavard.mjs
//
// Authorized auto-acquisition of Rahavard365 reference bars.
//
// Why a browser and not curl: the reference API answers only inside the
// owner's own logged-in Rahavard365 session.  This driver attaches to an Edge
// window that the OWNER opened and logged into, and issues the same
// same-origin fetch() the product's own chart page issues.  It never reads,
// prints or stores a cookie, token, password or account id: the session stays
// inside the browser and only bar JSON comes back out.
//
// It talks raw CDP over the DevTools WebSocket (no Playwright dependency, so
// it runs on the pinned Node without an install step).
//
// Usage
//   node capture_rahavard.mjs --symbols <symbols.json> --out <export.json> \
//        [--port 9333] [--launch] [--probe-auth] \
//        [--types type0,type7] [--res D,W] [--countback 400] \
//        [--from 1990-01-01] [--to 2030-01-01] [--marks]
//
// Exit codes
//   0  capture complete, or probe-auth says the session is authenticated
//   3  session not authenticated (owner must log in in the attached window)
//   4  no attachable browser/target (owner must run with --launch, then log in)
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import os from 'node:os';
import cp from 'node:child_process';

const require = createRequire(import.meta.url);

const BASE = 'https://rahavard365.com';
const ORIGIN_HINT = 'rahavard365.com';
const TYPE_TO_ADJUST = {
  type0: 'raw', type1: 'adjusted', type2: 'adjusted', type3: 'adjusted',
  type4: 'adjusted', type5: 'adjusted', type6: 'adjusted', type7: 'adjusted',
};

function parseArgs(argv) {
  const out = { port: 9333, types: 'type0,type7', res: 'D,W', countback: 400, marks: false };
  for (let i = 2; i < argv.length; i += 1) {
    const a = argv[i];
    const take = () => argv[++i];
    if (a === '--symbols') out.symbols = take();
    else if (a === '--out') out.out = take();
    else if (a === '--port') out.port = Number(take());
    else if (a === '--types') out.types = take();
    else if (a === '--res') out.res = take();
    else if (a === '--countback') out.countback = Number(take());
    else if (a === '--from') out.from = take();
    else if (a === '--to') out.to = take();
    else if (a === '--launch') out.launch = true;
    else if (a === '--probe-auth') out.probeAuth = true;
    else if (a === '--marks') out.marks = true;
    else if (a === '--browser') out.browser = take();
    else if (a === '--profile') out.profile = take();
    else if (a === '--help' || a === '-h') out.help = true;
    else throw new Error('unknown argument: ' + a);
  }
  return out;
}

const HELP = `capture_rahavard.mjs --symbols <file> --out <file> [--port 9333] [--launch]
  [--probe-auth] [--browser <exe>] [--profile <dir>]
  [--types type0,type7] [--res D,W] [--countback N] [--from D] [--to D] [--marks]`;

function log(...a) { process.stdout.write(a.join(' ') + '\n'); }

async function tryJson(url, timeoutMs = 4000) {
  const ac = new AbortController();
  const t = setTimeout(() => ac.abort(), timeoutMs);
  try {
    const r = await fetch(url, { signal: ac.signal });
    return await r.json();
  } finally { clearTimeout(t); }
}

async function launchBrowser(port, startUrl, exe, profileDir) {
  if (!fs.existsSync(exe)) throw new Error('browser not found: ' + exe);
  const profile = profileDir;
  const args = [
    `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
    '--no-first-run', '--no-default-browser-check', '--disable-features=Translate',
    '--window-size=1600,900', '--new-window', startUrl || BASE,
  ];
  const child = cp.spawn(exe, args, { detached: true, stdio: 'ignore' });
  child.unref();
  log('spawned ' + path.basename(exe) + ' pid=' + child.pid + ' profile=' + profile);
  const t0 = Date.now();
  while (Date.now() - t0 < 90000) {
    try {
      const v = await tryJson(`http://127.0.0.1:${port}/json/version`);
      if (v && v.Browser) return v;
    } catch { /* not up yet */ }
    await new Promise((r) => setTimeout(r, 1500));
  }
  throw new Error('CDP port ' + port + ' never came up — if a browser with this '
    + 'profile is already running, close that window and retry');
}

//: A debugging port is refused on Chromium's default profile, so the probe
//: always runs on its own data directory; the owner logs in there once and the
//: session stays inside the browser.
function pickBrowser(explicit) {
  const want = explicit || process.env.RA_BROWSER;
  if (want) return want;
  const local = process.env.LOCALAPPDATA || '';
  const candidates = [
    'C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe',
    'C:\\Program Files (x86)\\BraveSoftware\\Brave-Browser\\Application\\brave.exe',
    local ? path.join(local, 'BraveSoftware', 'Brave-Browser', 'Application', 'brave.exe') : '',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  ].filter(Boolean);
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  throw new Error('no Chromium browser found; pass --browser <exe>');
}

function pickProfile(explicit) {
  return explicit || process.env.RA_PROFILE
    || path.join(os.tmpdir(), 'bors-ra365-probe-profile');
}

async function pickTarget(port) {
  const list = await tryJson(`http://127.0.0.1:${port}/json/list`);
  if (!Array.isArray(list)) return null;
  const pages = list.filter((t) => t.type === 'page' && t.webSocketDebuggerUrl);
  return pages.find((t) => String(t.url).includes(ORIGIN_HINT)) || pages[0] || null;
}

class Cdp {
  constructor(ws) { this.ws = ws; this.id = 0; this.pending = new Map(); this.seq = 0; }

  static async attach(wsUrl) {
    const ws = new WebSocket(wsUrl);
    const cdp = new Cdp(ws);
    ws.addEventListener('message', (ev) => {
      let msg; try { msg = JSON.parse(ev.data); } catch { return; }
      if (msg.id && cdp.pending.has(msg.id)) {
        const { resolve, reject } = cdp.pending.get(msg.id);
        cdp.pending.delete(msg.id);
        if (msg.error) reject(new Error('CDP ' + JSON.stringify(msg.error)));
        else resolve(msg.result);
      }
    });
    await new Promise((resolve, reject) => {
      ws.addEventListener('open', resolve, { once: true });
      ws.addEventListener('error', () => reject(new Error('CDP websocket failed')), { once: true });
    });
    return cdp;
  }

  send(method, params = {}) {
    const id = ++this.id;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }

  async evaluate(fnSource, arg, timeoutMs = 60000) {
    const res = await this.send('Runtime.evaluate', {
      expression: `(${fnSource})(${JSON.stringify(arg)})`,
      awaitPromise: true, returnByValue: true, timeout: timeoutMs,
    });
    if (res.exceptionDetails) {
      throw new Error('page exception: ' + JSON.stringify(res.exceptionDetails).slice(0, 300));
    }
    return res.result ? res.result.value : null;
  }

  close() { try { this.ws.close(); } catch { /* already gone */ } }
}

// The chart API answers only with a bearer token.  The token is minted by the
// site itself at /api/v2/accounts/access-token and is fetched and used INSIDE
// the page: it is cached on the page's own window, never returned to Node,
// never printed and never written anywhere.  Only the response body comes back.
const IN_PAGE_FETCH = `async (u) => {
  const HEADERS = {
    'Application-Name': 'rahavard',
    'platform': 'web',
    'Page-Id': '44',
    'Content-Type': 'application/json',
  };
  const call = async (retry) => {
    try {
      if (!window.__r32_token) {
        const tr = await fetch('/api/v2/accounts/access-token', { credentials: 'include' });
        if (!tr.ok) return { status: tr.status, ok: false, json: null, head: 'token-endpoint ' + tr.status };
        const tj = await tr.json();
        window.__r32_token = (tj && tj.data && tj.data.token) || null;
        if (!window.__r32_token) return { status: -1, ok: false, json: null, head: 'no token field in response' };
      }
      const res = await fetch(u, {
        credentials: 'include',
        headers: Object.assign({ Authorization: 'Bearer ' + window.__r32_token }, HEADERS),
      });
      if ((res.status === 401 || res.status === 403) && !retry) {
        window.__r32_token = null;          // expired: mint once more, retry once
        return call(true);
      }
      const text = await res.text();
      let json = null; try { json = JSON.parse(text); } catch (e) { /* not json */ }
      return { status: res.status, ok: res.ok, json, head: text.slice(0, 300) };
    } catch (e) {
      return { status: -1, ok: false, json: null, head: 'ERR ' + String(e).slice(0, 200) };
    }
  };
  return call(false);
}`;

function sha256OfBuffer(buf) { return crypto.createHash('sha256').update(buf).digest('hex'); }

async function main() {
  const a = parseArgs(process.argv);
  if (a.help || (!a.probeAuth && (!a.symbols || !a.out))) { log(HELP); process.exit(a.help ? 0 : 2); }

  let version = null;
  try { version = await tryJson(`http://127.0.0.1:${a.port}/json/version`); } catch { version = null; }
  if (!version) {
    if (!a.launch) {
      log('NO_BROWSER: nothing listening on CDP port ' + a.port);
      log('Run again with --launch, log in to Rahavard365 in the window that opens, then re-run without --launch.');
      process.exit(4);
    }
    version = await launchBrowser(a.port, BASE, pickBrowser(a.browser), pickProfile(a.profile));
  }
  log('attached: ' + (version.Browser || 'unknown') + ' @ ' + a.port);

  const target = await pickTarget(a.port);
  if (!target) { log('NO_TARGET: no page target to attach to'); process.exit(4); }
  log('target: ' + target.url);

  const cdp = await Cdp.attach(target.webSocketDebuggerUrl);
  try {
    const auth = await cdp.evaluate(IN_PAGE_FETCH,
      '/api/v2/chart/bars?countback=2&symbol=' + encodeURIComponent('exchange.asset:453:real_close:type7')
      + '&resolution=D&from=2026-01-01T00:00:00Z&to=2026-12-31T00:00:00Z');
    log('auth probe: status=' + auth.status);
    if (auth.status === 401 || auth.status === 403 || auth.status === -1) {
      log('SESSION_NOT_AUTHENTICATED: ' + (auth.head || 'status ' + auth.status));
      log('Log in to Rahavard365 in the attached window, then re-run.');
      process.exit(3);
    }
    if (a.probeAuth) {
      log(auth.ok ? 'AUTH_OK' : 'AUTH_UNKNOWN status=' + auth.status + ' head=' + auth.head);
      process.exit(auth.ok ? 0 : 3);
    }

    const symbols = JSON.parse(fs.readFileSync(a.symbols, 'utf8'));
    const list = Array.isArray(symbols) ? symbols : (symbols.symbols || []);
    const types = a.types.split(',').map((s) => s.trim()).filter(Boolean);
    const resolutions = a.res.split(',').map((s) => s.trim().toUpperCase()).filter(Boolean);
    const capturedAt = new Date().toISOString().replace(/\.\d+Z$/, 'Z');
    // the bars endpoint rejects a request without a window
    const from = a.from || '1990-01-01T00:00:00Z';
    const to = a.to || (new Date(Date.now() + 86400000).toISOString().replace(/\.\d+Z$/, 'Z'));

    const series = [];
    const ledger = [];
    for (const item of list) {
      const assetId = item.asset_id != null ? item.asset_id : item.id;
      if (assetId == null) { ledger.push({ symbol: item.symbol, state: 'NO_ASSET_ID' }); continue; }
      const basis = item.basis || 'real_close';
      for (const type of types) {
        const ticker = `exchange.asset:${assetId}:${basis}:${type}`;
        for (const res of resolutions) {
          const parts = [`countback=${a.countback}`, `symbol=${encodeURIComponent(ticker)}`, `resolution=${res}`];
          parts.push('from=' + encodeURIComponent(from));
          parts.push('to=' + encodeURIComponent(to));
          const url = '/api/v2/chart/bars?' + parts.join('&');
          const r = await cdp.evaluate(IN_PAGE_FETCH, url);
          const bars = r.json && Array.isArray(r.json.data) ? r.json.data : [];
          const rec = {
            asset_id: assetId, symbol: item.symbol, ticker, basis,
            adjust: TYPE_TO_ADJUST[type] || 'adjusted', resolution: res,
            status: r.status,
            bars: bars.map((b) => ({
              utc: b.utc || b.time, open: b.open, high: b.high, low: b.low,
              close: b.close, volume: b.volume,
            })),
          };
          if (!bars.length) rec.head = r.head;
          series.push(rec);
          ledger.push({
            symbol: item.symbol, asset_id: assetId, type, resolution: res,
            status: r.status, bars: bars.length,
          });
          log(`${item.symbol} ${type} ${res} status=${r.status} n=${bars.length}`);
          await new Promise((r2) => setTimeout(r2, 400));
        }
        if (a.marks) {
          const mr = await cdp.evaluate(IN_PAGE_FETCH, `/api/v2/chart/timescale_marks?ticker=${encodeURIComponent(ticker)}&resolution=D`);
          const tgt = series.find((s) => s.ticker === ticker);
          if (tgt) tgt.marks = mr.json || { status: mr.status, head: mr.head };
        }
      }
    }

    const doc = {
      source: {
        kind: 'rahavard365-web-api',
        endpoint: BASE,
        session: 'owner-browser-cdp',
        captured_at: capturedAt,
        browser: version.Browser || null,
        types, resolutions, countback: a.countback, from, to,
        auth: 'bearer token minted in-page at /api/v2/accounts/access-token; never leaves the page',
        license: 'owner subscription; not redistributable',
      },
      ledger,
      series,
    };
    const text = JSON.stringify(doc, null, 1);
    doc.source.input_sha256 = sha256OfBuffer(Buffer.from(text, 'utf8'));
    fs.mkdirSync(path.dirname(a.out), { recursive: true });
    fs.writeFileSync(a.out, JSON.stringify(doc, null, 1), 'utf8');
    const ok = ledger.filter((l) => l.status === 200 && l.bars > 0).length;
    log(`wrote ${a.out}  series=${series.length}  non-empty=${ok}/${ledger.length}`);
    log('input_sha256=' + doc.source.input_sha256);
  } finally {
    cdp.close();
  }
}

main().catch((e) => { console.error('FATAL ' + String(e && e.stack ? e.stack : e)); process.exit(1); });