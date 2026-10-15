// shared/api/local/diagnostics.ts — پنل عیب‌یابی روی خود گوشی (فقط بیلد موبایل)
//
// چرا: گزارش «همه بی‌داده» از روی گوشی بدون لاگ قابل ریشه‌یابی نیست. این پنل
// با دکمهٔ شناور 🛠 باز می‌شود و همان چیزهایی را نشان می‌دهد که برای عیب‌یابی
// لازم است: برچسب بیلد (تا معلوم شود APK نصب‌شده واقعاً کدام است)، نسخهٔ
// WebView، وضعیت دیتابیس اسنپ‌شات، و دسترسی زنده به TSETMC.
//
// بدون React و بدون وابستگی به پوسته — حتی اگر کل UI از کار افتاده باشد، این
// پنل باید کار کند (همان فلسفهٔ بنر قرمز localData).
import { baked, metaValue, query, bootTiming, snapshotStatus, requestManualCheck,
  rollbackToPreviousPackage } from './localData';
import { liveWatch } from './live';
import { overlayStatus } from './resolvers';

const BUILD_TAG = (import.meta.env.VITE_BUILD_TAG as string | undefined) ?? 'بیلد محلی';

/** مقدارهایی که پنل نشان می‌دهد ازِ بیرون می‌آیند: `package_id` و `built_at`
 *  از manifestِ ریموت، `detail` و `message` از رشته‌هایِ خطایِ شبکه/JSON.
 *  پنل با `innerHTML` ساخته می‌شود، پس یک manifestِ دست‌خورده (یا خطایی که
 *  تکه‌ای از پاسخ را بازمی‌گرداند) می‌توانست درِ WebView اسکریپت شود — با
 *  همان دسترسیِ برنامه به دیتابیسِ محلی و پلِ بومی. تنها راهِ درست: هرِ
 *  مقدارِ کنترل‌نشده پیش ازِ درج درِ HTML گریز می‌گیرد. */
/** بیرون‌داده شده تا دروازۀ گریز درِ تست مستقیم دیده شود (تستِ متنِ CSS
 *  این را نمی‌گیرد و آزمونِ رفتاریِ پنل به `localData` وابسته است). */
export function esc(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

export function row(label: string, value: string, ok?: boolean): string {
  const mark = ok === undefined ? '' : ok ? ' ✅' : ' ❌';
  return `<div style="padding:4px 0;border-bottom:1px solid rgba(255,255,255,.08)">` +
         `<b>${esc(label)}:</b> ${esc(value)}${mark}</div>`;
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
  // وضعیتِ چرخۀِ بسته: کدام نسخۀ **اعتبارسنجی‌شده** فعال است، آخرینِ نتیجه چه بود،
  // و چندِ شکست پشتِ هم جمع شده (backoff). بی‌این، «داده کهنه است یا دانلود شکست
  // خورد؟» رویِ گوشیِ کاربر پاسخ‌نداشت — و کاربر راهِ دیگری جزِ پاک‌کردنِ کش نداشت.
  {
    const st = snapshotStatus();
    parts.push(row('بستۀِ فعال', st.packageId ? `${st.packageId} · ${st.builtAt}` : 'بستۀ همراهِ برنامه (بی‌فعال‌سازیِ تازه)', !!st.packageId));
    parts.push(row('آخرینِ نتیجه', st.lastOutcome
      ? `${st.lastOutcome.ok ? 'موفق' : 'ناموفق'}: ${st.lastOutcome.detail}`
      : 'هنوز بررسی نشده', st.lastOutcome ? st.lastOutcome.ok : undefined));
    if (st.failStreak > 0) {
      const mins = Math.max(0, Math.round((st.nextTryAt - Date.now()) / 60000));
      parts.push(row('تلاشِ دوباره', `${st.failStreak} شکستِ پی‌درپی · ${mins} دقیقه دیگر`));
    }
    if (st.lastOkAt) parts.push(row('آخرینِ فعال‌سازیِ موفق', new Date(st.lastOkAt).toLocaleString('fa-IR')));
    parts.push('<div id="bors-diag-check"></div>');
    parts.push('<div id="bors-diag-rollback"></div>');
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
    // با viewport-fit=cover (تازۀ index.html) WebView تا زیرِ ناوتی‌بارِ سیستم
    // می‌رود؛ بی‌این env() دکمهٔ 🛠 و پنلش رویِ گوشی‌هایِ سه‌دکمه‌ای زیرِ
    // نوارِ سیستم می‌ماند و «دکمه غیب شده» به نظر می‌رسد.
    'position:fixed;bottom:calc(70px + env(safe-area-inset-bottom));left:8px;z-index:9998;' +
    'width:34px;height:34px;' +
    'border-radius:50%;border:1px solid rgba(255,255,255,.2);background:rgba(20,20,30,.75);' +
    'color:#fff;font-size:16px;line-height:1;opacity:.55';
  btn.addEventListener('click', () => {
    const old = document.getElementById('bors-diag-panel');
    if (old) { old.remove(); return; }
    const panel = document.createElement('div');
    panel.id = 'bors-diag-panel';
    panel.dir = 'rtl';
    panel.style.cssText =
      'position:fixed;bottom:calc(112px + env(safe-area-inset-bottom));left:8px;right:8px;z-index:9998;max-height:55vh;' +
      'overflow-y:auto;background:rgba(10,12,20,.96);color:#e5e7eb;border:1px solid ' +
      'rgba(255,255,255,.15);border-radius:10px;padding:10px 12px;font-size:12px;' +
      'line-height:1.9;font-family:inherit;word-break:break-word;direction:rtl;text-align:right';
    panel.innerHTML = '<div>در حال جمع‌آوری وضعیت…</div>';
    document.body.appendChild(panel);
    const render = (html: string) => {
      panel.innerHTML = html;
      const slot = panel.querySelector('#bors-diag-check');
      if (!slot) return;
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = 'بررسی دستیِ به‌روزرسانی داده';
      b.style.cssText =
        'width:100%;margin:8px 0;padding:10px;border-radius:8px;border:1px solid rgba(255,255,255,.25);' +
        'background:rgba(37,99,235,.25);color:#e5e7eb;font:inherit;font-size:12px';
      b.addEventListener('click', () => {
        b.disabled = true;
        b.textContent = 'در حال بررسی…';
        void requestManualCheck()
          .then((out) => {
            // نتیجه از خودِ وضعیت خوانده می‌شود، نه از چیزی که اینجا حدس بزنیم:
            // «موفق» فقط وقتی است که اعتبارسنجی کامل شده و pointer جابه‌جا شده باشد.
            b.textContent = out?.ok ? 'بررسی شد — نسخۀ تازه فعال شد'
              : out ? `بررسی نشد: ${out.detail}` : 'بررسی لازم نبود (پنجرۀ زمانی یا بی‌اتصال)';
            setTimeout(() => { void show(); }, 1200);
          })
          .catch((e: unknown) => {
            b.textContent = `خطا: ${e instanceof Error ? e.message : String(e)}`;
          });
      });
      slot.appendChild(b);
      // بازگشت به آخرین بستۀِ **فعال‌شدۀِ معتبر**. بی‌این دکمه، اگر یکِ بستۀِ
      // خرابِ تازه فعال می‌شد و برنامه رویِ دادهٔ کهنه می‌ماند، کاربر رویِ گوشی
      // هیچ راهی جز پاک‌کردنِ کش نداشت — و پاک‌کردنِ کش هر دو بسته را می‌برد.
      const prevId = snapshotStatus().previousPackageId;
      if (prevId) {
        const rbSlot = panel.querySelector('#bors-diag-rollback');
        if (rbSlot) {
          const rb = document.createElement('button');
          rb.type = 'button';
          rb.textContent = `بازگشت به نسخۀ پیشین (${prevId})`;
          rb.style.cssText =
            'width:100%;margin:8px 0;padding:10px;border-radius:8px;border:1px solid rgba(255,255,255,.25);' +
            'background:rgba(120,80,20,.25);color:#e5e7eb;font:inherit;font-size:12px';
          rb.addEventListener('click', () => {
            rb.disabled = true;
            rb.textContent = 'در حال بازگشت…';
            void rollbackToPreviousPackage()
              .then((r) => {
                rb.textContent = r.ok ? `بازگشت شد: ${r.detail}` : `بازنگشت: ${r.detail}`;
                setTimeout(() => { void show(); }, 900);
              })
              .catch((e: unknown) => {
                rb.textContent = `خطا: ${e instanceof Error ? e.message : String(e)}`;
              });
          });
          rbSlot.appendChild(rb);
        }
      }
    };
    const show = () => collect().then(render).catch((e: unknown) => {
      panel.textContent = `خطای عیب‌یابی: ${e instanceof Error ? e.message : String(e)}`;
    });
    void show();
  });
  document.body.appendChild(btn);
}
