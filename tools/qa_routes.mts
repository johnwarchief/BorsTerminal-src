// tools/qa_routes.mts — جدولِ routeها را از خودِ router بخوان، نه از حافظه
//
// چرا این فایل هست: `tools/clip_audit.mts` رویِ main هنوز `['tape', '#/']` را
// «تابلو» می‌شمرد، درحالی‌که از رأیِ مالکِ ۱۴۰-۰۷-۱۷ مسیرِ خالی به `/master`
// redirect می‌شود. یعنی آزمونِ ریسپانسیو یکِ صفحه را دو بار سنجید و سه صفحه‌ای
// را که بعداً اضافه شدند (market-status، notifications، watch، engine-lab) هرگز
// ندید. هیچ‌کس متوجه نشد، چون جدولِ دستی هیچ‌وقت باِ کد مقایسه نمی‌شد.
//
// راهِ رفع، درست‌کردنِ ابزار است نه دست‌زدنِ router محصول: فهرست از
// `frontend/src/routes.tsx` پارس می‌شود و اگر شمارِ routeها با انتظارِ سندِ QA
// نخواند، خودِ کاوشگر می‌ایستد.
import { readFileSync, existsSync } from 'node:fs';

export type RouteKind = 'page' | 'redirect' | 'fallback';
export type RouteSpec = {
  name: string;
  path: string;
  hash: string;
  kind: RouteKind;
  component: string;
};

const SAMPLE_SYMBOL = 'فولاد';

/** آرایۀ mainRoutes را از routes.tsx درمی‌یابد و به spec تبدیل می‌کند. */
export function readRoutes(repoRoot = '.'): RouteSpec[] {
  const file = `${repoRoot}/frontend/src/routes.tsx`;
  if (!existsSync(file)) throw new Error(`router not found: ${file}`);
  const src = readFileSync(file, 'utf8');
  const start = src.indexOf('mainRoutes');
  if (start < 0) throw new Error('mainRoutes not found in routes.tsx');
  const body = src.slice(start);

  const out: RouteSpec[] = [];
  // هر ورودی با path: شروع می‌شود و تا '},' یا پایانِ آرایه ادامه دارد
  const entry = /path:\s*'([^']*)'([\s\S]*?)(?=\n\s*\{\s*path:|\n\s*\}\s*\];|\n\s*\];)/g;
  let m: RegExpExecArray | null;
  while ((m = entry.exec(body))) {
    const path = m[1];
    const chunk = m[2];
    const imp = /import\('@?([^']+)'\)/.exec(chunk);
    let kind: RouteKind = 'page';
    if (/Navigate\s+to=/.test(chunk)) kind = 'redirect';
    else if (/route-not-found/.test(chunk)) kind = 'fallback';
    const component = imp ? imp[1] : (kind === 'redirect' ? 'Navigate' : 'inline');
    const base = path.replace(/\/?:[^/]+\/?$/, '').replace(/:symbol\??$/, '');
    const needsSymbol = /:symbol\?/.test(path);
    const hash = '#/' + (kind === 'fallback'
      ? 'qa-route-that-does-not-exist'
      : base + (needsSymbol ? '/' + encodeURIComponent(SAMPLE_SYMBOL) : ''));
    out.push({
      name: path === '' ? 'root' : (path === '*' ? 'not-found' : path.replace(/\/?:\w+\??$/, '')),
      path,
      hash,
      kind,
      component,
    });
  }
  if (out.length === 0) throw new Error('routes.tsx parsed but zero entries matched — the parser is broken, not the app');
  return out;
}

/** نامِ مقصدِ یکِ redirect را از متنِ router می‌خواند (برایِ سنجشِ «#/ → /master»). */
export function redirectTarget(repoRoot = '.'): string {
  const src = readFileSync(`${repoRoot}/frontend/src/routes.tsx`, 'utf8');
  const m = /Navigate\s+to="([^"]+)"/.exec(src);
  return m ? m[1] : '';
}
