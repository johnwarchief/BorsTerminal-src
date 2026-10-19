# -*- coding: utf-8 -*-
# dev/execution_har_api_v1.py — گاردِ دو درِ HAR درِ لایۀ API
#
# چرا فراخوانِ مستقیم و نه TestClient: دو در `async` هستند و به بانک یا شبکه نیازی
# ندارند؛ یکِ `Request`ِ ساختگی همان مسیرِ کد را باِ کنترلِ کامل می‌آرد و گارد به
# `httpx` یا به `market.db` (که درِ Git نیست) گره نمی‌خورد.
#
# پنج حکمی که می‌پرسد:
#   درِ تحلیل هیچ‌وقت نشانی نمی‌نویسد، حتی اگر HAR پر ازِ هدرِ دسترسی باشد.
#   درِ برداشت بی‌آداپتورِ token‌پذیر یا بی‌ترافیکِ مجاز رد می‌شود و هیچ مقداری
#     درِ حافظه نمی‌ماند (رفتارِ قرینِ `/session`).
#   برداشتِ موفق تأییدهایِ پیشین را بی‌اعتبار می‌کند — همان قفلِ «نشستنِ تازه ⇒
#     تأییدِ قبلی مرده است».
#   هیچ پاسخِ هیچ‌کدام ازِ دو در مقدارِ نشانی، کوکی یا بدنه را برنمی‌گرداند.
#   ثبت‌شدنِ دو در درِ خودِ router، ازِ router خوانده می‌شود (نه ازِ متنِ فایل).

import asyncio
import base64
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS = FAIL = 0


def ck(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   " + label)
    else:
        FAIL += 1
        print("  FAIL " + label + ((" — " + extra) if extra else ""))


class FakeRequest:
    def __init__(self, body: bytes, headers: dict[str, str] | None = None) -> None:
        self._body = body
        self.headers = headers or {}

    async def body(self) -> bytes:
        return self._body


class FakeAdapter:
    def __init__(self) -> None:
        self.token = None
        self.calls = 0

    def set_token(self, v):
        self.calls += 1
        self.token = v

    def has_token(self):
        return bool(self.token)

    def capabilities(self):
        from execution_contract import Capabilities
        return Capabilities(place=False, list_orders=False, order_state=False,
                            queue_position=False, cancel=False, best_bid_ask=False,
                            balances=False)


def _jwt(exp: int) -> str:
    def b64(obj):
        return base64.urlsafe_b64encode(
            json.dumps(obj, separators=(",", ":")).encode("utf-8")
        ).decode("ascii").rstrip("=")
    return "%s.%s.%s" % (b64({"alg": "RS256"}), b64({"exp": exp, "sub": "hidden-sub"}),
                         "sig-not-verifiable-abc")


def _har(tok: str, host: str = "api-mts.orbis.easytrader.ir") -> bytes:
    return json.dumps({"log": {"entries": [{
        "request": {"method": "GET", "url": "https://%s/core/api/order" % host,
                    "headers": [{"name": "Authorization", "value": "Bearer " + tok},
                                {"name": "Cookie", "value": "COOKIE-SENT-1"}]},
        "response": {"status": 200, "content": {"mimeType": "application/json",
                                                "text": json.dumps(
                                                    {"buyingPower": 999,
                                                     "password": "BODY-SENT-1"})}}}]}}
    ).encode("utf-8")


SENT = ("Bearer ", "hidden-sub", "COOKIE-SENT-1", "BODY-SENT-1", "999")


def _no_secret(doc, tok: str) -> bool:
    blob = json.dumps(doc, ensure_ascii=False)
    return all(s not in blob for s in SENT[1:]) and tok not in blob


def main():
    print("execution_har_api_v1 — دو درِ HAR، بی‌نشتی و بی‌نشستِ جعلی")
    import api.execution as EX

    exp = 1_800_000_000
    tok = _jwt(exp)

    # ── ثبتِ درها ازِ خودِ router ──
    paths = {r.path for r in EX.router.routes}
    ck("/api/execution/har/inspect" in paths and "/api/execution/har/session" in paths,
       "هر دو در درِ router ثبت است", str(sorted(p for p in paths if "har" in p)))

    voided_calls: list[str] = []
    void_real, inspect_real = EX._void_confirmations, EX._session_dict
    EX._void_confirmations = lambda why: (voided_calls.append(why), 2)[1]
    EX._session_dict = lambda: {"state": "unknown", "proven": False}
    adapter_real, kind_real, traffic_real = (EX._ACTIVE_ADAPTER, EX.ADAPTER_KIND,
                                             EX.TRAFFIC_ALLOWED)
    try:
        # ── ۱) درِ تحلیل: هیچ نشانی‌ای نمی‌نویسد ──
        fa = FakeAdapter()
        EX._ACTIVE_ADAPTER, EX.ADAPTER_KIND, EX.TRAFFIC_ALLOWED = fa, "mock", False
        r = asyncio.run(EX.post_har_inspect(FakeRequest(_har(tok))))
        ck(r["status"] == "success" and fa.calls == 0 and voided_calls == [],
           "تحلیل نه نشانی می‌نویسد نه تأییدها را می‌شکند", json.dumps(r)[:160])
        ck(_no_secret(r, tok), "پاسخِ تحلیل هیچ مقداری ازِ HAR ندارد",
           json.dumps(r, ensure_ascii=False)[:200])
        ck(len(r["api_paths"]) == 1 and r["api_paths"][0]["path"] == "/core/api/order",
           "مسیرِ wire درِ پاسخ هست", str(r.get("api_paths")))

        bad = asyncio.run(EX.post_har_inspect(FakeRequest(b"not json at all")))
        ck(bad["code"] == "NOT_JSON" and bad["session_touched"] is False,
           "پروندۀِ خراب ⇒ کدِ خطا، بی‌ادعایِ نشست", json.dumps(bad))
        huge = asyncio.run(EX.post_har_inspect(
            FakeRequest(b"{}", {"content-length": str(1024 ** 3)})))
        ck(huge["code"] == "TOO_LARGE", "سقفِ اندازه پیشِ خواندنِ بدن رد می‌کند")
        empty = asyncio.run(EX.post_har_inspect(FakeRequest(b"")))
        ck(empty["code"] == "EMPTY" and empty["session"]["state"] == "unknown",
           "بدنۀِ خالی ⇒ EMPTY، بی‌هیچ تغییری درِ نشست")

        # ── ۲) درِ برداشت: همان دو گیتِ `/session` ──
        fa = FakeAdapter()
        EX._ACTIVE_ADAPTER, EX.ADAPTER_KIND, EX.TRAFFIC_ALLOWED = fa, "mock", True
        r = asyncio.run(EX.post_har_session(FakeRequest(_har(tok))))
        ck(r["imported"] is False and fa.calls == 0 and r["code"] == "UNSUPPORTED",
           "آداپتورِ بدل ⇒ رد، بی‌نوشتنِ نشانی", json.dumps(r)[:160])
        fa = FakeAdapter()
        EX._ACTIVE_ADAPTER, EX.ADAPTER_KIND, EX.TRAFFIC_ALLOWED = fa, "easytrader", False
        r = asyncio.run(EX.post_har_session(FakeRequest(_har(tok))))
        ck(r["imported"] is False and fa.calls == 0 and "ترافیک" in r["detail"],
           "ترافیکِ بسته ⇒ رد، قرینِ /session", json.dumps(r)[:160])

        # ── ۳) برداشتِ موفق — باِ خودِ EasyTraderAdapter، نه بدلِ دست‌ساز ──
        # درِ تولید `_ACTIVE_ADAPTER` یکِ EasyTraderAdapter واقعی است؛ سنجشِ این
        # شاخه باِ شیءِ ساختگی خودِ `isinstance` را می‌کشت و گارد سبزِ بی‌معنی می‌داد.
        from execution_easytrader import EasyTraderAdapter, RefusingTransport
        real = EasyTraderAdapter(transport=RefusingTransport(), writes_allowed=False)
        EX._ACTIVE_ADAPTER, EX.ADAPTER_KIND, EX.TRAFFIC_ALLOWED = real, "easytrader", True
        voided_calls.clear()
        r = asyncio.run(EX.post_har_session(FakeRequest(_har(tok))))
        ck(r["imported"] is True and real.has_token(),
           "نشست درِ حافظه نشست", json.dumps({k: v for k, v in r.items() if k != "session"}))
        ck(voided_calls and "HAR" in voided_calls[0] and r["confirmations_voided"] == 2,
           "تأییدهایِ پیشین باِ نشستنِ تازه بی‌اعتبار شدند", str(voided_calls))
        ck(_no_secret(r, tok), "پاسخِ برداشت مقدارِ نشانی را ندارد",
           json.dumps(r, ensure_ascii=False)[:240])
        ck(r["session"]["proven"] is False and r["live"] is False,
           "برداشت ≠ تأیید: نشستِ پاسخ هنوز proven=false و live=false است")
        ck(r["capabilities"]["balances"] is False,
           "پاسخ capabilityهایِ واقعیِ آداپتور را می‌گوید، نه ادعایِ تازه")

        # ── ۴) میزبانِ بیگانه: هیچ چیزی برداشت نمی‌شود ──
        dead = EasyTraderAdapter(transport=RefusingTransport(), writes_allowed=False)
        voided_calls.clear()
        r = asyncio.run(EX.post_har_session(
            FakeRequest(_har(tok, host="collector.example"))))
        ck(r["imported"] is False and not dead.has_token() and r["code"] == "NO_WIRE_HOST",
           "کنترلِ منفی: HARِ میزبانِ بیگانه نشانی نمی‌نویسد", json.dumps(r)[:160])
        ck(voided_calls == [], "برداشتِ ردشده تأییدها را نمی‌شکند", str(voided_calls))
    finally:
        EX._void_confirmations, EX._session_dict = void_real, inspect_real
        EX._ACTIVE_ADAPTER, EX.ADAPTER_KIND, EX.TRAFFIC_ALLOWED = (
            adapter_real, kind_real, traffic_real)

    print("\nexecution_har_api_v1: %d passed / %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
