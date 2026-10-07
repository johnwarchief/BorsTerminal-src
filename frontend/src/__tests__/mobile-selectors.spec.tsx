// گاردِ «انتخابگرِ مرده».
//
// باگی که این تست جلویش را می‌گیرد و هفته‌ها بی‌صدا ماند: mobile.css چهار
// قاعده رویِ aside[data-shell='sidebar'] داشت تا در صفحهٔ کوچک سایدبار را
// به نوارِ پایین تبدیل کند، ولی آن صفت هرگز رویِ کامپوننت نوشته نشده بود.
// قاعده‌ها مرده بودند و رویِ گوشی سایدبار عمودی و کنارِ صفحه می‌ماند.
// همین برایِ اینسپکتور هم بود (CSS دنبالِ aria-label="داور نماد" می‌گشت
// در حالی که متنِ واقعی «بازرسی نماد فولاد» است).
//
// CSS را هیچ تستِ رفتاری اجرا نمی‌کند، پس تنها راهِ گرفتنِ این خطا همین
// است: هر انتخابگرِ ساختاریِ فایل باید در DOMِ واقعی وجود داشته باشد.
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import fs from 'node:fs';
import { Sidebar } from '@app/components/Sidebar';
import { SymbolInspector } from '@widgets/SymbolInspector';
import { useSymbolStore } from '@shared/stores/symbolStore';

const css = fs.readFileSync('src/shared/styles/mobile.css', 'utf8');

/** همهٔ فایل‌هایِ منبعِ فرانت (برایِ جست‌وجویِ شناسه‌ها). */
function listSources(dir = 'src'): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = `${dir}/${e.name}`;
    if (e.isDirectory()) return listSources(full);
    return /\.tsx?$/.test(e.name) ? [full] : [];
  });
}

const wrap = (node: React.ReactNode) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter>{node}</MemoryRouter>
  </QueryClientProvider>
);

/** همهٔ انتخابگرهایی که به صفتِ ساختاری چنگ می‌زنند. */
function structuralSelectors(): string[] {
  return [...css.matchAll(/aside\[[^\]]+\]/g)].map((m) => m[0]);
}

describe('انتخابگرهایِ چیدمانِ موبایل مرده نباشند', () => {
  it('فهرستِ انتخابگرها خالی نیست (اگر خالی شد یعنی CSS عوض شده)', () => {
    expect(structuralSelectors().length).toBeGreaterThan(0);
  });

  it('سایدبار صفتی را دارد که CSS دنبالش می‌گردد', () => {
    const { container } = render(wrap(<Sidebar />));
    expect(container.querySelector("aside[data-shell='sidebar']")).not.toBeNull();
  });

  it('اینسپکتور هم همین‌طور', () => {
    useSymbolStore.setState({ symbol: 'فولاد' });
    const { container } = render(wrap(<SymbolInspector />));
    expect(container.querySelector("aside[data-shell='inspector']")).not.toBeNull();
  });

  it('هیچ data-testidِ اختراعی در mobile.css نمانده', () => {
    // باگِ واقعی: قاعده‌ای رویِ .strategy-canvas-wrap نوشته بودم که فقط در
    // همان فایل وجود داشت و در DOM نبود — مرده. این بررسی هر شناسه‌ای را
    // که CSS به آن چنگ می‌زند در خودِ سورس می‌جوید.
    const ids = [...css.matchAll(/data-testid='([a-z0-9-]+)'/g)].map((m) => m[1]);
    expect(ids.length).toBeGreaterThan(0);
    const all = listSources().map((f) => fs.readFileSync(f, 'utf8')).join('\n');
    const dead = [...new Set(ids)].filter((id) => !all.includes(`"${id}"`) && !all.includes(`'${id}'`));
    expect(dead).toEqual([]);
  });

  it('هیچ انتخابگرِ asideای در CSS نمانده که به aria-label بچسبد', () => {
    // aria-label متنِ نمایشی است و با نامِ نماد عوض می‌شود؛ تکیهٔ چیدمان
    // رویِ آن یعنی قاعده‌ای که روزی بی‌صدا می‌میرد.
    const fragile = structuralSelectors().filter((s) => s.includes('aria-label'));
    expect(fragile).toEqual([]);
  });
});
