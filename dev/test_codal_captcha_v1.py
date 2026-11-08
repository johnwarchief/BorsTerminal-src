# -*- coding: utf-8 -*-
"""گاردِ اتصال چالش 429 به fetch_page — fake session، بی‌شبکه/بی‌خواب."""
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import codal_captcha  # noqa: E402
import codal_fetcher as cf  # noqa: E402

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
    def __init__(self):
        self.headers = {}
        self.search_calls = 0
        self.posts = []

    def get(self, url, headers=None, timeout=None, **kw):
        if "/Captcha/" in url:
            return Resp(content=b"CAPTCHA")
        self.search_calls += 1
        if self.search_calls == 1:
            return Resp(status=429, text="rate limit")
        return Resp(payload={"Letters": [{"TracingNo": 1, "Title": "مجمع"}]})

    def post(self, url, json=None, timeout=None, **kw):
        self.posts.append((url, json))
        if url.endswith("/begin"):
            return Resp(payload={"CaptchaToken": "tok-9"})
        if url.endswith("/end"):
            return Resp()
        return Resp(status=404)


def run():
    old_image = codal_captcha.CAPTCHA_IMAGE
    old_opener = codal_captcha.open_captcha_image
    old_pause, old_sleep, old_backoff = cf.polite_pause, cf._control_sleep, cf._trigger_backoff
    with tempfile.TemporaryDirectory() as tmp:
        codal_captcha.CAPTCHA_IMAGE = Path(tmp) / "captcha.png"
        codal_captcha.open_captcha_image = lambda path: None
        cf.polite_pause = lambda: None
        cf._control_sleep = lambda s: None
        cf._trigger_backoff = lambda s: None
        try:
            # ۱) 429 → چالش → retryِ همان صفحه → 200
            s = FakeSession()
            cf.enable_captcha(prompt=lambda: "AB12")
            letters = cf.fetch_page(s, 1, query={"Category": 6}, quiet=True)
            check("retry after captcha returns the page",
                  letters == [{"TracingNo": 1, "Title": "مجمع"}], repr(letters))
            check("search request retried exactly once", s.search_calls == 2)
            check("captcha token is attached to the session",
                  s.headers.get("X-Captcha-Token") == "tok-9")
            ends = [p for p in s.posts if p[0].endswith("/end")]
            check("end carries the operator code",
                  ends and ends[-1][1].get("Captchatext") == "AB12")

            # ۲) بدون روشن‌بودن captcha هیچ چالشی باز نمی‌شود
            cf._CAPTCHA_ENABLED = False
            cf._CAPTCHA_ATTEMPTED = False
            s2 = FakeSession()
            out2 = cf.fetch_page(s2, 1, query={"Category": 6},
                                 max_429_retries=0, quiet=True)
            check("disabled captcha keeps the old give-up path", out2 is None)
            check("disabled captcha never calls begin/end",
                  not any(p[0].endswith("/begin") or p[0].endswith("/end") for p in s2.posts))
        finally:
            codal_captcha.CAPTCHA_IMAGE = old_image
            codal_captcha.open_captcha_image = old_opener
            cf.polite_pause, cf._control_sleep, cf._trigger_backoff = old_pause, old_sleep, old_backoff
            cf._CAPTCHA_ENABLED = False
    print("codal fetch captcha guard: %d passed / %d failed" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
