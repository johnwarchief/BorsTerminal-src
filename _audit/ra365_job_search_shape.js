// _audit/ra365_job_search_shape.js — خوانشِ **شکلِ واقعی** پاسخِ `/api/v2/search` (فقط‌خواندنی)
// چرا: هارنسِ `ra365_job_phase5f_capture.js` هویتِ نماد را با تطبیقِ **دقیق** می‌سنجد (قیدِ
// مأموریت: «از نگاشت مبتنی بر شباهت نام … به‌عنوان اثبات هویت استفاده نکن»). نسخهٔ پیشینِ
// پروژه `list.find(... .includes(s)) || list[0]` بود که اولینِ نتیجهٔ بی‌ربط را می‌پذیرفت.
// اما اسمِ فیلدها را **حدس** زدم، و سنجشِ زنده نشان داد هر ۵۵ نماد `no-exact-match` می‌دهند.
// پس پیش ازِ هر ادعا، خودِ پاسخ را می‌خوانم: کلیدها، نمونۀِ اولینِ آیتم، و اینکه کدام فیلد
// با نمادِ TSETMC یکی است. توکن فقط درِ حافظه مصرف می‌شود؛ درِ خروجی **فقط طولِ** آن می‌آید.
const WANT = (process.env.RA_SHAPE || "فولاد,وبملت,كگل,طلا").split(",");

const TOK = `(async()=>{for(let a=0;a<40;a++){try{const t=await fetch('/api/v2/accounts/access-token',{credentials:'include'});const x=await t.text();if(!x){await new Promise(r=>setTimeout(r,3000));continue;}let j=null;try{j=JSON.parse(x)}catch(e){}const v=[];for(const o of [j,j&&j.data,j&&j.data&&j.data.data]){if(typeof o==='string')v.push(o);else if(o&&typeof o==='object')for(const k in o)if(typeof o[k]==='string')v.push(o[k]);}const s=v.find(x=>x&&x.length>20);if(s)return s;}catch(e){}await new Promise(r=>setTimeout(r,3000));}return null;})()`;

module.exports = async ({ page, say, shot }) => {
  const notes = [];
  await page.goto('https://rahavard365.com/', { waitUntil: 'domcontentloaded', timeout: 90000 });
  // سنجشِ همین دور: گرفتنِ توکن ۲۹۳ ثانیه طول کشید (دورِ پیش <۱s) — پس صبرِ کوتاه
  // «نشست نداریم» را جعل می‌کند. تا ~۲ دقیقه تلاش می‌کنیم و بعد صادق می‌گوییم نگرفت.
  await page.waitForTimeout(10000);
  const res = await page.evaluate(async ({ code, list }) => {
    const tk = await eval(code);
    if (!tk) return { authed: false };
    const out = [];
    for (const s of list) {
      const r = await fetch('/api/v2/search?keyword=' + encodeURIComponent(s),
        { headers: { Authorization: 'Bearer ' + tk, 'application-name': 'rahavard', platform: 'web' } });
      const txt = await r.text();
      let j = null; try { j = JSON.parse(txt); } catch (e) { }
      const rec = { q: s, status: r.status, bytes: txt.length, parsed: !!j };
      if (j) {
        rec.topKeys = Object.keys(j).slice(0, 8);
        const paths = { "j.data": j.data, "j.data.items": j.data && j.data.items, "j.items": j.items };
        rec.shapeOfData = j.data && typeof j.data === 'object' && !Array.isArray(j.data)
          ? Object.keys(j.data).slice(0, 10) : (Array.isArray(j.data) ? 'ARRAY:' + j.data.length : null);
        let arr = null;
        for (const k of ["j.data.items", "j.data", "j.items"]) {
          const v = paths[k];
          if (Array.isArray(v)) { arr = v; rec.arrPath = k; break; }
        }
        rec.n = arr ? arr.length : 0;
        if (arr && arr.length) {
          rec.itemKeys = Object.keys(arr[0]).slice(0, 24);
          // نمونهٔ کاملِ اولینِ دو آیتم (بدنه‌ای که نام/کدِ نماد در آن است؛ هیچ دادهٔ
          // احراز هویتی در پاسخِ جست‌وجو نیست)
          rec.samples = arr.slice(0, 2).map((x) => JSON.stringify(x).slice(0, 420));
        }
      } else {
        rec.head = txt.slice(0, 120);
      }
      out.push(rec);
      await new Promise((r2) => setTimeout(r2, 400));
    }
    return { authed: true, tokenLen: tk.length, results: out };
  }, { code: TOK, list: WANT }).catch((e) => ({ err: String(e).slice(0, 200) }));

  notes.push('پاسخِ جست‌وجو فقط خوانده شد؛ هیچِ کلیکی رویِ چارت و هیچِ فرمی انجام نشد.');
  if (res.authed) notes.push('طولِ توکن = ' + res.tokenLen + ' (مقدارش ثبت نمی‌شود)');
  return { res, notes, shot: await shot('ra365_search_shape') };
};
