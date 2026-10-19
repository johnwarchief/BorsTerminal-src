#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""execution_credentials.py — خواندنِ اعتبارنامۀ EasyTrader از Windows Credential Manager.

چرا این فایل هست: مأموریتِ مالک (2026-10-19) می‌گوید رمز *نباید* درِ چت،
ترمینالِ قابلِ ثبت، فایلِ تنظیمات یا Git نوشته شود، و باید از مخزنِ امنِ خودِ
ویندوز خوانده شود. پیش ازِ این، مسیرِ ورودِ برنامه فقط «پنجرۀ مرورگرِ کاربر» بود
(`execution_connect.py`) و برنامه هیچ‌جا نمی‌توانست بگوید «اعتبارنامه رویِ این
ماشین هست یا نه».

چه چیزی *نمی‌کند*: هیچ رمز را لاگ نمی‌کند، درِ `repr` نمی‌گذارد، درِ پاسخِ API
نمی‌فرستد، و هرگز چیزی به مخزن نمی‌نویسد یا پاک نمی‌کند — خواندنِ صرف.

چیدمانِ ساختار (این بخش ازِ حدس نیست؛ سه بار اندازه‌گیری شد):
  `CredReadW` رویِ این ویندوز (10.0.26300/x64) رکوردی برمی‌گرداند که میدان‌هایش
  باِ ترتیبِ مستندِ `CREDENTIALW` *جابه‌جا*ست. این را با دو رکوردِ ساختگیِ خودی
  (cmdkey باِ مقادیرِ SENTINEL/probe-user) و یکِ رکوردِ واقعی سنجیدم:

      +4  Type                 = 1 (GENERIC)
      +8  TargetName*          → رشته‌ای که باِ targetِ خواسته‌شده برابر است
      +16 Comment*             (ممکن است NULL باشد)
      +24 LastWritten (FILETIME)
      +32 CredentialBlobSize   (36 بایت برایِ «SENTINEL-DUMMY-123» = ۱۸ کاراکتر UTF-16)
      +40 CredentialBlob*      (رمز؛ هرگز چاپ نمی‌شود)
      +48 Persist | +52 AttributeCount | +56 Attributes*
      +72 UserName*
      +80 AuthDataLength

  باِ ترتیبِ مستند، `CredentialBlobSize` صفر و `Persist` ۳۶ درمی‌آمد و خواندنِ
  `TargetName` کرش می‌کرد — یعنی حدس‌زدنِ همان ترتیب، کد را می‌شکست. اگر روزی
  ویندوز این چیدمان را عوض کند، `_parse` همان اول می‌شکند و `MALFORMED` می‌دهد،
  نه دادهٔ غلط.

  **نکتۀ ایمنیِ ثبت‌شده:** درِ همان بررسیِ چیدمان، یکِ پیش‌نمایشِ ۴۰ کاراکتری از
  کنارِ نشانهٔ blob چاپ شد که می‌توانست محتوایِ رمزِ کاربر باشد. آن رخداد درِ
  گزارشِ مأموریت ثبت شد و پس ازِ آن هیچ بایتی ازِ blob چاپ نمی‌شود — این فایل هم
  هرگز محتوا را بیرون نمی‌دهد، فقط طول و صحتِ رمزگشایی.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import datetime
from dataclasses import dataclass, field
from typing import Any, Optional

#: همان نشانیِ مشخصی که مالک درِ Windows Credential Manager ساخته است.
EASYTRADER_TARGET = "BorsTerminal:EasyTrader"
CRED_TYPE_GENERIC = 1
_ERROR_NOT_FOUND = 1168          # ERROR_NOT_FOUND: «چنین اعتبارنامه‌ای نیست»
_RECORD_BYTES = 96               # اندازه‌ای که برایِ پارسِ امن می‌خوانیم

# آفست‌هایِ اثبات‌شده (بالا ببینید)
_OFF_TYPE, _OFF_TARGET, _OFF_COMMENT = 4, 8, 16
_OFF_LASTWRITEN, _OFF_BLOBSIZE, _OFF_BLOB = 24, 32, 40
_OFF_PERSIST, _OFF_ATTRCOUNT, _OFF_ATTRS = 48, 52, 56
_OFF_USERNAME, _OFF_AUTHLEN = 72, 80


@dataclass(frozen=True)
class CredentialRead:
    """نتیجۀ خواندن. `password` تنها راهِ دسترسی به رمز است و درِ `repr` نیست."""
    ok: bool
    code: str                                   # OK | MISSING | UNSUPPORTED | MALFORMED | DENIED
    username: str = ""
    password: str = field(default="", repr=False, compare=False)
    target: str = ""
    persist: Optional[int] = None
    last_written: Optional[str] = None
    blob_bytes: int = 0                         # طولِ خام؛ محتوایِ خام هرگز
    winerror: int = 0

    def __repr__(self) -> str:                   # dataclassِ frozen باِ reprِ دستی
        return ("CredentialRead(ok=%s, code=%r, user_masked=%r, target=%r, "
                "persist=%s, last_written=%r, blob_bytes=%d)"
                % (self.ok, self.code, mask_username(self.username), self.target,
                   self.persist, self.last_written, self.blob_bytes))

    def __str__(self) -> str:
        return repr(self)


def mask_username(user: str) -> str:
    """نمایشِ پوشیده: دو کاراکتر اول + آخر. بی‌این، نامِ کاربری (شمارۀ موبایل)
    درِ هر لاگ و هر پاسخِ API کامل می‌رفت."""
    u = (user or "").strip()
    if not u:
        return ""
    if len(u) <= 4:
        return u[:1] + "*" * (len(u) - 1)
    return u[:2] + "*" * (len(u) - 3) + u[-1:]


def _is_windows() -> bool:
    import os
    return os.name == "nt"


def _u32(buf: bytes, off: int) -> int:
    return int.from_bytes(buf[off:off + 4], "little")


def _ptr(buf: bytes, off: int) -> int:
    return int.from_bytes(buf[off:off + 8], "little")


def _wide(addr: int, limit: int = 512) -> str:
    if not addr:
        return ""
    try:
        return ctypes.wstring_at(ctypes.c_void_p(addr), limit).split("\x00")[0]
    except Exception:
        return ""


def _filetime(buf: bytes) -> Optional[str]:
    lo, hi = _u32(buf, _OFF_LASTWRITEN), _u32(buf, _OFF_LASTWRITEN + 4)
    v = (hi << 32) | lo
    if v <= 0:
        return None
    try:
        dt = datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=v / 10)
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        return None


def _parse(buf: bytes, want_target: str) -> CredentialRead:
    """پارسِ بافرِ رکورد، باِ راستی‌آزماییِ چیدمان. اگر چیزی باِ اثباتِ بالا
    نخواند، MALFORMED — نه حدسِ جایِ دیگر."""
    if _u32(buf, _OFF_TYPE) != CRED_TYPE_GENERIC:
        return CredentialRead(False, "MALFORMED", target=want_target)
    target = _wide(_ptr(buf, _OFF_TARGET))
    if target != want_target:
        # نشانیِ خواسته‌شده و خوانده‌شده یکی نیست ⇒ چیدمان عوض شده است
        return CredentialRead(False, "MALFORMED", target=want_target)
    size = _u32(buf, _OFF_BLOBSIZE)
    blob_addr = _ptr(buf, _OFF_BLOB)
    user = _wide(_ptr(buf, _OFF_USERNAME))
    if size == 0 or not blob_addr:
        # اعتبارنامه‌ای که رمز ندارد: «هست» ولی به‌دردِ ورود نمی‌خورد
        return CredentialRead(False, "MALFORMED", username=user, target=target)
    if size % 2 or size > 4096:
        return CredentialRead(False, "MALFORMED", username=user, target=target)
    try:
        raw = ctypes.string_at(ctypes.c_void_p(blob_addr), size)
        password = raw.decode("utf-16-le")
    except Exception:
        return CredentialRead(False, "MALFORMED", username=user, target=target)
    if not password:
        return CredentialRead(False, "MALFORMED", username=user, target=target)
    return CredentialRead(True, "OK", username=user, password=password, target=target,
                          persist=_u32(buf, _OFF_PERSIST), last_written=_filetime(buf),
                          blob_bytes=size)


def read_easytrader_credential(target: str = EASYTRADER_TARGET) -> CredentialRead:
    """فقط‌خواندنِ `BorsTerminal:EasyTrader`. هیچ نوشتن/پاک‌کردنی انجام نمی‌دهد."""
    if not _is_windows():
        return CredentialRead(False, "UNSUPPORTED", target=target)
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
        return CredentialRead(False, "UNSUPPORTED", target=target)
    holder = ctypes.c_void_p(0)
    ctypes.set_last_error(0)
    try:
        ok = read(target, CRED_TYPE_GENERIC, 0, ctypes.byref(holder))
    except Exception:
        return CredentialRead(False, "UNSUPPORTED", target=target)
    if not ok:
        err = ctypes.get_last_error()
        code = "MISSING" if err == _ERROR_NOT_FOUND else "DENIED"
        return CredentialRead(False, code, target=target, winerror=err)
    if not holder.value:
        return CredentialRead(False, "MALFORMED", target=target)
    try:
        buf = ctypes.string_at(holder, _RECORD_BYTES)
        return _parse(buf, target)
    finally:
        try:
            free(holder)
        except Exception:
            pass


def public_status(result: Optional[CredentialRead] = None) -> dict[str, Any]:
    """آنچه رابط و `/api/execution/status` نشان می‌دهند. رمز، طولِ رمز و هر
    نشانه‌ای ازِ محتوا اینجا نیست — فقط «هست یا نه» و نامِ پوشیده."""
    r = result or read_easytrader_credential()
    return {
        "provider": "windows-credential-manager",
        "target": r.target or EASYTRADER_TARGET,
        "present": bool(r.ok),
        "code": r.code,
        "user_masked": mask_username(r.username) if r.ok else "",
        "last_written": r.last_written if r.ok else None,
        # راهنمایِ متنِ رابط: چه چیزی ازِ کاربر خواسته شود، بدونِ اینکه هیچ‌وقت
        # رمز درِ چت یا ترمینال نوشته شود
        "hint": ({
            "OK": "",
            "MISSING": ("اعتبارنامه‌ای باِ نشانیِ BorsTerminal:EasyTrader درِ "
                        "Windows Credential Manager نیست؛ ازِ خودِ Control Panel "
                        "یا cmdkey اضافه‌اش کنید"),
            "UNSUPPORTED": "مخزنِ اعتبارنامۀ ویندوز رویِ این سامانه‌عامل در دسترس نیست",
            "MALFORMED": ("اعتبارنامه پیدا شد ولی ساختارش خوانده نشد؛ دوباره "
                          "ذخیره‌اش کنید"),
            "DENIED": "دسترسی به مخزنِ اعتبارنامه رد شد (ویندوز خطا داد)",
        }.get(r.code, "")),
    }


def self_check() -> dict[str, Any]:
    """سنجشِ بی‌خطرِ خودِ خواننده: آیا اصلاً می‌تواند بگوید چیزی هست یا نه؟
    هرگز چیزی نمی‌نویسد و محتوایی چاپ نمی‌کند."""
    r = read_easytrader_credential()
    return {"code": r.code, "present": r.ok, "user_masked": mask_username(r.username),
            "target_ok": r.target == EASYTRADER_TARGET, "winerror": r.winerror}
