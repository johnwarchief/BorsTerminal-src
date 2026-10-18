# -*- coding: utf-8 -*-
"""نمونه‌گیرِ سبُکِ CPU/RAMِ یک پردازه رویِ ویندوز، بی‌psutil و بی‌PowerShell.

چرا: هر `Get-Process` یک پاورشلِ تازه است (~۰٫۵ ثانیه CPU) و خودش اندازه را
خراب می‌کند. اینجا فقط `GetProcessTimes` و `K32GetProcessMemoryInfo` با دسترسیِ
`PROCESS_QUERY_LIMITED_INFORMATION` خوانده می‌شود: فقط‌خواندنی، بی‌اثر رویِ پردازهٔ هدف.

    from perf_winproc import ProcSampler
    s = ProcSampler(pid); a = s.read(); ...; b = s.read()
    cpu_ms = b["cpu_ms"] - a["cpu_ms"]
"""
import ctypes
import ctypes.wintypes as wt
import time

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_PROCESS_VM_READ = 0x0010
_STILL_ACTIVE = 259


class _FILETIME(ctypes.Structure):
    _fields_ = [("lo", wt.DWORD), ("hi", wt.DWORD)]


class _PMC(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.OpenProcess.restype = wt.HANDLE
_k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
_k32.GetProcessTimes.argtypes = [wt.HANDLE] + [ctypes.POINTER(_FILETIME)] * 4
_k32.K32GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(_PMC), wt.DWORD]
_k32.GetExitCodeProcess.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
_k32.CloseHandle.argtypes = [wt.HANDLE]


def _ft(ft):
    return (ft.hi << 32) | ft.lo


class ProcSampler:
    def __init__(self, pid):
        self.pid = int(pid)
        self.h = _k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION | _PROCESS_VM_READ, False, self.pid)
        if not self.h:
            self.h = _k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, self.pid)
        if not self.h:
            raise OSError("OpenProcess(%d) failed: %d" % (self.pid, ctypes.get_last_error()))

    def alive(self):
        code = wt.DWORD()
        return bool(_k32.GetExitCodeProcess(self.h, ctypes.byref(code))) and code.value == _STILL_ACTIVE

    def read(self):
        """`wall` = time.time() (ساعتِ همین ماشین)؛ `cpu_ms` = user+kernelِ تجمعی."""
        c, e, k, u = _FILETIME(), _FILETIME(), _FILETIME(), _FILETIME()
        ok = _k32.GetProcessTimes(self.h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u))
        pmc = _PMC()
        pmc.cb = ctypes.sizeof(_PMC)
        okm = _k32.K32GetProcessMemoryInfo(self.h, ctypes.byref(pmc), pmc.cb)
        return {"wall": time.time(), "mono": time.perf_counter(),
                "cpu_ms": (_ft(k) + _ft(u)) / 10_000.0 if ok else None,
                "ws_mb": pmc.WorkingSetSize / 1e6 if okm else None,
                "peak_ws_mb": pmc.PeakWorkingSetSize / 1e6 if okm else None,
                "private_mb": pmc.PagefileUsage / 1e6 if okm else None}

    def close(self):
        if self.h:
            _k32.CloseHandle(self.h)
            self.h = None


if __name__ == "__main__":
    import json
    import sys
    s = ProcSampler(int(sys.argv[1]))
    a = s.read()
    time.sleep(1.0)
    b = s.read()
    print(json.dumps({"pid": s.pid, "alive": s.alive(), "cpu_pct_1s": round((b["cpu_ms"] - a["cpu_ms"]) / 10.0, 1),
                      **{k: round(v, 1) for k, v in b.items() if k in ("ws_mb", "peak_ws_mb", "private_mb")}}))
    s.close()
