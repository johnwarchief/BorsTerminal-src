// shared/lib/flashClock.ts -- طولِ فلاش از ریتمِ خودِ تابلو می‌آید، نه از عددِ ثابتِ CSS
//
// رأیِ مالک (۱۴۰۵-۰۷-۰۷): «اگر ۵ ثانیه بازۀِ بروزرسانی است، ۳ تا ۴ ثانیه فلاش
// بزند». تا پیش از این `.flash-up/.flash-down` سربسته ۱.۶ ثانیه بود؛ با
// پولینگِ ۵ ثانیه یعنی یک‌سومِ عمرِ سلول رنگی و درِ عمل — چون ردیف‌هایِ
// جدول با هر تیک از نو ساخته می‌شوند — پیش از دیدنِ محو با انیمیشنِ بعدی
// بازنشانی می‌شد. ۷۰٪ِ بازه سهمِ رنگ است و سقفش ۴ ثانیه، تا درِ بازۀِ
// یک‌دقیقه‌ای و پنج‌دقیقه‌ای فلاش رویِ سلول خشک نشود.
import { useEffect } from 'react';
import { useMarketStore } from '@shared/stores/marketStore';
import { effectivePollMs } from '@shared/lib/marketHours';

export const FLASH_SHARE = 0.7;
export const FLASH_MIN_MS = 1_200;
export const FLASH_MAX_MS = 4_000;

/** مدتِ فلاش برایِ یک بازۀِ پولینگ — همان چیزی که CSS می‌خواند. */
export function flashDurationMs(pollMs: number): number {
  const v = Math.round(pollMs * FLASH_SHARE);
  return Math.min(FLASH_MAX_MS, Math.max(FLASH_MIN_MS, Number.isFinite(v) ? v : FLASH_MIN_MS));
}

/** متغیرِ CSS را رویِ ریشۀِ سند می‌نشیند و همان میلی‌ثانیه را برمی‌گرداند. */
export function applyFlashClock(pollMs: number): number {
  const ms = flashDurationMs(effectivePollMs(pollMs));
  document.documentElement.style.setProperty('--bors-flash-dur', `${ms}ms`);
  return ms;
}

/**
 * یک‌بار درِ پوستۀِ اپ صدا زده می‌شود. بازهٔ ۳۰ ثانیه‌ای برایِ این است که
 * باز/بسته‌شدنِ بازار (که `effectivePollMs` را عوض می‌کند) ریتمِ فلاش را هم
 * عوض کند؛ خودِ store بی‌خبر می‌ماند چون انتخابِ کاربر ثابت است.
 */
export function useFlashClock(): void {
  const pollMs = useMarketStore((s) => s.refetchIntervalMs);
  useEffect(() => {
    applyFlashClock(pollMs);
    const t = window.setInterval(() => applyFlashClock(pollMs), 30_000);
    return () => window.clearInterval(t);
  }, [pollMs]);
}
