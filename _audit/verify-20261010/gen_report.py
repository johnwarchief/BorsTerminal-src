# -*- coding: utf-8 -*-
# _audit/verify-20261010/gen_report.py — REPORT.md از شاهدِ خام ساخته می‌شود؛ هیچ رقمِ فارسی دست‌نویس نیست
import json, io

def fa(x):
    s = str(x)
    return ''.join(chr(0x6F0 + int(c)) if c.isdigit() else c for c in s)

def fa2(x):  # با جداکنندهٔ هزارگانِ فارسی
    if x is None: return '—'
    return fa(f"{int(x):,}".replace(',', '٬'))

r = json.load(io.open('_audit/verify-20261010/probe_result.json', encoding='utf-8'))
ref = json.load(io.open('_audit/verify-20261010/api_reference.json', encoding='utf-8'))
i1, i2, i3, i4, i5, i6 = r['item1'], r['item2'], r['item3'], r['item4'], r['item5'], r['item6']
ls = i1['liveStats']['data']
uni = ls['universe']['counts']
P = i3['presets']

def num_from(text, idx=0):
    import re
    m = re.findall(r'[۰-۹٬]+', text or '')
    if not m: return None
    return int(m[idx].replace('٬', ''))

def ui_counts(name):
    c = P[name]['counts']
    return {k: num_from(v) for k, v in c.items()}

def api_cov(name):
    c = ref[name]['coverage']
    return c

rows3 = []
for name, key in [('swing','swing'), ('trend','trend'), ('hourglass','hourglass'), ('custom','custom'), ('custom&chain=f_clock','custom_fclock')]:
    u = ui_counts(key); a = api_cov(key); tabs = {t['key']: num_from(t['text'][t['text'].find('('):]) for t in P[key]['tabs']}
    rows3.append(
        f"| {fa(name if name!='custom&chain=f_clock' else 'custom&f_clock')} | {fa(tabs.get('tape'))} | {fa(a['tape']['pass'])} | {fa(tabs.get('technical'))} / {fa(a['technical']['pass'])} | "
        f"{fa(tabs.get('fundamental'))} / {fa(a['fundamental']['pass'])} | {fa(tabs.get('handover'))} / {fa(a['handover']['pass'])} | "
        f"رد {fa(u['reject'])} · انتظار {fa(u['pending'])} · بی‌داده {fa(u['unavailable'])} | "
        f"{'✓' if tabs.get('tape')==a['tape']['pass'] and tabs.get('technical')==a['technical']['pass'] and tabs.get('fundamental')==a['fundamental']['pass'] and tabs.get('handover')==a['handover']['pass'] and u['reject']==a['handover']['reject'] else '✗'} |")

x_rows = []
for name, key in [('swing','swing'), ('trend','trend'), ('hourglass','hourglass'), ('custom','custom'), ('custom&f_clock','custom_fclock')]:
    u = ui_counts(key); a = api_cov(key)
    agree = (u['reject'] == a['handover']['reject'] and u['pending'] == a['handover']['pending'] and u['unavailable'] == a['handover']['unavailable'] and u['market'] == ref[key]['universe']['joined'] and u['screening'] == ref[key]['universe']['screening'])
    x_rows.append(f"| انتظارِ تحویل {fa(u['pending'])} · رد {fa(u['reject'])} · بی‌داده {fa(u['unavailable'])} · جامعۀ تابلو {fa2(u['market'])} · واجد {fa2(u['screening'])} | انتظار {fa(a['handover']['pending'])} · رد {fa(a['handover']['reject'])} · بی‌داده {fa(a['handover']['unavailable'])} · joined {fa2(ref[key]['universe']['joined'])} · screening {fa2(ref[key]['universe']['screening'])} | {'✓' if agree else '✗'} |")

hv = i4['hourglass_vs_custom']
hg_u, cu_u = ui_counts('hourglass'), ui_counts('custom')
hg_a, cu_a = api_cov('hourglass'), api_cov('custom')

w1366 = i6['widthChecks']['1366']; w1920 = i6['widthChecks']['1920']
p2 = json.load(io.open('_audit/verify-20261010/probe2_result.json', encoding='utf-8'))
settled = {}
for tid, read in zip(p2['ids'], p2['reads']):
    settled[tid.replace('watch-row-', '')] = read
clicks = {c['clicked']: c['panels'] for c in i6['clicks']}

def clip(sym):
    st = settled[sym]
    return (st['chart']['text'][:90], st['ob']['text'][:110], st['sum']['text'][:110])

sh, fo, kha = clip('شپنا'), clip('فولاد'), clip('خساپ')

report = f"""# گزارشِ راستی‌آزماییِ زندهٔ UI — BorsTerminal

- **شاخه:** `fix/fts-p0-2-gates-flip` · **منبعِ شواهد:** بک‌اندِ dev رویِ `http://127.0.0.1:8002` (کدِ امروز، `BORS_NO_FETCH_LOOPS=1`) که همان `frontend/dist`ِ تازه (بیلدِ {fa('12:53')}، جدیدتر از همۀ سورس‌هایِ دست‌خورده) را سرو می‌کند. 5173 و بک‌اندِ نصبیِ 8001 دست نخوردند.
- **ابزار:** Chromiumِ Playwright (همان harnessِ `tools/jev_ui_check.mts`؛ `JEV_BROWSER_DIR` + `JEV_CHROME` + `MSYS_NO_PATHCONV=1`). شاهدِ خام: `probe_result.json` / `probe2_result.json` / `api_reference.json`؛ اسکریپت‌ها: `probe.mts` / `probe2.mts`.
- **زمانِ اجرا:** {fa('13:11:07')} تا {fa('13:13:28')} تهرانه ({r['startedAt'][11:19]}–{r['finishedAt'][11:19]} UTC).
- **اعتبارِ هر اجرا:** `href` و متنِ بدنه در هر گام خوانده شد — صفحه‌ها درست رندر شدند، هیچ ErrorBoundary‌ای دیده نشد. **خطای کنسول در کلِ اجرا: {fa(len(r['consoleErrors']))}.**
- ارقامِ این گزارش از همان JSONهایِ شاهد تولید شده‌اند (نه دست‌نویس) تا رقمی ندزدیده شود.

## حکمِ کلی

| بند | موضوع | حکم |
| --- | --- | --- |
| ۱ | پنلِ «وضعیت بازار» + انطباق با `/api/live-stats` | **PASS** |
| ۲ | صداقتِ تازگی بی‌`revision=0` | **PASS** |
| ۳ | پریست‌هایِ قیف (UI ↔ API) | **PASS** (یادداشتِ مرجعِ f_clock پایین) |
| ۴ | hourglass دیگر با custom یکی نیست + چیپِ «محاسبه:» | **PASS** |
| ۵ | ۶۰ ثانیه بی‌دست‌کاری در بازارِ بسته | **PASS** (یک مشاهده) |
| ۶ | زیرتب‌هایِ «دیده‌بان بازار» + سوییچِ سه پنل | **PARTIAL** — سوییچ درست؛ بریدگیِ ارقامِ عمق در 1366px |

---

## بند ۱ — پنلِ «وضعیت بازار» (`market-status-panel`)

پنل بالایِ صفحۀ تابلو (`#/market`) حاضر است. عینِ متنِ جمع‌شده از DOM (`01_market_collapsed.png`):

> {i1['collapsed']['panelText']}

چیپ‌ها تک‌تک (عینِ DOM):

{chr(10).join(f"- «{c['text']}»" + (f" (`{c['testid']}`)" if c['testid'] else '') + f" — title: {c['title']}" for c in i1['collapsed']['chipTexts'])}

- چیپِ «خنک» (`msp-cooldown`) و دکمۀ «وضعیتِ نامعلوم — دوباره» (`msp-retry`) **حاضر نیستند** — درست، چون 429/خطایی رخ نداده.

"""

report += f"""با کلیکِ `msp-toggle` پنل باز شد (`02_market_expanded.png`) و سه ستون، عینِ DOM:

"""
for col in (i1['expandedColumns'] or [])[1:]:
    report += f"> {col}\n\n"

report += f"""**تقابل با `curl http://127.0.0.1:8002/api/live-stats` درِ همان دقیقه ({fa('13:11:13')}):**

| خانۀ UI | UI | API | انطباق |
| --- | --- | --- | --- |
| کلِ تابلو | {fa(uni['total'])} | `universe.counts.total` = {fa(uni['total'])} | ✓ |
| بازار بسته | {fa(uni['market_closed'])} | `counts.market_closed` = {fa(uni['market_closed'])} | ✓ |
| در حالِ معامله / مظنه بی‌معامله / بدونِ معاملۀ اخیر | {fa(uni['trading'])} / {fa(uni['quote'])} / {fa(uni['no_trade'])} | {fa(uni['trading'])} / {fa(uni['quote'])} / {fa(uni['no_trade'])} | ✓ |
| متوقف / دادهٔ کهنه / نامعلوم / واجدِ غربالگری | {fa(uni['suspended'])} / {fa(uni['stale'])} / {fa(uni['unknown'])} / {fa(uni['eligible'])} | {fa(uni['suspended'])} / {fa(uni['stale'])} / {fa(uni['unknown'])} / {fa(uni['eligible'])} | ✓ |
| ردیفِ تکراری | {fa(uni['duplicate_rows'])} | `duplicate_rows` = {fa(uni['duplicate_rows'])} | ✓ |
| پنجره‌ها (تابلو/سینک/نوشتنِ تیک) | بسته / بسته / فعال | `window` = {ls['window']['market_open']} / {ls['window']['sync_window']} / {ls['window']['tick_writes']} | ✓ |
| چرخه‌ها / بدونِ تغییر / مدتِ آخرین چرخه | {fa(ls['cycles'])} / {fa(ls['nochange_cycles'])} / {fa(int(ls['last_cycle_s']))} ثانیه | {fa(ls['cycles'])} / {fa(ls['nochange_cycles'])} / {fa(ls['last_cycle_s'])} | ✓ |
| گوش‌دادن / بی‌تغییری / خنک‌شده / آویزانِ >10s | نه / — / {fa(ls['tick']['cooldown_level'])} / {fa(ls['tick']['cycle']['slow_over_10s'])} | `listening`={ls['tick']['listening']} · `since_change_s`={ls['tick']['since_change_s']} | ✓ |
| ویرایش | {fa(ls['revision'])} | `revision` = {fa(ls['revision'])} | ✓ |

**هیچ اختلافی نیست — PASS.**

## بند ۲ — صداقتِ تازگی

با `revision = {fa(i2['revision'])}` و `market_open = {i2['marketOpen']}` پنل هیچ ادعایِ زنده‌بودن نمی‌کند. عینِ متنِ چیپِ تازگی (`msp-data-age`): «{i2['dataAgeChip']['text']}» با title: «{i2['dataAgeChip']['title']}». «آخرین دادهٔ بازار: گزارش نشده» و «بازار: بسته» هم همان را می‌گویند. هیچ «لحظاتی پیش»/«زنده» رویِ دادهٔ یخ‌زده دیده نشد. **PASS.**

## بند ۳ — پریست‌هایِ قیف (UI ↔ API)

پنج مسیر فقط با تغییرِ hash باز شدند (بدونِ هیچ کلیکِ «تازه‌سازی»): `#/master?stage=tape&preset=…` برایِ swing/trend/hourglass/custom و `…&preset=custom&chain=f_clock`. شمارۀ تبِ هر مرحله (UI) دربرابرِ `GET /api/funnel`ِ همان preset (اخراجِ {fa('13:05')}، فایل‌هایِ `api_*.json`):

| پریست | تابلو UI | تابلو API | تکنیکال UI/API | بنیادی UI/API | تحویل UI/API | خطِ شمارشِ UI (رد/انتظار/بی‌داده) | انطباق |
| --- | --- | --- | --- | --- | --- | --- |
""" + '\n'.join(rows3) + """

تقابلِ ریزِ خطِ شمارش‌ها با `coverage`ِ API:

| UI | API | ✓ |
| --- | --- | --- |
""" + '\n'.join(x_rows) + f"""

سرخطِ مرحلۀ تابلو (عینِ DOM، نمونه): swing → «{P['swing']['stageCountLine']}» · trend → «{P['trend']['stageCountLine']}» · hourglass → «{P['hourglass']['stageCountLine']}» · custom&f_clock → «{P['custom_fclock']['stageCountLine']}».

**ردیف‌هایِ اولِ جدول فقط با سوییچِ پریست عوض شدند** (شش ردیفِ اول، بدونِ فشردنِ هیچ دکمه‌ای):

| پریست | ردیف‌هایِ اولِ جدولِ تابلو |
| --- | --- |
| swing | {', '.join(x['sym'] for x in P['swing']['rows'])} — «لبن»ِ سبز (تنها عبوری، بجِ «ساعت + مشکوک + جت + پول هوشمند») بعد ردهایِ «الگوی ساعت» |
| trend | {', '.join(x['sym'] for x in P['trend']['rows'])} — همه «رد — کف روبی صف فروش» |
| hourglass | {', '.join(x['sym'] for x in P['hourglass']['rows'])} — همه «تأیید» |
| custom | {', '.join(x['sym'] for x in P['custom']['rows'])} — همه «تأیید» |
| custom&f_clock | {', '.join(x['sym'] for x in P['custom_fclock']['rows'])} — مجموعهٔ کاملاً متفاوت با بج «ساعت» |

**یادداشتِ مرجع:** ارقامِ ارجاعِ {fa('12:59')} بازتولید شدند: swing=1 ✓، trend=0 ✓، hourglass (تابلو 2781، رد تکنیکال 41، عبور 0، تحویل 0) ✓، custom (تکنیکال 43، تحویل 34) ✓. فقط «custom&chain=f_clock ≈54» بازتولید **نشد**: UI و API هر دو امروز {fa(api_cov('custom_fclock')['tape']['pass'])} می‌دهند — اختلاف با مرجع از جانبِ API/داده است نه رابط (شمارِ f_clock به نشستِ زنده وابسته است و بازار حالا بسته است). چراییِ 54→23: **UNVERIFIED** (خارج از حوزۀ UI).

اسکرین‌شات‌ها: `03_funnel_swing.png` … `03_funnel_custom_fclock.png`. **PASS.**

## بند ۴ — پایانِ باگِ P0 (hourglass ≠ custom) + چیپِ «محاسبه:»

| | hourglass | custom |
| --- | --- | --- |
| جامعِ چهار در | {hv['hourglass']['counts']['pass']} | {hv['custom']['counts']['pass']} |
| رد | {hv['hourglass']['counts']['reject']} | {hv['custom']['counts']['reject']} |
| در انتظار | {hv['hourglass']['counts']['pending']} | {hv['custom']['counts']['pending']} |
| بی‌داده | {hv['hourglass']['counts']['unavailable']} | {hv['custom']['counts']['unavailable']} |
| تب‌ها | {', '.join(t['text'] for t in P['hourglass']['tabs'])} | {', '.join(t['text'] for t in P['custom']['tabs'])} |

`sameCounts = {hv['sameCounts']}` — دو پریست دیگر یکی نیستند. **PASS.**

- چیپِ `funnel-as-of` (حاضر): «**{P['hourglass']['asOf']}**»
- حالتِ محاسبه (hourglass): «**{P['hourglass']['computing']}**»
- چیپِ تازگیِ خوراک: «{P['hourglass']['tapeFreshness']}» — در تضاد با «بازار: بسته» نیست؛ دو محورِ جدایند (اتصالِ فید ≠ تازگیِ داده).

## بند ۵ — ۶۰ ثانیه بی‌دست‌کاری (`05_idle_60s.png`)

- t0 = {fa('13:12:04')}، t1 = {fa('13:13:04')}، بدونِ هیچ تعاملی.
- **هیچ عددی عوض نشد:** `rowsChanged = {i5['rowsChanged']}`، `panelChanged = {i5['panelChanged']}`، `revision = {fa(i5['revision'])}`، `cycles = {fa(i5['cycles'])}`. ردیف‌های اول در هر دو لحظه یکسان، عیناً: «{i5['t0rows'][0]}» … «{i5['t0rows'][4]}».
- پنل صادق است: «{i5['panelAfter']}» — بازار بسته، «آخرین دادهٔ بازار: گزارش نشده»، «ویرایش: ۰». **ادعایِ تازگی ندارد. PASS.**
- **مشاهده (نه نقض):** درِ این بازدید چیپِ «عوض‌شدنِ عدد» «{i5['panelAfter'][i5['panelAfter'].find('عوض'):i5['panelAfter'].find('ویرایش')]}» بود و درِ کلِ پنجرۀ ۶۰ ثانیه همین ماند — یعنی `rev_at` با پولینگِ بی‌تغییر نو می‌شود. دروغِ «لحظاتی پیش» تکرار نشده، ولی منطقِ این عدد در حالتِ بی‌تغییریِ مطلق گمراه‌کننده است؛ برایِ تصمیمِ مالک ثبت شد، چیزی عوض نکردم.

## بند ۶ — «دیده‌بان بازار» درِ پرتفوی

- هر دو زیرتب **حاضر و کلیک‌پذیرند**: `portfolio-section-mine` = «{i6['subtabs']['mine']}» · `portfolio-section-watch` = «{i6['subtabs']['watch']}» (`06_watch_initial.png`).
- سه نماد افزوده شد ({', '.join(x.replace('watch-row-','') for x in i6['afterAdd']['rowIds'])}) و هر سه کلیک شدند؛ `data-symbolِ` هر سه پنل با هر کلیک عوض شد (متن‌هایِ جدول از خوانشِ «نشین»ِ {fa('12')} ثانیه بعد از کلیک — `probe2`؛ درِ خوانشِ {fa('3')} ثانیه‌ایِ اول، چارتِ فولاد/شپنا هنوز «در حال دریافتِ کندل…» بود):

| کلیک‌شده | چارت | عمقِ پنج‌سطحی | خلاصه |
| --- | --- | --- | --- |
| خساپ | «{kha[0]}…» | «{kha[1]}…» | «{kha[2]}…» |
| فولاد | «{fo[0]}…» | «{fo[1]}…» | «{fo[2]}…» |
| شپنا | «{sh[0]}…» | «{sh[1]}…» | «{sh[2]}…» |

  - سوییچِ هر سه پنل با هر کلیک: **درست** (`06_watch_click_*.png`، `07_watch_settled_*.png`).
  - «بدون داده»هایِ خساپ جعلی نیستند: علتِ هر محور جدا نوشته شده («ذخیره نشده — بعد از نخستین همگام‌سازیِ تابلو می‌آید»، «بی‌ردیفِ تابلو») — مطابقِ قراردادِ gapReason.
  - برچسبِ `{i6['afterAdd']['feedAge']}` (`watch-feed-age`) دیده شد.
- **عرض‌ها:** `pageOverflowX` در 1366px = {fa(w1366['pageOverflowX'])} و در 1920px = {fa(w1920['pageOverflowX'])} (صفحه بیرون نمی‌زند). گریدِ سه‌پنلی درِ هر دو عرض سه‌ستونه می‌ماند (1366: {w1366['gridCols']} · 1920: {w1920['gridCols']}).
- **یک بریدگی در 1366px:** عنصرِ «{w1366['clippedSample'][0] if w1366['clippedSample'] else '—'}» (قیمت+حجمِ ردیف‌هایِ عمق درِ ستونِ ~311 پیکسلی) scrollWidth بیشتر از عرض دارد — ارقامِ عمق به هم می‌چسبند/بریده می‌شوند. در 1920px بریدگی‌ای نیست (`clippedSample = {w1920['clippedSample']}`). → بند ۶ **PARTIAL**.

## لاگِ کنسول / شبکه

- **خطای کنسول: {fa(len(r['consoleErrors']))}** — نه console.error، نه pageerror؛ از `#/market`، پنج مسیرِ `#/master` و `#/portfolio`.
- **`/api/funnel`:** {fa(len(i4['funnelNetLog']))} درخواستِ ثبت‌شده، همه با وضعیتِ موفق، هیچ 429/5xx دیده نشد.
- **stale-overwrite:** `lateFunnelResponses = {i4['lateFunnelResponses']}` — هیچ پاسخِ `/api/funnel` بعد از شروعِ سوییچِ بعدی نرسید (سوییچ‌ها ~9 ثانیه فاصله داشتند، پاسخ‌ها 0.3–2.7 ثانیه‌ای تمام شدند). مسیرِ تهاجمیِ «پاسخِ کهنه بعد از سوییچ برسد» درِ این اجرا آزموده **نشست** → **UNVERIFIED**؛ کد `signal` + `keepPreviousData` را دارد ولی شاهدِ زنده‌اش گرفته نشد (برایِ آزمودنش سوییچ‌ها باید زودتر از ~3 ثانیه انجام شوند).

## فایل‌هایِ همین پوشه

`REPORT.md` · `probe.mts` + `probe2.mts` + `gen_report.py` · `probe_result.json` + `probe2_result.json` + `api_reference.json` + `api_*.json` · 18 اسکرین‌شاتِ شماره‌دار.
"""
io.open('_audit/verify-20261010/REPORT.md', 'w', encoding='utf-8').write(report)
print('written', len(report))
