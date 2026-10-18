# -*- coding: utf-8 -*-
"""tools/perf_market_open_sampler.py — نمونه‌گیرِ منفعلِ پایشِ بازشدنِ بازار.

چه می‌خواند (همه فقط‌خواندنی؛ هیچ درخواستی به TSETMC/CODAL و هیچ حلقهٔ دریافت):
  * CPU/RAMِ پردازه‌ای که رویِ `--port` گوش می‌دهد (GetProcessTimes/K32GetProcessMemoryInfo)
  * CPUِ کلِ سیستم (GetSystemTimes) و هر `--top-every` ثانیه پنج پرمصرف‌ترین پردازه
  * کلاینت‌هایِ وصل به پورت (netstat) — تا روشن باشد پایش تنها کلاینت است یا نه
  * mtime/اندازهٔ فایل‌هایِ `--watch` (market.db، -wal، market_sync.json): تنها نشانِ
    «بانک واقعاً نوشته شد» بی‌آنکه به سرور درخواستی زده شود
  * آفستِ ساعتِ این ماشین نسبت به NTP (`w32tm /stripchart`) در آغاز و پایان
  * اختیاری: `--spot-every N` یک GETِ ترتیبی به مسیرهایِ غیرِ UI (sync-state،
    mstat/board) هر N ثانیه؛ پیش‌فرض خاموش، چون بارِ اضافه است.

همهٔ زمان‌ها `t` = epochِ ثانیه‌ایِ ساعتِ همین ماشین (time.time())؛ ساعتِ تهران.
خروجی JSONL است؛ تحلیل با tools/perf_market_open_analyze.py.

    python tools/perf_market_open_sampler.py --port 8000 --out _audit/x/sampler.jsonl \
        --watch <checkout>/market.db --watch <checkout>/market.db-wal \
        --watch <checkout>/market_sync.json --start-at 08:30 --until 12:45
توقف: فایلِ STOP کنارِ خروجی، یا Ctrl+C، یا رسیدنِ --until.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import datetime as dt
import gzip
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from perf_winproc import ProcSampler, _FILETIME, _ft  # noqa: E402

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_psapi = ctypes.WinDLL("psapi", use_last_error=True)
_k32.GetSystemTimes.argtypes = [ctypes.POINTER(_FILETIME)] * 3
_k32.OpenProcess.restype = wt.HANDLE
_k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
_k32.GetProcessTimes.argtypes = [wt.HANDLE] + [ctypes.POINTER(_FILETIME)] * 4
_k32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
_k32.CloseHandle.argtypes = [wt.HANDLE]
_psapi.EnumProcesses.argtypes = [ctypes.POINTER(wt.DWORD), wt.DWORD, ctypes.POINTER(wt.DWORD)]
_LIMITED = 0x1000
_NO_WINDOW = 0x08000000

TS_KEYS = {"as_of", "computed_at", "last_sync", "d_even", "h_even", "activity_h_even",
           "data_updated_at", "clock_now", "session_day", "official_state", "phase",
           "phase_source", "rev", "revision", "status", "running", "ts", "stage"}


def system_times():
    i, k, u = _FILETIME(), _FILETIME(), _FILETIME()
    _k32.GetSystemTimes(ctypes.byref(i), ctypes.byref(k), ctypes.byref(u))
    return _ft(i), _ft(k), _ft(u)


def proc_cpu_and_name(pid):
    h = _k32.OpenProcess(_LIMITED, False, pid)
    if not h:
        return None, None
    try:
        c, e, k, u = _FILETIME(), _FILETIME(), _FILETIME(), _FILETIME()
        ok = _k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u))
        buf = ctypes.create_unicode_buffer(520)
        n = wt.DWORD(520)
        name = os.path.basename(buf.value) if _k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else None
        return ((_ft(k) + _ft(u)) / 10_000.0 if ok else None), name
    finally:
        _k32.CloseHandle(h)


def all_pids():
    arr = (wt.DWORD * 4096)()
    got = wt.DWORD()
    _psapi.EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(got))
    return [arr[i] for i in range(got.value // ctypes.sizeof(wt.DWORD)) if arr[i]]


def netstat_rows():
    out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True,
                         creationflags=_NO_WINDOW).stdout
    rows = []
    for line in out.splitlines():
        p = line.split()
        if len(p) == 5 and p[0] == "TCP":
            rows.append((p[1], p[2], p[3], int(p[4])))
    return rows


def listening_pid(port, rows=None):
    for local, _remote, state, pid in rows or netstat_rows():
        if state == "LISTENING" and local.endswith(":%d" % port):
            return pid
    return None


def clients(port, rows):
    """کلاینت‌هایِ واقعی: سوکتی که *remote*ش پورتِ سرور است، با PIDِ صاحبِ همان سوکت."""
    by = {}
    for _local, remote, state, pid in rows:
        if state == "ESTABLISHED" and remote.endswith(":%d" % port):
            by[pid] = by.get(pid, 0) + 1
    return [{"pid": p, "name": proc_cpu_and_name(p)[1], "conns": n} for p, n in sorted(by.items())]


def file_stats(paths):
    out = {}
    for p in paths:
        try:
            st = os.stat(p)
            out[p] = {"mtime": round(st.st_mtime, 3), "size": st.st_size}
        except OSError:
            out[p] = None
    return out


def ntp_offsets(server):
    """آفستِ ساعتِ محلی نسبت به NTP به ثانیه (مثبت = ساعتِ محلی عقب است، قراردادِ w32tm)."""
    try:
        out = subprocess.run(["w32tm", "/stripchart", "/computer:%s" % server, "/samples:3", "/dataonly"],
                             capture_output=True, text=True, timeout=40, creationflags=_NO_WINDOW).stdout
    except Exception as e:  # noqa: BLE001
        return {"server": server, "error": str(e)[:120]}
    offs = [float(m) for m in re.findall(r",\s*([+-]\d+\.\d+)s", out)]
    return {"server": server, "offsets_s": offs, "raw_tail": out.strip().splitlines()[-4:]}


def server_identity(pid):
    """یک‌بار در آغاز: خطِ فرمان و زمانِ ساختِ پردازهٔ سرور (CIM)، تا روشن باشد کدام checkout سرو می‌کند."""
    if not pid:
        return None
    try:
        out = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                              "Get-CimInstance Win32_Process -Filter 'ProcessId=%d' | "
                              "Select-Object ProcessId,ParentProcessId,CreationDate,ExecutablePath,CommandLine | "
                              "ConvertTo-Json -Compress" % pid],
                             capture_output=True, text=True, timeout=30, creationflags=_NO_WINDOW).stdout
        return json.loads(out) if out.strip() else None
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:160]}


def extract_ts(obj, prefix="", depth=0, out=None):
    out = {} if out is None else out
    if depth > 3 or not isinstance(obj, dict):
        return out
    for k, v in obj.items():
        if isinstance(v, dict):
            extract_ts(v, prefix + k + ".", depth + 1, out)
        elif not isinstance(v, list) and k in TS_KEYS:
            out[prefix + k] = v
    return out


def spot(base, path):
    req = urllib.request.Request(base + path, headers={"Accept-Encoding": "gzip", "Accept": "application/json"})
    t0 = time.perf_counter()
    rec = {"k": "spot", "t": round(time.time(), 3), "path": path}
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            t1 = time.perf_counter()
            raw = r.read()
            t2 = time.perf_counter()
            enc = r.headers.get("Content-Encoding", "identity")
            body = gzip.decompress(raw) if enc == "gzip" else raw
            rec.update(status=r.status, ttfb_ms=round((t1 - t0) * 1000, 1), total_ms=round((t2 - t0) * 1000, 1),
                       wire_bytes=len(raw), body_bytes=len(body), enc=enc, x_cache=r.headers.get("X-Cache", ""),
                       date_hdr=r.headers.get("Date", ""))
            try:
                rec["ts"] = extract_ts(json.loads(body))
            except ValueError:
                rec["ts"] = None
    except Exception as e:  # noqa: BLE001
        rec.update(status=getattr(e, "code", 0), error=str(e)[:160], total_ms=round((time.perf_counter() - t0) * 1000, 1))
    return rec


def at_today(hhmm):
    h, m = (int(x) for x in hhmm.split(":"))
    now = dt.datetime.now()
    t = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if t < now - dt.timedelta(hours=12):
        t += dt.timedelta(days=1)
    return t.timestamp()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--out", required=True)
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--top-every", type=float, default=60.0)
    ap.add_argument("--watch", action="append", default=[])
    ap.add_argument("--extra-port", type=int, action="append", default=[],
                    help="پورت‌هایِ دیگری که فقط CPU/RAMشان ثبت می‌شود (مثلاً بک‌اندِ دومِ هم‌زمان)")
    ap.add_argument("--spot-every", type=float, default=0.0)
    ap.add_argument("--spot-path", action="append", default=[])
    ap.add_argument("--ntp", default="time.windows.com")
    ap.add_argument("--start-at", default="")
    ap.add_argument("--until", default="")
    ap.add_argument("--duration", type=float, default=0.0)
    a = ap.parse_args()
    spot_paths = a.spot_path or ["/api/market/sync-state", "/api/mstat/board?group=eq_all&limit=60"]
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    stop_file = os.path.join(os.path.dirname(os.path.abspath(a.out)), "STOP")
    fh = open(a.out, "a", encoding="utf-8")

    def emit(rec):
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()

    if a.start_at:
        t_start = at_today(a.start_at)
        emit({"k": "armed", "t": round(time.time(), 3), "pid_self": os.getpid(), "start_at": t_start})
        while time.time() < t_start and not os.path.exists(stop_file):
            time.sleep(min(30.0, max(0.5, t_start - time.time())))
    t_end = at_today(a.until) if a.until else (time.time() + a.duration if a.duration else float("inf"))

    rows = netstat_rows()
    pid = listening_pid(a.port, rows)
    emit({"k": "start", "t": round(time.time(), 3), "pid_self": os.getpid(), "port": a.port, "pid": pid,
          "tz": time.strftime("%z"), "args": vars(a), "server": server_identity(pid), "ntp": ntp_offsets(a.ntp),
          "clients": clients(a.port, rows), "files": file_stats(a.watch)})
    samp = ProcSampler(pid) if pid else None
    extra = {}
    for p in a.extra_port:
        xp = listening_pid(p, rows)
        if xp:
            try:
                extra[p] = ProcSampler(xp)
            except OSError:
                pass
    prev = samp.read() if samp else None
    prev_x = {p: s.read() for p, s in extra.items()}
    prev_sys = system_times()
    prev_top = {}
    next_top = time.time()
    next_spot = time.time() + 30 if a.spot_every > 0 else float("inf")
    try:
        while time.time() < t_end and not os.path.exists(stop_file):
            time.sleep(a.interval)
            now = time.time()
            rec = {"k": "s", "t": round(now, 3), "pid": samp.pid if samp else None}
            if samp and samp.alive():
                cur = samp.read()
                wall = cur["wall"] - prev["wall"]
                rec.update(cpu_pct=round((cur["cpu_ms"] - prev["cpu_ms"]) / (wall * 10.0), 1),
                           ws_mb=round(cur["ws_mb"], 1), private_mb=round(cur["private_mb"], 1))
                prev = cur
            else:
                rows = netstat_rows()
                npid = listening_pid(a.port, rows)
                old = samp.pid if samp else None
                # سرورِ خاموش نباید هر ۵ ثانیه یک پاورشل (server_identity) بسازد.
                if npid != old or samp:
                    emit({"k": "pidchange", "t": round(now, 3), "old": old, "new": npid,
                          "server": server_identity(npid) if npid else None})
                if samp:
                    samp.close()
                samp = ProcSampler(npid) if npid else None
                prev = samp.read() if samp else None
            xs = {}
            for p, s in extra.items():
                if s.alive():
                    c = s.read()
                    w = c["wall"] - prev_x[p]["wall"]
                    xs[str(p)] = {"pid": s.pid, "cpu_pct": round((c["cpu_ms"] - prev_x[p]["cpu_ms"]) / (w * 10.0), 1),
                                  "ws_mb": round(c["ws_mb"], 1)}
                    prev_x[p] = c
            if xs:
                rec["extra"] = xs
            st = system_times()
            di, dk, du = (st[0] - prev_sys[0]), (st[1] - prev_sys[1]), (st[2] - prev_sys[2])
            rec["sys_cpu_pct"] = round(100.0 * (1 - di / (dk + du)), 1) if dk + du else None
            prev_sys = st
            rec["files"] = file_stats(a.watch)
            emit(rec)
            if now >= next_top:
                cur_top = {}
                for p in all_pids():
                    ms, name = proc_cpu_and_name(p)
                    if ms is not None:
                        cur_top[p] = (ms, name, now)
                top = []
                for p, (ms, name, t) in cur_top.items():
                    if p in prev_top and t > prev_top[p][2]:
                        top.append({"pid": p, "name": name,
                                    "cpu_pct": round((ms - prev_top[p][0]) / ((t - prev_top[p][2]) * 10.0), 1)})
                top.sort(key=lambda x: -x["cpu_pct"])
                rows = netstat_rows()
                emit({"k": "top", "t": round(now, 3), "top": top[:6], "clients": clients(a.port, rows),
                      "listening_pid": listening_pid(a.port, rows)})
                prev_top = cur_top
                next_top = now + a.top_every
            if now >= next_spot:
                base = "http://127.0.0.1:%d" % a.port
                for sp in spot_paths:
                    emit(spot(base, sp))
                next_spot = time.time() + a.spot_every
    except KeyboardInterrupt:
        pass
    finally:
        emit({"k": "end", "t": round(time.time(), 3), "ntp": ntp_offsets(a.ntp),
              "reason": "stop-file" if os.path.exists(stop_file) else "until/duration/interrupt"})
        fh.close()


if __name__ == "__main__":
    main()
