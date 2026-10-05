# -*- coding: utf-8 -*-
"""execution_latency.py — سنجشِ تأخیرِ واقعیِ مسیر، فاز‌به‌فاز.

مرجعِ طراحی: docs/execution/SARKHATI-ARCHITECTURE.md §۷-ج و §۹-د. دو چیز از آن‌جا
اینجا وارد شده:

۱) مرجع به **ریشۀِ میزبان** `HEAD` می‌زد و آن را تأخیرِ مسیرِ سفارش می‌خواند.
   اینجا فازها جدا اندازه گرفته می‌شوند (DNS / TCP / TLS / TTFB) و هر فاز
   گزارش می‌شود، پس «تأخیرِ مسیرِ سفارش» با «تأخیرِ یکِ ریشه‌یِ بی‌ربط» قاطی
   نمی‌شود.

۲) مرجع `jitter` را حساب می‌کرد و هیچ‌جا مصرف نمی‌کرد. اینجا خروجی یک
   `LatencyReport` است که `usable_for_planning` دارد: اگر نمونه‌ها کم بودند یا
   پراکندگی از حد بیشتر، برآوردِ یک‌طرفه برایِ زمان‌بندی **قابلِ استفاده
   نیست** و `Scheduler` باید همان `ClockNotTrusted`-وار رفتار کند.

ریاضِ صدک و یک‌طرفه از `execution_timing` **وارد** می‌شود، نه از نو نوشته —
دو منبعِ حقیقت برایِ یکِ عدد نداریم (§۲ دستورِ کارِ قبلی: «judge موازی» ممنوع).

هیچ نشانیِ کارگزاری درِ این فایل نیست؛ هر آدرسی که مصرف‌کننده بدهد اندازه
گرفته می‌شود. آزمون‌ها رویِ یک سرورِ HTTP محلی می‌چرخند.
"""
from __future__ import annotations

import socket
import ssl
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from execution_timing import estimate_one_way, percentile

DEFAULT_PORTS = {"http": 80, "https": 443}


@dataclass(frozen=True)
class PhaseSample:
    """یک نمونهٔ کامل. None یعنی آن فاز انجام نشد (مثلاً HTTP بی‌TLS)."""
    dns_ms: float | None
    tcp_ms: float | None
    tls_ms: float | None
    ttfb_ms: float | None
    total_ms: float
    error: str = ""


@dataclass(frozen=True)
class LatencyReport:
    target: str
    samples: tuple[PhaseSample, ...]
    dropped: tuple[str, ...] = ()
    rtt_ms: tuple[float, ...] = ()

    @property
    def n(self) -> int:
        return len(self.rtt_ms)

    def stat(self, p: str) -> float | None:
        if not self.rtt_ms:
            return None
        if p == "min":
            return min(self.rtt_ms)
        if p == "max":
            return max(self.rtt_ms)
        return percentile(self.rtt_ms, float(p[1:]))

    @property
    def jitter_ms(self) -> float | None:
        """p90 − p50؛ همان تعریفِ مرجع، ولی این‌جا مصرف می‌شود."""
        p90, p50 = self.stat("p90"), self.stat("p50")
        return None if p90 is None or p50 is None else round(p90 - p50, 3)

    def usable_for_planning(self, min_samples: int = 3,
                            max_spread_ms: float = 150.0) -> bool:
        if self.n < min_samples:
            return False
        spread = max(self.rtt_ms) - min(self.rtt_ms)
        return spread <= max_spread_ms


class LatencyProber:
    """فازها را جدا می‌سنجد. `scheme=http` ⇒ بی‌TLS؛ `https` ⇒ کامل."""

    def __init__(self, target: str, *, timeout_s: float = 2.0,
                 path: str = "/", host_header: str | None = None,
                 verify_tls: bool = False) -> None:
        u = urlsplit(target if "://" in target else "https://" + target)
        self.scheme = u.scheme or "https"
        self.host = u.hostname or ""
        self.port = u.port or DEFAULT_PORTS.get(self.scheme, 443)
        self.path = u.path or path
        self.host_header = host_header or self.host
        self.timeout_s = timeout_s
        self.verify_tls = verify_tls

    def sample(self) -> PhaseSample:
        t0 = time.perf_counter()
        dns_ms = tcp_ms = tls_ms = ttfb_ms = None
        try:
            a = time.perf_counter()
            infos = socket.getaddrinfo(self.host, self.port, 0, socket.SOCK_STREAM)
            dns_ms = (time.perf_counter() - a) * 1000.0
            family, socktype, proto, _canon, addr = infos[0]

            a = time.perf_counter()
            sock = socket.socket(family, socktype, proto)
            sock.settimeout(self.timeout_s)
            sock.connect(addr)
            tcp_ms = (time.perf_counter() - a) * 1000.0

            if self.scheme == "https":
                a = time.perf_counter()
                ctx = ssl.create_default_context()
                if not self.verify_tls:
                    # سنجشِ تأخیر، نه اعتبارِ گواهی: بررسیِ زنجیره بی‌rootِ
                    # به‌روز رویِ همهٔ ماشین‌ها ممکن نیست و خطایِ تأخیر می‌شود
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                sock = ctx.wrap_socket(sock, server_hostname=self.host)
                tls_ms = (time.perf_counter() - a) * 1000.0

            a = time.perf_counter()
            req = (f"HEAD {self.path} HTTP/1.1\r\nHost: {self.host_header}\r\n"
                   "User-Agent: bors-latency-probe\r\nConnection: keep-alive\r\n"
                   "Accept-Encoding: identity\r\n\r\n")
            sock.sendall(req.encode("ascii"))
            head = sock.recv(1)
            while head and head != b"\n":
                head = sock.recv(1)
            ttfb_ms = (time.perf_counter() - a) * 1000.0
            sock.close()
        except Exception as e:                                # noqa: BLE002
            return PhaseSample(dns_ms, tcp_ms, tls_ms, ttfb_ms,
                               (time.perf_counter() - t0) * 1000.0,
                               error=type(e).__name__)
        total = (time.perf_counter() - t0) * 1000.0
        return PhaseSample(dns_ms, tcp_ms, tls_ms, ttfb_ms, total)


def measure(target: str, *, samples: int = 10, warmup: int = 2,
            max_rtt_ms: float = 1000.0, path: str = "/",
            **kw) -> LatencyReport:
    """`warmup` نمونه اول دور ریخته می‌شود (اتصالِ سرد ≠ حالتِ پایدار) و
    نمونه‌هایِ بالاتر از `max_rtt_ms` به‌عنوانِ پرت حذف می‌شوند — هر دو مثلِ
    مرجع، ولی این‌جا *گزارش* هم می‌شوند (`dropped`)."""
    prober = LatencyProber(target, path=path, **kw)
    got: list[PhaseSample] = []
    dropped: list[str] = []
    for i in range(max(1, samples + warmup)):
        s = prober.sample()
        tag = f"#{i} {s.error or f'{s.total_ms:.1f}ms'}"
        if s.error:
            dropped.append("error " + tag)
            continue
        if i < warmup:
            dropped.append("warmup " + tag)
            continue
        if s.total_ms > max_rtt_ms:
            dropped.append("outlier " + tag)
            continue
        got.append(s)
    return LatencyReport(target=target, samples=tuple(got),
                         dropped=tuple(dropped),
                         rtt_ms=tuple(round(s.total_ms, 3) for s in got))


def one_way_from(report: LatencyReport, estimator: str = "p50") -> float | None:
    """برآوردِ یک‌طرفه برایِ `Scheduler.plan(one_way_ms=...)`.

    بی‌گزارشِ قابلِ اتکا `None` می‌دهد — صفر نه. صفر یعنی «بدونِ پیش‌دستی
    بفرست» و رویِ زمانِ بازگشایی، یعنی دیر رسیدن.
    """
    if not report.rtt_ms or not report.usable_for_planning():
        return None
    return estimate_one_way(report.rtt_ms, estimator)


__all__ = ["PhaseSample", "LatencyReport", "LatencyProber", "measure",
           "one_way_from"]
