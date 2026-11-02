/**
 * frontend-v2/src/features/technical/overlays/__tests__/technicalOverlays.test.ts
 *
 * آزمون‌های محاسباتی و ترسیمی اورلی‌های FTS، پیش‌بینی هوش مصنوعی و پرایس‌اکشن SMC:
 * ۱. تولید کدرنگ، چندضلعی کان، خط میانه و بج‌های احتمالاتی predictionCone
 * ۲. تشخیص زون‌های صعودی/نزولی FVG و Order Block و کاهش شفافیت در صورت Mitigation
 * ۳. سطوح حمایت/مقاومت، کانال روند و خطوط پیوت برنجی FTS
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  registerPredictionOverlay,
} from '../predictionOverlay';
import {
  registerFVGOverlay,
  registerOrderBlockOverlay,
  registerAllSMCZonesOverlay,
} from '../smcOverlays';
import {
  registerFTSSupportResistanceOverlay,
  registerFTSTrendChannelOverlay,
  registerFTSKeyPivotOverlay,
} from '../ftsOverlays';
import {
  registerCorporateEventsOverlay,
} from '../corporateEventsOverlay';
import { useTechnicalStore } from '../../model/technicalStore';
import type { PredictionData, PriceZone, CorporateEventItem } from '../../model/types';

// ثبت قالب‌های اورلی
const registeredTemplates = new Map<string, any>();

vi.mock('klinecharts', () => ({
  registerOverlay: vi.fn((template: any) => {
    registeredTemplates.set(template.name, template);
  }),
}));

function createMockParams(overlayName: string, extendData: any = null, coordinates: any[] = []) {
  return {
    chart: {
      getDataList: () => [
        { timestamp: 1730000000000, open: 1000, high: 1050, low: 980, close: 1020, volume: 50000 },
        { timestamp: 1730086400000, open: 1020, high: 1100, low: 1010, close: 1080, volume: 75000 },
      ],
      convertToPixel: vi.fn(({ dataIndex, value }: any) => {
        if (typeof dataIndex === 'number') return { x: dataIndex * 30 + 50, y: 100 };
        if (typeof value === 'number') return { x: 50, y: Math.max(10, 500 - value * 0.2) };
        return { x: 0, y: 0 };
      }),
    },
    xAxis: {
      convertToPixel: (idx: number) => idx * 30 + 50,
      convertTimestampToPixel: (ts: number) => (ts - 1730000000000) / 1000000 + 50,
    },
    yAxis: {
      convertToPixel: (price: number) => Math.max(10, 500 - price * 0.2),
    },
    bounding: {
      width: 800,
      height: 500,
    },
    overlay: {
      name: overlayName,
      extendData,
    },
    coordinates,
  };
}

describe('Technical Overlays Figure Generators', () => {
  beforeEach(() => {
    registeredTemplates.clear();
  });

  describe('predictionCone Overlay', () => {
    it('creates shaded polygon, P50 dashed trajectory and upside/volatility badges', () => {
      registerPredictionOverlay();
      const template = registeredTemplates.get('predictionCone');
      expect(template).toBeDefined();

      const predictionData: PredictionData = {
        symbol: 'FOOLAD',
        generatedAt: 1730086400000,
        horizon: 3,
        isLiquid: true,
        forecastSteps: [
          { stepIndex: 1, timestamp: 1730172800000, p10: 1040, p50: 1100, p90: 1150 },
          { stepIndex: 2, timestamp: 1730259200000, p10: 1030, p50: 1120, p90: 1190 },
          { stepIndex: 3, timestamp: 1730345600000, p10: 1020, p50: 1150, p90: 1240 },
        ],
      };

      const params = createMockParams('predictionCone', predictionData);
      const figures = template.createPointFigures(params);

      expect(figures.length).toBeGreaterThan(4);

      // ۱. چندضلعی کان با رنگ برنجی شفاف
      const polygonFigure = figures.find((f: any) => f.type === 'polygon');
      expect(polygonFigure).toBeDefined();
      expect(polygonFigure.styles.color).toBe('rgba(218, 165, 32, 0.15)');

      // ۲. خط میانه P50
      const p50Line = figures.find((f: any) => f.type === 'line' && f.styles.color === '#eab308');
      expect(p50Line).toBeDefined();
      expect(p50Line.styles.style).toBe('dashed');

      // ۳. نقطه پایانی افق زمانی
      const terminalCircle = figures.find((f: any) => f.type === 'circle');
      expect(terminalCircle).toBeDefined();
      expect(terminalCircle.attrs.r).toBe(4.5);

      // ۴. بج‌های احتمال صعود و بزرگ‌نمایی نوسان
      const texts = figures.filter((f: any) => f.type === 'text');
      const upsideText = texts.find((t: any) => t.attrs.text.includes('احتمال صعود'));
      const volText = texts.find((t: any) => t.attrs.text.includes('بزرگ‌نمایی نوسان'));

      expect(upsideText).toBeDefined();
      expect(volText).toBeDefined();
    });

    it('returns empty array when forecastSteps is missing', () => {
      registerPredictionOverlay();
      const template = registeredTemplates.get('predictionCone');
      const params = createMockParams('predictionCone', null);
      const figures = template.createPointFigures(params);
      expect(figures).toEqual([]);
    });
  });

  describe('SMC Overlays (FVG & Order Block)', () => {
    beforeEach(() => {
      useTechnicalStore.getState().setShowSMCZones(true);
    });

    it('creates bullish FVG with green fill and dashed equilibrium line', () => {
      registerFVGOverlay();
      const template = registeredTemplates.get('fvgZone');
      expect(template).toBeDefined();

      const fvgZone: PriceZone = {
        id: 'fvg-bull-1',
        type: 'FVG',
        isBullish: true,
        top: 1100,
        bottom: 1040,
        equilibrium: 1070,
        startIndex: 0,
        startTs: 1730000000000,
        mitigated: false,
      };

      const params = createMockParams('fvgZone', { zone: fvgZone });
      const figures = template.createPointFigures(params);

      expect(figures.length).toBeGreaterThanOrEqual(3);

      const rectFigure = figures.find((f: any) => f.type === 'rect');
      expect(rectFigure).toBeDefined();
      expect(rectFigure.styles.color).toBe('rgba(34, 197, 94, 0.07)');

      const eqLine = figures.find((f: any) => f.type === 'line');
      expect(eqLine).toBeDefined();
      expect(eqLine.styles.color).toBe('#22c55e');
      expect(eqLine.styles.style).toBe('dashed');

      const textFigure = figures.find((f: any) => f.type === 'text');
      expect(textFigure.attrs.text).toContain('FVG · تقاضا');
    });

    it('creates bearish FVG with red fill and handles mitigation opacity reduction', () => {
      registerFVGOverlay();
      const template = registeredTemplates.get('fvgZone');

      const fvgMitigated: PriceZone = {
        id: 'fvg-bear-1',
        type: 'FVG',
        isBullish: false,
        top: 1200,
        bottom: 1150,
        equilibrium: 1175,
        startIndex: 0,
        startTs: 1730000000000,
        mitigated: true,
        mitigatedTs: 1730086400000,
      };

      const params = createMockParams('fvgZone', { zone: fvgMitigated });
      const figures = template.createPointFigures(params);

      const rectFigure = figures.find((f: any) => f.type === 'rect');
      expect(rectFigure).toBeDefined();
      // شفافیت کاهش‌یافته زون مصرف‌شده
      expect(rectFigure.styles.color).toBe('rgba(239, 68, 68, 0.02)');

      const textFigure = figures.find((f: any) => f.type === 'text');
      expect(textFigure.attrs.text).toContain('مصرف');
    });

    it('registers and renders order block overlay', () => {
      registerOrderBlockOverlay();
      const template = registeredTemplates.get('orderBlockZone');
      expect(template).toBeDefined();

      const obZone: PriceZone = {
        id: 'ob-test-1',
        type: 'ORDER_BLOCK',
        isBullish: true,
        top: 1100,
        bottom: 1060,
        equilibrium: 1080,
        startIndex: 0,
        startTs: 1730000000000,
        mitigated: false,
      };

      const params = createMockParams('orderBlockZone', { zone: obZone });
      const figures = template.createPointFigures(params);
      expect(figures.length).toBeGreaterThanOrEqual(3);
      expect(figures.some((f: any) => f.type === 'rect')).toBe(true);
    });

    it('creates composite smcZones rendering multiple zones', () => {
      registerAllSMCZonesOverlay();
      const template = registeredTemplates.get('smcZones');
      expect(template).toBeDefined();

      const zones: PriceZone[] = [
        {
          id: 'z1',
          type: 'FVG',
          isBullish: true,
          top: 1050,
          bottom: 1010,
          equilibrium: 1030,
          startIndex: 0,
          startTs: 1730000000000,
          mitigated: false,
        },
        {
          id: 'z2',
          type: 'ORDER_BLOCK',
          isBullish: false,
          top: 1150,
          bottom: 1120,
          equilibrium: 1135,
          startIndex: 1,
          startTs: 1730086400000,
          mitigated: false,
        },
      ];

      const params = createMockParams('smcZones', { zones });
      const figures = template.createPointFigures(params);

      // هر زون شامل حداقل مستطیل، خط تعادل و متن است (۲ * ۳ = ۶)
      expect(figures.length).toBeGreaterThanOrEqual(6);
    });
  });

  describe('FTS Overlays (Support/Resistance, Channel, Pivot)', () => {
    it('creates FTS support & resistance levels with brass badges', () => {
      registerFTSSupportResistanceOverlay();
      const template = registeredTemplates.get('ftsSupportResistance');
      expect(template).toBeDefined();

      const params = createMockParams('ftsSupportResistance', {
        levels: [
          { price: 1000, type: 'support', labelFa: 'حمایت FTS', strength: 3 },
          { price: 1200, type: 'resistance', labelFa: 'مقاومت FTS', strength: 2 },
        ],
      });

      const figures = template.createPointFigures(params);
      expect(figures.length).toBe(4); // ۲ خط + ۲ متن

      const lines = figures.filter((f: any) => f.type === 'line');
      expect(lines).toHaveLength(2);
      expect(lines[0].attrs.coordinates[0].x).toBe(0);
      expect(lines[0].attrs.coordinates[1].x).toBe(800);
    });

    it('creates FTS trend channel with parallel lines and shaded brass area', () => {
      registerFTSTrendChannelOverlay();
      const template = registeredTemplates.get('ftsTrendChannel');
      expect(template).toBeDefined();

      const coordinates = [
        { x: 50, y: 150 },
        { x: 250, y: 100 },
        { x: 50, y: 200 },
      ];

      const params = createMockParams('ftsTrendChannel', null, coordinates);
      const figures = template.createPointFigures(params);

      expect(figures.length).toBeGreaterThanOrEqual(4);
      const polygon = figures.find((f: any) => f.type === 'polygon');
      expect(polygon).toBeDefined();
      expect(polygon.styles.color).toBe('rgba(218, 165, 32, 0.08)');
    });

    it('creates FTS key pivot line with dashed golden line and pivot badge', () => {
      registerFTSKeyPivotOverlay();
      const template = registeredTemplates.get('ftsKeyPivot');
      expect(template).toBeDefined();

      const coordinates = [{ x: 100, y: 180 }];
      const params = createMockParams('ftsKeyPivot', null, coordinates);
      const figures = template.createPointFigures(params);

      expect(figures.length).toBe(2);
      expect(figures[0].styles.color).toBe('#eab308');
      expect(figures[1].attrs.text).toBe('پیوت کلیدی FTS');
    });
  });

  describe('corporateEvents Overlay (Rahavard 365 M/D/E)', () => {
    it('creates M (assembly), D (dividend), and E (capital increase) badges stacked along bottom axis', () => {
      registerCorporateEventsOverlay();
      const template = registeredTemplates.get('corporateEvents');
      expect(template).toBeDefined();

      const events: CorporateEventItem[] = [
        { date: '2024-10-30', type: 'priceAdjust', kind: 'M' },
        { date: '2024-10-31', type: 'shareChange', kind: 'E' },
        { date: '2024-10-31', type: 'priceAdjust', kind: 'D' }, // Same date -> vertical stacking
      ];

      const params = createMockParams('corporateEvents', { events });
      const figures = template.createPointFigures(params);

      expect(figures.length).toBe(6); // 2 circles (M, D) + 1 rect (E) + 3 text markers

      const circles = figures.filter((f: any) => f.type === 'circle');
      const rects = figures.filter((f: any) => f.type === 'rect');
      const texts = figures.filter((f: any) => f.type === 'text');
      expect(circles).toHaveLength(2);
      expect(rects).toHaveLength(1);
      expect(texts).toHaveLength(3);

      const markerLetters = texts.map((t: any) => t.attrs.text);
      expect(markerLetters).toContain('M');
      expect(markerLetters).toContain('D');
      expect(markerLetters).toContain('E');

      // Verifying vertical stacking on same date
      const sameDateTexts = texts.filter((t: any) => t.attrs.text === 'E' || t.attrs.text === 'D');
      expect(sameDateTexts[0].attrs.x).toBe(sameDateTexts[1].attrs.x);
      expect(sameDateTexts[0].attrs.y).not.toBe(sameDateTexts[1].attrs.y);
    });
  });
});
