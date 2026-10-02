// `_audit/indicator_audit/js_entry.ts` — پلِ bundling برایِ سنجشِ عددیِ ریاضیِ فرانت.
// هیچ کدِ محصولی را تغییر نمی‌دهد: فقط چیزهایی را که export شده‌اند دوباره export
// می‌کند تا esbuild آن‌ها را به یکِ فایلِ .mjs بدونِ DOM تبدیل کند.
import * as I from "../../frontend/src/features/technical/lib/indicators";
import { pineStd, MABNA_TEMPLATES, STDEV_SAMPLE } from "../../frontend/src/features/technical/lib/mabnaIndicators";

export { I, pineStd, MABNA_TEMPLATES, STDEV_SAMPLE };
