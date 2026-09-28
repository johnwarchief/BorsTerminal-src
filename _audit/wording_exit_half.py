# اصلاحِ واژگانِ «ذخیره سود در R1» به عبارتِ خودِ جزوه («سیگنال فروش ٪۵۰» در «اولین سقف»)
# و هم‌راستاکردنِ ادعاهایِ تست‌ها. ارقامِ فارسی با chr() ساخته می‌شوند.
import io

FA = lambda n: ''.join(chr(0x06F0 + int(d)) for d in n)
P50 = FA('50')


def patch(path, pairs):
    s = io.open(path, encoding='utf-8', newline='').read()
    for old, new in pairs:
        if s.count(old) != 1:
            raise SystemExit('ANCHOR %r found %d times in %s' % (old[:40], s.count(old), path))
        s = s.replace(old, new)
    io.open(path, 'w', encoding='utf-8', newline='').write(s)
    print('patched', path)


patch('frontend/src/features/master/lib/ftsPipelineEvaluator.ts', [
    ('طبق قانون FTS ذخیره سود ' + P50 + '٪ جهت خروج اصل سرمایه و نگهداری سود باقیمانده.',
     'طبق قانون FTS فروشِ ' + P50 + '٪ در اولین سقف برای آزادکردن اصل سرمایه، و نگهداریِ سودِ باقی‌مانده.'),
])

patch('frontend/src/features/master/components/ObsidianStrategyGraph.tsx', [
    ('{/* ۹. درصد ذخیره سود ' + P50 + '٪ در مقاومت اول R1 */}',
     '{/* ۹. درصدِ فروش در اولین سقف — جزوه: «سیگنال فروش ٪' + P50 + '» */}'),
])

patch('frontend/src/__tests__/fts-pipeline-evaluator.spec.ts', [
    ("expect(trendRes.tradePlan.halfExitLabel).toContain('ذخیره سود " + P50 + "٪');",
     "expect(trendRes.tradePlan.halfExitLabel).toContain('فروش " + P50 + "٪ در اولین سقف');"),
    ("expect(sc.bullish.targetOrStop).toContain('ذخیره سود " + P50 + "٪');",
     "expect(sc.bullish.targetOrStop).toContain('فروشِ " + P50 + "٪ در اولین سقف');"),
])

patch('frontend/src/__tests__/obsidian-strategy-graph.spec.tsx', [
    ('expect(screen.getAllByText(/ذخیره سود/i).length).toBeGreaterThan(0);',
     'expect(screen.getAllByText(/در اولین سقف/i).length).toBeGreaterThan(0);'),
])

patch('frontend/src/features/master/stores/strategyParamsStore.ts', [
    ('exitHalfPct: number; // درصد ذخیره سود در مقاومت اول R1 (پیش‌فرض جزوه: 50%)',
     'exitHalfPct: number; // درصدِ فروش در اولین سقف (جزوه: «سیگنال فروش ٪۵۰»)'),
])

patch('frontend/src/features/master/lib/strategyTree.ts', [
    ('halfExitAtResistance: false, // خروج 100% در R1',
     'halfExitAtResistance: false, // خروجِ کامل در اولین سقف'),
])
