// scratch: prove the board header tooltips name the right TSETMC filter variables.
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR ?? '';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const arg = (n, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const url = arg('url', 'http://127.0.0.1:5173/');
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.JEV_CHROME || undefined,
});
const page = await browser.newPage({ viewport: { width: 1600, height: 950 } });
await page.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
  } catch {
    /* پوستهٔ بدونِ دروازه هم همین را می‌پذیرد */
  }
});
const errors = [];
page.on('pageerror', (e) => errors.push('pageerror: ' + String(e.message).slice(0, 160)));
page.on('response', (r) => {
  if (r.status() >= 400) errors.push(`http ${r.status()} ${r.url().slice(0, 150)}`);
});
page.on('console', (m) => {
  if (m.type() === 'error') errors.push('console: ' + m.text().slice(0, 160));
});
await page.goto(url, { waitUntil: 'networkidle' });
await page.waitForTimeout(9000);
const diag = await page.evaluate(() => {
  const titles = Array.from(document.querySelectorAll('[title]')).map((el) => ({
    label: (el.textContent || '').trim().slice(0, 16),
    title: (el.getAttribute('title') || '').slice(0, 140),
  }));
  return {
    bodyText: (document.body.innerText || '').slice(0, 260),
    withTitle: titles.length,
    tsetmc: titles.filter((t) => /TSETMC|plp|pcp/.test(t.title)),
  };
});
const out = { url, at: new Date().toISOString(), ...diag, errors };
console.log(JSON.stringify(out, null, 1));
writeFileSync(arg('out', '_audit/header_tooltip_check.json'), JSON.stringify(out, null, 1), 'utf8');
await browser.close();
