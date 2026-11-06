import io

path = "docs/RELEASE_NOTES.md"
tag = "v1.0.73"
text = io.open(path, encoding="utf-8").read()
want = ("## " + tag, "## v" + tag.lstrip("v"), "## " + tag.lstrip("v"))
lines = text.splitlines()
out, hit = [], False
for ln in lines:
    if ln.startswith("## "):
        if hit:
            break
        hit = ln.strip() in [w.strip() for w in want] or any(ln.strip().startswith(w) for w in want)
        continue
    if hit:
        out.append(ln)
body = "\n".join(out).strip()
print("placeholder?", body.startswith("یادداشتِ نسخه‌ای"))
print("len:", len(body))
print("head:", body.splitlines()[0][:80])
print("tail:", body.splitlines()[-1][:80])
