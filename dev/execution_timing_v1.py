# -*- coding: utf-8 -*-
# dev/execution_timing_v1.py — گاردِ موتورِ زمانِ سرخطی (Stage H)
#
# هیچ درخواستِ NTP به بیرون نمی‌رود: سرورِ SNTP بدل رویِ 127.0.0.1 می‌نشیند و
# همان قالبِ ۴۸ بایتی را برمی‌گرداند. هیچ sleepِ واقعیِ دراز هم نمی‌کنیم:
# هر دو ساعت (دیواری و یکنوا) تزریق می‌شوند.
#
# چهار حکمی که این سوئیت می‌سنجد (docs/execution/SARKHATI-ARCHITECTURE.md §۹-ب، §۷-ج):
#   • یک‌طرفه = نصفِ RTT، نه کلِ آن (اشتباهِ مرجعِ Rust).
#   • آفستِ بی‌کیفیت ⇒ یا DEGRADED با پرچم، یا ClockNotTrusted؛ هیچ‌وقت
#     `offset=0` بی‌صدا (اشتباهِ دومِ مرجع).
#   • مهلت رویِ monotonic است ⇒ پرشِ ساعتِ دیواری dispatch را جابه‌جا نمی‌کند.
#   • نزدیکِ مهلت spin می‌شود، نه فقط sleep (اشتباهِ سومِ مرجع).
#
# اجرا:  python dev/execution_timing_v1.py

import os
import socket
import struct
import sys
import threading
import time
from datetime import date, datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from execution_timing import (  # noqa: E402
    ClockNotTrusted, ClockQuality, NtpProber, Scheduler, TEHRAN_UTC_OFFSET,
    TimeSource, estimate_one_way, percentile,
)

PASS = FAIL = 0


def ck(cond, what, got=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {what}")
    else:
        FAIL += 1
        print(f"  FAIL {what}" + (f"  -> {got}" if got else ""))


# ── ساعتِ قابلِ کنترل ────────────────────────────────────────────────────────
class FakeClock:
    """یک لایۀِ زمانِ واحد: mono و wall هر دو از `t` می‌خورند، با پرشِ اختیاری."""

    def __init__(self, start_s=1_000.0, wall_ms=1_760_000_000_000):
        self.t = start_s
        self.wall0 = wall_ms
        self.wall_jump_ms = 0

    def mono(self):
        return self.t

    def wall(self):
        return self.wall0 + int(self.t * 1000) + self.wall_jump_ms

    def advance(self, dt):
        self.t += dt

    def source(self):
        return TimeSource(wall_ms=self.wall, mono=self.mono)

    def scheduler(self, **kw):
        return Scheduler(self.source(), **kw)


# ── سرورِ SNTP بدل ───────────────────────────────────────────────────────────
class FakeNtpServer:
    """۴۸ بایتِ استاندارد؛ transmit timestamp = «الانِ سرور + آفستِ دلخواه»."""

    def __init__(self, offset_ms=0.0, jitter_ms=0.0, mode="ok"):
        self.offset_ms = offset_ms
        self.jitter_ms = jitter_ms
        self.mode = mode
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.requests = 0
        self._stop = threading.Event()
        self._th = threading.Thread(target=self._serve, daemon=True)
        self._th.start()

    def _serve(self):
        self.sock.settimeout(0.2)
        while not self._stop.is_set():
            try:
                data, addr = self.sock.recvfrom(64)
            except socket.timeout:
                continue
            except OSError:
                break
            self.requests += 1
            if self.mode == "silent":
                continue                      # هیچ پاسخی نمی‌دهد ⇒ timeoutِ کلاینت
            if self.mode == "short":
                self.sock.sendto(b"\x1b" * 8, addr)
                continue
            now = time.time() + (self.offset_ms + (
                (self.jitter_ms if self.requests % 2 else -self.jitter_ms))) / 1000.0
            sec = int(now) + 2_208_988_800
            frac = int((now % 1) * 2**32)
            pkt = bytearray(48)
            pkt[0] = 0x24                     # LI=0 VN=4 Mode=4 (server)
            pkt[40:48] = struct.pack("!II", sec, frac)
            self.sock.sendto(bytes(pkt), addr)

    def close(self):
        self._stop.set()
        try:
            self.sock.close()
        except OSError:
            pass


# ── ۱) تقویمِ تهران ──────────────────────────────────────────────────────────
def part_tz():
    src = TimeSource()
    target = src.to_target_wall_ms(date(2026, 10, 6), "09:00:00")
    as_dt = datetime.fromtimestamp(target / 1000.0, tz=src.tz)
    ck(as_dt.hour == 9 and as_dt.minute == 0, "۰۹:۰۰ِ تهران به همان ساعت برمی‌گردد",
       str(as_dt))
    offs = [datetime(2026, m, 15, 12, tzinfo=src.tz).utcoffset()
            for m in (1, 4, 7, 10)]
    ck(all(o == TEHRAN_UTC_OFFSET for o in offs),
       "آفستِ تهران درِ چهار فصل +۳:۳۰ است (بی‌DST از ۱۴۰۱)", str(offs))
    fixed = TimeSource(tz=timezone(TEHRAN_UTC_OFFSET))
    ck(fixed.to_target_wall_ms(date(2026, 10, 6), "09:00:00") == target,
       "مسیرِ fallback (بی‌tzdata) همان لحظه را می‌دهد")
    ms = src.to_target_wall_ms(date(2026, 10, 6), "09:00:00.500")
    ck(ms - target == 500, "میلی‌ثانیهٔ هدف حفظ می‌شود", str(ms - target))
    try:
        src.to_target_wall_ms(date(2026, 10, 6), "۹ صبح")
        ck(False, "زمانِ بی‌قالب باید خطا بدهد")
    except ValueError:
        ck(True, "زمانِ بی‌قالب خطایِ صریح می‌دهد، نه حدس")


# ── ۲) یک‌طرفه از RTT ────────────────────────────────────────────────────────
def part_one_way():
    ck(abs(estimate_one_way([40.0], "p50") - 20.0) < 1e-9,
       "یک‌طرفه = نصفِ RTT (مرجع کلِ RTT را کم می‌کرد)")
    ck(abs(estimate_one_way([40.0, 60.0, 200.0], "min") - 20.0) < 1e-9,
       "برآوردِ min نصفِ کمینه می‌شود")
    ck(abs(estimate_one_way([40.0, 60.0, 200.0], "p90") - 100.0) < 1e-9,
       "برآوردِ p90 نصفِ صدکِ نودم می‌شود")
    ck(percentile([1, 2, 3, 4, 5], 50) == 3 and percentile([5, 1, 3], 0) == 1,
       "percentile nearest-rank درست است")
    try:
        estimate_one_way([], "p50"); ck(False, "بدونِ نمونه باید خطا بدهد")
    except ValueError:
        ck(True, "بدونِ نمونه خطا می‌دهد، نه صفرِ جعلی")
    try:
        estimate_one_way([10.0], "bogus"); ck(False, "برآوردگرِ ناشناخته باید خطا بدهد")
    except ValueError:
        ck(True, "برآوردگرِ ناشناخته بی‌سکوت رد می‌شود")


# ── ۳) NTP با سرورِ بدل ──────────────────────────────────────────────────────
def part_ntp():
    srv = FakeNtpServer(offset_ms=1234.0)
    try:
        p = NtpProber(server="127.0.0.1", port=srv.port, samples=4, timeout_s=1.0,
                      max_spread_ms=20.0)
        st = p.measure()
        ck(st.quality is ClockQuality.TRUSTED, "چهار نمونهٔ هم‌خوان ⇒ TRUSTED",
           f"{st.quality} spread={st.spread_ms}")
        ck(st.offset_ms is not None and abs(st.offset_ms - 1234.0) < 60.0,
           "آفستِ اندازه‌گیری‌شده نزدیکِ آفستِ کاشته‌شده است", str(st.offset_ms))
        ck(len(st.samples) >= 3, "نمونه‌ها شمرده و نگه داشته می‌شوند", str(len(st.samples)))
    finally:
        srv.close()

    srv = FakeNtpServer(offset_ms=0.0, jitter_ms=90.0)
    try:
        st = NtpProber(server="127.0.0.1", port=srv.port, samples=4, timeout_s=1.0,
                       max_spread_ms=20.0).measure()
        ck(st.quality is ClockQuality.UNTRUSTED,
           "پراکندگیِ بالا ⇒ UNTRUSTED (نه «میانگین بگیر و رد شو»)",
           f"{st.quality} spread={st.spread_ms}")
    finally:
        srv.close()

    srv = FakeNtpServer(offset_ms=500.0)
    try:
        st = NtpProber(server="127.0.0.1", port=srv.port, samples=2, min_samples=3,
                       timeout_s=1.0).measure()
        ck(st.quality is ClockQuality.DEGRADED,
           "نمونهٔ کمتر از حد ⇒ DEGRADED با آفست، بی‌ادعایِ اعتماد", str(st.quality))
    finally:
        srv.close()

    srv = FakeNtpServer(mode="silent")
    try:
        st = NtpProber(server="127.0.0.1", port=srv.port, samples=2, timeout_s=0.2).measure()
        ck(st.quality is ClockQuality.UNAVAILABLE and st.offset_ms is None,
           "سرورِ بی‌پاسخ ⇒ UNAVAILABLE و offset=None (مرجع بی‌صدا صفر می‌گذاشت)",
           f"{st.quality} {st.offset_ms}")
    finally:
        srv.close()

    srv = FakeNtpServer(mode="short")
    try:
        st = NtpProber(server="127.0.0.1", port=srv.port, samples=1, timeout_s=0.3).measure()
        ck(st.quality is ClockQuality.UNAVAILABLE, "بستهٔ کوتاه ⇒ UNAVAILABLE، نه آفستِ زباله",
           str(st.quality))
    finally:
        srv.close()

    dead = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dead.bind(("127.0.0.1", 0)); port = dead.getsockname()[1]; dead.close()
    st = NtpProber(server="127.0.0.1", port=port, samples=1, timeout_s=0.3).measure()
    ck(st.quality is ClockQuality.UNAVAILABLE,
       "پورتِ بسته ⇒ UNAVAILABLE (بی‌استثنا-یِ بی‌صدا از سرورِ واقعی)")


# ── ۴) برنامه‌ریزی و fail-safe ───────────────────────────────────────────────
def part_plan():
    fc = FakeClock(start_s=1000.0, wall_ms=1_760_000_000_000)
    sched = fc.scheduler(spin_window_ms=20.0)
    target = fc.wall() + 5_000
    plan = sched.plan(target, one_way_ms=20.0, margin_ms=5.0)
    ck(plan.send_at_wall_ms == target - 25,
       "مهلت = هدف − یک‌طرفه − حاشیه", str(plan.send_at_wall_ms))
    ck(abs(plan.wait_s - 4.975) < 1e-6, "صبر از همان مهلت حساب می‌شود", str(plan.wait_s))
    from execution_timing import ClockState
    loose = sched.plan(target, one_way_ms=0.0,
                       clock=ClockState(1.0, ClockQuality.DEGRADED))
    ck(loose.clock_quality is ClockQuality.DEGRADED,
       "بی‌require_trusted، آفستِ DEGRADED *با پرچم* رد می‌شود، نه بی‌صدا")

    strict = fc.scheduler(require_trusted=True)
    try:
        strict.plan(target, clock=ClockState(1.0, ClockQuality.DEGRADED))
        ck(False, "fail-safe: آفستِ DEGRADED با require_trusted باید رد شود")
    except ClockNotTrusted as e:
        ck(e.quality is ClockQuality.DEGRADED,
           "fail-safe: آفستِ غیرقابلِ اتکا بی‌صدا رد نمی‌شود، ClockNotTrusted می‌دهد")
    try:
        strict.plan(target, clock=None)
        ck(False, "بی‌اندازه‌گیری هم باید رد شود")
    except ClockNotTrusted:
        ck(True, "بی‌اندازه‌گیریِ ساعت هم رد می‌شود، نه حدس")
    try:
        sched.plan(fc.wall() + 10 * 3600 * 1000)
        ck(False, "هدفِ خیلی دور باید رد شود")
    except ValueError:
        ck(True, "هدفِ بیرونِ پنجرهٔ مجاز رد می‌شود")


# ── ) dispatch: spin، درفت، و مصونیت در برابر پرشِ ساعت ────────────────────
def part_dispatch():
    fc = FakeClock(start_s=1000.0, wall_ms=1_760_000_000_000)
    sched = fc.scheduler(spin_window_ms=20.0)
    plan = sched.plan(fc.wall() + 1_000, one_way_ms=0.0)

    slept = []
    spins = {"n": 0}

    def spin_step():
        spins["n"] += 1
        fc.advance(0.001)                       # هر گامِ spin یکِ ms جلو می‌رود

    calls = {"send": 0}

    def send():
        calls["send"] += 1
        return "BR-1"

    tel = sched.dispatch(plan, send=send, sleep=lambda s: (slept.append(s),
                                                           fc.advance(s)),
                         yield_cpu=spin_step)
    ck(calls["send"] == 1, "ارسال دقیقاً یک بار", str(calls["send"]))
    ck(spins["n"] > 0, "نزدیکِ مهلت spin می‌شود (نه فقط sleep)", f"spins={spins['n']}")
    ck(slept and slept[0] > 0, "ابتدا خوابِ درشت تا پیشِ پنجرۀِ spin", str(slept[:1]))
    ck(tel.drift_us is not None and abs(tel.drift_us) <= 1_000,
       "درفتِ dispatch زیرِ ~۱ms می‌ماند", f"{tel.drift_us}us")
    ck(tel.broker_order_id == "BR-1" and tel.actual_send_wall_ms >= plan.send_at_wall_ms,
       "تلمتری زمانِ واقعی و شناسۀِ کارگزاری را نگه می‌دارد")

    # پرشِ ساعتِ دیواری: mono عادی جلو می‌رود، wall یکدفعه ۳۰ ثانیه عقب می‌پرد
    fc2 = FakeClock(start_s=500.0, wall_ms=1_760_000_000_000)
    plan2 = fc2.scheduler(spin_window_ms=20.0).plan(fc2.wall() + 2_000)
    jumped = {"done": False}

    def send2():
        calls["send"] += 1
        return "BR-2"

    def spin2():
        if not jumped["done"]:
            fc2.wall_jump_ms = -30_000          # همان‌جا که spin است، ساعت بپرد
            jumped["done"] = True
        fc2.advance(0.001)

    tel2 = fc2.scheduler(spin_window_ms=20.0).dispatch(
        plan2, send=send2, sleep=lambda s: fc2.advance(s), yield_cpu=spin2)
    ck(jumped["done"] and abs(tel2.drift_us) <= 1_000,
       "پرشِ ۳۰ ثانیه‌ای ساعتِ دیواری dispatch را جابه‌جا نمی‌کند (لنگر = monotonic)",
       f"drift={tel2.drift_us}us")
    ck(tel2.actual_send_wall_ms != tel2.planned_send_wall_ms,
       "و این را از برچسبِ دیواری هم می‌شود دید (پلن و واقعیتِ wall فرق دارند)")


def main():
    print("execution_timing_v1 — موتورِ زمان (بی‌شبکهٔ بیرونی، بی‌خوابِ واقعی)")
    part_tz(); part_one_way(); part_ntp(); part_plan(); part_dispatch()
    print(f"\nexecution_timing_v1: {PASS} passed / {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
