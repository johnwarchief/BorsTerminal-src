import * as React from 'react';
import { cn } from '@shared/lib/cn';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'secondary' | 'outline' | 'ghost' | 'destructive' | 'cyan' | 'success' | 'link';
  size?: 'default' | 'sm' | 'xs' | 'lg' | 'icon';
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'default', type = 'button', disabled, children, ...props }, ref) => {
    const variantStyles = {
      default:
        'bg-accent-blue text-on-accent hover:bg-accent-blue/90 active:scale-[0.98] shadow-xs font-bold border border-transparent',
      secondary:
        'bg-bg-card/80 text-text-primary hover:bg-bg-card hover:text-accent-blue active:scale-[0.98] border border-border-c',
      outline:
        'border border-border-c bg-transparent text-text-primary hover:border-border-accent hover:text-accent-blue hover:bg-bg-card/40 active:scale-[0.98]',
      ghost:
        'bg-transparent text-text-secondary hover:bg-bg-card/60 hover:text-text-primary active:scale-[0.98] border border-transparent',
      destructive:
        'bg-accent-red/15 text-accent-red border border-accent-red/30 hover:bg-accent-red/25 hover:border-accent-red/50 active:scale-[0.98] font-bold',
      cyan:
        'neon-edge-cyan bg-gradient-to-r from-neon-cyan to-accent-blue text-black font-black hover:opacity-95 active:scale-[0.98] border border-transparent',
      success:
        'bg-accent-green/15 text-accent-green border border-accent-green/30 hover:bg-accent-green/25 active:scale-[0.98] font-bold',
      link:
        'text-accent-blue underline-offset-4 hover:underline p-0 h-auto border-none bg-transparent',
    }[variant];

    const sizeStyles = {
      default: 'h-8 px-3 py-1.5 text-xs rounded-lg',
      sm: 'h-7 px-2.5 py-1 text-2xs rounded-md',
      xs: 'h-6 px-2 py-0.5 text-3xs rounded-md',
      lg: 'h-9 px-4 py-2 text-sm rounded-lg',
      icon: 'h-8 w-8 p-0 rounded-lg flex items-center justify-center shrink-0',
    }[size];

    return (
      <button
        ref={ref}
        type={type}
        disabled={disabled}
        className={cn(
          'inline-flex items-center justify-center gap-1.5 font-medium transition-all duration-150 select-none outline-none',
          'focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1',
          'disabled:pointer-events-none disabled:opacity-40 disabled:cursor-not-allowed',
          variantStyles,
          sizeStyles,
          className,
        )}
        {...props}
      >
        {children}
      </button>
    );
  },
);
Button.displayName = 'Button';

export interface IconButtonProps extends ButtonProps {
  'aria-label': string;
}

export const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ size = 'icon', variant = 'ghost', className, ...props }, ref) => {
    return <Button ref={ref} size={size} variant={variant} className={cn('p-1', className)} {...props} />;
  },
);
IconButton.displayName = 'IconButton';
