import type { CapacitorConfig } from '@capacitor/cli';

// پیکربندی پوستهٔ اندروید (اپ موبایل مستقل — بدون سرور)
// - webDir: همان خروجی vite با VITE_LOCAL_DATA=1 (+ mobile_snapshot.db.gz کنارش)
// - CapacitorHttp: fetch را از مسیر بومی می‌برد ⇒ درخواست مستقیم گوشی به
//   cdn.tsetmc.com و GitHub Releases بدون دیوار CORS (ستون فاز ۳ب).
const config: CapacitorConfig = {
  appId: 'com.borsterminal.mobile',
  appName: 'بورس‌ترمینال',
  webDir: 'dist',
  plugins: {
    CapacitorHttp: {
      enabled: true,
    },
  },
  android: {
    allowMixedContent: false,
  },
};

export default config;
