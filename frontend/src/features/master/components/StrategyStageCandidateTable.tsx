// features/master/components/StrategyStageCandidateTable.tsx
// جدول تعاملی کاندیداها و نمادهای هر مرحله از نقشه راه FTS
// نمایش دقیق خروجی مرحله‌به‌مرحله: چه کسانی وارد شدند، چه کسانی حذف شدند و چه کسانی عبور کردند

import React, { useMemo, useState } from 'react';
import { fmtInt, fmtPct, toFaDigits } from '@shared/lib/fmt';
import { matchFa } from '@shared/lib/normalizeFa';
import { SymbolBasketAction } from '@features/portfolio/components/SymbolBasketAction';
import {
  IND_COLUMNS,
  STATUS_LABEL,
  trendLabel,
  type Candidate,
  type FunnelStageKey,
  type StageStatus,
} from '../lib/ftsFunnel';

export interface StrategyStageCandidateTableProps {
  stageKey: FunnelStageKey;
  stageTitle: string;
  stagePage: string;
  stageDescription: string;
  candidates: Candidate[];
  selectedSymbol?: string;
  onSelectSymbol: (symbol: string) => void;
  isOpen: boolean;
  onClose: () => void;
}

const STATUS_BADGE_STYLE: Record<StageStatus, { bg: string; text: string; label: string }> = {
  pass: { bg: 'bg-accent-green/15 border-accent-green/40', text: 'text-accent-green', label: 'تایید (PASS)' },
  reject: { bg: 'bg-accent-red/15 border-accent-red/40', text: 'text-accent-red', label: 'رد (REJECT)' },
  pending: { bg: 'bg-accent-yellow/15 border-accent-yellow/40', text: 'text-accent-yellow', label: 'در انتظار (PENDING)' },
  unavailable: { bg: 'bg-border-c/40 border-border-c', text: 'text-text-muted', label: 'بی‌داده (UNAVAILABLE)' },
  not_required: { bg: 'bg-border-c/25 border-border-c/60', text: 'text-text-muted', label: 'لازم نبود (NOT REQUIRED)' },
};

export const StrategyStageCandidateTable = React.memo(function StrategyStageCandidateTable({
  stageKey,
  stageTitle,
  stagePage,
  stageDescription,
  candidates,
  selectedSymbol,
  onSelectSymbol,
  isOpen,
  onClose,
}: StrategyStageCandidateTableProps) {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'pass' | 'reject' | 'other'>('all');

  const filteredCandidates = useMemo(() => {
    return candidates.filter((c) => {
      // فیلتر جستجو
      if (search.trim()) {
        const q = search.trim();
        const match = matchFa(c.symbol, q) || matchFa(c.name, q) || matchFa(c.sector, q);
        if (!match) return false;
      }

      // فیلتر وضعیت
      const st = c.status[stageKey];
      if (statusFilter === 'pass') return st === 'pass';
      if (statusFilter === 'reject') return st === 'reject';
      if (statusFilter === 'other') return st === 'pending' || st === 'unavailable';
      return true;
    });
  }, [candidates, search, statusFilter, stageKey]);

  const summary = useMemo(() => {
    let pass = 0;
    let reject = 0;
    let other = 0;
    for (const c of candidates) {
      const st = c.status[stageKey];
      if (st === 'pass') pass++;
      else if (st === 'reject') reject++;
      else other++;
    }
    return { total: candidates.length, pass, reject, other };
  }, [candidates, stageKey]);

  if (!isOpen) return null;

  return (
    <div
      data-testid="stage-candidate-drawer"
      className="fixed inset-y-0 end-0 z-50 w-full max-w-4xl bg-bg-card/95 border-s border-border-c shadow-2xl backdrop-blur-md flex flex-col animate-in slide-in-from-right duration-200"
    >
      {/* سربرگ کشو */}
      <div className="p-4 border-b border-border-c flex flex-col gap-3 bg-bg-secondary/60">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="rounded-lg bg-accent-blue/15 px-2 py-0.5 text-2xs font-black text-accent-blue">
                {stagePage}
              </span>
              <h2 className="text-base font-black text-text-primary">
                کاندیداهای مرحله: {stageTitle}
              </h2>
            </div>
            <p className="text-xs text-text-muted mt-1 leading-relaxed">
              {stageDescription}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-border-c p-1.5 text-text-muted hover:text-text-primary hover:bg-bg-primary transition-colors text-sm font-bold"
            aria-label="بستن پنجره"
            title="بستن جدول کاندیداها"
          >
            ✕
          </button>
        </div>

        {/* خلاصه شمارش و تب‌های فیلتر */}
        <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-border-c/40">
          <div className="flex items-center gap-1.5 text-2xs font-bold">
            <span className="text-text-muted">مجموع ورودی:</span>
            <span className="font-mono text-text-primary">{toFaDigits(summary.total)} نماد</span>
            <span className="text-border-c">|</span>
            <span className="text-accent-green">تایید: {toFaDigits(summary.pass)}</span>
            <span className="text-border-c">|</span>
            <span className="text-accent-red">رد: {toFaDigits(summary.reject)}</span>
            {summary.other > 0 && (
              <>
                <span className="text-border-c">|</span>
                <span className="text-text-muted">سایر: {toFaDigits(summary.other)}</span>
              </>
            )}
          </div>

          <div className="flex items-center gap-1">
            {(
              [
                { id: 'all' as const, label: `همه (${toFaDigits(summary.total)})` },
                { id: 'pass' as const, label: `تایید (${toFaDigits(summary.pass)})` },
                { id: 'reject' as const, label: `رد شده (${toFaDigits(summary.reject)})` },
                ...(summary.other > 0 ? [{ id: 'other' as const, label: `سایر (${toFaDigits(summary.other)})` }] : []),
              ]
            ).map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setStatusFilter(tab.id)}
                className={`rounded-lg px-2.5 py-1 text-2xs font-bold transition-all ${
                  statusFilter === tab.id
                    ? 'bg-accent-blue/20 text-accent-blue border border-accent-blue/40'
                    : 'text-text-muted hover:text-text-primary hover:bg-bg-primary'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* فیلد جستجوی نماد */}
        <div className="relative">
          <input
            type="text"
            placeholder="جستجوی نماد، نام شرکت یا صنعت..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-xl border border-border-c bg-bg-primary px-3 py-1.5 text-xs text-text-primary placeholder:text-text-muted focus:border-border-accent focus:outline-none"
          />
          {search && (
            <button
              type="button"
              onClick={() => setSearch('')}
              className="absolute end-2.5 top-2 text-text-muted hover:text-text-primary text-xs"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* بدنه جدول */}
      <div className="flex-1 overflow-auto p-4">
        {filteredCandidates.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center text-text-muted">
            <span className="text-3xl mb-2">🔍</span>
            <p className="text-xs font-bold">هیچ نمادی مطابق با فیلترهای انتخابی یافت نشد.</p>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-border-c bg-bg-card">
            <table className="w-full text-start text-xs border-collapse">
              <thead>
                <tr className="border-b border-border-c bg-bg-secondary/70 text-text-muted text-2xs font-black">
                  <th className="py-2.5 px-3 text-start">نماد / شرکت</th>
                  <th className="py-2.5 px-3 text-start">صنعت</th>
                  {stageKey === 'tape' && (
                    <>
                      <th className="py-2.5 px-3 text-end">آخرین قیمت</th>
                      <th className="py-2.5 px-3 text-end">حجم امروز</th>
                      <th className="py-2.5 px-3 text-start">الگوهای تابلو</th>
                    </>
                  )}
                  {stageKey === 'technical' && (
                    <>
                      <th className="py-2.5 px-3 text-center">روند هفتگی (ماژور)</th>
                      <th className="py-2.5 px-3 text-center">روند روزانه</th>
                      <th className="py-2.5 px-3 text-start">ستاپ تکنیکال</th>
                    </>
                  )}
                  {stageKey === 'fundamental' && (
                    <>
                      <th className="py-2.5 px-3 text-center" title={IND_COLUMNS[0].full}>رشد فروش</th>
                      <th className="py-2.5 px-3 text-center" title={IND_COLUMNS[1].full}>EPS ۳ ساله</th>
                      <th className="py-2.5 px-3 text-center" title={IND_COLUMNS[2].full}>حاشیه سود</th>
                      <th className="py-2.5 px-3 text-center" title={IND_COLUMNS[3].full}>فروش÷ارزش</th>
                      <th className="py-2.5 px-3 text-center" title={IND_COLUMNS[4].full}>نرخ‌گذاری</th>
                      <th className="py-2.5 px-3 text-center font-black">امتیاز</th>
                    </>
                  )}
                  {stageKey === 'handover' && (
                    <>
                      <th className="py-2.5 px-3 text-end">آخرین قیمت</th>
                      <th className="py-2.5 px-3 text-center">امتیاز FTS</th>
                      <th className="py-2.5 px-3 text-start">ستاپ فعال</th>
                      <th className="py-2.5 px-3 text-center">مجمع عمومی</th>
                      <th className="py-2.5 px-3 text-center">عملیات سبد</th>
                    </>
                  )}
                  <th className="py-2.5 px-3 text-center">وضعیت</th>
                  <th className="py-2.5 px-3 text-start">دلیل داوری FTS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-c/60">
                {filteredCandidates.map((c) => {
                  const isSelected = c.symbol === selectedSymbol;
                  const st = c.status[stageKey];
                  const badge = STATUS_BADGE_STYLE[st] ?? STATUS_BADGE_STYLE.unavailable;
                  const why = c.why[stageKey] || '—';

                  return (
                    <tr
                      key={c.symbol}
                      onClick={() => onSelectSymbol(c.symbol)}
                      className={`cursor-pointer transition-colors hover:bg-bg-secondary/80 ${
                        isSelected ? 'bg-accent-blue/15 font-bold' : ''
                      }`}
                    >
                      {/* ستون نماد */}
                      <td className="py-2 px-3 whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          <span className="font-black text-text-primary text-xs hover:text-accent-blue">
                            {c.symbol}
                          </span>
                          <span className="text-3xs text-text-muted truncate max-w-[90px]" title={c.name}>
                            {c.name}
                          </span>
                        </div>
                      </td>

                      {/* ستون صنعت */}
                      <td className="py-2 px-3 whitespace-nowrap text-2xs text-text-muted truncate max-w-[110px]" title={c.sector}>
                        {c.sector || '—'}
                      </td>

                      {/* ستون‌های اختصاصی مرحله تابلو */}
                      {stageKey === 'tape' && (
                        <>
                          <td className="py-2 px-3 text-end whitespace-nowrap font-mono text-2xs">
                            {c.row?.p_closing != null ? (
                              <div className="flex flex-col items-end">
                                <span>{fmtInt(c.row.p_closing)}</span>
                                {c.row.percent_change != null && (
                                  <span className={`text-3xs font-bold ${c.row.percent_change >= 0 ? 'text-accent-green' : 'text-accent-red'}`}>
                                    {fmtPct(c.row.percent_change)}
                                  </span>
                                )}
                              </div>
                            ) : (
                              '—'
                            )}
                          </td>
                          <td className="py-2 px-3 text-end whitespace-nowrap font-mono text-2xs text-text-secondary">
                            {c.row?.tvol != null ? toFaDigits(fmtInt(c.row.tvol)) : '—'}
                          </td>
                          <td className="py-2 px-3 whitespace-nowrap">
                            <div className="flex items-center gap-1 flex-wrap">
                              {c.patterns && c.patterns.length > 0 ? (
                                c.patterns.map((p, i) => (
                                  <span
                                    key={i}
                                    className="rounded bg-accent-yellow/15 border border-accent-yellow/40 px-1.5 py-0.5 text-3xs font-bold text-accent-yellow"
                                  >
                                    {p}
                                  </span>
                                ))
                              ) : (
                                <span className="text-3xs text-text-muted">—</span>
                              )}
                            </div>
                          </td>
                        </>
                      )}

                      {/* ستون‌های اختصاصی مرحله تکنیکال */}
                      {stageKey === 'technical' && (
                        <>
                          <td className="py-2 px-3 text-center whitespace-nowrap">
                            <span
                              className={`rounded px-1.5 py-0.5 text-3xs font-bold ${
                                c.trendW === 'up'
                                  ? 'bg-accent-green/20 text-accent-green'
                                  : c.trendW === 'down'
                                  ? 'bg-accent-red/20 text-accent-red'
                                  : 'bg-bg-primary text-text-muted'
                              }`}
                            >
                              {trendLabel(c.trendW)}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-center whitespace-nowrap text-2xs text-text-secondary">
                            {trendLabel(c.trendD)}
                          </td>
                          <td className="py-2 px-3 whitespace-nowrap">
                            {c.setups ? (
                              <span className="rounded bg-accent-blue/15 border border-accent-blue/40 px-1.5 py-0.5 text-3xs font-bold text-accent-blue">
                                {c.setups}
                              </span>
                            ) : (
                              <span className="text-3xs text-text-muted">—</span>
                            )}
                          </td>
                        </>
                      )}

                      {/* ستون‌های اختصاصی مرحله بنیادی */}
                      {stageKey === 'fundamental' && (
                        <>
                          {c.inds.map((indSt, idx) => (
                            <td key={idx} className="py-2 px-2 text-center whitespace-nowrap">
                              <span
                                className={`inline-block h-2 w-2 rounded-full ${
                                  indSt === 'pass'
                                    ? 'bg-accent-green'
                                    : indSt === 'reject'
                                    ? 'bg-accent-red'
                                    : 'bg-text-muted/40'
                                }`}
                                title={`${IND_COLUMNS[idx]?.label}: ${STATUS_LABEL[indSt]}`}
                              />
                            </td>
                          ))}
                          <td className="py-2 px-3 text-center whitespace-nowrap font-mono font-bold text-xs text-text-primary">
                            {c.score != null ? `${toFaDigits(c.score)} / ۵` : '—'}
                          </td>
                        </>
                      )}

                      {/* ستون‌های اختصاصی تحویل نهایی */}
                      {stageKey === 'handover' && (
                        <>
                          <td className="py-2 px-3 text-end whitespace-nowrap font-mono text-2xs">
                            {c.row?.p_closing != null ? fmtInt(c.row.p_closing) : '—'}
                          </td>
                          <td className="py-2 px-3 text-center whitespace-nowrap font-mono font-bold text-xs text-accent-green">
                            {c.score != null ? `${toFaDigits(c.score)} از ۵` : '—'}
                          </td>
                          <td className="py-2 px-3 whitespace-nowrap text-2xs text-accent-blue font-bold">
                            {c.setups || 'تایید روند FTS'}
                          </td>
                          <td className="py-2 px-3 text-center whitespace-nowrap">
                            {c.assemblyVeto ? (
                              <span className="rounded bg-accent-red/20 px-1.5 py-0.5 text-3xs font-bold text-accent-red">
                                وتوی مجمع
                              </span>
                            ) : (
                              <span className="rounded bg-accent-green/20 px-1.5 py-0.5 text-3xs font-bold text-accent-green">
                                بدون مجمع ✓
                              </span>
                            )}
                          </td>
                          <td
                            className="py-2 px-3 text-center whitespace-nowrap"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <SymbolBasketAction symbol={c.symbol} />
                          </td>
                        </>
                      )}

                      {/* وضعیت کلی این مرحله */}
                      <td className="py-2 px-3 text-center whitespace-nowrap">
                        <span className={`rounded-md border px-2 py-0.5 text-3xs font-black ${badge.bg} ${badge.text}`}>
                          {badge.label}
                        </span>
                      </td>

                      {/* دلیل داوری */}
                      <td className="py-2 px-3 text-2xs text-text-muted truncate max-w-[220px]" title={why}>
                        {why}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
});
