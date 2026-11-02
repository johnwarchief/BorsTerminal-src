/**
 * features/technical/lib/telegramIndicatorCatalog.ts
 *
 * کاتالوگِ اندیکاتورهای گروه indicators در تلگرام، استخراج‌شده در 2026-11-03.
 * داده از data/telegram-indicators.json می‌آید و عکس‌ها از assets/…/*.webp.
 *
 * چرا ادعای سطحِ ماژول: tvIndicatorCatalog.ts:1 همان دردی را نوشته که منوی
 * hardcode با لیستِ ثبتِ جدا می‌سازد — کلیکِ بی‌صدایِ بی‌نتیجه. اینجا نبودِ
 * یک عکس باعث خطایِ روشن می‌شود، نه سطرِ بی‌عکس.
 */

import { z } from 'zod';

import { ADVANCED_INDICATORS_REGISTRY } from '../overlays/advancedTradingIndicators';
import { USER_INDICATORS_REGISTRY } from '../overlays/userIndicators';
import rawCatalog from '../data/telegram-indicators.json';

const RowSchema = z.object({
  id: z.string().regex(/^p\d{2}$/),
  titleEn: z.string(),
  captionEn: z.string(),
  photo: z.string().regex(/^p\d{2}\.webp$/),
  dims: z.string(),
  attachments: z.array(z.string()),
});

const CatalogSchema = z.array(RowSchema);

/**
 * `dims` ابعادِ تصویرِ مبدأِ export است (مثلاً 1280×608)، نه اندازهٔ webpِ
 * تحویلی روی دیسک که روی ۹۰۰ پیکسل سقف می‌خورد (p01: فایل 900×428).
 * هیچ‌وقت dims را به width/heightِ <img> ندهید — Ruling 5 در progress.md.
 */
export type TelegramRow = z.infer<typeof RowSchema> & {
  photoUrl: string;
  overlayId: string | null;
};

const photoModules = import.meta.glob('../assets/telegram-indicators/*.webp', {
  eager: true,
  query: '?url',
  import: 'default',
}) as Record<string, string>;

const urlByName = new Map<string, string>(
  Object.entries(photoModules).map(([path, url]) => [path.split('/').pop() as string, url]),
);

/**
 * ردیف‌های کاتالوگ ← اورلیِ پیاده‌شده در همین درخت. دستی نگه داشته می‌شود و
 * در JSONِ تولیدی نیست تا با تولیدِ دوباره گم نشود.
 * p28 و p42 تکراریِ همان پست‌های p22 و p14 هستند (یک تصویر در دو پیام)، پس
 * لینک می‌گیرند. ترتیب از export واقعی است، نه از telegram_indicators_catalog.json.
 */
export const TELEGRAM_OVERLAY_LINKS: Record<string, string> = {
  p02: 'FiboRSI8',
  p03: 'SuperTrendHeikinAshi',
  p05: 'RsiMaSmooth',
  p06: 'BreakoutRetestPro',
  p12: 'DoubleTap3D',
  p14: 'AutoTrendlineCHoCH',
  p22: 'SuperTrendPullback',
  p28: 'SuperTrendPullback',
  p42: 'AutoTrendlineCHoCH',
};

/** دو اورلیِ پیاده‌شده که هیچ پستِ تلگرامی بی‌ابهام نامشان نمی‌برد — حدس زده نشد */
export const UNLINKED_OVERLAYS: string[] = ['MultiModeChannel', 'MultiVariantRSI'];

function assertCatalog(rows: ReturnType<typeof CatalogSchema.parse>): void {
  if (rows.length !== 64) {
    throw new Error(`telegram catalog: expected 64 rows, got ${rows.length}`);
  }
  const noPhoto = rows.filter((r) => !urlByName.has(r.photo)).map((r) => r.id);
  if (noPhoto.length > 0) {
    throw new Error(`telegram catalog: photos missing from assets for ${noPhoto.join(', ')}`);
  }
  const known = new Set([
    ...ADVANCED_INDICATORS_REGISTRY.map((i) => i.id),
    ...USER_INDICATORS_REGISTRY.map((i) => i.id),
  ]);
  const dead = Object.entries(TELEGRAM_OVERLAY_LINKS).filter(([, id]) => !known.has(id));
  if (dead.length > 0) {
    throw new Error(`telegram catalog: links to absent overlays: ${JSON.stringify(dead)}`);
  }
}

const parsed = CatalogSchema.parse(rawCatalog);
assertCatalog(parsed);

export const TELEGRAM_CATALOG: TelegramRow[] = parsed.map((r) => ({
  ...r,
  photoUrl: urlByName.get(r.photo) as string,
  overlayId: TELEGRAM_OVERLAY_LINKS[r.id] ?? null,
}));

export function searchTelegramRows(query: string): TelegramRow[] {
  const q = query.trim().toLowerCase();
  if (!q) return TELEGRAM_CATALOG;
  return TELEGRAM_CATALOG.filter(
    (r) =>
      r.titleEn.toLowerCase().includes(q) ||
      r.captionEn.toLowerCase().includes(q) ||
      r.attachments.some((a) => a.toLowerCase().includes(q)),
  );
}
