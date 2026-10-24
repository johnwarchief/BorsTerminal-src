#!/usr/bin/env python3
"""Static server + same-origin /api proxy for the M1 desktop prototype.

Why a proxy instead of calling the backend cross-origin: the production shell
(and its loopback_guard) accepts only 127.0.0.1/localhost origins. Serving the
prototype from this loopback origin keeps the security contract identical to
the shipped app and needs no CORS relaxation.

usage:
  python tools/desktop-migration/serve_prototype.py \
      --root frontend/prototype/dist --backend http://127.0.0.1:8102 --port 8105
"""
from __future__ import annotations

import argparse
import http.client
import mimetypes
import os
import posixpath
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("font/ttf", ".ttf")

ARGS = None
BACKEND = None
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _host_ok(value: str | None) -> bool:
    if not value:
        return False
    try:
        return (urlsplit("//" + value).hostname or "").lower() in LOOPBACK_HOSTS
    except ValueError:
        return False


def _origin_ok(value: str | None) -> bool:
    # Same contract as app.loopback_guard: absent Origin is allowed (native
    # GETs), but "null" and every non-loopback origin are rejected. The proxy
    # must enforce this itself because it rewrites Host for the upstream call.
    if not value:
        return True
    try:
        parts = urlsplit(value)
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and (parts.hostname or "").lower() in LOOPBACK_HOSTS


class Handler(BaseHTTPRequestHandler):
    server_version = "BorsProto/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # keep the console usable
        return

    def _guard(self) -> bool:
        if _host_ok(self.headers.get("Host")) and _origin_ok(self.headers.get("Origin")):
            return True
        msg = b'{"status":"forbidden","message":"loopback host/origin required"}'
        self.send_response(403)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(msg)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(msg)
        return False

    def _proxy(self):
        up = urlsplit(BACKEND)
        conn = http.client.HTTPConnection(up.hostname, up.port or 80, timeout=180)
        body = None
        length = self.headers.get("Content-Length")
        if length:
            body = self.rfile.read(int(length))
        headers = {}
        for key in ("Accept", "Accept-Encoding", "Content-Type", "Origin", "User-Agent"):
            val = self.headers.get(key)
            if val:
                headers[key] = val
        headers["Host"] = f"{up.hostname}:{up.port or 80}"
        t0 = time.perf_counter()
        try:
            conn.request(self.command, self.path, body=body, headers=headers)
            resp = conn.getresponse()
            payload = resp.read()
        except Exception as exc:  # backend down: report honestly
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            msg = ('{"status":"error","message":"prototype proxy: backend unavailable (%s)"}'
                   % str(exc).replace('"', "'")).encode("utf-8")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(msg)
            return
        finally:
            conn.close()
        self.send_response(resp.status)
        for key, val in resp.getheaders():
            if key.lower() in ("transfer-encoding", "connection", "content-length", "server", "date"):
                continue
            self.send_header(key, val)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)
        sys.stderr.write("[proxy] %.3f %s %s -> %s %dms\n" % (
            time.time(), self.command, self.path, resp.status,
            (time.perf_counter() - t0) * 1000))

    def _static(self, path):
        root = os.path.realpath(ARGS.root)
        rel = unquote(path).lstrip("/")
        target = os.path.realpath(os.path.join(root, rel))
        if not (target == root or target.startswith(root + os.sep)):
            self.send_error(403)
            return
        if os.path.isdir(target):
            target = os.path.join(target, "index.html")
        if not os.path.isfile(target):
            if "." not in posixpath.basename(path):
                target = os.path.join(root, "index.html")
                if not os.path.isfile(target):
                    self.send_error(404)
                    return
            else:
                self.send_error(404)
                return
        with open(target, "rb") as fh:
            payload = fh.read()
        ctype = mimetypes.guess_type(target)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text/") or "javascript" in ctype or "json" in ctype else ""))
        self.send_header("Content-Length", str(len(payload)))
        if "/assets/" in path and "." in posixpath.basename(path):
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        else:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def do_GET(self):
        if not self._guard():
            return
        if self.path.startswith("/api/"):
            self._proxy()
        else:
            self._static(self.path.split("?", 1)[0])

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        if not self._guard():
            return
        if self.path.startswith("/api/"):
            self._proxy()
        else:
            self.send_error(405)


def main():
    global ARGS, BACKEND
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--backend", default="http://127.0.0.1:8102")
    ap.add_argument("--port", type=int, default=8105)
    ARGS = ap.parse_args()
    BACKEND = ARGS.backend.rstrip("/")
    if not os.path.isdir(ARGS.root):
        raise SystemExit(f"dist not found: {ARGS.root} (run the prototype build first)")
    srv = ThreadingHTTPServer(("127.0.0.1", ARGS.port), Handler)
    srv.daemon_threads = True
    print(f"prototype server: http://127.0.0.1:{ARGS.port}/  backend={BACKEND}  root={ARGS.root}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
