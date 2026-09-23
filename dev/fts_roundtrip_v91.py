"""v9.1 — round-trip the FTS threshold save path used by «💾 ذخیره و اعمال»."""
import io, json, os, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 'http://127.0.0.1:8012'
OUT = []

def req(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(BASE + path, data=data,
                               headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(r, timeout=40) as resp:
        return json.loads(resp.read().decode('utf-8'))

def ck(c, m): OUT.append(('  OK   ' if c else '  FAIL ') + m); return c

orig = req('/api/fts/config')['config']
OUT.append('initial: growth_min=%s margin_min=%s sales_to_mcap_min=%s eps_years=%s industry_mode=%s'
           % (orig['growth_min'], orig['margin_min'], orig['sales_to_mcap_min'],
              orig['eps_years'], orig['industry_mode']))
# v9.7: دو کلید جدید باید از همان مسیرِ قبلی رد شوند — نبودشان یعنی گاردِ
# «k not in FTS_DEFAULTS» در set_fts_config آن‌ها را دور انداخته است.
ck('filter_m141' in orig, 'filter_m141 exposed by GET /api/fts/config')
ck('min_trade_val' in orig, 'min_trade_val exposed by GET /api/fts/config')

# همان مجموعه‌ای که saveFtsConfig() می‌فرستد
patch = {'growth_min': 41.0, 'v10_monetary_growth_min': 61.0, 'eps_years': 4, 'margin_min': 21.0,
         'margin_optimal': 31.0, 'sales_to_mcap_min': 1.1, 'profit_potential_min': 31.0,
         'mcap_min_hmt': 1.0, 'watchlist_max': 51, 'suspended_max_stale_sessions': 4,
         'min_trade_val': 2.5, 'filter_m141': True,
         'industry_mode': 'Rank_Only',
         'mandatory_sectors': 'خودرو، دارو، آزمایشی', 'free_sectors': 'سیمان، آزمایشی-آزاد'}
res = req('/api/fts/config', patch)
ck(res.get('status') == 'success', 'POST /api/fts/config accepted: %s' % res.get('status'))

back = req('/api/fts/config')['config']
for k, want in patch.items():
    got = back.get(k)
    if k in ('mandatory_sectors', 'free_sectors'):
        got_s, want_s = '، '.join(got or []), want      # بک‌اند رشته را به لیست تبدیل میکند
    else:
        got_s, want_s = got, want
    ck(str(got_s) == str(want_s), 'persisted %s = %s (got %s)' % (k, want, got_s))

# بازگرداندن مقادیر اصلی
res2 = req('/api/fts/config', {k: (v if not isinstance(v, list) else '، '.join(v))
                               for k, v in orig.items()})
ck(res2.get('status') == 'success', 'restored original thresholds')
after = req('/api/fts/config')['config']
ck(after['growth_min'] == orig['growth_min'] and after['industry_mode'] == orig['industry_mode']
   and after['eps_years'] == orig['eps_years'],
   'config back to baseline: growth_min=%s industry_mode=%s' % (after['growth_min'], after['industry_mode']))

n_bad = sum(1 for l in OUT if l.startswith('  FAIL'))
OUT.append('')
OUT.append('═══ %s ═══' % ('همهٔ بررسی‌های ذخیرهٔ آستانه‌ها موفق' if not n_bad else '%d ناموفق' % n_bad))
io.open(os.path.join(ROOT, 'dev', '_fts.txt'), 'w', encoding='utf-8').write('\n'.join(OUT) + '\n')
print('fts round-trip failures:', n_bad)
