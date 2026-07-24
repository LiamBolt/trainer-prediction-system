import { cn } from '@/lib/cn';
import { CREST_IMAGE_SRC } from '@/lib/assets';

/**
 * UPF crest. Renders the client's crest image when supplied (§15); otherwise a
 * dignified inline-SVG shield placeholder so nothing ever looks broken. Uses
 * currentColor so it inherits the surrounding ink / knockout colour.
 */
export interface CrestProps {
  size?: number;
  className?: string;
  title?: string;
}

export function Crest({ size = 32, className, title = 'Uganda Police Force' }: CrestProps) {
  if (CREST_IMAGE_SRC) {
    return (
      <img
        src={CREST_IMAGE_SRC}
        width={size}
        height={size}
        alt={title}
        className={cn('object-contain', className)}
      />
    );
  }
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 56"
      role="img"
      aria-label={title}
      className={cn('shrink-0', className)}
      fill="none"
    >
      <title>{title}</title>
      {/* Shield */}
      <path
        d="M24 2 L44 9 V27 C44 40 35 49 24 54 C13 49 4 40 4 27 V9 Z"
        fill="currentColor"
        fillOpacity="0.10"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      {/* Star */}
      <path
        d="M24 13 l2.6 5.7 6.2 .7 -4.6 4.2 1.2 6.1 -5.4 -3 -5.4 3 1.2 -6.1 -4.6 -4.2 6.2 -.7 Z"
        fill="currentColor"
      />
      {/* Twin bands */}
      <rect x="13" y="34" width="22" height="2.4" rx="1.2" fill="currentColor" />
      <rect x="15" y="40" width="18" height="2.4" rx="1.2" fill="currentColor" fillOpacity="0.7" />
    </svg>
  );
}
