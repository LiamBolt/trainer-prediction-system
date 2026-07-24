import { Quote } from 'lucide-react';
import { cn } from '@/lib/cn';

/**
 * RationaleCard — §12.3. The single most important piece of text in the product:
 * one plain-English sentence naming the two strongest criteria, in body-lg at the
 * top of the detail rail.
 */
export function RationaleCard({ rationale, className }: { rationale: string; className?: string }) {
  return (
    <div
      className={cn('flex gap-3 rounded-md border border-hairline bg-surface-sunken p-4', className)}
    >
      <Quote size={16} className="mt-1 shrink-0 text-text-muted" aria-hidden="true" />
      <p className="text-body-lg text-ink">{rationale}</p>
    </div>
  );
}
