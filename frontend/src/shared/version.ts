// src/shared/version.ts -- منبعِ واحدِ حقیقتِ نسخهٔ فرانت‌اند.
//
// مقدارِ نسخه مستقیماً از package.json خوانده می‌شود و Vite آن را در زمان build
// به‌صورت یک رشته‌ی ثابت درون باندل اینلاین می‌کند. به این ترتیب هیچ مقدار
// hardcode شده‌ای در سورس وجود ندارد که نسبت به package.json استیل شود —
// دقیقاً همین موضوع باعث شده بود نسخهٔ ۱.۰.۶ هنوز «۱.۰.۳» نمایش دهد.
//
// منبعِ تغییرِ این مقدار فقط فایل package.json است.
import { version } from '../../package.json';

export const APP_VERSION: string = version;
