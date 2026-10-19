// _audit/ra365_deepbars.js — گنجینۀِ روزانۀِ مرجع تا اولِ تاریخچةِ خودی (فقط خواندنی)
//
// چرا: سنجشِ پاریتیِ تعدیل تا اینجا رویِ ۶۰۱ روزِ آخر بود (`ra365_ref_bars.json`).
// زنجیرۀِ ضریبِ خودی تا ۰٫۰۰۱۶ پایین می‌آید (۲۰۰۷-۰۳-۱۱)؛ آن ۱۹ سالِ تاریخ هیچ
// شاهدی از مرجع نداشت. این اسکریپت همان رابطِ خودیِ مرجع را درِ همان نشستِ
// لاگین‌شدۀِ مالک صدا می‌زند (fetch هم‌ریشه؛ کوکی را ما نمی‌خوانیم و هیچ‌جا
// ذخیره نمی‌شود) و کندل‌هایِ روزانه را با هر دو مبنای type0/type7 می‌گیرد.
//
// اجرا: node _audit/ra365_deepbars.js      (نیاز: Edgeِ بازِ CDP پورت ۹۳۳۳)
const fs = require('fs');
const path = require('path');
const pw = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright-core'));

const PORT = Number(process.env.RA_CDP_PORT || 9333);
const OUT = path.join(__dirname, 'ra365_folad_deep_daily.json');
const TICKERS = { type0: 'exchange.asset:453:real_close:type0', type7: 'exchange.asset:453:real_close:type7' };

(async () => {
  const browser = await pw.chromium.connectOverCDP(`http://127.0.0.1:${PORT}`);
  const pages = [];
  for (const ctx of browser.contexts()) for (const p of ctx.pages()) pages.push(p);
  const page = pages.find((p) => (p.url() || '').includes('rahavard365.com'));
  if (!page) throw new Error(' Rahavard page not found in the CDP browser; tabs: ' + pages.map((p) => p.url()).join(' , '));

  // وضعیتِ نشست، بی‌خواندنِ هیچ کوکیِ توکنی: آیا صفحۀ چارت «ورود» می‌خواهد؟
  const state = await page.evaluate(() => ({
    url: location.href,
    asksLogin: /ورود|ثبت‌نام/.test(document.body.innerText || '') &&
               !!document.querySelector('a[href*="login"],button[onclick*="login"]'),
    bodyHead: (document.body.innerText || '').replace(/\s+/g, ' ').slice(0, 200),
  }));

  const grab = async (ticker, countback) => {
    // توکن فقط درِ بافتِ همانِ صفحه خوانده و همان‌جا مصرف می‌شود؛ هیچ رمز یا
    // توکنی به Node، لاگ یا فایلِ خروجی برنمی‌گردد (همان قانونِ
    // `_audit/ra365_job_authchan.js`).
    const url = '/api/v2/chart/bars?countback=' + countback + '&symbol=' + encodeURIComponent(ticker) +
      '&resolution=D&from=2026-10-18T00:00:00Z&to=2026-10-19T00:00:00Z';
    return page.evaluate(async (u) => {
      const hdrs = {};
      let tok = null;
      try {
        const rt = await fetch('/api/v2/accounts/access-token', { credentials: 'include' });
        if (rt.ok) {
          const jt = await rt.json();
          const cand = [].concat(jt, jt && jt.data, jt && jt.result).filter(Boolean);
          for (const c of cand) {
            if (typeof c === 'string' && c.length > 20) { tok = c; break; }
            if (c && typeof c === 'object') {
              for (const k of ['access_token', 'accessToken', 'token', 'jwt']) {
                if (typeof c[k] === 'string' && c[k].length > 20) { tok = c[k]; break; }
              }
            }
            if (tok) break;
          }
        }
      } catch { /* بی‌توکن هم امتحان می‌شود */ }
      if (tok) hdrs.Authorization = 'Bearer ' + tok;
      const res = await fetch(u, { headers: hdrs, credentials: 'include' });
      const text = await res.text();
      let data = null;
      try { data = JSON.parse(text).data; } catch { /* not json */ }
      return { status: res.status, usedToken: !!tok, n: Array.isArray(data) ? data.length : 0,
               bars: Array.isArray(data) ? data : null, head: text.slice(0, 200) };
    }, url);
  };

  const rep = { ranAt: new Date().toISOString(), page: state.url, session: state, series: {} };
  for (const [k, ticker] of Object.entries(TICKERS)) {
    const r = await grab(ticker, 5200);
    rep.series[k] = {
      ticker, status: r.status, usedToken: r.usedToken, n: r.n, head: r.n ? null : r.head,
      firstUtc: r.bars && r.bars[0] ? r.bars[0].utc : null,
      lastUtc: r.bars && r.bars[r.bars.length - 1] ? r.bars[r.bars.length - 1].utc : null,
      bars: (r.bars || []).map((b) => ({
        utc: b.utc, t: b.time, o: b.open, h: b.high, l: b.low, c: b.close, v: b.volume })),
    };
    console.log(`${k}: status=${r.status} n=${r.n} ${rep.series[k].firstUtc} -> ${rep.series[k].lastUtc}` +
      (r.n ? '' : ' head=' + r.head));
  }

  fs.writeFileSync(OUT, JSON.stringify(rep, null, 1), 'utf8');
  console.log('written: ' + OUT);
  await browser.close();
})().catch((e) => { console.error('FAILED: ' + ((e && e.stack) || e)); process.exit(1); });
