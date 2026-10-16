// __tests__/order-line-contract.spec.ts -- خوانشِ schema باِ پاسخِ *واقعیِ* ضبط‌شده
//
// سطح (بندِ ۱.۵ مأموریت): «تستِ backend آزمایشی» -- نه اتصالِ واقعی. فیکسچرِ
// `fixtures/execution-contract.json` را `tools/ui_execution_contract_capture.py`
// ازِ خودِ `api/execution.py` (mock/dry-run) ضبط کرده وِ هرِ سطر `content-type`
// خودش را هم دارد. چرا اینِ فایل هست: اولینِ اجرایِ زندهٔ سنجشِ سرخطی نشان داد
// پاسخِ موفقِ `/dispatch` باِ schemaِ دست‌سازِ رابط نمی‌خواند (`kill_switch` رشته
// است نه شیء، `execution_id` درِ پاسخِ موفق نیست) وِ همانِ خطا درِ UI بهِ «نتیجهٔ
// نامعلوم» ترجمه می‌شد -- یعنی یکِ سفارشِ acceptance‌شده بی‌دلیلِ واقعی. آزمونِ
// امروز همانِ اشتباه را قفل می‌کند: پاسخ‌هایی که سرویس *واقعاً* می‌دهد، نه آنچه
// رابط حدس می‌زند.
//
// هیچ‌جا درِ اینِ فایل رفتارِ مطلوب باِ رفتارِ واقعی اشتباه گرفته نشده: سطرهایی که
// «دروازہ اینِ کار را می‌کند» را ثابت می‌کنند، همانِ چیزی است که امروز درِ
// بک‌اندِ آزمایشی می‌گذرد -- اگرِ روزی عوض شود، اینِ آزمون می‌شکند وِ مستندات
// باِ آن بازبینی می‌شود.
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  DispatchSchema, LimitsSchema, PrepareSchema, PreflightSchema,
} from '@features/execution/api/orderLineApi';
import { ExecutionStatusSchema } from '@features/portfolio/lib/orderClient';

// `import.meta.url` درِ jsdom آدرسِ http می‌دهد؛ پسِ مسیر ازِ ریشۀِ آزمون (frontend) خوانده می‌شود.
const FX = path.join(process.cwd(), 'src', '__tests__', 'fixtures', 'execution-contract.json');
const fx = JSON.parse(readFileSync(FX, 'utf8')) as {
  base: string;
  cases: Record<string, { request: { method: string; path: string; body: unknown };
                           response: { http: number | null; content_type: string | null; body: any } }>;
};

const body = (k: string) => fx.cases[k].response.body;
const http = (k: string) => fx.cases[k].response.http;
const ctype = (k: string) => (fx.cases[k].response.content_type ?? '');

const REGISTERED = Object.keys(fx.cases).filter((k) => k !== 'unregistered_path');

describe('قراردادِ ضبط‌شده درِ بک‌اندِ آزمایشی (mock/dry-run)', () => {
  it('هرِ مسیرِ ثبت‌شدہ application/json می‌دهد؛ ۲۰۰-HTML فقط مالِ مسیرِ ثبت‌نشده است', () => {
    for (const k of REGISTERED) expect(ctype(k).startsWith('application/json')).toBe(true);
    expect(http('unregistered_path')).toBe(200);
    expect(ctype('unregistered_path').startsWith('text/html')).toBe(true);
    // شاهدِ بندِ ۱.۱: بی‌schema، همینِ ۲۰۰ «موفق» خوانده می‌شد
    expect(body('unregistered_path').__non_json__).toContain('<!doctype html>');
  });

  it('پاسخِ /status باِ schema می‌خواند وِ سه‌قفلۀِ بدل درِ آن روشن است', () => {
    const p = ExecutionStatusSchema.safeParse(body('status'));
    expect(p.success).toBe(true);
    expect(body('status').adapter).toBe('mock');
    expect(body('status').dry_run).toBe(true);
    expect(body('status').live_enabled).toBe(false);
    expect(body('status').nothing_will_leave_the_machine).toBe(true);
  });

  it('/session توکنی بیرون نمی‌دهد (token_present:false درِ پاسخِ خودِ سرویس)', () => {
    expect(body('session_get').token_present).toBe(false);
    expect(JSON.stringify(body('session_get'))).not.toMatch(/token["']?\s*:\s*["'][^"']{6,}/);
  });

  it('پاسخِ موفقِ /dispatch باِ schema می‌خواند (kill_switch رشته، بی‌execution_id)', () => {
    const p = DispatchSchema.safeParse(body('dispatch_ok'));
    expect(p.success).toBe(true);
    expect(typeof body('dispatch_ok').kill_switch).toBe('string');
    expect(body('dispatch_ok').record?.status).toBeTruthy();
  });

  it('پیش‌فرودِ واقعیِ نمادِ بی‌ISIN رد می‌شود وِ رابط نگاشت اختراع نمی‌کند', () => {
    expect(PreflightSchema.safeParse(body('preflight_no_isin')).success).toBe(true);
    expect(body('preflight_no_isin').checks.instrument).toBe('FAIL');
    expect(body('preflight_no_isin').reasons.instrument).toMatch(/^NOT_ORDERABLE:/);
  });

  it('بی‌`mock_instrument` صریح، هیچِ broker_instrument ساخته نمی‌شود (§۱-ج)', () => {
    const b = body('preflight_bare_no_mapping');
    expect(PreflightSchema.safeParse(b).success).toBe(true);
    expect(b.instrument.broker_instrument).toBeNull();
    expect(b.checks.instrument).toBe('FAIL');
    expect(b.reasons.instrument).toBe('NOT_ORDERABLE:broker_instrument');
  });

  it('UNKNOWN درِ checks باِ FAIL یکی نیست: نشست/موجودی نامعلوم مسیر را رد نمی‌کند', () => {
    const b = body('preflight_ok');
    expect(b.checks.session).toBe('UNKNOWN');
    expect(b.checks.balance).toBe('UNKNOWN');
    expect(b.unknown).toEqual(expect.arrayContaining(['session', 'balance']));
    expect(b.ok).toBe(true);
  });

  it('رزروِ شناسه: prepare وِ بعد dispatch باِ یکِ شناسه ⇒ DUPLICATE_GUARD (پسِ UI دکمۀِ آماده‌سازی ندارد)', () => {
    expect(PrepareSchema.safeParse(body('prepare_ok')).success).toBe(true);
    expect(body('prepare_ok').sendable).toBe(true);
    expect(DispatchSchema.safeParse(body('prepare_then_dispatch_same_id')).success).toBe(true);
    expect(body('prepare_then_dispatch_same_id').code).toBe('DUPLICATE_GUARD');
    expect(body('prepare_then_dispatch_same_id').checks.duplicate).toBe('FAIL');
  });

  it('دوبارهِ dispatch باِ یکِ شناسه رد می‌شود؛ سطرِ ردِّپا دوتایی نمی‌شود', () => {
    const again = body('dispatch_same_id_again');
    expect(again.status).toBe('error');
    expect(again.code).toBe('DUPLICATE_GUARD');
    const ids = (body('ledger').records ?? []).map((r: { execution_id: string }) => r.execution_id);
    expect(ids.length).toBe(new Set(ids).size);
  });

  it('تأییدِ صریح را درِ حالتِ safe خودِ دروازہ الزام نمی‌کند -- پسِ رابط `confirmed: true` می‌فرستد وِ ادعایِ بک‌اند نمی‌کند', () => {
    expect(body('limits').limits.require_confirmation).toBe(true);
    expect(body('dispatch_without_confirmed_flag').status).toBe('success');
    // اینِ دوِ سطر باِ هم یعنی: گروۀِ UI («تأییدِ صریحِ کاربر») یکِ رأیِ رابط است،
    // نه چیزی که دروازہ امروز برایش خطا می‌دهد. ادعایِ «دروازہ تأیید را الزام می‌کند» درِ
    // مستندات ثبت نشده، دقیقاً بهِ همینِ دلیل.
  });

  it('کلیدِ توقف: halt ⇒ dispatch رد (HALTED) وِ resume ⇒ ARMED', () => {
    expect(body('halt').kill_switch).toBe('HALTED');
    expect(body('dispatch_while_halt').code).toBe('HALTED');
    expect(body('resume').kill_switch).toBe('ARMED');
  });

  it('reconcile باِ شناسۀِ شناخته‌شده record می‌آورد وِ باِ شناسۀِ ناشناخته ۴۰۴ + detail', () => {
    expect(http('reconcile_ok')).toBe(200);
    expect(DispatchSchema.safeParse(body('reconcile_ok')).success).toBe(true);
    expect(http('reconcile_unknown_id')).toBe(404);
    expect(body('reconcile_unknown_id').detail).toMatch(/^INVALID_EXECUTION_ID/);
  });

  it('limits باِ schema می‌خواند وِ سقفِ سفارش ازِ همانِ پاسخ خوانده می‌شود، نه حدسِ رابط', () => {
    expect(LimitsSchema.safeParse(body('limits')).success).toBe(true);
    expect(typeof body('limits').limits.max_orders).toBe('number');
  });
});
