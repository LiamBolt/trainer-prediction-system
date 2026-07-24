import { forwardRef } from 'react';
import { cn } from '@/lib/cn';
import { inputBase } from './Input';
import { useField } from './Field';

/**
 * PhoneInput — fixed +256 prefix, formats the national number as typed
 * ("772 419 273"). Stored/emitted value is the full "+256 772 419 273" form (§8.8).
 */
export interface PhoneInputProps {
  value: string;
  onChange: (value: string) => void;
  id?: string;
  invalid?: boolean;
  disabled?: boolean;
  className?: string;
}

/** Extract the 9 national digits from any stored form. */
function toNationalDigits(value: string): string {
  const digits = value.replace(/\D/g, '');
  const withoutCountry = digits.startsWith('256') ? digits.slice(3) : digits.replace(/^0/, '');
  return withoutCountry.slice(0, 9);
}

function groupNational(digits: string): string {
  const parts = [digits.slice(0, 3), digits.slice(3, 6), digits.slice(6, 9)].filter(Boolean);
  return parts.join(' ');
}

export const PhoneInput = forwardRef<HTMLInputElement, PhoneInputProps>(function PhoneInput(
  { value, onChange, id, invalid, disabled, className },
  ref,
) {
  const field = useField();
  const hasError = invalid ?? field?.hasError ?? false;
  const national = toNationalDigits(value);

  return (
    <div className="relative flex items-center">
      <span className="pointer-events-none absolute left-0 flex h-10 items-center pl-3.5 font-mono text-body tabular-nums text-text-muted">
        +256
      </span>
      <input
        ref={ref}
        id={id ?? field?.id}
        type="tel"
        inputMode="tel"
        disabled={disabled}
        aria-invalid={hasError || undefined}
        value={groupNational(national)}
        onChange={(e) => {
          const digits = toNationalDigits(e.target.value);
          onChange(digits ? `+256 ${groupNational(digits)}` : '');
        }}
        className={cn(
          inputBase,
          'pl-14 font-mono',
          hasError ? 'border-danger-fg' : 'border-strong',
          className,
        )}
        placeholder="772 000 000"
      />
    </div>
  );
});
