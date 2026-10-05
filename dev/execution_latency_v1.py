# -*- coding: utf-8 -*-
# dev/execution_latency_v1.py — گاردِ سنجشِ تأخیر (Stage I، بی‌کارگزاری)
#
# همه‌چیز رویِ 127.0.0.1 و با یک سرورِ HTTP محلی می‌چرخد؛ هیچ نشانیِ کارگزاری
# اندازه گرفته نمی‌شود و هیچ درخواستی به بیرون نمی‌رود.
#
# چهار حکمی که سنجیده می‌شود:
#   • فازها جدا گزارش می‌شوند (DNS/TCP/TTFB) — نه یکِ HEAD به ریشۀِ میزبان (§۷-ج).
#   • warmup و پرت حذف می‌شوند و *ثبت* می‌شوند، نه بی‌صدا دور ریخته.
#   • بدونِ نمونهٔ قابلِ اتکا، برآوردِ یک‌طرفه `None` است؛ صفر یعنی «زود بفرست»
#     و رویِ لحظۀِ بازگشایی یعنی دیر رسیدن.
#   • ریاضِ صدک/یک‌طرفه از `execution_timing` می‌آید، از نو نوشته نمی‌شود.
#
# اجرا:  python dev/execution_latency_v1.py

import io
import os
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from execution_latency import LatencyProber, measure, one_way_from  # noqa: E402

PASS = FAIL = 0


def ck(cond, what, got=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {what}")
    else:
        FAIL += 1
        print(f"  FAIL {what}" + (f"  -> {got}" if got else ""))


class Handler(BaseHTTPRequestHandler):
    """HEAD/GET ساده؛ اگر `delay_for` ست شده باشد، آن تعدادِ اول را کند می‌کند."""
    slow_first = 0
    slow_s = 0.0

    def do_HEAD(self):
        type(self).seen += 1
        if type(self).seen <= type(self).slow_first:
            time.sleep(type(self).slow_s)
        self.send_response(200)
        self.end_headers()

    do_GET = do_HEAD

    def log_message(self, *a):                      # بی‌لاگِ سروصدا
        pass


Handler.seen = 0


def serve(slow_first=0, slow_s=0.0):
    Handler.seen = 0
    Handler.slow_first = slow_first
    Handler.slow_s = slow_s
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def part_phases():
    srv, port = serve()
    try:
        s = LatencyProber(f"http://127.0.0.1:{port}").sample()
        ck(not s.error, "نمونۀِ محلی بی‌خطا است", s.error)
        ck(s.dns_ms is not None and s.tcp_ms is not None,
           "DNS و TCP جدا اندازه گرفته می‌شوند", f"dns={s.dns_ms} tcp={s.tcp_ms}")
        ck(s.tls_ms is None, "HTTP بی‌TLS فازِ TLS جعلی نمی‌سازد", str(s.tls_ms))
        ck(s.ttfb_ms is not None and s.total_ms >= (s.tcp_ms or 0),
           "TTFB و کلِ مسیر گزارش می‌شوند", f"ttfb={s.ttfb_ms} total={s.total_ms}")
    finally:
        srv.shutdown()


def part_stats():
    srv, port = serve()
    try:
        rep = measure(f"http://127.0.0.1:{port}", samples=6, warmup=2)
        ck(rep.n >= 4, "نمونه‌ها پس از warmup می‌مانند", str(rep.n))
        ck(any(d.startswith("warmup") for d in rep.dropped),
           "warmup حذف می‌شود ولی *ثبت* می‌شود", str(rep.dropped[:2]))
        mn, p50, p90, mx = rep.stat("min"), rep.stat("p50"), rep.stat("p90"), rep.stat("max")
        ck(mn <= p50 <= p90 <= mx, "صدکها مرتب‌اند", f"{mn}/{p50}/{p90}/{mx}")
        ck(rep.jitter_ms is not None and rep.jitter_ms >= 0.0,
           "jitter = p90 − p50 محاسبه می‌شود", str(rep.jitter_ms))
        ck(rep.usable_for_planning(), "نمونۀِ محلیِ کم‌نوسان قابلِ برنامه‌ریزی است")
        ow = one_way_from(rep, "p50")
        ck(ow is not None and abs(ow - p50 / 2.0) < 1e-6,
           "یک‌طرفه از همین گزارش = نصفِ صدکِ برگزیده", f"{ow} vs {p50}")
    finally:
        srv.shutdown()


def part_outliers():
    # دو اول را ~۳۰۰ms کند می‌کنیم؛ با سقفِ ۱۰۰ms باید به‌عنوانِ پرت حذف و ثبت شوند
    srv, port = serve(slow_first=3, slow_s=0.3)
    try:
        rep = measure(f"http://127.0.0.1:{port}", samples=5, warmup=0, max_rtt_ms=100.0)
        ck(any(d.startswith("outlier") for d in rep.dropped),
           "پرتِ تأخیر حذف و *نامش* ثبت می‌شود", str(rep.dropped[:3]))
        ck(rep.n and max(rep.rtt_ms) <= 100.0,
           "آمارِ باقی‌مانده از سقفِ پرت بیرون نمی‌زند", str(rep.rtt_ms[:3]))
    finally:
        srv.shutdown()


def part_no_data():
    dead = socket.socket(); dead.bind(("127.0.0.1", 0)); port = dead.getsockname()[1]; dead.close()
    rep = measure(f"http://127.0.0.1:{port}", samples=3, warmup=0, timeout_s=0.3)
    ck(rep.n == 0, "میزبانِ بی‌گوش ⇒ صفر نمونه", str(rep.n))
    ck(rep.stat("p50") is None and rep.jitter_ms is None,
       "بی‌نمونه هیچ صدکی جعلی ساخته نمی‌شود")
    ck(not rep.usable_for_planning(), "بی‌نمونه قابلِ برنامه‌ریزی نیست")
    ck(one_way_from(rep) is None, "برآوردِ یک‌طرفه None است، **نه صفر**",
       str(one_way_from(rep)))
    ck(any(d.startswith("error") for d in rep.dropped),
       "خطا ثبت می‌شود، نه بی‌صدا", str(rep.dropped[:2]))

    # کمبودِ نمونه ⇒ قابلِ استفاده نیست، حتی اگر همه‌چیز سالم باشد
    srv, p2 = serve()
    try:
        thin = measure(f"http://127.0.0.1:{p2}", samples=1, warmup=0)
        ck(not thin.usable_for_planning(min_samples=3),
           "یک نمونه برایِ زمان‌بندی کافی نیست")
        ck(one_way_from(thin, "p50") is None,
           "با نمونهٔ کم، برآورد داده نمی‌شود (بی‌صدا جلو نمی‌رود)")
    finally:
        srv.shutdown()


def part_single_source():
    """ریاض نباید دو جا نوشته شود."""
    lat = io.open(os.path.join(ROOT, "execution_latency.py"), encoding="utf-8").read()
    body = lat.split('"""', 2)[2]
    ck("from execution_timing import" in body,
       "صدک/یک‌طرفه از execution_timing وارد می‌شود")
    ck("def percentile" not in body and "/ 2.0" not in body.replace("p90 - p50", ""),
       "درِ execution_latency ریاضِ تکراریِ صدک/یک‌طرفه نوشته نشده")


def main():
    print("execution_latency_v1 — سنجشِ تأخیر رویِ سرورِ محلی (بی‌کارگزاری)")
    part_phases(); part_stats(); part_outliers(); part_no_data(); part_single_source()
    print(f"\nexecution_latency_v1: {PASS} passed / {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
