// Phase D TinyJS shell: owns the Python sidecar, gates the window on HTTP
// readiness, reports failures, and lets the sidecar shut down when the shell
// dies (stdin EOF). Remote UI stays on the loopback origin so the production
// Host/Origin guard is never bypassed and no proxy rewrites the origin.
//
// Benchmark hooks are opt-in via env:
//   BORS_PYTHON / BORS_HEADLESS_ENTRY   sidecar paths (dev)
//   BORS_WORK_DIR                       isolated data root
//   BORS_SHELL_TRACE                    JSONL shell trace
//   BORS_PROBE_SCRIPT / BORS_COLLECTOR_PORT  in-page probe via app.window().eval
//   BORS_FAIL_TEST=1                    deliberately start a failing sidecar

const dec = new TextDecoder();
const enc = new TextEncoder();
const env = tjs.env;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const t0 = Date.now();
let tracePath = env.BORS_SHELL_TRACE || '';
let workDir = env.BORS_WORK_DIR || '';
let logsDir = workDir ? workDir.replace(/[\\/]+$/, '') + '\\logs' : '';

let child = null;
let childExit = null;
let traceChain = Promise.resolve();
let stopping = false;
let readyUrl = '';
let appRef = null;

function trace(stage, extra = {}) {
  if (!tracePath) return;
  const rec = { stage, t: Date.now() / 1000, dt: (Date.now() - t0) / 1000,
                pid: tjs.pid, ...extra };
  traceChain = traceChain.then(async () => {
    const f = await tjs.open(tracePath, 'a');
    await f.write(enc.encode(JSON.stringify(rec) + '\n'));
    await f.close();
  }).catch(() => {});
}

async function appendLine(path, line) {
  try {
    const f = await tjs.open(path, 'a');
    await f.write(enc.encode(line + '\n'));
    await f.close();
  } catch { /* logging must never kill the shell */ }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

async function showError(app, title, detail) {
  trace('error_window', { title, detail: String(detail).slice(0, 400) });
  if (!logsDir) return;
  const path = logsDir + '\\tinyjs-error.html';
  const html = '<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8">'
    + '<title>' + esc(title) + '</title>'
    + '<style>html,body{height:100%;margin:0;background:#0b0f17;color:#e6edf7;'
    + 'font:14px/1.9 Tahoma,"Segoe UI",sans-serif}.w{min-height:100%;display:flex;'
    + 'align-items:center;justify-content:center;padding:24px}.c{width:min(680px,100%);'
    + 'background:#111827;border:1px solid #1f2a3a;border-radius:16px;padding:26px}'
    + 'h1{font-size:17px;margin:0 0 10px;color:#fca5a5}pre{white-space:pre-wrap;'
    + 'font-size:12px;color:#cfe3ff;background:#0b1220;padding:12px;border-radius:8px}'
    + '.p{font-size:12px;color:#8ea3bd;margin:12px 0 0}</style>'
    + '<div class="w"><div class="c"><h1>' + esc(title) + '</h1>'
    + '<pre>' + esc(detail) + '</pre>'
    + '<p class="p">log: ' + esc(logsDir) + '</p></div></div>';
  try {
    await tjs.writeFile(path, html);
    app.win.open('error', { page: path, title: 'BorsTerminal — startup failed',
                            size: '760x440' });
    app.window('error').show();
    app.window('error').zoom();
  } catch (e) {
    trace('error_window_failed', { error: String(e).slice(0, 300) });
    try { app.win.open('error', { page: 'about:blank', title: 'BorsTerminal — startup failed' }); } catch { }
  }
}

async function existingServer(port) {
  if (!port) return '';
  try {
    const r = await fetch('http://127.0.0.1:' + port + '/api/update/version',
                          { cache: 'no-store' });
    if (!r.ok) return '';
    const j = await r.json();
    return j && j.version ? 'http://127.0.0.1:' + port + '/' : '';
  } catch { return ''; }
}

function parseReady(line) {
  const p = line.startsWith('M2_READY ')
    ? 'M2_READY '
    : (line.startsWith('PHASE_D_READY ') ? 'PHASE_D_READY ' : '');
  if (!p) return null;
  try { return JSON.parse(line.slice(p.length)); } catch { return null; }
}

async function pump(stream, label, logPath, onLine) {
  if (!stream) return;
  const reader = stream.getReader();
  let buf = '';
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, nl).replace(/\r$/, '');
        buf = buf.slice(nl + 1);
        appendLine(logPath, '[' + label + '] ' + line);
        if (onLine) onLine(line);
      }
    }
    if (buf) {
      appendLine(logPath, '[' + label + '] ' + buf);
      if (onLine) onLine(buf);
    }
  } catch (e) {
    appendLine(logPath, '[' + label + '] read error: ' + String(e).slice(0, 300));
  }
}

async function injectProbe(app) {
  const probePath = env.BORS_PROBE_SCRIPT || '';
  const collector = env.BORS_COLLECTOR_PORT || '';
  if (!probePath || !collector) return;
  let src = '';
  try {
    src = dec.decode(await tjs.readFile(probePath))
      .replaceAll('__BORS_COLLECTOR__', String(collector));
    if (env.BORS_VISUAL === '1') src = 'window.__BORS_VISUAL__=true;' + src;
    if (env.BORS_D3_CHECKS === '1') {
      src = 'window.__BORS_D3_CHECKS__=true;window.__BORS_SYMBOL2__='
        + JSON.stringify(env.BORS_SYMBOL2 || '') + ';' + src;
    }
  } catch (e) {
    trace('probe_read_failed', { error: String(e).slice(0, 300) });
    return;
  }
  for (let i = 0; i < 40 && !stopping; i++) {
    if (env.BORS_PROBE_STOP_FILE) {
      try {
        await tjs.stat(env.BORS_PROBE_STOP_FILE);
        trace('probe_stop_file', { attempt: i + 1 });
        break;
      } catch { /* not created yet */ }
    }
    try {
      app.window('app').eval(src);
      trace('probe_eval', { attempt: i + 1 });
    } catch (e) {
      trace('probe_eval_failed', { attempt: i + 1, error: String(e).slice(0, 200) });
    }
    await sleep(900);
  }
}

function joinPath(base, child) {
  return String(base || '').replace(/[\\/]+$/, '') + '\\' + child;
}

async function fileExists(path) {
  try { await tjs.stat(path); return true; } catch { return false; }
}

// The installed package ships the PyInstaller sidecar inside resources/.
// Dev/benchmark runs keep the explicit BORS_PYTHON + BORS_HEADLESS_ENTRY path.
async function resolveSidecar(app, pathsInfo) {
  if (env.BORS_SIDECAR_EXE) {
    return { exe: env.BORS_SIDECAR_EXE, argv: [], installed: true };
  }
  const candidates = [];
  if (pathsInfo && pathsInfo.resources) {
    candidates.push(joinPath(pathsInfo.resources, 'sidecar\\BorsTerminalSidecar.exe'));
  }
  if (pathsInfo && pathsInfo.executables) {
    candidates.push(joinPath(pathsInfo.executables, 'BorsTerminalSidecar.exe'));
  }
  for (const c of candidates) {
    if (await fileExists(c)) return { exe: c, argv: [], installed: true };
  }
  const py = env.BORS_PYTHON || '';
  const entry = env.BORS_HEADLESS_ENTRY || '';
  if (py && entry) return { exe: py, argv: [entry], installed: false };
  return null;
}

async function start(app) {
  appRef = app;
  let pathsInfo = null;
  try { pathsInfo = await app.paths(); } catch (e) {
    trace('paths_failed', { error: String(e).slice(0, 300) });
  }
  if (!workDir && pathsInfo && pathsInfo.data) workDir = pathsInfo.data;
  if (!workDir) {
    await showError(app, 'Application data path is unavailable',
      'TinyJS did not return a writable data directory; refusing to start.');
    return;
  }
  logsDir = joinPath(workDir, 'logs');
  if (!tracePath) tracePath = joinPath(logsDir, 'shell-trace.jsonl');
  try { await tjs.makeDir(logsDir, { recursive: true }); } catch { }
  trace('backend_init', { work: workDir, main: true,
    installed: !!(pathsInfo && pathsInfo.resources),
    resources: (pathsInfo && pathsInfo.resources) || null });

  const preferred = env.BORS_PORT || '8105';
  const reused = env.BORS_REUSE_SERVER === '1' ? await existingServer(preferred) : '';
  if (reused) {
    trace('server_reused', { url: reused });
    readyUrl = reused;
    await openAppWindow(app, reused);
    return;
  }

  const sidecar = await resolveSidecar(app, pathsInfo);
  if (!sidecar) {
    await showError(app, 'Backend path is not configured',
      'No bundled BorsTerminalSidecar.exe was found, and BORS_PYTHON/BORS_HEADLESS_ENTRY are not set.');
    return;
  }
  const dbPath = env.BORS_DB || joinPath(workDir, 'market.db');
  const childEnv = {
    ...env,
    BORS_PORT: env.BORS_PORT || '0',
    BORS_WORK_DIR: workDir,
    BORS_DB: dbPath,
    BORS_SHOW_CONSOLE: '1',
    BORS_STARTUP_TRACE: '1',
  };
  if (env.BORS_FAIL_TEST === '1') childEnv.BORS_FAIL_TEST = '1';

  trace('sidecar_spawn_begin', { exe: sidecar.exe, argv: sidecar.argv,
    installed: sidecar.installed, port: childEnv.BORS_PORT, work: workDir });
  try {
    const exeDir = String(sidecar.exe).replace(/[\\/][^\\/]+$/, '');
    const opts = {
      cwd: sidecar.installed ? exeDir : (workDir || tjs.cwd),
      env: childEnv,
      stdin: 'pipe',
      stdout: 'pipe',
      stderr: 'pipe',
    };
    // tjs.spawn opens a console window for a GUI app's child on Windows;
    // spawnHidden is the shell's supported wrapper around the same spawn.
    const argv = [sidecar.exe, ...sidecar.argv];
    child = typeof app.spawnHidden === 'function'
      ? app.spawnHidden(argv, opts)
      : tjs.spawn(argv, opts);
  } catch (e) {
    trace('sidecar_spawn_failed', { error: String(e).slice(0, 300) });
    await showError(app, 'Backend could not start', String(e));
    return;
  }
  trace('sidecar_spawned', { pid: child.pid });

  let ready = null;
  let exited = null;
  let tail = [];
  const logPath = logsDir + '\\sidecar.log';
  const onLine = (line) => {
    tail.push(line);
    if (tail.length > 40) tail.shift();
    if (!ready) {
      const r = parseReady(line);
      if (r) { ready = r; trace('sidecar_ready_line', { port: r.port, pid: r.pid }); }
    }
  };
  const pOut = pump(child.stdout, 'out', logPath, onLine);
  const pErr = pump(child.stderr, 'err', logPath, (line) => tail.push(line));
  childExit = child.wait().then((st) => {
    exited = st;
    trace('sidecar_exit', { code: st.exit_status, signal: st.term_signal });
    if (!ready && !stopping) {
      showError(app, 'Backend exited before it was ready',
        'exit=' + st.exit_status + '\n\n' + tail.slice(-20).join('\n'));
    } else if (ready && !stopping) {
      showError(app, 'Backend stopped unexpectedly',
        'exit=' + st.exit_status + '\n\n' + tail.slice(-20).join('\n'));
    }
    return st;
  }).catch(() => null);

  const deadline = Date.now() + 240000;
  while (!ready && !exited && Date.now() < deadline && !stopping) {
    await sleep(100);
  }
  if (!ready) {
    await pOut; await pErr;
    trace('ready_timeout', { exited: !!exited, code: exited && exited.exit_status });
    if (!exited) {
      await showError(app, 'Backend did not become ready',
        'No READY line within 240s.\n\n' + tail.slice(-20).join('\n'));
    }
    return;
  }

  const url = 'http://127.0.0.1:' + ready.port + '/';
  let verified = false;
  for (let i = 0; i < 120 && !stopping; i++) {
    try {
      const r = await fetch(url + 'api/update/version', { cache: 'no-store' });
      if (r.ok) {
        const j = await r.json();
        if (j && j.version) { verified = true; break; }
      }
    } catch { }
    await sleep(250);
  }
  trace(verified ? 'http_verified' : 'http_verify_failed', { url });
  if (!verified) {
    await showError(app, 'Backend is running but not answering',
      'HTTP readiness check failed for ' + url);
    return;
  }
  readyUrl = url;
  await openAppWindow(app, url);
}

async function openAppWindow(app, url) {
  trace('window_open_begin', { url });
  try {
    app.win.open('app', {
      page: url,
      title: 'بورس‌ترمینال — BorsTerminal',
      size: '1360x740',
      x: 0,
      y: 0,
    });
    app.window('app').show();
    app.window('app').zoom();
    trace('window_open');
  } catch (e) {
    trace('window_open_failed', { error: String(e).slice(0, 300) });
    await showError(app, 'Application window could not open', String(e));
    return;
  }
  injectProbe(app);
}

export function init(app) {
  start(app).catch(async (e) => {
    trace('fatal', { error: String(e && e.stack || e).slice(0, 600) });
    await showError(app, 'Shell failed to start', String(e));
  });
}

export async function onWindowClosed(id, app) {
  trace('window_closed', { id });
  if (stopping) return;
  if (id === 'app' || id === 'error') {
    stopping = true;
    trace('shutdown_wait_begin', { id });
    if (child && child.stdin) {
      try { child.stdin.close(); } catch { }
    }
    // The sidecar must finish uvicorn's shutdown before the shell dies, or the
    // launcher tears the child down mid-write. Keep the backend alive for it.
    let graceful = false;
    if (childExit) {
      const timer = sleep(15000).then(() => 'timeout');
      const won = await Promise.race([childExit.then((st) => ({ st })), timer]);
      graceful = won !== 'timeout';
      trace('shutdown_wait_done', { graceful, code: graceful ? (won.st && won.st.exit_status) : null });
      if (!graceful && child) {
        try { child.kill(); } catch { }
      }
    }
    trace('quit_requested', { id, graceful });
    app.quit();
  }
}
