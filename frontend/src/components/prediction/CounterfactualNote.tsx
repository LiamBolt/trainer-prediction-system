import { TrendingUp } from 'lucide-react';
import { cn } from '@/lib/cn';

/**
 * CounterfactualNote — §7.1/§12. The smallest single change that would lift this
 * trainer to rank 1 (ranks 2–5 only). Rendered only when the engine produced one;
 * never invented.
 */
export function CounterfactualNote({
  counterfactual,
  className,
}: {
  counterfactual: string | null;
  className?: string;
}) {
  if (!counterfactual) return null;
  return (
    <div
      className={cn(
        'flex items-start gap-2 rounded-sm border border-info-border bg-info-bg px-3 py-2 text-body-sm text-info-fg',
        className,
      )}
    >
      <TrendingUp size={16} className="mt-0.5 shrink-0" />
      <span>{counterfactual}</span>
    </div>
  );
}
