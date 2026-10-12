// __tests__/mobile-manifest-signature.spec.ts — اصالتِ manifest (مرحلۀ ۲، دور ۴ اندروید)
//
// سه چیز جدا آزمون می‌شود (نباید یکی خوانده شوند):
//   الف) **پلِ پایتون⇄تایپاسکریپت**: بلوکِ `.sig` تولیدشده با
//      `scripts/sign_mobile_manifest.py` درِ WebCrypto هم بررسی می‌شود (fixtureِ
//      commit‌شده؛ کلید خصوصیش هرگز commit نشده).
//   ب) **رد**: تغییرِ یکِ بایتِ manifest، امضایِ نامعتبر، کلیدِ اشتباه، امضایِ
//      مفقود، بلوکِ ناقص، و الگوریتمِ `ED` (پیش‌هشِ blake2b — درِ WebView
//      بررسی‌ناپذیر است، پس باید صریح رد شود نه «بساز و بفرست»).
//   پ) **fail-closed**: بی‌کلیدِ عمومی درِ بیلد، هیچ بسته‌ای پذیرفته نمی‌شود.
//
// دادهٔ کاربر و نسخۀ سالمِ پیشین در آزمون‌هایِ چرخهٔ بسته سنجیده می‌شود
// (`mobile-snapshot-integrity.spec.ts`) — اینجا فقطِ لایۀ اصالت.
import { createHash, createPrivateKey, generateKeyPairSync, sign as nodeSign, webcrypto } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { beforeAll, describe, expect, it, vi } from 'vitest';

import {
  ACCEPTED_SIG_ALG, bundledManifestPublicKey, keyIdOfRawPublic, parseSigBlock,
  verifyManifestSignature,
} from '@shared/api/local/manifestSignature';

const FIX = join(__dirname, 'fixtures', 'mobile_manifest_signed');
const MANIFEST_TEXT = readFileSync(join(FIX, 'manifest.json'), 'utf-8');
const SIG_TEXT = readFileSync(join(FIX, 'manifest.json.sig'), 'utf-8');
const PUB_B64 = readFileSync(join(FIX, 'pubkey.txt'), 'utf-8').trim();
const EXPECTED = JSON.parse(readFileSync(join(FIX, 'EXPECTED.json'), 'utf-8'));

const enc = (s: string): ArrayBuffer => {
  const u = new TextEncoder().encode(s);
  return u.slice().buffer as ArrayBuffer;
};
const b64 = (b: Uint8Array): string => Buffer.from(b).toString('base64');

/** کلیدِ آزمایشیِ **درِ همین اجرا** ساخته می‌شود؛ هیچ کلیدِ خصوصیِ real درِ گیت نیست. */
function demoKey() {
  const kp = generateKeyPairSync('ed25519');
  const spki = new Uint8Array(kp.publicKey.export({ type: 'spki', format: 'der' }));
  const kid = new Uint8Array(createHash('sha256').update(spki).digest()).subarray(0, 8);
  const raw = spki.subarray(spki.length - 32);
  const signBlock = (bytes: ArrayBuffer, comment = 'timestamp=1700000000 file=manifest.json'): string => {
    const u = new Uint8Array(bytes);
    const sig64 = new Uint8Array(nodeSign(null, u, kp.privateKey));
    const globalSig = new Uint8Array(nodeSign(null,
      new Uint8Array([...sig64, ...new TextEncoder().encode(comment)]), kp.privateKey));
    return 'untrusted comment: signature from bors mobile-manifest signing key\n'
      + b64(new Uint8Array([...new TextEncoder().encode(ACCEPTED_SIG_ALG), ...kid, ...sig64])) + '\n'
      + 'trusted comment: ' + comment + '\n'
      + b64(globalSig) + '\n';
  };
  return { pubB64: b64(new Uint8Array([...new TextEncoder().encode(ACCEPTED_SIG_ALG), ...kid, ...raw])),
           keyId: Buffer.from(kid).toString('hex'), signBlock };
}

beforeAll(() => {
  vi.stubGlobal('crypto', webcrypto);
});

describe('پلِ پایتون ⇄ WebCrypto', () => {
  it('الف) امضایِ ساخته‌شده با scripts/sign_mobile_manifest.py درِ کلاینت می‌خواند', async () => {
    const r = await verifyManifestSignature(enc(MANIFEST_TEXT), SIG_TEXT, PUB_B64);
    expect(r.ok, JSON.stringify(r)).toBe(true);
  });

  it('الف۲) key_id درِ هر دو پیاده‌سازی یکی است (SHA-256(DER)[:8])', async () => {
    const raw = new Uint8Array(Buffer.from(PUB_B64, 'base64'));
    const p = parseSigBlock(SIG_TEXT);
    if ('ok' in p && !p.ok) throw new Error('fixtureِ امضا خوانده نشد: ' + p.detail);
    expect((p as { keyId: string }).keyId).toBe(EXPECTED.key_id);
    expect(await keyIdOfRawPublic(raw.subarray(raw.length - 32))).toBe(EXPECTED.key_id);
  });
});

describe('ردِ حالت‌هایِ نامعتبر', () => {
  const key = demoKey();

  it('ب۱) تغییرِ یکِ بایتِ manifest ⇒ signature-invalid', async () => {
    const bytes = enc(MANIFEST_TEXT);
    const u = new Uint8Array(bytes);
    u[Math.floor(u.length / 2)] ^= 0x01;   // یکِ بایت، همان‌جا که امضا رویش است
    const r = await verifyManifestSignature(u.buffer as ArrayBuffer, SIG_TEXT, PUB_B64);
    expect(r.ok).toBe(false);
    expect((r as { reason: string }).reason).toBe('signature-invalid');
  });

  it('ب۲) manifestِ امضاشده با کلیدِ دیگر ⇒ signature-key-mismatch', async () => {
    const other = demoKey();
    const good = await verifyManifestSignature(enc(MANIFEST_TEXT), SIG_TEXT, other.pubB64);
    expect(good.ok).toBe(false);
    expect((good as { reason: string }).reason).toBe('signature-key-mismatch');
  });

  it('ب۳) امضایِ ساخته‌شده با کلیدِ دیگر رویِ همان manifest ⇒ signature-invalid', async () => {
    const r = await verifyManifestSignature(enc(MANIFEST_TEXT), key.signBlock(enc(MANIFEST_TEXT)), PUB_B64);
    expect(r.ok).toBe(false);
    expect((r as { reason: string }).reason).toBe('signature-key-mismatch');
  });

  it('ب۴) امضایِ مفقود ⇒ signature-missing (نه پذیرشِ بی‌آزمون)', async () => {
    for (const empty of ['', '   ', '\n']) {
      const r = await verifyManifestSignature(enc(MANIFEST_TEXT), empty, PUB_B64);
      expect(r.ok).toBe(false);
      expect((r as { reason: string }).reason).toBe('signature-missing');
    }
  });

  it('ب۵) بلوکِ ناقص/بی‌قاعده ⇒ signature-malformed', async () => {
    const cases = [
      'untrusted comment: x\n' + SIG_TEXT.split('\n')[1] + '\ntrusted comment: y\n',
      'untrusted comment: x\nZZZZnot-base64\ntrusted comment: y\nAAAA\n',
      JSON.stringify({ note: 'اشتباهاً JSON به‌جای بلوکِ امضا' }),
    ];
    for (const c of cases) {
      const r = await verifyManifestSignature(enc(MANIFEST_TEXT), c, PUB_B64);
      expect(r.ok, c.slice(0, 30)).toBe(false);
      expect((r as { reason: string }).reason).toBe('signature-malformed');
    }
  });

  it('ب۶) الگوریتمِ `ED` (blake2b پیش‌هش، خروجیِ tauri signer) ⇒ صریحاً رد', async () => {
    const line = SIG_TEXT.split('\n')[1];
    const raw = new Uint8Array(Buffer.from(line, 'base64'));
    const swapped = b64(new Uint8Array([...new TextEncoder().encode('ED'), ...raw.subarray(2)]));
    const tampered = SIG_TEXT.split('\n').map((l, i) => (i === 1 ? swapped : l)).join('\n');
    const r = await verifyManifestSignature(enc(MANIFEST_TEXT), tampered, PUB_B64);
    expect(r.ok).toBe(false);
    expect((r as { reason: string }).reason).toBe('signature-alg-unknown');
  });

  it('ب۷) trusted commentِ تغییریافته ⇒ امضایِ جهانی نمی‌خواند', async () => {
    const lines = SIG_TEXT.split('\n');
    lines[2] = 'trusted comment: timestamp=9999999999 file=other.json';
    const r = await verifyManifestSignature(enc(MANIFEST_TEXT), lines.join('\n'), PUB_B64);
    expect(r.ok).toBe(false);
    expect((r as { reason: string }).reason).toBe('signature-invalid');
  });

  it('ب۸) کلیدِ عمومیِ خراب درِ برنامه ⇒ ردِ امن، بی‌استثنا', async () => {
    for (const k of ['', 'not-base64!!!', b64(new Uint8Array(8))]) {
      const r = await verifyManifestSignature(enc(MANIFEST_TEXT), SIG_TEXT, k);
      expect(r.ok, k).toBe(false);
      expect((r as { reason: string }).reason).toBe('signature-key-mismatch');
    }
  });
});

describe('fail-closed درِ نبودِ کلید', () => {
  it('پ۱) بی‌VITE_MOBILE_MANIFEST_PUBKEY هیچ کلیدی از شبکه گرفته نمی‌شود و داوری «رد» است', () => {
    vi.stubEnv('VITE_MOBILE_MANIFEST_PUBKEY', '');
    expect(bundledManifestPublicKey()).toBe('');
    vi.unstubAllEnvs();
    vi.stubEnv('VITE_MOBILE_MANIFEST_PUBKEY', '   ' + PUB_B64 + '  ');
    expect(bundledManifestPublicKey()).toBe(PUB_B64);   // فاصله‌هایِ build-time آزار نمی‌دهد
    vi.unstubAllEnvs();
  });

  it('پ۲) بی‌subtle (موتورِ کهنه) ⇒ signature-crypto-unavailable، نه «بساز و بیاور»', async () => {
    const real = globalThis.crypto;
    vi.stubGlobal('crypto', {});
    const r = await verifyManifestSignature(enc(MANIFEST_TEXT), SIG_TEXT, PUB_B64);
    expect(r.ok).toBe(false);
    expect((r as { reason: string }).reason).toBe('signature-crypto-unavailable');
    vi.stubGlobal('crypto', real);
  });

  it('پ۳) کلیدِ عمومیِ آزمایشیِ دیگر هم بستهٔ fixture را نمی‌پذیرد (امضا به کلیدش بند است)', async () => {
    const other = demoKey();
    const r = await verifyManifestSignature(enc(MANIFEST_TEXT), SIG_TEXT, other.pubB64);
    expect(r.ok).toBe(false);
  });
});

// امضایِ درستِ کلیدِ آزمایشی — ثابتِ اینکه آزمون‌هایِ بالا از کور بودنِ سنسور
// سبز نشده‌اند: همان کلید با همان بلوک، رویِ manifestِ خودش می‌خواند.
it('کنترلِ مثبتِ کلیدِ آزمایشی (سنسور کور نیست)', async () => {
  const key = demoKey();
  const m = JSON.stringify({ schema_version: 2, hello: 'bors' });
  const r = await verifyManifestSignature(enc(m), key.signBlock(enc(m)), key.pubB64);
  expect(r.ok, JSON.stringify(r)).toBe(true);
  const bad = await verifyManifestSignature(enc(m + ' '), key.signBlock(enc(m)), key.pubB64);
  expect(bad.ok).toBe(false);
  expect((bad as { reason: string }).reason).toBe('signature-invalid');
});

// کلیدِ خصوصیِ ساخته‌شده درِ همین فایل بیرون از تست نمی‌ماند — آزمونِ ساختار:
it('کلیدِ خصوصیِ آزمون درِ مخزن نوشته نمی‌شود', () => {
  expect(() => createPrivateKey('nope')).toThrow();
});
