# -*- coding: utf-8 -*-
"""audit_runlog — لاگِ streamِ اجرایِ Jobهایِ پایشِ زنده.

چرا لازم شد: دو Jobِ Task Scheduler (`BorsFTSLiveAudit`، `BorsTapeLiveAudit`)
هیچ‌جا stdout/stderr را جایی نمی‌نوشتند — Task Scheduler فقط کدِ خروج را نگه
می‌دارد و printها دور ریخته می‌شدند. سنجشِ این دور: اجرایِ ۱۴:۰۰ تا ۱۲ دقیقه‌ایِ
FTS درِ `_audit/fts_live_audit/` هیچ اثری نگذاشته بود جزِ یکِ فایلِ JSONL که
آخرِ کار نوشته می‌شد؛ اگر دور کشته می‌شد، نه خطایی می‌ماند نه ردیابی.

این helper دو کار می‌کند:
  • هر خطِ stdout/stderr را بی‌درنگ درِ `<outdir>/run.log` هم می‌نویسد (tee و flush)
  • خطِ START/END با PID، آرگومان‌ها و کدِ خروج — پس «اجرایِ از دست رفته»،
    «شکستِ میانی» و «دو اجرایِ هم‌زمان» از خودِ لاگ خوانده می‌شوند.

فقط ابزارِ dev است؛ درِ EXE بسته نمی‌شود (درِ `fts_terminal.spec` فهرست نیست و
باید هم نباشد — این فایل بیرونِ ریپویِ کاری اجرا نمی‌شود).
"""
import datetime as dt
import os
import sys


class _Tee:
    def __init__(self, stream, logfh):
        self._s = stream
        self._f = logfh

    def write(self, data):
        try:
            self._s.write(data)
        except Exception:
            pass
        try:
            self._f.write(data)
            self._f.flush()
        except Exception:
            pass
        return len(data) if isinstance(data, str) else 0

    def flush(self):
        for x in (self._s, self._f):
            try:
                x.flush()
            except Exception:
                pass

    def __getattr__(self, name):
        return getattr(self._s, name)


def attach(outdir: str, argv=None) -> str:
    """stdout/stderr را به `outdir/run.log` گره می‌زند؛ مسیرِ لاگ را برمی‌گرداند."""
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "run.log")
    try:
        fh = open(path, "a", encoding="utf-8", buffering=1)
    except OSError:
        return ""
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    args = " ".join(str(x) for x in (argv if argv is not None else sys.argv[1:]))
    fh.write(f"\n===== START {stamp} pid={os.getpid()} args={args}\n")
    fh.flush()
    sys.stdout = _Tee(sys.stdout, fh)
    sys.stderr = _Tee(sys.stderr, fh)
    return path


def mark_end(path: str, code, detail: str = "") -> None:
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"===== END {dt.datetime.now():%Y-%m-%d %H:%M:%S} "
                    f"pid={os.getpid()} exit={code} {detail}\n")
    except OSError:
        pass
