// features/master/ui/MasterFtsDetails.tsx -- جزئیاتِ چهار صفحه زیرِ خلاصه (Round M §۱–۵)
// ترتیبِ هسته: S → T → F، و بعد Strategy/Management (که داورِ چهارم نیست).
// هیچ‌چه اینجا حساب نمی‌شود: سطرها از `Candidate`، `patternBadges` (همان تابعِ
// تبِ تابلو)، `IND_COLUMNS` (همان پنج شاخصِ جزوه) و payloadِ `/api/fts` می‌آیند.
import type { ReactNode } from 'react';
import { Badge } from '@shared/components/Badge';
import { toFaDigits, fmtInt, fmtPct } from '@shared/lib/fmt';
import type { TapeBadge } from '@features/market/lib/tapeBadges';
import { IND_COLUMNS, type Candidate, type StageStatus } from '../lib/ftsFunnel';
import { jalaliText, type MasterDossier } from '../lib/masterDossier';

const MARK: Record<StageStatus, { icon: string; tone: 'green' | 'red' | 'yellow' | 'blue'; word: string }> = {
  pass: { icon: '✅', tone: 'green', word: 'قبول' },
  reject: { icon: '❌', tone: 'red', word: 'رد' },
  pending: { icon: '⏳', tone: 'yellow', word: 'در انتظار' },
  unavailable: { icon: '○', tone: 'blue', word: 'بی‌داده' },
  not_required: { icon: '·', tone: 'blue', word: 'لازم نبود' },
};

const n = (v: number | null | undefined): string =>
  v === null || v === undefined || !Number.isFinite(v) ? '—' : fmtInt(v);

/** رشتهٔ جلالی از تاریخِ میلادیِ payload؛ نبودِ تاریخ ⇒ '—' */
const jal = (iso: string | null | undefined): string => jalaliText(iso);

/** رأیِ موتورِ غربالگری (api/fundamental.py) — ترجمۀ کد، بی‌داوریِ دوم */
const SCREEN_VERDICT_FA: Record<string, string> = {
  STRONG: 'سوپر بنیادی',
  WATCH: 'واچ‌لیست',
  REJECT: 'رد',
  EXCLUDED: 'خارج از صف',
};

function Section({
  id, title, mark, children, open = false,
}: { id: string; title: string; mark?: string; children: ReactNode; open?: boolean }) {
  return (
    <details open={open} className="rounded-xl border border-border-c px-3 py-2" data-testid={id}>
      <summary className="cursor-pointer text-2xs font-black text-text-primary">
        {title}
        {mark ? <span className="ms-2 text-text-muted">{mark}</span> : null}
      </summary>
      <div className="mt-2 flex flex-col gap-1.5 text-2xs leading-5 text-text-secondary">{children}</div>
    </details>
  );
}

export function MasterFtsDetails({
  candidate, dossier, badges, support, srResistance,
}: {
  candidate: Candidate | null;
  dossier: MasterDossier;
  /** بج‌هایِ ستونِ «الگو» — از همان `patternBadges` تبِ تابلو */
  badges: TapeBadge[];
  support: number | null;
  srResistance: number | null;
}) {
  const sc = candidate?.screen ?? null;
  const inds = candidate?.inds ?? [];
  const t = dossier.technical;
  const tapeFilters = badges.filter((b) => b.filter);

  return (
    <div className="flex flex-col gap-2" data-testid="master-fts-details">
      {/* ── S — تابلوخوانی ── */}
      <Section id="details-selection" title="S — تابلوخوانی" mark={MARK[candidate?.status.tape ?? 'unavailable'].icon}>
        <p>{candidate?.why.tape || 'دلیلی برایِ درِ تابلو ثبت نشده'}</p>
        {tapeFilters.length ? (
          <ul className="flex flex-wrap gap-1.5">
            {tapeFilters.map((b) => (
              <li key={b.key} title={b.title}>
                <Badge tone={b.tone === 'red' ? 'red' : 'blue'}>{b.label}</Badge>
              </li>
            ))}
          </ul>
        ) : (
          <li>هیچ‌یک از پنج فیلترِ فایل برایِ همین نماد فعال نیست (نشانهٔ رد، نه کمبودِ داده).</li>
        )}
      </Section>

      {/* ── T — تکنیکال ── */}
      <Section id="details-technical" title="T — تکنیکال" mark={MARK[candidate?.status.technical ?? 'unavailable'].icon}>
        <ul className="flex flex-col gap-1">
          <li>هفتگی: <b>{dossier.flow.weekly}</b> · روزانه: <b>{dossier.flow.gated ? '— (زیرِ وتو)' : dossier.flow.daily}</b></li>
          <li>ستاپِ فعال: <b>{dossier.flow.setup ?? '—'}</b>{t.matrixDesc ? ` · ${t.matrixDesc}` : ''}</li>
          <li className="num">
            نقطه ورود (تریگر): {n(t.trigger?.price ?? null)}
            {' · '}مقاومت: {n(dossier.levels.resistance ?? srResistance)}
            {' · '}حمایت: {n(support)}
          </li>
          <li className="num">
            حد ضرر: {n(dossier.levels.hardStop)}
            {' · '}مبنا: {t.stopBasis ?? '—'}
            {' · '}MA14: {n(dossier.levels.ma14)}
          </li>
          <li>
            شرط ابطال: {t.exitVerdict
              ? t.exitConfirmed
                ? `خروجِ تأییدشده (${t.exitVerdict})`
                : `هنوز خروجِ تأییدشده نیست (${t.exitVerdict})`
              : '—'}
            {t.trigger?.date ? ` · تاریخِ تریگر: ${jal(t.trigger.date)}` : ''}
          </li>
          <li>مبنای سری: {t.basis ?? '—'} · متن موتور: {t.engineText ?? '—'}</li>
        </ul>
      </Section>

      {/* ── F — بنیادی ── */}
      <Section id="details-fundamental" title="F — بنیادی" mark={MARK[candidate?.status.fundamental ?? 'unavailable'].icon}>
        <p>
          رأیِ موتور: <b>{SCREEN_VERDICT_FA[sc?.verdict ?? ''] ?? sc?.verdict ?? '—'}</b>
          {sc ? ` · نمره: ${toFaDigits(sc.score)} از ۵` : ''}
        </p>
        <p>{candidate?.why.fundamental || 'دلیلِ ثبت‌شده‌ای برایِ بنیادی نیست'}</p>
        {sc?.excluded ? <p>خارج از صف: {sc.exclusion_reasons ?? 'بدونِ علتِ ثبت‌شده'}</p> : null}
        {sc?.applicable === false ? (
          <p>این ابزار در پنج‌شاخصه نمی‌گنجد — نه رد، نه قبول.</p>
        ) : null}
        <ul className="grid gap-1 sm:grid-cols-2">
          {IND_COLUMNS.map((c, i) => {
            const st = inds[i] ?? 'unavailable';
            const na = st === 'pending' || st === 'unavailable';
            const val =
              c.key === 'i2' ? (sc?.eps_last != null ? toFaDigits(sc.eps_last) : null)
                : c.key === 'i3' ? (sc?.gross_margin != null ? fmtPct(sc.gross_margin, 1) : null)
                : c.key === 'i4' ? (sc?.sales_to_mcap != null ? toFaDigits(sc.sales_to_mcap.toFixed(2)) : null)
                : null;
            return (
              <li key={c.key} title={c.full} className="flex items-center gap-2 rounded-lg border border-border-c px-2 py-1">
                <span aria-hidden>{MARK[st].icon}</span>
                <span className="font-bold text-text-primary">{c.label}</span>
                <span className="num text-text-muted">{val ?? (na ? 'داده نیست / بی‌کاربرد' : '✓')}</span>
              </li>
            );
          })}
        </ul>
      </Section>

      {/* ── استراتژی و مدیریت — داورِ چهارم نیست ── */}
      <Section id="details-strategy" title="استراتژی و مدیریت">
        <ul className="flex flex-col gap-1">
          <li>
            ساعت شنی (هفتگی، سازۀ مستقلِ صفحهٔ ۴): {dossier.hourglass.active === null ? 'سنجیده نشد'
              : dossier.hourglass.active ? 'فعال' : 'غیرفعال'}
            {' · '}MA52 هفتگی: {n(dossier.hourglass.ma52)}
            {' · '}RSI5 هفتگی: {dossier.hourglass.rsi5 != null ? toFaDigits(dossier.hourglass.rsi5) : '—'}
          </li>
          <li>{dossier.hourglass.desc ?? '—'}</li>
          {dossier.hourglass.action ? <li>اقدامِ سازۀ ساعت شنی: {dossier.hourglass.action}</li> : null}
          {candidate?.assemblyVeto ? <li>وتوی مجمع: {candidate.assemblyWhy}</li> : null}
        </ul>
      </Section>
    </div>
  );
}
