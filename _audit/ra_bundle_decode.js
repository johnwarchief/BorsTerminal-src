// Decode the javascript-obfuscator string table in tradersarena's technicalChart bundle.
// Top-level function declarations leak onto the vm global; call each with every plausible
// index (the decoder subtracts an offset, so low indices throw) and dump index -> string.
const fs = require('fs'), vm = require('vm');
const src = fs.readFileSync(process.argv[2], 'utf8');

const nofun = new Proxy(function () {}, {
  get: (t, k) => (k === Symbol.toPrimitive || k === 'toString' ? () => '' : nofun),
  apply: () => nofun, construct: () => nofun, has: () => true,
});
const doc = new Proxy({ readyState: 'complete' }, { get: (t, k) => (k in t ? t[k] : nofun), set: () => true });
const win = new Proxy({ document: doc, location: { href: 'https://tradersarena.ir/', search: '' } },
  { get: (t, k) => (k in t ? t[k] : nofun), set: () => true });
const sandbox = {
  window: win, document: doc, navigator: nofun, localStorage: nofun, sessionStorage: nofun,
  fetch: nofun, XMLHttpRequest: nofun, setTimeout: (f) => f, setInterval: () => 0,
  console, String, Array, Object, Number, Math, JSON, parseInt, parseFloat, isNaN,
  encodeURIComponent, decodeURIComponent, atob: (s) => Buffer.from(s, 'base64').toString('binary'),
  btoa: (s) => Buffer.from(s, 'binary').toString('base64'), Date, RegExp, Function, Symbol, Map, Set, Promise, Error, Buffer,
};
sandbox.globalThis = sandbox; sandbox.self = win;
vm.createContext(sandbox);
let ran = 'ok';
try { vm.runInContext(src, sandbox, { filename: 'bundle.js', timeout: 20000 }); }
catch (e) { ran = 'threw: ' + String(e && e.message).slice(0, 160); }

const names = [...new Set([...src.matchAll(/\bfunction (_0x[0-9a-f]{4,})\s*\(/g)].map((m) => m[1]))];
const fns = names.filter((n) => typeof sandbox[n] === 'function');
const out = [];
for (const n of fns) {
  const f = sandbox[n];
  for (let i = 0; i < 8000; i++) {
    let v;
    try { v = f(i); } catch (e) { continue; }
    if (typeof v === 'string') out.push(`${n}:${i}\t${v}`);
  }
}
fs.writeFileSync(process.argv[3], out.join('\n'), 'utf8');
console.error(ran, '| name-decls:', names.length, '| callable:', fns.join(','), '| strings:', out.length);
