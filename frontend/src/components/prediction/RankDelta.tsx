import { useEffect, useState } from 'react';
import { ChevronUp, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/cn';

/**
 * RankDelta — §12.6. Shows how far a row moved in the last re-rank (▲2 / ▼1) and
 * fades out after 4 seconds. `delta` is (oldRank − newRank): positive = moved up.
 */
export function RankDelta({ delta }: { delta: number }) {
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    setVisible(true);
    const id = setTimeout(() => setVisible(false), 4000);
    return () => clearTimeout(id);
  }, [delta]);

  if (delta === 0) return null;
  const up = delta > 0;
  return (
    <span
      className={cn(
        'inline-flex items-center gap-0.5 rounded-full px-1.5 font-mono text-label font-semibold tabular-nums transition-opacity duration-500',
        up ? 'bg-success-bg text-success-fg' : 'bg-danger-bg text-danger-fg',
        visible ? 'opacity-100' : 'opacity-0',
      )}
      aria-label={`Moved ${up ? 'up' : 'down'} ${Math.abs(delta)} ${Math.abs(delta) === 1 ? 'place' : 'places'}`}
    >
      {up ? <ChevronUp size={12} className="shrink-0" /> : <ChevronDown size={12} className="shrink-0" />}
      {Math.abs(delta)}
    </span>
  );
}
