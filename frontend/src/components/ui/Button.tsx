/* eslint-disable react-refresh/only-export-components -- variants/hooks are intentionally co-located with their component; this rule only affects dev-time Fast Refresh. */
import { forwardRef } from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/cn';
import { DotPulse } from './DotPulse';

/**
 * Button — §10.1. Variants primary/secondary/ghost/danger/link; sizes sm/md/lg
 * (heights 32/36/40, §5.3). `loading` renders <DotPulse/> inline and keeps the
 * label mounted (invisible) so the button never changes width.
 */
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-sm font-sans font-semibold ' +
    'transition-colors duration-micro ease-entry select-none ' +
    'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ' +
    'disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none',
  {
    variants: {
      variant: {
        primary: 'bg-brand text-brand-fg hover:bg-brand-hover shadow-e1',
        secondary: 'bg-surface text-ink border border-strong hover:bg-surface-sunken',
        ghost: 'bg-transparent text-text-secondary hover:bg-surface-sunken hover:text-ink',
        // text-canvas inverts with the theme: light text on the dark-red light-mode
        // fill, dark text on the light-red dark-mode fill (keeps AA contrast).
        danger: 'bg-danger-fg text-canvas hover:opacity-90',
        link: 'bg-transparent text-brand underline-offset-4 hover:underline px-0 h-auto',
      },
      size: {
        sm: 'h-8 px-3 text-body-sm', // 32px tall, 12px pad
        md: 'h-9 px-4 text-body', // 36px tall, 16px pad
        lg: 'h-10 px-5 text-body-lg', // 40px tall, 20px pad
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
  /** Optional icon element (16 or 20px). Rendered before the label. */
  icon?: React.ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, asChild = false, loading = false, icon, children, disabled, ...props },
  ref,
) {
  const Comp = asChild ? Slot : 'button';
  const dotSize = size === 'lg' ? 20 : 16;
  const dotTone = variant === 'primary' || variant === 'danger' ? 'current' : 'brand';

  // When asChild, Radix Slot requires a single child — skip the loading overlay.
  if (asChild) {
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      >
        {children}
      </Comp>
    );
  }

  return (
    <Comp
      ref={ref}
      className={cn(buttonVariants({ variant, size }), 'relative', className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading && (
        <span className="absolute inset-0 flex items-center justify-center">
          <DotPulse size={dotSize} tone={dotTone} />
        </span>
      )}
      <span className={cn('inline-flex items-center gap-2', loading && 'invisible')}>
        {icon}
        {children}
      </span>
    </Comp>
  );
});

export { buttonVariants };
