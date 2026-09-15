// shared/lib/breakpoints.ts -- نقاط شکست واکنشی (فاز ۲)
export const BREAKPOINT_XL = 1280;
export const BREAKPOINT_LG = 1024;

/** نمایشگر کوچک: زیر ۱۲۸۰px */
export const MEDIA_SMALL = `(max-width: ${BREAKPOINT_XL - 0.02}px)`;
/** نمایشگر فشرده: زیر ۱۰۲۴px */
export const MEDIA_COMPACT = `(max-width: ${BREAKPOINT_LG - 0.02}px)`;