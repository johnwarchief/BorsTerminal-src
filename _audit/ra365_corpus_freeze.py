# _audit/ra365_corpus_freeze.py -- یخ‌زدنِ corpus مرحلۀِ ۲ در یک CSVِ ردیابی‌شدنی
# چرا: `.gitignore` الگویِ `_audit/*.json` را کنار می‌گذارد، پس ra365_corpus.json (فهرستِ ۲۹ نماد
# با شناسۀِ دارایی و دلیلِ انتخاب) درِ مخزن نمی‌ماند؛ بدونِ آن، سطرهایِ گزارشِ مرحلۀِ ۳ قابلِ
# بازبینی نیستند. این فایل همان داده را با ستون‌هایِ سنجشِ هر نماد بیرون می‌ریزد.
import csv
import io
import json
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = "C:/Users/[LOCAL_USER]/Desktop/Borsterminal/BorsTerminal-src"
AUD = f"{ROOT}/_audit"

corpus = json.load(open(f"{AUD}/ra365_corpus.json", encoding="utf-8"))
metrics = list(csv.DictReader(open(f"{AUD}/ra365_corpus_metrics.csv", encoding="utf-8-sig")))
mrows = {r["symbol"]: r for r in metrics}

MFIELDS = ["bars", "last_date", "last_close", "sector", "return_500d", "max_drawdown",
           "daily_vol", "missing_sessions", "flat_candles", "adjust_events"]

rows = []
for c in corpus:
    m = mrows.get(c["sym"], {})
    rows.append({
        "symbol": c["sym"],
        "asset_id": c["id"],
        "name": c.get("name", ""),
        "exchange": c.get("exchange", ""),
        "type": c.get("type", ""),
        "selection_reason": c.get("reason", ""),
        "ref_window_daily": "2023-12-04 تا 2026-10-11 (۶۰۱ کندلِ درخواستی)",
        "ref_window_weekly": "2023-01-07 تا 2026-10-11 (۴۲۰ کندلِ درخواستی)",
        **{k: m.get(k, "") for k in MFIELDS},
    })

missing_reason = [r["symbol"] for r in rows if not r["selection_reason"]]
missing_metric = [r["symbol"] for r in rows if r["bars"] == ""]

out = f"{AUD}/RA365-CORPUS-2026-10-12.csv"
with open(out, "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print(f"نوشته شد: {out}  ({len(rows)} سطر)")
print("  ستون‌ها:", ", ".join(rows[0].keys()))
print(f"  بی‌دلیلِ انتخاب: {missing_reason or '—'}   بی‌سنجش: {missing_metric or '—'}")
print("  اجباریِ مأموریت:", [r["symbol"] for r in rows if "اجباری" in r["selection_reason"]])
