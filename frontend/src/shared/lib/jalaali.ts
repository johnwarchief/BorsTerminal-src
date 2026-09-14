// shared/lib/jalaali.ts -- تبدیل تاریخ جلالی به میلادی (الگوریتم استاندارد)
// پورت حداقلی jalaali-js برای سن صورت مالی؛ بدون وابستگی.
// تقسیم و باقیمانده با معنای برشی (مانند jalaali-js) نه کف -- برای اعداد منفی فرق می کند
function div(a: number, b: number): number {
  return Math.trunc(a / b);
}
function mod(a: number, b: number): number {
  return a - Math.trunc(a / b) * b;
}

const BREAKS = [-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178];

function jalCal(jy: number): { leap: number; gy: number; march: number } {
  const bl = BREAKS.length;
  const gy = jy + 621;
  let leapJ = -14;
  let jp = BREAKS[0];
  let jm = 0;
  let jump = 0;
  for (let i = 1; i < bl; i += 1) {
    jm = BREAKS[i];
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

function j2d(jy: number, jm: number, jd: number): number {
  const r = jalCal(jy);
  return g2d(r.gy, 3, r.march) + (jm - 1) * 31 - div(jm, 7) * (jm - 7) + jd - 1;
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

/** تبدیل تاریخ جلالی به میلادی؛ ورودی نامعتبر یعنی null */
export function jalaaliToGregorian(jy: number, jm: number, jd: number): [number, number, number] | null {
  if (![jy, jm, jd].every((v) => Number.isInteger(v))) return null;
  if (jy < 1200 || jy > 1600 || jm < 1 || jm > 12 || jd < 1 || jd > 31) return null;
  return d2g(j2d(jy, jm, jd));
}

/** پارس رشته دوره کدال به شکل YYYY/MM/DD و تبدیل به epoch ms */
export function jalToEpochMs(jal: string | null | undefined): number | null {
  if (!jal) return null;
  const m = /^(\d{4})\/(\d{1,2})\/(\d{1,2})/.exec(jal.trim());
  if (!m) return null;
  const g = jalaaliToGregorian(Number(m[1]), Number(m[2]), Number(m[3]));
  if (!g) return null;
  return Date.UTC(g[0], g[1] - 1, g[2]);
}

/** سن صورت مالی به روز؛ نامشخص یعنی null */
export function statementAgeDays(periodEnd: string | null | undefined, nowMs = Date.now()): number | null {
  const t = jalToEpochMs(periodEnd);
  if (t == null) return null;
  return Math.max(0, Math.floor((nowMs - t) / 86_400_000));
}
