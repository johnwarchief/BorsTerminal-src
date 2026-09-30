// قرصِ فعالِ نوارِ کناری — تنها جایی از برنامه که «تک‌فعال» است، پس تنها
// جایی که قرصِ لغزان معنا دارد. چیپ‌هایِ فیلترِ تابلوخوانی چندانتخابی‌اند.
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { Sidebar } from '@app/components/Sidebar';

const paint = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Sidebar />
    </MemoryRouter>,
  );

describe('قرصِ فعالِ نوارِ کناری', () => {
  it('فقط یک قرص وجود دارد — دو تا یعنی layoutId تکراری و پرشِ انیمیشن', () => {
    paint('/market');
    expect(screen.getAllByTestId('sidebar-active-pill')).toHaveLength(1);
  });

  it('قرص داخلِ همان لینکِ فعال است', () => {
    paint('/fundamental');
    const pill = screen.getByTestId('sidebar-active-pill');
    const link = pill.closest('a');
    expect(link?.getAttribute('href')).toBe('/fundamental');
  });

  it('با عوض‌شدنِ مسیر، قرص هم جابه‌جا می‌شود', () => {
    paint('/portfolio');
    expect(screen.getByTestId('sidebar-active-pill').closest('a')?.getAttribute('href'))
      .toBe('/portfolio');
  });
});
