import json, sqlite3, urllib.parse, urllib.request

BASE = "http://127.0.0.1:8124"
COPY_DB = r"C:\Users\PCMOD\Desktop\up1084_verify\app\user.db"

# ردیفِ بی‌رمزِ پیشین (که curl با رموزسازیِ Git Bash نوشت) پاک می‌شود
req = urllib.request.Request(BASE + "/api/watchlist/" + urllib.parse.quote("?????"), method="DELETE")
try:
    print("delete:", urllib.request.urlopen(req, timeout=15).read()[:120])
except Exception as e:
    print("delete err:", str(e)[:120])

body = json.dumps({"symbol": "فولاد", "note": "آزمونِ پچ 1084"}, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(BASE + "/api/watchlist", data=body, method="POST",
                             headers={"Content-Type": "application/json; charset=utf-8"})
print("post:", json.dumps(json.loads(urllib.request.urlopen(req, timeout=15).read()), ensure_ascii=False)[:220])

# خواندن از اتصالِ تازه (نویسنده را باور نمی‌کنیم)
con = sqlite3.connect(f"file:{COPY_DB}?mode=ro", uri=True)
print("rows:", con.execute("SELECT symbol, note FROM user_watchlists").fetchall())
con.close()
