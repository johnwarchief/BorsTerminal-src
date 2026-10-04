// features/master/ui/MasterDossier.tsx -- برآیندِ تک‌نامادِ FTS (Round L)
// پنج ثانیه اول: حکم، علت، هفتگی←روزانه←ستاپ، و جایِ نماد در چهار در.
// این کامپوننت هیچ داوری‌ای ندارد: همه‌چیز را `buildDossier` از مدلِ قیف و
// payloadِ `/api/fts` ترجمه کرده است. تنها کارِ اینجا نمایش و ترتیبِ نمایش است.
import { Link } from 'react-router';
import { Badge } from '@shared/components/Badge';
import { toFaDigits, fmtInt, fmtPct } from '@shared/lib/fmt';
import { jalaliText, type DossierVerdict, type MasterDossier } from '../lib/masterDossier';

const TONE: Record<DossierVerdict, 'green' | 'blue' | 'yellow' | 'red'> = {
  confirmed: 'green',
  watch: 'blue',
  wait: 'yellow',
  reject: 'red',
  insufficient: 'yellow',
};

/** اعداد با همان قالبِ خانگیِ برنامه (جداکنندۀ «٬» و ارقامِ فارسی) */
function money(v: number | null): string {
  return v === null || !Number.isFinite(v) ? '—' : fmtInt(v);
}

function pct(v: number | null): string {
  if (v === null || !Number.isFinite(v)) return '—';
  return (v >= 0 ? '+' : '') + fmtPct(v, 2);
}

export function MasterDossierPanel({ dossier }: { dossier: MasterDossier }) {
  const d = dossier;
  return (
    <section
      data-testid="master-dossier"
      aria-label="برآیند FTS نماد"
      className="glass-panel flex flex-col gap-3 p-4"
    >
      {/* ── ۱) هدر ── */}
      <div className="flex flex-wrap items-baseline gap-2">
        <h3 className="text-sm font-black text-text-primary">{d.symbol}</h3>
        {d.name ? <span className="text-2xs text-text-secondary">{d.name}</span> : null}
        {d.sector ? <span className="text-2xs text-text-muted">{d.sector}</span> : null}
        {d.last !== null ? (
          <span className="num ms-auto text-2xs text-text-secondary">
            {money(d.last)} ریال ·{' '}
            <span className={d.percent !== null && d.percent < 0 ? 'text-accent-red' : 'text-accent-green'}>
              {pct(d.percent)}
            </span>
          </span>
        ) : null}
        <Link
          to={`/technical/${encodeURIComponent(d.symbol)}`}
          data-testid="dossier-open-chart"
          className="rounded-lg border border-border-c px-2 py-1 text-2xs font-bold text-accent-blue hover:border-accent-blue/60"
        >
          نمودار تکنیکال
        </Link>
      </div>

      {/* ── ۲) حکم + علت (علت از همان منبعِ حکم) ── */}
      <div className="flex flex-wrap items-center gap-2" data-testid="dossier-verdict">
        <span className="text-2xs uppercase tracking-widest text-text-muted">حکم FTS</span>
        <Badge tone={TONE[d.verdict]}>{d.verdictText}</Badge>
        {d.verdictStage ? (
          <span className="text-2xs text-text-muted">
            تعیین‌کننده: {d.verdictStage === 'tape' ? 'Selection' : d.verdictStage === 'technical' ? 'Technical' : d.verdictStage === 'fundamental' ? 'Fundamental' : 'Master'}
          </span>
        ) : null}
      </div>

      {/* ── ۳) WEEKLY → DAILY → SETUP؛ در وتویِ هفتگی روزانه جایگزین نشان داده نمی‌شود ── */}
      <div
        data-testid="dossier-flow"
        className="flex flex-col gap-1 rounded-xl border border-border-c bg-bg-card/60 px-3 py-2"
      >
        <div className="flex flex-wrap items-center gap-2 text-2xs">
          <span className="w-16 shrink-0 text-text-muted">WEEKLY</span>
          <span className="font-bold text-text-primary">{d.flow.weekly}</span>
        </div>
        {d.flow.gated ? (
          <div className="flex flex-wrap items-center gap-2 text-2xs" data-testid="dossier-flow-gated">
            <span className="w-16 shrink-0 text-text-muted">TECHNICAL</span>
            <Badge tone="red">REJECT</Badge>
            <span className="text-text-secondary">
              علت: {d.flow.reason ?? 'گیتِ هفتگی بسته است'}
            </span>
          </div>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-2 text-2xs">
              <span className="w-16 shrink-0 text-text-muted">DAILY</span>
              <span className="font-bold text-text-primary">{d.flow.daily}</span>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-2xs">
              <span className="w-16 shrink-0 text-text-muted">SETUP</span>
              <span className="font-bold text-text-primary">{d.flow.setup ?? 'ستاپ فعالی ثبت نشده'}</span>
              {d.technical.trigger ? (
                <span className="num text-text-muted">
                  تریگر: {d.technical.trigger.label}
                  {d.technical.trigger.price !== null ? ` · ${money(d.technical.trigger.price)}` : ''}
                  {d.technical.trigger.date ? ` · ${jalaliText(d.technical.trigger.date)}` : ''}
                </span>
              ) : null}
            </div>
          </>
        )}
      </div>

      {/* ── ۴) چهار در، با دلیلِ همان در ── */}
      <ul className="grid gap-1.5 sm:grid-cols-2" data-testid="dossier-stages">
        {d.stages.map((s) => (
          <li
            key={s.key}
            className="flex flex-col gap-0.5 rounded-xl border border-border-c px-3 py-2"
            data-testid={`dossier-stage-${s.key}`}
          >
            <span className="flex items-center gap-2 text-2xs font-bold text-text-primary">
              <span aria-hidden>{s.icon}</span>
              {s.label}
            </span>
            <span className="text-2xs leading-5 text-text-secondary" title={s.why}>
              {s.why || 'بدونِ دلیلِ ثبت‌شده'}
            </span>
          </li>
        ))}
      </ul>

      {/* ── ۵) سطوحِ عملیاتی و منبعِ تحلیل — یک خط، بی‌کارتِ اضافی ── */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-2xs text-text-muted" data-testid="dossier-levels">
        <span className="num">مقاومت: {money(d.levels.resistance)}</span>
        <span className="num">حد ضرر: {money(d.levels.hardStop)}</span>
        <span className="num">MA14: {money(d.levels.ma14)}</span>
        {d.hourglass.active !== null ? (
          <span>
            ساعت شنی: {d.hourglass.active ? 'فعال' : 'غیرفعال'}
            {d.hourglass.rsi5 !== null ? ` · RSI هفتگی ${toFaDigits(d.hourglass.rsi5)}` : ''}
          </span>
        ) : (
          <span>ساعت شنی: سنجیده نشد</span>
        )}
        {d.technical.basis ? <span>مبنای تحلیل: {d.technical.basis}</span> : null}
        {d.inFunnel ? null : <span>نماد در جامعۀ قیف نیست — خطوطِ S/F سنجیده نشده‌اند، نه رد</span>}
      </div>

      {d.technical.engineText && d.verdictText !== d.technical.engineText ? (
        <p className="text-2xs leading-5 text-text-muted" data-testid="dossier-engine-text">
          متنِ موتور: {d.technical.engineText}
        </p>
      ) : null}

      {/* §۸ — جزئیاتِ عملیاتیِ تکنیکال، همه از همان payload؛ هیچ عددی اینجا ساخته
          نمی‌شود و رشته‌ها عینِ متنِ موتورند */}
      <details className="text-2xs" data-testid="dossier-tech-details">
        <summary className="cursor-pointer font-bold text-text-secondary">
          جزئیاتِ تکنیکال (از همان موتور)
        </summary>
        <ul className="mt-1 flex flex-col gap-1 text-text-secondary">
          <li>ماتریسِ روند: {d.technical.matrixDesc ?? '—'}</li>
          <li>
            حکمِ خروج: {d.technical.exitVerdict ?? '—'} · مبنایِ حد ضرر: {d.technical.stopBasis ?? '—'}
          </li>
          <li className="num">
            سقفِ تاریخی: {d.technical.jetAth === null ? '—' : d.technical.jetAth ? 'بله' : 'خیر'}
            {' · '}
            {money(d.levels.ceiling)}
          </li>
          <li>ساعت شنی: {d.hourglass.desc ?? '—'}</li>
          <li>مبنایِ سریِ تحلیل: {d.technical.basis ?? '—'}</li>
        </ul>
      </details>
    </section>
  );
}
