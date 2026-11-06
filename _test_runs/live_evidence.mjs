#!/usr/bin/env node
/**
 * Live UI evidence via raw CDP (Node built-in WebSocket, no new deps).
 * Waits for the Vite app to actually mount, then captures 1366/1920
 * analysis/scan/research, the Ctrl+K palette and save/restore of a layout.
 */
import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { setTimeout as sleep } from 'node:timers/promises';

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const OUT = 'D:/BorsTerminal-worktrees/4axes-main-integration/_test_runs/live';
const URL = 'http://127.0.0.1:5181/#/technical';
const PORT = 9226;

mkdirSync(OUT, { recursive: true });

const edge = spawn(EDGE, [
  '--headless=new', '--disable-gpu', '--hide-scrollbars',
  `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${OUT}/edge-profile3`,
  '--no-first-run', '--no-default-browser-check',
  'about:blank',
], { stdio: 'ignore' });

async function getWs() {
  for (let i = 0; i < 60; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const pages = await res.json();
      const page = pages.find((p) => p.type === 'page');
      if (page?.webSocketDebuggerUrl) return page.webSocketDebuggerUrl;
    } catch { /* not ready */ }
    await sleep(300);
  }
  throw new Error('CDP not ready');
}

const ws = new WebSocket(await getWs());
await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });

let seq = 0;
const pending = new Map();
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id);
    pending.delete(msg.id);
    if (msg.error) reject(new Error(msg.error.message));
    else resolve(msg.result);
  }
};

function send(method, params = {}) {
  const id = ++seq;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
    setTimeout(() => {
      if (pending.has(id)) { pending.delete(id); reject(new Error(`timeout: ${method}`)); }
    }, 40000);
  });
}

async function evaluate(expression) {
  const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  return result.result?.value;
}

async function shot(name) {
  const { data } = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync(`${OUT}/${name}.png`, Buffer.from(data, 'base64'));
  console.log('saved', name);
}

async function waitMounted(timeoutMs = 90000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const mounted = await evaluate('(document.querySelector("#root")?.childElementCount || 0) > 0');
    if (mounted) return true;
    await sleep(1500);
  }
  return false;
}

async function clickByText(text) {
  return evaluate(`(() => {
    const needle = ${JSON.stringify(text)};
    const els = [...document.querySelectorAll('button')];
    const el = els.find((b) => (b.textContent || '').trim().includes(needle));
    if (!el) return false;
    el.click();
    return true;
  })()`);
}

await send('Page.enable');
await send('Runtime.enable');
await send('Emulation.setDeviceMetricsOverride', { width: 1366, height: 768, deviceScaleFactor: 1, mobile: false });
await send('Page.navigate', { url: URL });
const mounted = await waitMounted();
console.log('mounted:', mounted);
await sleep(5000);

// ask the chart to fit its data, then zoom out in time
await evaluate(`(() => {
  const btn = [...document.querySelectorAll('button')].find((b) =>
    (b.getAttribute('aria-label') || b.getAttribute('title') || '').includes('Auto-fit'));
  if (btn) btn.click();
  return Boolean(btn);
})()`);
const chartBox = await evaluate(`(() => {
  const c = document.querySelector('canvas');
  if (!c) return null;
  const r = c.getBoundingClientRect();
  return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) };
})()`);
if (chartBox) {
  for (let i = 0; i < 3; i++) {
    await send('Input.dispatchMouseEvent', {
      type: 'mouseWheel', x: chartBox.x, y: chartBox.y, deltaX: 0, deltaY: 420,
    });
    await sleep(350);
  }
}
await sleep(1200);
const spotlight = await evaluate(`({
  spotlights: document.querySelectorAll('[data-testid="pattern-spotlight"]').length,
  inspector: (document.body.innerText.match(/الگوی[^
]*/g)||[]).slice(0,3),
  canvas: document.querySelectorAll('canvas').length,
  bars: (document.body.innerText.match(/Volume: [^
]+/g)||[])[0] || null,
})`);
console.log('spotlight-state:', JSON.stringify(spotlight));
await shot('1366-analysis');

if (await clickByText('اسکن')) { await sleep(2000); await shot('1366-scan'); }
if (await clickByText('پژوهش')) { await sleep(2000); await shot('1366-research'); }
if (await clickByText('تحلیل')) { await sleep(1500); }

// Ctrl+K palette
await send('Input.dispatchKeyEvent', { type: 'keyDown', modifiers: 2, key: 'k', code: 'KeyK', windowsVirtualKeyCode: 75 });
await sleep(1000);
await shot('1366-palette');

// save the current layout through the palette action
const saved = await clickByText('ذخیرهٔ چیدمان فعلی');
await sleep(700);
console.log('save-clicked:', saved);
await shot('1366-palette-saved');
await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
await sleep(500);

// restore the default layout through the palette action
await send('Input.dispatchKeyEvent', { type: 'keyDown', modifiers: 2, key: 'k', code: 'KeyK', windowsVirtualKeyCode: 75 });
await sleep(800);
const restored = await clickByText('بازیابی چیدمان');
console.log('restore-clicked:', restored);
await sleep(900);
await shot('1366-palette-restore');
await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
await sleep(500);

await send('Emulation.setDeviceMetricsOverride', { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
await sleep(2500);
await shot('1920-analysis');
if (await clickByText('اسکن')) { await sleep(2000); await shot('1920-scan'); }
if (await clickByText('پژوهش')) { await sleep(2000); await shot('1920-research'); }
if (await clickByText('تحلیل')) { await sleep(1500); }

ws.close();
edge.kill();
console.log('done');
