# -*- coding: utf-8 -*-
# dev/execution_har_v1.py — گاردِ «HAR را بخوان، راز را برندار»
#
# پنج حکمی که نگهبانش است:
#   ۱) گزارشِ تحلیل هیچ مقدارِ هدر یا بدنه‌ای ندارد — با sentinel کاشته‌شده درِ
#      هر سه جایِ ممکن (هدرِ authorization، هدرِ cookie، بدنۀِ پاسخ) سنجیده می‌شود.
#   ۲) توکن فقط ازِ میزبانِ مجازِ wire برداشته می‌شود؛ همان هدر رویِ میزبانِ
#      بیگانه باید برداشت نشود (کنترلِ منفی).
#   ۳) برداشتِ نشانی بی‌هیچ «موفقیتِ» ساختگی: بی‌هدر، بی‌میزبان، یا آداپتورِ
#      بی‌set_token ⇒ imported=False باِ علتِ دقیق.
#   ۴) اگر مقداری درِ متنِ مسیر هم باشد (JWT درِ query/path) ازِ `redact()`
#      می‌گذرد — لایۀِ دوم، تزئینی نیست.
#   ۵) کنترلِ منفیِ خودِ سنسور: گزارشی که sentinel را حمل کند باید قرمز شود،
#      وگرنه سبزِ بندهایِ ۱ و ۴ هیچ معنایی ندارد.

import base64
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import execution_har as EH  # noqa: E402

PASS = FAIL = 0


def ck(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   " + label)
    else:
        FAIL += 1
        print("  FAIL " + label + ((" — " + extra) if extra else ""))


def _jwt(exp: int, sub: str = "someone-not-to-print") -> str:
    def b64(obj):
        raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return "%s.%s.%s" % (b64({"alg": "RS256", "typ": "JWT"}),
                         b64({"sub": sub, "exp": exp, "iat": exp - 300}),
                         "Zm9vcy1zaWctbm90LXZlcmlmaWFibGU")


BEAR_SENT = "Bearer SENT-BEARER-9f3a." + "x" * 24
COOKIE_SENT = "SESSIONCOOKIE=COOKIE-SENTINEL-AbCdEf; csrftoken=CSRf-SENTINEL-zz9"
BODY_SENT = "PWSENTINEL-q1w2e3"
WIRE = ("api-mts.orbis.easytrader.ir",)
EVIL = ("evil-collector.example",)


def _har(exp: int, auth_host: str = WIRE[0]) -> tuple[str, str]:
    """یکِ HARِ آزمونی باِ sentinel درِ هر سه جایِ نشتیِ ممکن."""
    tok = _jwt(exp)
    entries = [
        {"request": {"method": "GET", "url": "https://%s/core/api/order?since=1" % auth_host,
                     "headers": [{"name": "Authorization", "value": "Bearer " + tok},
                                 {"name": "Cookie", "value": COOKIE_SENT}],
                     "cookies": []},
         "response": {"status": 200,
                      "content": {"mimeType": "application/json",
                                  "text": json.dumps({"data": [{"id": 7, "password": BODY_SENT}],
                                                      "buyingPower": 12345678})}}},
        {"request": {"method": "POST", "url": "https://cdn.example/logo.png",
                     "headers": [], "cookies": []},
         "response": {"status": 200, "content": {"mimeType": "image/png"}}},
    ]
    return json.dumps({"log": {"version": "1.2", "entries": entries}}), tok


def _main_har_leaks(report: dict, tok: str) -> list[str]:
    """هر sentinel درِ JSONِ گزارش = نشتی. این خودِ سنسور است."""
    blob = json.dumps(report, ensure_ascii=False)
    return [s for s in (tok, "SENT-BEARER-9f3a", "COOKIE-SENTINEL-AbCdEf",
                        "CSRf-SENTINEL-zz9", BODY_SENT, "12345678",
                        "someone-not-to-print") if s in blob]


def main():
    print("execution_har_v1 — ساختار را ببین، مقدار را نه")

    # ── ۱) تجزیۀِ سخت‌گیرانه ──
    for bad, code in (("نه JSON", "NOT_JSON"),
                      ('{"log":{}}', "SHAPE"),
                      ('{"log":{"entries":"نه فهرست"}}', "SHAPE"),
                      ('{"entries":[]}', "SHAPE")):
        try:
            EH.load_entries(bad)
            ck(False, "رد می‌شود: %s" % code, "هیچ خطایی نگرفتیم")
        except EH.HarError as e:
            ck(e.code == code, "رد باِ %s" % code, "کدِ %s آمد" % e.code)
    ck(EH.load_entries('{"log":{"entries":[{}]}}') == [{}], "HARِ درست پذیرفته می‌شود")

    # ── ۲) نشانی ──
    ck(EH.url_parts("https://H.example/core/api/order?token=S#frag")[0:3]
       == ("https", "h.example", "/core/api/order"), "کوئری و fragment ازِ مسیر می‌روند")
    ck(EH.url_parts("not a url") == ("", "", ""), "نشانیِ بی‌ساختار ⇒ سه خالی")
    ck(EH.url_parts("https://user:pass@H.example/x")[1] == "h.example",
       "userinfo ازِ میزبان بیرون می‌رود")

    # ── ۳) تحلیلِ بی‌نشتی ──
    now = 1_800_000_000
    raw, tok = _har(now)
    rep = EH.inspect(raw, hosts=WIRE)
    leaks = _main_har_leaks(rep, tok)
    ck(not leaks, "هیچ مقداری ازِ HAR درِ گزارش نیست", ", ".join(leaks[:3]))
    ck(rep["entries_total"] == 2, "شمارشِ ردیف‌ها ازِ خودِ پروندۀ", str(rep))
    ck(rep["api_paths_capped"] is False, "سقفِ مسیرها خورده نشده")
    paths = [(r["method"], r["path"], r["status"]) for r in rep["api_paths"]]
    ck(("GET", "/core/api/order", 200) in paths,
       "مسیرِ wire باِ متد و وضعیت ثبت می‌شود", str(paths))
    ck(all("cdn.example" != r["host"] for r in rep["api_paths"]),
       "میزبانِ بیرونِ wire ردیفِ مسیر نمی‌گیرد")
    hosts = {h["host"]: h for h in rep["hosts"]}
    ck(hosts[WIRE[0]]["auth_bearing"] == 1 and hosts[WIRE[0]]["cookie_bearing"] == 1,
       "میزبان علامتِ auth و cookie می‌گیرد (بدونِ مقدار)")
    keys = next(r["response_keys"] for r in rep["api_paths"] if r["path"] == "/core/api/order")
    ck("buyingPower" in keys and "data[].id" in keys,
       "نامِ کلیدهایِ پاسخ برایِ کشفِ مسیرِ موجودی دیده می‌شود", str(keys))
    ck(rep["session_touched"] is False and rep["is_order"] is False,
       "گزارش صریح است که نه نشست است نه سفارش")

    # ── ۴) لایۀِ دوم: مقداری که درِ خودشِ مسیر جا شده ──
    leaky = json.dumps({"log": {"entries": [{
        "request": {"method": "GET", "headers": [],
                    "url": "https://%s/ping?access_token=%s" % (WIRE[0], tok)},
        "response": {"status": 200, "content": {"mimeType": "application/json",
                                                "text": "{}"}}}]}})
    rep2 = EH.inspect(leaky, hosts=WIRE)
    ck(_main_har_leaks(rep2, tok) == [], "JWTِ جاافتاده درِ مسیر هم پاک می‌شود",
       json.dumps(rep2["api_paths"], ensure_ascii=False)[:160])
    ck("<redacted>" in json.dumps(rep2, ensure_ascii=False),
       "پاک‌سازی درِ گزارش علامت می‌گذارد (سنسور کور نیست)")

    # ── ۵) برداشتِ نشانی ──
    class Fake:
        def __init__(self): self.token = None; self.calls = 0
        def set_token(self, v): self.calls += 1; self.token = v

    got, meta = EH.find_bearer(EH.load_entries(raw), WIRE)
    ck(got == "Bearer " + tok, "بردارِ کاملِ هدر ازِ میزبانِ مجاز برداشته می‌شود")
    ck(meta["kind"] == "bearer" and meta["exp"] == now,
       "نوعِ نشانی و `exp` ازِ خودِ مقدار خوانده می‌شود", str(meta))
    ck("Bearer" not in json.dumps(meta, ensure_ascii=False),
       "متای گزارشِ برداشت مقدارِ نشانی را ندارد", json.dumps(meta))
    bad_host, m2 = EH.find_bearer(EH.load_entries(_har(now, auth_host=EVIL[0])[0]), WIRE)
    ck(bad_host is None and m2["on_wire"] == 0,
       "کنترلِ منفی: همان هدر رویِ میزبانِ بیگانه برداشت نمی‌شود", str(m2))

    a = Fake()
    r = EH.import_session(raw, a, hosts=WIRE)
    ck(r["imported"] is True and a.token == "Bearer " + tok, "set_token صدا زده می‌شود")
    ck(_main_har_leaks(r, tok) == [], "پاسخِ برداشت مقدارِ نشانی را ندارد",
       json.dumps(r, ensure_ascii=False)[:200])
    ck(r.get("token_in_response") is False, "پاسخ صریح است که نشانی برنگشته")

    b = Fake()
    r2 = EH.import_session(_har(now, auth_host=EVIL[0])[0], b, hosts=WIRE)
    ck(r2["imported"] is False and b.calls == 0 and r2["code"] == "NO_WIRE_HOST",
       "بی‌میزبانِ مجاز ⇒ هیچ نشانی‌ای نوشته نمی‌شود", json.dumps(r2))
    cookie_only = json.dumps({"log": {"entries": [{
        "request": {"method": "GET", "url": "https://%s/x" % WIRE[0],
                    "headers": [{"name": "Cookie", "value": COOKIE_SENT}]},
        "response": {"status": 200, "content": {"mimeType": "application/json",
                                                "text": "{}"}}}]}})
    c = Fake()
    r3 = EH.import_session(cookie_only, c, hosts=WIRE)
    ck(r3["imported"] is False and c.calls == 0 and r3["code"] == "COOKIE_ONLY",
       "کوکی تنها ⇒ برداشت نمی‌شود، چون آداپتور کوکی نمی‌فرستَد", json.dumps(r3))
    d = EH.import_session(raw, object(), hosts=WIRE)
    ck(d["imported"] is False and d["code"] == "UNSUPPORTED",
       "آداپتورِ بی‌set_token ⇒ رد، بی‌خطایِ غیرمنتظره")
    e = EH.import_session(raw, Fake(), hosts=("nothing.example",))
    ck(e["imported"] is False and e["code"] == "NO_WIRE_HOST",
       "کنترلِ منفیِ دوم: wire_hostsِ بی‌ربط همان رد را می‌سازد")

    # ── ۶) کنترلِ منفیِ خودِ سنسور ──
    planted = dict(rep)
    planted["detail"] = "این خط عمداً می‌نوشتم: " + tok
    ck(len(_main_har_leaks(planted, tok)) >= 1,
       "اگر مقداری نشت کند سنسور قرمز می‌شود (پس سبزِ بندِ ۳ معنا دارد)")
    ck(_jwt_exp_none(), "غیرِ JWT ⇒ None، نه خطا")

    print("\nexecution_har_v1: %d passed / %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


def _jwt_exp_none() -> bool:
    return EH._jwt_exp("نهjwt") is None and EH._jwt_exp("") is None \
        and EH._jwt_exp("a.b") is None


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
