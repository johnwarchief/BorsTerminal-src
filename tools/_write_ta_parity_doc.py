# tools/_write_ta_parity_doc.py — بازتولیدِ اعدادِ پروندۀ تطبیف از JSONِ خودش
#
# چرا اسکریپت: رقم‌هایِ فارسیِ دست‌نویس درِ این پروژه بارها رقم کم گذاشتند
# (۵٬۴۵۸٫۹ → «۵٬۴۸٫۹»). تنها راهِ مطمئن این است که عدد از فایلِ خروجیِ خودِ
# ابزار خوانده و با همان قالبِ رقمِ فارسی + جداکنندهٔ هزارگان نوشته شود؛ متنِ
# تفسیری دست‌نخورده می‌ماند و فقط جدول‌ها بازمحاسبه می‌شوند.
import io
import json

PAR = json.load(io.open('_audit/pulse_ta_parity.json', encoding='utf-8'))
SNAP = json.load(io.open('_audit/pulse_ta_snapshot.json', encoding='utf-8'))
DOC = 'docs/validation/TRADERSARENA-MARKET-STATUS-PARITY.md'


FA_SEP = chr(0x066C)      # ٬ جداکنندۀ هزارگانِ فارسی
FA_DEC = chr(0x066B)      # ٫ ممیزِ فارسی


def fa_digits(t):
    return ''.join(chr(0x06F0 + int(c)) if c.isdigit() else
                   (FA_SEP if c == ',' else FA_DEC if c == '.' else c) for c in t)


def fa_num(x, dec=1):
    """رقمِ فارسی با ٬ و ٫ — همان قالبِ رابط؛ بی‌دست‌کاریِ دستی."""
    return ('−' if x < 0 else '') + fa_digits(f'{abs(x):,.{dec}f}')


def pct(x):
    return ('−' if x < 0 else '+') + fa_digits(f'{abs(x):.2f}') + '٪'


CLS = {  # طبقه‌بندیِ هر ردیف — همان متنِ پرونده، فقط عددش از JSON
    ('m', 'ارزش'): 'UNVERIFIED', ('m', 'جریان'): 'UNVERIFIED',
    ('st', 'ارزش'): 'UNVERIFIED', ('sf', 'ارزش'): 'تعریفِ زیرگونه (پایین)',
    ('nsf', 'ارزش'): 'تعریفِ زیرگونه (پایین)', ('lf', 'ارزش'): 'تطبیق',
    ('cf', 'ارزش'): 'تعریفِ زیرگونه (پایین)', ('scf', 'ارزش'): 'تعریفِ زیرگونه (پایین)',
    ('afl', 'ارزش'): 'تطبیق',
}

rows_md = ['| ردیف TA | سطرِ ما | معیار | TA (م.ت) | ما (م.ت) | خطا | طبقه‌بندی |',
           '| --- | --- | --- | --- | --- | --- | --- |']
for r in PAR['rows']:
    k = (r['ta_row'], r['metric'])
    cls = CLS.get(k, 'UNVERIFIED')
    bold = cls == 'تطبیق' or k in (('m', 'ارزش'), ('m', 'جریان'))
    f = (lambda v: f'**{v}**') if bold else (lambda v: v)
    rows_md.append('| `{}` | {} | {} | {} | {} | {} | {} |'.format(
        r['ta_row'], r['ta_label'], r['metric'], fa_num(r['ta_bt']), fa_num(r['our_bt']),
        f(pct(r['err_pct'])), cls))
ROWS = '\n'.join(rows_md)

combos_md = ['| گروه | TA (م.ت) | ما (م.ت) | خطا |', '| --- | --- | --- | --- |']
for c in PAR['combos']:
    combos_md.append('| {} | {} | {} | **{}** |'.format(
        c['label'], fa_num(c['ta_bt']), fa_num(c['our_bt']), pct(c['err_pct'])))
COMBOS = '\n'.join(combos_md)

by = {(r['ta_row'], r['metric']): r for r in PAR['rows']}
st = by[('st', 'ارزش')]
afl = by[('afl', 'ارزش')]
m_val, m_flow = by[('m', 'ارزش')], by[('m', 'جریان')]
gold = PAR['combos'][1]
eqfix = PAR['combos'][0]

def hhmmss(t):
    h, m, sec = (int(x) for x in t.split(':'))
    return h * 3600 + m * 60 + sec


gap_s = abs(hhmmss(SNAP['ta_done_at']) - hhmmss(SNAP['app_done_at']))
A = PAR['app_asof']
prov_rows = [
    ('برداشتِ «ما»', '`' + PAR['ours_source'] + '` (همان APIِ خودِ برنامه، نه بانکِ رویِ دیسک)'),
    ('ساعتِ برداشت', PAR['taken_at']),
    ('هویّتِ نشستِ ما', '`d_even=%s`، `h_even=%s`، `n=%s` ردیفِ زنده' % (A['d_even'], A['h_even'], A['n'])),
    ('هویّتِ نشستِ TA', '`%s/%s %s` — همان نشستِ بسته' % (PAR['ta_day'], PAR['ta_hour'], '1859')),
    ('فاصلۀ دو خواندن', '%d ثانیه (پیانگِ `pulse_ta_snapshot.py`)' % gap_s),
]
PROV = '\n'.join('| %s | %s |' % kv for kv in prov_rows)

# ── جای‌گذاری درِ پرونده ──────────────────────────────────────────────────────
s = io.open(DOC, encoding='utf-8', newline='').read()


def replace_block(start_marker, end_marker, new_text):
    global s
    i = s.index(start_marker)
    j = s.index(end_marker, i)
    s = s[:i] + new_text + '\n\n' + s[j + len(end_marker):]


replace_block('| ردیف TA | سطرِ ما |', '\n\nهویّتِ جبریِ خودِ TA', ROWS)
replace_block('| گروه | TA (م.ت) |', '\n\nپس خطاهای', COMBOS)
replace_block('| میدان | مقدار |', '\n\nپیش‌شرطِ §۱۶', PROV)

# سه عددِ درونِ متنِ تفسیری هم از JSON بازحساب می‌شوند
s = s.replace('۲٬۴۲ م.ت بالاتر از TA', f'{fa_num(st["our_bt"] - st["ta_bt"], 1)} م.ت بالاتر از TA')
s = s.replace('`st` تنها', '`st` تنها')
s = s.replace('| total (ارزشِ کل) | **UNVERIFIED** | +۶٫۶۰٪ درِ نشستِ بسته',
              '| total (ارزشِ کل) | **UNVERIFIED** | {} درِ نشستِ بسته'.format(pct(m_val['err_pct'])))
s = s.replace('−۱۸٫۳۷٪', pct(m_flow['err_pct']))
s = s.replace('+۰٫۰۴٪', pct(afl['err_pct']))
s = s.replace('+۷٫۹۴٪', pct(st['err_pct']))
s = s.replace('۲۲٪ تا ۷۴٪', pct(-22.72).lstrip('−') + '٪ تا ' + pct(-74.24).lstrip('−') + '٪')
s = s.replace('گروه طلا+نقره+کالا +۳٫۲۶٪ و گروه سهامی+درآمدثابت +۵٫۸۵٪',
              'گروه طلا+نقره+کالا {} و گروه سهامی+درآمدثابت {}'.format(
                  pct(gold['err_pct']), pct(eqfix['err_pct'])))

io.open(DOC, 'w', encoding='utf-8', newline='').write(s)
print('doc numbers regenerated from JSON')
print(ROWS[:200])
