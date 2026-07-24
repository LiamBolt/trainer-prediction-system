import { forwardRef, useEffect, useRef } from 'react';
import { cn } from '@/lib/cn';
import { useField } from './Field';

/**
 * Textarea — auto-grow with an optional character count (§10.1). Padding is the
 * exact §5.2 field value: 12px vertical, 14px horizontal.
 */
export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
  /** Show a live "n / max" counter; requires maxLength. */
  showCount?: boolean;
  autoGrow?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { className, invalid, showCount, autoGrow = true, maxLength, value, onChange, id, ...props },
  ref,
) {
  const field = useField();
  const innerRef = useRef<HTMLTextAreaElement | null>(null);
  const hasError = invalid ?? field?.hasError ?? false;
  const count = typeof value === 'string' ? value.length : 0;

  useEffect(() => {
    if (!autoGrow) return;
    const el = innerRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, [value, autoGrow]);

  const described =
    [field?.hasError ? field.errorId : null, field?.hasHelp ? field.helpId : null]
      .filter(Boolean)
      .join(' ') || undefined;

  return (
    <div className="flex flex-col">
      <textarea
        ref={(node) => {
          innerRef.current = node;
          if (typeof ref === 'function') ref(node);
          else if (ref) ref.current = node;
        }}
        id={id ?? field?.id}
        aria-invalid={hasError || undefined}
        aria-describedby={described}
        maxLength={maxLength}
        value={value}
        onChange={onChange}
        className={cn(
          'min-h-20 w-full resize-none rounded-sm border bg-surface px-3.5 py-3 text-body text-ink ' +
            'placeholder:text-text-disabled transition-colors duration-micro ' +
            'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ' +
            'disabled:cursor-not-allowed disabled:opacity-50',
          hasError ? 'border-danger-fg' : 'border-strong',
          className,
        )}
        {...props}
      />
      {showCount && maxLength && (
        <div className="mt-1.5 self-end font-mono text-label tabular-nums text-text-muted">
          {count} / {maxLength}
        </div>
      )}
    </div>
  );
});
