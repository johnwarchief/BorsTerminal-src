# -*- coding: utf-8 -*-
"""Local sink for the in-page Rahavard scanner. Stores bars only; no auth material.

Run:
  python tools/ra365_ingest_server.py --port 8791 --dir _scratch/ra365 --targets _scratch/scan_targets.json

Endpoints (CORS-limited to https://rahavard365.com):
  GET  /targets   -> [asset_id, ...] from --targets
  GET  /done      -> [series_key, ...] already ingested
  GET  /          -> progress counters
  POST /ingest    -> one JSON line {key, asset_id, type, res, status, bars, error}
"""
import argparse, json, os, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ARGS = None
LOCK = threading.Lock()
STATE = {"series": 0, "bars": 0, "keys": [], "errors": []}
STATE_PATH = None


def save_state():
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(STATE, fh, ensure_ascii=False)
    os.replace(tmp, STATE_PATH)


class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "https://rahavard365.com")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Max-Age", "600")

    def _json(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors()
        self.end_headers()
        self.wfile.write(json.dumps(body, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/targets":
            try:
                tg = json.load(open(ARGS.targets, encoding="utf-8"))["targets"]
                return self._json(200, [t["asset_id"] for t in tg])
            except Exception:
                return self._json(200, [])
        if path == "/done":
            return self._json(200, STATE["keys"])
        return self._json(200, {"series": STATE["series"], "bars": STATE["bars"],
                                "n_keys": len(STATE["keys"]), "errors": STATE["errors"][-8:]})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            item = json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception as e:
            return self._json(400, {"ok": False, "error": str(e)[:120]})
        key = item.get("key")
        with LOCK:
            with open(os.path.join(ARGS.dir, "ref_bars.jsonl"), "a", encoding="utf-8") as fh:
                fh.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
            if key:
                STATE["keys"].append(key)
            STATE["series"] += 1
            STATE["bars"] += len(item.get("bars") or [])
            if item.get("error"):
                STATE["errors"].append({"key": key, "error": str(item["error"])[:160]})
            if STATE["series"] % 5 == 0:
                save_state()
        return self._json(200, {"ok": True})


def main():
    global ARGS, STATE_PATH
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--targets", required=True)
    ARGS = ap.parse_args()
    os.makedirs(ARGS.dir, exist_ok=True)
    STATE_PATH = os.path.join(ARGS.dir, "ingest_state.json")
    if os.path.exists(STATE_PATH):
        try:
            STATE.update(json.load(open(STATE_PATH, encoding="utf-8")))
        except Exception:
            pass
    print(f"listening on 127.0.0.1:{ARGS.port}; dir={ARGS.dir}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", ARGS.port), H).serve_forever()


if __name__ == "__main__":
    main()
