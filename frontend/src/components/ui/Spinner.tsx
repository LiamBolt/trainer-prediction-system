import { cn } from '@/lib/cn';

/**
 * <Spinner/> — a rotating ring of 10 dots stepping in shade from primary-200
 * (tail) to primary-900 (head), giving a comet trail as it turns. Inverted in
 * dark mode. Used for FULL-PANEL waits and the prediction run only. §10.2
 */
export interface SpinnerProps {
  size?: number;
  className?: string;
  label?: string;
}

const DOTS = 10;

export function Spinner({ size = 40, className, label = 'Loading' }: SpinnerProps) {
  const dot = Math.max(3, Math.round(size * 0.11));
  const radius = size / 2 - dot / 2;

  return (
    <span
      className={cn('tps-spinner relative inline-block', className)}
      style={{ width: size, height: size }}
      role="status"
      aria-label={label}
    >
      {Array.from({ length: DOTS }).map((_, i) => {
        const angle = (i / DOTS) * 2 * Math.PI;
        const x = radius + radius * Math.sin(angle);
        const y = radius - radius * Math.cos(angle);
        // Head is brightest; shade steps down around the ring.
        const shade = i / (DOTS - 1);
        return (
          <span
            key={i}
            className="tps-spinner-dot"
            style={{
              position: 'absolute',
              width: dot,
              height: dot,
              left: x,
              top: y,
              borderRadius: '9999px',
              background: `var(--spinner-shade)`,
              opacity: 0.25 + shade * 0.75,
            }}
          />
        );
      })}
      <style>{`
        .tps-spinner { --spinner-shade: #19154e; animation: tps-spin 1s linear infinite; }
        .dark .tps-spinner { --spinner-shade: #ecebf0; }
        @keyframes tps-spin { to { transform: rotate(360deg); } }
        @media (prefers-reduced-motion: reduce) {
          .tps-spinner { animation-duration: 2.4s; }
        }
      `}</style>
    </span>
  );
}
