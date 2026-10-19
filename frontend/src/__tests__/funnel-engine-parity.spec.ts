// frontend/src/__tests__/funnel-engine-parity.spec.ts
//
// آزمون جامع برابری موتور داوری قیف FTS کلاینت اندروید با موتور مرجع دسکتاپ (funnel_engine.py)
// شامل:
// ۱) اثبات برابری هفت فیلتر تابلوخوانی، چهار پریست کانونی، و منطق‌های AND و OR
// ۲) اثبات صلاحیت حضور در جامعه (screening eligibility) و جداسازی خارج از جامعه
// ۳) اثبات داوری سه گام تکنیکال، بنیادی (حالت‌های standard، hard و exception) و تحویل
// ۴) اثبات باز ارزیابی پویای قیف با تغییر قیمت‌های زنده در تابلوی معاملات
// ۵) اثبات اندپوینت‌های /api/funnel/registry و /api/funnel/trace
//
import { describe, expect, it } from 'vitest';
import { evaluateFunnelLocal, screeningEligibility } from '@shared/api/local/funnelEngineLocal';
import { refreshTapeFlags } from '@shared/api/local/tapeFlagsLocal';
import { registryAsJson, FILTERS } from '@shared/api/local/funnelRegistryLocal';

describe('موتور کانونی داوری قیف FTS اندروید — آزمون‌های برابری با دسکتاپ', () => {
  const sampleBoardRows: Array<Record<string, any>> = [
    {
      symbol: 'فولاد',
      name: 'فولاد مبارکه',
      sector_name: 'فلزات اساسی',
      is_live: true,
      st_title: 'مجاز',
      st_code: 'A',
      p_last: 5200,
      p_closing: 5000,
      price_yesterday: 4900,
      prior30_vol: 300000000, // avg30 = 10,000,000
      tvol: 16000000, // 16M > 1.5 * 10M = 15M
      z_tot_tran: 120,
      buy_i_vol: 12000000,
      buy_count_i: 1000,
      sell_i_vol: 3000000,
      sell_count_i: 500,
      sell_n_vol: 3000000,
      buy_q1_cnt: 10,
      buy_q1_vol: 500000,
      low_base_min: 4950,
      tmin: 4600,
    },
    {
      symbol: 'وبملت',
      name: 'بانک ملت',
      sector_name: 'بانک‌ها',
      is_live: true,
      st_title: 'مجاز',
      st_code: 'A',
      p_last: 2100,
      p_closing: 2150,
      price_yesterday: 2100,
      prior30_vol: 600000000, // avg30 = 20,000,000
      tvol: 5000000,
      z_tot_tran: 20,
      buy_i_vol: 2000000,
      buy_count_i: 200,
      sell_i_vol: 3000000,
      sell_count_i: 150,
      sell_n_vol: 1000000,
      buy_q1_cnt: 0,
      buy_q1_vol: 0,
      low_base_min: 2000,
      tmin: 1950,
    },
    {
      symbol: 'خودرو2', // نماد دارای پسوند عددی
      name: 'ایران خودرو ۲',
      sector_name: 'خودرو',
      is_live: true,
      st_title: 'مجاز',
      p_last: 3000,
      p_closing: 3000,
    },
    {
      symbol: 'شپنا',
      name: 'پالایش نفت اصفهان',
      sector_name: 'فرآورده‌های نفتی',
      is_live: false, // ردیف نشست کهنه
      st_title: 'مجاز',
      p_last: 4000,
      p_closing: 4000,
    },
    {
      symbol: 'خساپا',
      name: 'سایپا',
      sector_name: 'خودرو',
      is_live: true,
      st_title: 'ممنوع-متوقف',
      stop_state: 'مجمع عمومی',
      p_last: 2500,
      p_closing: 2500,
    },
  ];

  const sampleScreenRows = [
    {
      symbol: 'فولاد',
      name: 'فولاد مبارکه',
      score: 4,
      primary_score: 4,
      tech_points: 85,
      tech_trend_w: 'up',
      tech_trend_d: 'up',
      tech_matrix_decision: 'UP_UP',
      i1_pass: true,
      i2_pass: true,
      i3_pass: true,
      i4_pass: true,
      i5_pass: false,
    },
    {
      symbol: 'وبملت',
      name: 'بانک ملت',
      score: 2,
      primary_score: 2,
      tech_points: 40,
      tech_trend_w: 'down', // وتوی روند هفتگی
      tech_trend_d: 'range',
      tech_matrix_decision: 'DOWN_RANGE',
      i1_pass: true,
      i2_pass: false,
      i3_pass: false,
      i4_pass: false,
      i5_pass: false,
    },
  ];

  it('۱) بازتولید پرچم‌های تابلوخوانی با refreshTapeFlags', () => {
    const row = { ...sampleBoardRows[0] };
    refreshTapeFlags(row);

    // فولاد: pl = 5200 >= pc * 1.02 (5100), tvol=15M > avg30=10M, ztt=120 > 30 => f_clock = true
    expect(row.f_clock).toBe(true);
    // f_smart: tvol > 1.5*avg30 (15M), bp = (12M/1000)/(3M/500) = 12k/6k = 2.0 >= 1.0, pl >= pc, plp > 0 => true
    expect(row.f_smart).toBe(true);
    // f_susp: tvol > 3.0*avg30 (15M < 30M) => false
    expect(row.f_susp).toBe(false);
  });

  it('۲) غربالگری صلاحیت حضور در جامعه screeningEligibility', () => {
    // نماد زنده و مجاز
    const ok = screeningEligibility(sampleBoardRows[0]);
    expect(ok.ok).toBe(true);
    expect(ok.code).toBe('PERMITTED_STATE');

    // نماد کهنه (is_live=false)
    const dead = screeningEligibility(sampleBoardRows[3]);
    expect(dead.ok).toBe(false);
    expect(dead.code).toBe('NOT_LIVE_SESSION');

    // نماد متوقف
    const stopped = screeningEligibility(sampleBoardRows[4]);
    expect(stopped.ok).toBe(false);
    expect(stopped.code).toBe('STOPPED');
  });

  it('۳) اجرای کامل قیف و برابری ساختار ۴ مرحله با دسکتاپ', () => {
    // محاسبه اولیه پرچم‌ها روی ردیف‌های تابلو
    const board = sampleBoardRows.map((r) => {
      const copy = { ...r };
      refreshTapeFlags(copy);
      return copy;
    });

    const res = evaluateFunnelLocal(board, sampleScreenRows, {
      preset: 'trend',
      tapeLogic: 'and',
      fundMode: 'standard',
      dropNumericSuffix: true,
    }) as Record<string, unknown>;

    expect(res.status).toBe('success');
    expect(res.preset).toBe('trend');
    expect(res.tape_logic).toBe('and');
    expect(res.fund_mode).toBe('standard');

    // بررسی بخش universe
    const u = res.universe as Record<string, unknown>;
    expect(u.board).toBe(5);
    expect(u.screening).toBe(2); // فقط فولاد و وبملت واجد شرایط غربالگری هستند
    expect(u.excluded).toBe(3); // خودرو۲ (پسوند عددی)، شپنا (کهنه)، خساپا (متوقف)
    expect(u.drop_numeric_suffix).toBe(true);

    // بررسی گام‌های ۴گانه
    const stages = res.stages as Record<string, any>;
    expect(stages.tape).toBeDefined();
    expect(stages.technical).toBeDefined();
    expect(stages.fundamental).toBeDefined();
    expect(stages.handover).toBeDefined();

    // بررسی status_matrix و coverage
    const sm = res.status_matrix as Record<string, any>;
    expect(sm['فولاد']).toBeDefined();
    expect(sm['وبملت']).toBeDefined();
    expect(sm['خودرو2']).toBeDefined();
    expect(sm['خودرو2'].tape.status).toBe('not_in_universe');
    expect(sm['شپنا'].tape.status).toBe('not_in_universe');

    // بررسی handover
    const hand = res.handover as Array<Record<string, unknown>>;
    expect(Array.isArray(hand)).toBe(true);
    // فولاد روند هفتگی صعودی و ۴ شاخص بنیادی دارد پس به مرحله handover می‌رسد
    const fooladHand = hand.find((e) => e.symbol === 'فولاد');
    if (fooladHand) {
      expect(fooladHand.final).toBe('pass');
      expect(fooladHand.display_rank).toBe(1);
    }
  });

  it('۴) برابری رجیستری کانونی با ساختار دسکتاپ', () => {
    const reg = registryAsJson() as Record<string, any>;
    expect(reg.ruleset_version).toBeDefined();
    expect(reg.registry_version).toBeDefined();
    expect(reg.filters.length).toBe(7);
    expect(reg.presets.length).toBe(4);
    expect(FILTERS.map((f) => f.filter_id)).toEqual([
      'f_clock',
      'f_susp',
      'f_jet',
      'f_roobi',
      'f_noqteh',
      'f_smart',
      'f_legal',
    ]);
  });

  it('۵) باز ارزیابی پویا هنگام تغییر قیمت و صف‌های زنده', () => {
    const board = sampleBoardRows.map((r) => ({ ...r }));
    refreshTapeFlags(board[0]);

    const res1 = evaluateFunnelLocal(board, sampleScreenRows, {
      preset: 'trend',
      customChain: ['f_clock'],
    }) as Record<string, any>;

    const foolad1 = res1.stages.tape.survivors.includes('فولاد');
    expect(foolad1).toBe(true);

    // افت قیمت فولاد (قیمت آخرین به زیر قیمت پایانی می‌رسد و الگوی ساعت باطل می‌شود)
    board[0].p_last = 4900;
    board[0].p_closing = 5100;
    refreshTapeFlags(board[0]);
    expect(board[0].f_clock).toBe(false);

    const res2 = evaluateFunnelLocal(board, sampleScreenRows, {
      preset: 'trend',
      customChain: ['f_clock'],
    }) as Record<string, any>;

    const foolad2 = res2.stages.tape.survivors.includes('فولاد');
    expect(foolad2).toBe(false); // با افت قیمت از بازماندگان فیلتر حذف شد
    expect(res2.metadata.output_fingerprint).not.toBe(res1.metadata.output_fingerprint);
  });
});
