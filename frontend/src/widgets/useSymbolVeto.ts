// widgets/useSymbolVeto.ts -- دو وتویِ واقعیِ یک نماد، از همان منبعِ جدول و قیف
// سایدبارِ چپ تا پیش از این «وتو» را خودش از سیگنال‌هایِ باس می‌ساخت؛ نتیجه دو چیز
// بود: (۱) نمادی که کاربر هنوز تبش را باز نکرده بود قرمز «وتو» می‌خورد (بی‌داده ≠
// وتو — همان قاعدۀ dev/weekly_veto_guard.py و dev/assembly_veto_v1064.py)، و
// (۲) وتوی مجمع — که مالک رأی داد (#53) — هیچ‌جا در سایدبار دیده نمی‌شد.
// اینجا داوریِ تازه‌ای ساخته نمی‌شود: مجمع از همان `/api/calendar/upcoming` (یک
// درخواستِ انبوه، همان که برچسبِ جدول می‌خواند) و هفتگی از همان `weekly_veto`ِ
// بک‌اند در payload اسکرینر، فقط وقتی کش‌شده باشد. نبودِ ردیف ⇒ نظر نمی‌دهیم.
import { useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';
import { groupBySymbol, useCalendarUpcoming } from '@features/fundamental/api/useCalendarUpcoming';
import { pickAssemblyBadge } from '@features/fundamental/lib/assemblyEvent';
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';
import { normalizeFa } from '@shared/lib/normalizeFa';

export type SymbolVeto = {
  /** وتوی مجمع — زمان‌بندیِ ورود، نه ضعفِ بنیادی */
  assembly: { veto: boolean; days: number | null; date: string | null; label: string };
  /** وتوی روند هفتگی — رأیِ بک‌اند (matrix.decision === REJECT) */
  weekly: { veto: boolean; desc: string | null };
  /** آیا اصلاً منبعی برای داوری بوده؟ */
  known: boolean;
  /** ردیفِ اسکرینرِ همین نماد از کشِ موجود (null = هنوز خوانده نشده) — همان
   *  منبعی که قیف می‌خواند، تا سایدبار قواعدِ دومی نسازد. */
  screen: FtsScreenRow | null;
};

const NONE: SymbolVeto = {
  assembly: { veto: false, days: null, date: null, label: '' },
  weekly: { veto: false, desc: null },
  known: false,
  screen: null,
};

/** کلیدهایِ `useFtsScreen` که در برنامه مصرف می‌شوند — هر کدام اگر کش شده باشد خوانده می‌شود */
const SCREEN_KEYS: readonly number[] = [120, 60];

export function useSymbolVeto(symbol: string): SymbolVeto {
  const qc = useQueryClient();
  // بی‌نمادِ انتخابی هیچ درخواستی نمی‌سازیم؛ سایدبار در آن حالت پشتِ صحنه است.
  const upcoming = useCalendarUpcoming(undefined, symbol.length > 0);
  const grouped = useMemo(() => groupBySymbol(upcoming.data?.items), [upcoming.data]);

  return useMemo(() => {
    if (!symbol) return NONE;
    const want = normalizeFa(symbol);
    const eventList =
      grouped[symbol] ??
      Object.entries(grouped).find(([k]) => normalizeFa(k) === want)?.[1] ??
      [];
    const badge = pickAssemblyBadge(eventList);
    const assembly =
      badge?.kind === 'near'
        ? { veto: true, days: badge.days, date: badge.date, label: badge.label }
        : { veto: false, days: badge?.days ?? null, date: badge?.date ?? null, label: '' };

    let weekly: SymbolVeto['weekly'] = { veto: false, desc: null };
    let screen: FtsScreenRow | null = null;
    for (const limit of SCREEN_KEYS) {
      const rows = qc.getQueryData<{ data?: FtsScreenRow[] }>(['fts-screen', limit])?.data;
      if (!rows?.length) continue;
      const row =
        rows.find((r) => r.symbol === symbol) ??
        rows.find((r) => normalizeFa(r.symbol ?? '') === want);
      if (!row) continue;
      screen = row;
      if (row.weekly_veto === true || row.tech_matrix_decision === 'REJECT') {
        weekly = {
          veto: true,
          desc: row.tech_matrix_desc ?? (row.tech_trend_w === 'down' ? 'روند نزولی' : 'روند خنثی'),
        };
      }
      break;
    }

    return {
      assembly,
      weekly,
      known: screen != null || eventList.length > 0,
      screen,
    };
  }, [symbol, grouped, qc]);
}
