// Diagnose: after login, what tab are we on and what does بنیادی click do?
const { chromium } = require('playwright-core');
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const browser = await chromium.launch({ executablePath: EDGE, headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto('http://localhost:8001/', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await sleep(2500);
  await page.fill('input[type="text"]', 'admin').catch(() => {});
  await page.fill('input[type="password"]', 'bors123').catch(() => {});
  await page.getByRole('button', { name: /ورود/i }).click({ timeout: 8000 }).catch(() => {});
  await sleep(4000);

  const before = await page.evaluate(() => ({
    tables: document.querySelectorAll('table').length,
    grids: document.querySelectorAll('[class*="grid-cols"]').length,
    btns: [...document.querySelectorAll('button')].map((b) => b.textContent.trim().slice(0, 18))
      .filter((t) => t.includes('بنیادی') || t.includes('تابلو') || t.includes('تکنیکال') || t.includes('پورتفو')),
  }));
  console.log('BEFORE:', JSON.stringify(before, null, 1));

  const btn = page.locator('button:has-text("بنیادی")').first();
  const count = await btn.count();
  console.log('بنیادی buttons found:', count);
  if (count) {
    await btn.click({ timeout: 6000 });
    await sleep(6000);
    const after = await page.evaluate(() => ({
      tables: document.querySelectorAll('table').length,
      grids: document.querySelectorAll('[class*="grid-cols"]').length,
      bodySample: document.body.textContent.replace(/\s+/g, ' ').slice(0, 200),
    }));
    console.log('AFTER:', JSON.stringify(after, null, 1));
  }
  await browser.close();
})().catch((e) => { console.error('FAIL', e.message); process.exit(1); });
