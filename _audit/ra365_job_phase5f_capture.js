// _audit/ra365_job_phase5f_capture.js — Stage 2ِ دورِ بستۀ Phase 5: گرفتنِ **زندهٔ** سریِ روزانۀ
// رهاورد ۳۶۵ (type7 = تعدیل‌شدۀ عملکردی، type0 = خام/بدونِ تعدیل) برایِ نمادهایِ Stage 1.
//
// چهار چیز که این هارنس نسبت بهِ نسخهٔ Phase 5 عوض می‌کند، چون آن‌ها درِ مأموریتِ جدید صریح‌اند:
// ۱) **هویت با نگاشتِ نام اثبات نمی‌شود.** نسخهٔ پیشین `list.find(... .includes(s)) || list[0]`
//    بود؛ یعنی اگر هیچِ نامی نمی‌خورد، اولینِ نتیجهٔ جست‌وجو به‌عنوانِ نماد پذیرفته می‌شد.
//    اینجا فقط تطبیقِ **دقیق** (بعد ازِ نرمال‌سازیِ ZWNJ/فاصله) پذیرفته می‌شود، و اگر
//    دقیق نبود، سطر `identity:"unresolved"` می‌گیرد — هیچِ `list[0]`‌ای وجود ندارد.
// ۲) **مانیفستِ بیرونی:** نمادها ازِ `_audit/ra365_phase5f_targets.json` (خروجیِ
//    `tools/phase5f_select_symbols.py`) خوانده می‌شوند، نه ازِ فهرستِ دستِ‌نویسِ کد.
// ۳) **بی‌کلیک رویِ چارتِ مالک:** گرفتنِ داده فقط با `fetch` رویِ یکِ صفحهٔ دامنه انجام
//    می‌شود؛ صفحهٔ چارت تنها برایِ **چند** اسکرین‌شاتِ انتخابی باز می‌شود و درِ پایانِ
//    اجرا بهِ همان نمادی که پیش‌تر باز بود برمی‌گردد و وضعیتش **ثبت** می‌شود.
// ۴) **تفکیکِ خطا:** خطایِ احرازِ نشست/دسترسی (`NO-TOKEN`، `401/403`، بدنهٔ HTML) ازِ
//    خطایِ محاسباتی/ساختاری جدا برچسب می‌خورد؛ هیچ‌کدام «صفرِ کندل» تفسیر نمی‌شوند.
//
// امنیت: هیچِ رمز/کوکی/توکنی خوانده یا نوشته نمی‌شود. توکن کوتاه‌مدت ازِ endpointِ خودِ
// اپ با `credentials: include` گرفته می‌شود و فقط درِ همان evaluate مصرف می‌گردد؛ درِ
// خروجی **فقط طولِ** آن ثبت می‌شود. فرمِ ورود پر نمی‌شود؛ اگر نشست نبود، اجرا با
// `BLOCKED-NO-SESSION` می‌ایستد و ادامهٔ کارهایِ مستقلِ دورِ من متوقف نمی‌شود.
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const TARGETS = path.join(ROOT, '_audit', 'ra365_phase5f_targets.json');
const OWNER_HOME_ASSET = process.env.RA_HOME_ASSET || '453';   // همان چارتی که مالک باز کرده بود
const N_SHOTS = Number(process.env.RA_SHOTS || 8);
const GAP_MS = Number(process.env.RA_GAP_MS || 350);
const COUNTBACK = Number(process.env.RA_COUNTBACK || 1500);
const FROM_ISO = process.env.RA_FROM || '2018-01-01T00:00:00Z';

// یکِ منبعِ حقیقت برایِ نرمال‌سازیِ نام: ZWNJ و فاصله‌هایِ نامرئی حذف، «ي» عربی → «ی»،
// و «ك» عربی → «ک» — همان دو حرفی که گاردِ `persian_glyph_guard` هم ردیابی می‌کند.
const NORM = `const norm = (s) => (s || '').toString().replace(/\\u200c|\\u200d|\\u00a0/g, '')
  .replace(/ي/g, 'ی').replace(/ك/g, 'ک').replace(/\\s+/g, ' ').trim();`;

const TOK = `(async()=>{for(let a=0;a<8;a++){try{const t=await fetch('/api/v2/accounts/access-token',
  {credentials:'include'});const x=await t.text();if(!x){await new Promise(r=>setTimeout(r,1200));continue;}
  let j=null;try{j=JSON.parse(x)}catch(e){}
  const v=[];for(const o of [j,j&&j.data,j&&j.data&&j.data.data]){
    if(typeof o==='string')v.push(o);
    else if(o&&typeof o==='object')for(const k in o)if(typeof o[k]==='string')v.push(o[k]);}
  const s=v.find(x=>x&&x.length>20);if(s)return s;}catch(e){}
  await new Promise(r=>setTimeout(r,1500));}return null;})()`;

// resolveIdِ سخت‌گیرانه — فیلدها **حدس نیستند**: `_audit/ra365_search_shape.js` پاسخِ واقعیِ
// `/api/v2/search` را خواند و شکلِ آن این است: `{data:[{type_id, type, entity_id,
// entity_type:'exchange.asset', trade_symbol, name, short_name, exchange, unlisted_item}]}`
// و کلیدِ نمادِ قابلِ معامله همان `trade_symbol` است (نه `symbol`/`ticker`/`lVal18` — این سه
// درِ پاسخ هیچ نیستند، و به همین دلیل اجرایِ اولِ همین هارنس هر ۵۵ نماد را `no-exact-match`
// داد). تطبیق = **دقیق** رویِ `trade_symbol`، و فقط آیتمِ `exchange.asset`.
// چرا این جایِ `.includes()` را می‌گیرد: سنجشِ همین دور ثابت کرد `keyword` سمتِ سرور فیلتر
// نمی‌کند (جست‌وجوی «فولاد» ۱۳۴۲ آیتم برمی‌گرداند)؛ پس «اولینِ آیتم» یا «شاملِ نام» بودن
// می‌تواند نمادِ دیگری بدهد. شاهدِ واقعیِ همین نقص: دورِ پیش «طلا» با `includes` به
// `entity_id=40745` («طلای ناب08»، نوع=اوراق) نشست، درحالیِ که «طلا»یِ بانکِ ما صندوقِ
// «پشتوانه چندکالایی پارسیان» (`entity_id=2672`) است. آن سطرِ کنترلِ بی‌رویداد، نمادِ
// دیگری را می‌سنجید.
// یکِ بارِ دوباره‌گیریِ املایی بی‌ضرر مجاز است (بانکِ ما برخی نمادها را با «ك/ي» عربی نگه
// می‌دارد؛ مرجع همان نام را با حرفِ فارسی دارد: «كگل» ⇔ «کگل»). این هویت‌سازی نیست —
// رفعِ اختلافِ املایِ همانِ نام است، و هویت درِ Stage 6 با مقابلهٔ کندلِ خام بستۀ می‌شود.
const RESOLVE = `async (tk, s) => {
  ${NORM}
  const forms = [s];
  const alt = norm(s);
  if (alt && alt !== s) forms.push(alt);
  let last = { err: 'no-search', candidates: 0 };
  for (const form of forms) {
    const r = await fetch('/api/v2/search?keyword=' + encodeURIComponent(form), {
      headers: { Authorization: 'Bearer ' + tk, 'application-name': 'rahavard', platform: 'web' } });
    const txt0 = await r.text();
    let j = null;
    try { j = JSON.parse(txt0); } catch (e) {
      last = { err: 'search-' + (r.status === 401 || r.status === 403 ? 'AUTH-' : 'not-json-') + r.status,
               head: txt0.slice(0, 60) };
      continue;
    }
    const arr0 = (j && (j.data && (j.data.items || j.data) || j.items)) || [];
    const list = (Array.isArray(arr0) ? arr0 : []).filter((it) => it && it.entity_type === 'exchange.asset');
    const want = norm(form);
    const exact = list.filter((it) => norm(it.trade_symbol) === want);
    const listed = exact.filter((it) => it.unlisted_item !== true);
    const pool = listed.length ? listed : exact;
    if (!pool.length) {
      last = { err: 'no-exact-match', candidates: list.length,
               nearest: list.length ? String(norm(list[0].trade_symbol)).slice(0, 40) : null,
               triedForms: forms };
      continue;
    }
    const ids = [...new Set(pool.map((x) => String(x.entity_id || x.id || x.asset_id)).filter(Boolean))];
    if (ids.length > 1) {
      last = { err: 'ambiguous-exact', candidates: list.length, ids: ids.slice(0, 6),
                types: pool.slice(0, 6).map((x) => x.type + ':' + x.exchange), triedForms: forms };
      continue;
    }
    const hit = pool[0];
    return { id: String(hit.entity_id || hit.id || hit.asset_id),
      matchedField: 'trade_symbol', matchedForm: form, tradeSymbol: norm(hit.trade_symbol),
      refName: norm(hit.name || hit.short_name || ''), refType: hit.type, type_id: hit.type_id,
      exchange: hit.exchange, unlisted: hit.unlisted_item === true,
      candidates: list.length, exact: true };
  }
  return last;
}`;

const BARS = `async (tk, assetId, knd) => {
  const to = new Date();
  const iso = (d) => d.toISOString().slice(0, 19) + 'Z';
  const u = '/api/v2/chart/bars?countback=' + COUNTBACK_ + '&symbol=exchange.asset:' + assetId +
    ':real_close:' + knd + '&resolution=D&from=' + iso(new Date('${FROM_ISO}')) + '&to=' + iso(to);
  const r = await fetch(u, { headers: { Authorization: 'Bearer ' + tk,
    'application-name': 'rahavard', platform: 'web', Accept: 'application/json' } });
  const txt0 = await r.text();
  let j = null; try { j = JSON.parse(txt0); } catch (e) {
    return { status: r.status, err: (r.status === 401 || r.status === 403) ? 'AUTH-or-ACCESS-' + r.status
      : 'not-json-' + r.status, head: txt0.slice(0, 60) }; }
  const d = (j && j.data !== undefined) ? j.data : j;
  const arr = Array.isArray(d) ? d : (d.candles || d.bars || d.data || []);
  const rows = [];
  for (const b of (Array.isArray(arr) ? arr : [])) {
    const tt = b.time !== undefined ? b.time : (Array.isArray(b) ? b[0] : undefined);
    const cc = b.close !== undefined ? b.close : (Array.isArray(b) ? b[4] : undefined);
    if (tt !== undefined && cc !== undefined) {
      // روزِ تهرانی: += 3:30 سپسِ برچسبِ UTC. Stage 6 فقط «بستن» و نسبتِ type7/type0 را
      // می‌سنجد، پس OHLC/volume درِ بارِ JSON تکراری نمی‌آید (۵۵ نماد × ۱۵۰۰ × ۲).
      const day = new Date(Number(tt) + 3.5 * 3600 * 1000).toISOString().slice(0, 10);
      rows.push({ t: Number(tt), day, c: Number(cc) });
    }
  }
  rows.sort((a, b) => a.t - b.t);
  return { status: r.status, n: rows.length, first: rows.length ? rows[0].day : null,
    last: rows.length ? rows[rows.length - 1].day : null, all: rows };
}`;

// خودسنجیِ بارگذاری: هر سه قطعۀِ بالا داخلِ `page.evaluate` با `eval` اجرا می‌شوند. اگر روزی
// ویرایشِ متنِ فارسی یکِ `${}` ناهنجار یا نقل‌قولِ شکسته بجا بگذارد، بهتر است همین‌جا
// بلافاصله بسوزیم تا وسطِ اجرایِ ۵۵ نمادی (درِ نسخهٔ Phase 5 چنین شکستی بی‌صدا «id حل نشد»
// می‌داد و نمادها یکی‌یکی رد می‌شدند).
[['TOK', TOK], ['RESOLVE', RESOLVE], ['BARS', BARS]].forEach(([n, f]) => {
  if (/\$\{/.test(f)) throw new Error(n + ' هنوز یکِ ${…} تراویش‌نشده دارد');
  try { new Function('return (' + f + ')'); }   // ترجمه می‌کنیم، **اجرا نمی‌کنیم** (fetch در Node نیست)
  catch (e) { throw new Error(n + ' قطعهٔ معتبرِ JS نیست: ' + String(e.message).slice(0, 160)); }
});

const waitAuth = async (page, log, maxMs) => {
  const t0 = Date.now();
  for (;;) {
    const len = await page.evaluate(async (code) => {
      try { const t = await eval(code); return t ? t.length : 0; } catch (e) { return 0; }
    }, TOK).catch(() => 0);
    if (len > 20) return { authed: true, tokenLen: len, waitedMs: Date.now() - t0 };
    if (Date.now() - t0 > maxMs) return { authed: false, tokenLen: 0, waitedMs: Date.now() - t0 };
    log('در انتظارِ نشستِ احرازشده… ' + Math.round((Date.now() - t0) / 1000) + 's');
    await page.waitForTimeout(5000);
  }
};

module.exports = async ({ page, shot, say }) => {
  const steps = [];
  const log = (m) => { steps.push(m); say(m); };
  if (!fs.existsSync(TARGETS)) return { aborted: 'NO-TARGETS-FILE', steps, notes: [TARGETS] };
  const targets = JSON.parse(fs.readFileSync(TARGETS, 'utf8'));
  const syms = targets.symbols.map((s) => ({ sym: s.symbol, ins_code: s.ins_code,
    categories: s.categories, n_pa: s.n_price_adjust, n_sc: s.n_share_change,
    first_day: s.first_day, last_day: s.last_day, n_candles: s.n_candles }));
  log(` targets: ${syms.length} نماد | پوششِ مبدأ از ${targets.source_coverage_start} `);

  await page.goto('https://rahavard365.com/', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(4000);
  // `headless:false` درِ کارگرِ `_audit/ra365_live.js` یکِ پنجرۀِ واقعیِ Edge باز می‌کند؛
  // اگر نشستِ پروفایلِ آزمایشِ پروژه منقضی شده باشد، **منتظرِ لاگینِ خودِ مالک درِ همان
  // پنجره می‌مانیم** (فرم پر نمی‌شود، کنترل امنیتی دور زده نمی‌شود). سقفِ انتظار با
  // RA_AUTH_WAIT_MS تنظیم می‌شود تا اجرایِ بی‌نظارت هم بشود؛ اگر پر نشد `BLOCKED-NO-SESSION`.
  const auth = await waitAuth(page, log, Number(process.env.RA_AUTH_WAIT_MS || 300000));
  log(` نشست: authed=${auth.authed} tokenLen=${auth.tokenLen} waited=${auth.waitedMs}ms`);
  if (!auth.authed) {
    await shot('ra365_phase5f_no_session');
    return { phase: 'phase5f-live-capture', aborted: 'BLOCKED-NO-SESSION', login: auth, steps };
  }

  // وضعیتِ چارتِ مالک **پیش ازِ** هر کاری؛ تا بازگشتِ پایانِ اجرا سنجیدنی باشد، نه فرض.
  let beforeLegend = null;
  try {
    await page.goto(`https://rahavard365.com/asset/${OWNER_HOME_ASSET}/chart`,
      { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(9000);
    beforeLegend = await page.evaluate(() => {
      const t = (e) => (e ? (e.textContent || '').replace(/\s+/g, ' ').trim() : '');
      const el = document.querySelector('[class*="legend" i],[class*="title" i]');
      return t(el) || document.title;
    });
  } catch (e) { log(' پیش‌خوانیِ چارت ناموفق: ' + String(e).slice(0, 70)); }

  // یک evaluate برایِ هر دسته — توکن درِ همان evaluate تازه گرفته می‌شود؛ صفحه عوض نمی‌شود
  // پس مقدارِ window پاک نمی‌گردد و هیچِ کلیکی رویِ چارت لازم نیست.
  const results = [];
  const CH = Number(process.env.RA_CHUNK || 6);
  for (let i = 0; i < syms.length; i += CH) {
    const batch = syms.slice(i, i + CH);
    const got = await page.evaluate(async ({ code, list, tokFn, resolveFn, barsFn }) => {
      const tk = await eval(code);
      if (!tk) return list.map((x) => ({ sym: x.sym, err: 'NO-TOKEN' }));
      const resolve = eval('(' + resolveFn + ')');
      const bars = eval('(' + barsFn + ')');
      const out = [];
      for (const x of list) {
        const rec = { sym: x.sym, ins_code: x.ins_code, identity: null, id: null,
          t7: null, t0: null, error: null };
        try {
          const r = await resolve(tk, x.sym);
          if (r.err) { rec.error = r.err; out.push(rec); continue; }
          rec.id = r.id; rec.identity = { matchedField: r.matchedField, matchedForm: r.matchedForm,
            tradeSymbol: r.tradeSymbol, refName: r.refName, refType: r.refType,
            type_id: r.type_id, exchange: r.exchange, unlisted: r.unlisted,
            candidates: r.candidates, exact: true };
          if (!r.id) { rec.error = 'id-field-missing'; out.push(rec); continue; }
          const a = await bars(tk, r.id, 'type7');
          const b = await bars(tk, r.id, 'type0');
          rec.t7 = { status: a.status, points: a.n, first: a.first, last: a.last, err: a.err };
          rec.t0 = { status: b.status, points: b.n, first: b.first, last: b.last, err: b.err };
          rec.full = { t7: a.all, t0: b.all };
        } catch (e) { rec.error = String(e).slice(0, 120); }
        out.push(rec);
      }
      return out;
    }, { code: TOK, list: batch, resolveFn: RESOLVE, barsFn: BARS.replace('COUNTBACK_', String(COUNTBACK)) })
      .catch((e) => batch.map((x) => ({ sym: x.sym, err: 'evaluate:' + String(e).slice(0, 100) })));
    results.push(...got);
    const okN = got.filter((g) => g.t7 && g.t7.points > 0).length;
    log(` دسته ${Math.floor(i / CH) + 1}: ${okN}/${batch.length} سری گرفت`);
    await page.waitForTimeout(GAP_MS);
  }

  // اسکرین‌شاتِ **منتخب** (نه همه): تعدادِ کم = درخواستِ کمتر و ریسکِ کمترِ لمسِ چارت.
  const pick = [];
  const wantCat = (c) => results.find((r) => r.id && (r.ins_code) && (syms.find((s) => s.sym === r.sym) || {})
    .categories?.includes(c) && !pick.includes(r.sym));
  ['heavy_event', 'unresolved_type', 'near_source_boundary', 'no_event_control', 'mixed',
    'share_change', 'price_adjust', 'new_listing'].forEach((c) => {
    const r = wantCat(c);
    if (r && pick.length < N_SHOTS) pick.push(r.sym);
  });
  results.forEach((r) => { if (r.id && pick.length < N_SHOTS && !pick.includes(r.sym)) pick.push(r.sym); });

  const shots = [];
  for (const sym of pick) {
    const rec = results.find((r) => r.sym === sym);
    if (!rec || !rec.id) continue;
    try {
      await page.goto(`https://rahavard365.com/asset/${rec.id}/chart`,
        { waitUntil: 'domcontentloaded', timeout: 60000 });
      await page.waitForTimeout(9000);
      const f = await shot(`ra365_phase5f_${sym}`);
      const legend = await page.evaluate(() => {
        const t = (e) => (e ? (e.textContent || '').replace(/\s+/g, ' ').trim() : '');
        const el = document.querySelector('[class*="legend" i],[class*="title" i]');
        return t(el) || document.title;
      });
      shots.push({ sym, id: rec.id, file: f, legend });
      await page.keyboard.press('Escape').catch(() => {});
      log(`  shot ${sym} → ${f}`);
    } catch (e) { shots.push({ sym, id: rec.id, error: String(e).slice(0, 90) }); }
  }

  // بازگرداندنِ چارت بهِ همان جایِ اول + اثباتش
  let afterLegend = null;
  try {
    await page.goto(`https://rahavard365.com/asset/${OWNER_HOME_ASSET}/chart`,
      { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(9000);
    afterLegend = await page.evaluate(() => {
      const t = (e) => (e ? (e.textContent || '').replace(/\s+/g, ' ').trim() : '');
      const el = document.querySelector('[class*="legend" i],[class*="title" i]');
      return t(el) || document.title;
    });
  } catch (e) { log(' بازگردانیِ چارت ناموفق: ' + String(e).slice(0, 70)); }

  const summary = results.map((r) => ({
    sym: r.sym, ins_code: r.ins_code, id: r.id, identity: r.identity, error: r.error,
    t7_status: r.t7 && r.t7.status, t7_points: r.t7 && r.t7.points,
    t7_first: r.t7 && r.t7.first, t7_last: r.t7 && r.t7.last, t7_err: r.t7 && r.t7.err,
    t0_status: r.t0 && r.t0.status, t0_points: r.t0 && r.t0.points,
    t0_first: r.t0 && r.t0.first, t0_last: r.t0 && r.t0.last, t0_err: r.t0 && r.t0.err,
  }));
  const gotN = summary.filter((s) => s.t7_points > 0).length;
  log(` جمعِ بسته: ${gotN}/${syms.length} نماد سریِ type7 گرفت | اسکرین‌شات=${shots.length} `);

  return {
    phase: 'phase5f-live-capture',
    ranAt: new Date().toISOString(),
    captureWindow: { from: FROM_ISO, countback: COUNTBACK, resolution: 'D' },
    login: { authed: auth.authed, waitedMs: auth.waitedMs },
    tokenLenOnly: auth.tokenLen,
    targetsFile: '_audit/ra365_phase5f_targets.json',
    sourceCoverageStart: targets.source_coverage_start,
    ownerChart: { asset: OWNER_HOME_ASSET, legendBefore: beforeLegend, legendAfter: afterLegend,
      restored: !!beforeLegend && beforeLegend === afterLegend },
    summary, counts: { wanted: syms.length, gotBars: gotN, shots: shots.length },
    shots,
    // سری‌هایِ کامل جداگانه می‌نشینند تا `summary` خواندنی بماند
    series: results.map((r) => ({ sym: r.sym, id: r.id, full: r.full || null })),
    notes: [
      'هویتِ هر نماد با تطبیقِ **دقیقِ** فیلدِ هویتیِ خودِ رهاورد بسته شد؛ fallbackِ «اولینِ نتیجه» حذف شده است.',
      'سریِ type0 (خام) هم گرفته شد تا اثباتِ هویت درِ Stage 6 با مقابلهٔ کندلِ خام برِ `price_history` انجام شود، نه با نام.',
      'فقط طولِ توکن ثبت شد؛ هیچِ رمز/کوکی/توکنی درِ فایل نیامده است.',
    ],
    steps,
  };
};
