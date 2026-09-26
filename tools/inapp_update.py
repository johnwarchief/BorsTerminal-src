"""به‌روزرسانی درون‌برنامه‌ایِ نسخهٔ نصب‌شده را از طریق API خودِ برنامه اجرا می‌کند.

چرخهٔ تأییدِ ریلیز: یک ریلیز تا وقتی واقعی نیست که روی کلاینتِ نصب‌شده از
مسیرِ آپدیترِ داخلی (check → download → progress → install) بالا نرفته باشد.
این اسکریپت دقیقاً همان چهار فراخوانیِ دکمهٔ «به‌روزرسانی» را انجام می‌دهد
تا اثباتِ قابل‌تکرار داشته باشیم.

    python tools/inapp_update.py            # فقط بررسیِ موجود بودنِ آپدیت
    python tools/inapp_update.py --apply    # دانلود + نصب
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8001"


def _get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def _post(path: str, payload: dict | None) -> dict:
    data = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(
        BASE + path, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="دانلود و نصب کن")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    def say(*a):
        if not args.quiet:
            print(*a, flush=True)

    check = _get("/api/update/check")
    say("current=", check.get("current_version"),
        "latest=", check.get("latest_version"),
        "available=", check.get("available"),
        "delta=", check.get("delta"),
        "size=", check.get("size"))
    if not check.get("available"):
        say("به‌روزی موجود نیست.")
        return 0
    if not args.apply:
        say("بدون --apply: فقط بررسی شد.")
        return 0

    say("\n→ download")
    dl = _post("/api/update/download", {
        "url": check["url"],
        "signature": check.get("signature"),
        "version": check["latest_version"],
    })
    say("download:", json.dumps(dl, ensure_ascii=False)[:300])

    deadline = time.time() + 900
    last = ""
    while time.time() < deadline:
        prog = _get("/api/update/progress")
        cur = json.dumps({k: prog.get(k) for k in ("status", "percent", "message", "is_patch")},
                         ensure_ascii=False)
        if cur != last:
            say("progress:", cur)
            last = cur
        # وضعیتِ سرور در `status` است (downloading → ready → installing)؛ کلیدِ
        # `stage` در پاسخ وجود ندارد — با آن این حلقه تا مهلتِ ۹۰۰ ثانیه می‌چرخید
        # و نصب هرگز صدا زده نمی‌شد.
        if prog.get("status") in ("ready", "installing", "installed", "error"):
            break
        time.sleep(2)
    else:
        say("timeout در انتظارِ دانلود")
        return 2

    prog = _get("/api/update/progress")
    if prog.get("status") == "error":
        say("دانلود خطا داد:", json.dumps(prog, ensure_ascii=False)[:400])
        return 3
    if prog.get("status") != "ready":
        say("بسته آماده نیست:", json.dumps(prog, ensure_ascii=False)[:300])
        return 3

    say("\n→ install")
    # مسیرِ پچ: برنامه برایِ اعمالِ overlay خودش خارج می‌شود، پس پاسخِ این درخواست
    # عملاً قطع می‌شود (WinError 10054). قطعِ اتصال = شروعِ نصب، نه شکست؛ دلیلِ
    # واقعی فقط نسخهٔ تازه‌ای است که پس از بالا آمدنِ برنامه می‌خوانیم.
    try:
        inst = _post("/api/update/install", None)
        say("install:", json.dumps(inst, ensure_ascii=False)[:400])
    except Exception as exc:  # noqa: BLE001
        say("install: اتصال قطع شد (%s) — در مسیرِ پچ طبیعی است" % type(exc).__name__)

    want = str(check.get("latest_version") or "")
    deadline = time.time() + 240
    while time.time() < deadline:
        try:
            got = str(_get("/api/update/version").get("version") or "")
        except Exception:  # noqa: BLE001 — پنجرهٔ نصب/راه‌اندازیِ دوباره
            time.sleep(4)
            continue
        if got == want:
            say("نصب تأیید شد: نسخهٔ در حال اجرا =", got)
            return 0
        say("   در انتظارِ نسخهٔ %s (الان %s)" % (want, got or "-"))
        time.sleep(5)
    say("نسخهٔ تازه بالا نیامد.")
    return 4


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        print("FAILED:", type(e).__name__, e, file=sys.stderr)
        sys.exit(1)
