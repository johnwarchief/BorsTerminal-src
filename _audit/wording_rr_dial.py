# دو واژۀ نادرست درِ پنلِ پارامترها:
#   ۱) عنوانِ دستگیرۀ «درصد فروش در مقاومت ۱» ➔ «درصد فروش در اولین سقف» (واژۀ خودِ جزوه)
#   ۲) برچسبِ «جزوه: ۲.۰» زیرِ لغزندۀ R/R ➔ جزوه هیچ عددی برای R/R ندارد؛ این پیش‌فرضِ ماست
import io

FA = lambda n: ''.join(chr(0x06F0 + int(d)) for d in n)
D2 = FA('2') + '.' + FA('0')


def patch(path, pairs):
    s = io.open(path, encoding='utf-8', newline='').read()
    for old, new in pairs:
        if s.count(old) != 1:
            raise SystemExit('ANCHOR %r found %d times in %s' % (old[:40], s.count(old), path))
        s = s.replace(old, new)
    io.open(path, 'w', encoding='utf-8', newline='').write(s)
    print('patched', path)


P = 'frontend/src/features/master/components/ObsidianStrategyGraph.tsx'
patch(P, [
    ('درصد فروش در مقاومت ۱:', 'درصد فروش در اولین سقف:'),
    ('جزوه: ' + D2, 'پیش‌فرضِ برنامه: ' + D2),
])
