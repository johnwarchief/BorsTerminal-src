// shared/api/local/diagnostics.ts — پنل عیب‌یابی روی خود گوشی (فقط بیلد موبایل)
//
// چرا: گزارش «همه بی‌داده» از روی گوشی بدون لاگ قابل ریشه‌یابی نیست. این پنل
// با دکمهٔ شناور 🛠 باز می‌شود و همان چیزهایی را نشان می‌دهد که برای عیب‌یابی
// لازم است: برچسب بیلد (تا معلوم شود APK نصب‌شده واقعاً کدام است)، نسخهٔ
// WebView، وضعیت دیتابیس اسنپ‌شات، و دسترسی زنده به TSETMC.
//
// بدون React و بدون وابستگی به پوسته — حتی اگر کل UI از کار افتاده باشد، این
// پنل باید کار کند (همان فلسفهٔ بنر قرمز localData).
import { baked, metaValue, query, bootTiming } from './localData';
import { liveWatch } from './live';
import { overlayStatus } from './resolvers';

const BUILD_TAG = (import.meta.env.VITE_BUILD_TAG as string | undefined) ?? 'بیلد محلی';

function row(label: string, value: string, ok?: boolean): string {
  const mark = ok === undefined ? '' : ok ? ' ✅' : ' ❌';
  return `<div style="padding:4px 0;border-bottom:1px solid rgba(255,255,255,.08)">` +
         `<b>${label}:</b> ${value}${mark}</div>`;
}

async function collect(): Promise<string> {
  const parts: string[] = [];
  parts.push(row('بیلد', BUILD_TAG));
  parts.push(row('WebView', navigator.userAgent.match(/Chrome\/[\d.]+/)?.[0] ?? 'نامشخص'));
  const native = typeof (window as unknown as { Capacitor?: { isNativePlatform?: () => boolean } })
    .Capacitor?.isNativePlatform === 'function'
    ? (window as unknown as { Capacitor: { isNativePlatform: () => boolean } })
        .Capacitor.isNativePlatform()
    : false;
  parts.push(row('حالت', native ? 'اپ اندروید (بومی)' : 'مرورگر/پیش‌نمایش'));
  // دیتابیس اسنپ‌شات
  try {
    const builtAt = await metaValue('built_at');
    const ver = await metaValue('app_version');
    const n = await query('SELECT count(*) AS c FROM baked');
    parts.push(row('بستهٔ داده', `v${ver ?? '؟'} · ${builtAt ?? '؟'} · ${String(n[0]?.c ?? '؟')} بسته`, true));
    const board = (await baked('market_board')) as { data?: unknown[] } | null;
    const rows = Array.isArray(board?.data) ? board.data.length : 0;
    parts.push(row('تابلوی آفلاین', `${rows} ردیف`, rows > 0));
    // شمارشِ جهانِ داده — «کم بودنِ تب» data است یا UI، از همین‌جا خوانده می‌شود
    const scr = (await baked('screener')) as { count?: number; data?: unknown[] } | null;
    const screenRows = Array.isArray(scr?.data) ? scr.data.length : 0;
    parts.push(row('بنیادی (اسکرینر)', `${screenRows} ردیف · count=${scr?.count ?? '؟'}`, screenRows > 0));
    const perSymbol = await query(
      "SELECT substr(key, 1, instr(key, '/') - 1) AS grp, count(*) AS c FROM baked " +
      "WHERE instr(key, '/') > 0 GROUP BY grp ORDER BY c DESC");
    parts.push(row('پختِ هر-نماد', perSymbol.map((r) => `${String(r.grp)}=${String(r.c)}`).join(' · '), true));
    let ph = 'جدول price_history نیست';
    try {
      const hist = await query('SELECT count(*) AS n, count(DISTINCT symbol) AS s, min(date) AS a, max(date) AS b FROM price_history');
      const h = hist[0] ?? {};
      ph = `${String(h.n ?? 0)} کندل · ${String(h.s ?? 0)} نماد · ${String(h.a ?? '؟')} ← ${String(h.b ?? '؟')}`;
    } catch { /* اسنپ‌شاتِ بی‌تاریخچه — همان چیزی که پنل باید بگوید */ }
    parts.push(row('تاریخچۀ چارت', ph));
    const ov = overlayStatus();
    parts.push(row('آخرین رونشانیِ زندۀ تابلو', ov ? `${ov.patched} ردیف · ${ov.at}` : 'هنوز رونشانی نشده', !!ov));
  } catch (e) {
    parts.push(row('بستهٔ داده', e instanceof Error ? `${e.name}: ${e.message}` : String(e), false));
  }
  // زندهٔ TSETMC
  try {
    const mw = await liveWatch(1); // ttl=1ms ⇒ تست تازه، نه کشِ قبلی
    parts.push(row('TSETMC زنده', mw ? `${mw.size} نماد` : 'در دسترس نیست (آفلاین/فیلتر؟)', !!mw));
  } catch (e) {
    parts.push(row('TSETMC زنده', e instanceof Error ? e.message : String(e), false));
  }
  // زمان‌بندیِ راه‌اندازی — بی‌این عدد، هر «بهینه‌سازیِ سرعت» حدس است.
  // هر بار باز کردنِ اپ یعنی گشودنِ بستهٔ gzip و ساختنِ دیتابیس در حافظه؛
  // اینجا معلوم می‌شود کدام پله واقعاً گران است و رویِ *این* گوشی چقدر.
  {
    const t = bootTiming;
    const mb = (n: number) => (n / 1048576).toFixed(1);
    const srcLabel = { cache: 'کشِ دستگاه', bundle: 'همراهِ APK',
                       release: 'دانلود از ریلیز', '': '—' }[t.source];
    parts.push(row('منبعِ بسته', srcLabel));
    parts.push(row(
      'راه‌اندازی',
      t.totalMs
        ? `${t.totalMs}ms  (دریافت ${t.fetchMs} · بازگشایی ${t.gunzipMs} · باز کردن ${t.openMs})`
        : 'هنوز دیتابیس باز نشده',
      t.totalMs > 0 && t.totalMs < 6000,
    ));
    if (t.rawBytes) {
      parts.push(row('حجمِ بسته', `${mb(t.gzBytes)}MB فشرده ← ${mb(t.rawBytes)}MB در حافظه`));
    }
  }
  parts.push(row('صفحه', `${window.innerWidth}×${window.innerHeight} · bors-mobile=` +
    String(document.documentElement.classList.contains('bors-mobile'))));
  return parts.join('');
}

export function mountDiagnostics(): void {
  if (document.getElementById('bors-diag-btn')) return;
  const btn = document.createElement('button');
  btn.id = 'bors-diag-btn';
  btn.textContent = '🛠';
  btn.style.cssText =
    'position:fixed;bottom:70px;left:8px;z-index:9998;width:34px;height:34px;' +
    'border-radius:50%;border:1px solid rgba(255,255,255,.2);background:rgba(20,20,30,.75);' +
    'color:#fff;font-size:16px;line-height:1;opacity:.55';
  btn.addEventListener('click', () => {
    const old = document.getElementById('bors-diag-panel');
    if (old) { old.remove(); return; }
    const panel = document.createElement('div');
    panel.id = 'bors-diag-panel';
    panel.dir = 'rtl';
    panel.style.cssText =
      'position:fixed;bottom:112px;left:8px;right:8px;z-index:9998;max-height:55vh;' +
      'overflow-y:auto;background:rgba(10,12,20,.96);color:#e5e7eb;border:1px solid ' +
      'rgba(255,255,255,.15);border-radius:10px;padding:10px 12px;font-size:12px;' +
      'line-height:1.9;font-family:inherit;word-break:break-word;direction:rtl;text-align:right';
    panel.innerHTML = '<div>در حال جمع‌آوری وضعیت…</div>';
    document.body.appendChild(panel);
    void collect()
      .then((html) => { panel.innerHTML = html; })
      .catch((e: unknown) => {
        panel.textContent = `خطای عیب‌یابی: ${e instanceof Error ? e.message : String(e)}`;
      });
  });
  document.body.appendChild(btn);
}
