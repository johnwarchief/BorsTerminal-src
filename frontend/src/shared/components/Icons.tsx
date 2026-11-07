// shared/components/Icons.tsx -- آیکون های SVG درون خطی (بدون پکیج آیکون)
type IconProps = { className?: string; size?: number };

const SVG_PROPS = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
  focusable: false,
};

export function SunIcon({ className, size = 16 }: IconProps) {
  return (
    <svg {...SVG_PROPS} className={className} width={size} height={size}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M6.3 17.7l-1.4 1.4M19.1 4.9l-1.4 1.4" />
    </svg>
  );
}

export function MoonIcon({ className, size = 16 }: IconProps) {
  return (
    <svg {...SVG_PROPS} className={className} width={size} height={size}>
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
    </svg>
  );
}

export function SearchIcon({ className, size = 16 }: IconProps) {
  return (
    <svg {...SVG_PROPS} className={className} width={size} height={size}>
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}

export function ChevronIcon({ className, size = 16 }: IconProps) {
  return (
    <svg {...SVG_PROPS} className={className} width={size} height={size}>
      <path d="m15 6-6 6 6 6" />
    </svg>
  );
}

export function MarketIcon({ className, size = 16 }: IconProps) {
  return (
    <svg {...SVG_PROPS} className={className} width={size} height={size}>
      <path d="M3 3v18h18" />
      <path d="m7 14 3-3 3 3 5-6" />
    </svg>
  );
}

export function FundamentalIcon({ className, size = 16 }: IconProps) {
  return (
    <svg {...SVG_PROPS} className={className} width={size} height={size}>
      <path d="M6 2h9l5 5v15a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1Z" />
      <path d="M14 2v6h6M9 13h6M9 17h6" />
    </svg>
  );
}

export function TechnicalIcon({ className, size = 16 }: IconProps) {
  return (
    <svg {...SVG_PROPS} className={className} width={size} height={size}>
      <path d="M4 4v16M9 4v16M14 4v16M19 4v16" />
      <rect x="6.5" y="8" width="5" height="6" rx="1" />
      <rect x="11.5" y="6" width="5" height="8" rx="1" />
    </svg>
  );
}

export function PortfolioIcon({ className, size = 16 }: IconProps) {
  return (
    <svg {...SVG_PROPS} className={className} width={size} height={size}>
      <rect x="3" y="7" width="18" height="13" rx="2" />
      <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18" />
    </svg>
  );
}

export function MasterIcon({ className, size = 16 }: IconProps) {
  return (
    <svg {...SVG_PROPS} className={className} width={size} height={size}>
      <path d="M12 3l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9 6.8 19.1l1-5.8L3.5 9.2l5.9-.9L12 3Z" />
    </svg>
  );
}

export function TreeIcon({ className, size = 16 }: IconProps) {
  return (
    <svg {...SVG_PROPS} className={className} width={size} height={size}>
      <circle cx="18" cy="6" r="3" />
      <circle cx="6" cy="18" r="3" />
      <path d="M18 9a9 9 0 0 1-9 9H6" />
      <path d="M12 12a6 6 0 0 0 6 6" />
      <circle cx="18" cy="18" r="3" />
    </svg>
  );
}

/** نبض/خطِ وضعیت — برایِ مقصدِ «وضعیت بازار» درِ ناوبری */
export function StatusIcon({ className, size = 16 }: IconProps) {
  return (
    <svg {...SVG_PROPS} className={className} width={size} height={size}>
      <path d="M3 12h3.5l2-5 3 10 2.5-5H21" />
    </svg>
  );
}

/** رعدِ «سرخطی» — نشانۀِ ناوبریِ تبِّ سفارشِ سریع. هیچ شمارۀِ «پیشیِ صف» یا
 *  ادعایِ سرعتی درِ این SVG نیست؛ فقط شکل. */
export function BoltIcon({ className, size = 16 }: IconProps) {
  return (
    <svg {...SVG_PROPS} className={className} width={size} height={size}>
      <path d="M13 2 4 14h6l-1 8 9-12h-6z" />
    </svg>
  );
}

/** زنگولۀِ مرکزِ اعلان — فقط نشانۀِ ناوبری است؛ شمارۀِ ناخوانده درِ خودِ
 *  ناوبری وِژه می‌گیرد، نه درِ این SVG. */
export function BellIcon({ className, size = 16 }: IconProps) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.7 21a2 2 0 0 1-3.4 0" />
    </svg>
  );
}

export function ArrowUpLeftIcon({ className, size = 14 }: IconProps) {
  return (
    <svg {...SVG_PROPS} className={className} width={size} height={size}>
      <path d="M7 17V7h10" />
      <path d="M17 17 7 7" />
    </svg>
  );
}

export function ArrowDownLeftIcon({ className, size = 14 }: IconProps) {
  return (
    <svg {...SVG_PROPS} className={className} width={size} height={size}>
      <path d="M17 7 7 17" />
      <path d="M17 17H7V7" />
    </svg>
  );
}

export function XIcon({ className, size = 14 }: IconProps) {
  return (
    <svg {...SVG_PROPS} className={className} width={size} height={size}>
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

export function LoaderIcon({ className, size = 14 }: IconProps) {
  return (
    <svg {...SVG_PROPS} className={`animate-spin ${className ?? ''}`} width={size} height={size}>
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  );
}

// سه نشانۀِ خطِ جریانِ «سرخطی» (SarkhatiPipeline). تا پیش از این جایِ اینها
// یونیکدِ ✓ ✕ ? درِ متنِ فارسی می‌نشست — وزنِ قلمِ آن علامت‌ها باِ بقیۀِ آیکون‌ها
// یکی نیست و درِ فارسی جابه‌جا چاپ می‌شوند. اینجا همان viewBox/سروکِ ۲ است.
export function CheckIcon({ className, size = 14 }: IconProps) {
  return (
    <svg {...SVG_PROPS} className={className} width={size} height={size}>
      <path d="m5 13 4 4L19 7" />
    </svg>
  );
}

export function LockIcon({ className, size = 14 }: IconProps) {
  return (
    <svg {...SVG_PROPS} className={className} width={size} height={size}>
      <rect x="5" y="11" width="14" height="9" rx="2" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
    </svg>
  );
}

export function HelpIcon({ className, size = 14 }: IconProps) {
  return (
    <svg {...SVG_PROPS} className={className} width={size} height={size}>
      <path d="M9.2 9a2.9 2.9 0 1 1 4.2 2.6c-.9.5-1.4 1.1-1.4 2.1v.5" />
      <path d="M12 18.4h.01" />
    </svg>
  );
}


