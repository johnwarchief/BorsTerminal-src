// _audit/probe_download.mts -- اثباتِ زندهٔ «دانلودِ فقطِ ردیف‌های دیدنی» (جدولِ بنیادی)
const { pathToFileURL } = await import('node:url');
const PKG = process.env.JEV_BROWSER_DIR ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const b = await chromium.launch({ executablePath: process.env.JEV_CHROME, args: ['--no-sandbox'] });
const ctx = await b.newContext({ viewport: { width: 1366, height: 1000 }, acceptDownloads: true });
const p = await ctx.newPage();
await p.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
await p.goto('http://127.0.0.1:8002/#/fundamental', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(40000);

const before = await p.evaluate(() => {
  const btn = document.querySelector('[data-testid="download-screen-rows"]') as HTMLElement | null;
  return {
    found: !!btn,
    count: btn?.getAttribute('data-count') ?? null,
    label: btn?.textContent ?? null,
    disabled: btn?.hasAttribute('disabled') ?? null,
    rows_in_table: document.querySelectorAll('[data-testid="fts-screen-row"]').length,
    height_of_bar: Math.round((document.querySelector('[data-testid="download-screen-rows"]')?.getBoundingClientRect().height ?? 0)),
  };
});

const dl = p.waitForEvent('download', { timeout: 15000 }).catch(() => null);
await p.click('[data-testid="download-screen-rows"]');
const download = await dl;
let head: string[] = [];
let name = null as string | null;
if (download) {
  name = download.suggestedFilename();
  const stream = await download.createReadStream();
  const chunks: Buffer[] = [];
  for await (const c of stream) chunks.push(c as Buffer);
  head = Buffer.concat(chunks).toString('utf-8').replace('', '').split('\r\n').slice(0, 4);
}

// با جستجو ⇒ شمارِ ردیف‌های فایل باید بیفتد
await p.fill('[data-testid="fts-search"]', 'پترو');
await p.waitForTimeout(3000);
const after = await p.evaluate(() => ({
  count: document.querySelector('[data-testid="download-screen-rows"]')?.getAttribute('data-count') ?? null,
  rows_in_table: document.querySelectorAll('[data-testid="fts-screen-row"]').length,
}));
const dl2 = p.waitForEvent('download', { timeout: 15000 }).catch(() => null);
await p.click('[data-testid="download-screen-rows"]');
const d2 = await dl2;
let lines2 = 0;
if (d2) {
  const s = await d2.createReadStream();
  const ch: Buffer[] = [];
  for await (const c of s) ch.push(c as Buffer);
  lines2 = Buffer.concat(ch).toString('utf-8').replace('', '').split('\r\n').filter(Boolean).length;
}
console.log(JSON.stringify({ before, download_name: name, head, after, filtered_file_lines: lines2 }, null, 1));
await b.close();
