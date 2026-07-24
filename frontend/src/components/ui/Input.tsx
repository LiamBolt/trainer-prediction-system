import { forwardRef } from 'react';
import { cn } from '@/lib/cn';
import { useField } from './Field';

/**
 * Input — 40px tall (h-10) with 14px horizontal padding (px-3.5), a faithful
 * realisation of §5.2's "12px vertical, 14px horizontal" within the fixed-height
 * system. Focus uses the global focus ring; error swaps the border to danger so
 * the box model never shifts (§5.4, §5.6).
 */
export const inputBase =
  'h-10 w-full rounded-sm border bg-surface px-3.5 text-body text-ink tabular-nums ' +
  'placeholder:text-text-disabled transition-colors duration-micro ' +
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ' +
  'disabled:cursor-not-allowed disabled:opacity-50';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
  /** Optional leading adornment (e.g. an icon or a "+256" prefix). */
  leading?: React.ReactNode;
  trailing?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, invalid, leading, trailing, id, 'aria-describedby': describedBy, ...props },
  ref,
) {
  const field = useField();
  const controlId = id ?? field?.id;
  const hasError = invalid ?? field?.hasError ?? false;
  const described =
    describedBy ??
    ([field?.hasError ? field.errorId : null, field?.hasHelp ? field.helpId : null]
      .filter(Boolean)
      .join(' ') || undefined);

  const control = (
    <input
      ref={ref}
      id={controlId}
      aria-invalid={hasError || undefined}
      aria-describedby={described}
      className={cn(
        inputBase,
        hasError ? 'border-danger-fg' : 'border-strong',
        leading && 'pl-10',
        trailing && 'pr-10',
        className,
      )}
      {...props}
    />
  );

  if (!leading && !trailing) return control;

  return (
    <div className="relative">
      {leading && (
        <span className="pointer-events-none absolute left-0 top-0 flex h-10 w-10 items-center justify-center text-text-muted">
          {leading}
        </span>
      )}
      {control}
      {trailing && (
        <span className="absolute right-0 top-0 flex h-10 items-center justify-center pr-2 text-text-muted">
          {trailing}
        </span>
      )}
    </div>
  );
});
