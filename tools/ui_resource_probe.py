# tools/ui_resource_probe.py -- سنجشِ CPU/رمِ بک‌اند زیرِ بارِ همیشگیِ تب‌ها
#
# چرا اینِ فایل هست (فاز F): مأموریت «اندازۀِ پیش وِ پس» می‌خواهد وِ «بی‌اندازه‌گیری
# ادعایِ درصد نکن». سمتِ مرورگر باِ همانِ `ui_tabs_probe.mjs` خوانده می‌شود (زمانِ
# ورودِ route، سرریزِ افقی، حجمِ chunkها) -- اینِ فایل سمتِ *سرور* را می‌خواند، چون
# «CPU/رم» درِ اینِ اپِ رومیزی یعنی همینِ پروسۀِ uvicorn که market.db را اسکن می‌کند.
#
# دامنه وِ حدِ صریح:
# · پروسه ازِ رویِ پورتِ نشستِ توسعه پیدا می‌شود (پیش‌فرض ۸۰۱۰)؛ هیچِ پروسه‌ای کشته
#   یاِ راه‌اندازی نمی‌شود -- فقطِ خواندنِ شمارنده‌ها.
# · هیچِ مسیرِ *نوشتاری* زده نمی‌شود: GET رویِ اندپوینت‌هایِ پنل. /api/funnel (POSTِ
#   ارزیابیِ FTS) عمداً بیرون است تاِ اینِ سنجش نتواند چیزی را تغییر دهد.
# · عددِ «درصدِ بهبود» ساخته نمی‌شود؛ تفاوتِ RSS وِ ثانیهٔ CPU گزارش می‌شود وِ
#   چرخشِ طبیعیِ خودِ ماشین درِ «تکرارِ بی‌بار» ثبت می‌شود تاِ خواننده بفهمد نویزِ
#   اندازه‌گیری چقدر بزرگ‌تر ازِ اثرِ هرِ تغییر است.
#
# اجرا:  .venv-ui/Scripts/python.exe tools/ui_resource_probe.py --port=8010
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    import psutil
except ImportError:  # بی‌سقوطِ بی‌سبب: پیامِ روشن، نه traceback خام
    sys.exit('psutil لازم است:  .venv-ui/Scripts/python.exe -m pip install psutil')

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / '_audit' / 'ui2' / 'resources.json'

# همانِ پنل‌هایی که «وضعیت بازار» + تابلو + تکنیکال می‌خوانند (سنجشِ فاز D: هرِ کدام
# کوئریِ مستقلِ خودش را دارد وِ اینِ دلیلِ ردِ `/api/mstat/board` هم هست)
PANELS = [
    '/api/mstat/summary', '/api/mstat/histogram', '/api/mstat/clientsplit',
    '/api/mstat/phases', '/api/mstat/mainwatch?group=all', '/api/mstat/industries',
    '/api/mstat/treemap', '/api/mstat/tops', '/api/mstat/orderflows',
    '/api/mstat/ownership', '/api/mstat/indexcards', '/api/mstat/gold',
    '/api/market', '/api/live-stats',
]
BOARD = '/api/mstat/board'


def server_pid(port: int):
    """PIDِ پروسه‌ای که رویِ 127.0.0.1:port گوش می‌دهد."""
    for c in psutil.net_connections(kind='inet'):
        if c.status == 'LISTEN' and c.laddr and c.laddr.port == port and c.pid:
            return psutil.Process(c.pid)
    raise SystemExit(f'پروسیه‌ای رویِ پورتِ {port} پیدا نشد (اپِ توسعه را بالا بیاور)')


def snap(p: psutil.Process) -> dict:
    with p.oneshot():
        cpu = p.cpu_times()
        return {
            'rssMb': round(p.memory_info().rss / 1048576, 1),
            'cpuSec': round(cpu.user + cpu.system, 3),
            'numThreads': p.num_threads(),
        }


def hit(base: str, path: str) -> dict:
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(base + path, timeout=90) as r:
            body = r.read()
            return {'path': path, 'status': r.status, 'bytes': len(body),
                    'ms': round((time.perf_counter() - t0) * 1000)}
    except urllib.error.HTTPError as e:
        return {'path': path, 'status': e.code, 'bytes': 0,
                'ms': round((time.perf_counter() - t0) * 1000)}
    except Exception as e:  # اتصال/تايم‌اوت -- همانِ چیزی که رابط هم می‌بیند
        return {'path': path, 'status': 'error', 'bytes': 0, 'why': str(e)[:120],
                'ms': round((time.perf_counter() - t0) * 1000)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8010)
    ap.add_argument('--host', default='http://127.0.0.1')
    ap.add_argument('--idle-seconds', type=float, default=5.0,
                    help='چرخشِ بی‌بار، برایِ دیدنِ نویزِ خودِ پیکربندیِ polling')
    args = ap.parse_args()
    base = f'{args.host}:{args.port}'

    p = server_pid(args.port)
    out = {'server': {'pid': p.pid, 'name': p.name(), 'cmdline': ' '.join(p.cmdline())[:180]},
           'port': args.port, 'viewport_note': 'سمتِ سرور؛ سمتِ مرورگر درِ tabs-*.json',
           'generatedAt': time.strftime('%Y-%m-%dT%H:%M:%S')}

    a = snap(p)
    # ۱) بارِ عادیِ تب‌ها (GET، بی‌مسیرِ نوشتاری)
    t0 = time.perf_counter()
    out['panels'] = [hit(base, x) for x in PANELS]
    out['panelsWallMs'] = round((time.perf_counter() - t0) * 1000)
    b = snap(p)
    out['afterPanels'] = b
    out['panelsDelta'] = {'rssMb': round(b['rssMb'] - a['rssMb'], 1),
                          'cpuSec': round(b['cpuSec'] - a['cpuSec'], 3)}

    # ۲) همانِ داده درِ یکِ بسته (دلیلِ عددیِ ردِ board درِ §۵ سندِ معماری)
    r = hit(base, BOARD)
    out['board'] = r
    c = snap(p)
    out['boardDelta'] = {'rssMb': round(c['rssMb'] - b['rssMb'], 1),
                         'cpuSec': round(c['cpuSec'] - b['cpuSec'], 3)}
    # مقایسه باید *هم‌سنجه* باشد: `/api/market` (ردیف‌هایِ کاملِ تابلو، ۶.۸ مگابایت درِ
    # هرِ پاسخ) وِ `/api/live-stats` درِ بستهٔ `board` نیستند؛ شمردنِ آن‌ها کنارِ
    # پنل‌ها، برابریِ حجم را بهِ «۰.۰۴×» نشان می‌داد وِ دروغِ محاسبه بود.
    ms = [x for x in out['panels'] if x['path'].startswith('/api/mstat')]
    out['boardVsPanels'] = {
        'bytes': {'board': r['bytes'], 'mstatPanels': sum(x['bytes'] for x in ms)},
        'bytesRatio': round(r['bytes'] / max(sum(x['bytes'] for x in ms), 1), 3),
        'serverMs': {'board': r['ms'], 'mstatPanelsSum': sum(x['ms'] for x in ms)},
        'roundTrips': {'board': 1, 'mstatPanels': len(ms)},
        'comparedSet': 'فقطِ ۱۲ پنلِ mstat (بدونِ /api/market وِ /api/live-stats که درِ بسته نیستند)',
    }

    # ۳) نویزِ_ground truth_: بی‌بار، فقطِ pollingِ خودِ سرور
    time.sleep(args.idle_seconds)
    d = snap(p)
    out['idleWindow'] = {'seconds': args.idle_seconds,
                         'cpuSec': round(d['cpuSec'] - c['cpuSec'], 3),
                         'rssMb': round(d['rssMb'] - c['rssMb'], 1)}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"server pid={p.pid} rss={a['rssMb']}MB threads={a['numThreads']}")
    print(f"panels: n={len(PANELS)} wall={out['panelsWallMs']}ms "
          f"Δrss={out['panelsDelta']['rssMb']}MB Δcpu={out['panelsDelta']['cpuSec']}s")
    print(f"board : status={r['status']} bytes={r['bytes']} ms={r['ms']} "
          f"Δrss={out['boardDelta']['rssMb']}MB Δcpu={out['boardDelta']['cpuSec']}s")
    ms = [x for x in out['panels'] if x['path'].startswith('/api/mstat')]
    tot = sum(x['bytes'] for x in ms)
    print(f"bytes : board={r['bytes']} vs {len(ms)} mstat panels={tot} "
          f"({round(r['bytes']/max(tot,1),2)}×)  [هم‌سنجه]")
    print(f"cpuSec: panels={out['panelsDelta']['cpuSec']} board={out['boardDelta']['cpuSec']} "
          f"| serverMs: panels={out['boardVsPanels']['serverMs']['mstatPanelsSum']} board={r['ms']}")
    print(f"idle  : +{args.idle_seconds}s بی‌بار Δcpu={out['idleWindow']['cpuSec']}s "
          f"Δrss={out['idleWindow']['rssMb']}MB  ← نویزِ مرجع")
    for x in out['panels']:
        if x['status'] != 200:
            print('  non-200:', x)
    print('written →', OUT.relative_to(REPO))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
