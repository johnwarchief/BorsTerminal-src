#!/usr/bin/env python
"""اوراکلِ طلاییِ B1: بدنۀ واقعیِ پایتون رویِ فیکسچر، برایِ تستِ Go.

بیرون از مخزن (پوشهٔ موقت) اجرا می‌شود؛ پنجره‌هایِ board_hist_* را همان پایتون
درِ کپی می‌سازد. خروجی: golden/market.json, market_all.json, delta_negative.json,
delta_mirror.json, sync_state.json
"""
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = os.path.join(ROOT, "backend-go", "internal", "board", "testdata", "fixture")
OUT = os.path.join(ROOT, "backend-go", "internal", "board", "testdata", "golden")


class Req:
    headers = {}


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="bors-b1-golden-")
    for name in ("market.db", "user.db"):
        shutil.copy2(os.path.join(FIX, name), os.path.join(tmp, name))
    os.environ["BORS_DATA_DIR"] = tmp
    os.environ["BORS_NO_FETCH_LOOPS"] = "1"
    os.environ["BORS_CODAL_OFFLINE"] = "1"
    sys.path.insert(0, ROOT)
    import api.market as M  # noqa: E402  (پس از تنظیمِ متغیرها)

    os.makedirs(OUT, exist_ok=True)

    def save(name, resp):
        if isinstance(resp, dict):
            data = resp
            body = json.dumps(resp, ensure_ascii=False).encode("utf-8")
        else:
            body = resp.body
            data = json.loads(body)
        path = os.path.join(OUT, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
        print(name, len(body), "bytes", len(data.get("data") or data.get("rows") or []), "rows")

    save("market.json", M._build_market_response(Req(), drop_unused=True, store_cache=True))
    save("market_all.json", M._build_market_response(Req(), drop_unused=False, store_cache=False))
    save("delta_negative.json", M.get_market_delta(since=-1))
    save("delta_mirror.json", M.get_market_delta(since=int(json.load(open(os.path.join(OUT, "market.json"), encoding="utf-8"))["rev"])))
    save("sync_state.json", M.market_sync_state())
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
