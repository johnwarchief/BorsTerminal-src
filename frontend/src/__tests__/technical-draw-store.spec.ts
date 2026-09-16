// تست فاز ۳ (T-23): ماندگاری ترسیم‌ها + Undo/Redo + اسنپ مگنت
import { beforeEach, describe, expect, it } from 'vitest';
import {
  canRedo,
  canUndo,
  clearSymbolDrawings,
  commit,
  drawKey,
  initHistory,
  loadDrawings,
  redo,
  saveDrawings,
  snapToOhlc,
  undo,
  type StoredOverlay,
} from '@features/technical/lib/drawStore';

const OV: StoredOverlay = { name: 'ftsFib', points: [{ timestamp: 1000, value: 10 }] };

describe('ماندگاری ترسیم‌ها (LocalStorage)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('کلید شامل نماد و تایم‌فریم است', () => {
    expect(drawKey('فولاد', 'day')).toBe('fts-draw:فولاد:day');
    expect(drawKey('', 'week')).toBe('fts-draw:__market__:week');
  });

  it('ذخیره/بازیابی برای هر نماد جداگانه', () => {
    saveDrawings('فولاد', 'day', [OV]);
    saveDrawings('خساپا', 'day', [{ name: 'straightLine' }]);
    expect(loadDrawings('فولاد', 'day')).toHaveLength(1);
    expect(loadDrawings('فولاد', 'day')[0].name).toBe('ftsFib');
    expect(loadDrawings('خساپا', 'day')[0].name).toBe('straightLine');
    expect(loadDrawings('فولاد', 'week')).toEqual([]);
  });

  it('آرایهٔ خالی ⇒ حذف کلید (بازیابی خالی)', () => {
    saveDrawings('فولاد', 'day', [OV]);
    saveDrawings('فولاد', 'day', []);
    expect(loadDrawings('فولاد', 'day')).toEqual([]);
    expect(localStorage.getItem(drawKey('فولاد', 'day'))).toBeNull();
  });

  it('دادهٔ خراب ⇒ آرایهٔ خالی (بدون خطا)', () => {
    localStorage.setItem(drawKey('فولاد', 'day'), '{not json');
    expect(loadDrawings('فولاد', 'day')).toEqual([]);
    localStorage.setItem(drawKey('فولاد', 'day'), JSON.stringify([{ points: [] }, OV]));
    expect(loadDrawings('فولاد', 'day')).toHaveLength(1);
  });

  it('پاک‌کردن ترسیم‌های یک نماد در همهٔ تایم‌فریم‌ها', () => {
    saveDrawings('فولاد', 'day', [OV]);
    saveDrawings('فولاد', 'week', [OV]);
    saveDrawings('خساپا', 'day', [OV]);
    expect(clearSymbolDrawings('فولاد')).toBe(2);
    expect(loadDrawings('فولاد', 'day')).toEqual([]);
    expect(loadDrawings('فولاد', 'week')).toEqual([]);
    expect(loadDrawings('خساپا', 'day')).toHaveLength(1);
  });
});

describe('Undo/Redo', () => {
  it('زنجیرهٔ سادهٔ undo/redo', () => {
    let h = initHistory<string[]>([]);
    h = commit(h, ['a']);
    h = commit(h, ['a', 'b']);
    expect(canUndo(h)).toBe(true);
    expect(canRedo(h)).toBe(false);
    h = undo(h);
    expect(h.present).toEqual(['a']);
    expect(canRedo(h)).toBe(true);
    h = redo(h);
    expect(h.present).toEqual(['a', 'b']);
  });

  it('undo در ابتدا/redo در انتها بی‌اثر است', () => {
    const h = initHistory<string[]>([]);
    expect(undo(h)).toBe(h);
    expect(redo(h)).toBe(h);
  });

  it('ثبت جدید، آیندهٔ redo را پاک می‌کند', () => {
    let h = initHistory<string[]>([]);
    h = commit(h, ['a']);
    h = commit(h, ['a', 'b']);
    h = undo(h);
    h = commit(h, ['a', 'c']);
    expect(canRedo(h)).toBe(false);
    expect(h.present).toEqual(['a', 'c']);
  });
});

describe('اسنپ مگنت به OHLC', () => {
  const candle = { open: 100, high: 110, low: 90, close: 105 };

  it('نزدیک سقف ⇒ قفل روی high', () => {
    const r = snapToOhlc(109.8, candle, 0.4);
    expect(r.snapped).toBe(true);
    expect(r.target).toBe('high');
    expect(r.price).toBe(110);
  });

  it('دور از OHLC ⇒ بدون تغییر', () => {
    const r = snapToOhlc(100.6, candle, 0.1);
    expect(r.snapped).toBe(false);
    expect(r.price).toBe(100.6);
  });

  it('کندل نامعتبر/قیمت نامعتبر ⇒ بدون تغییر', () => {
    expect(snapToOhlc(10, null).snapped).toBe(false);
    expect(snapToOhlc(Number.NaN, candle).snapped).toBe(false);
    expect(snapToOhlc(0, candle).snapped).toBe(false);
  });
});
