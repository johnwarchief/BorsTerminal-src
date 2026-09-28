// توزیعِ دلیل‌های «ردیف در جدول نیست» رویِ فیدِ زنده، برایِ انتخابِ متنِ درستِ تولتیپِ +N
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const raw = readFileSync(resolve(process.cwd(), '_audit/rows_morning.json'), 'utf8');
const payload = JSON.parse(raw);
const rows = payload.data ?? payload;

const ZWNJ = new RegExp(String.fromCharCode(0x200c), 'g');
const norm = (s) => (s ?? '').replace(ZWNJ, '').replace(/ي/g, 'ی');
const DEFAULTS = new Set(['stock', 'payeh', 'right', 'energy', 'fund']);

function classify(d) {
  const name = norm(d.name);
  const sym = norm(d.symbol).toUpperCase();
  const sec = norm(d.sector_name);
  if (sym.startsWith('ض') || (sym.startsWith('ط') && !sym.startsWith('طال'))) return 'option';
  if (name.includes('صندوق') || name.includes('ETF') || sec.includes(norm('صندوق سرمايه'))) return 'fund';
  if (
    sym.startsWith('اخزا') || sym.startsWith('اراد') || sym.startsWith('افاد') || sym.startsWith('گام') ||
    name.includes('اوراق') || name.includes('اسناد') || sec.includes(norm('اوراق تامين'))
  ) return 'bond';
  if (sym.endsWith('ح') || name.includes('حق تقدم')) return 'right';
  if (sym.startsWith('تسه') || sym.startsWith('تملی') || name.includes('تسهیلات')) return 'teseh';
  if (sym.startsWith('طال') || sym.includes('TAL')) return 'tal';
  if (name.includes('آتی') && /[0-9]$/.test(sym)) return 'ati';
  if (sec.includes('کالا') || sym.includes('سلف') || name.includes('سلف')) return 'kala';
  if (sec.includes('انرژی') || sec.includes('برق') || name.includes('انرژی')) return 'energy';
  if (Number(d.board) === 2) return 'payeh';
  return 'stock';
}

const isSuffix = (s) => /[0-9\u06f0-\u06f9]$/.test((s ?? '').trim());
const FLAGS = ['f_clock', 'f_susp', 'f_jet', 'f_roobi', 'f_noqteh'];

const tally = {};
for (const f of FLAGS) {
  const all = rows.filter((r) => r[f] === true);
  const hidden = all.filter((r) => !(!isSuffix(r.symbol) && DEFAULTS.has(classify(r)) && r.is_live !== false));
  const t = { pass: all.length, hidden: hidden.length, suffix: 0, asset: 0, dead: 0, only: 0 };
  for (const r of hidden) {
    const s = isSuffix(r.symbol);
    const a = !DEFAULTS.has(classify(r));
    const d = r.is_live === false;
    if (s) t.suffix += 1;
    if (a) t.asset += 1;
    if (d) t.dead += 1;
    if ([s, a, d].filter(Boolean).length === 1) t.only += 1;
  }
  tally[f] = t;
}

console.log(`rows=${rows.length}`);
console.table(tally);
