/**
 * frontend-v2/src/features/technical/overlays/corporateEventsOverlay.ts
 *
 * اورلی رویدادهای تعدیلی و شرکتی بورس بر پایه مهندسی معکوس رهاورد ۳۶۵ (Rahavard 365):
 * - نشانگرهای دایره‌ای و مستطیلی اختصاصی در امتداد محور زمان در پایین چارت:
 *   - M (مجمع عمومی - Assembly): دایره سرخابی/بنفش (#d946ef) با حاشیه (#f0abfc)
 *   - D (سود نقدی - Dividend): دایره فیروزه‌ای/آبی (#0ea5e9) با حاشیه (#38bdf8)
 *   - E (افزایش سرمایه - Capital / Equity change): دایره زمردی/سبز (#10b981) با حاشیه (#34d399)
 * - چیدمان چندگانه روی یک تاریخ به صورت انباشته عمودی (Stacking) دقیقاً مشابه رهاورد ۳۶۵
 */

import { registerOverlay } from 'klinecharts';
import type {
  OverlayTemplate,
  OverlayFigure,
  OverlayCreateFiguresCallbackParams,
} from 'klinecharts';
import { useUiStore } from '@shared/stores/uiStore';
import { useTechnicalStore } from '../model/technicalStore';
import type { CorporateEventItem } from '../model/types';

function getIsLight(): boolean {
  try {
    const t = useUiStore.getState().theme;
    return t === 'warm' || t === 'cool';
  } catch {
    return false;
  }
}

function parseDateToTimestamp(dateStr: string): number {
  if (!dateStr) return 0;
  const clean = dateStr.replace(/\//g, '-').trim();
  const d = new Date(clean + 'T00:00:00Z');
  const t = d.getTime();
  return isNaN(t) ? 0 : t;
}

export function registerCorporateEventsOverlay(): void {
  const template: OverlayTemplate<{ events: CorporateEventItem[] }> = {
    name: 'corporateEvents',
    totalStep: 1,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: (params: OverlayCreateFiguresCallbackParams<{ events: CorporateEventItem[] }>): OverlayFigure[] => {
      const { overlay, chart, bounding } = params;

      const isVisible = useTechnicalStore.getState().showCorporateEvents;
      if (!isVisible) return [];

      const rawEvents: CorporateEventItem[] =
        (overlay.extendData as { events?: CorporateEventItem[] } | null)?.events ??
        useTechnicalStore.getState().corporateEvents;

      if (!rawEvents || rawEvents.length === 0) return [];

      const dataList = chart.getDataList();
      if (!dataList || dataList.length === 0) return [];

      const figures: OverlayFigure[] = [];
      const bottomY = bounding.height - 24;

      // گروهبندی رویدادها بر مبنای تاریخ جهت استک عمودی
      const dateStacks = new Map<string, number>();

      for (const ev of rawEvents) {
        if (!ev.date) continue;
        const ts = parseDateToTimestamp(ev.date);
        let x = -1;

        if (params.xAxis && typeof params.xAxis.convertTimestampToPixel === 'function' && ts > 0) {
          x = params.xAxis.convertTimestampToPixel(ts);
        }

        // اگر از طریق تایم‌استمپ مستقیم پیدا نشد، با کندل‌های نزدیک تطبیق می‌دهیم
        if (x == null || isNaN(x) || x <= 0) {
          for (let i = 0; i < dataList.length; i++) {
            const candleTs = dataList[i].timestamp;
            if (Math.abs(candleTs - ts) <= 86400 * 1000) {
              if (params.xAxis && typeof (params.xAxis as { convertToPixel?: (v: number) => number }).convertToPixel === 'function') {
                x = (params.xAxis as { convertToPixel: (v: number) => number }).convertToPixel(i);
              }
              break;
            }
          }
        }

        if (x == null || isNaN(x) || x < 0 || x > bounding.width) {
          continue;
        }

        // شمارش رویدادهای هم‌تاریخ برای استک عمودی
        const dateKey = ev.date.substring(0, 10);
        const stackIndex = dateStacks.get(dateKey) ?? 0;
        dateStacks.set(dateKey, stackIndex + 1);

        const y = bottomY - stackIndex * 22;

        // تعیین نوع رویداد: M (مجمع), D (سود نقدی), E (افزایش سرمایه)
        let kind: 'M' | 'D' | 'E' = 'M';
        if (ev.kind) {
          kind = ev.kind;
        } else if (ev.type === 'shareChange' || ev.type.includes('capital') || ev.type.includes('share')) {
          kind = 'E';
        } else if (ev.type === 'priceAdjust' || ev.type.includes('dividend')) {
          kind = 'D';
        }

        const isLight = getIsLight();
        let bg = isLight ? '#a21caf' : '#d946ef'; // Magenta
        let border = isLight ? '#c026d3' : '#f0abfc';
        if (kind === 'D') {
          bg = isLight ? '#0284c7' : '#0ea5e9'; // Cyan/Blue
          border = isLight ? '#0369a1' : '#38bdf8';
        } else if (kind === 'E') {
          bg = isLight ? '#059669' : '#10b981'; // Emerald/Green
          border = isLight ? '#047857' : '#34d399';
        }

        // ۱. نشانگر رویداد: در رهاورد ۳۶۵ افزایش سرمایه (E) با مربع گوشه‌گرد و مجمع/سود با دایره نشان داده می‌شود
        if (kind === 'E') {
          figures.push({
            type: 'rect',
            attrs: {
              x: x - 8.5,
              y: y - 8.5,
              width: 17,
              height: 17,
            },
            styles: {
              style: 'fill_stroke',
              color: bg,
              borderColor: border,
              borderWidth: 1.5,
              borderRadius: 3,
            },
          });
        } else {
          figures.push({
            type: 'circle',
            attrs: {
              x,
              y,
              r: 9,
            },
            styles: {
              style: 'fill_stroke',
              color: bg,
              borderColor: border,
              borderWidth: 1.5,
            },
          });
        }

        // ۲. نماد حرف لاتین در مرکز دایره (M, D, E)
        figures.push({
          type: 'text',
          attrs: {
            x,
            y: y + 0.5,
            text: kind,
            align: 'center',
            baseline: 'middle',
          },
          styles: {
            color: '#ffffff',
            size: 10,
            weight: 'bold',
            family: 'sans-serif',
          },
        });
      }

      return figures;
    },
  };

  try {
    registerOverlay(template);
  } catch {
    // جلوگیری از خطای ثبت مجدد
  }
}
