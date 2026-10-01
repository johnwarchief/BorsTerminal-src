// __tests__/drawing-toolbar-v1066.spec.tsx — هیچ چیپِ ترسیمی نباید بی‌نتیجه بماند
// klinecharts نامِ اورلیِ ثبت‌نشده را بی‌صدا نادیده می‌گیرد: کلیک می‌کنی، چیزی
// رسم نمی‌شود، و کاربر می‌ماند با یک دکمهٔ مرده. دو چیپ («دایره»، «سه‌موجه») و
// دو نگاشتِ غلط («خط افقی» → straightLine کج، «خط اطلاعاتی» → پاره‌خط) همین
// بودند. این تست هر چیپِ نوارِ ترسیم را می‌کشد و مقصدش را با فهرستِ واقعیِ
// اورلی‌هایِ ثبت‌شده (موتور + بستهٔ TV) می‌سنجد.
import { render, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import * as klinecharts from 'klinecharts';
import { DrawingToolbar } from '@features/technical/nahayatnegar/components/DrawingToolbar';
import { TV_TOOL_NAMES } from '@features/technical/lib/tvToolList';

/** چیپ‌های نشانگر/پاک‌کن اورلی نمی‌سازند؛ هندلرِ چارت آن‌ها را خودش می‌بندد */
const CURSOR_TYPES = new Set(['crosshair', 'eraser']);

const registered = new Set<string>([
  ...((klinecharts as unknown as { getSupportedOverlays?: () => string[] }).getSupportedOverlays?.() ?? []),
  ...TV_TOOL_NAMES,
]);

function everyChip(): { name: string; overlayType: string }[] {
  const picked: { name: string; overlayType: string }[] = [];
  const onSelectTool = vi.fn((id: string, overlayType: string) => picked.push({ name: id, overlayType }));
  const noop = () => undefined;
  const { container } = render(
    <DrawingToolbar
      activeToolId="crosshair"
      onSelectTool={onSelectTool}
      onClearDrawings={noop}
      isMagnetActive={false}
      onToggleMagnet={noop}
      isLocked={false}
      onToggleLock={noop}
      isHideActive={false}
      onToggleHide={noop}
    />,
  );
  // هر فلای‌اوت را باز کن و تک‌تک زیرابزارها را بزن. انتخابِ یک آیتم فلای‌اوت را
  // می‌بندد، پس پیش از هر کلیک باید دوباره باز شود — وگرنه هر اسلات فقط یک چیپ
  // می‌فرستد و باقیِ فهرست، مرده هم باشد، هرگز آزمایش نمی‌شود.
  const arrows = () => container.querySelectorAll<HTMLElement>('.tv-slot-arrow');
  const flyItems = () => container.querySelectorAll<HTMLElement>('.tv-flyout-item');
  for (let s = 0; s < arrows().length; s++) {
    fireEvent.click(arrows()[s]);
    const n = flyItems().length;
    fireEvent.click(arrows()[s]);
    for (let j = 0; j < n; j++) {
      fireEvent.click(arrows()[s]);
      fireEvent.click(flyItems()[j]);
    }
  }
  return picked;
}

describe('نگاشتِ چیپ‌های نوارِ ترسیم', () => {
  it('هر چیپ به اورلیِ ثبت‌شدۀ موتور می‌رود (بی‌کلیکِ بی‌نتیجه)', () => {
    const chips = everyChip();
    expect(chips.length).toBeGreaterThan(15);
    const dead = chips.filter((c) => !CURSOR_TYPES.has(c.overlayType) && !registered.has(c.overlayType));
    expect(dead.map((d) => `${d.name}→${d.overlayType}`)).toEqual([]);
  });

  it('خط افقی واقعاً افقی است و خط اطلاعاتی خطِ قیمت، نه پاره‌خطِ کج', () => {
    const chips = everyChip();
    expect(chips.find((c) => c.name === 'horizontalLine')?.overlayType).toBe('horizontalStraightLine');
    expect(chips.find((c) => c.name === 'infoLine')?.overlayType).toBe('priceLine');
  });
});
