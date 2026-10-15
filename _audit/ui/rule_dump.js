// _audit/ui/rule_dump.js — هرِ قاعدۀِ CSS که برِ یکِ سلکتورِ مشخص اثر می‌گذارد
// usage: node _audit/ui/rule_dump.js --sel=.nn-top-toolbar
const path = require('path'); const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || String.raw`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`;
const arg = (n, d) => { const h = process.argv.find((a) => a.startsWith('--' + n + '=')); return h ? h.split('=').slice(1).join('=') : d; };
const SEL = arg('sel', '.nn-top-toolbar');
(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run', '--disable-sync', '--force-device-scale-factor=1'] });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(900);
  if (await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
    const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
    await page.locator('input[type="text"]').first().fill((src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('input[type="password"]').first().fill((src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('button[type="submit"]').first().click(); await page.waitForTimeout(2000);
  }
  await page.goto(BASE + '/#/technical/فولاد', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !!document.querySelector('.nn-top-toolbar'), null, { timeout: 45000 }).catch(() => {});
  await page.waitForTimeout(2500);
  const r = await page.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (!el) return { missing: true };
    const hits = [];
    for (const sheet of document.styleSheets) {
      let rules; try { rules = sheet.cssRules; } catch { continue; }
      for (const rule of rules) {
        if (!rule.selectorText) continue;
        let ok = false; try { ok = el.matches(rule.selectorText); } catch {}
        if (!ok) continue;
        const props = ['display', 'flex-wrap', 'flexWrap', 'height', 'min-height', 'max-height', 'overflow', 'overflow-x', 'overflow-y', 'flex-shrink', 'white-space'];
        const decl = [...rule.style].filter((p) => props.includes(p)).map((p) => `${p}:${rule.style.getPropertyValue(p)}${rule.style.getPropertyPriority(p) ? '!imp' : ''}`).join(' ');
        if (decl) hits.push({ sel: rule.selectorText, media: rule.parentRule ? rule.parentRule.conditionText : null, sheet: (sheet.href || 'inline-style-tag').split('/').pop(), decl });
      }
    }
    const cs = getComputedStyle(el);
    return { sel, hits, computed: { display: cs.display, flexWrap: cs.flexWrap, height: cs.height, ovX: cs.overflowX, ovY: cs.overflowY },
             canScrollX: (() => { const s = el.scrollLeft; el.scrollLeft = 50; const ok = el.scrollLeft !== s; el.scrollLeft = s; return ok; })(),
             inline: el.style.cssText, cls: el.className };
  }, SEL);
  console.log(JSON.stringify(r, null, 1));
  await browser.close();
})();
