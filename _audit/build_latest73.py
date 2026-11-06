import io, json, sys

sys.path.insert(0, ".")

# همان منطقِ release_body() در scripts/publish_github_release.py (کپی، نه import؛
# آن ماژول درِ import بیلد را صدا می‌زند)
tag = "v1.0.73"
text = io.open("docs/RELEASE_NOTES.md", encoding="utf-8").read()
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
BODY = "\n".join(out).strip()
assert not BODY.startswith("یادداشتِ"), "متن هنوز placeholder است"

live = json.load(io.open("_audit/live_latest.json", encoding="utf-8"))
fixed = dict(live)
fixed["notes"] = BODY
io.open("_audit/latest_fixed.json", "w", encoding="utf-8", newline="\n").write(
    json.dumps(fixed, ensure_ascii=False, indent=2) + "\n")

diff = [k for k in set(list(live) + list(fixed)) if live.get(k) != fixed.get(k)]
print("تغییرکرده:", diff)
print("طولِ notes:", len(live["notes"]), "->", len(BODY))
# اثباتِ بی‌تغییریِ همه‌چیزِ امضاشده
for k in ("version", "pub_date", "platforms", "patches"):
    same = json.dumps(live.get(k), sort_keys=True) == json.dumps(fixed.get(k), sort_keys=True)
    print(f"  {k}: یکسان={same}")
sig_live = [p.get("signature") for p in live["platforms"].values()] + [e["signature"] for e in live["patches"]]
print("  امضاها:", len(sig_live), "تعداد، همه دست‌نخورده:",
      sig_live == [p.get("signature") for p in fixed["platforms"].values()] + [e["signature"] for e in fixed["patches"]])
