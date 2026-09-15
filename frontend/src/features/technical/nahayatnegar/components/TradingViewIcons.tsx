import React from 'react';

export const IconCrosshair: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
    <circle cx="9" cy="9" r="2" fill="currentColor" />
    <line x1="9" y1="1" x2="9" y2="5" />
    <line x1="9" y1="13" x2="9" y2="17" />
    <line x1="1" y1="9" x2="5" y2="9" />
    <line x1="13" y1="9" x2="17" y2="9" />
  </svg>
);

export const IconTrendLine: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
    <line x1="3" y1="15" x2="15" y2="3" />
    <circle cx="3" cy="15" r="2" fill="currentColor" />
    <circle cx="15" cy="3" r="2" fill="currentColor" />
  </svg>
);

export const IconRay: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
    <line x1="3" y1="14" x2="15" y2="4" />
    <circle cx="3" cy="14" r="2" fill="currentColor" />
    <polyline points="10,4 15,4 15,9" />
  </svg>
);

export const IconHorizontalLine: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
    <line x1="1" y1="9" x2="17" y2="9" />
    <circle cx="9" cy="9" r="2" fill="currentColor" />
  </svg>
);

export const IconVerticalLine: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
    <line x1="9" y1="1" x2="9" y2="17" />
    <circle cx="9" cy="9" r="2" fill="currentColor" />
  </svg>
);

export const IconParallelChannel: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.3" className={className}>
    <line x1="2" y1="11" x2="13" y2="2" />
    <line x1="5" y1="16" x2="16" y2="7" />
    <line x1="3.5" y1="13.5" x2="14.5" y2="4.5" strokeDasharray="2 2" />
  </svg>
);

export const IconFibRetracement: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.2" className={className}>
    <line x1="2" y1="3" x2="16" y2="3" />
    <line x1="2" y1="7" x2="16" y2="7" />
    <line x1="2" y1="11" x2="16" y2="11" />
    <line x1="2" y1="15" x2="16" y2="15" />
    <line x1="3" y1="15" x2="15" y2="3" strokeDasharray="2 2" stroke="currentColor" opacity="0.6" />
  </svg>
);

export const IconPitchfork: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" className={className}>
    <line x1="3" y1="15" x2="9" y2="9" />
    <line x1="9" y1="9" x2="16" y2="3" />
    <line x1="9" y1="9" x2="16" y2="9" />
    <line x1="9" y1="9" x2="16" y2="15" />
    <circle cx="3" cy="15" r="1.5" fill="currentColor" />
  </svg>
);

export const IconBrush: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.3" className={className}>
    <path d="M12 2l4 4-6 6H6v-4l6-6z" />
    <path d="M6 12c-2 0-4 1-4 3 0 1 1 1 2 1 3 0 4-2 4-4H6z" fill="currentColor" />
  </svg>
);

export const IconRectangle: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
    <rect x="2" y="4" width="14" height="10" rx="1.5" />
  </svg>
);

export const IconCircle: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
    <circle cx="9" cy="9" r="6.5" />
  </svg>
);

export const IconText: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="currentColor" className={className}>
    <path d="M3 4h12v3h-2V6H10v8h1.5v2h-5v-2H8V6H5v1H3V4z" />
  </svg>
);

export const IconRuler: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.3" className={className}>
    <rect x="2" y="5" width="14" height="8" rx="1" transform="rotate(-30 9 9)" />
    <line x1="5" y1="6" x2="6.5" y2="9" />
    <line x1="8" y1="4.5" x2="9.5" y2="7.5" />
    <line x1="11" y1="3" x2="12.5" y2="6" />
  </svg>
);

export const IconMagnet: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" className={className}>
    <path d="M4 3v6a5 5 0 0 0 10 0V3h-3v6a2 2 0 0 1-4 0V3H4z" />
    <rect x="4" y="2" width="3" height="3" fill="currentColor" />
    <rect x="11" y="2" width="3" height="3" fill="currentColor" />
  </svg>
);

export const IconLock: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" className={className}>
    <rect x="4" y="8" width="10" height="8" rx="1.5" />
    <path d="M6 8V5a3 3 0 0 1 6 0v3" />
  </svg>
);

export const IconTrash: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" className={className}>
    <path d="M3 5h12M6 5V3h6v2M7 8v6M11 8v6M5 5l1 10h6l1-10" />
  </svg>
);

export const IconCandles: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" className={className}>
    <line x1="5.5" y1="2" x2="5.5" y2="16" stroke="#089981" strokeWidth="1.2" />
    <rect x="3.5" y="5" width="4" height="7" fill="#089981" rx="0.5" />
    <line x1="12.5" y1="3" x2="12.5" y2="15" stroke="#f23645" strokeWidth="1.2" />
    <rect x="10.5" y="6" width="4" height="6" fill="#f23645" rx="0.5" />
  </svg>
);

export const IconFx: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="currentColor" className={className}>
    <text x="2" y="14" fontFamily="Georgia, serif" fontSize="13" fontStyle="italic" fontWeight="bold">fx</text>
  </svg>
);

export const IconSettings: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" className={className}>
    <circle cx="9" cy="9" r="2.5" />
    <path d="M9 1.5v2M9 14.5v2M1.5 9h2M14.5 9h2M3.7 3.7l1.4 1.4M12.9 12.9l1.4 1.4M3.7 14.3l1.4-1.4M12.9 5.1l1.4-1.4" />
  </svg>
);

export const IconCamera: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" className={className}>
    <path d="M2 6a1 1 0 0 1 1-1h2.5l1.5-2h4l1.5 2H15a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V6z" />
    <circle cx="9" cy="10" r="3" />
  </svg>
);

export const IconFullscreen: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
    <path d="M2 6V2h4M16 6V2h-4M2 12v4h4M16 12v4h-4" />
  </svg>
);

export const IconUndo: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" className={className}>
    <path d="M4 7h7a4 4 0 0 1 4 4v1" />
    <polyline points="7,4 4,7 7,10" />
  </svg>
);

export const IconRedo: React.FC<{ size?: number; className?: string }> = ({ size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" className={className}>
    <path d="M14 7H7a4 4 0 0 0-4 4v1" />
    <polyline points="11,4 14,7 11,10" />
  </svg>
);

export const IconChevronDown: React.FC<{ size?: number; className?: string }> = ({ size = 12, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 12 12" fill="currentColor" className={className}>
    <path d="M3 4.5l3 3 3-3" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
  </svg>
);
