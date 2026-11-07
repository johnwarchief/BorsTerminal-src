// job: یافتنِ asset idِ هر نمادِ گنجینە از رابطۀِ خودِ ره‌آورد (/api/v2/search?keyword=)
// فقط خواندنی. برایِ هر نماد، همه‌یِ زدن‌هایِ احتمالی ثبت می‌شود تا انتخابِ یکتا با نامِ کامل تأیید شود.
const fs = require('fs');
const path = require('path');

const SYMS = path.join(__dirname, 'ra365_symbols.txt');
const OUT = path.join(__dirname, 'ra365_ids_raw.json');

const CALLER = fs.readFileSync(path.join(__dirname, 'ra365_job_fetch.js'), 'utf8')
  .match(/const CALLER = `([\s\S]*?)`;/)[1];

module.exports = async ({ page, say, shot, probe }) => {
  const steps = [];
  const log = (m) => { steps.push(m); say(m); };
  await page.goto('https://rahavard365.com/asset/453/chart', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(9000);
  log('loginButton=' + (await probe()).loginButtonPresent);
  const inPage = (body) => page.evaluate(new Function('return (async () => {' + CALLER + body + '})()'));

  const symbols = fs.readFileSync(SYMS, 'utf8').split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
  log('symbols=' + symbols.length);

  // شکلِ پاسخِ یک پرس‌وجویِ نمونه
  const shape = await inPage(`
    const r = await call('/api/v2/search?keyword=' + encodeURIComponent('ولانا'));
    return { status: r.status, keys: r.json ? Object.keys(r.json) : null, sample: JSON.stringify(r.json).slice(0, 1500), raw: r.raw };
  `);
  log('sample status=' + shape.status);

  const res = {};
  for (const s of symbols) {
    const r = await inPage(`
      const q = await call('/api/v2/search?keyword=' + encodeURIComponent(${JSON.stringify(s)}));
      const j = q.json;
      const arr = j && (j.data || j.results || j.items || (j.data && j.data.results));
      const list = Array.isArray(arr) ? arr : (arr && Array.isArray(arr.assets) ? arr.assets : []);
      return { status: q.status, topKeys: j ? Object.keys(j) : null, n: list.length,
        hits: list.slice(0, 8).map(h => JSON.stringify(h).slice(0, 420)), raw: q.raw ? String(q.raw).slice(0, 200) : null };
    `);
    res[s] = r;
    log(`${s} status=${r.status} hits=${r.n}` + (r.n ? ' | ' + (r.hits[0] || '').slice(0, 90) : ' | ' + String(r.raw).slice(0, 90)));
  }
  fs.writeFileSync(OUT, JSON.stringify({ shape, res }, null, 1), 'utf8');
  const shotName = await shot('ra365_ids_view');
  return {
    steps,
    shotName,
    shapeStatus: shape.status,
    shapeSample: shape.sample,
    per: Object.fromEntries(Object.entries(res).map(([k, v]) => [k, { status: v.status, n: v.n }])),
    firstHitSample: res[symbols[0]] && res[symbols[0]].hits,
    rawFile: '_audit/ra365_ids_raw.json',
  };
};
