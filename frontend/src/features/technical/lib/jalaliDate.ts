// features/technical/lib/jalaliDate.ts -- نمایش تاریخ میلادی UTC به جلالی برای محور چارت
// پورت وفادار الگوریتم jalaali-js (toJalaali) تا وابستگی خارجی و CDN نباشد.
// فقط برای نمایش تاریخ؛ محاسبات ممیزی شده در lib/indicators.ts با epoch کار می کنند.

function div(a: number, b: number): number {
  return Math.trunc(a / b);
}

function mod(a: number, b: number): number {
  return a - Math.trunc(a / b) * b;
}

function jalCal(jy: number): { leap: number; gy: number; march: number } {
  const breaks = [-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178];
  const bl = breaks.length;
  const gy = jy + 621;
  let leapJ = -14;
  let jp = breaks[0];
  let jm = 0;
  let jump = 0;
  for (let i = 1; i < bl; i += 1) {
    jm = breaks[i];
    jump = jm - jp;
    if (jy < jm) break;
    leapJ += div(jump, 33) * 8 + div(mod(jump, 33), 4);
    jp = jm;
  }
  let n = jy - jp;
  leapJ += div(n, 33) * 8 + div(mod(n, 33) + 3, 4);
  if (mod(jump, 33) === 4 && jump - n === 4) leapJ += 1;
  const leapG = div(gy, 4) - div((div(gy, 100) + 1) * 3, 4) - 150;
  const march = 20 + leapJ - leapG;
  if (jump - n < 6) n = n - jump + div(jump + 4, 33) * 33;
  let leap = mod(mod(n + 1, 33) - 1, 4);
  if (leap === -1) leap = 4;
  return { leap, gy, march };
}

function g2d(gy: number, gm: number, gd: number): number {
  let d =
    div((gy + div(gm - 8, 6) + 100100) * 1461, 4) + div(153 * mod(gm + 9, 12) + 2, 5) + gd - 34840408;
  d = d - div(div(gy + 100100 + div(gm - 8, 6), 100) * 3, 4) + 752;
  return d;
}

function d2j(jdn: number): { jy: number; jm: number; jd: number } {
  const gy = d2g(jdn)[0];
  let jy = gy - 621;
  const r = jalCal(jy);
  const jdn1f = g2d(gy, 3, r.march);
  let k = jdn - jdn1f;
  if (k >= 0) {
    if (k <= 185) {
      const jm = 1 + div(k, 31);
      const jd = mod(k, 31) + 1;
      return { jy, jm, jd };
    }
    k -= 186;
  } else {
    jy -= 1;
    k += 179;
    if (r.leap === 1) k += 1;
  }
  const jm = 7 + div(k, 30);
  const jd = mod(k, 30) + 1;
  return { jy, jm, jd };
}

function d2g(jdn: number): [number, number, number] {
  let j = 4 * jdn + 139361631;
  j += div(div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908;
  const i = div(mod(j, 1461), 4) * 5 + 308;
  const gd = div(mod(i, 153), 5) + 1;
  const gm = mod(div(i, 153), 12) + 1;
  const gy = div(j, 1461) - 100100 + div(8 - gm, 6);
  return [gy, gm, gd];
}

/** تبدیل تاریخ میلادی به جلالی (هم ارز Jalaali.toJalaali) */
export function gregorianToJalaali(gy: number, gm: number, gd: number): { jy: number; jm: number; jd: number } {
  return d2j(g2d(gy, gm, gd));
}

function j2d(jy: number, jm: number, jd: number): number {
  const r = jalCal(jy);
  return g2d(r.gy, 3, r.march) + (jm - 1) * 31 - div(jm, 7) * (jm - 7) + jd - 1;
}

/** تبدیل تاریخ جلالی به میلادی [gy, gm, gd] */
export function jalaaliToGregorian(jy: number, jm: number, jd: number): [number, number, number] {
  return d2g(j2d(jy, jm, jd));
}

/** تاریخ epoch میلی ثانیه به رشته جلالی YYYY/MM/DD؛ ورودی نامعتبر رشته خالی */
export function epochToJalali(ts: number): string {
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return '';
  const j = gregorianToJalaali(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate());
  const jm = String(j.jm).padStart(2, '0');
  const jd = String(j.jd).padStart(2, '0');
  return `${j.jy}/${jm}/${jd}`;
}

/**
 * پارس مقاوم و جامع زمان به میلی‌ثانیه UTC
 * پشتیبانی از عدد ms/s، فرمت YYYYMMDD، رشته‌های استاندارد میلادی و تاریخ‌های شمسی
 */
export function parseCandleTimestamp(raw: unknown): number {
  if (typeof raw === 'number') {
    if (!Number.isFinite(raw) || raw <= 0) return Number.NaN;
    return raw < 1e11 ? raw * 1000 : raw;
  }
  if (typeof raw === 'string') {
    const s = raw.trim();
    if (!s) return Number.NaN;
    if (/^\d{10,13}$/.test(s)) {
      const num = Number(s);
      return num < 1e11 ? num * 1000 : num;
    }
    if (/^\d{8}$/.test(s)) {
      const y = Number(s.slice(0, 4));
      const m = Number(s.slice(4, 6));
      const d = Number(s.slice(6, 8));
      if (y >= 1300 && y <= 1500) {
        const [gy, gm, gd] = jalaaliToGregorian(y, m, d);
        return Date.UTC(gy, gm - 1, gd);
      }
      return Date.UTC(y, m - 1, d);
    }
    const match = s.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})/);
    if (match) {
      const y = Number(match[1]);
      const m = Number(match[2]);
      const d = Number(match[3]);
      if (y >= 1300 && y <= 1500) {
        const [gy, gm, gd] = jalaaliToGregorian(y, m, d);
        return Date.UTC(gy, gm - 1, gd);
      }
      return Date.UTC(y, m - 1, d);
    }
    const parsed = Date.parse(s);
    if (Number.isFinite(parsed) && parsed > 0) return parsed;
  }
  return Number.NaN;
}

