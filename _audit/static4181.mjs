import { createServer } from 'node:http';
import { createReadStream, statSync, existsSync } from 'node:fs';
import path from 'node:path';
const ROOT = 'C:/Users/PCMOD/Desktop/BorsTerminal-android/frontend/dist';
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.wasm': 'application/wasm',
  '.json': 'application/json', '.ttf': 'font/ttf', '.woff2': 'font/woff2', '.svg': 'image/svg+xml' };
createServer((req, res) => {
  const rel = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  let f = path.join(ROOT, rel === '/' ? '/index.html' : rel);
  if (!existsSync(f) || statSync(f).isDirectory()) f = path.join(ROOT, 'index.html');
  const ctype = f.endsWith('.gz') ? 'text/plain' : (TYPES[path.extname(f)] ?? 'application/octet-stream');
  res.writeHead(200, { 'Content-Type': ctype,
                      'Content-Length': statSync(f).size, 'Cache-Control': 'no-store' });
  createReadStream(f).pipe(res);
}).listen(4181, '127.0.0.1', () => console.log('static on 4181'));
