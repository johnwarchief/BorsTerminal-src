// model/patterns/config.ts
export interface PatternConfig {
  pivLeft: number;
  pivRight: number;
  atrPeriod: number;
  minTouchesPerLine: number;
  touchToleranceAtr: number;
  invalidationBufferAtr: number;
  /** نیم‌پنجرهٔ حذف هم‌پوشانی: ادامه‌دهندهٔ لنگرِ نزدیک‌تر از این مقدار کندل به یک بازگشتی حذف می‌شود. */
  overlapWindowBars: number;
  outcomeHorizon: number;
  returnHorizons: [number, number, number];
  returnsMinSamples: number;
  neutralMinTargetAtr: number;
  formationMinResolved: number;
  expiryGraceBars: number;
  expiryMinPoints: number;
  flag: {
    impulseLegAtrMin: number;
    channelMaxWidthPct: number;
    maxRetracePct: number;
    /** نسبت طول فشرده‌سازی به لگ؛ فشرده‌سازی بلندتر از این دیگر پرچم نیست. */
    maxDurationRatio: number;
    slopeOpposite: boolean;
    maxBars: number;
    minLegBars: number;
  };
  pennant: {
    impulseLegAtrMin: number;
    convergenceMin: number;
    maxRetracePct: number;
    maxDurationRatio: number;
    maxBars: number;
  };
  triangle: {
    flatToleranceAtr: number;
    convergenceMin: number;
    /** لگ اول نباید خودِ موج روند باشد؛ نسبت به بزرگ‌ترین لگ بعدی سنجیده می‌شود. */
    maxFirstLegRatio: number;
    maxBars: number;
    minSpan: number;
  };
  rectangle: { flatToleranceAtr: number; maxDriftPct: number; maxBars: number };
  wedge: { convergenceMin: number; maxFirstLegRatio: number; maxBars: number };
  hs: {
    headAboveShouldersAtr: number;
    shouldersToleranceAtr: number;
    /** سقف درصدیِ اختلاف شانه‌ها؛ ATR جاری بعد از ریزش می‌تواند بی‌معنا بزرگ شود. */
    shouldersTolerancePct: number;
    maxBars: number;
  };
  triple: { levelToleranceAtr: number; levelTolerancePct: number; maxBars: number };
  reversal: { minSpanBars: number };
  cup: { rimToleranceAtr: number; handleDepthPct: number; minDepthAtr: number; minBars: number; maxBars: number };
  rounding: {
    curvatureMin: number;
    minDepthAtr: number;
    minBulgeAtr: number;
    endSkewPct: number;
    minBars: number;
    maxBars: number;
  };
  tier2: {
    diamondConvergeMin: number;
    broadeningMin: number;
    islandGapAtr: number;
    /** حداکثر فاصلهٔ کندلیِ گپِ خروج از گپِ ورود (پنجرهٔ جزیره). */
    islandMaxBlockBars: number;
    /** پنجرهٔ خانوادهٔ جزیره برای `emitPattern`؛ ریشه بیش از این مقدار عقب نماند. */
    islandMaxBars: number;
    threePeaksToleranceAtr: number;
    /** حداقل شیبِ کلِ سه سقف (h3−h1) برای سه‌قله‌های صعودی/نزولی (R-PA-15). */
    threePeaksSlopeAtr: number;
  };
  /** p19 — Wedge & Channel Detector (Indi 407). همهٔ آستانه‌ها اینجا می‌مانند. */
  channelPivot: {
    /** طول پیوت دو طرفهٔ لبه‌ها (`ta.pivothigh/low(20,20)`). */
    pivotLen: number;
    autoPivotCount: number;
    autoLookbackBars: number;
    minAnchorSpacing: number;
    breakoutAtr: number;
    breakoutConfirmBars: number;
    expireAfterBreakBars: number;
    reclaimBars: number;
    lateStageWidthAtr: number;
    lateStageApexBars: number;
    touchTolAtr: number;
    violationTolAtr: number;
    minTouchSpacing: number;
    minWidthAtr: number;
    maxWidthAtr: number;
    balancePenaltyStart: number;
    balancePenaltyStrength: number;
    convergenceProjectionBars: number;
  };
}

export const PATTERN_CONFIG: PatternConfig = {
  pivLeft: 5,
  pivRight: 4,
  atrPeriod: 14,
  minTouchesPerLine: 2,
  touchToleranceAtr: 0.5,
  invalidationBufferAtr: 0.5,
  overlapWindowBars: 3,
  outcomeHorizon: 10,
  returnHorizons: [1, 3, 5],
  returnsMinSamples: 5,
  neutralMinTargetAtr: 0.5,
  formationMinResolved: 8,
  expiryGraceBars: 1,
  expiryMinPoints: 5,
  flag: {
    impulseLegAtrMin: 3.0,
    channelMaxWidthPct: 35,
    maxRetracePct: 38,
    maxDurationRatio: 2,
    slopeOpposite: true,
    maxBars: 40,
    minLegBars: 3,
  },
  pennant: {
    impulseLegAtrMin: 3.0,
    convergenceMin: 0.35,
    maxRetracePct: 38,
    maxDurationRatio: 2,
    maxBars: 30,
  },
  triangle: { flatToleranceAtr: 0.35, convergenceMin: 0.30, maxFirstLegRatio: 2, maxBars: 60, minSpan: 3 },
  rectangle: { flatToleranceAtr: 0.50, maxDriftPct: 8, maxBars: 80 },
  wedge: { convergenceMin: 0.30, maxFirstLegRatio: 2, maxBars: 60 },
  hs: { headAboveShouldersAtr: 0.50, shouldersToleranceAtr: 0.60, shouldersTolerancePct: 8, maxBars: 120 },
  triple: { levelToleranceAtr: 0.50, levelTolerancePct: 8, maxBars: 120 },
  reversal: { minSpanBars: 6 },
  cup: { rimToleranceAtr: 0.5, handleDepthPct: 33, minDepthAtr: 2, minBars: 20, maxBars: 160 },
  rounding: { curvatureMin: 0.55, minDepthAtr: 1, minBulgeAtr: 1, endSkewPct: 50, minBars: 30, maxBars: 200 },
  tier2: {
    diamondConvergeMin: 0.25,
    broadeningMin: 0.25,
    islandGapAtr: 0.5,
    islandMaxBlockBars: 5,
    islandMaxBars: 6,
    threePeaksToleranceAtr: 0.5,
    threePeaksSlopeAtr: 0.5,
  },
  channelPivot: {
    pivotLen: 20,
    autoPivotCount: 5,
    autoLookbackBars: 250,
    minAnchorSpacing: 10,
    breakoutAtr: 0.3,
    breakoutConfirmBars: 2,
    expireAfterBreakBars: 10,
    reclaimBars: 2,
    lateStageWidthAtr: 1.5,
    lateStageApexBars: 15,
    touchTolAtr: 0.2,
    violationTolAtr: 0.35,
    minTouchSpacing: 5,
    minWidthAtr: 1,
    maxWidthAtr: 20,
    balancePenaltyStart: 1.5,
    balancePenaltyStrength: 8,
    convergenceProjectionBars: 50,
  },
};
