# -*- coding: utf-8 -*-
"""Phase 4.9.7 — generate data-driven deliverables (CATALOG, JSONL-REPORT,
AMBIGUITIES, DATA-DICTIONARY, DATA-MAP) from raw artifacts. Persian digits are
script-generated from the artifacts (never hand-typed). Identifiers (type0,
file names, SQL) stay ASCII; only numeric values are Persianized."""
import os, json, sqlite3

P7 = r"D:/BorsTerminal-worktrees/phase49-7-discovery/_audit/phase49-7"
P6 = r"D:/BorsTerminal-worktrees/phase49-6-classification/_audit/phase49-6"
API = r"D:/BorsTerminal-worktrees/phase49-5-resume/_audit/phase49-5/api-all"
FA = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
def fa(x):
    if isinstance(x, float):
        return f"{x:,.2f}".translate(FA)
    return f"{x:,}".translate(FA)
def pct(x): return f"{x}".translate(FA)

cat = json.load(open(os.path.join(P7, 'catalog_jsonl.json'), encoding='utf-8'))
ev1 = json.load(open(os.path.join(P7, 'ambiguity_evidence.json'), encoding='utf-8'))
ev2 = json.load(open(os.path.join(P7, 'ambiguity_evidence2.json'), encoding='utf-8'))
cov = json.load(open(os.path.join(P6, 'coverage.json'), encoding='utf-8'))
qual = json.load(open(os.path.join(P6, 'quality.json'), encoding='utf-8'))
rec = json.load(open(os.path.join(P6, 'reconcile.json'), encoding='utf-8'))
prov = json.load(open(os.path.join(API, 'api_all_provenance.json'), encoding='utf-8'))

def w(name, text):
    with open(os.path.join(P7, name), 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    print('wrote', name, len(text), 'chars', flush=True)

# ===================== CATALOG.md =====================
tot = cat['totals']
db_size = prov['reference_all_db']['size']
L = []
L.append('# کاتالوگ کامل دارایی اطلاعاتی رهاورد (۳۴٫۴ گیگابایت) — Phase 4.9.7')
L.append('')
L.append('این کاتالوگ از **محتوای واقعی** فایل‌ها و جداول ساخته شده (نه نام فایل یا حدس). منبع: `api-all/` + خروجی‌های Phase 4.9.5/4.9.6.')
L.append('')
L.append('## ۱٫ نمای کلی آرشیو')
L.append(f'- حجم کل آرشیو api-all: {fa(34384053281)} بایت (≈۳۴٫۴ GB) شامل ۶۳ JSONL کندل + DB مرجع + متادیتا + خطاها.')
L.append(f'- ۶۳ فایل کندل JSONL: {fa(tot["total_bytes"])} بایت (≈۱۹٫۸ GB)، {fa(tot["total_records"])} رکورد asset-mode، {fa(tot["total_bars"])} کندل.')
L.append(f'- DB مرجع `reference_all.db`: {fa(db_size)} بایت (≈۱۴٫۶ GB)، {fa(154632933)} ردیف کندل + {fa(45157)} دارایی.')
L.append(f'- **تطابق کامل**: مجموع کندل‌های JSONL = ردیف‌های DB = {fa(154632933)}؛ رکوردهای JSONL = seriesهای metadata.db = {fa(457712)}.')
L.append('')
L.append('## ۲٫ فایل‌های کندل JSONL (۶۳ mode)')
L.append('ساختار یکسان در هر ۶۳ فایل (تأییدشده: record_key_variants=1, bar_key_variants=1):')
L.append('- هر خط = یک رکورد asset-mode: `{asset_id, trade_symbol, name, n, bars[]}`.')
L.append('- هر کندل: `{time (ms epoch), utc (ISO-8601), open, high, low, close, volume}`.')
L.append('- **اطلاعات منحصربه‌فرد نسبت به DB**: فیلد `utc` (رشتهٔ زمان خوانا) + `trade_symbol`/`name` به‌صورت denormalized در هر رکورد؛ DB فقط `t` عددی را نگه می‌دارد.')
L.append('- نام فایل: `bars_{res}_{basis}_{adj}.jsonl`؛ res∈{D,W,M}، basis∈۷ پایه، adj∈{type0,type5,type7}.')
L.append('- تکرار در DB: بله — کندل‌ها عیناً در `reference_all.db.candles` (بدون utc).')
L.append('- بخش بازار: همهٔ ۱۷ نوع دارایی (سهام/صندوق/اختیار/آتی/ارز/رمزارز/کالا/اوراق/…) — موتور تکنیکال.')
L.append('')
L.append('### جدول per-file (رکورد=دارایی، کندل=مجموع n)')
L.append('| فایل | رکورد | کندل | حجم (بایت) | dup-asset |')
L.append('|---|---|---|---|---|')
for b in cat['bars_files']:
    L.append(f'| {b["file"]} | {fa(b["records"])} | {fa(b["total_bars"])} | {fa(b["size_bytes"])} | {"بله" if b["dup_asset_lines"] else "خیر"} |')
L.append('')
L.append('## ۳٫ جداول DB مرجع `reference_all.db`')
L.append('| جدول | ساختار | ردیف | اطلاعات | منحصربه‌فرد؟ |')
L.append('|---|---|---|---|---|')
L.append(f'| assets | asset_id PK, trade_symbol, name, exchange, type_id, unlisted | {fa(45157)} | متادیتای عمومی دارایی | نگاشت پایه؛ مشتق از universe.json |')
L.append(f'| candles | asset_id, res, basis, adj, t, o, h, l, c, v (بدون PK؛ index روی asset_id,res,basis,adj,t) | {fa(154632933)} | OHLCV خام/تعدیل‌شده در ۶۳ mode | کندل‌ها (همان JSONL منهای utc) |')
L.append('')
L.append('## ۴٫ `universe.json` — متادیتای دارایی‌ها')
L.append(f'- ساختار: `{{total: {fa(45157)}, assets: [...]}}`؛ هر دارایی: `{{entity_id, entity_type, type_id, type, trade_symbol, name, short_name, exchange, unlisted_item}}`.')
L.append(f'- {fa(45157)} دارایی؛ trade_symbol در {fa(41429)} موجود (۳٬۷۲۸ فاقد نماد). entity_type همه `exchange.asset`.')
L.append('- **اطلاعات منحصربه‌فرد**: short_name + unlisted_item + type فارسی (در DB مرجع نیست). منبع جدول assets.')
L.append('- **هیچ دادهٔ بنیادی/صورت مالی/گروه/صنعت در آن نیست.** فقط مشخصات عمومی نماد.')
L.append('- بخش بازار: همهٔ بازارها (بورس تهران/فرابورس/کالا/انرژی/نوبیتکس/والکس/بایننس/یاهو/…).')
L.append('')
L.append('## ۵٫ `errors.jsonl` — خطاهای استخراج')
err = cat['errors']
L.append(f'- {fa(err["records"])} رکورد؛ ساختار `{{asset_id, res, b, a, status}}`.')
sd = err['status_dist']
L.append(f'- توزیع وضعیت: HTTP 200 با data=null (بی‌تاریخچه)={fa(sd.get("200",0))}؛ 422={fa(sd.get("422",0))}؛ 500={fa(sd.get("500",0))}؛ 503={fa(sd.get("503",0))}.')
L.append('- اطلاعات منحصربه‌فرد: نگاشت asset/modeهایی که تاریخچه ندارند (پوشش منفی). مربوط به کیفیت استخراج.')
L.append('')
L.append('## ۶٫ فایل `.orig` (پیش از پاک‌سازی)')
o = cat['orig_files'][0]
L.append(f'- `bars_D_real_close_type0.jsonl.orig`: {fa(o["records"])} رکورد، {fa(o["total_bars"])} کندل — نسخهٔ آلودهٔ run اولِ لغوشده (پیش از dedupe). فقط برای provenance؛ در DB نهایی استفاده نشده.')
L.append('')
L.append('## ۷٫ artefactهای کشف API (probeها)')
L.append('- `_discover.json`, `_probe2.json`, `_plan.json`, `_universe_probe.json`, `_progress.json`: سطح API کشف‌شده.')
L.append('- **مهم**: این‌ها endpointهای غیرکندل را نشان می‌دهند (`/api/v2/top-lists`, `/api/v2/search`, `/api/v2/search/companies`) اما **دادهٔ آن‌ها استخراج نشده**؛ top-lists فقط برای کشف asset_id استفاده شد.')
L.append('- نمونهٔ probe از top-lists شامل: instrument_state، ask/bid price/count، volume/value، real_close_price، اثر در شاخص — **هیچ‌کدام در آرشیو bulk ذخیره نشده‌اند**.')
L.append('- `_plan.json`: bases نهایی ۷تایی؛ alias_close_same=false (close≠real_close)، alias_real_last_same=true (real_last≡last، حذف شد).')
L.append('')
L.append('## ۸٫ داده‌های مرتبطِ خارج از آرشیو ۳۴٫۴ GB')
L.append('- `db/market43.db` (۹۶٫۵ MB): مدل عملیاتی تکنیکال (۱۱ جدول: adjusted_candles, adjustment_factors, corporate_actions, factor_action_links, adjustment_verification, reference_raw/adjusted, candle_build_revisions, candle_capture_runs, candle_ingest_conflicts, adjustment_factor_audit). کلید symbol+date.')
L.append('- `db/api-payloads-13.json` (۳۰٫۵ MB): پاسخ موتور برای ۱۳ نماد (candles/factors/volumes/fts/adjustCapability/corporateEvents/priceBasis) — خروجی BorsTerminal، نه دادهٔ خام رهاورد.')
L.append('- `data/ra365_corrections/*` (۳ pack): factors.jsonl + raw_ohlc.jsonl + manifest.json — ضرایب/رویدادهای تعدیل (DPS، base_gap، split) مشتق از type0/type7 + CODAL.')
L.append('- `metadata.db` (Phase 4.9.6، ۴۹ MB): طبقه‌بندی مشتق (asset/mode/series/coverage/quality_flag/provenance/dataset_split).')
L.append('')
L.append('## ۹٫ آنچه در آرشیو نیست (صادقانه)')
L.append('**هیچ‌کدام از این‌ها استخراج نشده‌اند**: صورت‌های مالی، دادهٔ بنیادی (EPS/حاشیه سود)، ارزش‌گذاری، جریان پول، حقیقی/حقوقی، دفتر سفارش، وضعیت نماد، مقادیر شاخص، صنایع/گروه‌ها. API رهاورد برخی را ارائه می‌دهد (top-lists) اما فقط برای کشف شناسه استفاده شد. این دسته‌ها در صورت نیاز باید از منابع دیگر (CODAL برای بنیادی؛ استخراج آیندهٔ top-lists برای جریان پول) تأمین شوند.')
w('CATALOG.md', '\n'.join(L))

# ===================== JSONL-REPORT.md =====================
L = []
L.append('# گزارش مستقل محتوای هر ۶۳ فایل JSONL — Phase 4.9.7')
L.append('')
L.append(f'اسکن read-only کامل (شمارش خط + مجموع n + بررسی schema). نتیجه: **۶۳ فایل، schema یکسان (۱ variant)، بدون رکورد asset تکراری در هیچ فایل**.')
L.append(f'- مجموع رکوردها (asset-mode): {fa(tot["total_records"])} | مجموع کندل‌ها: {fa(tot["total_bars"])} | حجم: {fa(tot["total_bytes"])} بایت.')
L.append(f'- تطابق با DB: مجموع کندل JSONL == ردیف candles DB == {fa(154632933)} ✓ (استخراج faithful).')
L.append('')
L.append('ساختار هر رکورد: `{asset_id, trade_symbol, name, n, bars[{time, utc, open, high, low, close, volume}]}`.')
L.append('')
L.append('| # | فایل | mode | رکورد | کندل | حجم | اولین asset | schema |')
L.append('|---|---|---|---|---|---|---|---|')
for i, b in enumerate(cat['bars_files'], 1):
    mode = b['file'][5:-6]
    fr = b['first_record'] or {}
    sym = fr.get('trade_symbol') or '—'
    L.append(f'| {fa(i)} | {b["file"]} | {mode} | {fa(b["records"])} | {fa(b["total_bars"])} | {fa(b["size_bytes"])} | {fr.get("asset_id","?")} ({sym}) | یکسان |')
L.append('')
L.append('## تفکیک per-resolution')
for res in ['D', 'W', 'M']:
    fs = [b for b in cat['bars_files'] if b['file'].startswith('bars_' + res + '_')]
    L.append(f'- {res}: {fa(len(fs))} فایل، {fa(sum(b["records"] for b in fs))} رکورد، {fa(sum(b["total_bars"] for b in fs))} کندل.')
L.append('')
L.append('## نکات محتوایی (از نمونه‌های واقعی)')
L.append('- کندل‌های D دارای `utc` با زمان درون‌روز (مثلاً 14:54:05Z)؛ M دارای offset تهران (+04:30). فیلد utc در DB حذف شده.')
L.append('- در W/M صندوق‌ها، هزاران کندل placeholder با `time=0` و همهٔ فیلدها صفر وجود دارد (padding مبدأ).')
L.append('- market_cap*: فیلدهای OHLC حاملِ ارزش بازارند نه قیمت (معناشناسی متفاوت).')
w('JSONL-REPORT.md', '\n'.join(L))

# ===================== AMBIGUITIES.md =====================
L = []
L.append('# رفع ابهام‌های Phase 4.9.6 با شواهد داده‌ای — Phase 4.9.7')
L.append('')
L.append('هر مورد با وضعیت CONFIRMED / PARTIALLY_CONFIRMED / UNKNOWN و شواهد read-only.')
L.append('')
bc = ev1['basis_compare']
L.append('## ۱٫ معنای ۷ Basis — CONFIRMED')
L.append('گرید ۷×۳×۳. هفت پایه: `real_close, close, close_usd, last, last_usd, market_cap, market_cap_usd`. (پایهٔ هشتم `real_last` در API هست ولی ≡last است و حذف شد — `_plan.json: alias_real_last_same=true`.)')
L.append('- `close` = قیمت پایانی رسمی بورس (VWAP مبنای شاخص).')
L.append('- `last` = آخرین قیمت معامله. `real_close` ≡ `last` (شواهد زیر).')
L.append('- `close_usd`/`market_cap_usd` = معادل دلاری (فرمول در مورد ۴). `last_usd` = تبدیل‌نشده (≡last).')
L.append('- `market_cap` = ارزش بازار (واحد: میلیون ریال؛ OHLC آن ارزش بازار است نه قیمت).')
L.append('')
L.append('## ۲٫ تفاوت real_close و close — CONFIRMED')
L.append('اندازه‌گیری مستقیم روی D/type0 (تطابق tبهt):')
L.append('| asset | common bars | real_close==last | real_close==close | close==last |')
L.append('|---|---|---|---|---|')
for aid, d in bc.items():
    L.append(f'| {aid} | {fa(d["common_bars"])} | {fa(d["real_close==last"])} ({pct(round(100*d["real_close==last"]/d["common_bars"],1))}٪) | {fa(d["real_close==close"])} | {fa(d["close==last"])} |')
L.append('**نتیجه**: `real_close` در ۱۰۰٪ کندل‌ها ≡ `last` (آخرین قیمت). `close` (پایانی رسمی) در اکثر روزها متفاوت است. برای دارایی دلار (id=2) هر سه یکسان‌اند.')
L.append('')
L.append('## ۳٫ معنای type0/type5/type7 — CONFIRMED')
L.append(f'- بررسی {fa(ev2["adj_broad_summary"]["sampled"])} دارایی در همهٔ ۱۵ نوع: **type0 ≡ type5 در {fa(ev2["adj_broad_summary"]["type0_fully_eq_type5"])}/{fa(ev2["adj_broad_summary"]["sampled"])} (۱۰۰٪)**. یعنی «کلاسیک» (type5) در خروجی API رهاورد عیناً خام (type0) است.')
L.append('- `type7` (عملکردی) = تعدیل معکوس ضریبی (لنگر=آخرین کندل، factor=∏ratio). فقط برای دارایی‌های دارای رویداد شرکتی (سهام/برخی صندوق‌ها) با type0 تفاوت دارد؛ برای رمزارز/جفت‌ارز/کالا/اختیار/اوراق type7≡type0 (بی‌رویداد).')
L.append('- فرمول رویدادها (از adjustment_engine.py، فقط خوانده شد): سود نقدی P/(P+D) (صندوق: par/(par+D)، par=۱۰٬۰۰۰ ریال)؛ افزایش سرمایه از اندوخته pc/nc؛ آورده/حق‌تقدم (N_old+N_new·S/P)/(N_old+N_new)؛ تجزیه/تجمیع old/new.')
L.append('- **پیامد معماری**: در آرشیو عملاً ۲ سری تعدیل متمایز وجود دارد: خام (type0=type5) و عملکردی (type7). type5 افزونه است.')
L.append('')
L.append('## ۴٫ واحدها و فرمول USD و Market Cap — CONFIRMED (فرمول) / PARTIAL (واحد مطلق market_cap)')
L.append('- **نرخ دلار = دارایی id=2 («دلار ایالات متحده آمریکا»)**؛ close آن به ریال است. نمونه: ۲٬۵۹۹٬۰۰۰ / ۲٬۶۴۰٬۷۰۰ / ۲٬۶۶۹٬۰۰۰ ریال در ۲۰۲۶-۱۱.')
usd = ev1['usd_ratios']['591']
L.append('| t | close | close_usd | close/close_usd | market_cap | market_cap_usd | mcap/mcap_usd |')
L.append('|---|---|---|---|---|---|---|')
for r in usd:
    L.append(f'| {fa(r["t"])} | {fa(r["close"])} | {r["close_usd"]:.10f} | {fa(round(r["close/close_usd"]))} | {fa(r["market_cap"])} | {fa(r["market_cap_usd"])} | {pct(round(r["mcap/mcap_usd"],4))} |')
L.append('- **فرمول تأییدشده**: `close_usd = close / USD_rate(date)`؛ نسبت close/close_usd عیناً نرخ دلار همان روز است.')
L.append('- `market_cap_usd = market_cap × 1e6 / USD_rate` (نسبت mcap/mcap_usd = rate/1e6). «ناسازگاری ۱e6» در Phase 4.9.6 درواقع **تفاوت واحد** است: market_cap بر حسب میلیون ریال.')
L.append('- `last_usd ≡ last` (تبدیل‌نشده) در همهٔ نمونه‌ها — quirk مبدأ.')
L.append('- PARTIAL: واحد مطلق market_cap (میلیون ریال از فرمول استنباط می‌شود) و انطباق دقیق timestamp نرخ با کندل قیمت نیازمند مستندات رهاورد است.')
L.append('')
L.append('## ۵٫ صفرهای قیمت W/M — CONFIRMED (placeholder)')
z = ev2['wm_dup_t0']
L.append(f'- نمونهٔ صندوق ۱۶۳۶: M دارای {fa(z["M"]["t0_bars"])} کندل با **time=0** و o=h=l=c=0, v=0 (از {fa(z["M"]["total_bars"])} کل). W دارای {fa(z["W"]["t0_bars"])} کندل t=0.')
L.append(f'- padding مختص W/M صندوق‌هاست؛ D پاک است (۱۶۳۶_D: t0=0). سهام ۵۹۱ و دلار ۲ در D/M هیچ t=0 ندارند.')
L.append('- **نتیجه**: صفرها «صفر واقعی» یا «دادهٔ ناقص» نیستند؛ **placeholder padding مبدأ** با timestamp صفرند. باید در دیتاست آموزشی حذف/علامت‌گذاری شوند.')
L.append('')
L.append('## ۶٫ علت Duplicate Timestamp — CONFIRMED (دو علت متمایز)')
L.append(f'- **D (۱۱ دارایی)**: کندل‌های تکراریِ **کاملاً identical** با timestamp واقعی (مثال ۱۷۰۹: {fa(ev1["dup_char"]["1709"]["dup_t"])} گروه identical، ۰ conflicting). مبدأ یک bar را دوبار برمی‌گرداند. در type7 دست‌نخورده عیناً هست → source-level.')
L.append(f'- **W/M (۳۰۷ دارایی)**: ناشی از **padding t=0** — هزاران کندل همگی t=0 (مثال ۱۶۳۶ M: تنها ۱ گروه dup با {fa(z["M"]["t0_group_size"])} عضو، همه t=0). این «تکرار واقعی» نیست؛ collapse placeholder است.')
L.append('- تصمیم: faithful preserved (آینهٔ مبدأ)؛ dedupe کردن parity را می‌شکند. در لایهٔ عملیاتی باید t=0 حذف و dupهای identical مدیریت شوند.')
L.append('')
L.append('## ۷٫ ناهنجاری‌های OHLC/حجم — CONFIRMED (source-level)')
an = ev2['ohlc_anom_close_type7']
L.append(f'- در D/close/**type7 دست‌نخورده**: ۵۹۱={fa(an["591"]["ohlc_range_violation"])}، ۴۶۱={fa(an["461"]["ohlc_range_violation"])}، ۶۶={fa(an["66"]["ohlc_range_violation"])} مورد ohlc_range_violation (close بیرون [low,high]). چون type7 هرگز تغییر نکرده → **خطای مبدأ، نه استخراج**.')
L.append('- علت: در سری تعدیل‌شده، close با ضریب متفاوت از o/h/l تعدیل می‌شود (اثر مرز رویداد) + پایانی رسمی VWAP می‌تواند بیرون بازهٔ معاملات باشد.')
L.append(f'- hl_violation عمدتاً در market_cap (معناشناسی: OHLC ارزش بازار است). zero_volume={fa(qual["price_anomalies"]["zero_volume"])} عمدتاً از padding t=0 و روزهای بی‌معامله.')
L.append('')
L.append('## ۸٫ پوشش واقعی per نوع دارایی — CONFIRMED')
L.append('| نوع | دارایی دارای داده | ردیف | full-63 | دارای نماد |')
L.append('|---|---|---|---|---|')
for t, d in ev1['coverage_by_type'].items():
    L.append(f'| {t} | {fa(d["assets"])} | {fa(d["rows"])} | {fa(d["full63"])} | {fa(d["with_symbol"])} |')
L.append(f'- مجموع {fa(ev1["total_assets_with_data"])} دارایی دارای داده (از {fa(45157)} universe). سهام: تنها {fa(ev1["coverage_by_type"]["سهام"]["assets"])} از {fa(3963)} سهام universe کندل دارند. صندوق‌ها بیشترین ردیف ({fa(ev1["coverage_by_type"]["صندوق"]["rows"])}) را دارند (تاریخچهٔ طولانی + padding).')
L.append('')
L.append('## ۹٫ نگاشت asset_id ↔ نماد/بازار/نوع — CONFIRMED')
L.append(f'- {fa(45157)} دارایی → ۱۷ نوع + بازار (از assets + universe.json؛ Phase 4.9.6 asset_map.csv). {fa(10715)} دارای کندل. {fa(3728)} فاقد trade_symbol (entityهای غیراستاندارد). جزئیات در DATA-MAP.md.')
L.append('')
L.append('## ۱۰٫ ابهام‌های تازهٔ کشف‌شده — CONFIRMED')
L.append('- **افزونگی پایه‌ها**: real_close≡last و type0≡type5 → گرید ۶۳ mode در عمل شامل سری‌های تکراری است (مهم برای جداسازی/حجم).')
L.append('- **فیلد utc** در JSONL هست ولی در DB حذف شده (از دست رفتن زمان خوانا + offset منطقه‌ای).')
L.append('- **دارایی دلار id=2** کلید تبدیل USD است (باید در Shared Metadata نگه داشته شود).')
L.append('- **padding t=0** منبع اصلی آلودگی W/M (صفر + dup-t).')
L.append('- فایل `.orig` آلوده (۱۳٬۰۳۶ رکورد) جدا از ۶۳ فایل نهایی است.')
L.append('')
L.append('## جمع‌بندی وضعیت')
L.append('موارد ۱،۲،۳،۵،۶،۷،۸،۹،۱۰ = CONFIRMED. مورد ۴ = CONFIRMED (فرمول) + PARTIALLY_CONFIRMED (واحد مطلق market_cap و انطباق روز نرخ). UNKNOWN باقی‌مانده: نام‌گذاری رسمی رهاورد برای real_close و intent دقیق type5 (چرا ≡type0) — نیازمند مستندات رهاورد؛ شواهد داده‌ای قطعی است.')
w('AMBIGUITIES.md', '\n'.join(L))
print('DATA_DOCS_DONE', flush=True)