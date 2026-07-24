import { cn } from '@/lib/cn';

/**
 * <DotPulse/> — matches the client-supplied loading.png: three dots, the centre
 * one 1.4x the outer ones, animating scale + opacity in a staggered 1.2s loop.
 * Used INLINE (inside buttons, beside "Saving…", in awaiting table cells). §10.2
 */
export interface DotPulseProps {
  size?: 16 | 20 | 24;
  className?: string;
  /** Inherit the current text colour (e.g. inside a primary button). */
  tone?: 'brand' | 'current';
}

export function DotPulse({ size = 20, className, tone = 'brand' }: DotPulseProps) {
  const outer = Math.round(size * 0.28);
  const centre = Math.round(outer * 1.4);
  const gap = Math.round(size * 0.16);
  const color = tone === 'current' ? 'currentColor' : 'rgb(var(--brand))';

  return (
    <span
      className={cn('inline-flex items-center', className)}
      style={{ gap }}
      role="status"
      aria-label="Loading"
    >
      {[0, 1, 2].map((i) => {
        const d = i === 1 ? centre : outer;
        return (
          <span
            key={i}
            className="tps-dotpulse-dot"
            style={{
              width: d,
              height: d,
              background: color,
              borderRadius: '9999px',
              display: 'inline-block',
              animationDelay: `${i * 160}ms`,
            }}
          />
        );
      })}
      <style>{`
        @keyframes tps-dotpulse {
          0%, 100% { transform: scale(0.7); opacity: 0.35; }
          40% { transform: scale(1); opacity: 1; }
        }
        .tps-dotpulse-dot { animation: tps-dotpulse 1.2s ease-in-out infinite; }
        @media (prefers-reduced-motion: reduce) {
          .tps-dotpulse-dot { animation: none; opacity: 0.7; }
        }
      `}</style>
    </span>
  );
}
