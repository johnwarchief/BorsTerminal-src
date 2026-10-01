// @vitest-environment node
// تست یکپارچهٔ آداپتور محلی موبایل با «اسنپ‌شات واقعی» — همان زنجیره‌ای که
// روی گوشی اجرا می‌شود: gz → gunzip → sql.js → resolveLocal(/api/…).
//
// فقط وقتی اجرا می‌شود که dist_mobile/mobile_snapshot.db.gz از پختِ محلی موجود
// باشد (در CI گارد/دسکتاپ این فایل نیست ⇒ skip بی‌صدا). شبکهٔ بیرونی عمداً
// قطع شبیه‌سازی می‌شود تا ثابت شود مسیر آفلاین به‌تنهایی دادهٔ کامل می‌دهد —
// دقیقاً وضعیت «فید تابلو برنگشت» که مالک گزارش کرد.
import { beforeAll, describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const GZ = path.resolve(__dirname, '../../../dist_mobile/mobile_snapshot.db.gz');
const hasSnapshot = fs.existsSync(GZ);

// sql-wasm.wasm?url در vitest به مسیر واقعی فایل سوییچ می‌شود تا sql.js در
// node آن را از دیسک بخواند (در مرورگر همان URL باندل است).
const require_ = createRequire(import.meta.url);
vi.mock('sql.js/dist/sql-wasm.wasm?url', () => ({
  default: require_.resolve('sql.js/dist/sql-wasm.wasm'),
}));

describe.skipIf(!hasSnapshot)('آداپتور محلی موبایل — اسنپ‌شات واقعی، شبکهٔ قطع', () => {
  let resolveLocal: (url: string, m: 'GET' | 'POST' | 'PUT' | 'DELETE', b?: unknown) => Promise<unknown>;

  beforeAll(async () => {
    vi.stubGlobal('fetch', (async (input: unknown) => {
      const u = String(input);
      if (u.includes('mobile_snapshot.db.gz')) {
        return new Response(fs.readFileSync(GZ));
      }
      throw new TypeError(`شبکهٔ بیرونی در تست قطع است: ${u}`);
    }) as typeof fetch);
    ({ resolveLocal } = await import('../shared/api/local/resolvers'));
  }, 120000);

  it('تابلو (/api/market) آفلاین با صدها ردیف برمی‌گردد', async () => {
    const b = (await resolveLocal('/api/market', 'GET')) as { data?: unknown[] };
    expect(Array.isArray(b.data)).toBe(true);
    expect((b.data ?? []).length).toBeGreaterThan(100);
  }, 120000);

  it('اسکرینر و بنیادی فولاد از بسته‌های پخته می‌آیند', async () => {
    const s = (await resolveLocal('/api/screener', 'GET')) as { data?: unknown[] };
    expect((s.data ?? []).length).toBeGreaterThan(50);
    const f = (await resolveLocal('/api/fundamental/فولاد', 'GET')) as Record<string, unknown>;
    expect(f).toBeTruthy();
  }, 60000);

  it('چارت فولاد (/api/chart) در قطعی شبکه به پختِ محلی برمی‌گردد — نه خالی', async () => {
    const c = (await resolveLocal('/api/chart/فولاد', 'GET')) as {
      candles?: unknown[]; adjustEvents?: unknown[];
    };
    expect((c.candles ?? []).length).toBeGreaterThan(300);
    expect(c.adjustEvents).toEqual([]);
  }, 60000);

  it('history و order-book هم آفلاین سالم‌اند', async () => {
    const h = (await resolveLocal('/api/history/فولاد', 'GET')) as { candles?: unknown[] };
    expect((h.candles ?? []).length).toBeGreaterThan(300);
    const ob = (await resolveLocal('/api/order-book/فولاد', 'GET')) as { levels?: unknown[] };
    expect(Array.isArray(ob.levels ?? [])).toBe(true);
  }, 60000);
});
