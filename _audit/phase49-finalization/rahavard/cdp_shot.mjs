// Read-only CDP probe: location/title/text + screenshot of the attached tab.
import fs from 'node:fs';
import crypto from 'node:crypto';

const port = Number(process.argv[2] || 9333);
const out = process.argv[3] || 'shot.png';

async function json(url) {
  const r = await fetch(url);
  return r.json();
}

class Cdp {
  constructor(ws) { this.ws = ws; this.id = 0; this.pending = new Map(); }
  static async attach(wsUrl) {
    const ws = new WebSocket(wsUrl);
    const c = new Cdp(ws);
    ws.addEventListener('message', (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id && c.pending.has(m.id)) {
        const { resolve, reject } = c.pending.get(m.id);
        c.pending.delete(m.id);
        m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result);
      }
    });
    await new Promise((res, rej) => {
      ws.addEventListener('open', res, { once: true });
      ws.addEventListener('error', () => rej(new Error('ws failed')), { once: true });
    });
    return c;
  }
  send(method, params = {}) {
    const id = ++this.id;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }
  async eval(expr) {
    const r = await this.send('Runtime.evaluate',
      { expression: expr, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails).slice(0, 400));
    return r.result ? r.result.value : null;
  }
}

const list = await json(`http://127.0.0.1:${port}/json/list`);
const pages = list.filter((t) => t.type === 'page' && t.webSocketDebuggerUrl);
const target = pages.find((t) => String(t.url).includes('rahavard365.com')) || pages[0];
console.log('target', target && target.url);
const cdp = await Cdp.attach(target.webSocketDebuggerUrl);
const info = await cdp.eval(`({
  href: location.href, title: document.title,
  readyState: document.readyState,
  text: (document.body && document.body.innerText || '').slice(0, 800),
  errorPage: (document.documentElement.innerHTML || '').includes('ERR_')
})`);
console.log(JSON.stringify(info, null, 1));
const shot = await cdp.send('Page.captureScreenshot', { format: 'png' });
const buf = Buffer.from(shot.data, 'base64');
fs.writeFileSync(out, buf);
console.log('screenshot', out, buf.length, 'sha256', crypto.createHash('sha256').update(buf).digest('hex'));
cdp.ws.close();
