// shared/lib/breakpoints.ts -- نقاط شکست واکنشی (فاز ۲)
export const BREAKPOINT_SM = 640; // موبایل بزرگ / حالت تلفن
export const BREAKPOINT_MD = 768; // تبلت و دسکتاپ ۷۶۸p
export const BREAKPOINT_LG = 1024; // لپ‌تاپ / دسکتاپ ۱۰۸۰p
export const BREAKPOINT_XL = 1280; // دسکتاپ متوسط
export const BREAKPOINT_2K = 1920; // ۲K / QHD
export const BREAKPOINT_3K = 2560; // ماقبل ۴K
export const BREAKPOINT_4K = 3840; // ۴K UHD

/** نمایشگر کوچک: زیر ۱۲۸۰px */
export const MEDIA_SMALL = `(max-width: ${BREAKPOINT_XL - 0.02}px)`;
/** نمایشگر فشرده: زیر ۱۰۲۴px */
export const MEDIA_COMPACT = `(max-width: ${BREAKPOINT_LG - 0.02}px)`;
/** نمایشگر موبایل/تبلت: زیر ۷۶۸px */
export const MEDIA_MOBILE = `(max-width: ${BREAKPOINT_MD - 0.02}px)`;
/** نمایشگر عریض: ۲K (۱۹۲۰px) و بالاتر */
export const MEDIA_WIDE = `(min-width: ${BREAKPOINT_2K}px)`;
/** نمایشگر فوق‌عریض: ۴K (۳۸۴۰px) و بالاتر */
export const MEDIA_ULTRA = `(min-width: ${BREAKPOINT_4K}px)`;