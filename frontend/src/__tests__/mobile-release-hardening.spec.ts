// invariantsِ انتشارِ اندروید — چیزی که درِ CSS/manifest/Gradle زندگی می‌کند و
// هیچ آزمونِ رفتاریِ مرورگر نمی‌بیندش. متنِ فایل خوانده می‌شود (همان الگویِ
// mobile-portrait.spec.ts) چون این‌ها قراردادِ بسته‌بندی‌اند، نه رفتارِ React:
// اگر روزی کسی `allowBackup` را برگرداند یا `viewport-fit` را از index.html
// بردارد، رویِ گوشی می‌شکند ولی jsdom هیچ‌وقت قرمز نمی‌شود.
import { describe, expect, it } from 'vitest';
import fs from 'node:fs';
import { esc, row } from '@shared/api/local/diagnostics';

const html = fs.readFileSync('index.html', 'utf8');
const css = fs.readFileSync('src/shared/styles/mobile.css', 'utf8');
const manifest = fs.readFileSync('android/app/src/main/AndroidManifest.xml', 'utf8');
const nsc = fs.readFileSync('android/app/src/main/res/xml/network_security_config.xml', 'utf8');
const gradle = fs.readFileSync('android/app/build.gradle', 'utf8');
const capconf = fs.readFileSync('capacitor.config.ts', 'utf8');
const boot = fs.readFileSync('src/app/components/MobileBootstrap.tsx', 'utf8');

describe('invariantsِ انتشارِ اندروید', () => {
  it('viewport-fit=cover نشسته تا env(safe-area-inset-*) رویِ گوشی صفر نباشد', () => {
    const m = html.match(/<meta name="viewport" content="([^"]+)"/);
    expect(m).not.toBeNull();
    expect(m![1]).toContain('viewport-fit=cover');
    expect(m![1]).toContain('width=device-width');
  });

  it('بدنه و بنرِ هشدار، بلندای ناوتی‌بار و نوارِ پایین را حساب می‌کنند', () => {
    // عددِ جادوییِ جدا (66px اینجا، 58px آن‌جا) همان چیزی بود که با هر تغییرِ
    // نوار یکی از them جا می‌ماند؛ حالا همه ازِ --bors-nav-h می‌آیند.
    expect(css).toMatch(/\.app-content\s*\{\s*padding-bottom:\s*calc\(var\(--bors-nav-h\) \+ 8px \+ env\(safe-area-inset-bottom\)\)/);
    expect(css).toMatch(/\[data-testid="price-alert-banner"\]\s*\{\s*bottom:\s*calc\(var\(--bors-nav-h\) \+ 1rem \+ env\(safe-area-inset-bottom\)\)/);
  });

  it('همۀ فاصله‌هایِ پایین ازِ یکِ متغیر می‌آیند (نه عددِ جداگانه)', () => {
    const users = ['--bors-nav-h) + 8px + env', '--bors-nav-h) + 1rem + env',
      '--bors-nav-h) + env', '--bors-nav-h, 104px) + 8px + env'];
    const all = css + fs.readFileSync('src/shared/api/local/diagnostics.ts', 'utf8');
    for (const u of users) expect(all).toContain(u);
    expect(css).toMatch(/--bors-nav-h: \d+px/);
  });

  it('پنلِ عیب‌یابی هم با viewport-fit=cover زیرِ نوارِ سیستم نمی‌ماند', () => {
    const diag = fs.readFileSync('src/shared/api/local/diagnostics.ts', 'utf8');
    expect(diag).toContain('calc(var(--bors-nav-h, 66px) + 6px + env(safe-area-inset-bottom))');
    expect(diag).toContain('calc(var(--bors-nav-h, 66px) + 48px + env(safe-area-inset-bottom))');
  });

  it('پشتیبانِ ابری و `adb backup` خاموش‌اند، صفحه‌کلید فشرده نمی‌کند', () => {
    expect(manifest).toMatch(/android:allowBackup="false"/);
    expect(manifest).toMatch(/android:windowSoftInputMode="adjustResize"/);
    expect(manifest).toMatch(/android:networkSecurityConfig="@xml\/network_security_config"/);
    // تنها مجوزِ لازم INTERNET است؛ هیچ چیزِ دیگری اضافه نشده باشد.
    const perms = [...manifest.matchAll(/uses-permission android:name="([^"]+)"/g)].map((x) => x[1]);
    expect(perms).toEqual(['android.permission.INTERNET']);
  });

  it('cleartext درِ پیکربندیِ شبکه بسته است و system anchors تنها مبنایِ اعتماد', () => {
    expect(nsc).toMatch(/cleartextTrafficPermitted="false"/);
    expect(nsc).toMatch(/<certificates src="system" \/>/);
    expect(nsc).not.toMatch(/user/);           // هیچ TrustStoreِ اضافه‌ای نصب نشده
    expect(capconf).toMatch(/allowMixedContent:\s*false/);
  });

  it('بیلدِ release: امضا فقط از keystoreِ پروژه، هرگز از debug.keystore', () => {
    expect(gradle).toMatch(/debuggable false/);
    expect(gradle).toMatch(/signingConfig signingConfigs\.borsRelease/);
    expect(gradle).toContain('debug.keystore');   // ردِّ صریحِ کلیدِ debug
    expect(gradle).toMatch(/throw new GradleException\(.BORS-SIGN: storeFile به debug\.keystore/);
    // رمز ازِ فرمانِ gradlew نمی‌آید؛ تنها مسیرِ فایلِ properties رد می‌شود.
    expect(gradle).toMatch(/System\.getenv\('BORS_KEYSTORE_PROPERTIES'\)/);
  });

  it('شیءِ خطا (با stack و URLِ پاسخ) درِ console نمی‌نشیند', () => {
    const logs = [...boot.matchAll(/console\.(log|error|warn|info)\(([^)]*)\)/g)].map((x) => x[2]);
    expect(logs.length).toBeGreaterThan(0);
    for (const line of logs) {
      // فقط رشتهٔ نقل‌قولی؛ هیچ شناسه‌ای مثلِ `err` به‌عنوان آرگومان نرود.
      expect(line).toMatch(/^'[^']*'$/);
    }
  });

  it('هر مقدارِ کنترل‌نشده پیش ازِ innerHTML گریز می‌کند', () => {
    expect(esc('<b a="x">&\'')).toBe('&lt;b a=&quot;x&quot;&gt;&amp;&#39;');
    const hostile = row('بستۀ فعال', '<img src=x onerror=alert(1)>');
    expect(hostile).not.toContain('<img');
    expect(hostile).toContain('&lt;img');
  });
});
