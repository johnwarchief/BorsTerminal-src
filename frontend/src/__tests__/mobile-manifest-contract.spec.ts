// __tests__/mobile-manifest-contract.spec.ts — سمتِ کلاینتِ قراردادِ manifest
//
// طرفِ دیگر این سنج، `dev/mobile_manifest_contract_v1115.py` است: آن گارد بستۀ
// واقعی می‌سازد و fixture را درِ `dev/fixtures/mobile_manifest_v2.json` می‌گذارد.
// این آزمون همان fixture را به `parseManifest()` واقعی می‌دهد. پس اگر سازنده
// فیلدی را کم بگذارد این‌جا می‌شکند، و اگر کلاینت فهرستِ الزامی را عوض کند،
// گاردِ پایتونی (که فهرست را ازِ همین سورس می‌خواند) می‌شکند. دو طرف، دو سنج.
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  ACCEPTED_MANIFEST_SCHEMA,
  parseManifest,
  type SnapshotManifest,
} from '@shared/api/local/snapshotPackage';

// vitest درِ frontend/ اجرا می‌شود و import.meta.url آن‌جا file: نیست؛ پس fixture
// ازِ بالاترین پوشه‌ای خوانده می‌شود که dev/fixtures در آن هست (ازِ frontend/ یا
// ریشۀ مخزن، هر دو کار می‌کند — و بی‌پیدا شدن، خطا مسیرِ آزمایش‌شده را می‌گوید).
function fixturePath(): string {
  let dir = process.cwd();
  for (let i = 0; i < 5; i++) {
    const p = join(dir, 'dev', 'fixtures', 'mobile_manifest_v2.json');
    if (existsSync(p)) return p;
    dir = dirname(dir);
  }
  throw new Error('fixture پیدا نشد؛ از ' + process.cwd() + ' تا چهار سطح بالا گشتم');
}

function real(): Record<string, unknown> {
  return JSON.parse(readFileSync(fixturePath(), 'utf-8')) as Record<string, unknown>;
}

const REQUIRED_STRINGS = ['package_id', 'built_at', 'gz_sha256', 'app_version', 'min_app_version'];

describe('قراردادِ manifest (schema 2) — همان چیزی که سازنده می‌نویسد', () => {
  it('۱) manifestِ واقعیِ سازنده پذیرفته می‌شود و همان اعداد را نگه می‌دارد', () => {
    const parsed = parseManifest(real());
    expect(parsed.ok).toBe(true);
    if (!parsed.ok) return;
    const m = parsed.value as SnapshotManifest;
    const src = real();
    expect(m.schema_version).toBe(ACCEPTED_MANIFEST_SCHEMA);
    expect(m.package_id).toBe(src.package_id);
    expect(m.gz_sha256).toBe(src.gz_sha256);
    expect(m.gz_bytes).toBe(src.gz_bytes);
    expect(m.series).toBe('mobile-latest-v2');
  });

  it('۲) هر فیلدِ رشته‌ایِ الزامی: غایب ⇒ رد، و رشتهٔ خالی هم ⇒ رد', () => {
    for (const k of REQUIRED_STRINGS) {
      const a = real();
      delete a[k];
      expect(parseManifest(a)).toMatchObject({ ok: false, reason: 'manifest-field-missing' });
      const b = real();
      b[k] = '';
      expect(parseManifest(b)).toMatchObject({ ok: false, reason: 'manifest-field-missing' });
    }
  });

  it('۳) نوعِ غلط رد می‌شود، نه «تبدیلِ بی‌آزمون»', () => {
    const numStr = real();
    numStr.gz_bytes = String(real().gz_bytes);     // Number('…') عدد می‌دهد ولی درِ منبع رشته است
    expect(parseManifest(numStr)).toMatchObject({ ok: false, reason: 'manifest-field-missing' });
    const neg = real();
    neg.gz_bytes = -5;
    expect(parseManifest(neg)).toMatchObject({ ok: false, reason: 'manifest-field-missing' });
    for (const k of REQUIRED_STRINGS) {
      const o = real();
      o[k] = 7;                              // عدد به‌جای رشته
      expect(parseManifest(o)).toMatchObject({ ok: false, reason: 'manifest-field-missing' });
    }
  });

  it('۴) gz_sha256 با شکلِ اشتباه (۶۳ هگز، یا حرفِ نامعتبر) رد می‌شود', () => {
    const short = real();
    short.gz_sha256 = String(short.gz_sha256).slice(0, 63);
    expect(parseManifest(short)).toMatchObject({ ok: false, reason: 'manifest-field-missing' });
    const bad = real();
    bad.gz_sha256 = 'z' + String(bad.gz_sha256).slice(1);
    expect(parseManifest(bad)).toMatchObject({ ok: false, reason: 'manifest-field-missing' });
  });

  it('۵) schema_versionِ ناشناخته (۱ = نسلِ کهنه) رد می‌شود، نه پذیرشِ تلویحی', () => {
    for (const sv of [1, 3, 0]) {
      const o = real();
      o.schema_version = sv;
      expect(parseManifest(o)).toMatchObject({ ok: false, reason: 'manifest-schema-unknown' });
    }
    const nan = real();
    nan.schema_version = '2abc';            // Number('2abc') = NaN ⇒ «نیست»، نه «ناشناخته»
    expect(parseManifest(nan)).toMatchObject({ ok: false, reason: 'manifest-field-missing' });
    const gone = real();
    delete gone.schema_version;
    expect(parseManifest(gone)).toMatchObject({ ok: false, reason: 'manifest-field-missing' });
  });

  it('۶) پاسخِ بی‌ساختار (null، رشته، آرایه) به‌عنوان manifest پذیرفته نمی‌شود', () => {
    expect(parseManifest(null)).toMatchObject({ ok: false, reason: 'manifest-missing' });
    expect(parseManifest(undefined)).toMatchObject({ ok: false, reason: 'manifest-missing' });
    expect(parseManifest('<html>404</html>')).toMatchObject({ ok: false, reason: 'manifest-unparsable' });
    expect(parseManifest('')).toMatchObject({ ok: false, reason: 'manifest-unparsable' });
  });
});
