// shared/api/local/symbolIdentity.ts — رجیستری و حل‌کنندهٔ هویت نماد در کلاینت محلی
//
// همتای دقیقِ قرارداد symbol_identity.py در دسکتاپ:
//   ۱) کلیدِ هویت: یکسان‌سازی ي/ك/ى ← ی/ک، و حذف همهٔ جداسازهای نامرئی و فاصله.
//   ۲) نامزدهای خام از خودِ پایگاه خوانده می‌شوند.
//   ۳) پسوندهای خط تابلو (مثل آباد3، خودرو2): تنها یک رقم انتهایی حذف می‌شود
//      و فقط با تایید یا عدم تعارض ISIN معتبر مجاز است.
//   ۴) هیچ تطبیق فازی/تقریبی مجاز نیست؛ اگر کلید فرق دارد، دو ابزار متفاوتند.

import { query } from './localData';

export type IdentityEvidence =
  | 'exact'
  | 'same-key'
  | 'isin-agree'
  | 'no-isin'
  | 'isin-clash'
  | 'ambiguous'
  | 'unmatched';

export interface SymbolIdentity {
  symbol: string;
  key: string;
  baseKey: string;
  hasLineSuffix: boolean;
  evidence: IdentityEvidence;
  isinPrefixes: string[];
  resolved: boolean;
}

export interface IdentityRegistryStats {
  totalInstruments: number;
  uniqueSymbols: number;
  uniqueKeys: number;
  lineSymbols: number;
  isinAgree: number;
  isinClash: number;
  noIsin: number;
  ambiguous: number;
}

const YA_FA = '\u06cc';
const YA_AR = '\u064a';
const HAMZA = '\u0649';
const KAF_FA = '\u06a9';
const KAF_AR = '\u0643';

const SEP_REGEX = /[ \u00a0\u200c\u200f\u200e\u202f]+/g;
const ONE_DIGIT_SUFFIX = /(?<=\D)\d$/;

/** یکسان‌سازی حروف عربی به فارسی بدون حذف فاصله. */
export function normSymbol(text: string | null | undefined): string {
  if (!text) return '';
  return String(text)
    .replace(new RegExp(YA_AR, 'g'), YA_FA)
    .replace(new RegExp(HAMZA, 'g'), YA_FA)
    .replace(new RegExp(KAF_AR, 'g'), KAF_FA);
}

/** کلید هویت یک نماد: یکسان‌سازی حروف + حذف کامل فواصل و جداسازهای نامرئی + حروف کوچک. */
export function symbolKey(symbol: string | null | undefined): string {
  if (!symbol) return '';
  return normSymbol(symbol).replace(SEP_REGEX, '').toLowerCase();
}

interface RegistryCache {
  builtAt: number;
  totalInstruments: number;
  uniqueSymbols: number;
  byKey: Map<string, string[]>;
  isinByKey: Map<string, Set<string>>;
}

let registryCache: RegistryCache | null = null;

/** بازنشانی کش هویت (برای تست‌ها) */
export function __resetIdentityRegistryForTest(): void {
  registryCache = null;
}

/** ساخت یا دریافت کش رجیستری هویت از جدول instruments */
export async function getIdentityRegistry(): Promise<RegistryCache> {
  if (registryCache) return registryCache;

  const byKey = new Map<string, string[]>();
  const isinByKey = new Map<string, Set<string>>();
  const seenRawSymbols = new Set<string>();
  let totalInstruments = 0;

  try {
    const rows = await query('SELECT l_val18, isin FROM instruments');
    totalInstruments = rows.length;
    for (const r of rows) {
      const sym = r.l_val18 ? String(r.l_val18).trim() : '';
      if (!sym) continue;
      seenRawSymbols.add(sym);
      const k = symbolKey(sym);
      if (!k) continue;

      const list = byKey.get(k) ?? [];
      if (!list.includes(sym)) {
        list.push(sym);
        byKey.set(k, list);
      }

      const isinStr = r.isin ? String(r.isin).trim().toUpperCase() : '';
      if (isinStr.startsWith('IR') && isinStr.length >= 9) {
        const seg = isinStr.slice(0, 9);
        const set = isinByKey.get(k) ?? new Set<string>();
        set.add(seg);
        isinByKey.set(k, set);
      }
    }
  } catch {
    // اگر جدول در دسترس نبود (در محیط تست بدون DB یا اسنپ‌شات اولیه)
  }

  registryCache = {
    builtAt: Date.now(),
    totalInstruments,
    uniqueSymbols: seenRawSymbols.size,
    byKey,
    isinByKey,
  };
  return registryCache;
}

/** تشخیص هویت نماد، پسوند خط و تطابق ISIN */
export async function resolveSymbolIdentity(rawSymbol: string): Promise<SymbolIdentity> {
  const k = symbolKey(rawSymbol);
  if (!k) {
    return {
      symbol: rawSymbol,
      key: '',
      baseKey: '',
      hasLineSuffix: false,
      evidence: 'unmatched',
      isinPrefixes: [],
      resolved: false,
    };
  }

  const reg = await getIdentityRegistry();
  const isinSet = reg.isinByKey.get(k);
  const isinPrefixes = isinSet ? Array.from(isinSet) : [];

  // بررسی پسوند تک‌رقمی خط تابلو (مثل شستا2 یا آباد3)
  const isNumericLine = k.length >= 3 && ONE_DIGIT_SUFFIX.test(k);
  if (!isNumericLine) {
    const isKnown = reg.byKey.has(k);
    return {
      symbol: rawSymbol,
      key: k,
      baseKey: k,
      hasLineSuffix: false,
      evidence: isKnown ? 'exact' : 'unmatched',
      isinPrefixes,
      resolved: isKnown,
    };
  }

  const base = k.replace(ONE_DIGIT_SUFFIX, '');
  const mineIsin = isinSet ?? new Set<string>();
  const baseIsin = reg.isinByKey.get(base) ?? new Set<string>();

  let evidence: IdentityEvidence = 'unmatched';
  let resolved = false;

  if (mineIsin.size > 0 && baseIsin.size > 0) {
    let hasIntersection = false;
    for (const p of mineIsin) {
      if (baseIsin.has(p)) {
        hasIntersection = true;
        break;
      }
    }
    if (hasIntersection) {
      evidence = 'isin-agree';
      resolved = true;
    } else {
      evidence = 'isin-clash';
      resolved = false;
    }
  } else if (mineIsin.size > 0 || baseIsin.size > 0) {
    evidence = 'no-isin';
    resolved = true;
  } else {
    // هر دو فاقد ISIN هستند؛ اگر پایه وجود داشته باشد
    evidence = reg.byKey.has(base) ? 'ambiguous' : 'unmatched';
    resolved = false;
  }

  return {
    symbol: rawSymbol,
    key: k,
    baseKey: base,
    hasLineSuffix: true,
    evidence,
    isinPrefixes,
    resolved,
  };
}

/** محاسبهٔ آمار کامل هویت نمادها بر اساس پایگاه داده */
export async function calculateIdentityStats(): Promise<IdentityRegistryStats> {
  const reg = await getIdentityRegistry();
  let lineSymbols = 0;
  let isinAgree = 0;
  let isinClash = 0;
  let noIsin = 0;
  let ambiguous = 0;

  for (const k of reg.byKey.keys()) {
    if (k.length >= 3 && ONE_DIGIT_SUFFIX.test(k)) {
      lineSymbols += 1;
      const base = k.replace(ONE_DIGIT_SUFFIX, '');
      const mine = reg.isinByKey.get(k) ?? new Set<string>();
      const theirs = reg.isinByKey.get(base) ?? new Set<string>();

      if (mine.size > 0 && theirs.size > 0) {
        let agree = false;
        for (const item of mine) {
          if (theirs.has(item)) {
            agree = true;
            break;
          }
        }
        if (agree) isinAgree += 1;
        else isinClash += 1;
      } else if (mine.size > 0 || theirs.size > 0) {
        noIsin += 1;
      } else {
        ambiguous += 1;
      }
    }
  }

  return {
    totalInstruments: reg.totalInstruments,
    uniqueSymbols: reg.uniqueSymbols,
    uniqueKeys: reg.byKey.size,
    lineSymbols,
    isinAgree,
    isinClash,
    noIsin,
    ambiguous,
  };
}
