// _audit/ra365_browser.js -- بازکردنِ Edge با پورتِ CDP واقعی (بدونِ Playwright) تا پنجره بستۀ خودِ مالک بماند
// چرا این روش: launchPersistentContext خودِ flag «--remote-debugging-pipe» را اضافه می‌کند و
// پورتِ HTTP خاموش می‌ماند؛ آن‌وقت هیچ سنجشی نمی‌تواند به همان پنجره وصل شود. اینجا Edge را
// مستقل و detached باز می‌کنیم؛ پنجره حتی با تمام‌شدنِ این اسکریپت باز می‌ماند و سنجش‌ها بعداً
// با chromium.connectOverCDP به آن وصل می‌شوند و از همان نشستِ لاگین‌شده استفاده می‌کنند.
// پروفایل بیرونِ مخزن است (temp). هیچ رمز/کوکی/توکنی خوانده یا ذخیره نمی‌شود.
const os = require('os');
const cp = require('child_process');
const fs = require('fs');
const path = require('path');

const PROFILE = path.join(os.tmpdir(), 'bors-ra365-probe-profile');
const PORT = Number(process.env.RA_CDP_PORT || 9333);
const URL0 = process.env.RA_START_URL || 'https://rahavard365.com/';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';

(async () => {
  if (!fs.existsSync(EXE)) throw new Error('msedge not found: ' + EXE);
  const args = [
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${PROFILE}`,
    '--no-first-run', '--no-default-browser-check', '--disable-features=Translate',
    `--window-size=1600,900`, '--new-window', URL0,
  ];
  const child = cp.spawn(EXE, args, { detached: true, stdio: 'ignore' });
  child.unref();
  console.log('spawned msedge pid=' + child.pid + ' profile=' + PROFILE);

  const t0 = Date.now();
  while (Date.now() - t0 < 60000) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/version`);
      const j = await r.json();
      const tabs = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      console.log('CDP-READY ' + j.Browser + ' | port=' + PORT);
      console.log('targets: ' + tabs.filter((x) => x.type === 'page').map((x) => x.url).join(' , '));
      console.log('پنجره باز است؛ لاگین را در همین پنجره انجام دهید.');
      process.exit(0);
    } catch { await new Promise((r) => setTimeout(r, 1500)); }
  }
  throw new Error('CDP port ' + PORT + ' never came up (60s) — Edge may have opened in an existing process; close that window and retry');
})().catch((e) => { console.error('FATAL ' + String(e)); process.exit(1); });
