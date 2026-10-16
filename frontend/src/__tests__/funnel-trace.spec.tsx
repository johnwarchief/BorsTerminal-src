// __tests__/funnel-trace.spec.tsx — قراردادِ نمایشِ ردپایِ غربالگری
//
// دو چیز که باید پایدار بماند:
//   • هیچ وضعیتی درِ فرانت ساخته نمی‌شود — برچسب از `STATUS_LABEL` می‌آید و
//     نبودِ سطر ⇒ «ردپایی ثبت نشده»، نه «قبول شد».
//   • رقم‌هایِ متنِ فارسی فارسی‌اند (قاعدۀ «رقمِ فارسی درِ متنِ فارسی») — شمارِ
//     ورودی/خروجیِ هر فیلتر دقیقاً همان‌جا است که رقمِ لاتین سرِ کار می‌آید.
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FunnelTraceList } from '@features/master/ui/FunnelTraceList';
import type { TraceStep } from '@features/master/api/useFunnelTrace';

const STEP = (over: Partial<TraceStep> = {}): TraceStep => ({
  stage: 'tape:f_roobi', seq: 1, status: 'reject', reason_code: 'TAPE_F_ROOBI_NO_MATCH',
  human_reason: 'کف روبی صف فروش — نشانه در این نماد نیست',
  input_count: 13, output_count: 1, source: 'tape_flags.py', timestamp: null, ...over,
});

describe('ردپایِ غربالگری', () => {
  it('هر سطرِ پاسخِ سرور یک سطرِ رابط است، با وضعیت و دلیلِ خودش', () => {
    render(<FunnelTraceList steps={[STEP(), STEP({ stage: 'technical', seq: null,
      status: 'pass', reason_code: 'TECH_PASS', human_reason: 'روند هفتگی صعودی',
      input_count: 900, output_count: 640 })]}
      rulesetVersion="555648ebff52" asOf={1791500000} />);
    const steps = screen.getAllByTestId(/^funnel-trace-step-/);
    expect(steps).toHaveLength(2);
    expect(steps[0].textContent).toContain('تابلوخوانی');
    expect(steps[0].textContent).toContain('کف روبی صف فروش');
    expect(steps[1].textContent).toContain('تکنیکال');
  });

  it('شمارِ ورودی/خروجی با رقمِ فارسی نوشته می‌شود', () => {
    render(<FunnelTraceList steps={[STEP()]} rulesetVersion="555648ebff52" />);
    const t = screen.getByTestId('funnel-trace-step-0').textContent ?? '';
    expect(t).toContain('ورودی ۱۳');
    expect(t).toContain('خروجی ۱');
    expect(t).not.toMatch(/\d/);            // هیچ رقمِ لاتینی درِ متنِ فارسی نمی‌ماند
  });

  it('نسخۀ قواعد دیده می‌شود؛ بی‌آن هم خط نمی‌افتد', () => {
    render(<FunnelTraceList steps={[STEP()]} rulesetVersion="555648ebff52" />);
    expect(screen.getByTestId('funnel-trace-meta').textContent).toContain('555648ebff52');
    render(<FunnelTraceList steps={[STEP()]} />);
    expect(screen.getAllByTestId('funnel-trace-meta').pop()?.textContent).toContain('—');
  });

  it('بی‌ردپا ⇒ «ثبت نشده»، نه حکمِ ساختگی', () => {
    render(<FunnelTraceList steps={[]} />);
    expect(screen.getByTestId('funnel-trace-empty').textContent).toContain('ثبت نشده');
  });
});
