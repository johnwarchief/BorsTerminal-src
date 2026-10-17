// shared/api/local/probe.ts — قلابِ خواندنیِ سنجهٔ دستگاه (فقط بیلدِ آزمایشی)
//
// چرا این فایل هست: «قیف آفلاین کار می‌کند» را تا امروز یا درِ jsdom سنجیده‌ایم
// یا درِ Chromiumِ دسکتاپ؛ هیچ‌کدام WebView واقعی نیست. این هوک تنها کاری که
// می‌کند همان resolveLocalِ خودِ برنامه را از بیرونِ React صدا می‌زند — نه
// پیاده‌سازیِ دوباره، نه دادهٔ ساختگی. اگر قراردادِ کلید یا پاسخ عوض شود،
// سنجهٔ دستگاه همان را می‌بیند، نه چیزی که آزمونِ جدا فرض می‌کند.
//
// درِ بیلدِ معمولی (VITE_ANDROID_PROBE≠'1') کلِ این شاخه tree-shake می‌شود؛
// هیچ بایتی به artifactِ منتشرشدنی راه نمی‌یابد. روشنشدنش فقط با پرچمِ
// build-time و درِ رانِ آزمایشیِ bake است (خروجیِ bake هرگز منتشر نمی‌شود).
import { resolveLocal } from './resolvers';

type ProbeReply = {
  ok: boolean;
  status?: string | null;
  joined?: number | null;
  entries?: number | null;
  matrixCells?: number | null;
  http?: number | null;
  message?: string;
};

async function ask(url: string, body?: unknown): Promise<ProbeReply> {
  try {
    const data = (await resolveLocal(url, 'GET', body)) as {
      status?: string; universe?: { joined?: number };
      entries?: unknown[]; status_matrix?: Record<string, unknown>;
    } | null;
    const matrix = data?.status_matrix;
    return {
      ok: true,
      status: data?.status ?? null,
      joined: data?.universe?.joined ?? null,
      entries: Array.isArray(data?.entries) ? data.entries.length : null,
      matrixCells: matrix ? Object.keys(matrix).length : null,
    };
  } catch (e) {
    const err = e as { status?: number; message?: string };
    return { ok: false, http: err?.status ?? null,
             message: String(err?.message ?? e).slice(0, 300) };
  }
}

export function mountProbe(): void {
  const w = window as unknown as Record<string, unknown>;
  w.__borsProbe = { version: 1, ask, booted: () => (w.bootTiming ?? null) };
}
