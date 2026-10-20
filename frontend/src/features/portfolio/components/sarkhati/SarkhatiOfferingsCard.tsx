// چند عرضهٔ اولیه: بودجهٔ مستقل، رزرو اتمیک، Preflight و زمان پیشنهادی.
// هیچ سفارش/ارسال زنده‌ای در این کارت وجود ندارد؛ اعداد از ورودیِ مالک و
// پاسخِ سرویس می‌آیند و مقدار نمونه/پیش‌فرض برای قیمت یا تعداد ساخته نمی‌شود.
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toFaDigits } from '@shared/lib/fmt';
import { offeringsApi, useOfferings, type OfferingView }
  from '../../lib/orderClient';
import { Chip, GhostBtn, Line, Note, Section, Table, Td, Tr } from './parts';

const INPUT = 'min-w-0 rounded-lg border border-border-c bg-bg-secondary px-2 py-1 '
  + 'text-xs text-text-primary outline-none focus:border-border-accent';
const METHOD_LABEL: Record<string, string> = {
  BOOK_BUILDING: 'ثبت سفارش / book building',
  TWO_STAGE: 'دومرحله‌ای',
  AUCTION: 'حراج',
  FIRST_LISTING_QUEUE: 'صفِ عرضهٔ اولیه',
  UNKNOWN: 'نامعلوم',
};
const RESULT_LABEL: Record<string, string> = {
  RESERVED: 'رزرو شد', COMMITTED: 'قطعی', RELEASED: 'آزاد',
  UNKNOWN_HOLD: 'نگه‌داشتِ UNKNOWN', SKIPPED_BUDGET: 'رد به‌خاطر بودجه',
  BLOCKED: 'مسدود',
};
const clock = (ms?: number | null) =>
  ms ? new Date(ms).toLocaleString('fa-IR', { hour12: false }) : '—';

type Dict = Record<string, unknown>;
const asDict = (v: unknown): Dict => (v && typeof v === 'object' ? v as Dict : {});
const str = (v: unknown) => (v == null ? '' : String(v));
const numOrNull = (v: unknown) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

export function SarkhatiOfferingsCard() {
  const q = useOfferings();
  const qc = useQueryClient();
  const rows: OfferingView[] = (q.data?.offerings ?? []) as OfferingView[];
  const capital = q.data?.capital ?? {};
  const reservations = q.data?.reservations ?? [];
  const [cap, setCap] = useState('');
  const [reserve, setReserve] = useState('');
  const [per, setPer] = useState('');
  const [sel, setSel] = useState('');
  const [price, setPrice] = useState('');
  const [qty, setQty] = useState('');
  const [intent, setIntent] = useState('');
  const [adapter, setAdapter] = useState('direct_api');
  const [pf, setPf] = useState<Dict | null>(null);
  const [plan, setPlan] = useState<Dict | null>(null);
  const [timing, setTiming] = useState<Dict | null>(null);
  const [busy, setBusy] = useState('');
  const [answer, setAnswer] = useState('');
  const [tone, setTone] = useState<'ok' | 'warn' | 'bad' | 'idle'>('idle');
  const [form, setForm] = useState({
    symbol: '', isin: '', method: 'UNKNOWN', start: '', end: '',
    price_min: '', price_max: '', min_qty: '', max_qty: '', quota: '',
    fee_rate: '', source: '', source_url: '', verified: false,
  });

  const refresh = () => { void qc.invalidateQueries({ queryKey: ['execution-offerings'] }); };
  const fail = (e: unknown) => {
    setTone('bad'); setAnswer(e instanceof Error ? e.message : String(e));
  };
  const chosen = rows.find((r) => r.id === sel);

  const saveBudget = async () => {
    setBusy('budget'); setAnswer('');
    try {
      const res = await offeringsApi.setBudget({
        total_cap: Number(cap), cash_reserve: Number(reserve || 0),
        max_per_offering: Number(per), priorities: {},
      });
      if (res.status === 'success') {
        setTone('ok'); setAnswer('سقف/ذخیره/سقف هر عرضه ذخیره شد');
        refresh();
      } else { setTone('bad'); setAnswer(str(res.detail ?? res.code ?? 'ذخیره نشد')); }
    } catch (e) { fail(e); } finally { setBusy(''); }
  };

  const addOffering = async () => {
    setBusy('add'); setAnswer('');
    try {
      const now = Date.now();
      const res = await offeringsApi.create({
        symbol: form.symbol.trim(), isin: form.isin.trim(), method: form.method,
        start_local: form.start, end_local: form.end,
        price_min: numOrNull(form.price_min), price_max: numOrNull(form.price_max),
        min_qty: numOrNull(form.min_qty), max_qty: numOrNull(form.max_qty),
        per_code_quota: numOrNull(form.quota), fee_rate: numOrNull(form.fee_rate),
        price_source: form.source, fee_source: form.source,
        source: form.source, source_url: form.source_url,
        verified_at_ms: form.verified ? now : null,
        data_as_of_ms: form.verified ? now : null,
      });
      if (res.status === 'success') {
        setTone('ok'); setAnswer('عرضه ثبت شد؛ وضعیت تأیید از پاسخ سرویس خوانده می‌شود');
        refresh();
      } else { setTone('bad'); setAnswer(str(res.detail ?? res.code ?? 'ثبت نشد')); }
    } catch (e) { fail(e); } finally { setBusy(''); }
  };

  const runPreflight = async () => {
    if (!chosen) { setTone('warn'); setAnswer('اول یک عرضه انتخاب کنید'); return; }
    setBusy('preflight'); setAnswer('');
    try {
      const res = await offeringsApi.preflight(chosen.id, {
        price: Number(price), quantity: Number(qty), max_age_s: 3600,
      });
      const rep = asDict(res.preflight);
      setPf(rep);
      if (res.status === 'success' && rep.ok === true) {
        setTone('ok'); setAnswer('Preflight این عرضه سبز است');
      } else { setTone('bad'); setAnswer('Preflight مسدود است؛ جزئیات را ببینید'); }
    } catch (e) { fail(e); } finally { setBusy(''); }
  };

  const runPlan = async () => {
    if (!chosen) { setTone('warn'); setAnswer('اول یک عرضه انتخاب کنید'); return; }
    setBusy('plan'); setAnswer('');
    try {
      const eid = intent.trim() || `ui-${Date.now()}`;
      const res = await offeringsApi.plan({
        plans: [{ offering_id: chosen.id, intent_id: eid,
          price: Number(price), quantity: Number(qty) }],
        max_age_s: 3600,
      });
      setPlan(res);
      const decisions = (res.decisions ?? []) as Dict[];
      const state = str((decisions[0] ?? {}).state);
      if (res.status === 'success' && state === 'RESERVED') {
        setTone('ok'); setAnswer('بودجه به‌صورت اتمیک رزرو شد (فقط رزرو، بدون ارسال)');
      } else {
        setTone('bad');
        setAnswer(`رزرو نشد: ${str((decisions[0] ?? {}).reason) || state}`);
      }
      refresh();
    } catch (e) { fail(e); } finally { setBusy(''); }
  };

  const runTiming = async () => {
    if (!chosen) { setTone('warn'); setAnswer('اول یک عرضه انتخاب کنید'); return; }
    setBusy('timing'); setAnswer('');
    try {
      const target = Number(chosen.start_ms ?? Date.now() + 3600_000);
      const res = await offeringsApi.timing(adapter, chosen.method, target);
      setTiming(res);
      const st = asDict(res.stats);
      setTone(st.confidence === 'INSUFFICIENT' ? 'warn' : 'ok');
      setAnswer(`نمونه‌ها: ${str(st.n ?? 0)} · اطمینان: ${str(st.confidence ?? '—')}`
        + ' · RTT است، نه زمان پذیرش');
    } catch (e) { fail(e); } finally { setBusy(''); }
  };

  const checks = Object.entries(asDict(pf?.checks));

  return (
    <Section title="عرضه‌های اولیه و بودجهٔ مستقل"
      sub="رزرو اتمیک؛ هیچ ارسال زنده‌ای این‌جا نیست"
      testId="sarkhati-offerings"
      right={<>
        <Chip tone={q.isError ? 'bad' : 'idle'}>
          {toFaDigits(String(rows.length))} عرضه
        </Chip>
        <Chip tone="warn">
          رزرو: {toFaDigits(String(Math.round(Number(q.data?.reserved_total ?? 0))))} ریال
        </Chip>
        <Chip tone="idle">live: خاموش</Chip>
      </>}>
      <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4">
        <label className="flex flex-col gap-0.5 text-3xs text-text-muted">سقف کل (ریال)
          <input className={INPUT} value={cap} onChange={(e) => setCap(e.target.value)}
            data-testid="offer-cap" inputMode="decimal" />
        </label>
        <label className="flex flex-col gap-0.5 text-3xs text-text-muted">ذخیره نقدی
          <input className={INPUT} value={reserve} onChange={(e) => setReserve(e.target.value)}
            data-testid="offer-reserve" inputMode="decimal" />
        </label>
        <label className="flex flex-col gap-0.5 text-3xs text-text-muted">سقف هر عرضه
          <input className={INPUT} value={per} onChange={(e) => setPer(e.target.value)}
            data-testid="offer-per" inputMode="decimal" />
        </label>
        <div className="flex items-end">
          <GhostBtn testId="offer-budget-save" disabled={busy !== ''}
            onClick={() => void saveBudget()}>ذخیرهٔ بودجه</GhostBtn>
        </div>
      </div>
      <Line kind="muted" testId="offer-budget-current">
        سقف فعلی: {capital.total_cap != null ? toFaDigits(String(capital.total_cap)) : '—'}
        {' · '}ذخیره: {capital.cash_reserve != null ? toFaDigits(String(capital.cash_reserve)) : '—'}
        {' · '}سقف هر عرضه: {capital.max_per_offering != null ? toFaDigits(String(capital.max_per_offering)) : '—'}
        {' · '}نسخه: {toFaDigits(String(capital.version ?? 0))}
      </Line>

      {rows.length === 0 ? (
        <Line testId="offer-empty">هیچ عرضه‌ای ثبت نشده است.</Line>
      ) : (
        <Table testId="offer-rows" minWidth={760}
          head={['نماد', 'روش', 'پنجره', 'قیمت', 'تعداد/سهمیه', 'وضعیت', 'منبع']}>
          {rows.map((r) => (
            <Tr key={r.id} testId={`offer-row-${r.id}`}>
              <Td strong>{r.symbol}<span className="text-text-muted"> · {r.isin}</span></Td>
              <Td>{METHOD_LABEL[r.method] ?? r.method}</Td>
              <Td num>{clock(r.start_ms)} — {clock(r.end_ms)}</Td>
              <Td num>{r.price_min ?? '—'}..{r.price_max ?? '—'}</Td>
              <Td num>{r.min_qty ?? '—'}..{r.max_qty ?? '—'} / {r.per_code_quota ?? '—'}</Td>
              <Td><Chip tone={r.status === 'VERIFIED' ? 'ok' : 'warn'}>{r.status}</Chip></Td>
              <Td>{r.source || '—'}</Td>
            </Tr>
          ))}
        </Table>
      )}

      <div className="mt-1.5 grid grid-cols-2 gap-1.5 sm:grid-cols-4">
        <label className="col-span-2 flex flex-col gap-0.5 text-3xs text-text-muted">عرضه
          <select className={INPUT} value={sel} onChange={(e) => setSel(e.target.value)}
            data-testid="offer-select">
            <option value="">—</option>
            {rows.map((r) => <option key={r.id} value={r.id}>{r.symbol}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-0.5 text-3xs text-text-muted">قیمت
          <input className={INPUT} value={price} onChange={(e) => setPrice(e.target.value)}
            data-testid="offer-price" inputMode="decimal" />
        </label>
        <label className="flex flex-col gap-0.5 text-3xs text-text-muted">تعداد
          <input className={INPUT} value={qty} onChange={(e) => setQty(e.target.value)}
            data-testid="offer-qty" inputMode="numeric" />
        </label>
        <label className="col-span-2 flex flex-col gap-0.5 text-3xs text-text-muted">شناسهٔ اجرا (intent)
          <input className={INPUT} value={intent} onChange={(e) => setIntent(e.target.value)}
            data-testid="offer-intent" placeholder="اختیاری؛ یکتا" />
        </label>
        <label className="flex flex-col gap-0.5 text-3xs text-text-muted">روشِ زمان‌سنجی
          <select className={INPUT} value={adapter} onChange={(e) => setAdapter(e.target.value)}>
            {['direct_api', 'playwright_dom', 'javascript', 'keyboard', 'autoclicker']
              .map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </label>
        <div className="flex flex-wrap items-end gap-1">
          <GhostBtn testId="offer-preflight" disabled={busy !== ''}
            onClick={() => void runPreflight()}>Preflight</GhostBtn>
          <GhostBtn testId="offer-plan" disabled={busy !== ''}
            onClick={() => void runPlan()}>رزرو بودجه</GhostBtn>
          <GhostBtn testId="offer-timing" disabled={busy !== ''}
            onClick={() => void runTiming()}>زمان پیشنهادی</GhostBtn>
        </div>
      </div>

      {checks.length ? (
        <Table testId="offer-preflight-checks" minWidth={520} head={['بررسی', 'وضعیت', 'جزئیات']}>
          {checks.map(([name, raw]) => {
            const c = asDict(raw);
            return (
              <Tr key={name} testId={`offer-check-${name}`}>
                <Td strong>{name}</Td>
                <Td><Chip tone={c.state === 'PASS' ? 'ok' : c.state === 'FAIL' ? 'bad' : 'warn'}>
                  {str(c.state)}</Chip></Td>
                <Td>{str(c.detail)}</Td>
              </Tr>
            );
          })}
        </Table>
      ) : null}

      {timing ? (
        <Line kind="muted" testId="offer-timing-result">
          n={toFaDigits(String(asDict(timing.stats).n ?? 0))}
          {' · '}p95={asyncP95(timing)}{' · '}اطمینان={str(asDict(timing.stats).confidence)}
          {' · '}پیشنهاد: {clock(numOrNull(asDict(timing.suggestion).suggested_send_wall_ms))}
          {' · '}{str(asDict(timing.suggestion).timing_note)}
        </Line>
      ) : null}
      {plan ? (
        <Line kind="muted" testId="offer-plan-result">
          {((plan.decisions ?? []) as Dict[]).map((d) => (
            <span key={str(d.offering_id)}>
              {str(d.offering_id)}: {RESULT_LABEL[str(d.state)] ?? str(d.state)}
              {str(d.reason) ? ` (${str(d.reason)})` : ''}{' '}
            </span>
          ))}
          {' · '}رزرو کل: {toFaDigits(String(plan.reserved_total ?? 0))}
        </Line>
      ) : null}
      {reservations.length ? (
        <Table testId="offer-reservations" minWidth={520} head={['عرضه', 'intent', 'مبلغ', 'وضعیت']}>
          {reservations.map((r) => (
            <Tr key={`${str(r.offering_id)}-${str(r.intent_id)}`}>
              <Td strong>{str(r.offering_id)}</Td>
              <Td num>{str(r.intent_id)}</Td>
              <Td num>{toFaDigits(String(r.amount ?? 0))}</Td>
              <Td><Chip tone={str(r.state) === 'UNKNOWN_HOLD' ? 'bad' : 'idle'}>
                {RESULT_LABEL[str(r.state)] ?? str(r.state)}</Chip></Td>
            </Tr>
          ))}
        </Table>
      ) : null}

      <details className="mt-1.5" data-testid="offer-add">
        <summary className="cursor-pointer text-2xs font-bold text-accent-blue">
          افزودن عرضه از منبعِ تأییدشده
        </summary>
        <div className="mt-1 grid grid-cols-2 gap-1.5 sm:grid-cols-4">
          {([['symbol', 'نماد'], ['isin', 'ISIN'], ['start', 'شروع'], ['end', 'پایان'],
             ['price_min', 'کف قیمت'], ['price_max', 'سقف قیمت'], ['min_qty', 'حداقل تعداد'],
             ['max_qty', 'حداکثر تعداد'], ['quota', 'سهمیهٔ هر کد'], ['fee_rate', 'نرخ کارمزد'],
             ['source', 'منبع'], ['source_url', 'نشانی منبع']] as const).map(([key, label]) => (
            <label key={key} className="flex flex-col gap-0.5 text-3xs text-text-muted">{label}
              <input className={INPUT}
                type={key === 'start' || key === 'end' ? 'datetime-local' : 'text'}
                value={form[key]} data-testid={`offer-add-${key}`}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
            </label>
          ))}
          <label className="flex flex-col gap-0.5 text-3xs text-text-muted">روش
            <select className={INPUT} value={form.method} data-testid="offer-add-method"
              onChange={(e) => setForm({ ...form, method: e.target.value })}>
              {Object.entries(METHOD_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-1 text-3xs text-text-muted">
            <input type="checkbox" checked={form.verified}
              data-testid="offer-add-verified"
              onChange={(e) => setForm({ ...form, verified: e.target.checked })} />
            منبع را تأیید می‌کنم
          </label>
          <div className="flex items-end">
            <GhostBtn testId="offer-add-save" disabled={busy !== ''}
              onClick={() => void addOffering()}>ثبت عرضه</GhostBtn>
          </div>
        </div>
        <Note label="قاعدهٔ تأیید" testId="offer-add-rule">
          فقط با منبع و تأییدِ صریح، وضعیت VERIFIED می‌شود؛ بدون آن UNVERIFIED می‌ماند و
          Preflight/رزرو آن مسدود است. قیمت/تعداد/سهمیه را از اطلاعیه یا منبع رسمی وارد کنید.
        </Note>
      </details>

      {answer ? <p data-testid="offer-answer"
        className={`mt-1.5 text-2xs leading-4 ${tone === 'ok' ? 'text-accent-green'
          : tone === 'bad' ? 'text-accent-red' : tone === 'warn'
            ? 'text-accent-yellow' : 'text-text-secondary'}`}>{answer}</p> : null}
      <Note label="محدودیت زمان‌بندی" testId="offer-timing-rule">
        زمان پیشنهادی از تأخیر HTTP همین آداپتور است، نه زمان پذیرش کارگزاری. برای
        book building/دومرحله‌ای مزیت چندمیلی‌ثانیه‌ای اثبات نشده و برای صف،
        جایگاه/اول‌شدن تضمین نمی‌شود. هیچ ارسال زنده‌ای از این کارت انجام نمی‌شود.
      </Note>
    </Section>
  );
}

function asyncP95(timing: Dict) {
  const st = asDict(timing.stats);
  const v = st.p95;
  return v == null ? 'بی‌نمونه' : toFaDigits(String(v));
}
