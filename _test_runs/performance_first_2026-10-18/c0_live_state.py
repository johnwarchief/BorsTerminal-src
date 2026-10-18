# C0: یک GETِ فقط‌خواندنی به هر مسیر رویِ دو بک‌اندِ زندهٔ دیگران (:8000 مالِ System 1، :8010 مالِ uiux-2-0). بی‌polling، بی‌POST.
import datetime
import json
import os
import subprocess
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PATHS = ["/api/update/version", "/api/mstat/phase", "/api/market/sync-state", "/api/sync/status", "/api/execution/status"]


def get(port, path):
    t0 = time.time()
    try:
        r = urllib.request.urlopen("http://127.0.0.1:%d%s" % (port, path), timeout=20)
        body = r.read()
        ct = r.headers.get("content-type", "")
        st = r.status
    except urllib.error.HTTPError as e:
        body, ct, st = e.read(), e.headers.get("content-type", ""), e.code
    except Exception as e:
        return {"error": repr(e)[:200], "ms": round((time.time() - t0) * 1000, 1)}
    out = {"status": st, "content_type": ct, "bytes": len(body), "ms": round((time.time() - t0) * 1000, 1)}
    # `/api/*`ِ ثبت‌نشده با 200+text/html (index.htmlِ SPA) جواب می‌دهد؛ فقط JSON یعنی مسیر وجود دارد
    if "json" in ct:
        out["json"] = json.loads(body)
    else:
        out["exists"] = False
    return out


def procs():
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'app:app|app\\.py|bors_entry|BorsTerminal' } | "
          "ForEach-Object { '{0}|{1}|{2}' -f $_.ProcessId, $_.CreationDate.ToString('s'), $_.CommandLine }")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [ln for ln in r.stdout.splitlines() if ln.strip() and "Get-CimInstance" not in ln]


if __name__ == "__main__":
    rec = {"captured_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "processes": procs(), "ports": {}}
    for port in (8000, 8010):
        rec["ports"][str(port)] = {p: get(port, p) for p in PATHS}
    with open(os.path.join(HERE, "c0-live-state.json"), "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)
    for port, d in rec["ports"].items():
        for p, v in d.items():
            j = v.get("json")
            print(port, p, v.get("status"), v.get("ms"), (json.dumps(j, ensure_ascii=False)[:300] if j is not None else v))
