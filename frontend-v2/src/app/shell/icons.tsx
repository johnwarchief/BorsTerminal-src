export const PATHS: Record<string, string> = {
  grid: 'M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z',
  pulse: 'M3 12h4l2-6 3 12 2-6h5',
  chart: 'M4 19V5M4 19h16M7 15l4-4 3 2 4-6',
  file: 'M14 3H6v18h12V8zM14 3v5h5M8 13h8M8 17h5',
  eye: 'M2.5 12S6 6 12 6s9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6zM12 9.4a2.6 2.6 0 1 0 0 5.2 2.6 2.6 0 0 0 0-5.2z',
  pie: 'M12 3a9 9 0 1 0 9 9h-9zM15 3.5A9 9 0 0 1 20.5 9H15z',
  tree: 'M12 3v5M6 21v-4h12v4M12 8v5M6 17v-2h12v2',
  compass: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM15.5 8.5l-2 5-5 2 2-5z',
  flask: 'M9 3h6M10 3v5l-5 9a2 2 0 0 0 1.8 3h10.4a2 2 0 0 0 1.8-3l-5-9V3',
  bell: 'M18 9a6 6 0 1 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4',
  bolt: 'M13 2L4 14h7l-1 8 9-12h-7z',
  funnel: 'M3 5h18l-7 8v6l-4-2v-4z',
  menu: 'M4 7h16M4 12h16M4 17h16',
};

export function Icon({ name, size = 16 }: { name: string; size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d={PATHS[name] ?? PATHS.grid} />
    </svg>
  );
}
