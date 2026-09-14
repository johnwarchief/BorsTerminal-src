// shared/components/Badge.tsx -- نشان وضعیت
type Tone = 'green' | 'red' | 'yellow' | 'blue' | 'gray' | 'orange';

const TONES: Record<Tone, string> = {
  green: 'bg-accent-green/15 text-accent-green border-accent-green/30',
  red: 'bg-accent-red/15 text-accent-red border-accent-red/30',
  yellow: 'bg-accent-yellow/15 text-accent-yellow border-accent-yellow/30',
  blue: 'bg-accent-blue/15 text-accent-blue border-accent-blue/30',
  gray: 'bg-bg-card text-text-secondary border-border-c',
  orange: 'bg-accent-susp-bg text-accent-susp border-accent-susp/30',
};

export function Badge({ tone = 'gray', children }: { tone?: Tone; children: React.ReactNode }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}
