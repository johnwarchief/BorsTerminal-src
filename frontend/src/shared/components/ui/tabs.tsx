import * as React from 'react';
import { cn } from '@shared/lib/cn';

type TabsIdPair = { tab: string; panel: string };

interface TabsContextValue {
  value: string;
  onValueChange: (val: string) => void;
  /** شناسۀِ جفتِ `tab ↔ tabpanel`. ازِ `useId()` ساخته می‌شود، نه ازِ خودِ `value`,
   *  چون یکِ صفحه دوِ گروهِ تب باِ همانِ مقدارها دارد (سوییچرِ نما + جدولِ سبد). */
  ids: (val: string) => TabsIdPair;
}

const TabsContext = React.createContext<TabsContextValue | null>(null);

export interface TabsProps extends React.HTMLAttributes<HTMLDivElement> {
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
}

export function Tabs({ value: controlledValue, defaultValue, onValueChange, className, children, ...props }: TabsProps) {
  const [uncontrolledValue, setUncontrolledValue] = React.useState(defaultValue ?? '');
  const isControlled = controlledValue !== undefined;
  const activeValue = isControlled ? controlledValue : uncontrolledValue;

  const handleValueChange = React.useCallback(
    (newVal: string) => {
      if (!isControlled) {
        setUncontrolledValue(newVal);
      }
      onValueChange?.(newVal);
    },
    [isControlled, onValueChange],
  );

  const uid = React.useId();
  const ids = React.useCallback(
    (val: string): TabsIdPair => ({ tab: `${uid}-tab-${val}`, panel: `${uid}-panel-${val}` }),
    [uid],
  );

  return (
    <TabsContext.Provider value={{ value: activeValue, onValueChange: handleValueChange, ids }}>
      <div className={cn('flex flex-col gap-2', className)} {...props}>
        {children}
      </div>
    </TabsContext.Provider>
  );
}

export const TabsList = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, onKeyDown, ...props }, ref) => (
    <div
      ref={ref}
      onKeyDown={(e) => {
        onKeyDown?.(e);
        if (e.defaultPrevented) return;
        const tabs = Array.from(
          e.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]:not([disabled])'),
        );
        if (!tabs.length) return;
        const at = tabs.indexOf(document.activeElement as HTMLButtonElement);
        if (at < 0) return;
        // اینِ اپ درِ `index.html` یکسره `dir=rtl` است، پس پیکانِ چپ «بعدی» وِ راست
        // «قبلی» -- همانِ نگاشتِ نوارِ تبِ فضایِ کاری (فاز C)، نه نگاشتِ APGِ چپ‌به‌راست.
        const step = e.key === 'ArrowLeft' ? 1 : e.key === 'ArrowRight' ? -1 : undefined;
        let next = -1;
        if (step !== undefined) next = (at + step + tabs.length) % tabs.length;
        else if (e.key === 'Home') next = 0;
        else if (e.key === 'End') next = tabs.length - 1;
        else return;
        e.preventDefault();
        const el = tabs[next];
        el.focus();
        // فعال‌سازیِ خودکار (automatic activation): برایِ سوییچرِ نمایِ یک‌صفحه‌ای،
        // APG همین را می‌خواهد؛ کاربر باِ پیکان *می‌بیند*، نه فقط فوکوس.
        el.click();
      }}
      role="tablist"
      className={cn(
        'inline-flex h-8 items-center justify-start rounded-lg bg-bg-card/80 p-0.5 border border-border-c/70 text-text-secondary select-none',
        className,
      )}
      {...props}
    />
  ),
);
TabsList.displayName = 'TabsList';

export interface TabsTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  value: string;
}

export const TabsTrigger = React.forwardRef<HTMLButtonElement, TabsTriggerProps>(
  ({ className, value, children, disabled, ...props }, ref) => {
    const context = React.useContext(TabsContext);
    const isSelected = context?.value === value;
    const ids = context?.ids(value);

    return (
      <button
        ref={ref}
        type="button"
        role="tab"
        id={ids?.tab}
        aria-controls={ids?.panel}
        // roving tabindex: تنها تبِ فعال درِ ترتیبِ Tab می‌ماند؛ کاربر یک‌بار واردِ
        // گروهِ تب می‌شود وِ بعد باِ پیکان جابه‌جا می‌شود (الگویِ APG).
        tabIndex={isSelected ? 0 : -1}
        aria-selected={isSelected}
        disabled={disabled}
        onClick={() => context?.onValueChange(value)}
        className={cn(
          'inline-flex items-center justify-center whitespace-nowrap rounded-md px-2.5 py-1 text-2xs font-bold ring-offset-background transition-all duration-150 outline-none',
          'focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1',
          'disabled:pointer-events-none disabled:opacity-50',
          isSelected
            ? 'bg-accent-blue/15 text-accent-blue shadow-2xs border border-accent-blue/30 font-black'
            : 'text-text-secondary hover:text-text-primary hover:bg-bg-primary/40 border border-transparent',
          className,
        )}
        {...props}
      >
        {children}
      </button>
    );
  },
);
TabsTrigger.displayName = 'TabsTrigger';

export interface TabsContentProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string;
}

export const TabsContent = React.forwardRef<HTMLDivElement, TabsContentProps>(
  ({ className, value, children, ...props }, ref) => {
    const context = React.useContext(TabsContext);
    const isSelected = context?.value === value;

    if (!isSelected) return null;

    return (
      <div
        ref={ref}
        role="tabpanel"
        id={context?.ids(value).panel}
        aria-labelledby={context?.ids(value).tab}
        tabIndex={0}
        className={cn('outline-none panel-in focus-visible:ring-2 focus-visible:ring-ring', className)}
        {...props}
      >
        {children}
      </div>
    );
  },
);
TabsContent.displayName = 'TabsContent';
