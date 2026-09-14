"""v2ray_rotator.py — pure-software IP rotation for Codal WAF 429 bans.

Chain: scrape public V2Ray subscriptions -> filter Iranian nodes (IR/Iran/
ایران/نیم بها/🇮🇷) -> generate xray config.json -> run xray.exe as a local
SOCKS5 proxy on 127.0.0.1:1080 -> health-check each config against
search.codal.ir -> rotate() kills xray and tries the next config until one
works. Rotation is transparent to the caller: the local port never changes,
only the upstream server does.

Design notes
------------
* Thread-safe: every public function goes through one RLock.
* Never raises: all entry points return bool/None; codal_fetcher must keep
  working even if xray/subscriptions are broken.
* xray.exe path: env V2RAY_XRAY_PATH -> known installs -> `xray.exe` in PATH.
* Pool: ir nodes first, then all others (feed IR quota is tiny; a fresh
  foreign IP beats a banned home IP). strict_ir flag can force IR-only.
"""

import base64
import json
import os
import queue
import random
import re
import socket
import sqlite3
import subprocess
import threading
import time
import urllib.parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "xray_config.json")
CACHE_DIR = os.path.join(BASE_DIR, ".v2cache")
# port 1080 may be blocked by Hyper-V/WSL excluded ranges (they MOVE
# dynamically — verified 10013 on 1080/2080/10880 within minutes) — pick the
# first bindable candidate so rotation works on any machine
def _resolve_port():
    cands = [1080, 2080, 10880, 28080, 38080, 47080, 57080]
    cands += [random.randint(20000, 50000) for _ in range(8)]
    for port in cands:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", port))
            s.close()
            return port
        except OSError:
            s.close()
            continue
    return 0


SOCKS_PORT = _resolve_port()
SOCKS_URL = f"socks5h://127.0.0.1:{SOCKS_PORT}"
TEST_URL = "https://search.codal.ir/"
MAX_TRIES_PER_ROTATE = 30
CACHE_TTL = 3 * 3600  # refetch subscriptions after 3 h
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

CHECKED_SOURCES = {   # pre-vetted domestic (MCI/Irancell/TCI) lists — trusted
    "https://raw.githubusercontent.com/sakha1370/OpenRay/refs/heads/main/output_iran/iran_top100_checked.txt",
    "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/IR.txt",
}

SOURCES = [
    # ✦ domestic intranet, auto-tested (hourly / auto-updated) — BEST first
    *CHECKED_SOURCES,
    # fresh daily global list (0 IR-name but short-lived foreign nodes)
    "https://raw.githubusercontent.com/0xRadikal/Free-v2ray-Configs/main/top100.txt",
    # جانشین زندهٔ TelegramV2rayCollector (originally yebekhe; repo removed)
    "https://raw.githubusercontent.com/Kwinshadow/TelegramV2rayCollector/main/sublinks/vless.txt",
    "https://raw.githubusercontent.com/Kwinshadow/TelegramV2rayCollector/main/sublinks/vmess.txt",
    "https://raw.githubusercontent.com/Kwinshadow/TelegramV2rayCollector/main/sublinks/mix.txt",
    "https://raw.githubusercontent.com/Kwinshadow/TelegramV2rayCollector/main/sublinks/b64mix.txt",
    # big global merges (vmess/trojan/ss; few IR labels but fresh IPs)
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/sub_merge.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/sub_merge_base64.txt",
    # original aggregator (may resurrect) — skipped silently if 404
    "https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/sub/normal/mix",
]

_LOCK = threading.RLock()
_xray_exe = None        # resolved once
_proc = None            # current xray subprocess (Popen or None)
_procs = []             # every xray this module started (killed on next fail)
_pool = []              # list of parsed config dicts (ir first)
_pool_ts = 0.0          # last refetch time
_rotating = False       # state flag (for status/logging)
_probe_ok = False
BAD_FILE = os.path.join(CACHE_DIR, "bad.json")
BAD_TTL = 12 * 3600     # connection-dead nodes: 12 h
LIMITED_TTL = 90 * 60   # alive but 429'd by codal: WAF lifts in 60-90 min
_bad = {}               # {"proto:host:port": expiry_ts}


def _fp(c):
    return f"{c['proto']}:{c.get('host')}:{c.get('port')}"


def _load_bad():
    global _bad
    try:
        with open(BAD_FILE, encoding="utf-8") as f:
            _bad = json.load(f)
    except Exception:
        _bad = {}


def _mark_bad(c, ttl=BAD_TTL):
    _bad[_fp(c)] = time.time() + ttl
    try:
        with open(BAD_FILE, "w", encoding="utf-8") as f:
            json.dump(_bad, f)
    except Exception:
        pass


def _is_bad(c):
    exp = _bad.get(_fp(c), 0)
    return bool(exp) and time.time() < exp


def _forget_old_bad():
    now = time.time()
    for k in list(_bad):
        if _bad[k] < now:
            del _bad[k]


GOOD_FILE = os.path.join(CACHE_DIR, "good.json")
GOOD_MAX = 8


def _load_good():
    """Known-working config dicts (most recent first); best effort."""
    try:
        with open(GOOD_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return [c for c in data
                if isinstance(c, dict) and c.get("proto") and c.get("host")
                and c.get("port")]
    except Exception:
        return []


def _save_good(c):
    try:
        key = _fp(c)
        good = [g for g in _load_good() if _fp(g) != key]
        good.insert(0, c)
        with open(GOOD_FILE, "w", encoding="utf-8") as f:
            json.dump(good[:GOOD_MAX], f, ensure_ascii=False)
    except Exception:
        pass


# ------------------------------------------------------------------ helpers


def _log(msg):
    print(f"  [v2ray] {msg}", flush=True)


def find_xray():
    """Locate xray.exe once. Returns absolute path or None."""
    global _xray_exe
    if _xray_exe:
        return _xray_exe
    cands = []
    env = os.environ.get("V2RAY_XRAY_PATH")
    if env:
        cands.append(env)
    cands += [
        os.path.join(BASE_DIR, "bin", "xray", "xray.exe"),
        r"E:\Downloads\Compressed\v2rayN-windows-64\v2rayN-windows-64\bin\xray\xray.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "v2rayN",
                     "bin", "xray", "xray.exe"),
    ]
    for c in cands:
        if c and os.path.isfile(c):
            _xray_exe = c
            return c
    # cross-platform: shutil.which روی ویندوز xray.exe را در PATH پیدا میکند
    # (جایگزین `where xray.exe` که لینوکس/اندروید آن را ندارد)
    hit = shutil.which("xray") or shutil.which("xray.exe")
    if hit:
        _xray_exe = hit
        return hit
    return None


def is_available():
    return find_xray() is not None


# ------------------------------------------------------ URI parsing (pure)


def _pct(s):
    try:
        return urllib.parse.unquote(s or "")
    except Exception:
        return s or ""


def _norm_sni(sni, host_addr):
    """xray 26 verifies TLS by default (allowInsecure removed) — a bad
    serverName kills the handshake. Subs often stuff brand strings into the
    `host=` param (e.g. 'MTMVPN--MTMVPN--MTMVPN') — not a valid domain →
    fall back to the server hostname, whose cert actually covers it."""
    if not sni:
        return host_addr or ""
    if "--" in sni or not re.search(r"\.[a-zA-Z]{2,}$", sni):
        return host_addr or sni
    return sni


def _ir_match(name):
    """Iranian-node keyword match on the decoded config name."""
    n = _pct(name or "")
    # [یي] covers Persian yeh U+06CC and Arabic yeh U+064A; [ن] harmless
    return bool(re.search(
        r"(?i)(\bIR\b|IR-|iran|ا[یي]را[نن]|[نن][یي]م ?بها|نيمبها)"
        r"|\U0001F1EE\U0001F1F7"          # 🇮🇷 raw emoji
        r"|%F0%9F%87%AE%F0%9F%87%B7", n))


OWN_DB_CANDIDATES = [
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "v2rayN",
                 "guiConfigs", "guiNDB.db"),
    os.path.join(os.path.expanduser("~"), ".v2rayN",
                 "guiConfigs", "guiNDB.db"),
    r"E:\Downloads\Compressed\v2rayN-windows-64\v2rayN-windows-64"
    r"\guiConfigs\guiNDB.db",
]


def _own_servers():
    """User's live panel nodes from the v2rayN guiNDB.db profile store.

    ConfigType: 5=vless, 6=trojan. Rows whose address is still the unresolved
    placeholder (127.0.0.1 / 0.0.0.0) are skipped. Returns [] on any failure —
    best effort, never raises."""
    for db in OWN_DB_CANDIDATES:
        if not (db and os.path.isfile(db)):
            continue
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            rows = con.execute(
                "SELECT ConfigType, Address, Port, Id, Network, Remarks, "
                "RequestHost, Path, StreamSecurity, Sni, Alpn "
                "FROM ProfileItem").fetchall()
            con.close()
        except Exception:
            continue
        out = []
        for ct, addr, port, cid, net, name, rhost, path, sec, sni, alpn in rows:
            if not addr or addr in ("127.0.0.1", "0.0.0.0") or not port:
                continue
            if ct == 5:
                c = {"proto": "vless", "host": addr, "port": port,
                     "id": cid or "", "enc": "none", "net": net or "tcp",
                     "security": sec or "none", "sni": sni or rhost or "",
                     "alpn": alpn or ""}
            elif ct == 6:
                c = {"proto": "trojan", "host": addr, "port": port,
                     "password": cid or "", "net": net or "tcp",
                     "security": sec or "tls", "sni": sni or rhost or addr,
                     "alpn": alpn or ""}
            else:
                continue
            c["name"] = (f"👤 {name}" if name else f"👤 {addr}")[:60]
            c["host_hdr"] = rhost or ""
            c["path"] = path or "/"
            c["checked"] = True
            c["own"] = True
            out.append(c)
        if out:
            _log(f"own panel nodes: {len(out)}")
            return out
    return []


def parse_uri(uri):
    """Parse vless/vmess/trojan/ss URI into a flat dict, or None."""
    uri = uri.strip()
    try:
        if uri.startswith("vless://"):
            return _parse_vless(uri)
        if uri.startswith("vmess://"):
            return _parse_vmess(uri)
        if uri.startswith("trojan://"):
            return _parse_trojan(uri)
        if uri.startswith("ss://"):
            return _parse_ss(uri)
    except Exception:
        return None
    return None


def _parse_vless(uri):
    u = urllib.parse.urlparse(uri)
    q = urllib.parse.parse_qs(u.query)
    g = lambda k: (q.get(k) or [""])[0]  # noqa: E731
    return {
        "proto": "vless", "name": _pct(u.fragment), "host": u.hostname or "",
        "port": u.port or 443, "id": (u.username or "").strip(),
        "enc": g("encryption") or "none", "flow": g("flow"),
        "net": g("type") or "tcp", "security": g("security") or "none",
        "sni": _norm_sni(g("sni") or g("host"), u.hostname or ""),
        "host_hdr": g("host"), "path": g("path"),
        "fp": g("fp") or "chrome", "alpn": g("alpn"),
        "pbk": g("pbk"), "sid": g("sid"), "spx": g("spx"),
    }


def _parse_vmess(uri):
    raw = uri[len("vmess://"):]
    raw = raw.split("#")[0]  # base64 part only (name kept separately below)
    name = _pct(urllib.parse.urlparse(uri).fragment)
    try:
        j = json.loads(base64.b64decode(raw + "=" * (-len(raw) % 4)))
    except Exception:
        j = {}
    return {
        "proto": "vmess", "name": name or j.get("ps", ""),
        "host": str(j.get("add", "")), "port": int(j.get("port", 443) or 443),
        "id": str(j.get("id", "")), "aid": int(j.get("aid", 0) or 0),
        "net": str(j.get("net", "tcp")), "security": str(j.get("tls", "none")),
        "sni": _norm_sni(str(j.get("sni", "") or j.get("host", "")),
                         str(j.get("add", ""))),
        "host_hdr": str(j.get("host", "")), "path": str(j.get("path", "")),
        "fp": str(j.get("fp", "chrome")),
    }


def _parse_trojan(uri):
    u = urllib.parse.urlparse(uri)
    q = urllib.parse.parse_qs(u.query)
    g = lambda k: (q.get(k) or [""])[0]  # noqa: E731
    return {
        "proto": "trojan", "name": _pct(u.fragment), "host": u.hostname or "",
        "port": u.port or 443, "password": (u.username or ""),
        "net": "tcp", "security": g("security") or "tls",
        "sni": g("sni") or g("host"), "fp": g("fp") or "chrome",
    }


def _parse_ss(uri):
    rest = uri[len("ss://"):]
    name = _pct(urllib.parse.urlparse(uri).fragment)
    scheme, _, frag = rest.partition("#")
    userinfo, sep, addr = scheme.rpartition("@")
    if sep and "@" not in userinfo[:0]:
        # method:password@host:port (plain) — decode if base64
        try:
            dec = base64.b64decode(userinfo + "=" * (-len(userinfo) % 4))
            if b":" in dec and b"@" not in dec:
                userinfo, addr = dec.decode("utf-8", "ignore"), addr
        except Exception:
            pass
        method, _, pw = userinfo.partition(":")
    else:
        # full base64 (SIP002)
        try:
            dec = base64.b64decode(rest.split("#")[0] + "=" * (-len(rest) % 4))
            s = dec.decode("utf-8", "ignore")
            userinfo, _, addr = s.partition("@")
            method, _, pw = userinfo.partition(":")
        except Exception:
            return None
    if not method or not pw:
        return None
    host, _, port = addr.partition(":")
    return {"proto": "ss", "name": name, "host": host, "port": int(port or 443),
            "method": method, "password": pw}


# ------------------------------------------------------- subscription fetch


def fetch_subscriptions(fresh=False):
    """Scrape all sources, parse URIs, order IR-first. Returns list of dicts."""
    global _pool, _pool_ts
    with _LOCK:
        if not fresh and _pool and (time.time() - _pool_ts) < CACHE_TTL:
            return _pool
        _load_bad()
        os.makedirs(CACHE_DIR, exist_ok=True)
        lines = []
        for url in SOURCES:
            checked = url in CHECKED_SOURCES
            try:
                import requests
                r = requests.get(url, timeout=25, headers={"User-Agent": UA})
                if r.status_code != 200:
                    continue
                body = r.text.strip()
                if not body:
                    continue
                # base64 blob? -> decode; else plain URI list
                probe = body.splitlines()[0]
                if re.fullmatch(r"[A-Za-z0-9+/=]{40,}", probe.replace(" ", "")):
                    try:
                        dec = base64.b64decode(body + "=" * (-len(body) % 4))
                        body = dec.decode("utf-8", "ignore")
                    except Exception:
                        pass
                lines += [(l.strip(), checked)
                          for l in body.splitlines() if l.strip()]
            except Exception as e:
                _log(f"source {url.split('/')[-1]}: {type(e).__name__}")
        seen, pool, ir = set(), [], []
        for l, checked in lines:
            if l.startswith("vless://") or l.startswith("vmess://") or \
               l.startswith("trojan://") or l.startswith("ss://"):
                if l[:120] in seen:
                    continue
                seen.add(l[:120])
                p = parse_uri(l)
                if p and p.get("host") and p.get("port"):
                    if checked:
                        p["checked"] = True
                    (ir if _ir_match(p.get("name", "")) else pool).append(p)
        # checked (domestic vetted) + own panel nodes at the very front;
        # shuffle both so random sampling spreads over the pool
        checked_list = [c for c in ir + pool if c.get("checked")]
        own = _own_servers()
        rest = [c for c in ir + pool if not c.get("checked")]
        random.shuffle(checked_list)
        random.shuffle(rest)
        _pool = own + checked_list + rest   # own panel + vetted domestic first
        _pool_ts = time.time()
        _log(f"pool: {len(_pool)} configs ({len(own)} own+{len(checked_list)} "
             f"checked-domestic, {len(ir)} IR-name) from {len(SOURCES)} sources")
        return _pool


# ---------- hang-proof subprocess runner -----------------------------
# Get-NetTCPConnection / Stop-Process on a wedged socket table can hang a
# powershell child in an uninterruptible wait: subprocess.run's own kill+
# wait() path then blocks forever (2026-08-26, 9-minute wedge). This runs
# the child in a daemon thread; if it does not return, the caller gets
# None while the child thread leaks (bounded by _HANG_THREADS).
_HANG_THREADS = [0]  # live (possibly wedged) bounded-run threads


def _run_bounded(cmd, timeout=15):
    if _HANG_THREADS[0] >= 3:
        return None  # already leaking too many wedged children - no more
    q = queue.Queue(maxsize=1)

    def _go():
        _HANG_THREADS[0] += 1
        try:
            try:
                q.put(subprocess.run(cmd, capture_output=True, text=True,
                                     timeout=timeout))
            except Exception as e:
                q.put(e)
        finally:
            _HANG_THREADS[0] -= 1

    t = threading.Thread(target=_go, daemon=True)
    t.start()
    try:
        r = q.get(timeout=timeout + 10)
    except queue.Empty:
        return None  # child wedged - drop it, never block the scan
    return None if isinstance(r, Exception) else r



# ------------------------------------------------------------- xray process


def _port_owner(port=None):
    try:
        out = _run_bounded(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-NetTCPConnection -LocalPort {port or SOCKS_PORT} -State Listen "
             f"-ErrorAction SilentlyContinue | Select-Object -First 1)"
             f".OwningProcess"])
        if out is None:
            return None
        txt = (out.stdout or "").strip()
        return int(txt) if txt.isdigit() else None
    except Exception:
        return None


def snapshot():
    """Read-only status for the UI. NEVER starts xray and NEVER probes Codal
    (zero extra traffic — a probe per UI poll would eat the node's budget).

    mode = 'node'   → xray.exe owns the inbound port of xray_config.json
           'direct' → config exists but nothing listening (HTTP goes direct)
           'idle'   → no config at all
    upstream = host:port of the current outbound (the node in use).
    ban_lift = HH:MM of the nearest short-TTL (LIMITED => 429-window) expiry,
               i.e. when a WAF-banned node becomes usable again.
    """
    with _LOCK:
        cfg = None
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
        upstream = ""
        running = False
        if cfg:
            port = None
            try:
                port = cfg["inbounds"][0].get("port")
            except Exception:
                pass
            if port:
                running = _port_owner(port) is not None
            try:
                for ob in cfg.get("outbounds", []):
                    vn = (ob.get("settings", {}) or {}).get("vnext")
                    if vn:
                        upstream = f"{vn[0].get('address', '')}:{vn[0].get('port', '')}"
                        break
            except Exception:
                pass
        now = time.time()
        lifts = []
        for e in (_load_bad() or {}).values():
            try:
                e = float(e)
            except Exception:
                continue
            if now < e <= now + 2.5 * 3600:
                lifts.append(e)
        return {
            "mode": "node" if running else ("direct" if cfg else "idle"),
            "upstream": upstream,
            "ban_lift": time.strftime("%H:%M", time.localtime(min(lifts))) if lifts else "",
            "good": len(_load_good() or []),
            "bad": len(_load_bad() or {}),
        }


def _kill_xray():
    """Kill every xray this module started + any process owning our SOCKS
    port (never the user's v2rayN, which listens on other ports/processes)."""
    global _proc
    pid = _port_owner()
    if pid:
        try:
            _run_bounded(["powershell", "-NoProfile", "-Command",
                          f"Stop-Process -Id {pid} -Force"])
            _log(f"killed stale xray pid {pid}")
        except Exception:
            pass
    for p in _procs:
        if p and p.poll() is None:
            try:
                p.terminate()
                p.wait(timeout=4)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
    _procs.clear()
    _proc = None


def _start_xray(config):
    """Start xray.exe -c config; returns True if the process is alive."""
    global _proc
    exe = find_xray()
    if not exe:
        _log("xray.exe not found")
        return False
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        _proc = subprocess.Popen(
            [exe, "-c", CONFIG_PATH], creationflags=flags,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _procs.append(_proc)
    except Exception as e:
        _log(f"cannot start xray: {e}")
        _proc = None
        return False
    # wait for the SOCKS listener
    for _ in range(8):
        time.sleep(0.5)
        if _proc.poll() is not None:
            _log("xray exited immediately (bad config)")
            return False
        try:
            with socket.create_connection(("127.0.0.1", SOCKS_PORT), 0.6):
                return True
        except OSError:
            continue
    return False


class RotatorStop(BaseException):
    """User stopped the scan (dashboard توقف/مکث via codal_control.json).
    BaseException: no `except Exception` in this module may swallow it."""


def _user_stop():
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "codal_control.json"), encoding="utf-8") as f:
            return (json.load(f).get("cmd") or "").strip().lower() in ("stop", "pause")
    except Exception:
        return False


def _tcp_alive(c, timeout=1.2):
    if _user_stop():
        raise RotatorStop()
    """Cheap pre-filter: dead IPs (TCP refused/unreachable) skip xray
    startup entirely. DNS hosts resolve via the system resolver."""
    try:
        with socket.create_connection((c.get("host"), int(c.get("port") or 0)),
                                      timeout):
            return True
    except Exception:
        return False


def _probe_via_proxy(timeout=9):
    if _user_stop():
        raise RotatorStop()
    """'ok' | 'limited' (node alive but codal throttles its IP) | 'dead'."""
    try:
        import requests
        r = requests.get(TEST_URL,
                         proxies={"http": SOCKS_URL, "https": SOCKS_URL},
                         headers={"User-Agent": UA}, timeout=timeout)
        if r.status_code < 400:
            return "ok"
        if r.status_code == 429:
            _log("proxy HTTP 429 (alive, IP limited)")
            return "limited"
        _log(f"proxy returned HTTP {r.status_code}")
        return "limited"
    except Exception as e:
        _log(f"proxy test failed: {type(e).__name__}")
        return "dead"


# ------------------------------------------------------------- config gen


def _stream_settings(c):
    """xray streamSettings for the parsed config `c`."""
    st = {"network": c.get("net") or "tcp"}
    sec = c.get("security") or "none"
    if sec == "reality":
        st["security"] = "reality"
        st["realitySettings"] = {
            "serverName": c.get("sni") or c.get("host_hdr") or "",
            "publicKey": c.get("pbk", ""), "shortId": c.get("sid", ""),
            "fingerprint": c.get("fp", "chrome"),
        }
    elif sec and sec != "none":
        st["security"] = sec
        st["tlsSettings"] = {
            "serverName": c.get("sni") or c.get("host_hdr") or "",
            "fingerprint": c.get("fp", "chrome"),
        }
        if c.get("alpn"):
            st["tlsSettings"]["alpn"] = [x.strip() for x in c["alpn"].split(",")
                                         if x.strip()]
    net = c.get("net")
    if net == "ws":
        st["wsSettings"] = {
            "path": c.get("path") or "/",
            "headers": {"Host": c.get("host_hdr") or c.get("host") or ""},
        }
    elif net in ("grpc", "gun"):
        st["grpcSettings"] = {
            "serviceName": c.get("path", "").lstrip("/") or "GunService"}
        st["network"] = "grpc"
    elif net == "kcp":
        st["kcpSettings"] = {"header": {"type": "none"}}
    elif net != "tcp":
        st["network"] = "tcp"
    return st


def gen_config(c):
    """Generate an xray config.json dict for the parsed config `c` (vless-first)."""
    proto = c["proto"]
    if proto == "vless":
        user = {"id": c.get("id", ""), "encryption": c.get("enc") or "none"}
        if c.get("flow"):
            user["flow"] = c["flow"]
        out = {"protocol": "vless",
               "settings": {"vnext": [{"address": c["host"], "port": c["port"],
                                       "users": [user]}]}}
    elif proto == "vmess":
        out = {"protocol": "vmess",
               "settings": {"vnext": [{"address": c["host"], "port": c["port"],
                                       "users": [{"id": c.get("id", ""),
                                                  "alterId": c.get("aid", 0),
                                                  "security": "auto"}]}]}}
    elif proto == "trojan":
        out = {"protocol": "trojan",
               "settings": {"servers": [{"address": c["host"],
                                         "port": c["port"],
                                         "password": c.get("password", "")}]}}
    else:  # ss
        out = {"protocol": "shadowsocks",
               "settings": {"servers": [{"address": c["host"], "port": c["port"],
                                         "method": c.get("method", ""),
                                         "password": c.get("password", "")}]}}
    out["streamSettings"] = _stream_settings(c)
    cfg = {
        "log": {"loglevel": "warning"},
        "inbounds": [{"listen": "127.0.0.1", "port": SOCKS_PORT,
                      "protocol": "socks",
                      "settings": {"udp": True, "auth": "noauth"},
                      "sniffing": {"enabled": True,
                                   "destOverride": ["http", "tls"]}}],
        "outbounds": [out,
                      {"protocol": "freedom", "tag": "direct"}],
    }
    return cfg


def _port_bindable(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        s.close()
        return True
    except OSError:
        s.close()
        return False


def _fix_port():
    """Guarantee a bindable SOCKS_PORT (excluded ranges move dynamically)."""
    global SOCKS_PORT, SOCKS_URL
    if not SOCKS_PORT or not _port_bindable(SOCKS_PORT):
        p = _resolve_port()
        if not p:
            return False
        SOCKS_PORT = p
        SOCKS_URL = f"socks5h://127.0.0.1:{p}"
    return True


def _write_config(cfg):
    if not _fix_port():
        raise RuntimeError("no bindable local port")
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    os.replace(tmp, CONFIG_PATH)


# ------------------------------------------------------------- rotate API


def rotate(force_fetch=False):
    """Kill xray, start the next config, verify against search.codal.ir.
    Sampling: up to 3 untried IR nodes first, then random untried configs
    (max MAX_TRIES_PER_ROTATE); known-dead nodes (bad-list) are skipped for
    12 h. Tries a fresh refetch once at the end. Never raises."""
    global _rotating, _pool, _pool_ts
    with _LOCK:
        _rotating = True
        try:
            # known-good nodes first (fast path after a WAF ban)
            for c in _load_good():
                if _is_bad(c):
                    continue
                if not _tcp_alive(c):
                    _mark_bad(c)
                    continue
                _write_config(gen_config(c))
                if not _start_xray(c):
                    _kill_xray()
                    _mark_bad(c)
                    continue
                st = _probe_via_proxy()
                if st == "ok":
                    _log(f"OK (good-cache) via {c['proto']} "
                         f"{c.get('name', '')[:40]} @ {c.get('host')}:{c.get('port')}")
                    return True
                _kill_xray()
                _mark_bad(c, LIMITED_TTL if st == "limited" else BAD_TTL)
                _log(f"good-cache stale({st}): {c['proto']} "
                     f"{c.get('name', '')[:40]} @ {c.get('host')}:{c.get('port')}")
            for rnd in (0, 1):
                cands = fetch_subscriptions(fresh=force_fetch or rnd == 1)
                cands = [c for c in cands if not _is_bad(c)]
                if not cands:
                    _forget_old_bad()
                    cands = [c for c in fetch_subscriptions(fresh=True)
                             if not _is_bad(c)]
                    if not cands:
                        _log("empty pool after bad-filter")
                        return False
                ir = [c for c in cands if not c.get("checked")
                      and _ir_match(c.get("name", ""))]
                own_in = [c for c in cands if c.get("own")]
                checked = [c for c in cands if c.get("checked")
                           and not c.get("own")]
                rest = [c for c in cands if not c.get("checked")
                        and not _ir_match(c.get("name", ""))]
                ir_rest = ir + rest
                random.shuffle(checked)
                random.shuffle(ir_rest)
                # interleave IR/foreign with checked so a live node in ANY
                # bucket is found within a handful of tries (checked-only
                # ordering burns all tries on dead vetted nodes first)
                inter = []
                for i in range(max(len(checked), len(ir_rest))):
                    if i < len(checked):
                        inter.append(checked[i])
                    if i < len(ir_rest):
                        inter.append(ir_rest[i])
                order = (own_in + inter)[:MAX_TRIES_PER_ROTATE]
                for c in order:
                    if not _tcp_alive(c):
                        _mark_bad(c)
                        continue
                    _write_config(gen_config(c))
                    if not _start_xray(c):
                        _kill_xray()
                        _mark_bad(c)
                        continue
                    st = _probe_via_proxy()
                    if st == "ok":
                        _log(f"OK via {c['proto']} {c.get('name', '')[:40]} "
                             f"@ {c.get('host')}:{c.get('port')}")
                        _save_good(c)
                        return True
                    _kill_xray()
                    _mark_bad(c, LIMITED_TTL if st == "limited" else BAD_TTL)
                    _log(f"bad({st}): {c['proto']} {c.get('name', '')[:40]}")
                # round exhausted -> refetch (fresh shuffle) once more
                _kill_xray()
                _pool = []
                _pool_ts = 0.0
            return False
        finally:
            _rotating = False


def ensure_running():
    """Idempotent: if the local proxy already answers, True; else try the
    last-written config once (fast), then full rotate()."""
    with _LOCK:
        if _port_owner() is not None and _probe_via_proxy(timeout=8) == "ok":
            return True
        if os.path.isfile(CONFIG_PATH):
            try:
                if _start_xray(None) and _probe_via_proxy(timeout=12) == "ok":
                    return True
                _kill_xray()
            except Exception:
                pass
        return rotate()


def status():
    return {"available": is_available(), "running": bool(_port_owner()),
            "rotating": _rotating, "pool": len(_pool),
            "xray": _xray_exe}


# ------------------------------------------------------------------- CLI

if __name__ == "__main__":
    import sys
    if "--list" in sys.argv:
        _pool = fetch_subscriptions(fresh=True)
        for c in _pool[:20]:
            print(f"  {c['proto']:6s} {c.get('name', '')[:40]:42s} "
                  f"{c['host']}:{c['port']}")
        print(f"... total {len(_pool)}")
    elif "--rotate" in sys.argv:
        ok = rotate(force_fetch=True)
        print(f"ROTATE {'OK' if ok else 'FAILED'}")
    elif "--status" in sys.argv:
        print(json.dumps(status(), ensure_ascii=False))
    elif "--gen" in sys.argv and len(sys.argv) > 2:
        p = parse_uri(sys.argv[2])
        if p:
            print(json.dumps(gen_config(p), indent=2, ensure_ascii=False))
        else:
            print("UNPARSEABLE")
    else:
        print(__doc__)
