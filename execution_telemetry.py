# -*- coding: utf-8 -*-
"""execution_telemetry.py — تلمتریِ مشترکِ API/Browser/Scheduler برایِ سرخطی.

هیچ شبکه‌ای اینجا نیست. قواعد:
  • فاصله‌هایِ درون‌فرایندی از monotonic (ms) محاسبه می‌شوند.
  • زمان‌هایِ دیواری فقط برایِ مقایسهٔ بینِ سیستم‌ها/نمایش‌اند و منبعشان صریح است.
  • هر عددی که شاهد ندارد `None` می‌ماند؛ صفرِ آرایشی ساخته نمی‌شود.
  • `request_rtt_ms` فقط از (request_started_mono, response_received_mono) می‌آید؛
    هیچ `one_way_ms` از تقسیمِ RTT بر ۲ ساخته نمی‌شود.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

TELEMETRY_FIELDS = (
    "intent_created_wall_ms",
    "preflight_started_mono_ms", "preflight_completed_mono_ms",
    "scheduled_target_wall_ms", "scheduled_target_mono_ms",
    "execution_start_mono_ms", "execution_start_wall_ms",
    "send_started_mono_ms", "send_started_wall_ms",
    "browser_click_started_mono_ms",
    "request_started_mono_ms", "request_started_wall_ms",
    "response_received_mono_ms", "response_received_wall_ms",
    "broker_acknowledged_mono_ms", "broker_acknowledged_wall_ms",
    "order_id_observed_mono_ms", "order_id_observed_wall_ms",
    "queue_position_observed_mono_ms", "queue_position_observed_wall_ms",
    "first_fill_mono_ms", "first_fill_wall_ms",
    "clock_offset_ms", "clock_quality",
)

METRIC_FIELDS = (
    "preflight_ms", "scheduler_lag_ms", "click_to_request_ms",
    "request_rtt_ms", "response_to_order_id_ms", "order_id_to_queue_ms",
    "target_error_ms", "execution_to_request_ms",
)


def _diff(a: float | int | None, b: float | int | None) -> float | None:
    if a is None or b is None:
        return None
    return round(float(b) - float(a), 3)


@dataclass
class ExecutionTelemetry:
    intent_created_wall_ms: int | None = None
    preflight_started_mono_ms: float | None = None
    preflight_completed_mono_ms: float | None = None
    scheduled_target_wall_ms: int | None = None
    scheduled_target_mono_ms: float | None = None
    execution_start_mono_ms: float | None = None
    execution_start_wall_ms: int | None = None
    #: لحظهٔ actual send (پس از انتظارِ scheduler)؛ جدا از execution_start.
    send_started_mono_ms: float | None = None
    send_started_wall_ms: int | None = None
    browser_click_started_mono_ms: float | None = None
    request_started_mono_ms: float | None = None
    request_started_wall_ms: int | None = None
    response_received_mono_ms: float | None = None
    response_received_wall_ms: int | None = None
    broker_acknowledged_mono_ms: float | None = None
    broker_acknowledged_wall_ms: int | None = None
    order_id_observed_mono_ms: float | None = None
    order_id_observed_wall_ms: int | None = None
    queue_position_observed_mono_ms: float | None = None
    queue_position_observed_wall_ms: int | None = None
    first_fill_mono_ms: float | None = None
    first_fill_wall_ms: int | None = None
    clock_offset_ms: float | None = None
    clock_quality: str = "unavailable"
    sources: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def latencies(self) -> dict[str, float | None]:
        """معیارهایِ استاندارد؛ هر کدام فقط با شاهدِ زمانیِ خودش."""
        return {
            "preflight_ms": _diff(self.preflight_started_mono_ms,
                                  self.preflight_completed_mono_ms),
            "scheduler_lag_ms": _diff(self.scheduled_target_mono_ms,
                                      self.send_started_mono_ms),
            "click_to_request_ms": _diff(self.browser_click_started_mono_ms,
                                         self.request_started_mono_ms),
            "request_rtt_ms": _diff(self.request_started_mono_ms,
                                    self.response_received_mono_ms),
            "response_to_order_id_ms": _diff(self.response_received_mono_ms,
                                             self.order_id_observed_mono_ms),
            "order_id_to_queue_ms": _diff(self.order_id_observed_mono_ms,
                                          self.queue_position_observed_mono_ms),
            "target_error_ms": _diff(self.scheduled_target_wall_ms,
                                     self.send_started_wall_ms),
            "execution_to_request_ms": _diff(self.execution_start_mono_ms,
                                             self.request_started_mono_ms),
        }

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["latencies"] = self.latencies()
        out["timezone"] = "Asia/Tehran (fixed +03:30)"
        out["precision"] = "ms"
        out["one_way_ms"] = None
        out["one_way_reason"] = "RTT/2 is not a one-way measurement"
        out["metric_sources"] = {
            "preflight_ms": "monotonic",
            "scheduler_lag_ms": "monotonic (target anchor to actual send)",
            "click_to_request_ms": "monotonic",
            "request_rtt_ms": "monotonic",
            "response_to_order_id_ms": "monotonic",
            "order_id_to_queue_ms": "monotonic",
            "target_error_ms": "wall (cross-system; clock offset uncertainty applies)",
            "execution_to_request_ms": "monotonic",
        }
        return out

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "ExecutionTelemetry":
        src = dict(data or {})
        kwargs = {k: src[k] for k in TELEMETRY_FIELDS if k in src}
        if "sources" in src and isinstance(src["sources"], Mapping):
            kwargs["sources"] = {str(k): str(v) for k, v in src["sources"].items()}
        if "notes" in src and isinstance(src["notes"], list):
            kwargs["notes"] = [str(x) for x in src["notes"]]
        return cls(**kwargs)


__all__ = ["ExecutionTelemetry", "TELEMETRY_FIELDS", "METRIC_FIELDS"]
