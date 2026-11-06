import io

P = "docs/RELEASE_NOTES.md"
t = io.open(P, encoding="utf-8", newline="").read()
CRLF = "\r\n"
old = CRLF + CRLF + CRLF + "## v1.0.72" + CRLF
old2 = CRLF + CRLF + "## v1.0.72" + "\n"
print("has 3-blank+CRLF form:", t.count(old))
print("has 2-blank+LF form  :", t.count(old2))
# هدف: یک خطِ خالی + «## v1.0.72» با پایانِ CRLF
t2 = t.replace(old2, CRLF + "## v1.0.72" + CRLF)
t2 = t2.replace(old, CRLF + "## v1.0.72" + CRLF)
assert t2 != t, "هیچ الگویی نخورد — فایلی را تغییر نده"
io.open(P, "w", encoding="utf-8", newline="").write(t2)

chk = io.open(P, encoding="utf-8", newline="").read()
lines = chk.split("\n")
print("non-crlf content lines:", sum(1 for x in lines[:-1] if x.strip() and not x.endswith("\r")))
import re
for k, l in enumerate(lines):
    if re.match(r"^## v1\.0\.7", l.rstrip("\r")):
        print(k + 1, l.rstrip("\r"), "|", repr(lines[k + 1][:44]))
