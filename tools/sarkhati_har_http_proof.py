# -*- coding: utf-8 -*-
# tools/sarkhati_har_http_proof.py — سنجشِ زندهٔ دو درِ HAR رویِ HTTPِ خودِ برنامه
#
# چرا یکِ فایلِ جدا و نه گارد: گاردها توابع را درِ همان پروسه صدا می‌زنند؛ اینجا
# پاسخِ واقعیِ یکِ uvicornِ روشن است — همان بدنه‌ای که رابطِ کاربری می‌بیند.
# دو چیز سنجیده می‌شود که گاردِ in-process نمی‌تواند: (۱) بدنهٔ خامِ POSTِ بزرگ
# می‌رسد و رد می‌شود/پذیرفته می‌شود، (۲) هیچ‌چیز درِ پاسخِ HTTP نیامده است.
#
# هیچ درخواستی به بیرون نمی‌رود: آداپتورِ پیش‌فرض بدل است، و شاخه‌هایِ ردِ نشانی
# پیشِ هر ترافیک برمی‌گردند. نشانیِ آزمونی ساختگی است.
import base64
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("BORS_PROOF_BASE", "http://127.0.0.1:8010")
PASS = FAIL = 0


def ck(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   " + label)
    else:
        FAIL += 1
        print("  FAIL " + label + ((" — " + extra) if extra else ""))


def _jwt(exp):
    def b64(o):
        return base64.urlsafe_b64encode(
            json.dumps(o, separators=(",", ":")).encode()).decode().rstrip("=")
    return "%s.%s.%s" % (b64({"alg": "RS256"}), b64({"exp": exp, "sub": "SECRET-SUB"}),
                         "sig-not-real")


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return r.status, r.read()


def post(path, body: bytes, ctype="application/json"):
    req = urllib.request.Request(BASE + path, data=body,
                                 headers={"Content-Type": ctype}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def main():
    print("sarkhati_har_http_proof — دو درِ HAR رویِ HTTPِ واقعی")
    print("  base = " + BASE)
    exp = 1_800_000_000
    tok = _jwt(exp)
    adapter = json.loads(get("/api/execution/status")[1]).get("adapter")
    print("  adapter درِ این پروسه = %s" % adapter)

    doc = {"log": {"entries": [
        {"request": {"method": "GET",
                     "url": "https://api-mts.orbis.easytrader.ir/core/api/order?x=1",
                     "headers": [{"name": "Authorization", "value": "Bearer " + tok},
                                 {"name": "Cookie", "value": "SESSION=COOKIE-SENT-42"}]},
         "response": {"status": 200,
                      "content": {"mimeType": "application/json",
                                  "text": json.dumps({"buyingPower": 777111,
                                                      "data": [{"id": 1,
                                                                "password": "BODY-SENT-7"}]})}}},
        {"request": {"method": "GET", "url": "https://login.emofid.com/realms/x/auth",
                     "headers": []},
         "response": {"status": 200, "content": {"mimeType": "text/html",
                                                 "text": "<html>hi</html>"}}},
    ]}}
    har = json.dumps(doc).encode("utf-8")

    st, raw = post("/api/execution/har/inspect", har)
    rep = json.loads(raw)
    ck(st == 200 and rep.get("status") == "success", "درِ تحلیل رویِ HTTP پاسخ داد",
       "%s %s" % (st, raw[:160]))
    leaks = [s for s in (tok, "SECRET-SUB", "COOKIE-SENT-42", "BODY-SENT-7", "777111")
             if s.encode() in raw]
    ck(not leaks, "بدنۀِ پاسخِ HTTP هیچ مقداری ازِ HAR ندارد", ", ".join(leaks))
    paths = [(r["method"], r["path"], r["status"]) for r in rep.get("api_paths", [])]
    ck(("GET", "/core/api/order", 200) in paths, "مسیرِ wire ازِ بدنه درِ پاسخ است",
       str(paths))
    ck(rep.get("entries_total") == 2 and rep.get("off_wire_hosts") == 1,
       "شمارش‌ها ازِ خودِ پرونده می‌آید (یکِ میزبانِ بیرونِ wire)",
       "%s / %s" % (rep.get("entries_total"), rep.get("off_wire_hosts")))
    keys = next((r["response_keys"] for r in rep.get("api_paths", [])
                 if r["path"] == "/core/api/order"), [])
    ck("buyingPower" in keys, "نامِ کلیدِ موجودی دیده می‌شود (همان چیزی که §۵ خواست)",
       str(keys))

    st, raw = post("/api/execution/har/session", har)
    imp = json.loads(raw)
    ck(st == 200 and imp.get("imported") is False,
       "بی‌آداپتورِ token‌پذیر، برداشت رد می‌شود", raw[:200].decode("utf-8", "replace"))
    ck("SECRET-SUB" not in raw.decode("utf-8", "replace") and tok not in
       raw.decode("utf-8", "replace"), "حتی درِ مسیرِ رد، نشانی برنمی‌گردد")

    st, raw = post("/api/execution/har/inspect", b"this is not json")
    ck(json.loads(raw).get("code") == "NOT_JSON", "بدنۀِ خراب ⇒ کدِ خطا، بی‌ادعا",
       raw[:160].decode("utf-8", "replace"))
    one = json.dumps({"x": "A" * 400}).encode("utf-8")
    big = b'{"log":{"entries":[' + b",".join([one] * 300) + b"]}}"
    st, raw = post("/api/execution/har/inspect", big)
    got = json.loads(raw).get("entries_total", 0)
    ck(st == 200 and got == 300, "بدنۀِ ~۱۳۰ هزاربایتی هم خوانده و تجزیه می‌شود",
       "%s %s" % (st, raw[:120]))

    print("\nsarkhati_har_http_proof: %d passed / %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
