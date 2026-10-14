// _audit/ra365_job_meta.js — خوانشِ **فقط‌خواندنیِ** متادیتایِ خودِ مرجع برایِ ماتریسِ
// تایم‌فریم/مقیاس — بی‌DOM و بی‌کلیک.
// چرا این روش: hover و caret برایِ بازکردنِ flyout بی‌نتیجه ماند (flyout lazy render است) و
// کلیک رویِ گروه، ابزارِ پیش‌فرض را فعال می‌کند → رویِ چارتِ مالک انجام نمی‌دهیم. ولی خودِ
// سایت درِ endpointهایی که همین حساب هر روز صدا می‌زند، فهرستِ رسمیِ resolutionها و
// ویژگی‌هایِ نماد را می‌دهد. این دادهٔ خواندنیِ همان حساب است، نه عبورِ ازِ محدودیت.
// ایمنی: هیچِ مقدارِ احراز هویتی خوانده/چاپ/ذخیره نمی‌شود؛ فقطِ نامِ کلید و شمار/مقادیرِ
// غیرحساسِ متادیتا.
const GETJSON = async (url) => {
  try {
    const r = await fetch(url, { credentials: 'include' });
    const t = await r.text();
    let j = null; try { j = JSON.parse(t); } catch (e) { /* متن */ }
    return { status: r.status, keys: j && typeof j === 'object' ? Object.keys(j).slice(0, 40) : [], len: t.length, j };
  } catch (e) { return { error: String(e).slice(0, 120) }; }
};

module.exports = async ({ page, say }) => {
  const out = { notes: [] };
  await page.goto('https://rahavard365.com/asset/453/chart', { waitUntil: 'domcontentloaded', timeout: 90000 })
    .catch((e) => out.notes.push('goto: ' + String(e).slice(0, 90)));
  await page.waitForTimeout(16000);

  const res = await page.evaluate(async () => {
    const g = async (u, opt) => { try { const r = await fetch(u, Object.assign({ credentials: 'include' }, opt || {})); const t = await r.text(); let j = null; try { j = JSON.parse(t); } catch (e) {} return { s: r.status, len: t.length, j }; } catch (e) { return { err: String(e).slice(0, 90) }; } };
    let tok = null;
    for (let a = 0; a < 8 && !tok; a++) {
      const t = await g('/api/v2/accounts/access-token');
      const j = t.j; const v = [];
      for (const o of [j, j && j.data, j && j.data && j.data.data]) {
        if (typeof o === 'string') v.push(o);
        else if (o && typeof o === 'object') for (const k in o) if (typeof o[k] === 'string') v.push(o[k]);
      }
      tok = v.find((x) => x && x.length > 20) || null;
      if (!tok) await new Promise((r) => setTimeout(r, 1500));
    }
    const H = { headers: { Authorization: 'Bearer ' + tok, 'application-name': 'rahavard', platform: 'web', 'content-type': 'application/json' } };
    const tk = 'exchange.asset:453:real_close:type7';
    // باگِ دورِ قبل: H ساخته شد ولی به هیچ فراخوانی‌ای داده نشد → هر چهار پاسخ ۴۰۴/۴۰۱
    // بود درحالی‌که خودِ توکن سالم گرفته شده بود (طولِ ۶۳۲ و epoch=۲۰۰ شاهدش). حالا
    // هدر صریح پاس می‌شود تا ۴۰۱ معنایِ «محدودیتِ مبدأ» بدهد نه «تستِ من غلط بود».
    const withH = (u) => g(u, H);
    // فقطِ متادیتایِ **ابزار/سری** خوانده می‌شود. دو endpointِ `chart/settings` و
    // `default-settings` حذف شدند چون تنظیماتِ **شخصیِ** حسابِ مالک را برمی‌گردانند و
    // شناسۀِ حساب نمی‌بایست درِ فایلِ commit‌شدنی hardcode شود؛ ماتریسِ تایم‌فریم بهِ
    // آنها نیاز ندارد (`symbols` فهرستِ resolution را دارد، `configs` پیکربندیِ ابزار).
    const symbols = await withH('/api/v2/chart/symbols?ticker=' + encodeURIComponent(tk));
    const configs = await withH('/api/v2/chart/configs?ticker=' + encodeURIComponent(tk));
    const ep = await g('/api/v2/time/epoch');
    return { tokLen: tok ? tok.length : 0, symbols, configs, ep };
  });
  out.tokenLengthOnly = res.tokLen;

  const pick = (label, r) => {
    if (!r) return null;
    const j = r.j;
    let d = j && j.data !== undefined ? j.data : j;
    // دورِ قبل «keys خالی» گزارش شد و من آن را «بی‌داده» خواندم؛ دلیلش شکلِ پاسخ بود:
    // این endpointها آرایه می‌دهند (فهرستِ ابزار/سری)، پس Object.keys رویِ خودِ آرایه
    // معنایی ندارد. حالا first-element باز می‌شود تا نامِ کلیدها و分辨率 دیده شود.
    if (Array.isArray(d)) { out[label + '_array_len'] = d.length; d = d[0] || {}; }
    if (d && typeof d === 'object' && d.results) d = d.results;
    const keys = d && typeof d === 'object' && !Array.isArray(d) ? Object.keys(d) : [];
    const interesting = {};
    ['supported_resolutions', 'resolutions', 'interval', 'intervals', 'timeframes', 'pricescale',
     'minimum_movement', 'fractional', 'timezone', 'session', 'type', 'name', 'description',
     'intraday_multipliers', 'allowed_intervals', 'calc_price_index', 'real_close'].forEach((k) => {
      if (keys.includes(k)) interesting[k] = Array.isArray(d[k]) ? d[k].slice(0, 40) : d[k];
    });
    out[label] = { status: r.s, bytes: r.len, keys: keys.slice(0, 60), interesting };
    say(label + ': status=' + r.s + ' bytes=' + r.len + ' keys=' + keys.slice(0, 20).join(','));
    if (Object.keys(interesting).length) say('   → ' + JSON.stringify(interesting).slice(0, 700));
  };
  pick('symbols', res.symbols);
  pick('configs', res.configs);
  out.epoch = res.ep && res.ep.s;
  out.notes.push('فقطِ متادیتایِ خواندنی؛ هیچِ کلیدِ احراز هویتی درِ خروجی نیست (طولِ توکن = ' + res.tokLen + ').');
  out.notes.push('settings برایِ account «me» ممکن است ۴۰۴ دهد؛ اگر داد، یعنی فهرستِ resolution درِ این endpoint نیست و ماتریس باید بهِ DOM/مشاهده تکیه کند.');
  return out;
};
