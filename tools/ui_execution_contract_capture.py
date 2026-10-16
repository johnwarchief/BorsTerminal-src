# tools/ui_execution_contract_capture.py -- ضبطِ قراردادِ واقعیِ دروازۀِ سرخطی
#
# چرا اینِ فایل هست (بندِ ۱.۱ مأموریتِ System 2: «پاسخِ ۲۰۰ به‌تنهایی کافی نیست»):
# آزمونِ رگرسیونِ `frontend/src/__tests__/order-line-contract.spec.ts` باید پاسخ‌های
# واقعیِ خودِ سرویس را بخواند، نه چیزی که رابط حدس زده. پسِ اینجا هرِ endpoint را
# رویِ یکِ بک‌اندِ آزمایشی (mock/dry-run) صدا می‌زند وِ http status + content-type +
# بدنه را عیناً ذخیره می‌کند. `content-type` عمدًاً ثبت می‌شود: مسیرِ ثبت‌نشده درِ
# همینِ اپ ۲۰۰ باِ `text/html` می‌دهد (fallbackِ SPA) وِ آنِ «موفقِ بی‌قرارداد» همان
# نقصی است که باید درِ آزمونِ ثابت بماند.
#
# اجرا:  python tools/ui_execution_contract_capture.py --base http://127.0.0.1:8012
#        (بک‌اندِ آزمایشی باِ BORS_NO_FETCH_LOOPS=1 وِ BORS_EXECUTION_ADAPTER=mock)
# هیچِ سفارشِ واقعی ارسال نمی‌شود: پیش ازِ هرِ نوشتار، `status` خوانده می‌شود وِ
# بی‌`dry_run: true` + `live_enabled: false` + `nothing_will_leave_the_machine: true`
# اسکریپت پیش ازِ اولینِ نوشتار می‌ایستد.
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "frontend" / "src" / "__tests__" / "fixtures" / "execution-contract.json"

ap = argparse.ArgumentParser()
ap.add_argument("--base", default="http://127.0.0.1:8012")
ap.add_argument("--out", default=str(OUT))
A = ap.parse_args()


def call(base, method, path, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data else {})
    ctype = http = None
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            http, ctype = r.status, r.headers.get("content-type")
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        http, ctype = e.code, e.headers.get("content-type")
        raw = e.read().decode("utf-8", "replace")
    except Exception as e:                      # network-level: ثبتِ «نرسید»
        return {"request": {"method": method, "path": path, "body": body},
                "response": {"http": None, "content_type": None, "error": str(e)[:200]}}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"__non_json__": raw[:200]}
    return {"request": {"method": method, "path": path, "body": body},
            "response": {"http": http, "content_type": ctype, "body": parsed}}


base = A.base
out = {"base": base, "cases": {}}

status = call(base, "GET", "/api/execution/status")
sb = status["response"]["body"]
safe = (sb.get("dry_run") is True and sb.get("live_enabled") is False
        and sb.get("nothing_will_leave_the_machine") is True)
out["cases"]["status"] = status
if not safe:
    print("توقف: سرویس درِ حالتِ بدلِ قفل نیست — هیچ نوشتاری آزموده نمی‌شود", file=sys.stderr)
    Path(A.out).parent.mkdir(parents=True, exist_ok=True)
    Path(A.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(1)

GOOD0 = {"execution_id": "fx-ok-1", "symbol": "فولاد", "side": "buy", "mode": "safe",
         "price": 5170, "quantity": 50, "confirmed": True, "mock_instrument": True}
RUN = str(int(time.time()))


def eid(tag, over=None):
    """شناسۀِ یکتا درِ هرِ اجرا: ردِّپا رویِ دیسک می‌ماند وِ تکرارِ شناسه،
    خودِ سرویس را DUPLICATE_GUARD می‌کند -- پسِ فیکسچرِ امروز نباید بهِ
    ردِّپایِ دیروز بربخورد (وِگرنه «تازگیِ شناسه» با «خطایِ سرویس» قاطی می‌شود)."""
    b = dict(GOOD0, execution_id=f"fx-{tag}-{RUN}")
    if over:
        b.update(over)
    return b


GOOD = eid("send")
PREPARED = eid("prepared")
NO_ISIN = {"execution_id": f"fx-noisin-{RUN}", "symbol": "شپنا", "side": "buy", "mode": "safe",
           "price": 1040, "quantity": 100, "confirmed": True, "mock_instrument": True}
BARE = eid("bare")
BARE.pop("mock_instrument")
NOCONF = eid("noconf", {"confirmed": False})
out["cases"]["session_get"] = call(base, "GET", "/api/execution/session")
out["cases"]["limits"] = call(base, "GET", "/api/execution/limits")
out["cases"]["preflight_ok"] = call(base, "POST", "/api/execution/preflight", GOOD)
out["cases"]["preflight_no_isin"] = call(base, "POST", "/api/execution/preflight", NO_ISIN)
out["cases"]["preflight_bare_no_mapping"] = call(base, "POST", "/api/execution/preflight", BARE)
out["cases"]["prepare_ok"] = call(base, "POST", "/api/execution/prepare", PREPARED)
# رزرو: همانِ شناسه‌ای که prepare گرفت، درِ dispatch رد می‌شود (بندِ ۱.۳: «باِ
# قراردادِ واقعی، نه باِ آرزویِ رابط»). اینِ دوِ سطر همینِ ترتیب را ثابت می‌کنند.
out["cases"]["prepare_then_dispatch_same_id"] = call(base, "POST", "/api/execution/dispatch", PREPARED)
out["cases"]["dispatch_ok"] = call(base, "POST", "/api/execution/dispatch", GOOD)
out["cases"]["dispatch_same_id_again"] = call(base, "POST", "/api/execution/dispatch", GOOD)
out["cases"]["dispatch_without_confirmed_flag"] = call(base, "POST", "/api/execution/dispatch", NOCONF)
out["cases"]["dispatch_unorderable"] = call(base, "POST", "/api/execution/dispatch", NO_ISIN)
out["cases"]["reconcile_ok"] = call(base, "POST", f"/api/execution/reconcile/{GOOD['execution_id']}", {})
out["cases"]["reconcile_unknown_id"] = call(base, "POST", "/api/execution/reconcile/fx-never-existed", {})
out["cases"]["audit"] = call(base, "GET", f"/api/execution/audit/{GOOD['execution_id']}")
out["cases"]["ledger"] = call(base, "GET", "/api/execution/ledger")
out["cases"]["halt"] = call(base, "POST", "/api/execution/halt", {})
out["cases"]["dispatch_while_halt"] = call(base, "POST", "/api/execution/dispatch", eid("halted"))
out["cases"]["resume"] = call(base, "POST", "/api/execution/resume", {})
# مسیرِ ثبت‌نشده: شاهدِ همانِ ۲۰۰-HTML که بندِ ۱.۱ درباره‌اش هشدار می‌دهد
out["cases"]["unregistered_path"] = call(base, "GET", "/api/execution/definitely-not-a-route")

Path(A.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
n = len(out["cases"])
kinds = {}
for k, v in out["cases"].items():
    ct = (v["response"].get("content_type") or "?").split(";")[0]
    kinds[ct] = kinds.get(ct, 0) + 1
print(f"موارد={n} → {A.out}")
print("content-typeها:", json.dumps(kinds, ensure_ascii=False))
dup = out["cases"]["dispatch_same_id_again"]["response"]["body"]
print("تکرارِ همانِ شناسه:", dup.get("status"), dup.get("code"),
      (dup.get("checks") or {}).get("duplicate"))
print("ارسال درِ حالتِ توقف:", out["cases"]["dispatch_while_halt"]["response"]["body"].get("status"),
      out["cases"]["dispatch_while_halt"]["response"]["body"].get("code"))
