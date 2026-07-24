import * as AvatarPrimitive from '@radix-ui/react-avatar';
import { cn } from '@/lib/cn';
import { initials as toInitials } from '@/lib/format';

/**
 * Avatar — generated initials on a primary-100 / dark primary-700 ground (§10.1).
 * No uploads anywhere (D8). Sizes 24/32/40 only (§5.3).
 */
export interface AvatarProps {
  name: string;
  size?: 24 | 32 | 40;
  className?: string;
}

const textForSize: Record<number, string> = {
  24: 'text-label',
  32: 'text-caption',
  40: 'text-body-sm',
};

export function Avatar({ name, size = 32, className }: AvatarProps) {
  return (
    <AvatarPrimitive.Root
      className={cn(
        'inline-flex shrink-0 select-none items-center justify-center overflow-hidden rounded-full ' +
          'bg-primary-100 text-primary-800 dark:bg-primary-700 dark:text-primary-100',
        className,
      )}
      style={{ width: size, height: size }}
    >
      {/* No image sources by design (D8) — always the initials fallback. */}
      <AvatarPrimitive.Fallback
        className={cn('font-mono font-semibold uppercase tabular-nums', textForSize[size])}
        delayMs={0}
      >
        {toInitials(name)}
      </AvatarPrimitive.Fallback>
    </AvatarPrimitive.Root>
  );
}
