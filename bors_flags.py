"""bors_flags.py -- optional-dependency bootstrap.

Split verbatim out of app.py. Keeps the orjson / notifier probes in one
place so api/*.py can import the resulting flags without importing app.
"""
try:
    import orjson as _orjson_mod  # noqa: F401 — کلاس ORJSONResponse بدون orjson import میشود ولی در render میترکد
    from fastapi.responses import ORJSONResponse
    _ORJ = True
except Exception:
    ORJSONResponse = None
    _ORJ = False

# ---------- Notification Dispatcher (Telegram + Bale) ----------
try:
    import notifier
    NOTIFIER_AVAILABLE = True
except Exception as _e:
    # httpx نصب نباشد یا فایل ناقص باشد — اپ نباید کرش کند
    NOTIFIER_AVAILABLE = False
    print(f"[notifier] unavailable: {_e}")
