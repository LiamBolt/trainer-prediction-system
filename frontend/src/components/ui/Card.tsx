import { forwardRef } from 'react';
import { cn } from '@/lib/cn';

/**
 * Card — §5.2 padding law. Padding is exactly 24px desktop / 16px < 768px.
 * Header, body, and footer share the same horizontal padding so their left
 * edges form one unbroken vertical line. Dividers are full-bleed (§5.4).
 *
 * Compose as: <Card><CardHeader/><CardBody/><CardFooter/></Card>. The card
 * owns vertical padding via its children; each region owns px-4 md:px-6.
 */

const PAD_X = 'px-4 md:px-6'; // 16 / 24
const PAD_Y = 'py-4 md:py-6';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Lift on hover (e1 -> e2, -2px) — for interactive cards only (§4.4). */
  interactive?: boolean;
  /** Render with the glass treatment (allowed only per §4.5). */
  glass?: boolean;
}

export const Card = forwardRef<HTMLDivElement, CardProps>(function Card(
  { className, interactive, glass, children, ...props },
  ref,
) {
  return (
    <div
      ref={ref}
      className={cn(
        'flex h-full flex-col rounded-md',
        glass ? 'glass' : 'border border-hairline bg-surface shadow-e1',
        interactive &&
          'transition-[transform,box-shadow] duration-default ease-entry hover:-translate-y-[2px] hover:shadow-e2',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
});

export function CardHeader({
  className,
  children,
  divider = true,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { divider?: boolean }) {
  return (
    <div
      className={cn(
        PAD_X,
        'pt-4 md:pt-6',
        divider ? 'pb-4 md:pb-4 border-b border-hairline' : 'pb-0',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardTitle({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3 className={cn('text-h3 text-ink', className)} {...props}>
      {children}
    </h3>
  );
}

export function CardDescription({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={cn('mt-1 text-body-sm text-text-muted', className)} {...props}>
      {children}
    </p>
  );
}

export function CardBody({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn(PAD_X, PAD_Y, 'flex-1', className)} {...props}>
      {children}
    </div>
  );
}

export function CardFooter({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(PAD_X, 'flex items-center gap-3 border-t border-hairline pb-4 pt-4 md:pb-6', className)}
      {...props}
    >
      {children}
    </div>
  );
}
