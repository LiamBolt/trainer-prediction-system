import { cn } from '@/lib/cn';

/**
 * Skeleton — the default for content loading (never a bare spinner, §5.7).
 * Compose these to match the real content's shape.
 */
export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('tps-skeleton rounded-sm bg-surface-sunken', className)}
      aria-hidden="true"
      {...props}
    >
      <style>{`
        .tps-skeleton { position: relative; overflow: hidden; }
        .tps-skeleton::after {
          content: ''; position: absolute; inset: 0;
          transform: translateX(-100%);
          background: linear-gradient(90deg, transparent, rgb(var(--ink) / 0.06), transparent);
          animation: tps-shimmer 1.4s infinite;
        }
        @keyframes tps-shimmer { 100% { transform: translateX(100%); } }
        @media (prefers-reduced-motion: reduce) { .tps-skeleton::after { animation: none; } }
      `}</style>
    </div>
  );
}

/** A line of skeleton text at a given width. */
export function SkeletonText({ className }: { className?: string }) {
  return <Skeleton className={cn('h-4 w-full', className)} />;
}
