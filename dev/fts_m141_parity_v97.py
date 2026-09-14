"""v9.7 — هم‌ارزی مسیر ماده ۱۴۱/نقدشوندگی + گارد ضدِN+1 و ضدِبازگشت.

چرا این تست متولد شد: هنگام افزودن فیلتر تک‌نمادی (`symbol=`) به m141_map،
کلیدهای نرمال‌شده (norm_fa) با نوشتار خامِ ستونِ دیتابیس تطبیق نکردند و
۱۴۵ نماد از ۲۲۴ بی‌صدا None برگرداندند — یعنی m141=False و نقدشوندگی‌بدون‌داده.
این فایل همان حالت را قفل می‌کند تا دوباره تکرار نشود.

اجرا:  python dev/fts_m141_parity_v97.py
اگر market.db در دسترس نباشد، بخشِ دیتا SKIP می‌شود (گاردهای استاتیک همیشه اجرا می‌شوند).
"""
import io, os, re, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))
    return cond


eng_src = io.open('fts_engine.py', encoding='utf-8').read()

# ---------- گارد ۱: فیلتر خامِ تک‌نمادی برنگردد ----------
# هر کوئری که کلیدش norm_fa(...) است نباید در SQL با `= ?` روی رشتهٔ خام سنجیده شود.
def fn_body(src, name):
    m = re.search(r'\ndef %s\(.*?(?=\ndef |\Z)' % re.escape(name), src, re.S)
    body = m.group(0) if m else ''
    # داکسترینگ/کامنت حذف شود، وگرنه توضیحِ خودِ ممنوعیت با ممنوعیت اشتباه گرفته می‌شود
    return re.sub(r'"""[\s\S]*?"""|#[^\n]*', '', body)


for fn in ['m141_map', 'avg_trade_value_hmt']:
    body = fn_body(eng_src, fn)
    ck(bool(body), '%s present in fts_engine.py' % fn)
    ck(not re.search(r'(symbol|l_val18)\s*(=|IN)\s*\?', body),
       '%s: no raw-string symbol filter in SQL (norm_fa keys would silently miss)' % fn)

# ---------- گارد ۲: نقشه‌ها بیرون از حلقه ساخته شوند (ضدِN+1) ----------
for fn in ['scan_all', 'bulk_scan']:
    body = fn_body(eng_src, fn)
    ck(bool(body), '%s found' % fn)
    for call in ['m141_map(conn)', 'avg_trade_value_hmt(conn)']:
        hit = [l for l in body.split('\n') if call in l]
        ck(len(hit) == 1, '%s builds %s exactly once' % (fn, call))
        if hit:
            ind = len(hit[0]) - len(hit[0].lstrip())
            # باید بیرون از هر for-loop باشد: کوچک‌ترین تورفتگیِ for در تابع
            for_ind = [len(l) - len(l.lstrip()) for l in body.split('\n')
                       if re.match(r'\s*for\b', l)]
            ck(not for_ind or ind <= min(for_ind),
               '%s: %s is outside the per-symbol loop' % (fn, call))
    ck(re.search(r'\n\s*key = norm_fa\(', body), '%s defines key = norm_fa(...)' % fn)

# ---------- گارد ۳: تزریق از بیرون، رفتار را عوض نمی‌کند ----------
ck(re.search(r'm141_hit:\s*Optional\[bool\]\s*=\s*None', eng_src),
   'scan_symbol accepts injected m141_hit')
ck(re.search(r'avg_trade_val:\s*Optional\[float\]\s*=\s*None', eng_src),
   'scan_symbol accepts injected avg_trade_val')
ck(eng_src.count('if m141_hit is None:') == 1 and eng_src.count('if avg_trade_val is None:') == 1,
   'both injected values are honoured (self-compute only when None)')

# ---------- بخش دیتا: هم‌ارزی واقعی روی نمونهٔ زنده ----------
DBP = r'../market.db' if os.path.exists(r'../market.db') else 'market.db'
if not os.path.exists(DBP):
    print('  SKIP data-parity section (no %s)' % DBP)
else:
    import fts_engine as F
    conn = sqlite3.connect(DBP, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL')
    big_m, big_l = F.m141_map(conn), F.avg_trade_value_hmt(conn)
    ck(len(big_m) > 0, 'm141_map returns rows (%d symbols, %d flagged)'
       % (len(big_m), sum(1 for v in big_m.values() if v)))
    ck(len(big_l) > 0, 'avg_trade_value_hmt returns rows (%d symbols)' % len(big_l))

    # نمادهای دارای نوشتارِ غیرفارسیِ خالص در دیتابیس — همان‌هایی که فیلتر خام می‌شکست
    raw = {r[0]: r[1] for r in conn.execute(
        "SELECT DISTINCT symbol, symbol FROM financial_statements "
        "WHERE period_months >= 12 AND capital > 0")}
    arabic = [s for s in raw if s != F.norm_fa(s)]
    ck(True, 'db symbols whose raw spelling differs from norm_fa: %d' % len(arabic))

    flagged = [s for s, v in big_m.items() if v][:6]
    clean = [s for s, v in big_m.items() if not v][:6]
    liq_only = [s for s in big_l if s not in big_m][:4]
    sample = flagged + clean + liq_only
    cfg = {'filter_m141': True, 'min_trade_val': 2.0}
    mism = 0
    for s in sample:
        a = F.scan_symbol(conn, s, 0.0, 0.0, '', cfg=cfg)
        b = F.scan_symbol(conn, s, 0.0, 0.0, '', cfg=cfg,
                          m141_hit=bool(big_m.get(s, False)), avg_trade_val=big_l.get(s))
        for k in ('m141', 'avg_trade_val_hmt', 'excluded', 'exclusion_reasons', 'score'):
            if a.get(k) != b.get(k):
                mism += 1
                print('  MISMATCH %s %s: self=%r injected=%r' % (s, k, a.get(k), b.get(k)))
    ck(mism == 0, 'self-computed == injected on %d sampled symbols (%d mismatches)'
       % (len(sample), mism))
    ck(any(F.scan_symbol(conn, s, 0.0, 0.0, '', cfg=cfg).get('m141') for s in flagged)
       if flagged else True, 'a known flagged symbol really reports m141=True')
    conn.close()

n_bad = sum(1 for ok, _ in CHECKS if not ok)
for ok, msg in CHECKS:
    print('  %s %s' % ('PASS' if ok else 'FAIL', msg))
print('\n%d checks, %d failed' % (len(CHECKS), n_bad))
sys.exit(1 if n_bad else 0)
