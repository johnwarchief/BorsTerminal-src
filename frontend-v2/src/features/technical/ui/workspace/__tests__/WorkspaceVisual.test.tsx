/**
 * frontend-v2/src/features/technical/ui/workspace/__tests__/WorkspaceVisual.test.tsx
 *
 * قراردادِ بصری و کیبوردیِ کرومِ میزکار تکنیکال (B5، پاسِ unslop):
 * ۱. کفِ قلم ۱۲px برای همهٔ گره‌های متنیِ کروم (نوار بالا، نوار فعالیت، ریل، فید و پنل‌ها)
 * ۲. نبودِ font-bold/font-extrabold در سورسِ ui/workspace
 * ۳. ریتمِ ۴px و نبودِ utilityهای نیم‌گامی در سورسِ کروم (به‌همراه ScannerFeed)
 * ۴. هم‌ارتفاعیِ کنترل‌های نوار بالا (یک ریتمِ ۳۶px)
 * ۵. حلقهٔ focus-visible روی دکمه‌های نوار فعالیت و تب‌های فید
 * ۶. aria-current برای بخشِ فعال نوار فعالیت
 * ۷. دسترسیِ Tab به نوار فعالیت، تب‌های فید و کارت رویداد ریل
 *
 * دربارهٔ آزمونِ Tab: jsdom فوکوس را با کلید Tab جابه‌جا نمی‌کند؛ پس این‌جا
 * «تب‌پذیر بودن + ترتیبِ DOM» را می‌سنجیم و مسیرِ واقعیِ Tab در Edge با
 * Playwright در پذیرشِ زنده ثبت شده است (acceptance.json).
 */

import { readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TechnicalWorkspace } from '../../TechnicalWorkspace';
import { useTechnicalStore } from '../../../model/technicalStore';
import type { ChartPattern } from '../../../model/patterns/types';

vi.mock('../../KLineChartWrapper', () => ({
  KLineChartWrapper: () => <div data-testid="kline-chart-wrapper" />,
}));

vi.mock('../../DrawingToolbar', () => ({
  DrawingToolbar: () => <div data-testid="drawing-toolbar" />,
}));

vi.mock('../../ForecastControls', () => ({
  ForecastControls: () => <div data-testid="forecast-controls" />,
}));

vi.mock('@features/technical/api/useTechnicalQueries', () => ({
  useForecastQuery: vi.fn(() => ({ data: null, isLoading: false })),
  useCandleEdgeQuery: vi.fn(() => ({ data: null, isLoading: false })),
  useIndicatorsQuery: vi.fn(() => ({ data: null, isLoading: false })),
}));

vi.mock('@features/market/api/useBoard', () => ({
  useBoard: vi.fn(() => ({
    data: {
      data: [
        {
          symbol: 'فولاد',
          name: 'فولاد مبارکه',
          sector_name: 'فلزات',
          p_last: 5850,
          percent_last: 2.5,
          q_tot_cap: 900_000_000_000,
          tvol: 150_000_000,
        },
      ],
    },
    isLoading: false,
    isError: false,
  })),
}));

// مسیرِ سورس از cwd ویتست (frontend-v2) خوانده می‌شود؛ در jsdom آدرسِ ماژول http است.
const WORKSPACE_DIR = resolve(process.cwd(), 'src/features/technical/ui/workspace').replace(/\\/g, '/');
const SCANNER_FEED = resolve(process.cwd(), 'src/features/technical/ui/ScannerFeed.tsx');

function sourceFiles(dir: string, into: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = `${dir}/${entry.name}`;
    if (entry.isDirectory()) {
      if (entry.name === '__tests__') continue;
      sourceFiles(full, into);
    } else if (/\.tsx?$/.test(entry.name)) {
      into.push(full);
    }
  }
  return into;
}

const workspaceSources = sourceFiles(WORKSPACE_DIR).map((path) => ({
  path,
  text: readFileSync(path, 'utf8'),
}));

/** نگاشتِ کلاس‌های اندازهٔ قلم به پیکسل؛ همان چیزی که Tailwind/توکن‌ها تولید می‌کنند. */
const FONT_BY_CLASS: Record<string, number> = {
  'text-xs': 12,
  'text-sm': 14,
  'text-base': 16,
  'text-lg': 18,
  'text-xl': 20,
  'text-[8px]': 8,
  'text-[9px]': 9,
  'text-[10px]': 10,
  'text-[11px]': 11,
  'text-[12px]': 12,
  'text-[13px]': 13,
  'text-[14px]': 14,
  'text-[20px]': 20,
  't-8': 8,
  't-85': 8.5,
  't-9': 9,
  't-95': 9.5,
  't-10': 10,
  't-105': 10.5,
  't-11': 11,
  't-115': 11.5,
  't-125': 12.5,
  't-145': 14.5,
};

function classFontSize(element: Element): number | null {
  for (const raw of element.classList) {
    // واریانت‌ها (مثل sm:text-xs) همان اندازهٔ پایه را می‌دهند.
    const token = raw.slice(raw.lastIndexOf(':') + 1);
    const known = FONT_BY_CLASS[token];
    if (known != null) return known;
    const arbitrary = token.match(/^text-\[(\d+(?:\.\d+)?)px\]$/);
    if (arbitrary) return Number(arbitrary[1]);
  }
  return null;
}

function effectiveFontSize(element: Element): number {
  let node: Element | null = element;
  while (node) {
    const size = classFontSize(node);
    if (size != null) return size;
    node = node.parentElement;
  }
  return 16; // پیش‌فرضِ مرورگر
}

function hasOwnText(element: Element): boolean {
  return Array.from(element.childNodes).some(
    (node) => node.nodeType === Node.TEXT_NODE && (node.textContent ?? '').trim().length > 0
  );
}

/** زیردرخت‌های hidden (فید بسته یا پنلِ غیرفعال) از سرشماری کنار می‌روند. */
function isHidden(element: Element): boolean {
  return element.closest('[hidden], .hidden') != null;
}

function textOffenders(roots: Element[], label: string): string[] {
  const offenders: string[] = [];
  for (const root of roots) {
    for (const element of [root, ...Array.from(root.querySelectorAll('*'))]) {
      if (isHidden(element) || !hasOwnText(element)) continue;
      const size = effectiveFontSize(element);
      if (size < 12) {
        const cls = typeof (element as HTMLElement).className === 'string' ? (element as HTMLElement).className : '';
        offenders.push(
          `${label} :: <${element.tagName.toLowerCase()}> ${size}px :: "${(element.textContent ?? '').trim().slice(0, 48)}" :: ${cls}`
        );
      }
    }
  }
  return offenders;
}

const formingPattern = (): ChartPattern => ({
  id: 'visual-flag',
  kind: 'FLAG_BULL',
  direction: 'bullish',
  family: 'continuation',
  tier: 2,
  anchor: { index: 40, price: 105, timestamp: 40 * 60_000 },
  points: [],
  upper: { from: { index: 30, price: 106, timestamp: 30 * 60_000 }, to: { index: 40, price: 106, timestamp: 40 * 60_000 } },
  lower: { from: { index: 30, price: 104, timestamp: 30 * 60_000 }, to: { index: 40, price: 104, timestamp: 40 * 60_000 } },
  target: 112,
  stopLoss: 98,
  quality: 60,
  status: 'forming',
});

function renderShell() {
  return render(<TechnicalWorkspace symbol="فولاد" />);
}

function openFeed() {
  fireEvent.click(screen.getByTestId('activity-section-scanner'));
}

function chromeRoots(): Element[] {
  return [
    screen.getByTestId('workspace-topbar'),
    screen.getByTestId('workspace-activity'),
    screen.getByTestId('workspace-rail'),
    screen.getByTestId('workspace-feed'),
  ];
}

beforeEach(() => {
  useTechnicalStore.getState().reset();
  useTechnicalStore.getState().setDetectedPatterns([formingPattern()]);
});

afterEach(cleanup);

describe('workspace visual contract · 12px floor', () => {
  it('keeps every chrome/panel text node at 12px or larger on all four feed tabs', () => {
    renderShell();
    openFeed();

    const offenders: string[] = [];
    for (const tab of ['events', 'top50', 'indicators', 'edge'] as const) {
      fireEvent.click(screen.getByTestId(`feed-tab-${tab}`));
      offenders.push(...textOffenders(chromeRoots(), tab));
    }

    expect(offenders, `متنِ زیر ۱۲px در کروم/پنل‌ها:\n${offenders.join('\n')}`).toEqual([]);
  });

  it('keeps the portal chrome at 12px or larger', () => {
    renderShell();
    openFeed();
    fireEvent.click(screen.getByTestId('portal-modal-btn'));

    const portal = screen.getByTestId('portal-modal-backdrop');
    expect(textOffenders([portal], 'portal')).toEqual([]);
  });
});

describe('workspace visual contract · unslop sources', () => {
  it('has no font-bold or font-extrabold in ui/workspace sources', () => {
    for (const file of workspaceSources) {
      for (const weight of ['font-bold', 'font-extrabold']) {
        expect(file.text.includes(weight), `${file.path} :: ${weight}`).toBe(false);
      }
    }
  });

  it('uses only the 4px grid (no half-step spacing utilities) in chrome and ScannerFeed', () => {
    const banned = [
      'gap-0.5', 'gap-1.5', 'gap-2.5',
      'p-0.5', 'p-1.5', 'p-2.5',
      'px-0.5', 'px-1.5', 'px-2.5',
      'py-0.5', 'py-1.5', 'py-2.5',
      'm-0.5', 'm-1.5', 'mt-0.5', 'mb-0.5', 'pb-0.5', 'pt-0.5',
    ];
    const files = [
      ...workspaceSources,
      { path: SCANNER_FEED, text: readFileSync(SCANNER_FEED, 'utf8') },
    ];
    for (const file of files) {
      for (const token of banned) {
        expect(file.text.includes(token), `${file.path} :: ${token}`).toBe(false);
      }
    }
  });

  it('unifies the topbar control heights on one 36px rhythm', () => {
    renderShell();

    for (const id of ['workspace-symbol-form', 'workspace-timeframe', 'workspace-adjustment', 'chart-type-selector']) {
      const control = screen.getByTestId(id);
      expect(control.className, id).toContain('h-9');
      expect(control.className, id).not.toContain('h-10');
    }

    // کنترل‌های درونی یک پله ۲۸px داخل قاب ۳۶px می‌نشینند.
    for (const button of document.querySelectorAll<HTMLElement>('[data-testid^="workspace-timeframe-"]')) {
      expect(button.className).toContain('h-7');
    }
  });
});

describe('workspace visual contract · focus and aria', () => {
  it('gives every activity button and feed tab a focus-visible style', () => {
    renderShell();
    openFeed();

    const activity = document.querySelectorAll<HTMLElement>('[data-testid^="activity-section-"]');
    expect(activity.length).toBe(4);
    for (const button of activity) expect(button.className).toMatch(/focus-visible:/);

    const tabs = document.querySelectorAll<HTMLElement>('[data-testid^="feed-tab-"]');
    expect(tabs.length).toBe(4);
    for (const tab of tabs) expect(tab.className).toMatch(/focus-visible:/);

    // کارت رویداد ریل هم حلقهٔ فوکوس دارد.
    const railCard = screen.getByTestId('pattern-card');
    expect(railCard.className).toMatch(/focus-visible:/);
  });

  it('marks exactly one activity section with aria-current at a time', () => {
    renderShell();

    const current = () =>
      Array.from(document.querySelectorAll<HTMLElement>('[data-testid^="activity-section-"][aria-current="true"]'));

    expect(current().map((node) => node.dataset.testid)).toEqual(['activity-section-chart']);

    fireEvent.click(screen.getByTestId('activity-section-scanner'));
    expect(current().map((node) => node.dataset.testid)).toEqual(['activity-section-scanner']);

    fireEvent.click(screen.getByTestId('activity-section-settings'));
    expect(current().map((node) => node.dataset.testid)).toEqual(['activity-section-settings']);
  });
});

describe('workspace visual contract · keyboard', () => {
  it('keeps the activity bar, rail card and feed tabs in the Tab order', () => {
    renderShell();
    openFeed();

    const tabbables = Array.from(
      document.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]')
    ).filter(
      (element) =>
        element.tabIndex >= 0 &&
        !element.hasAttribute('disabled') &&
        !element.closest('[hidden]') &&
        !element.closest('.hidden')
    );

    const position = (element: Element) => tabbables.indexOf(element as HTMLElement);
    const activity = tabbables.filter((element) => element.closest('[data-testid="workspace-activity"]'));
    const feedTabs = tabbables.filter((element) => (element.dataset.testid ?? '').startsWith('feed-tab-'));
    const railCard = screen.getByTestId('pattern-card');

    expect(activity.length).toBe(4);
    expect(feedTabs.length).toBe(4);
    expect(position(railCard)).toBeGreaterThanOrEqual(0);
    expect(railCard.tabIndex).toBe(0);

    // ترتیبِ DOM: نوار فعالیت ← کارت ریل ← تب‌های فید؛ هیچ tabindex مثبتی ترتیب را نمی‌شکند.
    expect(Math.max(...activity.map(position))).toBeLessThan(position(railCard));
    expect(position(railCard)).toBeLessThan(Math.min(...feedTabs.map(position)));
    expect(tabbables.every((element) => element.tabIndex <= 0)).toBe(true);
  });
});
