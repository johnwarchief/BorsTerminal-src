// shared/api/local/manifestSignature.ts — اصالتِ ناشرِ manifest (مرحلۀ ۲ دور ۴ اندروید)
//
// چرا لازم شد: `verifyBytes()` درِ snapshotPackage.ts فقط **تمامیت** را می‌سنجد —
// «این بایت‌ها همان چیزی است که manifest گفته». اگر کسی مسیرِ دانلود را بگیرد،
// می‌تواند manifest را هم با بستهٔ خودش بسازد و digestِ درونش را هم درستِ همان
// بسته بگذارد. پس یکِ لایۀ جدا لازم است: امضایِ دیجیتال رویِ بایت‌هایِ **خودِ
// فایلِ manifest**، بررسی‌شده **پیش از** اعتماد به هر فیلدی.
//
// قرارداد (یکپارچه، دو سرِ آن درِ همین مخزن):
//   • فایلِ جدا: `<meta>.sig` — امضا **بیرون** از manifest، پس دورِ باطلی نیست.
//   • بلوکِ clear-signatureِ سازگارِ minisign، الگوریتم `Ed` = Ed25519 رویِ پیامِ خام.
//     `ED` (blake2b-512 پیش‌هش، خروجیِ tauri signer) اینجا **ممنوع** است:
//     WebCrypto blake2b ندارد و بررسیِ بی‌موفق، بسته را می‌کُشت. سازندۀ Python
//     (scripts/sign_mobile_manifest.py) هم همین `Ed` را می‌نویسد.
//   • کلید عمومی: ثابتِ build-time (VITE_MOBILE_MANIFEST_PUBKEY) — هرگز از همان
//     مسیرِ نامطمئنی که بسته می‌آید خوانده نمی‌شود. نبودش ⇒ ردِ همه‌چیز
//     (fail-closed)، نه پذیرشِ بی‌آزمون.
//   • key_id = هشت بایتِ اولِ SHA-256(DERِ public). این را خودِ قراردادِ ما تعریف
//     می‌کند (canonical minisign نیست) و هر دو طرف از همان تعریف می‌خوانند.
//   • خطِ سومِ بلوک (trusted comment) هم امضایِ جهانی دارد رویِ
//     `sig64 || trusted-comment-text` — همان کاری که bors_minisign.py می‌کند.

/** الگوریتمِ پذیرفته‌شده درِ این قرارداد (نه `ED` پیش‌هش‌شده). */
export const ACCEPTED_SIG_ALG = "Ed";
/** نامِ الگوریتم درِ WebCrypto — رشته، تا با lib.domِ موجودِ پروژه بسازد. */
const ED25519 = "Ed25519";

export type SigReject =
  | 'signature-missing' | 'signature-malformed' | 'signature-alg-unknown'
  | 'signature-key-mismatch' | 'signature-invalid'
  | 'signature-crypto-unavailable';

export type SigCheck = { ok: true } | { ok: false; reason: SigReject; detail: string };

const bad = (reason: SigReject, detail: string): SigCheck => ({ ok: false, reason, detail });

const b64ToBytes = (line: string): Uint8Array => {
  const bin = atob(line.replace(/\s+/g, ""));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
};

const hex = (b: Uint8Array): string =>
  [...b].map((x) => x.toString(16).padStart(2, "0")).join("");

/** SHA-256(DER public)[:8] — همان تعریفِ key_id درِ scripts/sign_mobile_manifest.py */
export async function keyIdOfRawPublic(raw32: Uint8Array): Promise<string> {
  const spki = new Uint8Array(12 + raw32.length);
  spki.set([0x30, 0x2a, 0x30, 0x05, 0x06, 0x03, 0x2b, 0x65, 0x70, 0x03, 0x21, 0x00], 0);
  spki.set(raw32, 12);
  const d = await globalThis.crypto.subtle.digest("SHA-256", spki.slice().buffer as ArrayBuffer);
  return hex(new Uint8Array(d)).slice(0, 16);
}

export type ParsedSig = {
  alg: string; keyId: string; sig64: Uint8Array;
  trustedComment: string; globalSig64: Uint8Array;
};

/** بلوکِ چهارخطیِ clear-signature (یا base64ِ همان بلوک، همان قالبِ latest.json). */
export function parseSigBlock(text: string): ParsedSig | SigCheck {
  let t = String(text || "").trim();
  if (t && !t.startsWith("untrusted comment:")) {
    try { t = atob(t.replace(/\s+/g, "")).replace(/^﻿/, ""); }
    catch { /* ممکن است واقعاً base64 نباشد؛ پایین رد می‌شود */ }
  }
  const lines = t.split(/\r?\n/).filter((l) => l.length > 0);
  if (lines.length < 4) return bad('signature-malformed', `بلوکِ امضا ${lines.length} خط است، ۴ لازم است`);
  if (!lines[2].startsWith("trusted comment:")) {
    return bad('signature-malformed', 'خطِ سوم trusted comment نیست');
  }
  let raw: Uint8Array;
  try { raw = b64ToBytes(lines[1]); }
  catch { return bad('signature-malformed', 'خطِ امضا base64 نبود'); }
  if (raw.length !== 74) {
    return bad('signature-malformed', `امضا ${raw.length} بایت است، ۷۴ لازم است`);
  }
  let global: Uint8Array;
  try { global = b64ToBytes(lines[3]); }
  catch { return bad('signature-malformed', 'خطِ امضایِ جهانی base64 نبود'); }
  if (global.length !== 64) {
    return bad('signature-malformed', `امضایِ جهانی ${global.length} بایت است، ۶۴ لازم است`);
  }
  const alg = String.fromCharCode(raw[0], raw[1]);
  return {
    alg,
    keyId: hex(raw.subarray(2, 10)),
    sig64: raw.subarray(10, 74),
    trustedComment: lines[2].slice("trusted comment:".length).trim(),
    globalSig64: global,
  };
}

/**
 * بررسیِ امضایِ manifest. `pubkeyB64` = base64ِ همان خطِ دومِ فایلِ کلیدِ عمومیِ
 * minisign (alg|key_id|public32) یا base64ِ خودِ ۳۲ بایتِ خام.
 *
 * ترتیبِ داوری عمداً «اولِ همه‌چیز» است: اگر این رد کند، هیچ فیلدی از manifest
 * خوانده نمی‌شود.
 */
export async function verifyManifestSignature(manifestBytes: ArrayBuffer, sigText: string,
                                              pubkeyB64: string): Promise<SigCheck> {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) return bad('signature-crypto-unavailable', 'crypto.subtle در این موتور نیست');
  if (!sigText || !sigText.trim()) return bad('signature-missing', 'فایلِ امضا (.sig) نبود');
  const p = parseSigBlock(sigText);
  if ('ok' in p && !p.ok) return p;
  const sig = p as ParsedSig;
  if (sig.alg !== ACCEPTED_SIG_ALG) {
    return bad('signature-alg-unknown',
      `الگوریتمِ امضا «${sig.alg}» است؛ این کلاینت فقط «${ACCEPTED_SIG_ALG}» (Ed25519 رویِ پیامِ خام) را بررسی می‌کند`);
  }
  let pub: Uint8Array;
  try {
    const dec = b64ToBytes(pubkeyB64);
    pub = dec.length === 42 ? dec.subarray(10, 42) : dec;
  } catch {
    return bad('signature-key-mismatch', 'کلیدِ عمومیِ همراهِ برنامه base64 نبود');
  }
  if (pub.length !== 32) {
    return bad('signature-key-mismatch', `کلیدِ عمومی ${pub.length} بایت است، ۳۲ لازم است`);
  }
  const wantKid = await keyIdOfRawPublic(pub);
  if (wantKid !== sig.keyId) {
    return bad('signature-key-mismatch', `key_id نخواند: ${sig.keyId} در برابرِ ${wantKid}`);
  }
  let key: CryptoKey;
  try {
    key = await subtle.importKey("raw", pub.slice().buffer as ArrayBuffer, ED25519, false, ["verify"]);
  } catch (e) {
    return bad('signature-crypto-unavailable',
      `این موتور Ed25519 را نمی‌شناسد: ${e instanceof Error ? e.message : String(e)}`);
  }
  let mainOk = false, globalOk = false;
  try {
    mainOk = await subtle.verify(ED25519, key, sig.sig64.slice().buffer as ArrayBuffer,
      manifestBytes.slice(0, manifestBytes.byteLength));
  } catch (e) {
    return bad('signature-invalid', `بررسیِ امضایِ اصلی خطا داد: ${e instanceof Error ? e.message : String(e)}`);
  }
  if (!mainOk) return bad('signature-invalid', 'امضا با این بایت‌هایِ manifest نمی‌خواند');
  const commentBytes = new TextEncoder().encode(sig.trustedComment);
  const gbuf = new Uint8Array(sig.sig64.length + commentBytes.length);
  gbuf.set(sig.sig64, 0);
  gbuf.set(commentBytes, sig.sig64.length);
  try {
    globalOk = await subtle.verify(ED25519, key, sig.globalSig64.slice().buffer as ArrayBuffer,
      gbuf.buffer as ArrayBuffer);
  } catch {
    globalOk = false;
  }
  if (!globalOk) return bad('signature-invalid', 'امضایِ جهانیِ trusted comment نمی‌خواند');
  return { ok: true };
}

/** خواندنِ کلیدِ عمومیِ build-time. بی‌کلید ⇒ هیچ بسته‌ای فعال نمی‌شود (fail-closed). */
export function bundledManifestPublicKey(): string {
  const env = import.meta.env as Record<string, string | undefined>;
  return (env.VITE_MOBILE_MANIFEST_PUBKEY ?? "").trim();
}
