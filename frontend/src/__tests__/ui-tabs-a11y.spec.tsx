// تستِ صفحه‌کلید وِ ARIA درِ اصلِ `ui/tabs.tsx` (فاز D)
//
// چرا: فاز صفر ثابت کرد اینِ کامپوننت درِ تولید هیچِ مصرف‌کننده‌ای ندارد. قبلِ آنکه
// «برایِ یکی‌شدنِ اجباری» بهِ سوییچرِ پرتفوی چسبیده شود، باید **بهتر** ازِ نسخهِٔ دستی
// باشد، وگرنه جایگزینیِ بی‌فایده است. نسخهِٔ دستیِ پرتفوی نقشِ `tab` دارد وِ بی‌صفحه‌کلید؛
// اینِ فایل همانِ چیزی را می‌سنجد که افزودنش تفاوت واقعی می‌سازد: roving tabindex،
// پیکان‌ها (درِ RTL جهت‌ها برعکس‌اند، همانِ قاعدۀِ نوارِ تبِ فاز C)، Home/End وِ
// پیوندِ `tab ↔ tabpanel` باِ شناسۀِ یکتا برایِ هرِ گروه.
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@shared/components/ui/tabs';

function Switcher({ onSelect }: { onSelect?: (v: string) => void }) {
  return (
    <Tabs value="a" onValueChange={onSelect}>
      <TabsList aria-label="نمای پرتفوی">
        <TabsTrigger value="a">هدف</TabsTrigger>
        <TabsTrigger value="b">فعلی</TabsTrigger>
        <TabsTrigger value="c" disabled>
          حذفی
        </TabsTrigger>
      </TabsList>
      <TabsContent value="a">صفحۀِ هدف</TabsContent>
      <TabsContent value="b">صفحۀِ فعلی</TabsContent>
    </Tabs>
  );
}

describe('اصلِ تب: کیبورد وِ ARIA', () => {
  it('tabIndex فقط رویِ تبِ فعال صفر است (roving)', () => {
    render(<Switcher />);
    const [a, b, c] = screen.getAllByRole('tab');
    expect(a.tabIndex).toBe(0);
    expect(b.tabIndex).toBe(-1);
    expect(c.tabIndex).toBe(-1);
    expect(a.getAttribute('aria-selected')).toBe('true');
  });

  it('پیوندِ tab ↔ tabpanel باِ شناسه برقرار است وِ فقط صفحۀِ فعال دیده می‌شود', () => {
    render(<Switcher />);
    const a = screen.getByRole('tab', { name: 'هدف' });
    const panel = screen.getByRole('tabpanel');
    expect(a.getAttribute('aria-controls')).toBe(panel.id);
    expect(panel.getAttribute('aria-labelledby')).toBe(a.id);
    expect(screen.queryByText('صفحۀِ فعلی')).toBeNull();
  });

  it('درِ RTL، پیکانِ چپ می‌رود بعدی وِ پیکانِ راست قبلی (همانِ قاعدۀِ نوارِ تب)', () => {
    const onSelect = vi.fn();
    render(<Switcher onSelect={onSelect} />);
    const [a] = screen.getAllByRole('tab');
    a.focus();
    fireEvent.keyDown(a, { key: 'ArrowLeft' });
    expect(onSelect).toHaveBeenLastCalledWith('b');
    fireEvent.keyDown(a, { key: 'ArrowRight' });
    expect(onSelect).toHaveBeenLastCalledWith('a');
  });

  it('Home/End بهِ اول/آخرِ فعال می‌روند وِ تبِ ازکارافتاده رد می‌شود', () => {
    const onSelect = vi.fn();
    render(<Switcher onSelect={onSelect} />);
    const [a] = screen.getAllByRole('tab');
    a.focus();
    fireEvent.keyDown(a, { key: 'End' });
    // «حذفی» disabled است ⇒ End باید رویِ «فعلی» بایستد، نه رویِ خودِ آن
    expect(onSelect).toHaveBeenLastCalledWith('b');
    fireEvent.keyDown(a, { key: 'Home' });
    expect(onSelect).toHaveBeenLastCalledWith('a');
  });

  it('دوِ گروهِ تب رویِ یکِ صفحه، شناسه‌هایِ جدا می‌گیرند', () => {
    render(
      <div>
        <Switcher />
        <Switcher />
      </div>,
    );
    const ids = screen.getAllByRole('tab').map((t) => t.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids[0]).not.toBe(ids[3]);
  });

  it('بی‌onValueChange (گروهِ خودگردان)، تبِ تازه فعال می‌شود وِ صفحۀِ آنِ را می‌دهد', () => {
    render(
      <Tabs defaultValue="a">
        <TabsList aria-label="خودگردان">
          <TabsTrigger value="a">الف</TabsTrigger>
          <TabsTrigger value="b">ب</TabsTrigger>
        </TabsList>
        <TabsContent value="a">ص-الف</TabsContent>
        <TabsContent value="b">ص-ب</TabsContent>
      </Tabs>,
    );
    fireEvent.click(screen.getByRole('tab', { name: 'ب' }));
    expect(screen.getByText('ص-ب')).toBeInTheDocument();
    expect(screen.queryByText('ص-الف')).toBeNull();
  });
});
