// shared/api/local/funnelRegistryLocal.ts — رجیستری رسمی فیلترها و پریست‌های قیف FTS در اندروید
//
// همتای دقیقِ funnel_registry.py در دسکتاپ:
//   - هفت فیلتر کانونی: f_clock, f_susp, f_jet, f_roobi, f_noqteh, f_smart, f_legal
//   - چهار پریست کانونی: swing, trend, hourglass, custom
//   - گیت‌های تکنیکال: trend_matrix و hourglass_ma52_rsi5_weekly
//
export type FilterParam = {
  param_id: string;
  label: string;
  source: string;
  value: number | null;
  value_text?: string | null;
  unit: string;
  configurable: boolean;
  min?: number | null;
  max?: number | null;
  note?: string | null;
};

export type FunnelFilter = {
  filter_id: string;
  name: string;
  description: string;
  source_file: string;
  source_hash: string;
  formula_version: string;
  backend_impl: string;
  availability: 'backend' | 'backend-partial';
  status: 'canonical';
  note?: string | null;
  params: FilterParam[];
  test_refs: string[];
};

export type FunnelPreset = {
  preset_id: 'swing' | 'trend' | 'hourglass' | 'custom';
  label: string;
  chain: string[];
  technical_gate: string;
  source: string;
  status: string;
  note?: string | null;
};

export const TREND_GATE = 'trend_matrix';
export const HOURGLASS_GATE = 'hourglass_ma52_rsi5_weekly';
export const REGISTRY_VERSION = '1';
export const RULESET_VERSION = '6637192e4d10';

export const FILTERS: FunnelFilter[] = [
  {
    filter_id: 'f_clock',
    name: 'الگوی ساعت',
    description: 'آخرین روی پایانیِ ۲٪، حجمِ بیشتر از میانگینِ نشست‌ها و تعدادِ معامله.',
    source_file: 'docs/الگوی ساعت.txt',
    source_hash: '6637192e4d10a73d',
    formula_version: 'txt-1',
    backend_impl: 'tape_flags.clock_flag',
    availability: 'backend',
    status: 'canonical',
    test_refs: ['dev/test_tape_flags_v1059.py', 'tools/tape_formula_parity.py'],
    params: [
      { param_id: 'clock_delta', label: 'فاصلۀ آخرین از پایانی', source: 'docs/الگوی ساعت.txt:1', value: 0.02, unit: 'کسر', configurable: false },
      { param_id: 'vol_mult', label: 'ضریبِ حجم', source: 'docs/الگوی ساعت.txt:1', value: 1.0, unit: '×میانگین', configurable: true, min: 1.0, max: 5.0 },
      { param_id: 'min_trades', label: 'حداقلِ تعدادِ معامله', source: 'docs/الگوی ساعت.txt:1', value: 30, unit: 'معامله', configurable: false },
      { param_id: 'base_sessions', label: 'پنجرةٔ میانگینِ حجم', source: 'docs/الگوی ساعت.txt:1', value: 30, unit: 'نشست', configurable: false },
    ],
  },
  {
    filter_id: 'f_susp',
    name: 'حجم مشکوک',
    description: 'حجمِ همین نشست سه برابرِ میانگینِ سی نشست، با حداقلِ تعدادِ معامله.',
    source_file: 'docs/حجم مشکوک.txt',
    source_hash: 'b8a185c4168be33e',
    formula_version: 'txt-1',
    backend_impl: 'tape_flags.suspicious_flag',
    availability: 'backend',
    status: 'canonical',
    test_refs: ['dev/test_tape_flags_v1059.py', 'tools/tape_formula_parity.py'],
    params: [
      { param_id: 'vol_mult', label: 'ضریبِ حجم', source: 'docs/حجم مشکوک.txt:1', value: 3.0, unit: '×میانگین', configurable: true, min: 2.5, max: 5.0 },
      { param_id: 'min_trades', label: 'حداقلِ تعدادِ معامله', source: 'docs/حجم مشکوک.txt:1', value: 50, unit: 'معامله', configurable: false },
      { param_id: 'base_sessions', label: 'پنجرةٔ میانگینِ حجم', source: 'docs/حجم مشکوک.txt:1', value: 30, unit: 'نشست', configurable: false },
    ],
  },
  {
    filter_id: 'f_jet',
    name: 'فیلتر جت',
    description: 'حجمِ سنگین + قدرتِ خریدارِ حقیقی + شکستنِ سقفِ ایستای هشت پنجره.',
    source_file: 'docs/فیلتر جت.txt',
    source_hash: 'e93cab46073567c0',
    formula_version: 'txt-1',
    backend_impl: 'tape_flags.jet_flag',
    availability: 'backend',
    status: 'canonical',
    test_refs: ['dev/test_tape_flags_v1059.py', 'tools/tape_formula_parity.py'],
    params: [
      { param_id: 'vol_mult', label: 'ضریبِ حجم', source: 'docs/فیلتر جت.txt:1', value: 3.0, unit: '×میانگین', configurable: false },
      { param_id: 'buyer_power', label: 'سرانۀ سفارشِ خرید به فروشِ حقیقی', source: 'docs/فیلتر جت.txt:1', value: 1.5, unit: '×', configurable: false },
      { param_id: 'min_trades', label: 'حداقلِ تعدادِ معامله', source: 'docs/فیلتر جت.txt:1', value: 100, unit: 'معامله', configurable: false },
    ],
  },
  {
    filter_id: 'f_roobi',
    name: 'کف روبی صف فروش',
    description: 'قیمت رویِ آستانۀ مجاز پایین چسبیده و صفِ خریدِ سنگین همان‌جا نشسته است.',
    source_file: 'docs/کف روبی صف فروش.txt',
    source_hash: '053a12a7c96b6e4f',
    formula_version: 'txt-1',
    backend_impl: 'tape_flags.roobi_flag',
    availability: 'backend-partial',
    status: 'canonical',
    test_refs: ['dev/test_tape_flags_v1059.py', 'tools/tape_formula_parity.py'],
    params: [
      { param_id: 'plp_max', label: 'سقفِ درصدِ آخرین', source: 'docs/کف روبی صف فروش.txt:1', value: -1.0, unit: '٪', configurable: false },
      { param_id: 'zd1_min', label: 'حداقلِ تعدادِ سفارشِ سطرِ اولِ خرید', source: 'docs/کف روبی صف فروش.txt:1', value: 1, unit: 'سفارش', configurable: false },
      { param_id: 'qd1_min', label: 'حداقلِ حجمِ سفارشِ سطرِ اولِ خرید', source: 'docs/کف روبی صف فروش.txt:1', value: 100, unit: 'سهم', configurable: false },
    ],
  },
  {
    filter_id: 'f_noqteh',
    name: 'نقطه زنی',
    description: 'قیمت پایانی زیرِ ۳٪ از کمینۀ ماه، با حجمِ بیشتر از میانگین و حداقلِ تعدادِ معامله.',
    source_file: 'docs/نقطه زنی.txt',
    source_hash: 'e5d4fd99a6811443',
    formula_version: 'txt-1',
    backend_impl: 'tape_flags.noqteh_flag',
    availability: 'backend',
    status: 'canonical',
    test_refs: ['dev/test_tape_flags_v1059.py', 'tools/tape_formula_parity.py'],
    params: [
      { param_id: 'max_dist', label: 'سقفِ فاصلۀ تا کفِ ماه', source: 'docs/نقطه زنی.txt:1', value: 3.0, unit: '٪', configurable: false },
      { param_id: 'low_window', label: 'پنجرةٔ کمینه', source: 'docs/نقطه زنی.txt:1', value: 29, unit: 'نشست', configurable: false },
      { param_id: 'vol_mult', label: 'ضریبِ حجم', source: 'docs/نقطه زنی.txt:1', value: 1.0, unit: '×میانگین', configurable: false },
      { param_id: 'min_trades', label: 'حداقلِ تعدادِ معامله', source: 'docs/نقطه زنی.txt:1', value: 5, unit: 'معامله', configurable: false },
    ],
  },
  {
    filter_id: 'f_smart',
    name: 'ورود پول هوشمند',
    description: 'حجمِ ۱٫۵ برابرِ میانگین با سرانۀ سفارشِ خریدِ حقیقیِ بیشتر از فروش، رویِ روندِ صعودیِ همان نشست.',
    source_file: 'docs/ورود پول هوشمند.txt',
    source_hash: '590e52a23c78166f',
    formula_version: 'txt-1',
    backend_impl: 'tape_flags.smart_money_flag',
    availability: 'backend-partial',
    status: 'canonical',
    test_refs: ['dev/test_tape_flags_v1059.py', 'tools/tape_formula_parity.py'],
    params: [
      { param_id: 'vol_mult', label: 'ضریبِ حجم', source: 'docs/ورود پول هوشمند.txt:1', value: 1.5, unit: '×میانگین', configurable: false },
      { param_id: 'buyer_power_ge', label: 'سرانۀ خرید ≥ سرانۀ فروشِ حقیقی', source: 'docs/ورود پول هوشمند.txt:1', value: 1.0, unit: '×', configurable: false },
    ],
  },
  {
    filter_id: 'f_legal',
    name: 'پول هوشمند و کد به کد حقوقی به حقیقی',
    description: 'همان چهار قیدِ «ورود پول هوشمند» + خریدِ حقوقی و فروشِ حقیقیِ هر دو بالایِ نصفِ حجمِ نشست.',
    source_file: 'docs/ورود پول هوشمند و کد به کد حقوقی به حقیقی.txt',
    source_hash: '685b8832a5a57e33',
    formula_version: 'txt-1',
    backend_impl: 'tape_flags.legal_to_real_flag',
    availability: 'backend-partial',
    status: 'canonical',
    test_refs: ['dev/test_tape_flags_v1059.py', 'tools/tape_formula_parity.py'],
    params: [
      { param_id: 'vol_mult', label: 'ضریبِ حجم', source: 'docs/ورود پول هوشمند و کد به کد.txt:1', value: 1.5, unit: '×میانگین', configurable: false },
      { param_id: 'buyer_power_ge', label: 'سرانۀ خرید ≥ سرانۀ فروشِ حقیقی', source: 'docs/ورود پول هوشمند و کد به کد.txt:1', value: 1.0, unit: '×', configurable: false },
      { param_id: 'legal_share_of_tvol', label: 'سهمِ حجمِ حقوقی/حقیقی', source: 'docs/ورود پول هوشمند و کد به کد.txt:1', value: 0.5, unit: 'کسر', configurable: false },
    ],
  },
];

export const FILTERS_BY_ID = new Map<string, FunnelFilter>(FILTERS.map((f) => [f.filter_id, f]));

export const PRESETS: FunnelPreset[] = [
  {
    preset_id: 'swing',
    label: 'شخص نوسان‌گیر (زیر ۳ ماه)',
    chain: ['f_clock', 'f_jet', 'f_susp'],
    technical_gate: TREND_GATE,
    source: 'FTS_CHART3_extracted_text.txt',
    status: 'canonical',
    note: 'نوسان‌گیر: ساعت + جت + حجم مشکوک',
  },
  {
    preset_id: 'trend',
    label: 'شخص روندگیر (بالای ۳ ماه)',
    chain: ['f_roobi', 'f_noqteh'],
    technical_gate: TREND_GATE,
    source: 'FTS_CHART3_extracted_text.txt',
    status: 'canonical',
    note: 'روندگیر: کف‌روبی + نقطه‌زنی',
  },
  {
    preset_id: 'hourglass',
    label: 'استراتژی ساعت شنی (۳ تا ۱۰ ساله)',
    chain: [],
    technical_gate: HOURGLASS_GATE,
    source: 'jozve_FTS_handwritten_pages_25-34.md:74',
    status: 'unverified',
    note: 'ساعت شنی: گیت هفتگی MA52/RSI5',
  },
  {
    preset_id: 'custom',
    label: 'مسیر سفارشی (انتخاب دستی)',
    chain: [],
    technical_gate: TREND_GATE,
    source: 'مأموریتِ مالک ۱۴۰۵-۰۷-۱۶ بند ۴',
    status: 'canonical',
    note: 'زنجیره‌ای که کاربر می‌سازد',
  },
];

export const PRESETS_BY_ID = new Map<string, FunnelPreset>(PRESETS.map((p) => [p.preset_id, p]));

export function registryAsJson() {
  return {
    registry_version: REGISTRY_VERSION,
    ruleset_version: RULESET_VERSION,
    filters: FILTERS,
    presets: PRESETS,
    unimplemented_filters: {},
    gates: {
      technical: [TREND_GATE, HOURGLASS_GATE],
      fundamental: 'mandatory_i1_i2_i3_supporting_i4_i5',
    },
  };
}
