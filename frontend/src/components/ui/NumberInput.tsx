import { forwardRef } from 'react';
import { Minus, Plus } from 'lucide-react';
import { cn } from '@/lib/cn';
import { useField } from './Field';

/**
 * NumberInput — integer stepper with tabular numerals. Steppers are 40px to
 * match the field height; the value is right-aligned like every other numeral.
 */
export interface NumberInputProps {
  value: number | '';
  onChange: (value: number | '') => void;
  min?: number;
  max?: number;
  step?: number;
  id?: string;
  invalid?: boolean;
  disabled?: boolean;
  suffix?: string;
  className?: string;
  'aria-label'?: string;
}

export const NumberInput = forwardRef<HTMLInputElement, NumberInputProps>(function NumberInput(
  { value, onChange, min, max, step = 1, id, invalid, disabled, suffix, className, ...aria },
  ref,
) {
  const field = useField();
  const hasError = invalid ?? field?.hasError ?? false;

  const clamp = (n: number) => {
    let out = n;
    if (typeof min === 'number') out = Math.max(min, out);
    if (typeof max === 'number') out = Math.min(max, out);
    return out;
  };

  const bump = (dir: 1 | -1) => {
    const current = value === '' ? (min ?? 0) : value;
    onChange(clamp(current + dir * step));
  };

  return (
    <div
      className={cn(
        'flex h-10 w-full items-center rounded-sm border bg-surface',
        hasError ? 'border-danger-fg' : 'border-strong',
        disabled && 'cursor-not-allowed opacity-50',
        className,
      )}
    >
      <button
        type="button"
        tabIndex={-1}
        aria-hidden="true"
        disabled={disabled}
        onClick={() => bump(-1)}
        className="flex h-full w-10 shrink-0 items-center justify-center text-text-muted hover:text-ink disabled:pointer-events-none"
      >
        <Minus size={16} className="shrink-0" />
      </button>
      <input
        ref={ref}
        id={id ?? field?.id}
        type="text"
        inputMode="numeric"
        disabled={disabled}
        aria-invalid={hasError || undefined}
        value={value === '' ? '' : value}
        onChange={(e) => {
          const raw = e.target.value.replace(/[^\d-]/g, '');
          if (raw === '' || raw === '-') return onChange('');
          const n = Number.parseInt(raw, 10);
          if (!Number.isNaN(n)) onChange(clamp(n));
        }}
        className="h-full min-w-0 flex-1 bg-transparent text-center text-body tabular-nums text-ink outline-none"
        {...aria}
      />
      {suffix && <span className="px-2 text-body-sm text-text-muted">{suffix}</span>}
      <button
        type="button"
        tabIndex={-1}
        aria-hidden="true"
        disabled={disabled}
        onClick={() => bump(1)}
        className="flex h-full w-10 shrink-0 items-center justify-center text-text-muted hover:text-ink disabled:pointer-events-none"
      >
        <Plus size={16} className="shrink-0" />
      </button>
    </div>
  );
});
