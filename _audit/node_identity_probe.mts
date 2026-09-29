// scratch: does a board cell keep its DOM node between live polls, and does
// node loss coincide with the cell's value changing (benign) or not (defect)?
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR ?? '';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const url = arg('url', 'http://127.0.0.1:8001/');
const polls = Number(arg('polls', '9'));
const pollMs = Number(arg('poll', '5000'));
const N = Number(arg('rows', '25'));
const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 950 } });
await ctx.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
  } catch {}
});
const page = await ctx.newPage();
await page.goto(url, { waitUntil: 'networkidle' });
await page.waitForTimeout(8000);

const walk = (mark: boolean) =>
  page.evaluate(
    ({ mark, n }: { mark: boolean; n: number }) => {
      const rows = Array.from(document.querySelectorAll('[data-testid="tape-row"]')).slice(0, n);
      let seen = 0;
      let kept = 0;
      let changed = 0;
      rows.forEach((row, i) => {
        const cell = row.children[1];
        const num = (cell?.querySelector('.num') ?? cell) as HTMLElement | null;
        if (!num) return;
        seen++;
        const text = (num.textContent ?? '').trim();
        const prev = num.getAttribute('data-probe-text');
        if (prev !== null && prev !== text) changed++;
        if (num.hasAttribute('data-probe-id')) kept++;
        if (mark) {
          num.setAttribute('data-probe-id', 'p' + i);
          num.setAttribute('data-probe-text', text);
        }
      });
      return { seen, kept, changed, rows: rows.length };
    },
    { mark, n: N },
  );

const first = await walk(true);
const trail: unknown[] = [];
for (let i = 0; i < polls; i++) {
  await page.waitForTimeout(pollMs);
  trail.push({ at: i + 1, ...(await walk(false)) });
}
const out = {
  url, at: new Date().toISOString(), markedFirst: first, pollMs, rowsSampled: N, trail,
  totalSeen: trail.reduce((s: number, t: any) => s + t.seen, 0),
  totalKept: trail.reduce((s: number, t: any) => s + t.kept, 0),
  totalChanged: trail.reduce((s: number, t: any) => s + t.changed, 0),
};
console.log(JSON.stringify(out, null, 1));
writeFileSync(arg('out', '_audit/node_identity.json'), JSON.stringify(out, null, 1), 'utf8');
await browser.close();
