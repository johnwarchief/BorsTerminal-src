# -*- coding: utf-8 -*-
"""bors_minisign.py -- dependency-free minisign signature verification.

The shipped app is a PyInstaller-frozen Python build, so update signatures
must be verified without adding a crypto dependency to the bundle. Ed25519
curve arithmetic is implemented here (~130 lines, verification only);
SHA-512 and BLAKE2b-512 come from the stdlib (hashlib).

Format emitted by `tauri signer sign` (minisign-compatible):

    untrusted comment: <arbitrary text>
    <base64 signature>          -> 2-byte alg | 8-byte key id | 64-byte sig
    trusted comment: <arbitrary text>
    <base64 global signature>   -> 64-byte raw Ed25519 over the trusted line

Algorithm bytes:
    b"Ed" -> Ed25519 over the raw message
    b"ED" -> Ed25519 over BLAKE2b-512(message)   <-- what tauri signer emits

Public key format:

    untrusted comment: minisign public key: <KEYID>
    <base64 public key>         -> 2-byte alg | 8-byte key id | 32-byte point
"""
import base64
import hashlib

# ---------------------------------------------------------------------------
# Ed25519 (RFC 8032) -- pure-Python verification only.
# ---------------------------------------------------------------------------
_P = 2 ** 255 - 19                                      # field prime
_Q = 2 ** 252 + 27742317777372353535851937790883648493  # subgroup order
_D = (-121665 * pow(121666, _P - 2, _P)) % _P           # d = -121665 / 121666
_I = pow(2, (_P - 1) // 4, _P)                          # sqrt(-1) mod p


def _inv(x):
    return pow(x, _P - 2, _P)


def _xrecover(y):
    """Recover the even square root of the curve equation for a given y."""
    xx = ((y * y - 1) * _inv(_D * y * y + 1)) % _P
    x = pow(xx, (_P + 3) // 8, _P) % _P
    if (x * x - xx) % _P != 0:
        x = (x * _I) % _P
    if x % 2 != 0:
        x = _P - x
    return x


_BY = (4 * pow(5, _P - 2, _P)) % _P                     # B_y = 4/5 mod p
_BASE = (_xrecover(_BY), _BY)                           # even-x base point


def _isoncurve(point):
    x, y = point
    xx = (x * x) % _P
    yy = (y * y) % _P
    return (yy - xx - 1 - _D * xx * yy) % _P == 0


def _edwards(p1, p2):
    """Twisted Edwards curve point addition (a = -1, as required by Ed25519)."""
    x1, y1 = p1
    x2, y2 = p2
    dxx = (_D * x1 * x2 * y1 * y2) % _P
    x3 = ((x1 * y2 + x2 * y1) * _inv(1 + dxx)) % _P
    y3 = ((y1 * y2 + x1 * x2) * _inv(1 - dxx)) % _P
    return (x3, y3)


def _scalarmult(point, scalar):
    result = (0, 1)                                     # neutral element
    addend = point
    while scalar > 0:
        if scalar & 1:
            result = _edwards(result, addend)
        addend = _edwards(addend, addend)
        scalar >>= 1
    return result


def _decodepoint(enc):
    """Decode a 32-byte encoding: little-endian y, x-sign in the top bit."""
    y = int.from_bytes(enc, "little") & ((1 << 255) - 1)
    x = _xrecover(y)
    if (x & 1) != ((enc[31] >> 7) & 1):
        x = _P - x
    point = (x, y)
    if not _isoncurve(point):
        raise ValueError("encoded point is not on the ed25519 curve")
    return point


def _ed25519_verify(public32, message, sig64):
    """Standard EdDSA (SHA-512 challenge). Returns True/False, never raises."""
    if len(public32) != 32 or len(sig64) != 64:
        return False
    r_enc = sig64[:32]
    s = int.from_bytes(sig64[32:], "little")
    if s >= _Q:
        return False
    try:
        a_point = _decodepoint(public32)
        r_point = _decodepoint(r_enc)
    except ValueError:
        return False
    h = int.from_bytes(
        hashlib.sha512(r_enc + public32 + message).digest(), "little"
    ) % _Q
    # RFC 8032: S*B == R + H(R||A||M)*A   (S = r + h*sk, so S*B = R + h*A)
    rhs = _edwards(r_point, _scalarmult(a_point, h))
    return _scalarmult(_BASE, s) == rhs

# ---------------------------------------------------------------------------
# minisign parsing + verification
# ---------------------------------------------------------------------------
def _b64(text):
    """base64-decode a minisign line, tolerating its 76-char wrapping."""
    return base64.b64decode("".join(text.split()), validate=True)


def parse_minisign_pubkey(blob):
    """blob: minisign pubkey text (comment + base64 line) or base64 of that text.

    Returns (key_id: bytes, public_key: 32 bytes).
    """
    text = blob.strip()
    if not text.startswith("untrusted comment:"):
        # maybe base64-wrapped (the tauri.conf.json / .key.pub form)
        try:
            decoded = base64.b64decode("".join(text.split())).decode("utf-8", "replace").strip()
        except Exception:
            decoded = ""
        if decoded.startswith("untrusted comment:"):
            text = decoded
    lines = [ln for ln in text.splitlines() if ln.strip()]
    key_line = lines[-1] if len(lines) > 1 else text
    raw = _b64(key_line)
    if len(raw) != 42:
        raise ValueError(
            "minisign public key must decode to 42 bytes, got %d" % len(raw)
        )
    alg, key_id, public = raw[:2], raw[2:10], raw[10:42]
    if alg not in (b"Ed", b"ED"):
        raise ValueError("unsupported public key algorithm: %r" % alg)
    return key_id, public


def parse_minisign_signature(blob):
    """blob: minisign signature block text (4 lines) or base64 of that text.

    Returns dict(alg, key_id, sig64, trusted_comment, global_sig64).
    """
    text = blob.strip()
    if not text.startswith("untrusted comment:"):
        # stored base64-wrapped (e.g. the "signature" field of latest.json)
        text = base64.b64decode(text).decode("utf-8", "replace").strip()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 4:
        raise ValueError("incomplete minisign signature block (%d lines)" % len(lines))
    sig_line, trusted_line, global_line = lines[1], lines[2], lines[3]
    if not trusted_line.startswith("trusted comment:"):
        raise ValueError("malformed trusted comment line")

    raw = _b64(sig_line)
    if len(raw) != 74:
        raise ValueError(
            "minisign signature must decode to 74 bytes, got %d" % len(raw)
        )
    alg, key_id, sig64 = raw[:2], raw[2:10], raw[10:74]
    if alg not in (b"Ed", b"ED"):
        raise ValueError("unsupported signature algorithm: %r" % alg)
    global_sig = _b64(global_line)
    if len(global_sig) != 64:
        raise ValueError("global signature must be 64 bytes, got %d" % len(global_sig))
    return {
        "alg": alg,
        "key_id": key_id,
        "trusted_comment": trusted_line[len("trusted comment:"):].strip(),
        "sig64": sig64,
        "global_sig64": global_sig,
    }


def verify_minisign(data, signature_block, pubkey_block, check_trusted_comment=True):
    """Verify a minisign signature over `data` (raw bytes).

    signature_block / pubkey_block accept either the raw minisign text or its
    base64-wrapped form (as used in tauri.conf.json / latest.json).

    Returns True on success; raises ValueError with a precise reason otherwise.
    """
    key_id, public32 = parse_minisign_pubkey(pubkey_block)
    sig = parse_minisign_signature(signature_block)
    if sig["key_id"] != key_id:
        raise ValueError("signature key id does not match the bundled public key")
    if sig["alg"] == b"ED":
        digest = hashlib.blake2b(data, digest_size=64).digest()
    else:
        digest = data
    if not _ed25519_verify(public32, digest, sig["sig64"]):
        raise ValueError("signature verification failed (bad signature or tampered file)")
    if check_trusted_comment:
        # minisign-rs: global_sig = ed25519(sig64 || trusted_comment_text)
        # (no "trusted comment: " prefix, no trailing newline)
        msg = sig["sig64"] + sig["trusted_comment"].encode("utf-8")
        if not _ed25519_verify(public32, msg, sig["global_sig64"]):
            raise ValueError("trusted comment signature verification failed")
    return True
