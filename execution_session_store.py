# -*- coding: utf-8 -*-
"""execution_session_store.py — بازیابیِ نشستِ EasyTrader از Windows Credential Manager.

چرا این فایل هست: توکنِ نشست در `POST /api/execution/session` فقط درِ حافظه
می‌نشست و با restart می‌مرد. مالک خواست همان توکن پس از restart از مخزنِ امنِ
ویندوز بازیابی شود، با بررسیِ انقضا و بدونِ افشای مقدار.

قراردادِ مخزن (سنجش‌شده رویِ همین ماشین، 2026-10-20):
  target : BorsTerminal:EasyTrader:Session
  user   : easy_pkce            (شناسۀ OIDC client، نه شناسۀ حساب)
  blob   : b"v1:utf8:" + <access token>   (UTF-8)
چرا UTF-8: توکنِ مشاهده‌شده ۱۹۵۵ نویسه بود؛ UTF-16 آن ۳۹۱۰ بایت می‌شد و از
سقفِ ۲۵۶۰ بایتیِ CredentialBlob برایِ نوعِ Generic رد می‌شد.

سه قفل:
  ۱) این ماژول هیچ توکنی چاپ/لاگ نمی‌کند و در `repr` نمی‌گذارد؛ `token` فقط
     با دسترسیِ صریح به فیلد و برایِ `set_token`ِ آداپتور خوانده می‌شود.
  ۲) توکنِ بدونِ `exp` یا منقضی هرگز در حافظه نمی‌نشیند (`NO_EXP`/`EXPIRED`).
     امضای JWT بررسی نمی‌شود — این یک دروازۀ بازیابی است، نه احرازِ هویت؛
     داورِ نهایی همیشه پاسخِ خودِ کارگزاری است.
  ۳) هیچ نوشتنی در مخزن انجام نمی‌شود؛ فقط `CredReadW`. ساختِ توکن وظیفۀ
     مسیرِ ورودِ مالک است.

چیدمانِ `CredReadW` رویِ همین ویندوز (10.0.26300/x64) با دو رکوردِ ساختگی و یک
رکوردِ واقعی اندازه‌گیری شد؛ اگر روزی ویندوز آن را عوض کند، `MALFORMED` می‌دهیم،
نه دادهٔ غلط.
"""
from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes as wt
import datetime
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

SESSION_TARGET = "BorsTerminal:EasyTrader:Session"
SESSION_PREFIX = b"v1:utf8:"
CRED_TYPE_GENERIC = 1
_ERROR_NOT_FOUND = 1168

#: اندازه‌ای که برایِ پارسِ امن از بافرِ رکورد می‌خوانیم.
_RECORD_BYTES = 96
_OFF_BLOBSIZE, _OFF_BLOB = 32, 40

BlobReader = Callable[[str], "tuple[Optional[bytes], int]"]


@dataclass(frozen=True)
class SessionTokenRead:
    """نتیجۀ خواندن. `token` درِ `repr` نیست و فقط برایِ `set_token` است."""
    ok: bool
    code: str                                   # OK | MISSING | EXPIRED | NO_EXP | MALFORMED | UNSUPPORTED | DENIED
    token: str = field(default="", repr=False, compare=False)
    exp: Optional[int] = None
    exp_iso: Optional[str] = None
    blob_bytes: int = 0
    target: str = SESSION_TARGET
    winerror: int = 0

    @property
    def present(self) -> bool:
        """اعتبارنامه درِ مخزن هست (حتی اگر منقضی باشد)."""
        return self.code in ("OK", "EXPIRED")

    def __repr__(self) -> str:
        return ("SessionTokenRead(ok=%s, code=%r, exp=%s, exp_iso=%r, "
                "blob_bytes=%d, target=%r)"
                % (self.ok, self.code, self.exp, self.exp_iso,
                   self.blob_bytes, self.target))

    def __str__(self) -> str:
        return repr(self)


def _is_windows() -> bool:
    import os
    return os.name == "nt"


def _u32(buf: bytes, off: int) -> int:
    return int.from_bytes(buf[off:off + 4], "little")


def _ptr(buf: bytes, off: int) -> int:
    return int.from_bytes(buf[off:off + 8], "little")


def _windows_reader(target: str) -> tuple[Optional[bytes], int]:
    """فقط‌خواندنی از Credential Manager. (blob, winerror)؛ نبود ⇒ (None, 1168)."""
    if not _is_windows():
        return None, 0
    try:
        adv = ctypes.WinDLL("advapi32", use_last_error=True)
        read = adv.CredReadW
        read.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD,
                         ctypes.POINTER(ctypes.c_void_p)]
        read.restype = ctypes.c_int
        free = adv.CredFree
        free.argtypes = [ctypes.c_void_p]
        free.restype = None
    except Exception:
        return None, 0
    holder = ctypes.c_void_p(0)
    ctypes.set_last_error(0)
    try:
        ok = read(target, CRED_TYPE_GENERIC, 0, ctypes.byref(holder))
    except Exception:
        return None, 0
    if not ok:
        return None, ctypes.get_last_error()
    if not holder.value:
        return None, 0
    try:
        base = ctypes.string_at(holder, _RECORD_BYTES)
        size = _u32(base, _OFF_BLOBSIZE)
        addr = _ptr(base, _OFF_BLOB)
        if size <= 0 or not addr:
            return None, 0
        return ctypes.string_at(ctypes.c_void_p(addr), size), 0
    except Exception:
        return None, 0
    finally:
        try:
            free(holder)
        except Exception:
            pass


def _jwt_exp(token: str) -> tuple[Optional[int], Optional[str]]:
    """(exp, error_code) از payloadِ JWT؛ امضا بررسی نمی‌شود."""
    parts = (token or "").split(".")
    if len(parts) != 3:
        return None, "MALFORMED"
    pad = "=" * (-len(parts[1]) % 4)
    try:
        raw = base64.urlsafe_b64decode(parts[1] + pad)
        claims = json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        return None, "MALFORMED"
    if not isinstance(claims, dict):
        return None, "MALFORMED"
    exp = claims.get("exp")
    if isinstance(exp, bool) or not isinstance(exp, (int, float)):
        return None, "NO_EXP"
    return int(exp), None


def _iso(epoch_s: Optional[int]) -> Optional[str]:
    if epoch_s is None:
        return None
    try:
        return datetime.datetime.fromtimestamp(
            int(epoch_s), tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return None


def read_session_token(*, target: str = SESSION_TARGET,
                       now: Optional[float] = None,
                       reader: Optional[BlobReader] = None) -> SessionTokenRead:
    """توکن را می‌خواند و **پیش از** برگرداندن، انقضا را بررسی می‌کند.

    `reader` فقط برایِ آزمون تزریق می‌شود؛ پیش‌فرض `CredReadW` است.
    """
    read = reader or _windows_reader
    try:
        raw, err = read(target)
    except Exception:
        return SessionTokenRead(False, "UNSUPPORTED", target=target)
    if raw is None:
        code = "MISSING" if err == _ERROR_NOT_FOUND else (
            "UNSUPPORTED" if not _is_windows() else "DENIED")
        return SessionTokenRead(False, code, target=target, winerror=err)
    if not raw.startswith(SESSION_PREFIX):
        return SessionTokenRead(False, "MALFORMED", target=target,
                                blob_bytes=len(raw))
    try:
        token = raw[len(SESSION_PREFIX):].decode("utf-8").strip()
    except UnicodeDecodeError:
        return SessionTokenRead(False, "MALFORMED", target=target,
                                blob_bytes=len(raw))
    if not token:
        return SessionTokenRead(False, "MALFORMED", target=target,
                                blob_bytes=len(raw))
    exp, err_code = _jwt_exp(token)
    if err_code is not None:
        return SessionTokenRead(False, err_code, target=target,
                                blob_bytes=len(raw))
    exp_iso = _iso(exp)
    current = time.time() if now is None else float(now)
    if exp is None or int(exp) <= int(current):
        return SessionTokenRead(False, "EXPIRED", exp=exp, exp_iso=exp_iso,
                                target=target, blob_bytes=len(raw))
    return SessionTokenRead(True, "OK", token=token, exp=exp, exp_iso=exp_iso,
                            target=target, blob_bytes=len(raw))


def public_status(result: Optional[SessionTokenRead] = None) -> dict[str, Any]:
    """آنچه رابط/`/status` می‌بیند: هست یا نه، کد، انقضا. هیچ توکنی اینجا نیست."""
    r = result or read_session_token()
    hint = {
        "OK": "",
        "MISSING": "توکنِ نشست در Windows Credential Manager نیست — ورودِ مالک لازم است",
        "EXPIRED": "توکنِ ذخیره‌شده منقضی شده — ورود/استخراجِ تازه لازم است",
        "NO_EXP": "توکنِ ذخیره‌شده `exp` قابلِ‌خواندن ندارد — بارگذاری نشد",
        "MALFORMED": "اعتبارنامۀ ذخیره‌شده ساختارِ موردانتظار را ندارد",
        "UNSUPPORTED": "مخزنِ اعتبارنامۀ ویندوز رویِ این سامانه‌عامل در دسترس نیست",
        "DENIED": "دسترسی به مخزنِ اعتبارنامه رد شد",
    }.get(r.code, "")
    return {
        "provider": "windows-credential-manager",
        "target": r.target,
        "present": r.present,
        "code": r.code,
        "exp": r.exp,
        "exp_iso": r.exp_iso,
        "blob_bytes": r.blob_bytes,
        "hint": hint,
    }


def restore_session(adapter: Any, *, only_if_missing: bool = True,
                    now: Optional[float] = None,
                    reader: Optional[BlobReader] = None) -> dict[str, Any]:
    """توکنِ معتبر را درِ حافظۀ آداپتور می‌گذارد. خروجی هرگز توکن ندارد.

    `only_if_missing=True` (پیش‌فرض): اگر آداپتور از قبل توکن دارد، ذخیره‌شده
    جایگزینش نمی‌شود؛ نشستِ تازه‌تر همیشه بر کهنه مقدم است.
    """
    out: dict[str, Any] = {
        "attempted": False, "loaded": False,
        "source": "windows-credential-manager",
        "code": "NOT_ATTEMPTED", "present": False,
        "exp": None, "exp_iso": None,
    }
    setter = getattr(adapter, "set_token", None)
    if not callable(setter):
        out["code"] = "UNSUPPORTED"
        return out
    if only_if_missing:
        has = getattr(adapter, "has_token", None)
        try:
            if callable(has) and has():
                out["code"] = "ALREADY_PRESENT"
                return out
        except Exception:
            pass
    r = read_session_token(now=now, reader=reader)
    out.update({"attempted": True, "code": r.code, "present": r.present,
                "exp": r.exp, "exp_iso": r.exp_iso})
    if not r.ok:
        return out
    try:
        setter(r.token)
    except Exception:
        out.update({"code": "SET_FAILED", "loaded": False})
        return out
    out["loaded"] = True
    return out


if __name__ == "__main__":
    print(json.dumps(public_status(), ensure_ascii=False, indent=2))
