# بازسازیِ بخشِ v1.0.73 در RELEASE_NOTES: سرفصلِ v1.0.72 برگردد و ارقامِ افتاده درست شوند
import io, re, json

P = "docs/RELEASE_NOTES.md"
FA = "".join(chr(0x06F0 + d) for d in range(10))
TH = "٬"   # هزارگان
DP = "٫"   # اعشار


def n(x: int) -> str:
    return "".join(FA[int(c)] for c in str(x))


def grp(x: int) -> str:
    s = f"{x:,}"
    return "".join(FA[int(c)] if c.isdigit() else TH for c in s)


def dec(a: str) -> str:
    return "".join(FA[int(c)] if c.isdigit() else DP for c in a)


txt = io.open(P, encoding="utf-8", newline="").read()
orig = txt

# 1) سرفصلِ ## v1.0.72 که جابه‌جا حذف شده بود
head72 = "## " + "v1.0.72"
marker = "### ◆ داوریِ تکنیکال"
assert txt.count(head72) == 0, "سرفصل از قبل وجود دارد"
assert txt.count(marker) == 1
i = txt.index(marker)
j = txt.rindex("\n", 0, i) + 1
blank = txt[j:i]
print("prefix before marker:", repr(blank))
txt = txt[:j] + head72 + "\n" + marker + txt[i + len(marker):]

# 2) ارقامِ افتاده (هر کدام باید دقیقاً یک بار پیدا شود)
reps = []
# کندل‌ها و بازۀ زمانی
reps.append(("۲۴" + TH + "۴۴ کندل", f"{grp(245444)} کندل"))
reps.append(("(۲۲۴-۰۸ تا ۲۰۲۶-۱۰)", f"({n(2024)}-{n(8)}-{n(24)} تا {n(2026)}-{n(10)}-{n(3)})"))
# پوشِ نقطه‌زنی
reps.append(("۵٫۳٪ کلِ کندل‌ها", f"{dec('6.5')}٪ کلِ کندل‌ها"))
# نودجینگِ درصدی
reps.append(("نشان را ۲/۸٪ بالا", f"نشان را {dec('2.8')}٪ بالا"))
# شمارِ مارکرِ جت
reps.append(("تا **۳۴ نشان از ۴۰ نشان**", f"تا **{n(30)} تا {n(34)} نشان از {n(40)} نشان**"))

for a, b in reps:
    c = txt.count(a)
    print(f"count={c} :: {a!r} -> {b!r}")
    assert c == 1, a
    txt = txt.replace(a, b)

# 3) سرفصلِ v1.0.72: خطِ خالیِ اضافه پیش از «### ◆ داوریِ تکنیکال» و درجِ ##
lines = txt.split("\n")
for i, L in enumerate(lines):
    if L.startswith("### ◆ داوریِ تکنیکال"):
        print("found daavari at line", i + 1)
        print("  prev-2:", repr(lines[i - 2]))
        print("  prev-1:", repr(lines[i - 1]))
        print("  prev  :", repr(lines[i - 3]))
        break

io.open(P, "w", encoding="utf-8", newline="").write(txt)
print("changed:", txt != orig)
