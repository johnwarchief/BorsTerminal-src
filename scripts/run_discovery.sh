#!/bin/bash
# Wait out the Codal WAF ban (~20-30 min), then run the full Active Discovery Scan.
# Resumable-friendly: if the scan dies, re-run launches fresh (symbols with FS in
# DB are skipped by the candidate query, so re-runs only cover the remainder).
# Cross-platform: works on Windows (Git Bash / MSYS) and Linux/macOS.
cd "$(dirname "$0")/.." || exit 1   # scripts/ -> repo root

if [ -z "$PY" ]; then
    case "$(uname -s)" in
        MINGW*|MSYS*|CYGWIN*)
            # Windows: hermes venv (known-good) if present, else `python` on PATH
            PY="C:/Users/PCMOD/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"
            [ -x "$PY" ] || PY="python"
            ;;
        *)
            PY="python3"
            ;;
    esac
fi
LOG=logs/discovery_scan.log
mkdir -p "${LOG%/*}"

# گارد جلوگیری از اسکن همزمان: هر اسکن = یک جفت پروسه (launcher + real
# interpreter) روی ویندوز؛ روی POSIX یک پروسه (خود اسکریپت launcher است).
case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
        N=$(powershell -NoProfile -Command "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -match 'codal_fetcher.py --feed' }).Count" 2>/dev/null | tr -d ' \r\n')
        N=$(( (${N:-0} + 1) / 2 ))  # جفت (launcher+interpreter) → نصف
        ;;
    *)
        N=$(pgrep -f "codal_fetcher.py --feed" 2>/dev/null | wc -l)
        N=$(( ${N:-0} ))
        ;;
esac
if [ -n "$N" ] && [ "$N" -ge 1 ]; then
    echo "[wrapper] $(date +%H:%M:%S) — $N discovery scans already running; exiting (no duplicate)"
    exit 0
fi

echo "[wrapper] $(date +%H:%M:%S) — starting full discovery scan"
"$PY" -u codal_fetcher.py --feed discover >> "$LOG" 2>&1
echo "[wrapper] $(date +%H:%M:%S) — scan exited with code $?"
