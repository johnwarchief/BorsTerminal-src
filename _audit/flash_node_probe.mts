// scratch: when a board cell's number changes, is its DOM node replaced
// (marker lost) or patched in place (marker kept)?
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR ?? '';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const url = arg('url', 'http://127.0.0.1:8001/');
const polls = Number(arg('polls', '8'));
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

// one pass: for each sampled row, read the marker's own text and compare it to
// the element's current text. marker-present + text-equal = untouched;
// marker-present + text-differs = patched in place; marker-gone = node replaced.
const pass = () =>
  page.evaluate(
    (n: number) => {
      const rows = Array.from(document.querySelectorAll('[data-testid="tape-row"]')).slice(0, n);
      const out = { seen: 0, keptMark: 0, patched: 0, replaced: 0, flashed: 0 };
      rows.forEach((row, i) => {
        const cell = row.children[1];
        const num = ((cell && cell.querySelector('.num')) || cell) as HTMLElement | null;
        if (!num) return;
        out.seen++;
        const text = (num.textContent || '').trim();
        const markedAt = num.getAttribute('data-probe-text');
        const cls = num.className || '';
        if (cls.indexOf('flash-') >= 0) out.flashed++;
        if (markedAt === null) {
          num.setAttribute('data-probe-text', text);
        } else if (markedAt === text) {
          out.keptMark++;
        } else {
          out.patched++;
          num.setAttribute('data-probe-text', text);
        }
      });
      return out;
    },
    N,
  );

const firstPass = await pass();
const trail = [];
for (let i = 0; i < polls; i++) {
  await page.waitForTimeout(pollMs);
  trail.push({ at: i + 1, ...(await pass()) });
}
const sum = (k: string) => trail.reduce((s: number, t: any) => s + (t[k] as number), 0);
const out = {
  url,
  at: new Date().toISOString(),
  firstPass,
  trail,
  totals: {
    seen: sum('seen'),
    unchanged: sum('keptMark'),
    changedInPlace: sum('patched'),
    nodeReplaced: sum('replaced'),
    flashClassSeen: sum('flashed'),
  },
};
console.log(JSON.stringify(out.totals), JSON.stringify(firstPass));
writeFileSync(arg('out', '_audit/flash_node.json'), JSON.stringify(out, null, 1), 'utf8');
await browser.close();
