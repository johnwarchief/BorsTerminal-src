// tools/funnel_prove_api.mts — رانرِ اثباتِ قیف روی APIِ زنده (مرحلۀ #81)
//
// entry در `_audit/tmp/funnel_prove_entry.ts` با esbuild باندل می‌شود (aliasهای
// tsconfigِ فرانت لازم است؛ پس cwd = frontend/) و باندل با node اجرا می‌شود
// (cwd = ریشهٔ ریپو تا خروجیِ `_audit/…` سرِ جای خود بنشیند).
//
// فرمان:
//   node --experimental-strip-types tools/funnel_prove_api.mts
// متغیرها:
//   FUNNEL_BASE (پیش‌فرض http://127.0.0.1:8002) — «نسخهٔ دوم dev» نه اپِ نصبیِ 8001
//   FUNNEL_OUT  (پیش‌فرض _audit/funnel_prove_8002.json)
import { execFileSync, execSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..');

const TS_ENTRY = join(ROOT, '_audit', 'tmp', 'funnel_prove_entry.ts');
const MJS_OUT = join(ROOT, '_audit', 'tmp', 'funnel_prove_entry.mjs');
const FRONTEND = join(ROOT, 'frontend');

if (!existsSync(join(FRONTEND, 'tsconfig.json'))) {
  console.error('[prove] frontend/tsconfig.json پیدا نشد — از ریشۀ ریپو اجرا کنید.');
  process.exit(2);
}
if (!existsSync(TS_ENTRY)) {
  console.error('[prove] ورودیِ سنجش پیدا نشد: ' + TS_ENTRY);
  process.exit(2);
}

console.log('[prove] esbuild — باندلِ entry با aliasهای فرانت…');
execSync(
  `npx esbuild "${TS_ENTRY}" --bundle --format=esm --platform=node --tsconfig=tsconfig.json --outfile="${MJS_OUT}"`,
  { cwd: FRONTEND, stdio: 'inherit' },
);

console.log('[prove] node — اجرای باندل روی ' + (process.env.FUNNEL_BASE ?? 'http://127.0.0.1:8002'));
execFileSync(process.execPath, [MJS_OUT], {
  cwd: ROOT,
  stdio: 'inherit',
  env: {
    ...process.env,
    FUNNEL_BASE: process.env.FUNNEL_BASE ?? 'http://127.0.0.1:8002',
    FUNNEL_OUT: process.env.FUNNEL_OUT ?? '_audit/funnel_prove_8002.json',
  },
});
