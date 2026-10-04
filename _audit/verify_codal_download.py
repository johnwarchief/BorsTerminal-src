# بررسیِ مسیرِ دانلودِ دیتابیسِ بنیادی (کدال) از ریلیزِ زنده — فقطِ خواندن، بی‌نوشتن در DB
import io, json, os, sqlite3, sys, tempfile, urllib.request, lzma

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bors_minisign import verify_minisign          # noqa: E402
from api.update import UPDATE_PUBKEY               # noqa: E402

URL = ("https://github.com/johnwarchief/BorsTerminal/releases/"
       "latest/download/codal.db.lzma")


def get(u):
    req = urllib.request.Request(u, headers={"User-Agent": "bors-verify"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.status, r.read(), dict(r.headers)


st, body, hdr = get(URL)
print("1) بدنه:", URL.rsplit("/", 1)[-1], "http", st, "bytes", len(body))
st2, sig, _ = get(URL + ".sig")
print("2) امضا: http", st2, "bytes", len(sig))
verify_minisign(body, sig.decode(), UPDATE_PUBKEY)
print("3) verify_minisign با UPDATE_PUBKEY: PASS")

tmp = os.path.join(tempfile.mkdtemp(prefix="bors_codal_verify_"), "codal.db")
with lzma.LZMAFile(io.BytesIO(body)) as z, open(tmp, "wb") as f:
    while True:
        chunk = z.read(1 << 22)
        if not chunk:
            break
        f.write(chunk)
print("4) بازشدنِ LZMA:", os.path.getsize(tmp), "bytes")
con = sqlite3.connect(tmp)
tabs = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
print("5) جدول‌ها:", tabs)
for t in ("codal_notices", "codal_reports", "fundamental_data"):
    if t in tabs:
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"   {t}: {n} ردیف")
mx = None
for t in tabs:
    cols = [c[1] for c in con.execute(f"PRAGMA table_info({t})")]
    for c in ("fetched_at", "publish_date"):
        if c in cols:
            mx = con.execute(f"SELECT MAX({c}) FROM {t}").fetchone()[0]
            print(f"   {t}.{c} MAX = {mx}")
con.close()
os.remove(tmp)
print("6) فایلِ موقت پاک شد — هیچ DB ای دست‌نخورده ماند")
