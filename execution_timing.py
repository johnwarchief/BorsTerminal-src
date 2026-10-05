# -*- coding: utf-8 -*-
"""execution_timing.py — موتورِ زمانِ سرخطی: لنگرِ یکنوا، آفستِ چندنمونه‌ای، dispatch دقیق.

مرجعِ طراحی: docs/execution/SARKHATI-ARCHITECTURE.md §۹-ب و §۷-ج. آن‌جا سه اشتباهِ
مشاهده‌شده درِ مرجعِ Rust ثبت شد و این فایل دقیقاً ضدِّ همان سه‌تا نوشته شده:

۱) مرجع با `tokio::sleep` تا مهلت می‌خوابد و هیچ spin نزدیکِ deadline ندارد؛
   بیدارشدنِ scheduler می‌تواند چندِ میلی‌ثانیه دیر باشد. اینجا: خوابِ درشت تا
   `spin_window_ms` قبلِ مهلت، سپس spin تا خودِ مهلت.

۲) مرجع کلِ RTT را به‌عنوانِ «زمانِ یک‌طرفه» از هدف کم می‌کند — یعنی دو برابرِ
   خطا. اینجا `estimate_one_way()` نصفِ RTT می‌دهد و نیم‌ضرب/برآوردِ یک‌طرفه
   صریح و قابلِ تنظیم است.

۳) مرجع یک نمونهٔ NTP می‌گیرد، به میلی‌ثانیه برش می‌زند و هنگامِ خطا بی‌صدا
   `offset=0` می‌کند. اینجا کیفیتِ آفست یک *حالت* است (`ClockQuality`) و
   `Scheduler` با `require_trusted=True` بی‌آفستِ قابلِ اتکا اصلاً زمان‌بندی
   نمی‌کند — «زمان‌بندی را بی‌صدا خراب نکن» (بندِ ۱۱ دستورِ کار).

لنگرِ همهٔ محاسبه‌هایِ مهلت، `monotonic` است؛ ساعتِ دیواری فقط برایِ *گفتنِ*
زمانِ هدف و برایِ برچسبِ تلمتری به کار می‌رود. پس پرشِ ساعتِ سیستم (NTP ویندوز،
تغییرِ دستی، DST) مهلتِ ازپیش‌برنامه‌ریزی‌شده را جابه‌جا نمی‌کند.

هیچ شبکه‌ای درِ این فایل صدا زده نمی‌شود مگر آنکه خودت `NtpProber.measure()` را
بخوانی؛ آزمون‌ها با یک سرورِ SNTP بدل رویِ 127.0.0.1 کار می‌کنند.
"""
from __future__ import annotations

import os
import socket
import struct
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Sequence

TEHRAN_UTC_OFFSET = timedelta(hours=3, minutes=30)  # ایران از ۱۴۰ بی‌DST است
_NTP_PACKET = b"\x1b" + 47 * b"\0"
_SEVENTEEN_YEARS = 2_208_988_800  # 1900→1970، برایِ تبدیلِ timestampsِ SNTP


# ── ۱) ساعت ─────────────────────────────────────────────────────────────────
class ClockQuality(str, Enum):
    TRUSTED = "trusted"        # چندِ نمونهٔ هم‌خوان، پراکندگیِ کم
    DEGRADED = "degraded"      # آفست هست ولی پراکندگی/تأخیر بالا
    UNTRUSTED = "untrusted"    # آفستِ قابلِ دفاع نیست
    UNAVAILABLE = "unavailable"  # هیچ پاسخِ NTP نگرفتیم


@dataclass(frozen=True)
class NtpSample:
    offset_ms: float
    rtt_ms: float
    server: str
    error: str = ""


@dataclass(frozen=True)
class ClockState:
    """آفستِ ساعتِ سیستم نسبت به NTP، *با* کیفیتش. بی‌کیفیت، عدد بی‌معنی است."""
    offset_ms: float | None
    quality: ClockQuality
    samples: tuple[NtpSample, ...] = ()
    spread_ms: float | None = None
    measured_at: float | None = None
    detail: str = ""

    @property
    def usable(self) -> bool:
        return self.quality in (ClockQuality.TRUSTED, ClockQuality.DEGRADED)


class TimeSource:
    """ساعتِ دیواری + لنگرِ یکنوا + تقویمِ تهران، یک‌جا.

    `wall_ms` و `mono` تزریق‌پذیرند تا آزمون‌ها بی‌خوابِ واقعی و بی‌پرشِ ساعت
    بتوانند رفتارِ زمان‌بندی را بسنجند.
    """

    def __init__(self, *,
                 wall_ms: Callable[[], int] | None = None,
                 mono: Callable[[], float] | None = None,
                 tz: timezone | None = None) -> None:
        self._wall = wall_ms or (lambda: int(time.time() * 1000))
        self._mono = mono or time.monotonic
        self._tz = tz or _tehran_tz()

    def wall_ms(self) -> int:
        return int(self._wall())

    def mono(self) -> float:
        return float(self._mono())

    @property
    def tz(self) -> timezone:
        return self._tz

    def to_target_wall_ms(self, day: date, hhmmss: str) -> int:
        """«۰۹:۰۰:۰۰.۵۰۰»ِ تهران → epochِ میلی‌ثانیه.

        ثانیه/میلی‌ثانیه اختیاری‌اند؛ بی‌آن‌ها ۰۰ گرفته می‌شود.
        """
        parts = hhmmss.strip().split(":")
        if len(parts) not in (2, 3):
            raise ValueError(f"bad time: {hhmmss!r}")
        hour, minute = int(parts[0]), int(parts[1])
        sec_txt = parts[2] if len(parts) == 3 else "0"
        whole, _, frac = sec_txt.partition(".")
        second = int(whole or 0)
        micros = int((frac + "000000")[:6]) if frac else 0
        dt = datetime(day.year, day.month, day.day, hour, minute, second, micros,
                      tzinfo=self._tz)
        return int(dt.timestamp() * 1000)

    def label(self, wall_ms: int) -> str:
        return datetime.fromtimestamp(wall_ms / 1000.0, tz=self._tz).isoformat(
            timespec="milliseconds")


def _tehran_tz() -> timezone:
    """zoneinfo اگر بود؛ وگرنه +۳:۳۰ ثابت (ایران از ۱۴۰۱ تغییرِ ساعت ندارد).

    `tzdata` درِ requirements.txt نیست، پس رویِ ماشینِ تازه‌نصب zoneinfo ممکن است
    Asia/Tehran را پیدا نکند — همان‌جا به ثابتِ معلوم‌برمی‌گردیم، نه به UTC.
    """
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Asia/Tehran")
        if datetime(2026, 7, 1, tzinfo=tz).utcoffset() == TEHRAN_UTC_OFFSET:
            return tz
    except Exception:                                      # noqa: BLE002
        pass
    return timezone(TEHRAN_UTC_OFFSET, "Asia/Tehran(fixed)")


def _udp_socket() -> socket.socket:
    return socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


# ── ۲) NTP چندنمونه‌ای ───────────────────────────────────────────────────────
@dataclass
class NtpProber:
    """SNTP رویِ UDP، چندِ نمونه، انتخابِ کم‌تأخیرترین، و *داوریِ کیفیت*.

    آستانه‌ها پیش‌فرض‌هایِ مهندسی‌اند، نه روش‌شناسیِ FTS: عددِ «چندِ نمونه» و
    «چقدر پراکندگی» درِ Stage I با benchmarkِ واقعیِ همین ماشین تنظیم می‌شود؛
    تا آن‌جا صریح قابلِ تنظیم‌اند و هیچ‌جا پنهان نمی‌شوند.
    """
    server: str = "pool.ntp.org"
    port: int = 123
    samples: int = 4
    timeout_s: float = 0.4
    min_samples: int = 3
    max_spread_ms: float = 20.0
    max_rtt_ms: float = 250.0
    # دو ساعت جدا: RTT رویِ monotonic، و آفست نسبت به ساعتِ دیواریِ همان
    # لحظه. با یکِ ساعتِ واحد آفست برابرِ کلِ epoch درمی‌آمد.
    mono: Callable[[], float] = time.monotonic
    wall: Callable[[], float] = time.time
    # UDP، نه پیش‌فرضِ socket.socket که TCP است — با TCP هیچ پاسخِ SNTPی
    # برنمی‌گردد و آفست بی‌صدا UNAVAILABLE می‌شد.
    socket_factory: Callable[[], socket.socket] = _udp_socket

    def probe_once(self) -> NtpSample:
        t1m, t1w = self.mono(), self.wall()
        try:
            sock = self.socket_factory()
            sock.settimeout(self.timeout_s)
            try:
                sock.sendto(_NTP_PACKET, (self.server, self.port))
                data, _addr = sock.recvfrom(48)
            finally:
                sock.close()
        except OSError as e:
            return NtpSample(0.0, 0.0, self.server, error=type(e).__name__)
        t4m = self.mono()
        t4w = t1w + (t4m - t1m)          # ساعتِ دیواریِ لحظۀِ دریافت، تصحیح‌شده
        if len(data) < 48:
            return NtpSample(0.0, 0.0, self.server, error="short packet")
        try:
            # transmit timestamp = بایت‌هایِ ۴۰..۴۷ (uint32 ثانیه + uint32 کسر)
            sec, frac = struct.unpack("!II", data[40:48])
        except struct.error:
            return NtpSample(0.0, 0.0, self.server, error="unparsable")
        if sec == 0:
            return NtpSample(0.0, 0.0, self.server, error="zero transmit timestamp")
        server_ms = (sec - _SEVENTEEN_YEARS) * 1000.0 + frac * 1000.0 / 2**32
        rtt_ms = (t4m - t1m) * 1000.0
        # آفستِ کلاسیک: اختلافِ سرور با ساعتِ دیواریِ ما + نصفِ RTT (یک‌طرفه)،
        # نه کلِ RTT — همان اشتباهی که درِ §۷-ج ثبت شد.
        offset_ms = (server_ms + rtt_ms / 2.0) - t4w * 1000.0
        return NtpSample(offset_ms, rtt_ms, self.server)

    def measure(self) -> ClockState:
        got: list[NtpSample] = []
        for _ in range(max(1, self.samples)):
            s = self.probe_once()
            if not s.error and s.rtt_ms <= self.max_rtt_ms:
                got.append(s)
        if not got:
            return ClockState(None, ClockQuality.UNAVAILABLE,
                              detail="no usable NTP response")
        offsets = [s.offset_ms for s in got]
        spread = max(offsets) - min(offsets)
        # کم‌تأخیرترین نمونه بهترین تخمین است (مسیرِ کوتاه‌تر = خطایِ کمتر)
        best = min(got, key=lambda s: s.rtt_ms)
        if len(got) < self.min_samples:
            q = ClockQuality.DEGRADED
        elif spread > self.max_spread_ms:
            q = ClockQuality.UNTRUSTED
        else:
            q = ClockQuality.TRUSTED
        return ClockState(round(best.offset_ms, 3), q, tuple(got),
                          spread_ms=round(spread, 3), measured_at=self.mono(),
                          detail=f"{len(got)} samples, spread {spread:.1f}ms")


# ── ۳) برآوردِ یک‌طرفه ────────────────────────────────────────────────────────
def percentile(values: Sequence[float], p: float) -> float:
    if not values:
        raise ValueError("percentile of empty sequence")
    xs = sorted(values)
    k = max(0, min(len(xs) - 1, int(round(p / 100.0 * (len(xs) - 1)))))
    return xs[k]


def estimate_one_way(rtt_samples: Sequence[float], estimator: str = "p50") -> float:
    """میلی‌ثانیهٔ یک‌طرفه. §۷-ج: مرجع کلِ RTT را کم می‌کرد ⇒ اینجا نصفِ آن."""
    if not rtt_samples:
        raise ValueError("no rtt samples")
    if estimator == "min":
        chosen = min(rtt_samples)
    elif estimator == "max":
        chosen = max(rtt_samples)
    elif estimator.startswith("p"):
        chosen = percentile(rtt_samples, float(estimator[1:]))
    else:
        raise ValueError(f"unknown estimator: {estimator}")
    return chosen / 2.0


# ── ۴) برنامه‌ریزی و dispatch ────────────────────────────────────────────────
@dataclass(frozen=True)
class DispatchPlan:
    target_wall_ms: int
    send_at_wall_ms: int
    one_way_ms: float
    margin_ms: float
    lead_mono: float               # لنگرِ یکنوا درِ لحظۀِ ساختِ پلن
    wait_s: float                  # چقدر باید صبر کنیم
    spin_window_ms: float
    clock_offset_ms: float | None
    clock_quality: ClockQuality
    target_label: str = ""
    send_label: str = ""


@dataclass
class DispatchTelemetry:
    """همه‌چیزِ لازم برایِ benchmarkِ فردا (§۲۷ دستورِ کار)."""
    target_wall_ms: int
    planned_send_wall_ms: int
    actual_send_wall_ms: int = 0
    send_mono: float = 0.0
    one_way_ms: float = 0.0
    margin_ms: float = 0.0
    drift_us: float | None = None          # actual - planned، رویِ monotonic
    clock_offset_ms: float | None = None
    clock_quality: ClockQuality = ClockQuality.UNAVAILABLE
    response_at: float | None = None
    rtt_ms: float | None = None
    broker_order_id: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def early_by_us(self) -> float:
        return -self.drift_us if self.drift_us is not None else 0.0


class Scheduler:
    """مهلت را رویِ monotonic می‌گیرد؛ ساعتِ دیواری فقط برچسب است."""

    def __init__(self, clock: TimeSource, *,
                 spin_window_ms: float = 20.0,
                 require_trusted: bool = False,
                 max_wait_s: float = 6 * 3600.0) -> None:
        self.clock = clock
        self.spin_window_ms = spin_window_ms
        self.require_trusted = require_trusted
        self.max_wait_s = max_wait_s

    def plan(self, target_wall_ms: int, *, one_way_ms: float = 0.0,
             margin_ms: float = 0.0, clock: ClockState | None = None) -> DispatchPlan:
        if clock is not None:
            if self.require_trusted and clock.quality is not ClockQuality.TRUSTED:
                raise ClockNotTrusted(clock.quality, clock.detail)
        elif self.require_trusted:
            raise ClockNotTrusted(ClockQuality.UNAVAILABLE, "no measurement yet")

        now_wall = self.clock.wall_ms()
        # آفست فقط *گزارش* می‌شود؛ محاسبهٔ مهلت رویِ monotonic است، پس پرشِ
        # ساعتِ دیواریِ سیستمِ بی‌آفستِ غلط نمی‌تواند dispatch را جابه‌جا کند.
        send_at = int(target_wall_ms - one_way_ms - margin_ms)
        lead_mono = self.clock.mono()
        wait_s = (send_at - now_wall) / 1000.0
        if wait_s > self.max_wait_s:
            raise ValueError(f"target too far: {wait_s:.0f}s > {self.max_wait_s:.0f}s")
        return DispatchPlan(
            target_wall_ms=target_wall_ms, send_at_wall_ms=send_at,
            one_way_ms=one_way_ms, margin_ms=margin_ms, lead_mono=lead_mono,
            wait_s=max(0.0, wait_s), spin_window_ms=self.spin_window_ms,
            clock_offset_ms=clock.offset_ms if clock else None,
            clock_quality=clock.quality if clock else ClockQuality.UNAVAILABLE,
            target_label=self.clock.label(target_wall_ms),
            send_label=self.clock.label(send_at))

    def dispatch(self, plan: DispatchPlan, *, send: Callable[[], str | None],
                 sleep: Callable[[float], None] = time.sleep,
                 yield_cpu: Callable[[], None] | None = None) -> DispatchTelemetry:
        """تا مهلت صبر می‌کند (خوابِ درشت + spin) و بعد `send()` را صدا می‌زند.

        `send` باید *فقط* ارسالِ ازپیش‌ساخته‌شده را بزند: ساختِ payload، DNS،
        TLS و لاگِ سنگین همه باید درِ `prepare()` مانده باشد (§۱۳ دستورِ کار؛
        §۷-ج: مرجع کلاینت HTTP را بعد از بیدارشدن می‌ساخت).
        """
        step = yield_cpu or _spin_step
        tel = DispatchTelemetry(
            target_wall_ms=plan.target_wall_ms, planned_send_wall_ms=plan.send_at_wall_ms,
            one_way_ms=plan.one_way_ms, margin_ms=plan.margin_ms,
            clock_offset_ms=plan.clock_offset_ms, clock_quality=plan.clock_quality)

        deadline = plan.lead_mono + plan.wait_s
        spin_from = deadline - plan.spin_window_ms / 1000.0
        now = self.clock.mono()
        if now < spin_from:
            sleep(spin_from - now)
        while self.clock.mono() < deadline:
            step()
        tel.send_mono = self.clock.mono()
        tel.actual_send_wall_ms = self.clock.wall_ms()
        tel.drift_us = round((tel.send_mono - deadline) * 1_000_000, 1)
        tel.broker_order_id = send()
        return tel


class ClockNotTrusted(RuntimeError):
    """fail-safe: بی‌ساعتِ قابلِ اتکا زمان‌بندی نمی‌کنیم، بی‌صدا هم رد نمی‌شویم."""

    def __init__(self, quality: ClockQuality, detail: str = "") -> None:
        super().__init__(f"clock not trusted ({quality.value}) {detail}".strip())
        self.quality = quality
        self.detail = detail


def _spin_step() -> None:
    """یک گامِ spin: os.sched_yield اگر بود، وگرنه sleepِ صفر (کمتر از یکِ ms)."""
    yielder = getattr(os, "sched_yield", None)
    if yielder is not None:
        try:
            yielder()
            return
        except OSError:
            pass
    time.sleep(0)



__all__ = ["ClockQuality", "NtpSample", "ClockState", "TimeSource", "NtpProber",
           "DispatchPlan", "DispatchTelemetry", "Scheduler", "ClockNotTrusted",
           "estimate_one_way", "percentile", "TEHRAN_UTC_OFFSET"]
