import { cn } from '@/lib/cn';
import { Crest } from './Crest';
import { ORG_NAME, ORG_UNIT } from '@/lib/constants';

/**
 * Brand lockup — crest + wordmark. Until the client's knockout banner arrives
 * (§15) the wordmark is live text, legible on any ground.
 */
export interface WordmarkProps {
  variant?: 'full' | 'compact' | 'stacked';
  className?: string;
  crestSize?: number;
}

export function Wordmark({ variant = 'compact', className, crestSize }: WordmarkProps) {
  if (variant === 'stacked') {
    return (
      <div className={cn('flex flex-col items-start gap-3', className)}>
        <Crest size={crestSize ?? 56} />
        <div className="flex flex-col">
          <span className="font-display text-display-lg leading-none text-current">Trainer Prediction</span>
          <span className="font-display text-display-lg leading-none text-current">System</span>
          <span className="mt-2 font-mono text-label uppercase text-current opacity-80">{ORG_UNIT}</span>
        </div>
      </div>
    );
  }

  if (variant === 'full') {
    return (
      <div className={cn('flex items-center gap-3', className)}>
        <Crest size={crestSize ?? 36} />
        <div className="flex flex-col leading-tight">
          <span className="font-display text-h3 text-current">{ORG_NAME}</span>
          <span className="font-mono text-label uppercase text-current opacity-75">
            Trainer Prediction System
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <Crest size={crestSize ?? 28} />
      <div className="flex flex-col leading-none">
        <span className="font-display text-h3 tracking-tight text-current">TPS</span>
      </div>
    </div>
  );
}
