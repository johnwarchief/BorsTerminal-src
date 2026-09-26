import json, re, urllib.parse, urllib.request, collections

# نمادهایِ پراکنده: تولیدی، هلدینگ، مالی، صندوق، دارویی، پتروشیمی، خودرو، بانکی
SYMS = ["فولاد","خودرو","وتوسا","وغدير","شپدیس","تاپیکست","خکشف","وملل","وشمال","بیمه",
        "خساپا","فصبا","زترک","وغفادری","كگل","حاپا","لپارس","مفاخر","سپاس","وآسام",
        "خعمى","نماد","شارا","غمتن","وتو","صمكين","بورود","پتروش","فراس","شگما"]
BASE = "http://127.0.0.1:8001/api/fundamental/"
FIELDS = ("reason", "basis", "outlook", "note", "why", "fix", "denominator_basis")
BAN = re.compile(r"api/|monthly_sales|fts_engine|annualize|backfill|\bNone\b|\bNaN\b|YoY|بک‌اند|→", re.I)
CLAIM = re.compile(r"تضمین|انحصاری|بهره‌وری عالی|حباب|جهش عملیاتی|قدرت فروش|حاشیه امن|سرکوب|بی‌معنا|تایید می‌شود")

seen = collections.Counter()
bad = collections.Counter()
lat = collections.Counter()
ok = 0
for s in SYMS:
    try:
        with urllib.request.urlopen(BASE + urllib.parse.quote(s), timeout=120) as r:
            d = json.load(r)
    except Exception as e:
        bad["<fetch %s>" % type(e).__name__] += 1
        continue
    ok += 1
    bag = {k: d.get(k) for k in ("indicators", "data_gaps")}
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, str) and k in FIELDS and v.strip():
                    seen[v.strip()] += 1
                    if BAN.search(v): lat["JARGON: " + v.strip()] += 1
                    if CLAIM.search(v): lat["CLAIM: " + v.strip()] += 1
                    if re.search(r"[0-9]", v): lat["LATIN-DIGIT: " + v.strip()] += 1
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(bag)

print("cards read:", ok, "| distinct strings:", len(seen))
print("\n--- strings the display layer must still clean ---")
for k, n in lat.most_common(40):
    print("%3d  %s" % (n, k[:170]))
