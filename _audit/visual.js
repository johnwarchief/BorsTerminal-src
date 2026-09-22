// Visual audit: screenshot every main route at several viewport widths.
// Flags overflow (content wider than the viewport), overlapping elements,
// and clipped text — the classes of visual bug a user notices first.
const { chromium } = require('playwright-core');
const fs = require('fs');

const ROUTES = [
  { name: 'market', url: 'http://localhost:8001/#/market' },
  { name: 'fundamental', url: 'http://localhost:8001/#/fundamental' },
  { name: 'technical', url: 'http://localhost:8001/#/technical' },
];
const WIDTHS = [1280, 1024, 768];

async function main() {
  const browser = await chromium.launch({ channel: 'msedge', headless: true,
    args: ['--no-first-run', '--no-default-browser-check'] });
  const out = { issues: [] };

  for (const w of WIDTHS) {
    const ctx = await browser.newContext({ viewport: { width: w, height: 900 } });
    const page = await ctx.newPage();
    for (const r of ROUTES) {
      await page.goto(r.url, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(4000);
      const needsLogin = await page.locator('input[placeholder="admin"]').count().catch(() => 0);
      if (needsLogin > 0) {
        await page.locator('input[placeholder="admin"]').fill('admin');
        await page.locator('input[type="password"]').first().fill('bors123');
        await page.getByRole('button', { name: /ورود به ایستگاه/i }).click();
        await page.waitForTimeout(8000);
        await page.goto(r.url, { waitUntil: 'domcontentloaded' });
        await page.waitForTimeout(4000);
      }

      const shot = `shot_${r.name}_${w}.png`;
      await page.screenshot({ path: shot, fullPage: false });
      console.log('shot', shot);

      // overflow: any element wider than the viewport
      const ov = await page.evaluate((vw) => {
        const bad = [];
        document.querySelectorAll('*').forEach(el => {
          const rct = el.getBoundingClientRect();
          if (rct.width > 0 && (rct.right > vw + 2 || rct.left < -2)) {
            const cls = (el.className || '').toString().slice(0, 50);
            bad.push({ tag: el.tagName, cls, right: Math.round(rct.right),
                       left: Math.round(rct.left), w: Math.round(rct.width) });
          }
        });
        return bad.slice(0, 8);
      }, w);
      if (ov.length) {
        out.issues.push({ route: r.name, width: w, kind: 'overflow', els: ov });
        console.log('  OVERFLOW x', ov.length, JSON.stringify(ov[0]));
      }

      // horizontal scrollbar
      const hasHs = await page.evaluate(() =>
        document.documentElement.scrollWidth > document.documentElement.clientWidth);
      if (hasHs) {
        const sw = await page.evaluate(() => ({
          scrollW: document.documentElement.scrollWidth,
          clientW: document.documentElement.clientWidth }));
        out.issues.push({ route: r.name, width: w, kind: 'h-scrollbar', ...sw });
        console.log('  H-SCROLL', JSON.stringify(sw));
      }

      // clipped leaf text (ellipsis/overflow hidden with no room)
      const clipped = await page.evaluate(() => {
        let n = 0;
        document.querySelectorAll('*').forEach(el => {
          if (el.children.length !== 0) return;
          const t = (el.textContent || '').trim();
          if (t.length < 3) return;
          const s = getComputedStyle(el);
          if (s.overflow === 'hidden' || s.textOverflow === 'ellipsis') {
            if (el.scrollWidth > el.clientWidth + 1) n += 1;
          }
        });
        return n;
      });
      if (clipped > 0) {
        out.issues.push({ route: r.name, width: w, kind: 'clipped-text', n: clipped });
        console.log('  CLIPPED TEXT x', clipped);
      }
    }
    await ctx.close();
  }

  fs.writeFileSync('_visual.json', JSON.stringify(out, null, 1), 'utf-8');
  console.log('\n=== visual issues: %d ===' % out.issues.length);
  out.issues.forEach(i => console.log(' ', JSON.stringify(i).slice(0, 160)));
  await browser.close();
}

main().catch(e => { console.error('FATAL', e); process.exit(1); });
