# -*- coding: utf-8 -*-
# پرتاب‌گرِ تشخیصیِ ریگ ۸۰۲۰: همان app:app، به‌اضافهٔ یک نخِ نگهبان که هر ۲ms
# می‌خوابد و اگر بیدارشدنش بیش از GAP_MS طول کشید (یعنی نخِ دیگری GIL را نگه
# داشته بود)، پشتهٔ همهٔ نخ‌های دیگر را در همان لحظه ثبت می‌کند. کدِ محصول
# دست نمی‌خورد؛ فقط درِ همین فرایندِ آزمایشی اجرا می‌شود.
import json
import os
import sys
import threading
import time
import traceback

OUT = sys.argv[1]
SI = float(sys.argv[2]) if len(sys.argv) > 2 else 0.005
GAP_MS = float(sys.argv[3]) if len(sys.argv) > 3 else 80.0
sys.setswitchinterval(SI)
sys.path.insert(0, os.getcwd())


def watchdog():
    me = threading.get_ident()
    names = {}
    with open(OUT, "w", encoding="utf-8") as f:
        while True:
            t0 = time.perf_counter()
            time.sleep(0.002)
            gap = (time.perf_counter() - t0) * 1000.0
            if gap < GAP_MS:
                continue
            for t in threading.enumerate():
                names[t.ident] = t.name
            stacks = {}
            for ident, fr in sys._current_frames().items():
                if ident == me:
                    continue
                st = traceback.extract_stack(fr)
                if not any("Borsterminal" in s.filename and "site-packages" not in s.filename
                           for s in st):
                    continue
                stacks[names.get(ident, str(ident))] = [
                    "%s:%d %s | %s" % (os.path.relpath(s.filename, os.getcwd())
                                       if "Borsterminal" in s.filename else os.path.basename(s.filename),
                                       s.lineno, s.name, (s.line or "")[:120])
                    for s in st[-8:]]
            f.write(json.dumps({"wall": round(time.time(), 3), "gap_ms": round(gap, 1),
                                "stacks": stacks}, ensure_ascii=False) + "\n")
            f.flush()


threading.Thread(target=watchdog, name="gil-watchdog", daemon=True).start()
import uvicorn  # noqa: E402

uvicorn.run("app:app", host="127.0.0.1", port=8020, log_level="warning")
