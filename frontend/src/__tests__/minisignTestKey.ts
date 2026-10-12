// __tests__/minisignTestKey.ts — کلیدِ آزمایشیِ **درِ زمانِ اجرا** برایِ آزمون‌ها
//
// چرا فایلِ جدا (نه *.spec): آزمون‌هایِ `mobile-snapshot-integrity` و
// `mobile-manifest-signature` هر دو بهِ یکِ بلوکِ amضا نیاز دارند. کلید هیچ‌گاه
// درِ گیت نوشته نمی‌شود (فقط کلیدِ عمومیِ fixtureِ پایتون درِ fixtures/ هست) و
// هرگز به‌عنوانِ کلیدِ انتشار معرفی نمی‌شود.
import { createHash, generateKeyPairSync, sign as nodeSign } from 'node:crypto';

const b64 = (b: Uint8Array): string => Buffer.from(b).toString('base64');
export const utf8 = (s: string): Uint8Array => new TextEncoder().encode(s);
export const buf = (u: Uint8Array): ArrayBuffer => u.slice().buffer as ArrayBuffer;

export type TestSigner = {
  /** base64ِ خطِ دومِ کلیدِ عمومیِ minisign (alg|key_id|public32) — همان چیزی که
   *  درِ بیلد به‌عنوان VITE_MOBILE_MANIFEST_PUBKEY می‌نشیند. */
  pubB64: string;
  keyId: string;
  /** بلوکِ clear-signature با الگوریتم «Ed» رویِ همان بایت‌ها. */
  signBlock: (bytes: ArrayBuffer, comment?: string) => string;
};

export function makeTestSigner(): TestSigner {
  const kp = generateKeyPairSync('ed25519');
  const spki = new Uint8Array(kp.publicKey.export({ type: 'spki', format: 'der' }));
  const kid = new Uint8Array(createHash('sha256').update(spki).digest()).subarray(0, 8);
  const raw = spki.subarray(spki.length - 32);
  const alg = utf8('Ed');
  return {
    pubB64: b64(new Uint8Array([...alg, ...kid, ...raw])),
    keyId: Buffer.from(kid).toString('hex'),
    signBlock: (bytes: ArrayBuffer, comment = 'timestamp=1760000000 file=mobile_snapshot.db.meta.json') => {
      const sig64 = new Uint8Array(nodeSign(null, new Uint8Array(bytes), kp.privateKey));
      const globalSig = new Uint8Array(nodeSign(null,
        new Uint8Array([...sig64, ...utf8(comment)]), kp.privateKey));
      return 'untrusted comment: signature from bors mobile-manifest signing key\n'
        + b64(new Uint8Array([...alg, ...kid, ...sig64])) + '\n'
        + 'trusted comment: ' + comment + '\n'
        + b64(globalSig) + '\n';
    },
  };
}
