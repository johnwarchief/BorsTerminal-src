import type { CapacitorConfig } from '@capacitor/cli';

// پیکربندی پوستهٔ اندروید (اپ موبایل مستقل — بدون سرور)
// - webDir: همان خروجی vite با VITE_LOCAL_DATA=1 (+ mobile_snapshot.db.gz کنارش)
// - CapacitorHttp عمداً «سراسری» فعال نیست: پچِ سراسری همهٔ fetchها (حتی
//   دانلود اسنپ‌شات و sql-wasm از خود WebView: https://localhost/…) را به لایهٔ
//   بومی می‌برد که سرور مجازی WebView را نمی‌بیند ⇒ دیتابیس هرگز باز نمی‌شد و
//   همهٔ تب‌ها خالی می‌ماند (باگ گزارش‌شدهٔ نصب اول). به‌جایش لایهٔ زنده
//   (shared/api/local/nativeHttp.ts) خودش صریح CapacitorHttp.get را برای
//   دامنه‌های بیرونی (cdn.tsetmc.com و GitHub) صدا می‌زند — بدون دیوار CORS.
const config: CapacitorConfig = {
  appId: 'com.borsterminal.mobile',
  appName: 'بورس‌ترمینال',
  webDir: 'dist',
  android: {
    allowMixedContent: false,
  },
};

export default config;
