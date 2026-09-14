"""v9.7.3 — گارد موتور تایید سه‌گانه (confidence_engine.py).

چرا این تست متولد شد: در نخستین اجرای زنده، موتور برای هر رشتهٔ بی‌ربطی
«ستون بنیادی: مردود (۱ از ۵)» اعلام می‌کرد. علت: fts_engine شاخص صنعت را برای
هر نامی «خنثی → پاس» می‌دهد و eps_trend را حتی بدون هیچ صورت‌مالی به‌صورت dict
برمی‌گرداند (data_gap=True). پس «دیکشنری بودن» نشانهٔ داده نبود، و نمادِ بدون‌داده
به‌جای «نظر نمی‌دهم» «مردود» می‌شد. این فایل همان تفکیک سه‌حالته را قفل می‌کند.

سه چیز دیگری که قفل می‌کند:
  ۱) خلوص ماژول: نه HTTP، نه نوشتن در دیتابیس (نه CREATE TABLE، نه INSERT).
  ۲) بنیادی نباید بازنویسی شود؛ فقط از fts_engine.scan_symbol بیاید.
  ۳) ضدِN+1: نقشهٔ کل‌بازاری ماده ۱۴۱ نباید داخل ماتریس چند‌نمادی دوباره ساخته شود.

اجرا:  python dev/confidence_engine_v973.py
اگر market.db در دسترس نباشد، بخشِ دیتا SKIP می‌شود (گاردهای استاتیک همیشه اجرا می‌شوند).
"""
import ast
import io
import json
import math
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))
    return cond


def fn_body(src, name):
    """بدنهٔ یک تابع (دیکشنری/کامنت حذف‌شده، همان الگوی fts_m141_parity_v97)."""
    m = re.search(r'\ndef %s\(.*?(?=\ndef |\Z)' % re.escape(name), src, re.S)
    body = m.group(0) if m else ''
    return re.sub(r'"""[\s\S]*?"""|#[^\n]*', '', body)


MOD = 'confidence_engine.py'
ck(os.path.exists(MOD), '%s exists' % MOD)
src = io.open(MOD, encoding='utf-8').read() if os.path.exists(MOD) else ''

# ---------- گارد ۱: خلوص ماژول ----------
ck(not re.search(r'^\s*(from|import)\s+(fastapi|starlette|uvicorn|httpx|requests)\b',
                 src, re.M),
   'no HTTP/network imports - stays pure like fts_engine.py')
ck(not re.search(r'\bCREATE\s+(TABLE|INDEX)\b', src, re.I),
   'no schema writes (matrix is computed on read, nothing persisted)')
ck(not re.search(r'\bconn\.(execute|executescript)\(\s*["\'](INSERT|UPDATE|DELETE)', src),
   'no row writes at all')
ck(not os.path.exists('confluence.py'),
   'confluence.py stays deleted (new module is confidence_engine.py)')

# ---------- گارد ۲: دامنهٔ خواندن SQL ----------
sqll = []
try:
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            v = re.sub(r'\s+', ' ', node.value).strip()
            if re.match(r'^(SELECT|WITH)\b', v, re.I) and ' FROM ' in v.upper():
                sqll.append(v)
except SyntaxError as e:
    ck(False, 'confidence_engine.py parses cleanly: %s' % e)
ck(len(sqll) >= 5, 'SQL literals discovered via AST: %d' % len(sqll))
for tbl in ('financial_statements', 'monthly_sales', 'codal_notices'):
    ck(not any(tbl in s for s in sqll),
       'never queries %s directly (fundamental comes only via fts_engine)' % tbl)
for tbl in ('instruments', 'price_history', 'client_type', 'daily_prices', 'market_watch'):
    ck(any(tbl in s for s in sqll), 'reads %s' % tbl)
ck(not any('selection_decisions' in s for s in sqll),
   'does not read selection_decisions (empty table must not be a data source)')

# ---------- گارد ۳: بنیادی واگذار شده، نه بازنویسی ----------
ck('fts_engine.scan_symbol' in fn_body(src, 'conf_fund'),
   'conf_fund delegates to fts_engine.scan_symbol')
ck('import fts_engine' in src, 'imports fts_engine (single source of fundamental truth)')
ck(re.search(r'fts_engine\.norm_fa', src) and not re.search(r'^def norm_fa', src, re.M),
   'norm() delegates to fts_engine.norm_fa and does not fork it')
ck(re.search(r'\bm141_hit\s*=', src) and re.search(r'\bavg_trade_val\s*=', src),
   'injects m141_hit/avg_trade_val into scan_symbol (same contract as scan_all)')

# ---------- گارد ۴: ساختار یکنواخت سه ستون ----------
for fn in ('conf_tech', 'conf_tape', 'conf_fund'):
    body = fn_body(src, fn)
    ck(bool(body), '%s defined' % fn)
    ck('_pillar(' in body, '%s returns via _pillar (uniform state/score/reasons)' % fn)
ck(re.search(r'^PILLAR_ORDER\s*=\s*\(\s*"tech",\s*"tape",\s*"fund"\s*\)', src, re.M),
   'PILLAR_ORDER is exactly (tech, tape, fund)')
ck(re.search(r'^def _fund_has_data', src, re.M),
   '_fund_has_data exists (the no-data-vs-rejected separator)')

# ---------- گارد ۵: build_ctx هر نقشه را یک‌بار و بیرون حلقه می‌سازد ----------
cb = fn_body(src, 'build_ctx')
for call in ('symbol_index(conn)', 'tape_rows(conn', 'daily_map(conn)',
             'watch_map(conn)', 'fts_engine.m141_map(conn)',
             'fts_engine.avg_trade_value_hmt(conn)'):
    hit = [l for l in cb.split('\n') if call in l]
    ck(len(hit) == 1, 'build_ctx builds %s exactly once' % call)
    if hit:
        ind = len(hit[0]) - len(hit[0].lstrip())
        for_ind = [len(l) - len(l.lstrip()) for l in cb.split('\n')
                   if re.match(r'\s*for\b', l)]
        ck(not for_ind or ind <= min(for_ind),
           'build_ctx: %s is outside any loop' % call)

# =========================================== بخش دیتا (روی market.db واقعی)
DBP = "market.db" if os.path.exists("market.db") else "../market.db"
if not os.path.exists(DBP):
    print("  SKIP data section (no %s)" % DBP)
else:
    import confidence_engine as CE

    conn = sqlite3.connect(DBP, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    ctx = CE.build_ctx(conn)

    ck(len(ctx["index"]["map"]) > 1000, "symbol_index built %d lookup keys"
       % len(ctx["index"]["map"]))
    for k in ("tape", "daily", "watch", "m141", "liq"):
        ck(len(ctx[k]) > 0, "ctx['%s'] non-empty (%d)" % (k, len(ctx[k])))
    ck(ctx["total_mcap_rials"] > 0, "total market cap > 0")

    # ---------- گارد ۶: تطبیق نماد (l_val18) و نام شرکت (l_val30) ----------
    pair = conn.execute(
        "SELECT ins_code, l_val18, l_val30 FROM instruments "
        "WHERE IFNULL(l_val18,'')<>'' AND IFNULL(l_val30,'')<>'' LIMIT 400").fetchall()

    # نماد باید به همین instrument برسد، مگر آنکه نماد واقعاً تکراری باشد.
    sym_owners = {}
    for ic, a in conn.execute(
            "SELECT ins_code, l_val18 FROM instruments WHERE IFNULL(l_val18,'')<>''"):
        sym_owners.setdefault(CE.norm(a), []).append(ic)
    wrong = dup = 0
    for ic, a in conn.execute(
            "SELECT ins_code, l_val18 FROM instruments WHERE IFNULL(l_val18,'')<>''"):
        rb = CE.resolve(ctx["index"], a)
        if rb and rb["ins_code"] == ic:
            continue
        if len(sym_owners[CE.norm(a)]) > 1:
            dup += 1
        else:
            wrong += 1
    ck(wrong == 0, "unique l_val18 resolves to its own instrument (%d wrong, %d duplicated)"
       % (wrong, dup))

    # l_val30 «نام شرکت» است و یکتا نیست (خواهرهای یک صندوق یک نام مشترک دارند)،
    # پس خواستهٔ درست این است که گم نشود و به instrument دارای همان نام برسد.
    name_owners = {}
    for ic, b in conn.execute(
            "SELECT ins_code, l_val30 FROM instruments WHERE IFNULL(l_val30,'')<>''"):
        name_owners.setdefault(b, []).append(ic)
    l18_all = {r[0] for r in conn.execute(
        "SELECT DISTINCT l_val18 FROM instruments WHERE IFNULL(l_val18,'')<>''")}
    orphan = misroot = 0
    for b, owners in name_owners.items():
        rb = CE.resolve(ctx["index"], b)
        if not rb:
            orphan += 1
        elif rb["ins_code"] not in owners and b not in l18_all:
            misroot += 1
    ck(orphan == 0, "every l_val30 resolves to some instrument (%d orphans)" % orphan)
    ck(misroot == 0, "l_val30 never resolves to an instrument lacking that name (%d)" % misroot)
    ck(True, "company names shared by >1 instrument: %d groups (name lookup is ambiguous by design)"
       % sum(1 for o in name_owners.values() if len(o) > 1))

    # نوشتار عربیِ همان نماد باید به همان entry برسد (تلهٔ m141 در v9.7)
    variant_pairs = [(s, s.replace('\u064a', '\u06cc').replace('\u0643', '\u06a9'))
                     for (_ic, s, _b) in pair
                     if CE.norm(s) != s or s != s.replace('\u064a', '\u06cc')]
    variant_pairs = [(x, y) for x, y in variant_pairs if x != y][:20]
    vbad = [x for x, y in variant_pairs
            if CE.resolve(ctx["index"], x) is not CE.resolve(ctx["index"], y)]
    ck(not vbad, "arabic/persian script variants resolve identically (%d tested, %d bad)"
       % (len(variant_pairs), len(vbad)))

    # ---------- گارد ۷: رشتهٔ بی‌ربط «نظر نمی‌دهد»، نه «مردود» ----------
    junk = CE.triple(conn, "ZZ_NOT_A_SYMBOL_ZZ", ctx=ctx)
    ck(junk["states"]["fund"] == "nodata",
       "junk symbol abstains on fund, not fail (got %s)" % junk["states"]["fund"])
    ck(junk["verdict"] == "INSUFFICIENT", "junk verdict INSUFFICIENT (got %s)" % junk["verdict"])
    ck(junk["conf_count"] == 0, "junk passes nothing")

    # ---------- نمونه‌های زنده ----------
    sample = [r[0] for r in conn.execute(
        "SELECT symbol FROM price_history GROUP BY symbol HAVING COUNT(*) >= 60 "
        "ORDER BY COUNT(*) DESC LIMIT 25")]
    ck(len(sample) >= 5, "live sample: %d symbols" % len(sample))
    rows = CE.triple_many(conn, sample, ctx=ctx)
    ck(len(rows) == len(sample), "matrix returns one row per symbol")

    VOCAB = set(CE.PILLAR_STATES)
    ck(VOCAB == {"pass", "warn", "fail", "nodata"},
       "4-state vocabulary incl. warn (got %s)" % sorted(VOCAB))
    ck(all(set(r["states"].values()) <= VOCAB for r in rows), "state vocabulary only")
    ck(all(bool(r["conf_" + k]) == (r["states"][k] == "pass")
           for r in rows for k in CE.PILLAR_ORDER), "conf_* booleans agree with states")
    ck(all(r["coverage"] == 3 - sum(1 for v in r["states"].values() if v == "nodata")
           for r in rows), "coverage counts only pillars with data")
    ck(all(r["conf_count"] == sum(1 for v in r["states"].values() if v == "pass")
           for r in rows), "conf_count == number of passing pillars")
    # ---- v9.7.4: قرارداد «هشدار منعطف» — هیچ وتویی در کار نیست ----
    ck(all(r["verdict"] != "CONFIRMED" or r["conf_count"] == 3
           for r in rows), "CONFIRMED requires all three pillars to pass")
    ck(all("vetoed" not in r for r in rows)
       and all(r["verdict"] != "VETOED" for r in rows),
       "no veto field and no VETOED verdict anywhere")
    ck(all(not set(r["warns"]) & set(r["passing"]) for r in rows),
       "a warned pillar is never counted among the passing ones")
    ck(all(r["conf_reasons"] for r in rows if r["warns"]),
       "every warned symbol carries warning text in conf_reasons")
    ck(all(r["verdict"] in ("WATCH", "WEAK", "PROBABLE", "CONFIRMED", "INSUFFICIENT")
           for r in rows), "verdict vocabulary has no VETOED")
    excluded = [r for r in rows
                if str((r["pillars"]["fund"].get("detail") or {}).get("verdict")) == "EXCLUDED"]
    ck(all(r["pillars"]["fund"]["state"] == "warn" for r in excluded),
       "FTS-excluded symbol is warn, not fail (%d such in sample)" % len(excluded))
    dist = {}
    for r in rows:
        dist[r["verdict"]] = dist.get(r["verdict"], 0) + 1
    ck(True, "verdict distribution on sample: %s" % dist)
    ck(any(r["coverage"] >= 2 for r in rows), "at least one sampled symbol is judgeable")
    ck(sum(1 for r in rows for k in CE.PILLAR_ORDER if r["states"][k] == "pass") > 0,
       "sample is not uniformly negative (pillars really fire)")

    # ---------- گارد ۸: آستانه‌ها یکنوا اثر می‌کنند ----------
    s0 = sample[0]
    f_loose = CE.conf_fund(conn, s0, ctx=ctx, cfg={"fund_min_score": 0})
    f_mid = CE.conf_fund(conn, s0, ctx=ctx)
    f_strict = CE.conf_fund(conn, s0, ctx=ctx, cfg={"fund_min_score": 5})
    rank = {"fail": 0, "nodata": 0, "pass": 1}
    ck(rank[f_loose["state"]] >= rank[f_mid["state"]] >= rank[f_strict["state"]],
       "fund verdict is monotone in fund_min_score (%s>=%s>=%s)"
       % (f_loose["state"], f_mid["state"], f_strict["state"]))
    t_easy = CE.conf_tech(conn, s0, ctx=ctx, cfg={"tech_need": 1})
    t_hard = CE.conf_tech(conn, s0, ctx=ctx, cfg={"tech_need": 9})
    ck(t_easy["score"] == t_hard["score"] == CE.conf_tech(conn, s0, ctx=ctx)["score"],
       "tech_need changes the verdict, never the underlying score")
    ck(not (t_hard["pass"] and not t_easy["pass"]), "stricter need cannot pass what loose fails")

    # ---------- گارد ۹: هم‌ارزی ctx / بدون ctx ----------
    for s in sample[:4]:
        a = CE.triple(conn, s, ctx=ctx)
        b = CE.triple(conn, s)
        ck(a["states"] == b["states"] and a["verdict"] == b["verdict"],
           "ctx and no-ctx agree for %s (%s vs %s)" % (s, a["verdict"], b["verdict"]))
        ck((a["pillars"]["fund"].get("detail") or {}).get("score") ==
           (b["pillars"]["fund"].get("detail") or {}).get("score"),
           "fund score identical with/without ctx for %s" % s)

    # ---------- گارد ۱۰: خروجی JSON-امن است (برای endpoint آینده) ----------
    class _NoNaN(json.JSONEncoder):
        def default(self, o):
            raise AssertionError("non-serializable %r" % type(o))

    try:
        txt = json.dumps(rows, cls=_NoNaN, ensure_ascii=False, allow_nan=False)
        safe = True
    except (ValueError, AssertionError) as e:
        safe, txt = False, str(e)
    ck(safe, "matrix is strict-JSON safe (no NaN/Inf, no exotic types): %s" % txt[:80])

    def _floats(o):
        if isinstance(o, dict):
            for v in o.values():
                for w in _floats(v):
                    yield w
        elif isinstance(o, (list, tuple)):
            for v in o:
                for w in _floats(v):
                    yield w
        elif isinstance(o, float):
            yield o
    ck(all(math.isfinite(v) for r in rows for v in _floats(r)),
       "no NaN/Inf floats anywhere in the matrix")

    # ---------- گارد ۱۱: دترمینیسم ----------
    # ---------- گارد ۱۱: دترمینیسم ----------
    ck([CE.triple(conn, s, ctx=ctx) for s in sample[:6]] ==
       [CE.triple(conn, s, ctx=ctx) for s in sample[:6]],
       "identical inputs produce identical output (no hidden state/randomness)")

    # ---------- گارد ۱۲: ضدِN+1 عملی، با trace callback ----------
    def counted(fn):
        seen = []
        conn.set_trace_callback(seen.append)
        try:
            out = fn()
        finally:
            conn.set_trace_callback(None)
        return len(seen), seen, out

    n_ctx, sqls_ctx, _ = counted(lambda: CE.build_ctx(conn))
    ck(sum(1 for s in sqls_ctx if "total_equity" in s) == 1,
       "build_ctx runs the market-wide m141 query exactly once (saw %d)"
       % sum(1 for s in sqls_ctx if "total_equity" in s))

    syms = sample[:12]
    n_mat, sqls_mat, mat = counted(lambda: CE.triple_many(conn, syms, ctx=ctx))
    rebuilt = sum(1 for s in sqls_mat if "total_equity" in s)
    ck(rebuilt == 0,
       "triple_many(with ctx) never rebuilds the m141 map (rebuilt=%d)" % rebuilt)
    n_one, _, _ = counted(lambda: CE.triple(conn, syms[0], ctx=ctx))
    per = (n_mat - n_one) / float(max(len(syms) - 1, 1))
    ck(per < 30.0, "marginal queries/symbol via scan_symbol = %.2f "
       "(fts_engine runs ~19 FS reads per symbol; the bulk path below is the fix)" % per)
    liq_self = sum(1 for s in sqls_mat if "AVG(d.q_tot_cap)" in s)
    absent = sum(1 for r in mat
                 if CE.norm(r.get("db_symbol") or r["symbol"]) not in ctx["liq"])
    ck(liq_self <= absent,
       "liquidity recompute only for symbols missing from ctx.liq (%d <= %d)"
       % (liq_self, absent))
    ck(True, "ctx build = %d queries; matrix of %d symbols = %d queries (%.1f/symbol)"
       % (n_ctx, len(syms), n_mat, per))

    # ---------- گارد ۱۳: مسیر bulk_scan باید با مسیر تک‌نمادی هم‌ارز باشد ----------
    import fts_engine as F
    bulk = F.bulk_scan(conn)
    ck(len(bulk) > 50, "bulk_scan returns %d rows" % len(bulk))
    fmap = CE.fund_map(conn)
    groups = {}
    for r in bulk:
        groups.setdefault(CE.norm(r["symbol"]), []).append(r["symbol"])
    dups = {k: v for k, v in groups.items() if len(v) > 1}
    ck(len(fmap) == len(groups), "fund_map keys %d == unique normalized symbols %d"
       % (len(fmap), len(groups)))
    # v9.7.3: bulk_scan دیگر روی رشتهٔ خام کلید نمی‌زند؛ هر نماد دقیقاً یک ردیف
    # است. اگر این عدد از صفر درآمد، یعنی ادغام دو-املا شکسته و آن شرکت دوبار
    # در اسکرینر ظاهر می‌شود (رفتارِ قبل از اصلاحیه: ۸۸۳ ردیف / ۱۸ کلیدِ تکراری).
    ck(len(dups) == 0,
       "bulk_scan emits one row per normalized symbol (duplicate keys=%d: %s)"
       % (len(dups), list(dups.items())[:2]))
    ck(len(bulk) == len(fmap),
       "bulk rows %d == fund_map keys %d (no mixed-script inflation)"
       % (len(bulk), len(fmap)))

    # قاعدهٔ «صفر بی‌داده» با ردیفِ ساختگی سنجیده می‌شود، نه با دادهٔ زنده:
    # bulk_scan وقتی گزارش ماهانه نیست از fs_rev جایگزین استفاده می‌کند، پس
    # annualize_months=0 در تولید تقریباً رخ نمی‌دهد و تستِ داده‌محور پوچ بود.
    fake = {"symbol": "SYNTEST", "score": 1, "i1_pass": False, "i2_pass": False,
            "i3_pass": False, "i4_pass": False, "i5_pass": True, "rev_growth": None,
            "gross_margin": None, "sales_to_mcap": 0.0, "annualize_months": 0,
            "eps_series": None, "eps_data_gap": True, "excluded": False,
            "exclusion_reasons": "", "mcap": 0.0}
    p_zero = CE.conf_fund(conn, "SYNTEST", ctx=ctx, fts=dict(fake))
    ck(p_zero["state"] == "nodata",
       "zero sales_to_mcap with no annualized report reads as nodata (got %s)" % p_zero["state"])
    ck(CE.fund_from_bulk(dict(fake, annualize_months=12, gross_margin=25.0,
                              rev_growth=41.0))["detail"]["sales_to_mcap"] is not None,
       "the same zero is kept when a report window really exists")
    ck(CE.conf_fund(conn, "SYNTEST", ctx=ctx,
                    fts=CE.fund_from_bulk(dict(fake, annualize_months=12,
                                               gross_margin=25.0, rev_growth=41.0)
                                          ))["state"] != "nodata",
       "a bulk row with real indicators is judged, not abstained")

    tested = [s for s in sample if CE.norm(s) in fmap][:8]
    ck(len(tested) >= 3, "bulk rows overlap the live sample (%d symbols)" % len(tested))
    d_state = d_score = 0
    diverged = []
    for s in tested:
        a = CE.conf_fund(conn, s, ctx=ctx)                    # از scan_symbol
        b = CE.conf_fund(conn, s, ctx=ctx, fts=fmap[CE.norm(s)])  # از bulk_scan
        if a["state"] != b["state"]:
            d_state += 1
            diverged.append((s, a["state"], b["state"]))
        if (a.get("detail") or {}).get("score") != (b.get("detail") or {}).get("score"):
            d_score += 1
    ck(d_score == 0, "fund score identical via bulk_scan and scan_symbol (%d differ: %s)"
       % (d_score, diverged[:3]))
    # ---- گاردِ باگِ رفع‌شده (v9.7.3): نوشتار عربی/فارسی نباید نتیجه را عوض کند ----
    # پیش از این، scan_symbol با `symbol = ?` خام می‌گشت و نمادهایی که FS آن‌ها
    # را با «ي/ك» عربی ذخیره کرده بود بی‌صدا «بی‌داده» می‌شدند، در حالی که
    # bulk_scan (که امضای خودش را از دیتابیس برمی‌داشت) داده داشت — یعنی
    # /api/fts/{symbol} و /api/screener دو پاسخ متفاوت به یک نماد. حالا
    # هم‌ارزی «دوطرفه» الزامی است: هیچ انحرافی، در هیچ جهت، قبول نمی‌شود.
    spell_groups = {}
    for tbl in ("financial_statements", "monthly_sales"):
        for (v,) in conn.execute("SELECT DISTINCT symbol FROM %s" % tbl):
            if v:
                spell_groups.setdefault(CE.norm(v), set()).add(v)
    collisions = {k: sorted(v) for k, v in spell_groups.items() if len(v) > 1}
    ck(len(collisions) > 0,
       "market.db really contains mixed-script symbol pairs to test (%d groups)"
       % len(collisions))
    spell_gap = [k for k, v in collisions.items()
                 if len({int(F.scan_symbol(conn, s, cfg={}).get("score") or 0)
                         for s in v}) != 1][:4]
    ck(not spell_gap,
       "every spelling of a symbol yields the same FTS score (divergent: %s)" % spell_gap)
    nodata_gap = []
    for k, v in list(collisions.items())[:14]:
        row = fmap.get(k)
        if not row:
            continue
        for s in v:
            p = CE.conf_fund(conn, s, ctx=ctx)
            if p["state"] == "nodata" and (row.get("rev_growth") is not None
                                           or row.get("gross_margin") is not None
                                           or row.get("eps_series")):
                nodata_gap.append(s)
    ck(not nodata_gap,
       "no symbol is silently 'no data' in scan while bulk has data (regression: %s)"
       % nodata_gap[:3])
    ck(d_state == 0 and not diverged,
       "fund pillar state identical via scan_symbol and bulk_scan, both ways (%s)"
       % diverged[:3])
    ck(True, "mixed-script parity locked: %d collision groups, %d spellings checked"
       % (len(collisions), sum(len(v) for v in collisions.values())))

    n_b, _, mat_b = counted(lambda: CE.triple_many(conn, syms, ctx=ctx, fund_rows=fmap))
    per_b = (n_b - n_one) / float(max(len(syms) - 1, 1))
    ck(per_b < per, "fund_rows collapses FTS queries/symbol: %.2f vs %.2f" % (per_b, per))
    ck(per_b <= 3.0, "bulk path stays at %.2f queries/symbol (price_history only)" % per_b)
    ck([r["states"] for r in mat_b] == [r["states"] for r in mat],
       "matrix is identical whether fund comes from scan_symbol or bulk_scan "
       "(%d rows differ)" % sum(1 for x, y in zip(mat, mat_b) if x["states"] != y["states"]))
    ck(True, "with fund_rows: %.2f queries/symbol (was %.2f)" % (per_b, per))
    conn.close()

n_bad = sum(1 for ok, _ in CHECKS if not ok)
for ok, msg in CHECKS:
    print('  %s %s' % ('PASS' if ok else 'FAIL', msg))
print('\n%d checks, %d failed' % (len(CHECKS), n_bad))
sys.exit(1 if n_bad else 0)



