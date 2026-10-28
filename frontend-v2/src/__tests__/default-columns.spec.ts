import { describe, expect, it } from 'vitest';
import { COLUMNS, defaultColumns } from '@features/market/lib/columns';

describe('default columns', () => {
  it('keeps P/E out of the general and fundamental defaults', () => {
    expect(defaultColumns('general')).not.toContain('pe');
    expect(defaultColumns('fundamental')).not.toContain('pe');
  });

  it('still offers P/E from the column menu', () => {
    expect(COLUMNS.pe.available).toBe(true);
  });
});
