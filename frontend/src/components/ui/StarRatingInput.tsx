import { Star } from 'lucide-react';
import { cn } from '@/lib/cn';

/**
 * StarRatingInput — 1–5 with half steps, fully keyboard accessible (§10.4).
 * Implemented as an ARIA slider so arrow keys adjust and Home/End jump.
 */
export function StarRatingInput({
  value,
  onChange,
  disabled,
  id,
}: {
  value: number;
  onChange: (value: number) => void;
  disabled?: boolean;
  id?: string;
}) {
  const clamp = (v: number) => Math.max(1, Math.min(5, Math.round(v * 2) / 2));

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (disabled) return;
    let next: number | null = null;
    if (e.key === 'ArrowRight' || e.key === 'ArrowUp') next = clamp(value + 0.5);
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') next = clamp(value - 0.5);
    else if (e.key === 'Home') next = 1;
    else if (e.key === 'End') next = 5;
    if (next !== null) {
      e.preventDefault();
      onChange(next);
    }
  };

  return (
    <div className="flex items-center gap-3">
      <div
        id={id}
        role="slider"
        tabIndex={disabled ? -1 : 0}
        aria-valuemin={1}
        aria-valuemax={5}
        aria-valuenow={value}
        aria-valuetext={`${value.toFixed(1)} out of 5`}
        aria-label="Score awarded"
        onKeyDown={onKeyDown}
        className={cn(
          'inline-flex items-center gap-1 rounded-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring',
          disabled && 'cursor-not-allowed opacity-50',
        )}
      >
        {[1, 2, 3, 4, 5].map((star) => {
          const fill = Math.max(0, Math.min(1, value - (star - 1)));
          return (
            <span key={star} className="relative h-7 w-7">
              <Star size={28} className="absolute inset-0 shrink-0 text-primary-200 dark:text-primary-700" />
              <span
                className="absolute inset-0 overflow-hidden"
                style={{ width: `${fill * 100}%` }}
                aria-hidden="true"
              >
                <Star size={28} className="shrink-0 fill-warning-fg text-warning-fg" />
              </span>
              {!disabled && (
                <>
                  <button
                    type="button"
                    aria-label={`${star - 0.5} out of 5`}
                    onClick={() => onChange(star - 0.5)}
                    className="absolute inset-y-0 left-0 w-1/2"
                  />
                  <button
                    type="button"
                    aria-label={`${star} out of 5`}
                    onClick={() => onChange(star)}
                    className="absolute inset-y-0 right-0 w-1/2"
                  />
                </>
              )}
            </span>
          );
        })}
      </div>
      <span className="font-mono text-data-lg tabular-nums text-ink">
        {value.toFixed(1)}
        <span className="text-data text-text-muted"> / 5</span>
      </span>
    </div>
  );
}
