"""راستی‌آزماییِ مستقلِ دارایی‌هایِ ریلیزِ v1.0.84 (بی‌برنامه).

هرچه چاپ می‌شود از همین‌جا می‌آید: دانلودِ مستقیمِ هر دارایی از GitHub، شمارشِ
sha256 و size، و بررسیِ امضایِ minisign با کلیدِ عمومیِ خودِ آپدیتِرِ برنامه
(api/update.UPDATE_PUBKEY). هیچ ادعایی از latest.json پذیرفته نمی‌شود مگر اینکه
بایتِ واقعی همان عدد را بدهد.
"""
import hashlib
import json
import os
import sys
import urllib.request

TAG = os.environ.get("TAG", "v1.0.84")
REPO = "johnwarchief/BorsTerminal"
OUTDIR = os.environ.get("OUTDIR", "_audit/up1084")
OUT = os.path.join(OUTDIR, f"assets_verify_{TAG}.json")
os.makedirs(OUTDIR, exist_ok=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.update import UPDATE_PUBKEY            # noqa: E402
from bors_minisign import verify_minisign       # noqa: E402

# دارایی‌هایی که امضا دارند و باید رمزنگاری‌شان راستی‌آزمایی شود
SIGNED = [
    f"BorsTerminal_Ultimate_Setup_{TAG}.exe",
    f"BorsTerminal_Patch_1.0.83_to_{TAG[1:]}.zip",
    f"BorsTerminal_Patch_1.0.82_to_{TAG[1:]}.zip",
    f"BorsTerminal_Patch_1.0.81_to_{TAG[1:]}.zip",
]
# فقط هش/اندازه (بدونِ امضا): ZIP پرتابیل
UNSIGNED = [f"BorsTerminal_Ultimate_Portable_{TAG}.zip"]

R = {"tag": TAG, "pubkey_prefix": UPDATE_PUBKEY[:24], "assets": []}


def dl(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "release-verify"})
    with urllib.request.urlopen(req, timeout=600) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    return dest


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(name, expected_size, signed):
    url = f"https://github.com/{REPO}/releases/download/{TAG}/{name}"
    dest = os.path.join(OUTDIR, name)
    os.makedirs(OUTDIR, exist_ok=True)
    dl(url, dest)
    size = os.path.getsize(dest)
    digest = sha(dest)
    row = {"name": name, "url": url, "bytes_local": size, "sha256_local": digest,
           "size_matches_manifest": expected_size == size, "signature_ok": None}
    if signed:
        sig_name = name + ".sig"
        sig_path = dl(f"https://github.com/{REPO}/releases/download/{TAG}/{sig_name}",
                      os.path.join(OUTDIR, sig_name))
        sig_text = open(sig_path, encoding="utf-8", errors="replace").read()
        try:
            verify_minisign(open(dest, "rb").read(), sig_text, UPDATE_PUBKEY)
            row["signature_ok"] = True
            print(f"  ok   {name}: {size} بایت، امضایِ minisign با کلیدِ آپدیتِر درست")
        except Exception as e:
            row["signature_ok"] = False
            print(f"  FAIL {name}: امضا نخواند -> {repr(e)[:140]}")
    else:
        print(f"  ok   {name}: {size} بایت (بی‌امضا — ZIP پرتابیل)")
    print(f"        sha256={digest}")
    R["assets"].append(row)
    return row


# مانیفستِ عمومیِ ریلیز (latest.json) — اندازه‌هایِ اعلامی
def latest():
    p = os.path.join(OUTDIR, "latest.json")
    dl(f"https://github.com/{REPO}/releases/latest/download/latest.json", p)
    return json.load(open(p, encoding="utf-8"))


L = latest()
print("latest.json version =", L.get("version"))
sizes = {}
for e in L.get("patches") or []:
    sizes[os.path.basename(e["url"])] = int(e.get("size") or 0)
port = L.get("portable") or {}
if port.get("url"):
    sizes[os.path.basename(port["url"])] = int(port.get("size") or 0)
for plat in (L.get("platforms") or {}).values():
    if isinstance(plat, dict) and plat.get("url"):
        sizes[os.path.basename(plat["url"])] = int(plat.get("url_size") or plat.get("size") or 0)
R["latest_json"] = {"version": L.get("version"), "declared": sizes}
print("اندازه‌هایِ اعلامی درِ latest.json:", json.dumps(sizes, ensure_ascii=False)[:300])

rows = [check(n, sizes.get(n, -1), True) for n in SIGNED]
rows += [check(n, sizes.get(n, -1), False) for n in UNSIGNED]

json.dump(R, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
bad = [r["name"] for r in rows if r["signature_ok"] is False]
print(f"\n{len(rows)} دارایی سنجیده شد؛ امضایِ ناقص: {bad or 'هیچ'} — {OUT}")
sys.exit(1 if bad else 0)
