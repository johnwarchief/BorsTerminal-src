// job: Phase5 Stage 7 — مقایسۀِ زندۀِ ره‌آورد ۳۶۵ درِ Edge با نشستِ لاگین‌شدهٔ مالک
// امن: هیچ رمز/کوکی/توکنی درِ فایل نمی‌نشیند؛ توکنِ کوتاه‌مدت از endpointِ خودِ اپ با
// credentials:include گرفته و فقط درِ همان evaluate مصرف می‌شود (خروجی = طولِ توکن، نه مقدارش).
// فرمِ ورود را پُر نمی‌کنیم؛ اگر نشست نبود، مالک درِ همان پنجره لاگین می‌کند و job با سنجشِ
// تواناییِ گرفتنِ توکن (نه متنِ DOM) احراز را تشخیص می‌دهد. توکن هر evaluate مستقل است چون
// page.goto سندِ جدید می‌سازد و مقدارِ window را پاک می‌کند.
const SEED_IDS = {'فولاد': 453, 'وبملت': 462, 'ولانا': 599, 'فنوال': 149, 'خودرو': 167, 'شپنا': 484};
const WANT = ['فولاد', 'وبملت', 'ولانا', 'فنوال', 'خودرو', 'وبصادر', 'طلا', 'شنفت', 'شبهرن', 'لخزر', 'فخاس'];

// کدِ in-pageِ مستقلِ گرفتنِ توکن (retry + guardِ بدنهٔ خالی) — هر evaluate خودش اجرا می‌کند.
const TOK = `(async()=>{for(let a=0;a<8;a++){try{const t=await fetch('/api/v2/accounts/access-token',{credentials:'include'});const x=await t.text();if(!x){await new Promise(r=>setTimeout(r,1200));continue;}let j=null;try{j=JSON.parse(x)}catch(e){}const v=[];for(const o of [j,j&&j.data,j&&j.data&&j.data.data]){if(typeof o==='string')v.push(o);else if(o&&typeof o==='object')for(const k in o)if(typeof o[k]==='string')v.push(o[k]);}const s=v.find(x=>x&&x.length>20);if(s)return s;}catch(e){}await new Promise(r=>setTimeout(r,1500));}return null;})()`;

const hasToken = (page) => page.evaluate(async (code) => {
  try { const t = await eval(code); return t ? t.length : 0; } catch (e) { return 0; }
}, TOK);

const resolveId = (page, sym) => page.evaluate(async ({code, s}) => {
  try {
    const t = await eval(code); if (!t) return null;
    const r = await fetch('/api/v2/search?keyword=' + encodeURIComponent(s), {headers: {Authorization: 'Bearer ' + t, 'application-name': 'rahavard', platform: 'web'}});
    const j = await r.json();
    const arr = (j && (j.data && (j.data.items || j.data) || j.items)) || [];
    const list = Array.isArray(arr) ? arr : [];
    const hit = list.find(it => ((it.symbol || it.ticker || it.name || it.lVal18 || '') + '').includes(s)) || list[0];
    return hit ? (hit.id || hit.asset_id || hit.entity_id || null) : null;
  } catch (e) { return null; }
}, {code: TOK, s: sym});

const fetchBars = (page, id, kind) => page.evaluate(async ({code, assetId, knd}) => {
  try {
    const t = await eval(code); if (!t) return {err: 'NO-TOKEN'};
    const to = new Date(), from = new Date(Date.now() - 6 * 365 * 24 * 3600 * 1000);
    const iso = (d) => d.toISOString().slice(0, 19) + 'Z';
    const u = '/api/v2/chart/bars?countback=1500&symbol=exchange.asset:' + assetId + ':real_close:' + knd + '&resolution=D&from=' + iso(from) + '&to=' + iso(to);
    const r = await fetch(u, {headers: {Authorization: 'Bearer ' + t, 'application-name': 'rahavard', platform: 'web', Accept: 'application/json'}});
    const txt = await r.text(); let j = null; try { j = JSON.parse(txt); } catch (e) { return {status: r.status, err: 'not-json:' + txt.slice(0, 80)}; }
    const d = (j && j.data !== undefined) ? j.data : j;
    const arr = Array.isArray(d) ? d : (d.candles || d.bars || d.data || []);
    const rows = [];
    for (const b of (Array.isArray(arr) ? arr : [])) {
      const tt = b.time !== undefined ? b.time : b[0];
      const cc = b.close !== undefined ? b.close : (Array.isArray(b) ? b[4] : undefined);
      if (tt !== undefined && cc !== undefined) rows.push({t: Number(tt), utc: b.utc, o: b.open, h: b.high, l: b.low, c: Number(cc), v: b.volume});
    }
    return {status: r.status, n: rows.length, all: rows};
  } catch (e) { return {err: String(e).slice(0, 120)}; }
}, {code: TOK, assetId: id, knd: kind});

const waitAuth = async (page, log, maxMs) => {
  const t0 = Date.now();
  for (;;) {
    const len = await hasToken(page);
    if (len > 20) return {authed: true, tokenLen: len, waitedMs: Date.now() - t0};
    if (Date.now() - t0 > maxMs) return {authed: false, tokenLen: 0, waitedMs: Date.now() - t0};
    log('در انتظارِ نشستِ لاگین‌شده (توکن نگرفته شد)… ' + Math.round((Date.now() - t0) / 1000) + 's');
    await page.waitForTimeout(5000);
  }
};

module.exports = async ({page, say, shot, probe}) => {
  const steps = [];
  const log = (m) => { steps.push(m); say(m); };
  const out = {phase: 'live-ra365-daily-type7', symbols: [], tokenLenRecordedOnly: true};

  await page.goto('https://rahavard365.com/', {waitUntil: 'domcontentloaded', timeout: 60000});
  await page.waitForTimeout(4000);
  const auth = await waitAuth(page, log, 300000);
  out.login = {authed: auth.authed, waitedMs: auth.waitedMs};
  out.tokenLenOnly = auth.tokenLen;
  log('وضعیتِ نشست: authed=' + auth.authed + ' tokenLen=' + auth.tokenLen + ' waited=' + auth.waitedMs + 'ms');
  if (!auth.authed) {
    await shot('ra365_phase5_not_logged_in');
    return {...out, aborted: 'NO-SESSION-TOKEN', steps};
  }

  for (const sym of WANT) {
    let id = SEED_IDS[sym] || null;
    if (!id) { try { id = await resolveId(page, sym); } catch (e) { id = null; } }
    if (!id) { out.symbols.push({sym, error: 'id-not-resolved'}); log(`${sym}: id حل نشد`); continue; }
    await page.goto(`https://rahavard365.com/asset/${id}/chart`, {waitUntil: 'domcontentloaded', timeout: 60000});
    await page.waitForTimeout(5000);
    let sh = null; try { sh = await shot(`ra365_phase5_${sym}`); } catch (e) {}
    let t7 = {}, t0 = {};
    try { t7 = await fetchBars(page, id, 'type7'); } catch (e) { t7 = {err: String(e).slice(0, 120)}; }
    try { t0 = await fetchBars(page, id, 'type0'); } catch (e) { t0 = {err: String(e).slice(0, 120)}; }
    out.symbols.push({sym, id, screenshot: sh,
      t7: {status: t7.status, points: t7.n, err: t7.err, all: t7.all},
      t0: {status: t0.status, points: t0.n, err: t0.err, all: t0.all}});
    log(`${sym} id=${id} type7.status=${t7.status}/${t7.n}  type0.status=${t0.status}/${t0.n}  shot=${sh}`);
  }
  return {...out, steps};
};
