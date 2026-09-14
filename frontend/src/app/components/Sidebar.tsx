import { NavLink } from 'react-router';

const NAV_ITEMS = [
  { to: '/market', label: 'تابلو بازار', end: false },
  { to: '/fundamental', label: 'تحلیل بنیادی', end: false },
  { to: '/technical', label: 'تحلیل تکنیکال', end: false },
  { to: '/portfolio', label: 'مدیریت پرتفوی', end: false },
  { to: '/master', label: 'ایجنت ارشد', end: false },
];

export function Sidebar() {
  return (
    <aside className="glass-panel sticky top-0 flex h-screen w-60 shrink-0 flex-col gap-6 overflow-y-auto rounded-none border-y-0 border-r-0 p-5">
      <div className="flex items-center gap-3">
        <div className="neon-edge-cyan flex h-10 w-10 items-center justify-center rounded-[10px] bg-gradient-to-br from-neon-cyan to-blue-600 text-lg font-black text-black">
          ب
        </div>
        <div>
          <span className="block text-sm font-bold text-text-primary">ترمینال بورس</span>
          <span className="block text-[10px] tracking-wide text-text-muted">CYBER TERMINAL v1</span>
        </div>
      </div>
      <nav className="flex flex-col gap-1.5">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `group relative overflow-hidden rounded-lg border border-transparent px-3 py-2.5 text-right text-sm font-semibold transition-all duration-200 ${
                isActive
                  ? 'border-[var(--hairline)] bg-accent-blue/12 text-accent-blue shadow-[inset_0_0_12px_rgba(56,189,248,0.12)]'
                  : 'text-text-secondary hover:bg-bg-card/60 hover:text-accent-blue'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <span
                  className={`absolute bottom-1.5 right-0 top-1.5 w-[2px] rounded-full bg-neon-cyan transition-opacity duration-200 ${
                    isActive ? 'opacity-100 shadow-[0_0_8px_var(--neon-cyan)]' : 'opacity-0'
                  }`}
                />
                {item.label}
              </>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto rounded-xl border border-[var(--hairline)] bg-bg-card/40 p-3 text-[10px] leading-5 text-text-muted">
        میانبر سریع: <kbd className="num rounded border border-border-c px-1">Ctrl</kbd> +
        <kbd className="num mr-1 rounded border border-border-c px-1">K</kbd>
        <span className="block">جستجوی نماد و پرش بین نماها</span>
      </div>
    </aside>
  );
}
