// job: کشفِ کانالِ دادۀِ مرجع (ره‌آورد ۳۶۵) و ثبتِ کندل‌هایِ روزانه/هفتگی
// فقط خواندنی: درِ همانِ نشستِ لاگین‌شده، خودِ API هایِ رابط را صدا می‌زند (fetch با کوکیِ مرورگر).
// هیچ رمز/کوکی/توکنی خوانده یا ثبت نمی‌شود؛ account id هم هاردکد نشده، از پاسخِ خودِ رابط می‌آید.
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

const SUF = ['type7', 'type1', 'type2', 'type3', 'type4', 'type5', 'type6', 'type0'];

module.exports = async ({ page, say, probe, shot }) => {
  const steps = [];
  const log = (m) => { steps.push(m); say(m); };

  const J = async (url) => {
    const r = await page.evaluate(async (u) => {
      try {
        const res = await fetch(u, { credentials: 'include' });
        const text = await res.text();
        return { status: res.status, ok: res.ok, text: text.slice(0, 400000) };
      } catch (e) {
        return { status: -1, ok: false, text: 'ERR ' + String(e).slice(0, 200) };
      }
    }, url);
    let json = null;
    try { json = JSON.parse(r.text); } catch { /* not json */ }
    return { status: r.status, ok: r.ok, json, head: r.text.slice(0, 900) };
  };

  await page.goto('https://rahavard365.com/asset/453/chart', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(9000);
  const pre = await probe();
  log('opened chart page; nodes=' + pre.nodes + ' loginButton=' + pre.loginButtonPresent);

  // ---- فازِ الف: کشفِ واژگانِ ticker (priceType و adjustment) ----
  const discovery = {};
  for (const t of ['exchange.asset:453:real_close:type7']) {
    discovery['symbols:' + t] = await J('/api/v2/chart/symbols?ticker=' + encodeURIComponent(t));
    discovery['configs:' + t] = await J('/api/v2/chart/configs?ticker=' + encodeURIComponent(t));
  }
  // تنظیماتِ پیش‌فرضِ نشستن → account id و entity id ازِ خودِ پاسخ
  const def = await J('/api/v3/chart/default-settings?entity_id=453&entity_type=exchange.asset');
  discovery['default-settings'] = def;
  const acct =
    (def.json && (def.json.account_id || (def.json.data && def.json.data.account_id))) || null;
  log('default-settings status=' + def.status + ' accountIdDiscovered=' + Boolean(acct));

  const settings = acct
    ? await J('/api/v2/chart/settings?account_id=' + acct)
    : { status: -1, ok: false, json: null, head: 'no accountId in response' };
  discovery['settings'] = settings;

  const shotName = await shot('ra365_bars_view');

  // ---- فازِ ب: تفکیکِ تعدیل‌ها (کدام type همان «عملکردی» است) ----
  const adjProbe = [];
  for (const suf of SUF) {
    const ticker = 'exchange.asset:453:real_close:' + suf;
    const from = '2026-08-01T00:00:00Z';
    const to = '2026-10-13T00:00:00Z';
    const url =
      '/api/v2/chart/bars?countback=200&symbol=' + encodeURIComponent(ticker) +
      '&resolution=D&from=' + from + '&to=' + to;
    const r = await J(url);
    const bars = r.json && Array.isArray(r.json.data) ? r.json.data : null;
    adjProbe.push({
      ticker,
      status: r.status,
      n: bars ? bars.length : 0,
      head: bars ? null : r.head.slice(0, 300),
      last3: bars ? bars.slice(-3).map((b) => ({ utc: b.utc, o: b.open, h: b.high, l: b.low, c: b.close, v: b.volume })) : null,
      fractional: bars ? bars.some((b) => Math.abs(b.close - Math.round(b.close)) > 1e-9) : null,
    });
  }
  log('adjustment sweep: ' + adjProbe.map((a) => a.ticker.split(':')[3] + '=' + a.n + (a.fractional ? '/frac' : '/int')).join(' '));

  // ---- فازِ پ: گنجینۀِ نمادها، روزانه و هفتگی، با هر دو نوعِ دادۀِ قابلِ مشاهده ----
  const windows = { daily: [], weekly: [] };
  const corpus = [];
  for (const a of ASSETS) {
    for (const suf of ['type7', 'type1']) {
      for (const res of ['D', 'W']) {
        const ticker = `exchange.asset:${a.id}:real_close:${suf}`;
        const from = res === 'D' ? '2026-01-01T00:00:00Z' : '2024-01-01T00:00:00Z';
        const to = '2026-10-13T00:00:00Z';
        const url =
          '/api/v2/chart/bars?countback=' + (res === 'D' ? 300 : 200) +
          '&symbol=' + encodeURIComponent(ticker) + '&resolution=' + res +
          '&from=' + from + '&to=' + to;
        const r = await J(url);
        const bars = r.json && Array.isArray(r.json.data) ? r.json.data : [];
        const tag = { id: a.id, sym: a.sym, suf, res, status: r.status, n: bars.length };
        if (bars.length) {
          tag.firstUtc = bars[0].utc;
          tag.lastUtc = bars[bars.length - 1].utc;
          const tail = bars.slice(-14);
          (res === 'D' ? windows.daily : windows.weekly).push({
            id: a.id, sym: a.sym, suf,
            bars: tail.map((b) => ({ utc: b.utc, t: b.time, o: b.open, h: b.high, l: b.low, c: b.close, v: b.volume })),
          });
          // روزهایِ اکتبرِ ۲۰۲۶ (محلِ ادعایِ نبودِ جلسۀ ۱۰-۱۰)
          tag.oct = bars
            .filter((b) => /^2026-10/.test(String(b.utc)))
            .map((b) => ({ utc: b.utc, o: b.open, h: b.high, l: b.low, c: b.close, v: b.volume }));
        }
        corpus.push(tag);
        log(`bars ${a.sym} ${suf} ${res} status=${r.status} n=${bars.length}`);
      }
    }
  }

  // رویدادهایِ شرکتیِ مرجع (برایِ سنجشِ تعدیلِ شبهرن و ولانا)
  const marks = [];
  for (const a of ASSETS) {
    const r = await J('/api/v2/chart/timescale_marks?ticker=' + encodeURIComponent(`exchange.asset:${a.id}:real_close:type7`) + '&resolution=D');
    marks.push({ id: a.id, sym: a.sym, status: r.status, head: (r.json ? JSON.stringify(r.json) : r.head).slice(0, 1200) });
  }

  fs.writeFileSync(path.join(__dirname, 'ra365_bars_raw.json'),
    JSON.stringify({ windows, corpus, marks }, null, 1), 'utf8');

  return {
    steps,
    pre: { url: pre.url, loginButtonPresent: pre.loginButtonPresent, logoutTextPresent: pre.logoutTextPresent },
    shotName,
    discoverySummary: Object.fromEntries(
      Object.entries(discovery).map(([k, v]) => [
        k,
        { status: v.status, topKeys: v.json ? Object.keys(v.json).slice(0, 14) : null, head: v.json ? null : v.head.slice(0, 400) },
      ]),
    ),
    discoveryRaw: {
      symbols: discovery['symbols:exchange.asset:453:real_close:type7'],
      configs: discovery['configs:exchange.asset:453:real_close:type7'],
      defaultSettings: discovery['default-settings'],
    },
    adjProbe,
    corpus,
    marks,
    rawFile: '_audit/ra365_bars_raw.json',
  };
};
