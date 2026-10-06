import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { Stat } from '@shared/components/ui/stat';
import { Price } from '@shared/components/ui/price';
import { SegmentedControl } from '@shared/components/ui/segmented-control';
import { SearchInput } from '@shared/components/ui/search-input';
import { Counter } from '@shared/components/ui/counter';
import { fmtInt, fmtPct } from '@shared/lib/fmt';

describe('VibafarsiUI Primitives Integration', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('Stat component', () => {
    it('کارت آماری با مقدار، برچسب و واحد رندر می‌شود', () => {
      render(<Stat label="ارزش معاملات" value={fmtInt(1250000)} unit="تومان" />);
      expect(screen.getByText('ارزش معاملات')).toBeInTheDocument();
      expect(screen.getByText(fmtInt(1250000))).toBeInTheDocument();
      expect(screen.getByText('تومان')).toBeInTheDocument();
    });

    it('با تغییر مثبت دلتا، فلش سبز صعودی نشان می‌دهد', () => {
      render(<Stat label="شاخص کل" value="۲٬۱۵۰٬۰۰۰" delta={2.4} />);
      expect(screen.getByText(fmtPct(2.4))).toBeInTheDocument();
      expect(screen.getByText(fmtPct(2.4)).parentElement?.className).toContain('text-accent-green');
    });

    it('با تغییر منفی دلتا، فلش قرمز نزولی نشان می‌دهد', () => {
      render(<Stat label="شاخص کل" value="۲٬۱۵۰٬۰۰۰" delta={-1.5} />);
      expect(screen.getByText(fmtPct(-1.5))).toBeInTheDocument();
      expect(screen.getByText(fmtPct(-1.5)).parentElement?.className).toContain('text-accent-red');
    });
  });

  describe('Price component', () => {
    it('قیمت را با جداکننده هزارگان و واحد تومان رندر می‌کند', () => {
      render(<Price amount={54200} />);
      expect(screen.getByText(fmtInt(54200))).toBeInTheDocument();
      expect(screen.getByText('تومان')).toBeInTheDocument();
    });

    it('در صورت وجود original، قیمت خط‌خورده و درصد تغییر را نمایش می‌دهد', () => {
      render(<Price amount={50000} original={55000} />);
      expect(screen.getByText(fmtInt(50000))).toBeInTheDocument();
      expect(screen.getByText(fmtInt(55000))).toBeInTheDocument();
    });
  });

  describe('SegmentedControl component', () => {
    const options = [
      { value: 'day', label: 'روزانه' },
      { value: 'week', label: 'هفتگی' },
      { value: 'month', label: 'ماهانه' },
    ];

    it('گزینه‌ها را رندر کرده و با کلیک مقدار را عوض می‌کند', () => {
      const onChange = vi.fn();
      render(<SegmentedControl options={options} value="day" onChange={onChange} />);

      expect(screen.getByText('روزانه')).toBeInTheDocument();
      expect(screen.getByText('هفتگی')).toBeInTheDocument();

      fireEvent.click(screen.getByText('هفتگی'));
      expect(onChange).toHaveBeenCalledWith('week');
    });

    it('ناوبری با کلیدهای پیکان کیبورد (ArrowLeft/ArrowRight) در رادیوگروپ', () => {
      const onChange = vi.fn();
      render(<SegmentedControl options={options} defaultValue="day" onChange={onChange} />);

      const radioGroup = screen.getByRole('radiogroup');
      fireEvent.keyDown(radioGroup, { key: 'ArrowLeft' });
      expect(onChange).toHaveBeenCalledWith('week');
    });
  });

  describe('SearchInput component', () => {
    it('ورودی جست‌وجو با debounce متن را جستجو می‌کند', () => {
      const onSearch = vi.fn();
      render(<SearchInput onSearch={onSearch} debounce={200} placeholder="جستجوی نماد..." />);

      const input = screen.getByPlaceholderText('جستجوی نماد...');
      fireEvent.change(input, { target: { value: 'فولاد' } });

      expect(onSearch).not.toHaveBeenCalled();

      act(() => {
        vi.advanceTimersByTime(250);
      });

      expect(onSearch).toHaveBeenCalledWith('فولاد');
    });

    it('با کلید Enter بلافاصله جستجو می‌شود و کلید Escape ورودی را پاک می‌کند', () => {
      const onSearch = vi.fn();
      render(<SearchInput onSearch={onSearch} placeholder="جستجو..." />);

      const input = screen.getByPlaceholderText('جستجو...');
      fireEvent.change(input, { target: { value: 'شپنا' } });
      fireEvent.keyDown(input, { key: 'Enter' });
      expect(onSearch).toHaveBeenCalledWith('شپنا');

      fireEvent.keyDown(input, { key: 'Escape' });
      expect(onSearch).toHaveBeenCalledWith('');
    });
  });

  describe('Counter component', () => {
    it('مقدار هدف را با ارقام فارسی و واحد در دسترس قرار می‌دهد', () => {
      render(<Counter to={2500} unit="معامله" />);
      const text = screen.getByRole('text');
      expect(text).toHaveAttribute('aria-label', `${fmtInt(2500)} معامله`);
      expect(screen.getByText('معامله')).toBeInTheDocument();
    });
  });
});
