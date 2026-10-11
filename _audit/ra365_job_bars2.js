// job: خواندنِ کندل‌هایِ مرجع از API خودِ ره‌آورد ۳۶۵ درِ همانِ نشستِ لاگین‌شده
// کانال: توکنِ کوتاه‌مدت با endpoint خودِ اپ گرفته می‌شود و فقط درِ حافظۀِ صفحه می‌ماند.
// هیچ توکن/کوکی/رمز/سرسترِ احراز هویتی به فایل یا گزارش نمی‌نویسد (فقط طول و نامِ سرسترها).
const fs = require('fs');
const path = require('path');

const ASSETS = [
  { id: 453, sym: 'فولاد' },
  { id: 462, sym: 'وبملت' },
  { id: 599, sym: 'ولانا' },
  { id: 149, sym: 'فنوال' },
  { id: 167, sym: 'خودرو' },
  { id: 484, sym: 'شپنا' },
];

// تابعی که درِ صفحه اجرا می‌شود: توکن می‌گیرد و فهرستِ صداها را انجام می‌دهد
const PAGE_CALLER = `
const call = async (path, opts) => {
  if (!window.__raTok) {
    const t = await fetch('/api/v2/accounts/access-token', { credentials: 'include' });
    const j = await t.json();
    const src = [j, j && j.data, j && j.data && j.data.token].filter(Boolean);
    for (const c of src) {
      if (typeof c === 'string' && c.length > 20) { window.__raTok = c; break; }
      if (c && typeof c === 'object') {
        for (const k of ['access_token', 'accessToken', 'token', 'jwt']) {
          if (typeof c[k] === 'string' && c[k].length > 20) { window.__raTok = c[k]; break; }
        }
      }
      if (window.__raTok) break;
    }
  }
  if (!window.__raTok) return { status: 'NO-TOKEN' };
  const res = await fetch(path, {
    headers: Object.assign({
      Authorization: 'Bearer ' + window.__raTok,
      'application-name': 'rahavard',
      platform: 'web',
      Accept: 'application/json',
    }, (opts && opts.headers) || {}),
  });
  const text = await res.text();
  let json = null;
  try { json = JSON.parse(text); } catch (e) { /* not json */ }
  return { status: res.status, json, raw: json ? null : text.slice(0, 400) };
};
`;

module.exports = async ({ page, say, shot, probe }) => {
  const steps = [];
  const log = (m) => { steps.push(m); say(m); };

  await page.goto('https://rahavard365.com/asset/453/chart', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(10000);
  const pre = await probe();
  log('page open nodes=' + pre.nodes + ' loginButton=' + pre.loginButtonPresent);

  // هر فراخوانی درِ صفحه: متنِ تابعِ caller + بدنه‌هایِ job
  const inPage = async (body) => page.evaluate(new Function('return (async () => {' + PAGE_CALLER + body + '})()'));

  // ---- فازِ الف: واژگانِ ticker (تعدیل/قیمت) ----
  const vocab = await inPage(`
    const out = {};
    for (const t of ['exchange.asset:453:real_close:type7','exchange.asset:453']) {
      out['symbols:' + t] = await call('/api/v2/chart/symbols?ticker=' + encodeURIComponent(t));
      out['configs:' + t] = await call('/api/v2/chart/configs?ticker=' + encodeURIComponent(t));
    }
    out['default-settings'] = await call('/api/v3/chart/default-settings?entity_id=453&entity_type=exchange.asset');
    const s = await call('/api/v2/chart/settings');
    out['settingsStatus'] = s.status;
    out['settingsKeys'] = s.json ? Object.keys(s.json).slice(0, 20) : null;
    // فقط فیلدهایی که نامشان به تعدیل/مقیاس/قیمت ربط دارد — هیچ دادۀِ حسابی بیرون نمی‌رود
    const flat = [];
    const walk = (o, p) => {
      if (o == null) return;
      if (typeof o !== 'object') { flat.push([p, typeof o === 'string' ? o.slice(0, 40) : o]); return; }
      for (const k of Object.keys(o)) walk(o[k], p ? p + '.' + k : k);
    };
    walk(s.json, '');
    out['settingsAdjust'] = flat.filter(([k]) => /adjust|log|scale|price|resolution|type/i.test(k)).slice(0, 40);
    return out;
  `);
  const summary = {};
  for (const [k, v] of Object.entries(vocab)) {
    summary[k] = v && v.json ? { status: v.status, keys: Object.keys(v.json).slice(0, 12) } : { status: v.status, raw: String(v.raw).slice(0, 250) };
  }
  log('vocab statuses: ' + Object.entries(summary).map(([k, v]) => k + '=' + v.status).join(' '));

  const symInfo = vocab['symbols:exchange.asset:453:real_close:type7'];
  const cfgInfo = vocab['configs:exchange.asset:453:real_close:type7'];

  // ---- فازِ ب: کدام پسوندِ تعدیل = «عملکردی»؟ مقایسه درِ یک روزِ ثابت ----
  const variants = [];
  const sufList = ['type7', 'type1', 'type2', 'type3', 'type4', 'type5', 'type6', 'type0', 'type8'];
  const priceTypes = ['real_close', 'nominal_close', 'close', 'final_close'];
  const varRes = await inPage(`
    const out = [];
    const suls = ${JSON.stringify(sufList)};
    const pts = ${JSON.stringify(priceTypes)};
    for (const pt of pts) for (const s of suls) {
      const tk = 'exchange.asset:453:' + pt + ':' + s;
      const r = await call('/api/v2/chart/bars?countback=30&symbol=' + encodeURIComponent(tk) + '&resolution=D&from=2026-09-20T00:00:00Z&to=2026-10-13T00:00:00Z');
      const d = r.json && Array.isArray(r.json.data) ? r.json.data : null;
      out.push({ tk, status: r.status, n: d ? d.length : 0, last: d && d.length ? { utc: d[d.length - 1].utc, o: d[d.length - 1].open, c: d[d.length - 1].close } : null,
        frac: d ? d.some(b => Math.abs(b.close - Math.round(b.close)) > 1e-9) : null });
    }
    return out;
  `);
  for (const v of varRes) variants.push(v);
  log('variant sweep ok=' + varRes.filter((v) => v.n > 0).length + '/' + varRes.length);

  // ---- فازِ پ: گنجینە — روزانە و هفتگی، تعدیلِ پیش‌فرض (type7) و یکیِ صحیح ----
  const chosenSufs = ['type7', ...new Set(varRes.filter((v) => v.n > 0 && v.frac === false).map((v) => v.tk.split(':')[3]))].slice(0, 3);
  log('suffixes to sweep: ' + chosenSufs.join(','));

  const raw = { bars: {}, meta: {} };
  for (const a of ASSETS) {
    for (const suf of chosenSufs) {
      for (const res of ['D', 'W']) {
        const from = res === 'D' ? '2026-01-01T00:00:00Z' : '2023-01-01T00:00:00Z';
        const r = await inPage(`
          const tk = 'exchange.asset:${a.id}:real_close:${suf}';
          const q = await call('/api/v2/chart/bars?countback=${res === 'D' ? 300 : 200}&symbol=' + encodeURIComponent(tk) + '&resolution=${res}&from=${from}&to=2026-10-13T00:00:00Z');
          const d = q.json && Array.isArray(q.json.data) ? q.json.data : [];
          return { status: q.status, n: d.length, bars: d.map(b => ({ utc: b.utc, t: b.time, o: b.open, h: b.high, l: b.low, c: b.close, v: b.volume })) };
        `);
        raw.bars[`${a.sym}|${suf}|${res}`] = r;
        log(`bars ${a.sym} ${suf} ${res} status=${r.status} n=${r.n}`);
      }
    }
  }

  // رویدادهایِ شرکتیِ مرجع (برایِ ریشۀِ تعدیل)
  for (const a of ASSETS) {
    const m = await inPage(`
      const q = await call('/api/v2/chart/timescale_marks?ticker=' + encodeURIComponent('exchange.asset:${a.id}:real_close:type7') + '&resolution=D');
      return { status: q.status, json: q.json };
    `);
    raw.meta[`marks|${a.sym}`] = m;
    log(`marks ${a.sym} status=${m.status}`);
  }

  fs.writeFileSync(path.join(__dirname, 'ra365_ref_bars.json'), JSON.stringify(raw, null, 1), 'utf8');
  const shotName = await shot('ra365_bars_view_after');

  return {
    steps,
    shotName,
    pre: { url: pre.url, loginButtonPresent: pre.loginButtonPresent },
    vocabSummary: summary,
    symbolMeta: symInfo && symInfo.json ? symInfo.json : { status: symInfo && symInfo.status, raw: String(symInfo && symInfo.raw).slice(0, 400) },
    configMeta: cfgInfo && cfgInfo.json ? cfgInfo.json : { status: cfgInfo && cfgInfo.status, raw: String(cfgInfo && cfgInfo.raw).slice(0, 400) },
    defaultSettings: vocab['default-settings'] && vocab['default-settings'].json,
    variants,
    chosenSufs,
    counts: Object.fromEntries(Object.entries(raw.bars).map(([k, v]) => [k, { status: v.status, n: v.n }])),
    rawFile: '_audit/ra365_ref_bars.json',
  };
};
