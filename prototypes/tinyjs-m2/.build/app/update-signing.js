// Exact-byte Ed25519 update envelopes, shared by publisher and runtime.
// Only the baked key is authoritative; no key is taken from the envelope.
//
// The hosted manifest is the plain one plus a "signed" block holding the
// envelope: apps without a key (including every install from before signing
// existed) read the plain fields as always; apps with a key ignore them and
// trust only the verified payload. So one url serves both, and turning
// signing on needs no migration release. --signed-only drops the plain
// fields, leaving keyless apps with no update to see.
const enc = new TextEncoder();
const PREFIX = 'tinyjs-update-v1\n';

export function base64(bytes) {
  return btoa(Array.from(new Uint8Array(bytes), b => String.fromCharCode(b)).join(''));
}

export function unbase64(value, length, what) {
  if (typeof value !== 'string' || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value))
    throw new Error('invalid ' + what + ' base64');
  const bytes = Uint8Array.from(atob(value), c => c.charCodeAt(0));
  if ((length !== null && bytes.length !== length) || base64(bytes) !== value)
    throw new Error('invalid ' + what + ' encoding or length');
  return bytes;
}

// The baked key turns signing on only as a non-empty string, or a non-empty
// list of them (a backup key, or the next key during a rotation); anything
// else (absent, null, "", [], a number) means an unsigned app. A malformed
// entry in a list is not skipped: verification then fails closed.
export function pinnedKeys(value) {
  if (typeof value === 'string') return value !== '' ? [value] : null;
  return Array.isArray(value) && value.length ? [...value] : null;
}

function manifestObject(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value) || typeof value.version !== 'string')
    throw new Error('invalid signed update manifest');
  return value;
}

// publicKey: one base64 key or a list; a signature from any of them passes.
// Returns the verified payload; nothing outside "signed" is read.
export async function verifyManifest(doc, publicKey) {
  // Snapshot attacker-controlled values (and the key list) before the first
  // asynchronous call.
  const envelope = doc?.signed;
  const payload = envelope?.payload;
  const signature = envelope?.signature;
  const pins = Array.isArray(publicKey) ? [...publicKey] : [publicKey];
  if (!envelope || typeof envelope !== 'object' ||
      envelope.format !== 'tinyjs-update-v1' || envelope.algorithm !== 'Ed25519' ||
      typeof payload !== 'string' || Object.keys(envelope).sort().join(',') !== 'algorithm,format,payload,signature')
    throw new Error('signed Ed25519 update manifest required');
  const sig = unbase64(signature, 64, 'update signature');
  if (!pins.length) throw new Error('invalid update publicKey: empty list');
  // Decode every pin first so one bad entry fails closed, even when another
  // key would have matched.
  const raws = pins.map((pin) => unbase64(pin, 32, 'update publicKey'));
  const bytes = enc.encode(PREFIX + payload);
  let ok = false;
  for (const raw of raws) {
    const key = await crypto.subtle.importKey('raw', raw, 'Ed25519', false, ['verify']);
    if (await crypto.subtle.verify('Ed25519', key, sig, bytes)) { ok = true; break; }
  }
  if (!ok) throw new Error('update manifest signature verification failed');
  // Parse only after authentication, before any platform overlays.
  return manifestObject(JSON.parse(payload));
}

// manifest: the plain manifest (any old "signed" block is dropped, never
// signed over). Returns the hosted document.
export async function signManifest(manifest, privateKey, publicKey, { signedOnly = false } = {}) {
  const { signed: _, ...plain } = manifestObject(manifest);
  const payload = JSON.stringify(manifestObject(plain));
  const signature = base64(await crypto.subtle.sign('Ed25519', privateKey, enc.encode(PREFIX + payload)));
  const signed = { format: 'tinyjs-update-v1', algorithm: 'Ed25519', payload, signature };
  const doc = signedOnly ? { signed } : { ...JSON.parse(payload), signed };
  // A missing/mismatched configured key must fail before publishing anything.
  await verifyManifest(doc, publicKey);
  return doc;
}
