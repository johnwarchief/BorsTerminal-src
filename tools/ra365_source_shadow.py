#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 27: isolated shadow source-mode prototype (NOT wired to production).

Defines how TSETMC-primary, Rahavard-primary and dual-source modes would
select a raw series, with explicit provenance and a hard no-mixing rule:
a series is served by exactly one source. Dual mode is *per series*, not per
field: TSETMC when it has data, otherwise Rahavard, and the choice is recorded.
Missing on both sides is `UNAVAILABLE`, never a silent fallback.

Nothing here changes the chart path; it exists to measure and review the
architecture before any production decision.
"""
from dataclasses import dataclass, field

MODES = ("tsetmc", "rahavard", "dual")


class SourceMixError(ValueError):
    pass


@dataclass
class SourceSeries:
    symbol: str
    source: str
    bars: list
    provenance: dict = field(default_factory=dict)

    def __post_init__(self):
        sources = {b.get("source") for b in self.bars if isinstance(b, dict)}
        if len(sources) > 1 or (sources and self.source not in sources):
            raise SourceMixError("a series must come from exactly one source: %r" % sources)


def select_series_source(symbol, mode, tsetmc_bars, ref_bars,
                         tsetmc_snapshot=None, ref_snapshot=None):
    """Return a SourceSeries or raise LookupError when no source has data."""
    if mode not in MODES:
        raise ValueError("unknown source mode: %r" % mode)
    tsetmc_bars = list(tsetmc_bars or [])
    ref_bars = list(ref_bars or [])
    if mode == "tsetmc":
        if not tsetmc_bars:
            raise LookupError("UNAVAILABLE: tsetmc has no bars for %s" % symbol)
        src, bars, snap, policy = "tsetmc", tsetmc_bars, tsetmc_snapshot, "tsetmc_primary"
    elif mode == "rahavard":
        if not ref_bars:
            raise LookupError("UNAVAILABLE: rahavard has no bars for %s" % symbol)
        src, bars, snap, policy = "rahavard", ref_bars, ref_snapshot, "rahavard_primary"
    else:
        if tsetmc_bars:
            src, bars, snap, policy = "tsetmc", tsetmc_bars, tsetmc_snapshot, "dual_per_series_tsetmc"
        elif ref_bars:
            src, bars, snap, policy = "rahavard", ref_bars, ref_snapshot, "dual_per_series_rahavard"
        else:
            raise LookupError("UNAVAILABLE: neither source has bars for %s" % symbol)
    tagged = [dict(b, source=src) for b in bars]
    return SourceSeries(symbol=symbol, source=src, bars=tagged,
                        provenance={"mode": mode, "source": src,
                                    "snapshot": snap, "policy": policy,
                                    "mixed": False})


def compare_sources(tsetmc_bars, ref_bars):
    """Coverage/overlap of the two sources for the shadow report (read-only)."""
    t = {b["date"]: b for b in (tsetmc_bars or [])}
    r = {b["date"]: b for b in (ref_bars or [])}
    common = set(t) & set(r)
    diffs = 0
    for d in common:
        for f in ("open", "high", "low", "close"):
            if t[d].get(f) != r[d].get(f):
                diffs += 1
                break
    return {"tsetmc_rows": len(t), "rahavard_rows": len(r),
            "common_rows": len(common), "tsetmc_only": len(set(t) - common),
            "rahavard_only": len(set(r) - common),
            "rows_with_field_difference": diffs}
