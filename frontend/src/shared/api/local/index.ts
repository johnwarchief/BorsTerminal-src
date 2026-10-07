// shared/api/local — لایهٔ دادهٔ محلی برای بیلد موبایل (VITE_LOCAL_DATA='1')
// نقطهٔ ورود: resolveLocal(url, method, body) — از http.ts (تنها مصرف‌کننده)
// به‌صورت ایمپورت داینامیک صدا می‌شود تا بیلد دسکتاپ دست‌نخورده بماند.
export { resolveLocal } from './resolvers';
export { getDb, metaValue } from './localData';
