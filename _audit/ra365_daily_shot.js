// _audit/ra365_daily_shot.js — مرجع درِ **روزانه**، درِ یکِ تبِ جدا
//
// چرا تبِ جدا: چارتِ خودِ مالک رویِ همانِ نماد ترسیم‌هایِ شخصی دارد و AutoSave
// روشن است؛ این اسکریپت هرگز آن تب را باز نمی‌کند و هیچ ابزاری رویِ صحنه
// نمی‌سازد، نمی‌حرکت می‌دهد و حذف نمی‌کند. اینجا فقط بازۀِ زمانیِ یکِ تبِ تازه
// عوض می‌شود و متنِ برچسبِ OHLC خوانده می‌شود (فقط خواندنی).
//
// اجرا: node _audit/ra365_daily_shot.js      (Edgeِ CDP پورت ۹۳۳۳ باید باز باشد)
const fs = require('fs');
const path = require('path');
const pw = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright-core'));

const PORT = Number(process.env.RA_CDP_PORT || 9333);
const ROOT = path.join(__dirname, '..');
const OUT = path.join(ROOT, '_audit', 'ra365_daily_shot.json');
const URL = 'https://rahavard365.com/asset/453/chart';

const readLegend = () => {
  const txt = (document.body.innerText || '').replace(/\s+/g, ' ');
  const m = txt.match(/(O|باز|open)\s*[:\s]*([\d٬.,]+)/i);
  const o = txt.match(/([^\n]{0,160}\b(?:O|H|L|C)\b[^\n]{0,160})/);
  return { sample: o ? o[1] : null, ohlcFound: !!m };
};

(async () => {
  const browser = await pw.chromium.connectOverCDP(`http://127.0.0.1:${PORT}`);
  const ctx = browser.contexts()[0];
  const page = await ctx.newPage();
  const rep = { ranAt: new Date().toISOString(), url: URL, steps: [] };
  const say = (m) => { rep.steps.push(m); console.log(m); };

  await page.setViewportSize({ width: 1600, height: 900 });
  await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 90000 });
  await page.waitForTimeout(14000);

  const frames = page.frames().map((f) => ({ url: (f.url() || '').slice(0, 90), name: f.name() }));
  say('frames: ' + JSON.stringify(frames));

  const widget = page.frames().find((f) => (f.url() || '').startsWith('blob:')) || page.mainFrame();

  // چه چیزهایی برایِ انتخابِ بازۀِ زمانی رویِ صحنه هست؟ (کشف، نه حدس)
  const buttons = await widget.evaluate(() => [...document.querySelectorAll('button,[role="button"],[data-name]')]
    .map((b) => ({
      t: (b.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 24),
      title: (b.getAttribute('title') || '').slice(0, 30),
      dn: b.getAttribute('data-name'),
      aria: (b.getAttribute('aria-label') || '').slice(0, 30),
    }))
    .filter((x) => x.t || x.dn || x.title)
    .slice(0, 220));
  say('buttons seen: ' + buttons.length);
  const intervalish = buttons.filter((b) => /^(۱|1)\s*(D|d|روز|روزانه)$|^(روزانه|1D|D)$/.test(b.t || '') ||
    /interval|timeScale|resolution/i.test((b.dn || '') + (b.aria || '') + (b.title || '')));
  rep.intervalCandidates = intervalish;
  say('interval candidates: ' + JSON.stringify(intervalish.slice(0, 6)));

  rep.asFound = await widget.evaluate(readLegend);
  await page.screenshot({ path: path.join(ROOT, '_audit', 'ref_folad_before_interval.png') });

  // کلیکِ بازۀِ روزانه — ازِ نامِ عنصرِ TV (data-name="interval-button") یا متنِ «۱روز»
  let clicked = null;
  for (const sel of ['[data-name="interval-button"]', 'button[title*="روز"]', 'div[data-name="time-scale-tool"] button']) {
    const loc = widget.locator(sel).first();
    if (await loc.count().catch(() => 0)) {
      await loc.click({ timeout: 5000 }).catch(() => {});
      clicked = sel; break;
    }
  }
  await page.waitForTimeout(1500);
  if (clicked) {
    const opts = await widget.evaluate(() => [...document.querySelectorAll('[class*="item"],[role="menuitem"],[data-name]')]
      .map((e) => (e.textContent || '').replace(/\s+/g, ' ').trim())
      .filter((s) => s && s.length < 24 && /(^|\D)(1\s*D|۱\s*D|روزانه|Day)/i.test(s)).slice(0, 20));
    rep.dayOptions = opts;
    say('day options: ' + JSON.stringify(opts));
    for (const text of ['1D', '۱D', '1 روز', '۱ روز', 'روزانه']) {
      const it = widget.getByText(text, { exact: true }).first();
      if (await it.count().catch(() => 0)) { await it.click({ timeout: 4000 }).catch(() => {}); say('clicked day option: ' + text); break; }
    }
  }
  await page.waitForTimeout(6000);
  rep.afterClick = await widget.evaluate(readLegend);
  await page.screenshot({ path: path.join(ROOT, '_audit', 'ref_folad_daily_1d.png'), fullPage: false });

  // برچسبِ OHLCِ آخرین کندل، بدونِ ساختنِ هیچ چیزی رویِ صحنه: فقط مکان‌نمایِ خودِ رابط
  rep.intervalButton = await widget.evaluate(() => {
    const b = document.querySelector('[data-name="interval-button"]');
    return b ? (b.textContent || '').replace(/\s+/g, ' ').trim() : null;
  });
  say('interval button now reads: ' + JSON.stringify(rep.intervalButton));
  fs.writeFileSync(OUT, JSON.stringify(rep, null, 1), 'utf8');
  say('written: ' + OUT);
  await page.close();
  await browser.close();
})().catch((e) => { console.error('FAILED: ' + ((e && e.stack) || e)); process.exit(1); });
