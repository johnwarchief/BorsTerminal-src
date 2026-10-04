import io, re

P = "docs/RELEASE_NOTES.md"
FA = "".join(chr(0x06F0 + d) for d in range(10))
TH, DP, PCT = "٬", "٫", "٪"


def g(x):
    return "".join(FA[int(c)] if c.isdigit() else TH for c in f"{x:,}")


def d(s):
    return "".join(FA[int(c)] if c.isdigit() else DP for c in s)


t = io.open(P, encoding="utf-8", newline="").read()

pairs = [
    # پنلِ پس از ترمیمِ حفرۀ پنج‌روزه
    (g(725) + " نماد و " + g(245444) + " کندل", g(727) + " نماد و " + g(249170) + " کندل"),
    ("از " + d("47.5") + PCT + " به **" + d("49.8") + PCT + "**",
     "از " + d("47.8") + PCT + " به **" + d("50.0") + PCT + "**"),
    ("دقتش " + d("43") + PCT + " بود", "دقتش " + d("43.7") + PCT + " بود"),
    ("دقت به **" + d("48.7") + PCT + "**", "دقت به **" + d("48.8") + PCT + "**"),
    ("(" + d("44.6") + PCT + " در برابر " + d("48.3") + PCT + ")",
     "(" + d("45.1") + PCT + " در برابر " + d("49.7") + PCT + ")"),
]
for a, b in pairs:
    c = t.count(a)
    print(("OK " if c == 1 else "!! ") + f"count={c} :: {a}  ->  {b}")
    assert c == 1, a
    t = t.replace(a, b)

io.open(P, "w", encoding="utf-8", newline="").write(t)
sec = t.split("## v1.0.73")[1].split("## v1.0.72")[0]
print("\n-- شمارشِ دوبارۀ همهٔ ارقامِ بخشِ v1.0.73 --")
for m in re.finditer("[\\u06f0-\\u06f9\\u066c\\u066b]+[\\u066a%]?", sec):
    print("  ", m.group())
