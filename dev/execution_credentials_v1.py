# -*- coding: utf-8 -*-
# dev/execution_credentials_v1.py — گاردِ providerِ اعتبارنامۀ EasyTrader
#
# چه چیزی سنجیده می‌شود و چرا:
#   پارسرِ چیدمان: بافرهایِ ساختگیِ هم‌اندازه باِ Type/Target/BlobSize نادرست
#     باید MALFORMED بدهند، نه دادهٔ غلط. چیدمان ازِ سه رکوردِ مستقل
#     اندازه‌گیری شده؛ اگر روزی ویندوز آن را عوض کند، همین گارد اول می‌فهمد.
#   سانسور: رمز درِ repr، str، public_status و self_check نباید بیاید، و نامِ
#     کاملِ کاربری هم نه.
#   نبودِ اعتبارنامه ⇒ کدِ MISSING باِ راهنمایِ روشن، نه کرش و نه «هست».
#   کنترلِ منفی: سنجشِ «targetِ نادرست» باید باِ برداشتنِ بررسیِ برابری قرمز
#     شود — ثابت می‌کند سنسور کور نیست.
#
# این سوئیت چیزی درِ مخزنِ اعتبارنامه نمی‌نویسد و پاک نمی‌کند؛ فقط بافرهایِ
# ساختگی و یکِ خواندنِ targetِ وجودنداشته. آفلاین است.
# اجرا:  python dev/execution_credentials_v1.py

import ctypes
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import execution_credentials as EC  # noqa: E402

PASS = FAIL = 0
TARGET = "BorsTerminal:EasyTrader"
DUMMY_USER = "09120000000"
DUMMY_SECRET = "DUMMY-NOT-A-REAL-PASSWORD"


def ck(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   " + label)
    else:
        FAIL += 1
        print("  FAIL " + label + ((" — " + extra) if extra else ""))


def make_record(target=TARGET, user=DUMMY_USER, secret=DUMMY_SECRET,
                cred_type=1, persist=3, blob_size=None):
    """رکوردِ ۹۶ بایتی باِ چیدمانِ اثبات‌شده، رویِ حافظۀِ زندهٔ همین پروسه.
    هیچ دادهٔ واقعی‌ای درِ آن نیست؛ شیءها زنده نگه داشته می‌شوند."""
    blob = ctypes.create_unicode_buffer(secret) if secret is not None else None
    raw_bytes = secret.encode("utf-16-le") if secret else b""
    size = len(raw_bytes) if blob_size is None else blob_size
    blob_addr = ctypes.addressof(blob) if blob is not None else 0
    tgt = ctypes.create_unicode_buffer(target)
    usr = ctypes.create_unicode_buffer(user)
    buf = (ctypes.c_char * EC._RECORD_BYTES)()
    view = bytearray(EC._RECORD_BYTES)
    for off, val in ((0, 0), (4, cred_type), (48, persist), (52, 0),
                     (32, size), (80, size)):
        view[off:off + 4] = int(val).to_bytes(4, "little")
    for off, addr in ((EC._OFF_TARGET, ctypes.addressof(tgt)),
                      (EC._OFF_USERNAME, ctypes.addressof(usr)),
                      (EC._OFF_BLOB, blob_addr),
                      (EC._OFF_COMMENT, 0), (EC._OFF_ATTRS, 0)):
        view[off:off + 8] = int(addr).to_bytes(8, "little")
    ctypes.memmove(buf, bytes(view), EC._RECORD_BYTES)
    keep = (buf, blob, tgt, usr, raw_bytes)
    return ctypes.addressof(buf), keep


def parse(addr):
    return EC._parse(ctypes.string_at(ctypes.c_void_p(addr), EC._RECORD_BYTES), TARGET)


def main():
    print("execution_credentials_v1 — گاردِ providerِ مخزنِ اعتبارنامۀ ویندوز")

    # ── مسیرِ موفقِ پارس، بی‌دست‌زدن به مخزن ──
    addr, keep = make_record()
    r = parse(addr)
    ck(r.ok and r.code == "OK", "چیدمانِ اثبات‌شده ⇒ OK", r.code)
    ck(r.username == DUMMY_USER, "نامِ کاربری درست خوانده شد")
    ck(r.password == DUMMY_SECRET, "رمزِ ساختگی درست رمزگشایی شد (UTF-16)")
    ck(r.blob_bytes == len(DUMMY_SECRET) * 2, "طولِ blob ازِ خودِ رکورد خوانده می‌شود",
       str(r.blob_bytes))
    ck(r.persist == 3, "Persist خوانده شد")
    ck(r.last_written is None or len(r.last_written) == 19,
       "زمانِ نوشتن یا تهی است یا ISO", str(r.last_written))

    # ── سانسور ──
    shown = repr(r) + str(r)
    ck(DUMMY_SECRET not in shown, "رمز درِ repr/str نیست")
    ck(DUMMY_USER not in shown, "نامِ کاملِ کاربری درِ repr نیست")
    ck("*" in shown, "نمایشِ پوشیده جایِ آن را می‌گیرد")
    pub = EC.public_status(r)
    pub_s = repr(pub)
    ck(DUMMY_SECRET not in pub_s, "رمز درِ public_status نیست")
    ck(DUMMY_USER not in pub_s, "نامِ کامل درِ public_status نیست")
    ck("blob_bytes" not in pub_s, "طولِ رمز هم بیرون نمی‌رود")
    ck(pub["present"] is True and pub["user_masked"].startswith("09")
       and pub["user_masked"].endswith("0"), "public_status وضعیتِ روشن می‌دهد")

    # ── حالت‌هایِ خرابِ چیدمان: رد، بی‌حدس ──
    for label, kw in (("Typeِ نادرست", dict(cred_type=2)),
                      ("targetِ نخوانده", dict(target="SomeOther:Target")),
                      ("blobِ تهی", dict(blob_size=0)),
                      ("طولِ فرد (غیرِ UTF-16)", dict(blob_size=27)),
                      ("رمزِ بی‌محتوا", dict(secret=""))):
        a2, k2 = make_record(**kw)
        rr = parse(a2)
        ck((not rr.ok) and rr.code == "MALFORMED", "ردِ بی‌حدس: " + label, rr.code)

    # ── نبودِ اعتبارنامه ⇒ MISSING، نه کرش ──
    if EC._is_windows():
        gone = EC.read_easytrader_credential("BorsTerminal:_definitely_absent_"
                                             + str(os.getpid()))
        ck(gone.code == "MISSING", "اعتبارنامۀ نبود ⇒ MISSING", gone.code)
        ck(not gone.ok and not gone.password, "بی‌اعتبارنامه هیچ رمزی نیست")
        st = EC.public_status(gone)
        ck(st["present"] is False and "Credential Manager" in st["hint"],
           "راهنمایِ روشن برایِ «نیست»")
        ck(gone.winerror == EC._ERROR_NOT_FOUND, "winerror ازِ خودِ ویندوز ثبت می‌شود",
           str(gone.winerror))
    else:
        print("  skip این ماشین ویندوز نیست ⇒ مسیرِ MISSING سنجیده نشد")

    # ── پوشاندنِ نام ──
    ck(EC.mask_username("") == "", "نامِ تهی ⇒ تهی")
    ck(EC.mask_username("ab") == "a*", "نامِ کوتاه فقط حرفِ اول")
    ck(EC.mask_username(DUMMY_USER) == "09" + "*" * 8 + "0",
       "نامِ ۱۱ رقمی پوشیده می‌شود", EC.mask_username(DUMMY_USER))

    # ── کنترلِ منفی: سنسورِ target باید باِ برداشتنِ بررسی قرمز شود ──
    src = open(os.path.join(ROOT, "execution_credentials.py"), encoding="utf-8").read()
    ck("if target != want_target:" in src,
       "بررسیِ برابریِ target درِ پارسر هست (بی‌آن، ردِ «targetِ نخوانده» کور است)")
    ck("if _u32(buf, _OFF_TYPE) != CRED_TYPE_GENERIC:" in src,
       "بررسیِ Type هم درِ پارسر هست")

    # ── self_check رویِ machineِ واقعی: بی‌کرش، بی‌رمز ──
    try:
        sc = EC.self_check()
        ck(all(k in sc for k in ("code", "present", "user_masked", "target_ok")),
           "self_check چهار کلیدِ روشن دارد")
        ck("password" not in repr(sc) and "blob" not in repr(sc),
           "self_check هیچ رمز یا طولِ آن را بیرون نمی‌دهد")
    except Exception as exc:                          # noqa: BLE001
        ck(False, "self_check کرش کرد", type(exc).__name__ + ": " + str(exc)[:80])

    print(f"\nexecution_credentials_v1: {PASS} passed / {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
