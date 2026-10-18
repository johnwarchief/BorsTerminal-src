"""Contract capture for the read-only portfolio work (mission 2026-10-18, stage 4).

Reads only the app's OWN endpoints on the local dev backend. Records method,
status, content-type, and the *shape* of every field (type + null-ness), never a
raw value. Nothing here talks to a broker host; the shapes come from this
machine's FastAPI process on 127.0.0.1.
"""
import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:%s" % (sys.argv[1] if len(sys.argv) > 1 else "8106")
DUMMY = "BORS-CONTRACT-PROBE-NOT-A-REAL-SESSION"


def shape(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool(%s)" % value
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string(len=%d)" % len(value)
    if isinstance(value, list):
        if not value:
            return "array(empty)"
        first = value[0]
        if isinstance(first, dict):
            return "array(%d x object{%s})" % (len(value), ",".join(sorted(first)))
        return "array(%d x %s)" % (len(value), shape(first))
    if isinstance(value, dict):
        return "object{%s}" % ",".join(sorted(value))
    return type(value).__name__


def fields(body):
    if not isinstance(body, dict):
        return {}
    return {k: shape(v) for k, v in sorted(body.items())}


def call(method, path, payload=None):
    url = BASE + path
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    rec = {"method": method, "path": path, "request_fields":
           sorted(payload) if isinstance(payload, dict) else None}
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            raw = res.read()
            rec["status"] = res.status
            rec["content_type"] = res.headers.get("content-type")
            try:
                body = json.loads(raw.decode("utf-8"))
            except ValueError:
                rec["body_kind"] = "non-json(len=%d)" % len(raw)
                return rec
            rec["body_kind"] = shape(body)
            rec["fields"] = fields(body)
            for key in ("status", "code", "error", "detail", "rows", "as_of",
                        "source", "session_proven", "applies_on_restart",
                        "secrets_stored", "live", "adapter"):
                if isinstance(body, dict) and key in body:
                    rec.setdefault("notable", {})[key] = (
                        body[key] if isinstance(body[key], (bool, type(None), int, float))
                        else (DUMMY not in str(body[key]) and str(body[key])[:120]))
            return rec
    except urllib.error.HTTPError as e:
        rec["status"] = e.code
        rec["content_type"] = e.headers.get("content-type")
        rec["error_body_kind"] = "non-json"
        return rec
    except Exception as e:  # noqa: BLE001
        rec["status"] = "transport-error"
        rec["error"] = "%s: %s" % (type(e).__name__, str(e)[:120])
        return rec


out = {"base": BASE, "records": [
    call("GET", "/api/execution/status"),
    call("GET", "/api/execution/config"),
    call("GET", "/api/execution/portfolio"),
    call("GET", "/api/execution/connect"),
    call("POST", "/api/execution/session", {"token": DUMMY}),
    call("GET", "/api/execution/portfolio"),
    call("DELETE", "/api/execution/session"),
    # هیچ POST /config اینجا نیست: آن نوشتن رویِ دیسک می‌نشیند و این سنجش فقط
    # باید شکلِ پاسخ را ببینَد، نه وضعِ پروسۀ دیگری را عوض کند.
    call("GET", "/api/execution/portfolio"),
]}
print(json.dumps(out, ensure_ascii=False, indent=1))
