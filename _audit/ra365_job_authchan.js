// job: تشخیصِ کانالِ احراز هویتِ درخواست‌هایِ چارت (بدونِ خواندن/ذخیرۀ هیچ رمز یا توکن)
// خروجی فقط: نامِ سرسترها، طول/پیشوندِ مجازِ سرسترها، وضعیت‌ها، و اینکه آیا fetchِ درون‌صفحۀِ خام قبول می‌شود.
module.exports = async ({ page, say, probe }) => {
  const reqs = [];
  page.on('request', (r) => {
    const u = r.url();
    if (!/rahavard365\.com\/api\//.test(u)) return;
    const h = r.headers();
    const shape = {};
    for (const k of Object.keys(h)) {
      const v = String(h[k] || '');
      // سرسترهایِ حساس: فقط نام و طول. هیچ پیشوند/مقداری ثبت نمی‌شود.
      if (/authorization|x-api|token|cookie|bearer/i.test(k)) shape[k] = { namesOnly: true, len: v.length };
      else shape[k] = { value: v.slice(0, 40) };
    }
    reqs.push({ url: u.slice(0, 170), method: r.method(), resourceType: r.resourceType(), frame: r.frame().url().slice(0, 120), headers: shape });
  });

  const responses = [];
  page.on('response', (r) => {
    if (/rahavard365\.com\/api\/v[23]\/chart\/bars/.test(r.url())) responses.push({ url: r.url().slice(0, 200), status: r.status() });
  });

  await page.goto('https://rahavard365.com/asset/453/chart', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(12000);

  const frames = page.frames().map((f) => ({ url: f.url().slice(0, 140), name: f.name() }));

  // فقط وضعیت، نه محتوا
  const rawFetch = await page.evaluate(async () => {
    const out = {};
    const r1 = await fetch('/api/v2/chart/bars?countback=5&symbol=' + encodeURIComponent('exchange.asset:453:real_close:type7') + '&resolution=D&from=2026-09-01T00:00:00Z&to=2026-10-13T00:00:00Z', { credentials: 'include' });
    out.barsPlain = r1.status;
    const r2 = await fetch('/api/v2/accounts/access-token', { credentials: 'include' });
    out.tokenEndpointStatus = r2.status;
    // ساختارِ پاسخِ توکن: فقط نامِ کلیدها و نوعِ مقدار. مقدار هرگز بیرون نمی‌رود.
    try {
      const j = await r2.json();
      out.tokenShape = j && typeof j === 'object'
        ? Object.fromEntries(Object.entries(j).map(([k, v]) => [k, typeof v === 'string' ? { type: 'string', len: v.length } : { type: typeof v }]))
        : { type: typeof j };
      // آیا توکن درِ localStorage/sessionStorage هست؟ فقط نامِ کلیدها
      out.lsKeys = Object.keys(localStorage).slice(0, 40);
      out.ssKeys = Object.keys(sessionStorage).slice(0, 40);
    } catch (e) {
      out.tokenShape = { err: String(e).slice(0, 80) };
    }
    return out;
  });

  // تلاشِ دوم: fetch با همان توکنی که خودِ اپلیکیشن می‌سازد — مقدار به Node برنمی‌گردد
  const withBearer = await page.evaluate(async () => {
    let r;
    try { r = await fetch('/api/v2/accounts/access-token', { credentials: 'include' }); } catch (e) { return { step: 'token', status: 'ERR ' + String(e).slice(0, 80) }; }
    if (!r.ok) return { step: 'token', status: r.status };
    let tok = null;
    try {
      const j = await r.json();
      const cand = [].concat(j, j && j.data, j && j.result).filter(Boolean);
      for (const c of cand) {
        if (typeof c === 'string' && c.length > 20) { tok = c; break; }
        if (c && typeof c === 'object') {
          for (const k of ['access_token', 'accessToken', 'token', 'jwt']) {
            if (typeof c[k] === 'string' && c[k].length > 20) { tok = c[k]; break; }
          }
        }
        if (tok) break;
      }
    } catch (e) { return { step: 'tokenParse', err: String(e).slice(0, 80) }; }
    if (!tok) return { step: 'token', status: 'not-found-in-shape' };
    const path = '/api/v2/chart/bars?countback=5&symbol=' + encodeURIComponent('exchange.asset:453:real_close:type7') + '&resolution=D&from=2026-09-01T00:00:00Z&to=2026-10-13T00:00:00Z';
    const tries = {};
    for (const h of [['Authorization', 'Bearer ' + tok], ['Authorization', tok], ['token', tok], ['x-access-token', tok]]) {
      const res = await fetch(path, { headers: Object.fromEntries([h]), credentials: 'include' });
      const txt = await res.text();
      let n = null, keys = null, firstUtc = null;
      try { const j = JSON.parse(txt); n = Array.isArray(j.data) ? j.data.length : null; keys = Object.keys(j).slice(0, 8); firstUtc = j.data && j.data[0] && j.data[0].utc; } catch { /* ignore */ }
      // هیچ مقدارِ سرستر یا توکنی بیرون نمی‌رود؛ فقط نامِ سرستر، طولِ توکن و وضعیت
      tries[h[0] === 'Authorization' ? (h[1].startsWith('Bearer') ? 'Authorization:Bearer' : 'Authorization:bare') : h[0]] = { status: res.status, n, keys, firstUtc, head: n === null ? txt.slice(0, 200) : null };
      if (n !== null && n > 0) break;
    }
    return { step: 'barsWithBearer', tokenLength: tok.length, tried: tries };
  });

  const barsReq = reqs.filter((q) => /chart\/bars/.test(q.url));
  return {
    loginButtonPresent: (await probe()).loginButtonPresent,
    frames,
    barsRequests: barsReq,
    barsResponses: responses,
    allApiRequests: reqs.map((q) => ({ url: q.url, hasAuth: Object.keys(q.headers).some((k) => /authorization/i.test(k)), cookieSent: Object.keys(q.headers).some((k) => /^cookie$/i.test(k)) })),
    rawFetch,
    withBearer,
  };
};
