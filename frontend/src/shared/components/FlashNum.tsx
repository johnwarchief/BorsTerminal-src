// shared/components/FlashNum.tsx -- فلاش لطیف سلول هنگام تغییر مقدار
// انیمیشن با key جدید از سر گرفته می شود؛ مقدار اولیه فلاش نمی گیرد.
import { useEffect, useRef, useState } from 'react';

export function FlashNum({
  value,
  render,
  className = '',
}: {
  value: number | null | undefined;
  render: (v: number | null | undefined) => string;
  className?: string;
}) {
  const prev = useRef(value);
  const [flash, setFlash] = useState<{ dir: 'up' | 'down'; n: number } | null>(null);

  useEffect(() => {
    const before = prev.current;
    if (before !== value && before != null && value != null) {
      setFlash((f) => ({ dir: value > before ? 'up' : 'down', n: (f?.n ?? 0) + 1 }));
    }
    prev.current = value;
  }, [value]);

  return (
    <span
      key={flash ? flash.n : 'static'}
      className={`num inline-block rounded px-1 ${flash ? (flash.dir === 'up' ? 'flash-up' : 'flash-down') : ''} ${className}`}
    >
      {render(value)}
    </span>
  );
}
