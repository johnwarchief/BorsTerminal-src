# -*- coding: utf-8 -*-
"""پیش‌نمایش حالت موبایل (VITE_LOCAL_DATA=1) — سرور ایستای ساده + SPA fallback.

فقط ابزار توسعه است: dist/ را سرو می‌کند تا اپ آفلاین (اسنپ‌شات + sql.js)
بدون هیچ بک‌اندی در مرورگر/گوشی دیده شود. هیچ /api ای وجود ندارد — عمداً.

اجرا:  python tools/serve_mobile_preview.py [port]
پیش‌نیاز: VITE_LOCAL_DATA=1 npm run build  و کپی mobile_snapshot.db.gz در dist/
"""
import http.server
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dist")


class SpaHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def send_head(self):
        # مسیرهای بدون پسوند (روت‌های react-router) → index.html
        path = self.translate_path(self.path)
        base = os.path.basename(self.path.split("?")[0])
        if not os.path.exists(path) and "." not in base:
            self.path = "/index.html"
        return super().send_head()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
    http.server.ThreadingHTTPServer(("0.0.0.0", port), SpaHandler).serve_forever()
