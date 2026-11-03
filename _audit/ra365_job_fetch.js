// job: دو حالت — «search» برایِ یافتنِ asset idِ نمادها از رابطۀِ خودِ ره‌آورد،
// و «fetch» برایِ خواندنِ کندل‌هایِ مرجع درِ بازوهایِ تعدیل (type0 بدونِ تعدیل، type7 عملکردی) و دورهایِ D و W.
// فقط خواندنی. توکن فقط درِ حافظۀِ صفحه می‌ماند و هیچ‌جا ثبت نمی‌شود.
const fs = require('fs');
const path = require('path');

const CORPUS = path.join(__dirname, 'ra365_corpus.json');
const OUTRAW = path.join(__dirname, 'ra365_ref_bars.json');

const CALLER = `
const call = async (p) => {
  if (!window.__raTok) {
    const t = await fetch('/api/v2/accounts/access-token', { credentials: 'include' });
    const j = await t.json();
    for (const c of [j, j && j.data, j && (j.data && j.data.token)].filter(Boolean)) {
      if (typeof c === 'string' && c.length > 20) { window.__raTok = c; break; }
      if (c && typeof c === 'object') for (const k of ['access_token', 'accessToken', 'token', 'jwt'])
        if (typeof c[k] === 'string' && c[k].length > 20) { window.__raTok = c[k]; break; }
      if (window.__raTok) break;
    }
  }
  if (!window.__raTok) return { status: 'NO-TOKEN' };
  const res = await fetch(p, { headers: { Authorization: 'Bearer ' + window.__raTok, 'application-name': 'rahavard', platform: 'web', Accept: 'application/json' } });
  const text = await res.text();
  let json = null; try { json = JSON.parse(text); } catch (e) {}
  return { status: res.status, json, raw: json ? null : text.slice(0, 300) };
};
`;


module.exports = async ({ page, say, shot, probe }) => {
  const mode = (process.argv.find((a) => a.startsWith('--mode=')) || '--mode=fetch').split('=')[1];
  const steps = [];
  const log = (m) => { steps.push(m); say(m); };

  await page.goto('https://rahavard365.com/asset/453/chart', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(9000);
  log('chart page loginButton=' + (await probe()).loginButtonPresent);
  const inPage = (body) => page.evaluate(new Function('return (async () => {' + CALLER + body + '})()'));

  if (mode === 'search') {
    // الف) پیامِ خطایِ 422 را بخوان تا نامِ پارامترِ درستِ /api/v2/search معلوم شود
    const errs = await inPage(`
      const out = [];
      for (const q of ['q','query','term','text','search','s','name','symbol']) {
        const r = await call('/api/v2/search?' + q + '=' + encodeURIComponent('ولانا'));
        out.push({ param: q, status: r.status, body: r.json ? JSON.stringify(r.json).slice(0, 300) : String(r.raw).slice(0, 200) });
      }
      return out;
    `);
    for (const e of errs) log(`search param ${e.param} -> ${e.status}`);

    // ب) راهِ قطعی: خودِ جعبۀِ جست‌وجویِ رابط را با کیبورد پر کن و درخواستِ واقعی را بشنو
    const heard = [];
    page.on('request', (r) => {
      const u = r.url();
      if (/rahavard365\.com\/api\//.test(u) && !/bars|timescale|appearances|settings|feature_flags|licenses|notification|ip-check|time\/epoch/.test(u)) {
        heard.push({ url: u.slice(0, 200), method: r.method() });
      }
    });
    const inputs = await page.evaluate(() => Array.from(document.querySelectorAll('input, [role="searchbox"], [contenteditable="true"]'))
      .map((e, i) => ({ i, tag: e.tagName, type: e.type || '', ph: e.placeholder || '', aria: e.getAttribute('aria-label') || '', name: e.name || '', visible: !!(e.offsetWidth || e.offsetHeight) })).slice(0, 20));
    log('inputs seen: ' + JSON.stringify(inputs).slice(0, 500));

    let typed = null;
    const sel = ['input[placeholder]', 'input[type="search"]', '[role="searchbox"]', 'input[name*="search" i]', '[class*="search" i] input'];
    for (const s of sel) {
      const el = await page.$(s);
      if (!el) continue;
      await el.click().catch(() => {});
      await el.type('شبهرن', { delay: 90 }).catch(() => {});
      typed = s;
      break;
    }
    await page.waitForTimeout(6000);
    const shotName = await shot('ra365_search_typed');
    const resultsText = await page.evaluate(() => {
      const leaves = Array.from(document.querySelectorAll('body *')).filter((e) => e.childElementCount === 0);
      return leaves.map((e) => (e.textContent || '').trim()).filter((t) => t && t.length < 60 && /شبهرن|ولانا|فولاد|نتیجه|نبود/.test(t)).slice(0, 25);
    });
    return { mode, steps, searchParamErrors: errs, typedWith: typed, inputs, heard: heard.slice(-25), resultsText, shotName };
  }

  // حالتِ fetch
  const corpus = JSON.parse(fs.readFileSync(CORPUS, 'utf8'));
  const sufs = ((process.argv.find((a) => a.startsWith('--sufs=')) || '--sufs=type0,type7').split('=')[1]).split(',');
  const ress = ((process.argv.find((a) => a.startsWith('--res=')) || '--res=D,W').split('=')[1]).split(',');
  const raw = fs.existsSync(OUTRAW) ? JSON.parse(fs.readFileSync(OUTRAW, 'utf8')) : { bars: {}, meta: {} };
  raw.bars = raw.bars || {};
  raw.meta = raw.meta || {};

  for (const a of corpus) {
    for (const suf of sufs) {
      for (const res of ress) {
        const from = res === 'D' ? '2024-01-01T00:00:00Z' : '2018-01-01T00:00:00Z';
        const cnt = res === 'D' ? 600 : 380;
        const r = await inPage(`
          const tk = 'exchange.asset:${a.id}:real_close:${suf}';
          const q = await call('/api/v2/chart/bars?countback=${cnt}&symbol=' + encodeURIComponent(tk) + '&resolution=${res}&from=${from}&to=2026-10-13T00:00:00Z');
          const d = (q.json && Array.isArray(q.json.data)) ? q.json.data : [];
          return { status: q.status, n: d.length, ticker: tk, bars: d.map(b => ({ utc: b.utc, t: b.time, o: b.open, h: b.high, l: b.low, c: b.close, v: b.volume })) };
        `);
        raw.bars[`${a.sym}|${suf}|${res}`] = r;
        log(`bars ${a.sym} ${suf} ${res} status=${r.status} n=${r.n} last=${r.n ? r.bars[r.bars.length - 1].utc : '-'}`);
      }
    }
    // رویدادهایِ شرکتیِ مرجع (دفترِ تعدیل: افزایشِ سرمایه، سودِ نقدی)
    const m = await inPage(`
      const q = await call('/api/v2/chart/timescale_marks?ticker=' + encodeURIComponent('exchange.asset:${a.id}:real_close:type7') + '&resolution=D');
      return { status: q.status, json: q.json };
    `);
    raw.meta[`marks|${a.sym}`] = m;
    log(`marks ${a.sym} status=${m.status} n=${m.json && m.json.data ? m.json.data.length : 0}`);
  }
  raw.corpusSize = corpus.length;
  fs.writeFileSync(OUTRAW, JSON.stringify(raw, null, 1), 'utf8');
  const shotName = await shot('ra365_fetch_view');
  return {
    mode,
    steps,
    sufs,
    ress,
    shotName,
    corpusSize: corpus.length,
    counts: Object.fromEntries(Object.entries(raw.bars).map(([k, v]) => [k, { status: v.status, n: v.n }])),
  };
};
