#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Versioned contract for the Round 32A Rahavard reference pack.

Every record in the pack carries `schema` so a consumer can reject a file it
does not understand.  Fields that the source could not supply are *named*
inside `unavailable` and never guessed; a record is either measured or it is
explicitly marked as not measured.

Record schemas
--------------
  ra365-reference-bar/1        one OHLCV bar, one side (raw or adjusted)
  ra365-factor-segment/1       one interval over which one effective ratio holds
  ra365-mismatch/1             one paired date that failed, keyed for lookup
  ra365-reference-coverage/1   per-series row counts and status
  ra365-reference-pack/1       the manifest

Stdlib only: this package is imported by tools that must run with the pinned
interpreter without extra wheels.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import unicodedata

SCHEMA_BAR = "ra365-reference-bar/1"
SCHEMA_SEGMENT = "ra365-factor-segment/1"
SCHEMA_MISMATCH = "ra365-mismatch/1"
SCHEMA_COVERAGE = "ra365-reference-coverage/1"
SCHEMA_MANIFEST = "ra365-reference-pack/1"

PACK_DIRNAME = "reference-pack"

#: Nikud and Arabic presentation forms are stripped before joining symbols.
_ARABIC_TO_PERSIAN = {
    "\u0643": "\u06a9",  # ARABIC KAF -> PERSIAN KEHEH
    "\u064a": "\u06cc",  # ARABIC YEH -> PERSIAN YEH
    "\u0649": "\u06cc",  # ALEF MAKSURA -> PERSIAN YEH
    "\u0629": "\u0647",  # TEH MARBUTA -> HEH
}
_ZW = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u200e\u200f\ufeff"), None)

TIMEFRAMES = ("D", "W", "M")
ADJUST_MODES = ("raw", "adjusted")
PRICE_BASES = ("last", "closing", "real_close", "official", "unknown")

_LOWER = {t.lower(): t for t in TIMEFRAMES}
_ADJUST_ALIASES = {
    "raw": "raw",
    "": "raw",
    "none": "raw",
    "unadjusted": "raw",
    "type0": "raw",
    "bedoon": "raw",
    "\u0628\u062f\u0648\u0646": "raw",  # without (adjustment)
    "adjusted": "adjusted",
    "adj": "adjusted",
    "type7": "adjusted",
    "amali": "adjusted",
    "\u0639\u0645\u0644\u06a9\u0631\u062f\u06cc": "adjusted",
    "\u0639\u0645\u0644\u06cc": "adjusted",
}
_BASIS_ALIASES = {
    "last": "last",
    "\u0622\u062e\u0631\u06cc\u0646": "last",
    "closing": "closing",
    "close": "closing",
    "\u067e\u0627\u06cc\u0627\u0646\u06cc": "closing",
    "real_close": "real_close",
    "official": "official",
}

REQUIRED_BAR = ("symbol_id", "timeframe", "date", "adjust", "source_id")
REQUIRED_SEGMENT = ("symbol_id", "timeframe", "segment_index", "date_from", "date_to")
REQUIRED_MISMATCH = ("symbol_id", "timeframe", "date", "price_basis", "cause")

#: What backs a factor segment.  `series` means the two OHLC series were
#: replayed session by session; `step-boundary` means only a frozen boundary
#: observation survived and the sessions inside the interval are not known.
EVIDENCE_KINDS = ("series", "step-boundary")

#: How a breakpoint was tied to a corporate event.  A ratio break is a
#: computational witness, never by itself an event date.
EVENT_ATTRIBUTION = ("independent", "inferential", "unattributed")


class SchemaError(ValueError):
    """A record does not satisfy the frozen contract."""


def normalize_symbol(name):
    """Canonical join key for a symbol label (R26 parity contract, section 2)."""
    if name is None:
        return ""
    s = unicodedata.normalize("NFC", str(name)).translate(_ZW).strip()
    s = "".join(_ARABIC_TO_PERSIAN.get(ch, ch) for ch in s)
    return re.sub(r"\s+", " ", s)


def normalize_timeframe(tf):
    if tf is None:
        raise SchemaError("timeframe is required")
    s = str(tf).strip()
    if s in _LOWER:
        return _LOWER[s]
    if s in TIMEFRAMES:
        return s
    raise SchemaError("unknown timeframe: %r" % (tf,))


def normalize_adjust(value):
    s = "" if value is None else str(value).strip().lower()
    if s in _ADJUST_ALIASES:
        return _ADJUST_ALIASES[s]
    raise SchemaError("unknown adjust mode: %r" % (value,))


def normalize_basis(value):
    s = "" if value is None else str(value).strip().lower()
    if s in _BASIS_ALIASES:
        return _BASIS_ALIASES[s]
    return "unknown"


def normalize_date(value):
    """Accept YYYY-MM-DD, YYYY/MM/DD, ISO timestamps and epoch seconds."""
    if value is None:
        raise SchemaError("date is required")
    s = str(value).strip()
    if not s:
        raise SchemaError("date is empty")
    if re.fullmatch(r"-?\d+(\.\d+)?", s):
        n = float(s)
        if n > 1e11:
            n /= 1000.0
        try:
            return _dt.datetime.fromtimestamp(n, _dt.timezone.utc).strftime("%Y-%m-%d")
        except (OverflowError, OSError, ValueError) as exc:
            raise SchemaError("epoch out of range: %r" % (value,)) from exc
    m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if not m:
        raise SchemaError("unrecognised date: %r" % (value,))
    y, mo, d = (int(g) for g in m.groups())
    return "%04d-%02d-%02d" % (y, mo, d)


def normalize_number(value):
    """float or None; NaN/inf collapse to None (a present but unusable value)."""
    if value is None or value == "":
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return v


def now_utc():
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def mismatch_key(symbol_id, timeframe, date, price_basis):
    """Stable lookup key: symbol_id + timeframe + date + price_basis."""
    return "|".join((str(symbol_id), normalize_timeframe(timeframe),
                     normalize_date(date), normalize_basis(price_basis)))


def canonical_json(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def row_hash(obj):
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def validate(record, schema, partial=False):
    """Return a list of contract violations (empty means the record is valid)."""
    errs = []
    if not isinstance(record, dict):
        return ["record is not an object"]
    got = record.get("schema")
    if got != schema:
        errs.append("schema mismatch: expected %s got %r" % (schema, got))
    required = {
        SCHEMA_BAR: REQUIRED_BAR,
        SCHEMA_SEGMENT: REQUIRED_SEGMENT,
        SCHEMA_MISMATCH: REQUIRED_MISMATCH,
    }.get(schema, ())
    for field in required:
        if record.get(field) is None:
            errs.append("missing required field %r" % (field,))
    if schema == SCHEMA_BAR:
        if record.get("adjust") not in ADJUST_MODES:
            errs.append("adjust out of vocabulary: %r" % (record.get("adjust"),))
        if record.get("timeframe") not in TIMEFRAMES:
            errs.append("timeframe out of vocabulary: %r" % (record.get("timeframe"),))
        for field in ("open", "high", "low", "close", "volume"):
            if field not in record and not partial:
                errs.append("bar without field %r (use unavailable=)" % (field,))
        missing = record.get("unavailable") or []
        if not isinstance(missing, list):
            errs.append("unavailable must be a list")
        for field in ("open", "high", "low", "close", "volume"):
            if record.get(field) is None and field not in (missing or []):
                errs.append("bar field %r is null but not listed in unavailable" % (field,))
    if schema == SCHEMA_SEGMENT:
        ev = record.get("evidence")
        if not isinstance(ev, dict):
            errs.append("segment without an evidence object")
        else:
            if ev.get("evidence_kind") not in EVIDENCE_KINDS:
                errs.append("evidence_kind out of vocabulary: %r" % (ev.get("evidence_kind"),))
            if "n_sessions" not in ev:
                errs.append("evidence without n_sessions (use null when unknown)")
        if record.get("event_attribution") not in EVENT_ATTRIBUTION:
            errs.append("event_attribution out of vocabulary: %r"
                        % (record.get("event_attribution"),))
        if record.get("factor") is None and "factor" not in (record.get("unavailable") or []):
            errs.append("segment without factor must list 'factor' in unavailable")
    if schema == SCHEMA_MISMATCH:
        want = mismatch_key(record.get("symbol_id"), record.get("timeframe"),
                            record.get("date"), record.get("price_basis"))
        if record.get("key") and record["key"] != want:
            errs.append("key %r does not match the stable key %r" % (record["key"], want))
    return errs


def assert_valid(record, schema, partial=False):
    errs = validate(record, schema, partial=partial)
    if errs:
        raise SchemaError("; ".join(errs))
    return record


def fa_digits(text):
    """Render ASCII digits as Persian digits without hand-typing them.

    Hand-typed Persian numerals lose digits in this repository; build them from
    codepoints instead (AGENTS.md).
    """
    return "".join(chr(0x06F0 + ord(ch) - 0x30) if "0" <= ch <= "9" else ch
                   for ch in str(text))