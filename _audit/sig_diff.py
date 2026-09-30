import re, sys, datetime

L = sys.argv[1]
cur = None
rows = []
for l in open(L, encoding='utf-8', errors='replace'):
    m = re.match(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)', l)
    if m:
        cur = datetime.datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S')
    if 'history windows rebuilt' in l:
        s = re.search(r'sig=\((.*?)\)\)', l)
        if s:
            rows.append((cur, tuple(eval(s.group(1)))))

names = ['max_d_even', 'ph_cnt_excl_today', 'ph_sum_excl_today', 'dp_cnt_excl',
         'dp_sum_excl', 'tape_cnt', 'tape_sum', 'tape_ok']
prev = None
for c, t in rows[-14:]:
    delta = []
    if prev:
        for i, (a, b) in enumerate(zip(prev, t)):
            if a != b:
                nm = names[i] if i < len(names) else f'col{i}'
                delta.append(f'{nm}:{a}->{b}')
    print(f"{c.strftime('%H:%M:%S') if c else '??'} len={len(t)} changed={delta}")
    prev = t
