export type {
  Candle,
  CandleTime,
  DetectorId,
  PatternAnchor,
  PatternBias,
  PatternEvent,
  PatternFamily,
  ProvisionalSwing,
  ScanOptions,
  ScanResult,
  SwingPoint,
} from './types';

export { CandleEdgeInputError, assertValidCandles } from './validation';
export { candleParts, isDowntrend, isUptrend } from './candleMath';
export {
  isBearishEngulfing,
  isBullishEngulfing,
  isDoji,
  isHammer,
  isShootingStar,
} from './candlePatterns';
export {
  findLocalExtrema,
  findProvisionalSwings,
  findSwingPoints,
} from './swings';
export * from './structurePatterns';
export { scanPatterns } from './scanner';

export const CANDLEEDGE_SOURCE = {
  repository: 'https://github.com/michaelsboost/CandleEdge',
  commit: '75761e26b23ccaf59b31365e1ec817374673d77b',
  license: 'MIT',
  copyright: 'Copyright (c) 2026 Michael Schwartz',
  reviewedAt: '2026-10-25',
} as const;
