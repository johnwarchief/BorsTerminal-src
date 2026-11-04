# -*- coding: utf-8 -*-
"""گاردِ چالشِ رسمی 429 تقویم — begin/تصویر/end روی sessionِ ساختگی، بی‌شبکه."""
import sys
import tempfile
from pathlib import Path

DEV = Path(__file__).resolve().parent
if str(DEV) not in sys.path:
    sys.path.insert(0, str(DEV))
import calendar_fetcher as cf  # noqa: E402
import codal_captcha  # noqa: E402

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS %s%s" % (name, (" — " + str(detail)) if detail else ""))
    else:
        FAIL += 1
        print("  FAIL %s%s" % (name, (" — " + str(detail)) if detail else ""))


class Resp:
    def __init__(self, status=200, payload=None, content=b"IMG", text=""):
        self.status_code = status
        self._payload = payload or {}
        self.content = content
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP %d" % self.status_code)


class FakeSession:
    def __init__(self, end_statuses=None):
        self.headers = {}
        self.calls = []
        self.end_statuses = list(end_statuses or [200])

    def post(self, url, json=None, timeout=None):
        self.calls.append(("post", url, json))
        if url.endswith("/begin"):
            return Resp(payload={"CaptchaToken": "tok-1"})
        if url.endswith("/end"):
            return Resp(self.end_statuses.pop(0) if self.end_statuses else 200,
                        text="wrong")
        return Resp(status=404)

    def get(self, url, timeout=None):
        self.calls.append(("get", url))
        return Resp(content=b"PNG")


def run():
    old_image = codal_captcha.CAPTCHA_IMAGE
    with tempfile.TemporaryDirectory() as tmp:
        codal_captcha.CAPTCHA_IMAGE = Path(tmp) / "captcha.png"
        try:
            # ۱) موفق: begin → تصویر → end → هدرِ توکن
            s = FakeSession()
            opened = []
            ok = cf.solve_captcha(s, prompt=lambda: "AB12",
                                  opener=lambda p: opened.append(p))
            check("success returns True", ok is True)
            check("captcha image is written",
                  codal_captcha.CAPTCHA_IMAGE.read_bytes() == b"PNG")
            check("image is opened for the operator", opened == [codal_captcha.CAPTCHA_IMAGE])
            posts = [c for c in s.calls if c[0] == "post"]
            check("begin then end are called", [p[1].rsplit("/", 1)[-1] for p in posts] == ["begin", "end"])
            check("end carries token and code",
                  posts[-1][2] == {"CaptchaToken": "tok-1", "Captchatext": "AB12"})
            check("session carries the captcha token",
                  s.headers.get("X-Captcha-Token") == "tok-1")

            # ۲) کدِ نادرست: تلاشِ دوم با تصویرِ تازه
            s2 = FakeSession(end_statuses=[400, 200])
            codes = iter(["bad", "good"])
            ok2 = cf.solve_captcha(s2, prompt=lambda: next(codes),
                                   opener=lambda p: None)
            begins = [c for c in s2.calls if c[0] == "post" and c[1].endswith("/begin")]
            ends = [c for c in s2.calls if c[0] == "post" and c[1].endswith("/end")]
            check("wrong code retries and then succeeds", ok2 is True)
            check("each attempt begins a fresh challenge", len(begins) == 2)
            check("the accepted code is the second one",
                  ends[-1][2]["Captchatext"] == "good")

            # ۳) کدِ خالی: هیچ end و هیچ نوشتنِ داده
            s3 = FakeSession()
            ok3 = cf.solve_captcha(s3, prompt=lambda: "", opener=lambda p: None)
            check("empty code returns False", ok3 is False)
            check("empty code never submits end",
                  not any(c[0] == "post" and c[1].endswith("/end") for c in s3.calls))
        finally:
            codal_captcha.CAPTCHA_IMAGE = old_image
    print("calendar captcha guard: %d passed / %d failed" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
