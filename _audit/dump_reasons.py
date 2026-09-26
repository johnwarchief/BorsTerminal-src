import json, urllib.parse, urllib.request, sys

SYMS = sys.argv[1:] or ["فولاد", "خودرو", "وغدار", "بیمه", "وشمال", "تاپیکست", "خکشف", "وملل", "شپدیس", "فتأمین", "خساپا", "زگستر"]
BASE = "http://127.0.0.1:8001/api/fundamental/"

def walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, str) and k in ("reason", "why", "fix", "outlook", "what", "detail", "remediation", "text", "basis", "note", "tagline"):
                if v.strip():
                    print(f"  {path}.{k}: {v}")
            else:
                walk(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, f"{path}[{i}]")

for s in SYMS:
    url = BASE + urllib.parse.quote(s)
    try:
        with urllib.request.urlopen(url, timeout=90) as r:
            d = json.load(r)
    except Exception as e:
        print(f"!! {s}: {e}")
        continue
    print(f"=== {s} ({d.get('symbol')}) verdict={d.get('verdict') or d.get('result')}")
    walk({k: v for k, v in d.items() if k in ("indicators", "data_gaps", "details", "insights", "layers", "passes")}, "")
