import io, json, subprocess, sys, os

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---- متنِ بدنه، دقیقاً مثلِ publish_github_release.py ----
sys.path.insert(0, "_audit")
import build_latest73 as B  # noqa: E402  (همان فایل، BODY را می‌سازد)

BODY = B.BODY
RTL = '<div dir="rtl">\n\n%s\n\n</div>' % BODY
json.dump({"body": RTL}, io.open("_audit/payload_body.json", "w", encoding="utf-8"), ensure_ascii=False)
print("payload bytes:", os.path.getsize("_audit/payload_body.json"))
