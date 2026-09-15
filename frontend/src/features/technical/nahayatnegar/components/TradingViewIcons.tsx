import React from 'react';

export interface IconProps {
  size?: number;
  className?: string;
  color?: string;
}

// ==========================================
// نوار بالا (Top Toolbar)
// ==========================================

export const IconCandles: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.3" className={className}>
    <rect x="4" y="5" width="3" height="8" rx="0.5" fill="#089981" stroke="#089981" />
    <line x1="5.5" y1="2" x2="5.5" y2="5" stroke="#089981" />
    <line x1="5.5" y1="13" x2="5.5" y2="16" stroke="#089981" />
    <rect x="11" y="4" width="3" height="7" rx="0.5" fill="#f23645" stroke="#f23645" />
    <line x1="12.5" y1="1" x2="12.5" y2="4" stroke="#f23645" />
    <line x1="12.5" y1="11" x2="12.5" y2="15" stroke="#f23645" />
  </svg>
);

export const IconHollowCandles: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.3" className={className}>
    <rect x="4" y="5" width="3" height="8" rx="0.5" stroke="#089981" fill="none" />
    <line x1="5.5" y1="2" x2="5.5" y2="5" stroke="#089981" />
    <line x1="5.5" y1="13" x2="5.5" y2="16" stroke="#089981" />
    <rect x="11" y="4" width="3" height="7" rx="0.5" stroke="#f23645" fill="none" />
    <line x1="12.5" y1="1" x2="12.5" y2="4" stroke="#f23645" />
    <line x1="12.5" y1="11" x2="12.5" y2="15" stroke="#f23645" />
  </svg>
);

export const IconBars: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <line x1="5" y1="3" x2="5" y2="15" />
    <line x1="2" y1="9" x2="5" y2="9" />
    <line x1="5" y1="6" x2="8" y2="6" />
    <line x1="13" y1="3" x2="13" y2="15" />
    <line x1="10" y1="6" x2="13" y2="6" />
    <line x1="13" y1="11" x2="16" y2="11" />
  </svg>
);

export const IconLine: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <polyline points="2,14 6,8 10,11 16,4" />
  </svg>
);

export const IconArea: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.4" className={className}>
    <path d="M2 15L6 9L10 12L16 5V15H2Z" fill="rgba(41,98,255,0.25)" stroke="#2962ff" />
  </svg>
);

export const IconHeikinAshi: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.3" className={className}>
    <rect x="5" y="4" width="3" height="9" fill="#089981" stroke="#089981" rx="0.5" />
    <line x1="6.5" y1="2" x2="6.5" y2="16" stroke="#089981" />
    <rect x="11" y="6" width="3" height="7" fill="#f23645" stroke="#f23645" rx="0.5" />
    <line x1="12.5" y1="3" x2="12.5" y2="15" stroke="#f23645" />
  </svg>
);

export const IconAdjustments: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.4" className={className}>
    <line x1="9" y1="2" x2="9" y2="16" />
    <line x1="3" y1="5" x2="15" y2="5" />
    <path d="M3 5L1 10H5L3 5Z" />
    <path d="M15 5L13 10H17L15 5Z" />
    <line x1="6" y1="16" x2="12" y2="16" />
  </svg>
);

export const IconFx: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.6" className={className}>
    <text x="2" y="13" fontSize="13" fontWeight="bold" fill={color} stroke="none" fontFamily="serif">fx</text>
  </svg>
);

export const IconCompare: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.4" className={className}>
    <circle cx="7" cy="9" r="4.5" />
    <circle cx="11" cy="9" r="4.5" strokeDasharray="2 2" />
  </svg>
);

export const IconTemplates: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.4" className={className}>
    <rect x="3" y="3" width="5" height="5" rx="1" />
    <rect x="10" y="3" width="5" height="5" rx="1" />
    <rect x="3" y="10" width="5" height="5" rx="1" />
    <rect x="10" y="10" width="5" height="5" rx="1" />
  </svg>
);

export const IconSave: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.4" className={className}>
    <path d="M3 3H13L15 5V15H3V3Z" />
    <rect x="6" y="3" width="6" height="4" />
    <rect x="5" y="10" width="8" height="5" />
  </svg>
);

export const IconUndo: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <path d="M4 7h7a4 4 0 0 1 0 8H8" />
    <polyline points="7,4 4,7 7,10" />
  </svg>
);

export const IconRedo: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <path d="M14 7H7a4 4 0 0 0 0 8h3" />
    <polyline points="11,4 14,7 11,10" />
  </svg>
);

export const IconSettings: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.4" className={className}>
    <circle cx="9" cy="9" r="2.5" />
    <path d="M9 1v2m0 12v2M1 9h2m12 0h2m-2.6-5.4l-1.4 1.4M5 13l-1.4 1.4m0-9.8L5 6m8 8l1.4 1.4" />
  </svg>
);

export const IconCamera: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.4" className={className}>
    <path d="M2 6a2 2 0 0 1 2-2h2l1.5-1.5h3L12 4h2a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6z" />
    <circle cx="9" cy="10" r="3" />
  </svg>
);

export const IconFullscreen: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <polyline points="2,6 2,2 6,2" />
    <polyline points="12,2 16,2 16,6" />
    <polyline points="16,12 16,16 12,16" />
    <polyline points="6,16 2,16 2,12" />
  </svg>
);

export const IconExitFullscreen: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <polyline points="6,2 6,6 2,6" />
    <polyline points="12,2 12,6 16,6" />
    <polyline points="16,12 12,12 12,16" />
    <polyline points="2,12 6,12 6,16" />
  </svg>
);

export const IconSearch: React.FC<IconProps> = ({ size = 16, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <circle cx="8" cy="8" r="5" />
    <line x1="12" y1="12" x2="16" y2="16" />
  </svg>
);

export const IconChevronDown: React.FC<IconProps> = ({ size = 10, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 10 10" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <path d="M2 3.5l3 3 3-3" />
  </svg>
);

export const IconCheck: React.FC<IconProps> = ({ size = 14, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.8" className={className}>
    <polyline points="3,9 7,13 15,5" />
  </svg>
);

export const IconClose: React.FC<IconProps> = ({ size = 14, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.8" className={className}>
    <line x1="4" y1="4" x2="14" y2="14" />
    <line x1="14" y1="4" x2="4" y2="14" />
  </svg>
);

export const IconFts: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <polygon points="10,1 3,10 9,10 8,17 15,8 9,8" fill="rgba(255,171,0,0.2)" stroke="#ffab00" />
  </svg>
);

// ==========================================
// نوار ابزار رسم چپ (Drawing Toolbar)
// ==========================================

export const IconCrosshair: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <circle cx="9" cy="9" r="2" fill={color} />
    <line x1="9" y1="1" x2="9" y2="5" />
    <line x1="9" y1="13" x2="9" y2="17" />
    <line x1="1" y1="9" x2="5" y2="9" />
    <line x1="13" y1="9" x2="17" y2="9" />
  </svg>
);

export const IconDot: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <circle cx="9" cy="9" r="3" fill={color} />
  </svg>
);

export const IconArrowCursor: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <path d="M3 3l5 12 2-5 5-2L3 3z" fill={color} />
  </svg>
);

export const IconEraser: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <path d="M5 13l-3-3 8-8 5 5-8 8H5z" />
    <line x1="10" y1="15" x2="16" y2="15" />
  </svg>
);

export const IconTrendLine: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <line x1="3" y1="15" x2="15" y2="3" />
    <circle cx="3" cy="15" r="2" fill={color} />
    <circle cx="15" cy="3" r="2" fill={color} />
  </svg>
);

export const IconRay: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <line x1="3" y1="14" x2="15" y2="4" />
    <circle cx="3" cy="14" r="2" fill={color} />
    <polyline points="10,4 15,4 15,9" />
  </svg>
);

export const IconInfoLine: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <line x1="3" y1="15" x2="15" y2="3" />
    <circle cx="9" cy="9" r="1.5" fill={color} />
  </svg>
);

export const IconHorizontalLine: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <line x1="1" y1="9" x2="17" y2="9" />
    <circle cx="9" cy="9" r="2" fill={color} />
  </svg>
);

export const IconVerticalLine: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <line x1="9" y1="1" x2="9" y2="17" />
    <circle cx="9" cy="9" r="2" fill={color} />
  </svg>
);

export const IconParallelChannel: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.3" className={className}>
    <line x1="2" y1="11" x2="13" y2="2" />
    <line x1="5" y1="16" x2="16" y2="7" />
    <line x1="3.5" y1="13.5" x2="14.5" y2="4.5" strokeDasharray="2 2" />
  </svg>
);

export const IconFibRetracement: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.3" className={className}>
    <line x1="2" y1="3" x2="16" y2="3" />
    <line x1="2" y1="7" x2="16" y2="7" />
    <line x1="2" y1="11" x2="16" y2="11" />
    <line x1="2" y1="15" x2="16" y2="15" />
    <line x1="3" y1="15" x2="15" y2="3" strokeDasharray="2 2" stroke={color} />
  </svg>
);

export const IconPitchfork: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.3" className={className}>
    <line x1="2" y1="9" x2="8" y2="9" />
    <line x1="8" y1="4" x2="8" y2="14" />
    <line x1="8" y1="4" x2="16" y2="4" />
    <line x1="8" y1="9" x2="16" y2="9" />
    <line x1="8" y1="14" x2="16" y2="14" />
  </svg>
);

export const IconRectangle: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <rect x="3" y="4" width="12" height="10" rx="1" />
  </svg>
);

export const IconCircle: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <circle cx="9" cy="9" r="6" />
  </svg>
);

export const IconBrush: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <path d="M14 2c-1.5 0-3 1.5-4 3L4 11c-.5.7-.7 1.5-.7 2.3 0 1.5 1.2 2.7 2.7 2.7.8 0 1.6-.2 2.3-.7l6-6c1.5-1 3-2.5 3-4 0-.7-.6-1.3-1.3-1.3z" />
  </svg>
);

export const IconText: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.8" className={className}>
    <line x1="3" y1="4" x2="15" y2="4" />
    <line x1="9" y1="4" x2="9" y2="15" />
    <line x1="6" y1="15" x2="12" y2="15" />
  </svg>
);

export const IconPriceLabel: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.4" className={className}>
    <path d="M3 9L9 3H15V9L9 15L3 9Z" />
    <circle cx="12" cy="6" r="1.5" fill={color} />
  </svg>
);

export const IconPatterns: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.4" className={className}>
    <polyline points="2,14 6,5 10,12 14,4 16,14" />
    <circle cx="2" cy="14" r="1" fill={color} />
    <circle cx="6" cy="5" r="1" fill={color} />
    <circle cx="10" cy="12" r="1" fill={color} />
    <circle cx="14" cy="4" r="1" fill={color} />
  </svg>
);

export const IconLongPosition: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.3" className={className}>
    <rect x="3" y="3" width="12" height="6" fill="rgba(8,153,129,0.3)" stroke="#089981" />
    <rect x="3" y="9" width="12" height="6" fill="rgba(242,54,69,0.3)" stroke="#f23645" />
    <line x1="3" y1="9" x2="15" y2="9" stroke="#fff" strokeWidth="1.5" />
  </svg>
);

export const IconShortPosition: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.3" className={className}>
    <rect x="3" y="3" width="12" height="6" fill="rgba(242,54,69,0.3)" stroke="#f23645" />
    <rect x="3" y="9" width="12" height="6" fill="rgba(8,153,129,0.3)" stroke="#089981" />
    <line x1="3" y1="9" x2="15" y2="9" stroke="#fff" strokeWidth="1.5" />
  </svg>
);

export const IconRuler: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.4" className={className}>
    <path d="M14.5 3.5l-11 11 2 2 11-11-2-2z" />
    <line x1="11" y1="6.5" x2="13" y2="8.5" />
    <line x1="8.5" y1="9" x2="10.5" y2="11" />
    <line x1="6" y1="11.5" x2="8" y2="13.5" />
  </svg>
);

export const IconMagnet: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <path d="M4 3v5a5 5 0 0 0 10 0V3" />
    <line x1="4" y1="5" x2="7" y2="5" />
    <line x1="11" y1="5" x2="14" y2="5" />
  </svg>
);

export const IconLock: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.4" className={className}>
    <rect x="4" y="8" width="10" height="8" rx="1.5" />
    <path d="M6 8V5a3 3 0 0 1 6 0v3" />
  </svg>
);

export const IconUnlock: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.4" className={className}>
    <rect x="4" y="8" width="10" height="8" rx="1.5" />
    <path d="M6 8V5a3 3 0 0 1 6 0" />
  </svg>
);

export const IconEye: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.4" className={className}>
    <path d="M1 9s3-6 8-6 8 6 8 6-3 6-8 6-8-6-8-6z" />
    <circle cx="9" cy="9" r="3" />
  </svg>
);

export const IconEyeOff: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.4" className={className}>
    <path d="M1 9s3-6 8-6 8 6 8 6-3 6-8 6-8-6-8-6z" />
    <line x1="2" y1="2" x2="16" y2="16" stroke="#f23645" strokeWidth="1.6" />
  </svg>
);

export const IconTrash: React.FC<IconProps> = ({ size = 18, className = '', color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.4" className={className}>
    <polyline points="3,5 15,5" />
    <line x1="7" y1="8" x2="7" y2="13" />
    <line x1="11" y1="8" x2="11" y2="13" />
    <path d="M5 5l1 10a1.5 1.5 0 0 0 1.5 1.5h3a1.5 1.5 0 0 0 1.5-1.5L13 5" />
    <path d="M7 5V3a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v2" />
  </svg>
);

// ==========================================
// نشانگرهای ستاپ‌های FTS (FTS Setup Markers)
// ==========================================

export const IconJet: React.FC<IconProps> = ({ size = 18, className = '', color = '#2962ff' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <path d="M9 2L12 8L17 9L12 11L11 16L9 13L7 16L6 11L1 9L6 8L9 2Z" fill="rgba(41,98,255,0.2)" />
  </svg>
);

export const IconPullback: React.FC<IconProps> = ({ size = 18, className = '', color = '#089981' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <path d="M3 13L8 8L11 11L16 4" />
    <polyline points="12,4 16,4 16,8" />
  </svg>
);

export const IconChoch: React.FC<IconProps> = ({ size = 18, className = '', color = '#ff9800' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.5" className={className}>
    <polyline points="2,14 6,14 11,4 16,4" />
    <polyline points="13,2 16,4 13,6" />
  </svg>
);

export const IconPointTarget: React.FC<IconProps> = ({ size = 18, className = '', color = '#e91e63' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.4" className={className}>
    <circle cx="9" cy="9" r="6" />
    <circle cx="9" cy="9" r="2" fill={color} />
    <line x1="9" y1="1" x2="9" y2="4" />
    <line x1="9" y1="14" x2="9" y2="17" />
    <line x1="1" y1="9" x2="4" y2="9" />
    <line x1="14" y1="9" x2="17" y2="9" />
  </svg>
);

export const IconDoubleBottom: React.FC<IconProps> = ({ size = 18, className = '', color = '#00bcd4' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke={color} strokeWidth="1.6" className={className}>
    <polyline points="2,4 6,15 9,8 12,15 16,4" />
  </svg>
);
