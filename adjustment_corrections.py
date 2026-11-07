# -*- coding: utf-8 -*-
"""adjustment_corrections.py — لایهٔ تصحیحِ نسخه‌دار برای زنجیرهٔ تعدیل و OHLC خام.

این ماژول یک بستهٔ قابل‌ممیزی می‌خواند (نه یک سری خام):

  • `factors.jsonl` — قطعه‌های سطح‌رویداد:
      replace_step: همهٔ رویدادهای محصول در `effective_date` حذف و یک گام با
                    `ratio` مرجع جایگزین می‌شود.
      suppress_step: همهٔ رویدادهای محصول در `effective_date` حذف می‌شود.
  • `raw_ohlc.jsonl` — تصحیح‌های پراکندهٔ فیلد خام (open/high/low/close/last)
    برای تاریخ‌هایی که کندل خام محصول با نوار type0 مرجع تفاوت دارد.

هر دو فایل `ref_bars_sha256`، `correction_version`، `created_at`،
`source`/`method`، `confidence` و دلیل را حمل می‌کنند. این ماژول بی‌شبکه و
بی‌دیتابیس است و در نبودِ بسته، no-op است (تست‌ها و نصب تازه نمی‌شکنند).

حالت‌ها:
  • `overlay` (پیش‌فرض): فقط گام‌های ناهمخوان/گم‌شده اصلاح می‌شوند.
  • `authoritative`: برای نمادهای پوشش‌داده‌شده، زنجیرهٔ عامل فقط از گام‌های
    بسته ساخته می‌شود (همهٔ رویدادهای دیگر محصول حذف می‌شوند). این حالت برای
    بسته‌های factor-segment تولیدشده توسط ابزار مستقل (Round32A) است.

ترتیب اعمال در `api/chart.py`: پس از کشف/ادغام/تیزکردن رویدادها و پیش از
`AE.chain_factors`؛ تصحیح خام فقط روی کندل نمایشی و پس از محاسبهٔ عامل.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading

ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_VERSION = "ra365-r32b-v2"
DEFAULT_DIR = os.path.join(ROOT, "data", "ra365_corrections", DEFAULT_VERSION)
KNOWN_SCHEMAS = ("ra365-correction-pack-v1", "ra365-reference-pack-v1")
FACTOR_ACTIONS = ("replace_step", "suppress_step")
RAW_FIELDS = ("open", "high_raw", "high", "low_raw", "low", "close", "last")


class CorrectionPackError(RuntimeError):
    pass


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_jsonl(path):
    rows = []
    if not path or not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _as_float(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def _normalize_factor_row(r, version, source, method, ref_sha, created_at):
    ins = str(r.get("ins_code") or r.get("instrument_code") or "").strip()
    symbol = str(r.get("symbol") or "").strip()
    date = str(r.get("effective_date") or r.get("date") or "")[:10]
    action = str(r.get("action") or "replace_step").strip()
    if action not in FACTOR_ACTIONS:
        action = "replace_step"
    ratio = _as_float(r.get("ratio", r.get("target_ratio", r.get("factor"))))
    if not date or (action == "replace_step" and (ratio is None or ratio <= 0)):
        return None
    return {
        "ins_code": ins,
        "symbol": symbol,
        "action": action,
        "effective_date": date,
        "ratio": ratio,
        "class": r.get("class") or "",
        "event_sig": r.get("event_sig") or "",
        "confidence": r.get("confidence") or "",
        "fields_used": r.get("fields_used") or "",
        "samples": r.get("samples"),
        "max_field_dev": r.get("max_field_dev"),
        "prod_ratio": r.get("prod_ratio"),
        "ref_ratio": r.get("ref_ratio"),
        "source": r.get("source") or source,
        "method": r.get("method") or method,
        "ref_bars_sha256": r.get("ref_bars_sha256") or ref_sha,
        "correction_version": r.get("correction_version") or version,
        "created_at": r.get("created_at") or created_at,
        "reason": r.get("reason") or "",
    }


def _normalize_raw_row(r, version, source, method, ref_sha, created_at):
    ins = str(r.get("ins_code") or r.get("instrument_code") or "").strip()
    symbol = str(r.get("symbol") or "").strip()
    date = str(r.get("date") or r.get("effective_date") or "")[:10]
    field = str(r.get("field") or "").strip()
    value = _as_float(r.get("reference_value", r.get("value")))
    if not date or field not in RAW_FIELDS or value is None:
        return None
    return {
        "ins_code": ins,
        "symbol": symbol,
        "date": date,
        "field": field,
        "value": value,
        "product_value": r.get("product_value"),
        "abs_diff": r.get("abs_diff"),
        "source": r.get("source") or source,
        "method": r.get("method") or method,
        "confidence": r.get("confidence") or "",
        "ref_bars_sha256": r.get("ref_bars_sha256") or ref_sha,
        "correction_version": r.get("correction_version") or version,
        "created_at": r.get("created_at") or created_at,
        "reason": r.get("reason") or "",
    }


class Pack:
    def __init__(self, directory):
        self.directory = directory
        mpath = os.path.join(directory, "manifest.json")
        if not os.path.exists(mpath):
            raise CorrectionPackError("manifest missing: %s" % mpath)
        with open(mpath, encoding="utf-8") as fh:
            self.manifest = json.load(fh)
        schema = self.manifest.get("schema")
        if schema not in KNOWN_SCHEMAS:
            raise CorrectionPackError("unsupported correction schema: %r" % schema)
        self.version = self.manifest.get("correction_version") or DEFAULT_VERSION
        self.created_at = self.manifest.get("created_at") or ""
        self.ref_sha = self.manifest.get("reference_sha256") or ""
        self.mode = self.manifest.get("mode") or "overlay"
        if self.mode not in ("overlay", "authoritative"):
            self.mode = "overlay"
        source = self.manifest.get("source") or ""
        method = self.manifest.get("method") or ""
        files = self.manifest.get("files") or {}
        fpath = files.get("factors") or self.manifest.get("factors") or "factors.jsonl"
        rpath = files.get("raw_ohlc") or self.manifest.get("raw_ohlc") or "raw_ohlc.jsonl"
        if not os.path.isabs(fpath):
            fpath = os.path.join(directory, fpath)
        if not os.path.isabs(rpath):
            rpath = os.path.join(directory, rpath)
        self.factor_path = fpath
        self.raw_path = rpath
        expected = self.manifest.get("file_sha256") or {}
        for key, path in (("factors", fpath), ("raw_ohlc", rpath)):
            if path and os.path.exists(path) and expected.get(key):
                got = _sha256(path)
                if got != expected[key]:
                    raise CorrectionPackError(
                        "correction file hash mismatch: %s (%s != %s)"
                        % (path, got, expected[key]))
        self.factors = []
        for r in _read_jsonl(fpath):
            row = _normalize_factor_row(r, self.version, source, method,
                                        self.ref_sha, self.created_at)
            if row:
                self.factors.append(row)
        self.raws = []
        for r in _read_jsonl(rpath):
            row = _normalize_raw_row(r, self.version, source, method,
                                     self.ref_sha, self.created_at)
            if row:
                self.raws.append(row)
        self.factor_by_ins = {}
        self.factor_by_symbol = {}
        self.raw_by_ins = {}
        self.raw_by_symbol = {}
        self.ambiguous_symbols = set()
        symbol_ins = {}
        for r in self.factors:
            if r["ins_code"]:
                self.factor_by_ins.setdefault(r["ins_code"], []).append(r)
            if r["symbol"]:
                symbol_ins.setdefault(r["symbol"], set()).add(r["ins_code"])
                self.factor_by_symbol.setdefault(r["symbol"], []).append(r)
        for r in self.raws:
            if r["ins_code"]:
                self.raw_by_ins.setdefault(r["ins_code"], []).append(r)
            if r["symbol"]:
                symbol_ins.setdefault(r["symbol"], set()).add(r["ins_code"])
                self.raw_by_symbol.setdefault(r["symbol"], []).append(r)
        self.ambiguous_symbols = {s for s, ins in symbol_ins.items()
                                  if len({x for x in ins if x}) > 1}
        for s in self.ambiguous_symbols:
            self.factor_by_symbol.pop(s, None)
            self.raw_by_symbol.pop(s, None)
        self.factor_index = {}
        self.suppress_index = {}
        for ins, rows in self.factor_by_ins.items():
            self._index_factor(ins, rows)
        for sym, rows in self.factor_by_symbol.items():
            self._index_factor(sym, rows)
        self.raw_index = {}
        for ins, rows in self.raw_by_ins.items():
            self._index_raw(ins, rows)
        for sym, rows in self.raw_by_symbol.items():
            self._index_raw(sym, rows)
        self.covered_ins = set(self.factor_by_ins)
        self.covered_symbols = set(self.factor_by_symbol)
        # آخرین تاریخِ پوششِ بسته.  بستهٔ authoritative فقط تا همین تاریخ
        # معتبر است؛ رویدادِ شرکتیِ بعد از آن نباید حذف شود (بستهٔ منجمد
        # نمی‌تواند رویدادِ آینده را بداند).
        dates = [r["effective_date"] for r in self.factors]
        self.as_of = max(dates) if dates else ""

    def _index_factor(self, key, rows):
        rep = {}
        sup = set()
        for r in rows:
            if r["action"] == "replace_step":
                rep[r["effective_date"]] = r
            elif r["action"] == "suppress_step":
                sup.add(r["effective_date"])
        self.factor_index[key] = rep
        self.suppress_index[key] = sup

    def _index_raw(self, key, rows):
        self.raw_index[key] = {(r["date"], r["field"]): r for r in rows}

    def key(self, symbol=None, ins_code=None):
        ins = str(ins_code or "").strip()
        if ins:
            # A known instrument identity is authoritative.  Never fall back
            # to the display name: a test fixture may reuse a real symbol.
            return ins if (ins in self.factor_by_ins or ins in self.raw_by_ins) else None
        sym = str(symbol or "").strip()
        if sym and sym in self.factor_by_symbol:
            return sym
        if sym and sym in self.raw_by_symbol:
            return sym
        return None

    def factor_rows(self, symbol=None, ins_code=None):
        key = self.key(symbol, ins_code)
        if key is None:
            return {}, set(), None
        return (self.factor_index.get(key, {}), self.suppress_index.get(key, set()), key)

    def raw_rows(self, symbol=None, ins_code=None):
        key = self.key(symbol, ins_code)
        if key is None:
            return {}, None
        return self.raw_index.get(key, {}), key

    def capability(self, symbol=None, ins_code=None):
        rep, sup, key = self.factor_rows(symbol, ins_code)
        raw, _ = self.raw_rows(symbol, ins_code)
        return {
            "enabled": True,
            "version": self.version,
            "mode": self.mode,
            "directory": self.directory,
            "reference_sha256": self.ref_sha,
            "covered": key is not None,
            "as_of": self.as_of,
            "replace_steps": len(rep),
            "suppress_steps": len(sup),
            "raw_fields": len(raw),
            "ambiguous_symbol": str(symbol or "") in self.ambiguous_symbols,
            "error": None,
        }


_LOCK = threading.Lock()
_CACHE = {}


def pack_dir():
    if os.environ.get("BORS_CORRECTIONS_DISABLE", "").strip().lower() in ("1", "true", "yes", "on"):
        return None
    return os.environ.get("BORS_CORRECTIONS_DIR") or DEFAULT_DIR


def load_pack(directory=None):
    d = directory or pack_dir()
    if not d:
        return None
    if not os.path.exists(os.path.join(d, "manifest.json")):
        return None
    try:
        stamp = tuple(os.path.getmtime(os.path.join(d, f))
                      for f in ("manifest.json", "factors.jsonl", "raw_ohlc.jsonl")
                      if os.path.exists(os.path.join(d, f)))
    except OSError:
        stamp = ()
    with _LOCK:
        cached = _CACHE.get(d)
        if cached and cached[0] == stamp:
            if isinstance(cached[1], CorrectionPackError):
                raise cached[1]
            return cached[1]
        try:
            pack = Pack(d)
        except CorrectionPackError as e:
            _CACHE[d] = (stamp, e)
            raise
        _CACHE[d] = (stamp, pack)
        return pack


def get_pack():
    try:
        return load_pack()
    except CorrectionPackError:
        return None


def capability(symbol=None, ins_code=None):
    pack = get_pack()
    if pack is None:
        return {"enabled": False, "version": None, "covered": False,
                "replace_steps": 0, "suppress_steps": 0, "raw_fields": 0,
                "error": None}
    try:
        return pack.capability(symbol, ins_code)
    except CorrectionPackError as e:
        return {"enabled": False, "version": None, "covered": False,
                "replace_steps": 0, "suppress_steps": 0, "raw_fields": 0,
                "error": str(e)}


def apply_factor_events(symbol, events, ins_code=None):
    """(events, suppressed, meta) — لایهٔ عامل را روی فهرست رویدادها اعمال می‌کند.

    `suppressed` رویدادهای اصلیِ حذف‌شده است تا caller آن‌ها را با وضعیت
    `suppressed-by-correction` در `adjustRejected` نگه دارد (بی‌حذفِ خاموش).
    """
    pack = get_pack()
    if pack is None:
        return list(events or []), [], {"enabled": False}
    rep, sup, key = pack.factor_rows(symbol, ins_code)
    if key is None:
        return list(events or []), [], {"enabled": True, "covered": False,
                                        "version": pack.version, "mode": pack.mode}
    kept, suppressed = [], []
    authoritative = pack.mode == "authoritative" and bool(rep or sup)
    allowed = set(rep)
    cutoff = pack.as_of if authoritative else ""
    future_kept = 0
    for e in events or []:
        d = str(e.get("date") or "")[:10]
        if authoritative and cutoff and d > cutoff:
            # رویدادِ بعد از آخرین تاریخِ بسته: بسته از آن بی‌خبر است، پس
            # نباید حذف شود؛ زنجیره باید آن را روی گام‌های بسته سوار کند.
            kept.append(dict(e))
            future_kept += 1
            continue
        if d in rep or d in sup or (authoritative and d not in allowed):
            suppressed.append(dict(e))
            continue
        kept.append(dict(e))
    for date, r in sorted(rep.items()):
        kept.append({
            "date": date,
            "ratio": r["ratio"],
            "source": "rahavard-reference-correction",
            "correction": {
                "version": r["correction_version"],
                "class": r["class"],
                "event_sig": r["event_sig"],
                "confidence": r["confidence"],
                "fields_used": r["fields_used"],
                "samples": r["samples"],
                "max_field_dev": r["max_field_dev"],
                "prod_ratio": r["prod_ratio"],
                "ref_ratio": r["ref_ratio"],
                "source": r["source"],
                "method": r["method"],
                "ref_bars_sha256": r["ref_bars_sha256"],
                "created_at": r["created_at"],
                "reason": r["reason"],
            },
        })
    kept.sort(key=lambda e: str(e.get("date"))[:10])
    return kept, suppressed, {"enabled": True, "covered": True,
                              "version": pack.version, "mode": pack.mode,
                              "as_of": pack.as_of, "future_events_kept": future_kept,
                              "replace_steps": len(rep), "suppress_steps": len(sup)}


def apply_raw_candles(symbol, candles, ins_code=None):
    """(applied_count, meta) — تصحیح فیلدهای خام روی کندل نمایشی (in-place)."""
    pack = get_pack()
    if pack is None:
        return 0, {"enabled": False}
    raw, key = pack.raw_rows(symbol, ins_code)
    if key is None or not raw:
        return 0, {"enabled": True, "covered": key is not None, "raw_fields": 0}
    applied = 0
    for c in candles or []:
        d = str(c.get("time") or c.get("date") or "")[:10]
        for field in RAW_FIELDS:
            r = raw.get((d, field))
            if r is None:
                continue
            c[field] = r["value"]
            applied += 1
        # سایهٔ دیدنی از extremeِ literal ساخته می‌شود؛ اگر فقط خودِ literal
        # اصلاح شده باشد، کپیِ `high`/`low` باید دنبالش بیاید. اصلاحِ صریحِ
        # `high`/`low` (وقتی در بسته هست) بر این کپی اولویت دارد.
        if (d, "high_raw") in raw and (d, "high") not in raw and c.get("high_raw") is not None:
            c["high"] = c["high_raw"]
        if (d, "low_raw") in raw and (d, "low") not in raw and c.get("low_raw") is not None:
            c["low"] = c["low_raw"]
    return applied, {"enabled": True, "covered": True, "version": pack.version,
                     "raw_fields": len(raw)}


def manifest_summary():
    pack = get_pack()
    if pack is None:
        return {}
    return dict(pack.manifest)
