# -*- coding: utf-8 -*-
"""چالشِ رسمیِ 429 کدال — begin → تصویر → end، مشترک بین فچر تقویم و خط کدال.

این ماژول «دور زدن» نیست: همان مسیری است که خودِ کدال در مرورگر نشان می‌دهد.
بعد از end موفق، هدرِ X-Captcha-Token روی همان Session می‌نشیند؛ کد فقط تا
چند دقیقه معتبر است و هر Session تازه دوباره چالش می‌خواهد.
"""
import os
import sys
import tempfile
import time
from pathlib import Path

CAPTCHA_API = "https://search.codal.ir/api/ddos/v1"
CAPTCHA_IMAGE = Path(tempfile.gettempdir()) / "bors_codal_captcha.png"


def open_captcha_image(path):
    """تصویر را با نمایشگر پیش‌فرض ویندوز باز می‌کند؛ خطا فقط مسیر را می‌گوید."""
    try:
        os.startfile(str(path))  # type: ignore[attr-defined]
    except Exception:
        print("[captcha] تصویر: %s" % path)


def read_captcha_code(code_file=None, timeout_s=240):
    """کد را از فایل (اجرای غیرتعاملی/تست) یا stdin می‌خواند.

    بدون فایل و بدون TTY هرگز منتظر نمی‌ماند؛ اجرای خودکار باید سریع False
    بگیرد، نه اینکه ۴ دقیقه معلق بماند.
    """
    if code_file:
        p = Path(code_file)
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if p.exists():
                code = p.read_text(encoding="utf-8").strip()
                if code:
                    return code
            time.sleep(0.5)
        return ""
    if not sys.stdin or not sys.stdin.isatty():
        return ""
    try:
        return input("کد امنیتی کدال: ").strip()
    except EOFError:
        return ""


def solve_captcha(session, code_file=None, prompt=None, opener=None,
                  max_attempts=3):
    """یک چالش را کامل می‌کند؛ True یعنی همین session مجاز شد."""
    prompt = prompt or (lambda: read_captcha_code(code_file))
    opener = opener or open_captcha_image
    session.headers.setdefault("origin", "https://codal.ir")
    session.headers.setdefault("referer", "https://codal.ir/ReportList.aspx?search")
    for attempt in range(1, max_attempts + 1):
        try:
            begin = session.post(CAPTCHA_API + "/begin",
                                 json={"clientId": "ABBS"}, timeout=20)
            begin.raise_for_status()
            token = (begin.json() or {}).get("CaptchaToken")
            if not token:
                print("[captcha] توکنِ چالش نیامد")
                return False
            img = session.get(CAPTCHA_API + "/Captcha/" + token, timeout=20)
            img.raise_for_status()
            CAPTCHA_IMAGE.write_bytes(img.content)
            print("[captcha] تصویرِ چالش ذخیره شد (تلاش %d): %s" % (attempt, CAPTCHA_IMAGE))
            opener(CAPTCHA_IMAGE)
            code = (prompt() or "").strip()
            if not code:
                print("[captcha] کدی وارد نشد؛ توقف بدونِ نوشتنِ داده")
                return False
            end = session.post(CAPTCHA_API + "/end",
                               json={"CaptchaToken": token, "Captchatext": code},
                               timeout=20)
            if end.status_code == 200:
                session.headers["X-Captcha-Token"] = token
                print("[captcha] تأیید شد؛ ادامهٔ درخواست‌ها در همین session")
                return True
            print("[captcha] کد پذیرفته نشد (%s): %s" % (end.status_code, end.text[:120]))
        except Exception as exc:
            print("[captcha] خطای چالش: %s: %s" % (type(exc).__name__, exc))
    print("[captcha] پس از چند تلاش عبور نکرد؛ توقف")
    return False
