# _audit/inst_vs_dev_i3_na.py -- یکِ لحظه، دو بکاند: i3_pass برایِ ردیف‌هایِ بی‌حاشیه
import json, urllib.request, datetime

def get(port):
    u = f"http://127.0.0.1:{port}/api/screener"
    return json.load(urllib.request.urlopen(u, timeout=90))['data']

t = datetime.datetime.now().strftime('%H:%M:%S')
a = {r['symbol']: r for r in get(8001)}
b = {r['symbol']: r for r in get(8003)}
print('instant', t, 'installed rows', len(a), 'patched rows', len(b))
syms = ['وطوبي', 'اندوخته داريوش', 'شپلي', 'چاپ', 'نقره']
for s in syms:
    ra, rb = a.get(s), b.get(s)
    if not ra or not rb:
        print(s, 'MISSING', bool(ra), bool(rb)); continue
    fa = (ra['i1_pass'], ra['i2_pass'], ra['i3_pass'], ra['i4_pass'], ra['i5_pass'])
    fb = (rb['i1_pass'], rb['i2_pass'], rb['i3_pass'], rb['i4_pass'], rb['i5_pass'])
    print(f"{s}: inst(old)={fa} gm={ra.get('gross_margin')} patched={fb} gm={rb.get('gross_margin')} "
          f"applicable={ra.get('applicable')}/{rb.get('applicable')}")
bad_a = [s for s, r in a.items() if r['i3_pass'] is False and r.get('gross_margin') is None]
bad_b = [s for s, r in b.items() if r['i3_pass'] is False and r.get('gross_margin') is None]
na_true_a = [s for s, r in a.items() if r['i3_pass'] is True and r.get('gross_margin') is None]
print('installed i3=False&gm=None:', len(bad_a), '| dev same:', len(bad_b),
      '| i3=True&gm=None:', len(na_true_a))
